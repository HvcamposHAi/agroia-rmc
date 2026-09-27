"""Proporções com intervalo de Wilson (WILSON, 1927)."""

from __future__ import annotations

import math

from scipy.stats import norm


def wilson(k: int, n: int, confianca: float = 0.95) -> dict:
    """Intervalo de score de Wilson para k sucessos em n. n = 0 → valores None."""
    if n <= 0:
        return {"k": k, "n": n, "p": None, "li": None, "ls": None}
    z = norm.ppf(1 - (1 - confianca) / 2)
    p = k / n
    den = 1 + z ** 2 / n
    centro = (p + z ** 2 / (2 * n)) / den
    meia = z * math.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / den
    return {"k": int(k), "n": int(n), "p": p, "li": max(0.0, centro - meia), "ls": min(1.0, centro + meia)}
