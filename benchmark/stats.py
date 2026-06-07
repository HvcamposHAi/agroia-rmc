"""Significância estatística: teste t pareado bilateral com correção de Bonferroni.

Adaptado de Yang et al. (2025): cada motor não-baseline é comparado ao baseline
(Claude) pareando observações por (questao_id, repeticao). Bonferroni corrige o
número total de testes simultâneos.
"""

from __future__ import annotations


def comparar_pareado(baseline_scores: list[float], motor_scores: list[float]) -> dict:
    """Teste t pareado bilateral entre baseline e um motor.

    Os vetores DEVEM estar alinhados por (questao_id, repeticao). Retorna t, p e n.
    Requer scipy; com n<2 ou variância nula retorna p=1.0 (não significativo).
    """
    if len(baseline_scores) != len(motor_scores):
        raise ValueError("Vetores de tamanhos diferentes — pareamento inválido.")
    n = len(baseline_scores)
    if n < 2:
        return {"t": 0.0, "p_value": 1.0, "n": n}
    from scipy.stats import ttest_rel
    import numpy as np
    t, p = ttest_rel(baseline_scores, motor_scores)
    if np.isnan(p):
        return {"t": 0.0, "p_value": 1.0, "n": n}
    return {"t": float(t), "p_value": float(p), "n": n}


def bonferroni(p_values: dict[str, float], n_testes: int | None = None,
               alpha: float = 0.05) -> dict:
    """Aplica correção de Bonferroni a um dict {rotulo: p_value}.

    n_testes default = número de comparações fornecidas (m). p_corrigido = min(p*m, 1).
    """
    m = n_testes if n_testes else max(len(p_values), 1)
    out = {}
    for rotulo, p in p_values.items():
        p_corr = min(p * m, 1.0)
        out[rotulo] = {
            "p": round(p, 6),
            "p_corrigido": round(p_corr, 6),
            "significativo": p_corr < alpha,
            "m": m,
        }
    return out


# Mapa de superescritos p/ notação estilo Yang et al. (índice do motor → símbolo).
SUPERESCRITOS = {0: "⁰", 1: "¹", 2: "²", 3: "³"}
