"""A1.1: censo de processos. Conjunto do portal (P) × conjunto da base (B), por ano.

Status por processo:
  PRESENTE_AMBOS                     P ∩ B
  FALTANTE_NA_BASE                   P \\ B
  AUSENTE_NO_PORTAL                  B \\ P, registro coletado da fonte atual
  NAO_VERIFICAVEL_FONTE_DESATIVADA   B \\ P, registro do portal JSF desativado (fora do
                                     denominador da precisão)
  NAO_VERIFICADO_ERRO_PORTAL         ano cuja listagem falhou (fora das métricas)
"""

from __future__ import annotations

import pandas as pd

from validacao import estado
from validacao.comum import salvar_json


def executar_censo(run_id: str, cfg: dict, snap, extrator, dir_a1) -> dict:
    anos = cfg["fontes"]["anos"]
    lics = snap.licitacoes
    lics = lics[lics["ano"].isin(anos)]
    base = {r["chave"]: r for r in lics.to_dict("records")}
    portal, erros_ano, por_ano = {}, {}, {}
    estado.registrar_unidades(run_id, "a1_censo", [str(a) for a in anos])
    for ano in anos:
        try:
            linhas = extrator.listar_ano(ano)
            for l in linhas:
                portal.setdefault(l["processo"], {**l, "ano": ano})
            estado.marcar(run_id, "a1_censo", str(ano), "concluida", f"{len(linhas)} linhas", incrementar=True)
            estado.evento(run_id, "a1", f"censo {ano}: {len(linhas)} processos no portal")
        except Exception as e:  # noqa: BLE001
            erros_ano[ano] = str(e)[:300]
            estado.marcar(run_id, "a1_censo", str(ano), "falhou", str(e), incrementar=True)
            estado.evento(run_id, "a1", f"censo {ano} falhou: {str(e)[:150]}", "erro")

    linhas_csv = []
    for chave in sorted(set(portal) | set(base)):
        p, b = portal.get(chave), base.get(chave)
        ano = (p or {}).get("ano") or (b or {}).get("ano")
        if ano in erros_ano:
            status = "NAO_VERIFICADO_ERRO_PORTAL"
        elif p and b:
            status = "PRESENTE_AMBOS"
        elif p:
            status = "FALTANTE_NA_BASE"
        elif b.get("url_detalhe"):
            status = "AUSENTE_NO_PORTAL"
        else:
            status = "NAO_VERIFICAVEL_FONTE_DESATIVADA"
        linhas_csv.append({
            "chave": chave, "ano": int(ano) if ano else None, "status": status,
            "origem_base": ("TRANSPARENCIA" if b and b.get("url_detalhe") else "JSF_LEGADO") if b else None,
            "relevante_af": bool(b.get("relevante_af")) if b else None,
            "modalidade_portal": (p or {}).get("modalidade"), "situacao_portal": (p or {}).get("situacao"),
            "objeto_portal": (p or {}).get("objeto"), "valor_global_portal": (p or {}).get("valor_global"),
            "pagina_portal": (p or {}).get("pagina"),
            "modalidade_base": (b or {}).get("modalidade"), "situacao_base": (b or {}).get("situacao"),
        })
    df = pd.DataFrame(linhas_csv)
    df.to_csv(dir_a1 / "processos.csv", index=False, encoding="utf-8")

    def metricas(sub: pd.DataFrame) -> dict:
        n = sub["status"].value_counts().to_dict()
        ambos = n.get("PRESENTE_AMBOS", 0)
        P = ambos + n.get("FALTANTE_NA_BASE", 0)
        B_verif = ambos + n.get("AUSENTE_NO_PORTAL", 0)
        return {"P": P, "B_verificaveis": B_verif, "P_inter_B": ambos,
                "faltantes_na_base": n.get("FALTANTE_NA_BASE", 0),
                "ausentes_no_portal": n.get("AUSENTE_NO_PORTAL", 0),
                "nao_verificaveis_fonte_desativada": n.get("NAO_VERIFICAVEL_FONTE_DESATIVADA", 0),
                "nao_verificados_erro_portal": n.get("NAO_VERIFICADO_ERRO_PORTAL", 0),
                "completude": (ambos / P) if P else None,
                "precisao_existencia": (ambos / B_verif) if B_verif else None}

    parciais = [a for a in cfg["fontes"].get("anos_parciais", []) if a in anos]
    res = {"anos": anos, "erros_ano": erros_ano, "global": metricas(df),
           "anos_parciais": parciais, "inicio_corpus": cfg["fontes"].get("inicio_corpus"),
           "global_sem_parciais": metricas(df[~df["ano"].isin(parciais)]),
           "por_ano": {int(a): metricas(g) for a, g in df.groupby("ano")},
           # Escopo agrícola: relevante_af só existe do lado da base; a completude nesse recorte
           # não é definível (o portal não classifica), então só a precisão é reportada.
           "escopo_af": {k: v for k, v in metricas(df[df["relevante_af"] == True]).items()  # noqa: E712
                         if k not in ("P", "completude", "faltantes_na_base")},
           "portal_requisicoes": extrator.requisicoes}
    for a in res["por_ano"]:
        por_ano[a] = res["por_ano"][a]
    salvar_json(dir_a1 / "censo.json", res)
    return res
