"""GroqLlamaProvider — modelo aberto via Groq (API compatível com OpenAI).

Era o Llama 3.1 8B (llama-3.1-8b-instant), desligado na camada gratuita em 16/08/2026; o
substituto recomendado pela Groq é openai/gpt-oss-20b. Configurável por GROQ_MODELO.
O nome da classe e a chave do motor (groq_llama) ficaram por compatibilidade."""

from __future__ import annotations

import os

from benchmark.providers.openai_base import OpenAICompatProvider

MODELO_GROQ = os.getenv("GROQ_MODELO", "openai/gpt-oss-20b")
GROQ_BASE_URL_PADRAO = "https://api.groq.com/openai/v1"


class GroqLlamaProvider(OpenAICompatProvider):
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        chave = api_key or os.getenv("GROQ_API_KEY")
        if not chave:
            raise RuntimeError("Defina GROQ_API_KEY para usar o motor groq_llama.")
        super().__init__(
            api_key=chave,
            base_url=base_url or os.getenv("GROQ_BASE_URL", GROQ_BASE_URL_PADRAO),
            modelo=MODELO_GROQ,
            nome="groq_llama",
        )
