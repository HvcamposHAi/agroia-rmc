"""Camada A1 (fidelidade): censo → amostra → duas leituras → comparação → documentos → agregados.

Saídas em execucoes/<run_id>/a1/: processos.csv, campos.csv, documentos.csv, agregados.csv,
verificados.json, amostra.json, resumo.json.

Uso: python -m validacao.a1_fidelidade.executar --run-id RUN [--limite 10] [--sem-chrome]
"""

from __future__ import annotations

import argparse

import pandas as pd

from validacao import claude_chrome as cc
from validacao import estado
from validacao.a1_fidelidade import agregados, amostragem, censo, comparar_campos, comparar_documentos
from validacao.a1_fidelidade.extrator_chrome import ler_detalhe
from validacao.a1_fidelidade.extrator_playwright import ExtratorPortal
from validacao.comum import carregar_config, dir_execucao, ler_json, salvar_json
from validacao.dados import Snapshot
from validacao.estatistica.multiplos import cohen_kappa
from validacao.estatistica.proporcoes import wilson


def executar(run_id: str, cfg: dict | None = None, limite: int | None = None, usar_chrome: bool | None = None) -> dict:
    cfg = cfg or carregar_config()
    d = dir_execucao(run_id)
    dir_a1 = d / "a1"
    cache = dir_a1 / "cache"
    ev_dir = d / "evidencias" / "a1"
    dir_a1.mkdir(parents=True, exist_ok=True)
    snap = Snapshot(run_id)
    seed = int(cfg["execucao"]["seed"])
    usar_chrome = cfg["a1"].get("usar_extrator_chrome", True) if usar_chrome is None else usar_chrome

    with ExtratorPortal(cfg, cache) as ex:
        # A1.1 censo
        res_censo = censo.executar_censo(run_id, cfg, snap, ex, dir_a1)
        estado.evento(run_id, "a1", f"censo: completude {res_censo['global']['completude']}, "
                                    f"precisão {res_censo['global']['precisao_existencia']}")

        # A1.2 amostra estratificada (ano × modalidade) sobre P ∩ B
        proc = pd.read_csv(dir_a1 / "processos.csv")
        pop = proc[proc["status"] == "PRESENTE_AMBOS"]
        if cfg["a1"].get("somente_relevante_af", True):
            pop = pop[pop["relevante_af"] == True]  # noqa: E712
        itens = pop.to_dict("records")
        calc = amostragem.tamanho_amostra(len(itens), cfg["a1"]["confianca"], cfg["a1"]["margem"])
        n = int(cfg["a1"]["amostra_n"]) if cfg["a1"].get("amostra_n") else calc["n"]
        if limite:
            n = min(n, int(limite))
        amostra_arq = dir_a1 / "amostra.json"
        salva = ler_json(amostra_arq)
        if salva and salva.get("n") == n:
            amostra = salva["amostra"]
            estratos = salva["estratos"]
        else:
            sel, estratos = amostragem.sortear(itens, lambda x: f"{x['ano']}|{x.get('modalidade_base') or ''}", n, seed)
            amostra = [x["chave"] for x in sel]
            salvar_json(amostra_arq, {"calculo": calc, "n": n, "limite_piloto": limite, "seed": seed,
                                      "populacao": len(itens), "estratos": estratos, "amostra": amostra})
        estado.registrar_unidades(run_id, "a1_campos", amostra)
        estado.evento(run_id, "a1", f"amostra: n={n} (calculado {calc['n']}, N={len(itens)})")

        # Resolução de URLs e leitura Playwright
        anos = sorted({int(c.split("/")[-1]) for c in amostra})
        urls = {}
        for ano in anos:
            alvo = {c for c in amostra if c.endswith(f"/{ano}")}
            try:
                urls.update(ex.resolver_urls(ano, alvo))
            except Exception as e:  # noqa: BLE001
                estado.evento(run_id, "a1", f"resolução de URLs {ano} falhou: {str(e)[:150]}", "erro")
        det_pw = {}
        for chave in amostra:
            if chave not in urls:
                estado.marcar(run_id, "a1_campos", chave, "falhou", "URL do detalhe não resolvida", incrementar=True)
                continue
            try:
                det_pw[chave] = ex.detalhe(urls[chave], ev_dir / "paginas")
            except Exception as e:  # noqa: BLE001
                estado.marcar(run_id, "a1_campos", chave, "falhou", f"detalhe: {e}", incrementar=True)
        requisicoes_portal = ex.requisicoes

    # Segunda leitura (Claude in Chrome), com sonda e degradação automática
    det_ch, chrome_status = {}, {"usado": False, "degradado": False, "afetados": 0}
    if usar_chrome and det_pw:
        trab = dir_a1 / "chrome_work"
        if cc.garantir_conexao(cfg, trab, lambda m: estado.evento(run_id, "a1", m)):
            chrome_status["usado"] = True
            falhas_seguidas = 0
            for chave, det in det_pw.items():
                if falhas_seguidas >= 3:
                    chrome_status["degradado"] = True
                    chrome_status["afetados"] += 1
                    continue
                r = ler_detalhe(det["url"], cfg, trab, dir_a1 / "chrome")
                if r["status"] == "ERRO_INFRA_LIMITE":
                    # Leituras já feitas ficam em cache; --retomar lê só as que faltam.
                    chrome_status["interrompido_limite"] = True
                    estado.evento(run_id, "a1", "limite de uso do plano Claude: leituras pelo Chrome "
                                                "interrompidas; retome com --retomar", "aviso")
                    break
                if r["status"] == "OK":
                    det_ch[chave] = r["dados"]
                    falhas_seguidas = 0
                else:
                    falhas_seguidas += 1
                    chrome_status["afetados"] += 1
                    if falhas_seguidas == 3 and not cc.garantir_conexao(cfg, trab, lambda m: estado.evento(run_id, "a1", m)):
                        estado.evento(run_id, "a1", "extensão não reconectou: restante da amostra com leitura única", "aviso")
                    elif falhas_seguidas == 3:
                        falhas_seguidas = 0
                estado.evento(run_id, "a1", f"chrome {chave}: {r['status']}")
        else:
            chrome_status.update({"degradado": True, "afetados": len(det_pw)})
            estado.evento(run_id, "a1", "extensão indisponível: A1 com leitura única (Playwright)", "aviso")

    # Comparação campo a campo
    linhas, verificados = [], {}
    for chave, det in det_pw.items():
        p = snap.processo(chave)
        if p is None:
            continue
        ls = comparar_campos.comparar_processo(chave, p, det, det_ch.get(chave), cfg,
                                               ev_dir / "divergencias", cache)
        linhas += ls
        v = comparar_campos.processo_verificado(ls)
        verificados[chave] = {**v, "ano": int(chave.split("/")[-1]), "licitacao_id": int(p["licitacao"]["id"])}
        estado.marcar(run_id, "a1_campos", chave, "concluida",
                      f"{sum(l['status'] == 'CORRESPONDE' for l in ls)}/{len(ls)} campos")
    campos = pd.DataFrame(linhas)
    campos.to_csv(dir_a1 / "campos.csv", index=False, encoding="utf-8")

    # A1.3 documentos e A1.4 agregados
    res_docs = comparar_documentos.comparar(run_id, cfg, snap, det_pw, dir_a1, cache)
    res_agr = agregados.calcular(snap, dir_a1, cfg["fontes"]["anos"])

    # Anos aptos para tarefas agregadas da A2 (completude do censo)
    anos_aptos = [int(a) for a, m in res_censo["por_ano"].items()
                  if m["completude"] is not None and m["completude"] >= cfg["a1"]["completude_min_ano_a2"]]
    salvar_json(dir_a1 / "verificados.json", {"processos": verificados, "anos_aptos": sorted(anos_aptos),
                                              "criterio_ano": cfg["a1"]["completude_min_ano_a2"]})

    resumo = resumir(campos, cfg)
    resumo.update({"censo": res_censo, "documentos": res_docs, "agregados": res_agr, "chrome": chrome_status,
                   "amostra_n": n, "amostra_calculo": calc, "amostra_lida": len(det_pw),
                   "requisicoes_portal": requisicoes_portal,
                   "verificados_todos_campos_a2": sum(1 for v in verificados.values() if v["todos_campos_a2"]),
                   "anos_aptos_a2": sorted(anos_aptos)})
    salvar_json(dir_a1 / "resumo.json", resumo)
    return resumo


def resumir(campos: pd.DataFrame, cfg: dict) -> dict:
    if campos.empty:
        return {"por_campo": {}, "global": None}
    conf = 1 - cfg["estatistica"]["alfa"]
    principal = campos[(campos["tipo"] != "derivado") & (campos["status"] != "DIVERGENCIA_EXTRACAO")]
    por_campo = {}
    for campo, g in campos.groupby("campo"):
        gp = g[g["status"] != "DIVERGENCIA_EXTRACAO"]
        k = int((gp["status"] == "CORRESPONDE").sum())
        por_campo[campo] = {**wilson(k, len(gp), conf), "divergencia_extracao": int((g["status"] == "DIVERGENCIA_EXTRACAO").sum()),
                            "f1_medio": float(g["f1"].dropna().mean()) if g["f1"].notna().any() else None,
                            "lev_medio": float(g["similaridade_lev"].dropna().mean()) if g["similaridade_lev"].notna().any() else None,
                            "por_origem": {o: wilson(int((go["status"] == "CORRESPONDE").sum()), len(go), conf)
                                           for o, go in gp.groupby("origem")}}
    k = int((principal["status"] == "CORRESPONDE").sum())
    dupla = campos[campos["concordancia_extratores"].notna()]
    kappas = {}
    for c in comparar_campos.CATEGORICOS:
        g = dupla[dupla["campo"] == c]
        kappas[c] = cohen_kappa(list(g["valor_playwright"]), list(g["valor_chrome"])) if len(g) else None
    return {"por_campo": por_campo, "global": wilson(k, len(principal), conf),
            "global_por_origem": {o: wilson(int((g["status"] == "CORRESPONDE").sum()), len(g), conf)
                                  for o, g in principal.groupby("origem")},
            "divergencia_extracao_total": int((campos["status"] == "DIVERGENCIA_EXTRACAO").sum()),
            "concordancia_extratores": (float(dupla["concordancia_extratores"].astype(bool).mean()) if len(dupla) else None),
            "concordancia_n": int(len(dupla)), "kappa_categoricos": kappas}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--limite", type=int)
    ap.add_argument("--sem-chrome", action="store_true")
    a = ap.parse_args()
    r = executar(a.run_id, limite=a.limite, usar_chrome=False if a.sem_chrome else None)
    print({k: r[k] for k in ("global", "amostra_n", "amostra_lida", "chrome")})


if __name__ == "__main__":
    main()
