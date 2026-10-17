"""Métricas da projeção (plano v3, E6): MASE, perda por quantis, cobertura da faixa e
teste de Diebold-Mariano contra o ingênuo sazonal."""

from __future__ import annotations

import math

import numpy as np


def _arr(x) -> np.ndarray:
    return np.asarray(list(x), dtype=float)


def escala_ingenuo_sazonal(y_hist, m: int = 52) -> float:
    """Erro absoluto médio do ingênuo sazonal dentro da amostra de treino (denominador do MASE)."""
    h = _arr(y_hist)
    if len(h) <= m:
        raise ValueError(f"histórico de {len(h)} pontos; o ingênuo sazonal exige mais de {m}")
    escala = float(np.mean(np.abs(h[m:] - h[:-m])))
    if escala == 0:
        raise ValueError("série constante no histórico: MASE indefinido")
    return escala


def mase(y_true, y_pred, y_hist, m: int = 52) -> float:
    """Erro absoluto médio escalado pelo ingênuo sazonal: < 1 = melhor que o ingênuo."""
    yt, yp = _arr(y_true), _arr(y_pred)
    return float(np.mean(np.abs(yt - yp)) / escala_ingenuo_sazonal(y_hist, m))


def perda_quantil(y_true, q_pred, q: float) -> float:
    """Perda pinball média do quantil q."""
    e = _arr(y_true) - _arr(q_pred)
    return float(np.mean(np.maximum(q * e, (q - 1) * e)))


def cobertura_intervalo(y, lo, hi) -> float:
    """Fração dos valores reais dentro de [lo, hi]."""
    y, lo, hi = _arr(y), _arr(lo), _arr(hi)
    return float(np.mean((y >= lo) & (y <= hi)))


ALFA_PUBLICACAO = 0.05


def decidir_publicacao(real, previsto, ingenuo, ingenuo_sazonal, y_hist, h: int = 1,
                       m: int = 52, alfa: float = ALFA_PUBLICACAO) -> dict:
    """Regra de publicação de uma série (decidida em 16/10/2026).

    Publica só se MASE < 1 E o modelo vencer, com p < alfa no Diebold-Mariano, os DOIS
    ingênuos: o sazonal (mesma semana do ano anterior) e o simples (último preço). O
    simples entra porque, no PROHORT semanal, ele já erra muito menos que o sazonal.
    """
    real, previsto = _arr(real), _arr(previsto)
    erro = real - previsto
    valor_mase = mase(real, previsto, y_hist, m)
    dm_sazonal = diebold_mariano(erro, real - _arr(ingenuo_sazonal), h)
    dm_simples = diebold_mariano(erro, real - _arr(ingenuo), h)
    motivos = []
    if valor_mase >= 1:
        motivos.append(f"MASE {valor_mase:.2f} ≥ 1")
    for nome, dm in (("ingênuo sazonal", dm_sazonal), ("ingênuo simples", dm_simples)):
        if dm["p_valor"] is None or dm["p_valor"] >= alfa:
            p = "indefinido" if dm["p_valor"] is None else f"{dm['p_valor']:.3f}"
            motivos.append(f"não supera o {nome} (p = {p})")
    return {"publicar": not motivos, "mase": valor_mase,
            "p_vs_sazonal": dm_sazonal["p_valor"], "p_vs_ingenuo": dm_simples["p_valor"],
            "motivo": "; ".join(motivos) or None}


def diebold_mariano(erros_modelo, erros_referencia, h: int = 1) -> dict:
    """Teste de Diebold-Mariano (perda absoluta) com correção de Harvey, Leybourne e Newbold.

    H1 unilateral: o modelo tem perda MENOR que a referência. Devolve estatística e valor-p.
    """
    from scipy import stats

    d = np.abs(_arr(erros_modelo)) - np.abs(_arr(erros_referencia))
    n = len(d)
    if n < 3:
        return {"estatistica": None, "p_valor": None, "n": n}
    media = d.mean()
    gamma = [np.mean((d[k:] - media) * (d[:n - k] - media)) for k in range(h)]
    variancia = (gamma[0] + 2 * sum(gamma[1:])) / n
    if variancia <= 0:
        return {"estatistica": None, "p_valor": None, "n": n}
    dm = media / math.sqrt(variancia)
    correcao = math.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    estatistica = dm * correcao
    return {"estatistica": float(estatistica), "p_valor": float(stats.t.cdf(estatistica, df=n - 1)),
            "n": n}
