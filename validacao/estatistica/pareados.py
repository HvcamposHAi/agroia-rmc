"""Testes pareados: McNemar exato, Wilcoxon, Fisher exato e tamanhos de efeito."""

from __future__ import annotations

import math

import numpy as np
from scipy import stats


def tabela_2x2(a: list[int], b: list[int]) -> dict:
    """Pares (a_i, b_i) binários → contagens n11, n10, n01, n00 (a = linha, b = coluna)."""
    n11 = sum(1 for x, y in zip(a, b) if x and y)
    n10 = sum(1 for x, y in zip(a, b) if x and not y)
    n01 = sum(1 for x, y in zip(a, b) if not x and y)
    n00 = sum(1 for x, y in zip(a, b) if not x and not y)
    return {"n11": n11, "n10": n10, "n01": n01, "n00": n00, "n": len(a)}


def mcnemar_exato(n10: int, n01: int, confianca: float = 0.95) -> dict:
    """McNemar exato (MCNEMAR, 1947): binomial bilateral sobre os pares discordantes.

    Razão de chances condicional OR = n10/n01, IC exato via Clopper-Pearson em n10/(n10+n01)."""
    d = n10 + n01
    if d == 0:
        return {"b": n10, "c": n01, "discordantes": 0, "p_valor": 1.0, "or": None, "or_li": None, "or_ls": None}
    p = float(stats.binomtest(n10, d, 0.5, alternative="two-sided").pvalue)
    alfa = 1 - confianca
    li = stats.beta.ppf(alfa / 2, n10, d - n10 + 1) if n10 > 0 else 0.0
    ls = stats.beta.ppf(1 - alfa / 2, n10 + 1, d - n10) if n10 < d else 1.0
    conv = lambda q: (q / (1 - q)) if q < 1 else math.inf  # noqa: E731
    return {"b": n10, "c": n01, "discordantes": d, "p_valor": p,
            "or": (n10 / n01) if n01 else math.inf, "or_li": conv(float(li)), "or_ls": conv(float(ls))}


def wilcoxon_pareado(x: list[float], y: list[float]) -> dict:
    """Postos sinalizados de Wilcoxon (WILCOXON, 1945) sobre d = x − y.

    Efeito: r = Z/√N (N = pares não nulos), com Z da aproximação normal."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    d = x - y
    nz = d[d != 0]
    N = int(len(nz))
    if N == 0:
        return {"n": int(len(d)), "n_nao_nulos": 0, "W": None, "p_valor": 1.0, "z": 0.0, "r": 0.0,
                "mediana_dif": float(np.median(d)) if len(d) else None}
    res = stats.wilcoxon(x, y, zero_method="wilcox", method="exact" if N <= 50 else "approx")
    # Z pela aproximação normal (com correção de empates), p/ o tamanho de efeito.
    ranks = stats.rankdata(np.abs(nz))
    w_mais = ranks[nz > 0].sum()
    media = N * (N + 1) / 4
    _, cont = np.unique(np.abs(nz), return_counts=True)
    var = N * (N + 1) * (2 * N + 1) / 24 - (cont ** 3 - cont).sum() / 48
    z = (w_mais - media) / math.sqrt(var) if var > 0 else 0.0
    return {"n": int(len(d)), "n_nao_nulos": N, "W": float(res.statistic), "p_valor": float(res.pvalue),
            "z": float(z), "r": float(abs(z) / math.sqrt(N)), "mediana_dif": float(np.median(d))}


def cliff_delta(x: list[float], y: list[float]) -> float | None:
    """δ de Cliff = P(X > Y) − P(X < Y)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) == 0 or len(y) == 0:
        return None
    maior = sum(int((xi > y).sum()) for xi in x)
    menor = sum(int((xi < y).sum()) for xi in x)
    return (maior - menor) / (len(x) * len(y))


def magnitude_cliff(d: float | None) -> str | None:
    """Limiares de Romano et al. (2006): 0,147 / 0,33 / 0,474."""
    if d is None:
        return None
    a = abs(d)
    return "desprezível" if a < 0.147 else "pequeno" if a < 0.33 else "médio" if a < 0.474 else "grande"


def fisher_exato(k1: int, n1: int, k2: int, n2: int) -> dict:
    tab = [[k1, n1 - k1], [k2, n2 - k2]]
    oratio, p = stats.fisher_exact(tab)
    return {"tabela": tab, "or": float(oratio), "p_valor": float(p)}


def minimo_discordantes(alfa: float = 0.05) -> int:
    """Menor nº de pares discordantes, todos no mesmo sentido, para p < α no McNemar exato."""
    k = 1
    while 2 * 0.5 ** k >= alfa:
        k += 1
    return k


def poder_mcnemar(n: int, p10: float, p01: float, alfa: float = 0.05) -> float:
    """Poder aproximado do McNemar (Connor, 1987) para n pares e probabilidades discordantes."""
    psi = p10 + p01
    delta = abs(p10 - p01)
    if psi == 0 or delta == 0:
        return 0.0
    za = stats.norm.ppf(1 - alfa / 2)
    num = math.sqrt(n * delta ** 2) - za * math.sqrt(psi)
    den = math.sqrt(psi - delta ** 2)
    return float(stats.norm.cdf(num / den))


def menor_efeito_detectavel(n: int, psi: float, alfa: float = 0.05, poder: float = 0.8) -> float | None:
    """Menor |p10 − p01| detectável com o poder dado, fixada a discordância total ψ."""
    for passo in range(1, 1001):
        delta = psi * passo / 1000
        p10, p01 = (psi + delta) / 2, (psi - delta) / 2
        if poder_mcnemar(n, p10, p01, alfa) >= poder:
            return delta
    return None
