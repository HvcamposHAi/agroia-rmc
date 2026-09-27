"""A1.4: agregados por ano, base × portal.

Base (snapshot): nº de processos, nº de itens, soma empenhada, 10 maiores credores.
Portal: nº de processos e soma do "Valor global" da listagem (censo). O portal não
apresenta total de itens, de empenhos nem ranking de credores por órgão; esses campos
ficam como "não apresentado pela fonte".
"""

from __future__ import annotations

import pandas as pd

from validacao.comum import salvar_json, valor_brl


def calcular(snap, dir_a1, anos: list[int]) -> dict:
    lics = snap.licitacoes
    lics = lics[lics["ano"].isin(anos)]
    itens = snap.df("itens_licitacao").merge(lics[["id", "ano"]], left_on="licitacao_id", right_on="id",
                                             suffixes=("", "_lic"))
    emp = snap.df("empenhos").merge(itens[["id", "ano"]].rename(columns={"id": "item_id", "ano": "ano_proc"}),
                                    on="item_id")
    forn = snap.df("fornecedores")[["id", "razao_social", "cpf_cnpj"]].rename(columns={"id": "fornecedor_id"})
    emp = emp.merge(forn, on="fornecedor_id", how="left")
    proc = pd.read_csv(dir_a1 / "processos.csv") if (dir_a1 / "processos.csv").exists() else pd.DataFrame()

    linhas, ranking = [], {}
    for ano in anos:
        l_ano = lics[lics["ano"] == ano]
        n_base = int(len(l_ano))
        n_itens = int((itens["ano"] == ano).sum())
        e_ano = emp[emp["ano_proc"] == ano]
        soma_emp = float(pd.to_numeric(e_ano["valor_empenhado"], errors="coerce").fillna(0).sum())
        top = (e_ano.assign(v=pd.to_numeric(e_ano["valor_empenhado"], errors="coerce").fillna(0))
               .groupby("razao_social")["v"].sum().sort_values(ascending=False).head(10))
        ranking[int(ano)] = [{"credor": k, "valor": round(float(v), 2)} for k, v in top.items()]
        p_ano = proc[(proc["ano"] == ano) & proc["status"].isin(["PRESENTE_AMBOS", "FALTANTE_NA_BASE"])] if len(proc) else proc
        n_portal = int(len(p_ano)) if len(proc) else None
        soma_portal = float(sum(valor_brl(v) or 0 for v in p_ano["valor_global_portal"])) if len(proc) else None
        linhas.append({"ano": int(ano), "processos_base": n_base, "processos_portal": n_portal,
                       "dif_processos_abs": (n_base - n_portal) if n_portal is not None else None,
                       "dif_processos_rel": ((n_base - n_portal) / n_portal) if n_portal else None,
                       "itens_base": n_itens, "itens_portal": None,
                       "empenhado_base": round(soma_emp, 2), "empenhado_portal": None,
                       "valor_global_listagem_portal": round(soma_portal, 2) if soma_portal is not None else None})
    df = pd.DataFrame(linhas)
    df.to_csv(dir_a1 / "agregados.csv", index=False, encoding="utf-8")
    res = {"por_ano": linhas, "top10_credores_base": ranking,
           "nota": "O portal não apresenta totais de itens, de empenhos nem ranking de credores por órgão."}
    salvar_json(dir_a1 / "agregados.json", res)
    return res
