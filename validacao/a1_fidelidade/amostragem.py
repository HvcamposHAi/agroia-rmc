"""Tamanho de amostra (Cochran com correção de população finita) e sorteio estratificado.

n0 = z² · p(1−p) / e², com p = 0,5;   n = n0 / (1 + (n0 − 1)/N)
Alocação proporcional por estrato (ano × modalidade) pelo método dos maiores restos,
com semente fixa registrada.
"""

from __future__ import annotations

import math
import random

from scipy.stats import norm


def tamanho_amostra(N: int, confianca: float = 0.95, margem: float = 0.05, p: float = 0.5) -> dict:
    z = float(norm.ppf(1 - (1 - confianca) / 2))
    n0 = z ** 2 * p * (1 - p) / margem ** 2
    n = n0 / (1 + (n0 - 1) / N) if N > 0 else 0
    return {"N": N, "z": round(z, 4), "p": p, "e": margem, "confianca": confianca,
            "n0": round(n0, 2), "n_exato": round(n, 2), "n": min(N, math.ceil(n))}


def alocar(estratos: dict[str, list], n: int) -> dict[str, int]:
    """Alocação proporcional com maiores restos; garante soma = n."""
    N = sum(len(v) for v in estratos.values())
    if N == 0 or n <= 0:
        return {k: 0 for k in estratos}
    cotas = {k: n * len(v) / N for k, v in estratos.items()}
    base = {k: min(len(estratos[k]), int(math.floor(c))) for k, c in cotas.items()}
    resto = n - sum(base.values())
    for k in sorted(cotas, key=lambda k: (cotas[k] - math.floor(cotas[k]), k), reverse=True):
        if resto <= 0:
            break
        if base[k] < len(estratos[k]):
            base[k] += 1
            resto -= 1
    return base


def sortear(itens: list[dict], chave_estrato, n: int, seed: int) -> tuple[list[dict], dict]:
    estratos: dict[str, list] = {}
    for it in sorted(itens, key=lambda x: x["chave"]):
        estratos.setdefault(chave_estrato(it), []).append(it)
    aloc = alocar(estratos, n)
    rng = random.Random(seed)
    amostra = []
    for k in sorted(estratos):
        amostra += rng.sample(estratos[k], aloc[k])
    return amostra, {k: {"populacao": len(estratos[k]), "amostra": aloc[k]} for k in sorted(estratos)}
