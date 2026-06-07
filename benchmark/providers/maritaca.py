"""MaritacaProvider — Sabiá via Maritaca AI (API compatível com OpenAI).

Modelo configurável por env `MARITACA_MODELO` (default `sabia-4`). Os modelos
`sabia-3`/`sabia-3.1`/`sabiazinho-3` serão descontinuados em 15/07/2026 — por
isso o default já é `sabia-4`.

OBS de contexto: o `sabia-3` tinha janela curta (~8k). Por segurança, o
benchmark ainda trunca tool_results grandes para este motor via
max_tool_result_chars (ver benchmark_executor); inofensivo se o sabia-4 tiver
janela maior.
"""

from __future__ import annotations

import os

from benchmark.providers.openai_base import OpenAICompatProvider

MODELO_MARITACA_PADRAO = "sabia-4"
MARITACA_BASE_URL_PADRAO = "https://chat.maritaca.ai/api"


class MaritacaProvider(OpenAICompatProvider):
    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 modelo: str | None = None):
        chave = api_key or os.getenv("MARITACA_API_KEY")
        if not chave:
            raise RuntimeError("Defina MARITACA_API_KEY para usar o motor maritaca.")
        super().__init__(
            api_key=chave,
            base_url=base_url or os.getenv("MARITACA_BASE_URL", MARITACA_BASE_URL_PADRAO),
            modelo=modelo or os.getenv("MARITACA_MODELO", MODELO_MARITACA_PADRAO),
            nome="maritaca",
        )
