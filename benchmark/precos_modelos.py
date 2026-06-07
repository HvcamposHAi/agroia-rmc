"""Tabela de preços por motor (USD por 1 milhão de tokens).

ATUALIZE os valores no writeup com os preços de lista vigentes na data do experimento.
Cada entrada traz a `fonte` para citação ABNT. Sabiá-3 é cotado em BRL pela Maritaca;
converta pela taxa de câmbio da data (campo `moeda`/`cambio_brl_usd`).
"""

from __future__ import annotations

# Preços de LISTA (não consideram desconto de cache). Datados em 2026-06.
PRECOS = {
    "claude": {
        "entrada_por_1m": 0.80, "saida_por_1m": 4.00, "moeda": "USD",
        "fonte": "https://www.anthropic.com/pricing (Claude Haiku 4.5)",
    },
    "groq_llama": {
        "entrada_por_1m": 0.05, "saida_por_1m": 0.08, "moeda": "USD",
        "fonte": "https://groq.com/pricing (llama-3.1-8b-instant)",
    },
    "maritaca": {
        # Sabiá-4 — cotado em BRL pela Maritaca; converter p/ USD com cambio_brl_usd.
        # ATENÇÃO: valores abaixo são placeholders — confira a página "Preços" da
        # plataforma Maritaca (sabia-4 custa mais que o sabia-3) e atualize.
        "entrada_por_1m": 5.00, "saida_por_1m": 10.00, "moeda": "BRL",
        "cambio_brl_usd": 0.18,  # ATUALIZAR: BRL->USD na data do experimento
        "fonte": "https://plataforma.maritaca.ai (Sabiá-4 — verificar preço atual)",
    },
    "gemini": {
        "entrada_por_1m": 0.10, "saida_por_1m": 0.40, "moeda": "USD",
        "fonte": "https://ai.google.dev/pricing (Gemini 2.0 Flash, <=128k)",
    },
}


def custo_usd(motor: str, tokens_entrada: int, tokens_saida: int) -> float:
    """Custo da consulta em USD a partir dos tokens medidos."""
    p = PRECOS.get(motor)
    if not p:
        return 0.0
    bruto = (tokens_entrada / 1_000_000) * p["entrada_por_1m"] + \
            (tokens_saida / 1_000_000) * p["saida_por_1m"]
    if p.get("moeda") == "BRL":
        bruto *= p.get("cambio_brl_usd", 1.0)
    return round(bruto, 8)
