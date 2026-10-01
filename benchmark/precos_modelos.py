"""Tabela de preços por motor (USD por 1 milhão de tokens).

ATUALIZE os valores no writeup com os preços de lista vigentes na data do experimento.
Cada entrada traz a `fonte` para citação ABNT. Sabiá-3 é cotado em BRL pela Maritaca;
converta pela taxa de câmbio da data (campo `moeda`/`cambio_brl_usd`).
"""

from __future__ import annotations

# Preços de LISTA (não consideram desconto de cache). Datados em 2026-06.
PRECOS = {
    "claude": {
        # US$ 0,80/4,00 era o preço do Haiku 3.5; o de lista do Haiku 4.5 é US$ 1/5 (30/09/2026).
        "entrada_por_1m": 1.00, "saida_por_1m": 5.00, "moeda": "USD",
        "fonte": "https://www.anthropic.com/pricing (Claude Haiku 4.5, consultado em 30/09/2026)",
    },
    "groq_llama": {
        "entrada_por_1m": 0.075, "saida_por_1m": 0.30, "moeda": "USD",
        # openai/gpt-oss-20b (substituiu o llama-3.1-8b-instant em 30/09/2026)
        "fonte": "https://console.groq.com/docs/model/openai/gpt-oss-20b (consultado em 30/09/2026)",
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
        "entrada_por_1m": 0.30, "saida_por_1m": 2.50, "moeda": "USD",
        # gemini-2.5-flash (substituiu o gemini-2.0-flash em 30/09/2026); há camada gratuita
        "fonte": "https://ai.google.dev/gemini-api/docs/pricing (Gemini 2.5 Flash, consultado em 30/09/2026)",
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
