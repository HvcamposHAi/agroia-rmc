"""Comparações múltiplas e concordância: Cochran Q, Friedman, Holm, kappas."""

from __future__ import annotations

from collections import Counter

import numpy as np
from scipy import stats


def cochran_q(matriz: list[list[int]]) -> dict:
    """Q de Cochran (COCHRAN, 1950). matriz: linhas = blocos (perguntas), colunas = condições."""
    x = np.asarray(matriz, dtype=float)
    n, k = x.shape
    if n == 0 or k < 2:
        return {"q": None, "gl": None, "p_valor": None, "n": n, "k": k}
    col = x.sum(axis=0)
    lin = x.sum(axis=1)
    T = x.sum()
    den = k * T - (lin ** 2).sum()
    if den == 0:
        return {"q": 0.0, "gl": k - 1, "p_valor": 1.0, "n": n, "k": k}
    q = (k - 1) * (k * (col ** 2).sum() - T ** 2) / den
    return {"q": float(q), "gl": k - 1, "p_valor": float(stats.chi2.sf(q, k - 1)), "n": n, "k": k}


def friedman(*amostras) -> dict:
    """Teste de Friedman sobre k condições pareadas (mesmos blocos)."""
    amostras = [np.asarray(a, float) for a in amostras]
    if len(amostras) < 3 or any(len(a) != len(amostras[0]) for a in amostras) or len(amostras[0]) < 2:
        return {"chi2": None, "p_valor": None, "n": len(amostras[0]) if amostras else 0}
    r = stats.friedmanchisquare(*amostras)
    return {"chi2": float(r.statistic), "p_valor": float(r.pvalue), "n": len(amostras[0]), "k": len(amostras)}


def holm(pvalores: dict[str, float | None], alfa: float = 0.05) -> dict[str, dict]:
    """Correção de Holm (HOLM, 1979). Retorna p ajustado e decisão por hipótese."""
    validos = {k: v for k, v in pvalores.items() if v is not None}
    ordem = sorted(validos, key=lambda k: validos[k])
    m = len(ordem)
    ajust, acumulado = {}, 0.0
    for i, k in enumerate(ordem):
        acumulado = max(acumulado, min(1.0, (m - i) * validos[k]))
        ajust[k] = acumulado
    return {k: {"p": pvalores[k], "p_holm": ajust.get(k), "rejeita": (ajust[k] < alfa) if k in ajust else None}
            for k in pvalores}


def cohen_kappa(a: list, b: list) -> float | None:
    """κ de Cohen (COHEN, 1960) para dois avaliadores sobre rótulos categóricos."""
    pares = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    n = len(pares)
    if n == 0:
        return None
    po = sum(1 for x, y in pares if x == y) / n
    ca, cb = Counter(x for x, _ in pares), Counter(y for _, y in pares)
    pe = sum(ca[c] * cb[c] for c in set(ca) | set(cb)) / n ** 2
    if pe == 1:
        return 1.0
    return (po - pe) / (1 - pe)


def fleiss_kappa(rotulos_por_item: list[list]) -> float | None:
    """κ de Fleiss: cada item tem a mesma quantidade de avaliações (repetições)."""
    itens = [r for r in rotulos_por_item if r]
    if not itens:
        return None
    m = len(itens[0])
    if m < 2 or any(len(r) != m for r in itens):
        return None
    cats = sorted({c for r in itens for c in r}, key=str)
    tab = np.array([[r.count(c) for c in cats] for r in itens], float)
    N = len(itens)
    p_j = tab.sum(axis=0) / (N * m)
    P_i = ((tab ** 2).sum(axis=1) - m) / (m * (m - 1))
    Pb, Pe = P_i.mean(), (p_j ** 2).sum()
    if Pe == 1:
        return 1.0
    return float((Pb - Pe) / (1 - Pe))
