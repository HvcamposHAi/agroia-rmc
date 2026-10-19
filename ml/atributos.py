"""Atributos da projeção semanal (plano v3, E6).

Regra de ouro (integridade I18, teste T-P9): os atributos de uma origem só usam dados com
data ≤ origem. A série é cortada na origem ANTES de qualquer cálculo; o calendário da
semana-alvo é determinístico e pode ser usado.
"""

from __future__ import annotations

import math

import pandas as pd

DEFASAGENS = (0, 1, 2, 3, 4, 5, 6, 7, 8, 52)
JANELAS = (4, 12)


def _num(v) -> float | None:
    if v is None:
        return None
    v = float(v)
    return None if math.isnan(v) else v


def montar_atributos(serie: pd.Series, origem, horizonte: int = 1) -> dict:
    """Atributos para prever a semana origem + `horizonte` semanas.

    serie: preço semanal (índice de datas, uma por semana; pode ter lacunas).
    Devolve dict sem NaN (ausente = None), comparável por igualdade.
    """
    origem = pd.Timestamp(origem)
    passado = serie[serie.index <= origem].sort_index()
    out: dict[str, float | None] = {}
    for k in DEFASAGENS:
        out[f"lag_{k}"] = _num(passado.get(origem - pd.Timedelta(weeks=k)))
    for j in JANELAS:
        janela = passado[passado.index > origem - pd.Timedelta(weeks=j)]
        out[f"media_{j}"] = _num(janela.mean()) if len(janela) else None
        out[f"desvio_{j}"] = _num(janela.std(ddof=0)) if len(janela) > 1 else None
    alvo = origem + pd.Timedelta(weeks=horizonte)
    semana = int(alvo.isocalendar().week)
    out["semana_alvo"] = float(semana)
    out["sen_semana"] = math.sin(2 * math.pi * semana / 52.18)
    out["cos_semana"] = math.cos(2 * math.pi * semana / 52.18)
    out["horizonte"] = float(horizonte)
    out["n_historico"] = float(len(passado))
    return out
