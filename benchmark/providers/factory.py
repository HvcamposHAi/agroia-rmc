"""Factory de providers. A chave de API só é validada quando o motor é instanciado."""

from __future__ import annotations

from benchmark.providers.base import LLMProvider

MOTORES_DISPONIVEIS = ("claude", "groq_llama", "maritaca", "gemini")

# Rótulos amigáveis p/ relatórios e front.
# As chaves (groq_llama, gemini) ficaram iguais para não quebrar app_config.motor_ativo e o
# frontend; os modelos mudaram em 30/09/2026 porque os originais foram desligados pelos
# provedores (Groq: llama-3.1-8b-instant em 16/08/2026, migrado ao plano Enterprise;
# Google: gemini-2.0-flash em 01/06/2026).
ROTULOS = {
    "claude": "Claude Haiku 4.5",
    "groq_llama": "GPT-OSS 20B (Groq)",
    "maritaca": "Sabiá-4",
    "gemini": "Gemini 3.8 Flash",
}

MOTOR_BASELINE = "claude"


def get_provider(nome: str) -> LLMProvider:
    """Instancia o provider pelo nome. Levanta RuntimeError se a chave faltar."""
    nome = (nome or "").strip().lower()
    if nome == "claude":
        from benchmark.providers.claude import ClaudeProvider
        return ClaudeProvider()
    if nome == "groq_llama":
        from benchmark.providers.groq_llama import GroqLlamaProvider
        return GroqLlamaProvider()
    if nome == "maritaca":
        from benchmark.providers.maritaca import MaritacaProvider
        return MaritacaProvider()
    if nome == "gemini":
        from benchmark.providers.gemini import GeminiProvider
        return GeminiProvider()
    raise ValueError(
        f"Motor desconhecido: {nome!r}. Disponíveis: {', '.join(MOTORES_DISPONIVEIS)}"
    )
