"""Orquestrador da validação autônoma.

  python -m validacao.run_all --etapas snapshot,a1,a2,b,relatorios [--reusar RUN_ID] [--retomar RUN_ID]
  opções: --a1-limite N (piloto da A1) --a2-piloto --b-piloto --a2-instancias N --b-reps K --sem-chrome

- Checagens de saúde no início; falha crítica aborta tudo, falha não crítica bloqueia só as
  etapas que dependem dela.
- Falha em uma etapa nunca interrompe as seguintes; ao final os relatórios são sempre gerados
  com o que houver, marcando as etapas incompletas.
- --retomar reaproveita o run_id: cada unidade já concluída (SQLite) é pulada.
"""

from __future__ import annotations

import argparse
import copy
import os
import traceback

import yaml

from validacao import estado
from validacao.comum import (CONFIG_PADRAO, carimbo, carregar_config, carregar_env, dir_execucao, git_info,
                             ler_json, novo_run_id, salvar_json, sha256_arquivo, versoes)

ORDEM = ["snapshot", "a1", "a2", "b", "relatorios"]


def _manifesto(run_id: str) -> dict:
    return ler_json(dir_execucao(run_id) / "manifesto.json", {}) or {}


def _salvar_manifesto(run_id: str, m: dict) -> None:
    salvar_json(dir_execucao(run_id) / "manifesto.json", m)


def _impedir_suspensao() -> None:
    """Pede ao Windows para não suspender o sistema enquanto este processo roda (a suspensão
    congela downloads e sessões do navegador). O pedido termina junto com o processo."""
    if os.name == "nt":
        try:
            import ctypes
            ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        except Exception:
            pass


def executar(etapas: list[str], run_id: str | None = None, reusar: str | None = None, opcoes: dict | None = None) -> str:
    _impedir_suspensao()
    carregar_env()
    opcoes = opcoes or {}
    cfg = carregar_config()
    if opcoes.get("a2_instancias"):
        cfg["a2"]["instancias_por_modelo"] = int(opcoes["a2_instancias"])
    if opcoes.get("b_reps"):
        cfg["b"]["repeticoes"] = int(opcoes["b_reps"])
    run_id = run_id or novo_run_id()
    d = dir_execucao(run_id)
    etapas = [e for e in ORDEM if e in etapas]
    estado.criar_execucao(run_id, etapas, opcoes, os.getpid())
    m = _manifesto(run_id)
    m.update({"run_id": run_id, "etapas": etapas, "opcoes": opcoes, "git": git_info(), "versoes": versoes(),
              "config_sha256": sha256_arquivo(CONFIG_PADRAO), "config": copy.deepcopy(cfg),
              "preregistro": _prereg()})
    m.setdefault("inicio", carimbo())
    m.setdefault("etapas_concluidas", [])
    m.setdefault("erros", {})
    _salvar_manifesto(run_id, m)
    (d / "config_usado.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    estado.evento(run_id, "orquestrador", f"execução {run_id}: etapas {etapas}")

    from validacao.saude.checagens import rodar
    precisa_chrome = ("a2" in etapas) or ("a1" in etapas and not opcoes.get("sem_chrome"))
    saude = rodar(cfg, incluir_chrome=precisa_chrome)
    m["saude"] = saude
    _salvar_manifesto(run_id, m)
    for c in saude["checagens"]:
        estado.evento(run_id, "saude", f"{'ok' if c['ok'] else 'FALHA'} {c['nome']}: {c['mensagem']}",
                      "info" if c["ok"] else "aviso")
    if saude["abortar"]:
        estado.evento(run_id, "orquestrador", "pré-requisito crítico falhou: execução abortada", "erro")
        estado.status_execucao(run_id, "abortada")
        return run_id
    bloqueadas = set(saude["etapas_bloqueadas"])
    if "a1_chrome" in bloqueadas and "a1" in etapas:
        opcoes["sem_chrome"] = True       # A1 degrada para leitura única (seção 2.1)

    for etapa in etapas:
        if etapa == "relatorios":
            continue
        if etapa in bloqueadas:
            m["erros"][etapa] = f"bloqueada por pré-requisito: {sorted(bloqueadas)}"
            estado.evento(run_id, etapa, m["erros"][etapa], "erro")
            continue
        if etapa in m["etapas_concluidas"] and opcoes.get("retomando"):
            continue
        estado.evento(run_id, etapa, "início")
        try:
            if etapa == "snapshot":
                from validacao.snapshot import congelar
                info = congelar.reusar(run_id, reusar) if reusar else congelar.congelar(run_id, cfg)
                m["snapshot"] = {"hash_agregado": info["hash_agregado"], "reusado_de": info.get("reusado_de"),
                                 "linhas": {t: v["linhas"] for t, v in info["tabelas"].items()}}
            elif etapa == "a1":
                from validacao.a1_fidelidade.executar import executar as a1
                a1(run_id, cfg, limite=opcoes.get("a1_limite"), usar_chrome=False if opcoes.get("sem_chrome") else None)
            elif etapa == "a2":
                from validacao.a2_facilitacao.executor_chrome import executar as a2
                a2(run_id, cfg, piloto=bool(opcoes.get("a2_piloto")))
            elif etapa == "b":
                from validacao.b_benchmark.executar import executar as b
                b(run_id, cfg, piloto=bool(opcoes.get("b_piloto")))
            m["etapas_concluidas"].append(etapa)
            estado.etapa_concluida(run_id, etapa)
            estado.evento(run_id, etapa, "concluída")
        except Exception as e:  # noqa: BLE001 — falha de etapa não interrompe as seguintes
            m["erros"][etapa] = f"{type(e).__name__}: {e}"
            (d / f"erro_{etapa}.txt").write_text(traceback.format_exc(), encoding="utf-8")
            estado.evento(run_id, etapa, f"falhou: {str(e)[:300]}", "erro")
        _salvar_manifesto(run_id, m)

    m["fim"] = carimbo()
    _salvar_manifesto(run_id, m)
    if "relatorios" in etapas:
        try:
            from validacao.relatorios.gerar import gerar
            m["relatorios"] = gerar(run_id, cfg=cfg)
            m["etapas_concluidas"].append("relatorios")
            estado.etapa_concluida(run_id, "relatorios")
            estado.evento(run_id, "relatorios", f"gerados: {', '.join(m['relatorios'])}")
        except Exception as e:  # noqa: BLE001
            m["erros"]["relatorios"] = f"{type(e).__name__}: {e}"
            (d / "erro_relatorios.txt").write_text(traceback.format_exc(), encoding="utf-8")
            estado.evento(run_id, "relatorios", f"falhou: {e}", "erro")
        _salvar_manifesto(run_id, m)
    status = "concluida" if not m["erros"] else "concluida_com_falhas"
    estado.status_execucao(run_id, status)
    estado.evento(run_id, "orquestrador", f"fim: {status}")
    return run_id


def _prereg() -> dict:
    from validacao.comum import RAIZ_VALIDACAO
    arqs = sorted((RAIZ_VALIDACAO / "preregistro").glob("hipoteses_v*.md"))
    if not arqs:
        return {}
    a = arqs[-1]
    reg = a.with_suffix(".sha256")
    sha_reg = reg.read_text(encoding="utf-8").split()[0] if reg.exists() else None
    return {"arquivo": a.name, "sha256_registrado": sha_reg, "sha256_atual": sha256_arquivo(a),
            "integro": sha_reg == sha256_arquivo(a) if sha_reg else None}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--etapas", default="snapshot,a1,a2,b,relatorios")
    ap.add_argument("--reusar", help="run_id cujo snapshot será reutilizado")
    ap.add_argument("--retomar", help="run_id a retomar do checkpoint")
    ap.add_argument("--run-id")
    ap.add_argument("--a1-limite", type=int)
    ap.add_argument("--a2-piloto", action="store_true")
    ap.add_argument("--b-piloto", action="store_true")
    ap.add_argument("--a2-instancias", type=int)
    ap.add_argument("--b-reps", type=int)
    ap.add_argument("--sem-chrome", action="store_true")
    a = ap.parse_args()
    opcoes = {k: v for k, v in {"a1_limite": a.a1_limite, "a2_piloto": a.a2_piloto, "b_piloto": a.b_piloto,
                                "a2_instancias": a.a2_instancias, "b_reps": a.b_reps,
                                "sem_chrome": a.sem_chrome}.items() if v}
    etapas = [e.strip() for e in a.etapas.split(",") if e.strip()]
    run_id = a.retomar or a.run_id
    if a.retomar:
        anterior = estado.obter_execucao(a.retomar) or {}
        etapas = anterior.get("etapas") or etapas
        opcoes = {**(anterior.get("opcoes") or {}), **opcoes, "retomando": True}
    print(executar(etapas, run_id=run_id, reusar=a.reusar, opcoes=opcoes))


if __name__ == "__main__":
    main()
