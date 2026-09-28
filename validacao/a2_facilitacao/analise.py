"""Análise estatística da A2 (seção 4.2.6), conforme o pré-registro.

- Sucesso por tarefa e condição = maioria das repetições (principal) e proporção (sensibilidade).
- H1: McNemar exato; H2/H3: Wilcoxon pareado (+ r e δ de Cliff); H4: descritiva por tipo;
  H5: Wilson + Fisher exato; Holm sobre H1, H2, H3 e H5.
- Exclusões (4.2.7): ERRO_INFRA* persistente sai nas duas condições (pareamento);
  BLOQUEADO e TIMEOUT contam como insucesso na principal e são excluídos na sensibilidade.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from validacao.comum import dir_execucao, salvar_json
from validacao.estatistica.multiplos import holm
from validacao.estatistica.pareados import (cliff_delta, fisher_exato, magnitude_cliff, mcnemar_exato,
                                            tabela_2x2, wilcoxon_pareado)
from validacao.estatistica.proporcoes import wilson

INFRA = {"ERRO_INFRA", "ERRO_INFRA_CHROME", "ERRO_INFRA_PERMISSAO"}
NAO_MEDIDO = {"BLOQUEADO", "TIMEOUT"}


def _decisao(p_holm, efeito_ok: bool, alfa: float) -> str:
    if p_holm is None:
        return "inconclusiva"
    if p_holm < alfa:
        return "sustentada" if efeito_ok else "não sustentada"
    return "inconclusiva"


def analisar(run_id: str, df: pd.DataFrame, cfg: dict, sufixo: str = "") -> dict:
    alfa = cfg["estatistica"]["alfa"]
    conf = 1 - alfa
    d = dir_execucao(run_id) / "a2"
    res: dict = {"n_execucoes": int(len(df))}
    if df.empty:
        salvar_json(d / f"testes{sufixo}.json", res)
        return res
    df = df.copy()
    df["sucesso"] = df["sucesso"].fillna(0).astype(int)

    # Exclusão pareada por infraestrutura
    excl = sorted(df.loc[df["desfecho"].isin(INFRA), "instancia"].unique())
    base = df[~df["instancia"].isin(excl)]
    res["excluidas_infra"] = excl

    def agregar(sub: pd.DataFrame) -> pd.DataFrame:
        g = sub.groupby(["instancia", "modelo", "tipo", "condicao"])
        out = g.agg(n=("sucesso", "size"), sucessos=("sucesso", "sum"),
                    n_acoes_med=("n_acoes", "median"), klm_med=("tempo_humano_klm_s", "median"),
                    tempo_med=("tempo_s", "median"), paginas_med=("n_paginas", "median"),
                    docs_med=("n_documentos", "median"),
                    desfechos=("desfecho", lambda s: sorted(set(s)))).reset_index()
        out["prop_sucesso"] = out["sucessos"] / out["n"]
        out["sucesso_maioria"] = (out["sucessos"] > out["n"] / 2).astype(int)
        out["consistente"] = out["desfechos"].map(len) == 1
        return out

    tarefas = agregar(base)
    tarefas.to_csv(d / f"tarefas{sufixo}.csv", index=False, encoding="utf-8")
    res["tarefas"] = int(tarefas["instancia"].nunique())
    res["consistencia_intracondicao"] = {c: float(g["consistente"].mean()) for c, g in tarefas.groupby("condicao")}
    res["sucesso_por_condicao"] = {c: wilson(int(g["sucesso"].sum()), len(g), conf) for c, g in base.groupby("condicao")}
    res["sucesso_tarefa_por_condicao"] = {c: wilson(int(g["sucesso_maioria"].sum()), len(g), conf)
                                          for c, g in tarefas.groupby("condicao")}

    piv = tarefas.pivot_table(index="instancia", columns="condicao", values="sucesso_maioria")
    piv = piv.dropna()
    pvals, h = {}, {}
    # H1 eficácia
    if {"AGROIA", "PORTAL"} <= set(piv.columns) and len(piv):
        t = tabela_2x2(list(piv["AGROIA"].astype(int)), list(piv["PORTAL"].astype(int)))
        m = mcnemar_exato(t["n10"], t["n01"], conf)
        h["H1"] = {"tabela": t, **m, "prop_agroia": float(piv["AGROIA"].mean()), "prop_portal": float(piv["PORTAL"].mean())}
        pvals["H1"] = m["p_valor"]
        # sensibilidade: proporção de sucesso nas repetições, Wilcoxon
        pp = tarefas.pivot_table(index="instancia", columns="condicao", values="prop_sucesso").dropna()
        h["H1"]["sensibilidade_proporcao"] = wilcoxon_pareado(list(pp["AGROIA"]), list(pp["PORTAL"]))

    # H2 (ações) e H3 (KLM)
    max_turns = int(cfg["a2"]["max_turns"])
    for hid, col, teto in (("H2", "n_acoes_med", max_turns), ("H3", "klm_med", None)):
        ok = tarefas.pivot_table(index="instancia", columns="condicao", values="sucesso_maioria")
        val = tarefas.pivot_table(index="instancia", columns="condicao", values=col)
        if not ({"AGROIA", "PORTAL"} <= set(val.columns)):
            continue
        ambos = ok.dropna()
        ambos = ambos[(ambos["AGROIA"] == 1) & (ambos["PORTAL"] == 1)].index
        v = val.loc[val.index.intersection(ambos)].dropna()
        w = wilcoxon_pareado(list(v["AGROIA"]), list(v["PORTAL"]))
        cd = cliff_delta(list(v["AGROIA"]), list(v["PORTAL"]))
        # sensibilidade: todas as tarefas, falha recebe o orçamento máximo
        vv = val.copy()
        teto_v = teto if teto is not None else float(np.nanmax(vv.values)) if vv.size else None
        for c in ("AGROIA", "PORTAL"):
            vv.loc[ok[c] != 1, c] = teto_v
        vv = vv.dropna()
        ws = wilcoxon_pareado(list(vv["AGROIA"]), list(vv["PORTAL"]))
        h[hid] = {**w, "cliff": cd, "cliff_magnitude": magnitude_cliff(cd),
                  "mediana_agroia": float(v["AGROIA"].median()) if len(v) else None,
                  "mediana_portal": float(v["PORTAL"].median()) if len(v) else None,
                  "sensibilidade": {**ws, "cliff": cliff_delta(list(vv["AGROIA"]), list(vv["PORTAL"])), "teto": teto_v}}
        pvals[hid] = w["p_valor"] if w["n_nao_nulos"] else None

    # H4 cobertura por tipo (descritiva)
    cob = tarefas.groupby(["tipo", "condicao"])["sucessos"].sum().unstack(fill_value=0)
    h["H4"] = {"por_tipo": {t: {c: bool(cob.loc[t, c] > 0) for c in cob.columns} for t in cob.index},
               "proporcao_tipos": {c: float((cob[c] > 0).mean()) for c in cob.columns}}

    # H5 abstenção (T12)
    t12 = base[base["modelo"] == "T12"]
    if len(t12):
        por = {c: wilson(int(g["sucesso"].sum()), len(g), conf) for c, g in t12.groupby("condicao")}
        h["H5"] = {"por_condicao": por}
        if {"AGROIA", "PORTAL"} <= set(por):
            a, p = por["AGROIA"], por["PORTAL"]
            if (a["k"] + p["k"]) not in (0, a["n"] + p["n"]):
                fx = fisher_exato(a["k"], a["n"], p["k"], p["n"])
                h["H5"]["fisher"] = fx
                pvals["H5"] = fx["p_valor"]

    ajust = holm(pvals, alfa)
    for hid, a in ajust.items():
        h[hid]["p_holm"] = a["p_holm"]
    # Decisões
    if "H1" in h:
        h["H1"]["decisao"] = _decisao(h["H1"].get("p_holm"), h["H1"]["b"] > h["H1"]["c"], alfa)
    for hid in ("H2", "H3"):
        if hid in h:
            h[hid]["decisao"] = _decisao(h[hid].get("p_holm"), (h[hid].get("mediana_dif") or 0) < 0, alfa)
    pt = h["H4"]["proporcao_tipos"]
    h["H4"]["decisao"] = ("sustentada" if pt.get("AGROIA", 0) > pt.get("PORTAL", 0) else "não sustentada")
    if "H5" in h:
        pc = h["H5"]["por_condicao"]
        if "AGROIA" in pc and "PORTAL" in pc:
            # H5 é de não inferioridade descritiva: AGROIA ≥ PORTAL.
            h["H5"]["decisao"] = "sustentada" if (pc["AGROIA"]["p"] or 0) >= (pc["PORTAL"]["p"] or 0) else "não sustentada"
    res["hipoteses"] = h
    res["desfechos"] = {c: g["desfecho"].value_counts().to_dict() for c, g in df.groupby("condicao")}
    # Sensibilidade: exclui BLOQUEADO e TIMEOUT
    sens = agregar(base[~base["desfecho"].isin(NAO_MEDIDO)])
    ps = sens.pivot_table(index="instancia", columns="condicao", values="sucesso_maioria").dropna()
    if {"AGROIA", "PORTAL"} <= set(ps.columns) and len(ps):
        t = tabela_2x2(list(ps["AGROIA"].astype(int)), list(ps["PORTAL"].astype(int)))
        res["H1_sensibilidade_por_protocolo"] = {"tabela": t, **mcnemar_exato(t["n10"], t["n01"], conf)}
    res["usou_chat"] = float(base.loc[base["condicao"] == "AGROIA", "usou_chat"].fillna(False).astype(bool).mean()) \
        if "usou_chat" in base else None
    res["aquecimento_s_mediana"] = float(base["aquecimento_s"].dropna().median()) if base["aquecimento_s"].notna().any() else None
    salvar_json(d / f"testes{sufixo}.json", res)
    return res
