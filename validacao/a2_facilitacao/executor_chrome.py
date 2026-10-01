"""Camada A2: executa cada tarefa instanciada nas condições PORTAL e AGROIA com o agente
Claude Code + Claude in Chrome (seções 4.2.1 e 4.4).

- Mesmo agente, modelo, orçamento, prompt-base e formato de resposta nas duas condições.
- k repetições por tarefa e condição; ordem aleatorizada com semente, condições intercaladas.
- Aquecimento do backend antes de cada execução AGROIA (latência registrada à parte).
- ERRO_INFRA / ERRO_INFRA_CHROME: repetida até 2 vezes (regra de exclusão 4.2.7).
- Cada execução roda em diretório próprio, sem CLAUDE.md do projeto.

Uso: python -m validacao.a2_facilitacao.executor_chrome --run-id RUN [--piloto]
"""

from __future__ import annotations

import argparse
import random
import shutil
import time
from pathlib import Path

import pandas as pd
import requests

from validacao import claude_chrome as cc
from validacao import estado
from validacao.a2_facilitacao import parser_log, pontuacao
from validacao.a2_facilitacao.tarefas.instanciar import instanciar
from validacao.comum import (RAIZ_VALIDACAO, aquecer_backend, carimbo, carregar_config, dir_execucao,
                             ler_json, salvar_json)
from validacao.dados import Snapshot

CONDICOES = ("PORTAL", "AGROIA")
PROMPTS = RAIZ_VALIDACAO / "a2_facilitacao" / "prompts"
INSTRUCAO_GIF = ("- Grave a sessão com a ferramenta gif_creator: inicie a gravação antes da primeira "
                 "navegação e, ao final, exporte o GIF com o nome {nome}.gif.\n")


def montar_prompt(inst: dict, condicao: str, cfg: dict, nome_gif: str) -> str:
    f = cfg["fontes"]
    if condicao == "PORTAL":
        url, doms = f["portal_url"], f["portal_dominios"] + f["ceasa_pr_dominios"]
        modelo = (PROMPTS / "condicao_portal.md").read_text(encoding="utf-8")
    else:
        url, doms = f["agroia_front_url"], f["agroia_front_dominios"]
        modelo = (PROMPTS / "condicao_agroia.md").read_text(encoding="utf-8")
    gif = INSTRUCAO_GIF.format(nome=nome_gif) if cfg["a2"].get("gravar_gif") else ""
    return (modelo.replace("{URL_INICIAL}", url).replace("{LISTA_DOMINIOS}", ", ".join(doms))
            .replace("{ENUNCIADO}", inst["enunciado"]).replace("{INSTRUCAO_GIF}", gif))


def aquecer(cfg: dict) -> float | None:
    """Acorda o backend (espera /health) e carrega o frontend; o tempo fica fora da tarefa."""
    t = time.monotonic()
    pronto = aquecer_backend(cfg["fontes"]["agroia_api_url"], int(cfg["a2"].get("aquecimento_timeout_s", 300)))
    try:
        requests.get(cfg["fontes"]["agroia_front_url"], timeout=30)
    except Exception:
        pass
    return round(time.monotonic() - t, 2) if pronto is not None else None


def mover_gif(cfg: dict, nome: str, destino: Path, desde: float) -> str | None:
    pasta = Path(cfg["a2"].get("chrome_downloads", "~/Downloads")).expanduser()
    if not pasta.exists():
        return None
    cands = [p for p in pasta.glob(f"{nome}*.gif") if p.stat().st_mtime >= desde - 5]
    if not cands:
        return None
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(max(cands, key=lambda p: p.stat().st_mtime)), destino)
    return str(destino)


def plano_execucoes(instancias: list[dict], reps: int, seed: int) -> list[dict]:
    rng = random.Random(seed + 1)
    unidades = [{"inst": i, "condicao": c, "rep": r} for i in instancias for r in range(1, reps + 1) for c in CONDICOES]
    rng.shuffle(unidades)
    # Intercala condições: alterna PORTAL/AGROIA preservando a ordem sorteada dentro de cada uma.
    por = {c: [u for u in unidades if u["condicao"] == c] for c in CONDICOES}
    out = []
    while por["PORTAL"] or por["AGROIA"]:
        for c in CONDICOES:
            if por[c]:
                out.append(por[c].pop(0))
    return out


def chave_unidade(u: dict) -> str:
    return f"{u['inst']['id']}|{u['condicao']}|{u['rep']}"


def executar(run_id: str, cfg: dict | None = None, piloto: bool = False) -> dict:
    cfg = cfg or carregar_config()
    d = dir_execucao(run_id)
    dir_a2 = d / "a2"
    dir_a2.mkdir(parents=True, exist_ok=True)
    snap = Snapshot(run_id)
    inst = instanciar(run_id, snap, cfg)
    instancias = inst["instancias"]
    reps = int(cfg["a2"]["repeticoes"])
    if piloto:
        # Piloto: n tarefas de modelos distintos × 2 condições × 1 repetição.
        vistos, sel = set(), []
        for i in instancias:
            if i["modelo"] not in vistos:
                vistos.add(i["modelo"])
                sel.append(i)
        instancias, reps = sel[: int(cfg["a2"]["piloto_n_tarefas"])], 1
    plano = plano_execucoes(instancias, reps, int(cfg["execucao"]["seed"]))
    etapa = "a2_piloto" if piloto else "a2"
    estado.registrar_unidades(run_id, etapa, [chave_unidade(u) for u in plano])
    feitas = {u["chave"] for u in estado.unidades(run_id, etapa, "concluida")}
    estado.evento(run_id, "a2", f"{len(plano)} execuções planejadas ({len(feitas)} já concluídas)")

    work = dir_a2 / "work"
    chrome_ok = cc.garantir_conexao(cfg, work / "_sonda", lambda m: estado.evento(run_id, "a2", m))
    desde_sonda = 0
    incompleta = False
    for pos, u in enumerate(plano, 1):
        ch = chave_unidade(u)
        if ch in feitas:
            continue
        if not chrome_ok:
            _registrar(run_id, etapa, dir_a2, u, {"status": "ERRO_INFRA_CHROME", "duracao_s": 0}, None, None, None)
            continue
        if desde_sonda >= 10:
            chrome_ok = cc.garantir_conexao(cfg, work / "_sonda", lambda m: estado.evento(run_id, "a2", m))
            desde_sonda = 0
            if not chrome_ok:
                estado.evento(run_id, "a2", "extensão não reconectou: restante marcado ERRO_INFRA_CHROME", "erro")
                _registrar(run_id, etapa, dir_a2, u, {"status": "ERRO_INFRA_CHROME", "duracao_s": 0}, None, None, None)
                continue
        desde_sonda += 1
        estado.evento(run_id, "a2", f"[{pos}/{len(plano)}] {ch}")
        base = ch.replace("|", "_")
        for tentativa in range(3):
            aquec = aquecer(cfg) if u["condicao"] == "AGROIA" else None
            nome_gif = f"agroia_{run_id}_{base}_t{tentativa}"
            t0 = time.time()
            saida = dir_a2 / "logs" / f"{base}_t{tentativa}.jsonl"
            meta = cc.executar(montar_prompt(u["inst"], u["condicao"], cfg, nome_gif), cfg,
                               work / f"{base}_t{tentativa}", saida, int(cfg["a2"]["timeout_tarefa_s"]))
            negou = parser_log.analisar(saida).get("navegacao_negada") if meta["status"] == "OK" else 0
            if meta["status"] not in ("ERRO_INFRA", "ERRO_INFRA_CHROME") and not negou:
                break
            estado.evento(run_id, "a2", f"{ch}: {meta['status']} (tentativa {tentativa + 1}/3)", "aviso")
        if meta["status"] == "ERRO_INFRA_LIMITE":
            # Não registra: a execução fica pendente e --retomar a refaz quando o plano liberar.
            estado.evento(run_id, "a2", f"{ch}: limite de uso do plano Claude; etapa interrompida, "
                                        "retome com --retomar", "aviso")
            incompleta = True
            break
        gif = mover_gif(cfg, nome_gif, d / "evidencias" / "a2" / f"{base}.gif", t0) if cfg["a2"].get("gravar_gif") else None
        _registrar(run_id, etapa, dir_a2, u, meta, saida, aquec, gif, tentativa)
    res = consolidar(run_id, etapa)
    res["incompleta"] = incompleta
    return res


def pontuar_execucao(inst: dict, saida: Path | None, status_exec: str) -> tuple[dict, dict]:
    """Métricas do log + correção contra o gabarito (mesma regra em todas as execuções)."""
    met = parser_log.analisar(saida) if saida and Path(saida).exists() else {}
    pt = pontuacao.pontuar(inst, met.get("texto_final", ""), status_exec)
    # Site sem permissão na extensão: o agente não chegou a medir nada (infraestrutura).
    if met.get("navegacao_negada") and pt["desfecho"] != "CORRETO":
        pt.update({"desfecho": "ERRO_INFRA_PERMISSAO", "sucesso": 0, "pontuacao": 0.0,
                   "motivo": f"{met['navegacao_negada']} navegações negadas pela extensão (site sem permissão)"})
    if status_exec == "OK" and met.get("subtipo_resultado") == "error_max_turns" and pt["desfecho"] == "INCORRETO" \
            and pt["motivo"] == "FORMATO":
        pt["desfecho"], pt["motivo"] = "TIMEOUT", "orçamento de turnos esgotado"
    return met, pt


def _registrar(run_id, etapa, dir_a2, u, meta, saida, aquec, gif, tentativa=0):
    met, pt = pontuar_execucao(u["inst"], saida, meta["status"])
    linha = {"chave": chave_unidade(u), "instancia": u["inst"]["id"], "modelo": u["inst"]["modelo"],
             "tipo": u["inst"]["tipo"], "condicao": u["condicao"], "rep": u["rep"],
             "status_exec": meta["status"], "tentativas": tentativa + 1,
             "desfecho": pt["desfecho"], "sucesso": pt["sucesso"], "pontuacao": pt["pontuacao"],
             "motivo": pt["motivo"], "tempo_s": meta.get("duracao_s"), "aquecimento_s": aquec,
             "gif": gif, "log": str(saida.name) if saida else None,
             **{k: met.get(k) for k in ("n_acoes", "n_paginas", "n_documentos", "tokens_entrada", "tokens_saida",
                                        "turnos", "custo_usd", "tempo_humano_klm_s", "chars_lidos", "usou_chat",
                                        "ferramentas_negadas", "navegacao_negada")},
             "n_acoes_por_tipo": met.get("n_acoes_por_tipo"), "resposta": pt.get("resposta_json"),
             "fim": carimbo()}
    estado.marcar(run_id, etapa, linha["chave"], "concluida", f"{linha['desfecho']}", dados=linha, incrementar=True)
    estado.evento(run_id, "a2", f"{linha['chave']}: {linha['desfecho']} ({linha['n_acoes']} ações, {linha['tempo_s']} s)")


def consolidar(run_id: str, etapa: str = "a2") -> dict:
    """Junta as execuções e RECALCULA a correção a partir dos logs com a regra vigente, para
    que uma calibração da pontuação valha igual para todas as execuções e as duas condições."""
    d = dir_execucao(run_id) / "a2"
    insts = {i["id"]: i for i in (ler_json(d / "instancias.json", {}) or {}).get("instancias", [])}
    linhas = []
    for u in estado.unidades(run_id, etapa):
        dados = u.get("dados")
        if not dados:
            continue
        inst = insts.get(dados.get("instancia"))
        if inst and dados.get("log"):
            _, pt = pontuar_execucao(inst, d / "logs" / dados["log"], dados.get("status_exec") or "OK")
            dados = {**dados, "desfecho": pt["desfecho"], "sucesso": pt["sucesso"], "pontuacao": pt["pontuacao"],
                     "motivo": pt["motivo"], "resposta": pt.get("resposta_json")}
        linhas.append(dados)
    df = pd.DataFrame(linhas)
    nome = "execucoes.csv" if etapa == "a2" else "execucoes_piloto.csv"
    if not df.empty:
        df.to_csv(d / nome, index=False, encoding="utf-8")
    from validacao.a2_facilitacao.analise import analisar
    res = analisar(run_id, df, carregar_config(), sufixo="" if etapa == "a2" else "_piloto")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--piloto", action="store_true")
    a = ap.parse_args()
    r = executar(a.run_id, piloto=a.piloto)
    print({k: r.get(k) for k in ("n_execucoes", "hipoteses")})


if __name__ == "__main__":
    main()
