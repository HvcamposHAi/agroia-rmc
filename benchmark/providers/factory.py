"""Factory de providers. A chave de API só é validada quando o motor é instanciado."""

from __future__ import annotations

from benchmark.providers.base import LLMProvider

MOTORES_DISPONIVEIS = ("claude", "groq_llama", "maritaca", "gemini")

# Rótulos amigáveis p/ relatórios e front.
ROTULOS = {
    "claude": "Claude Haiku 4.5",
    "groq_llama": "Llama 3.1 8B",
    "maritaca": "Sabiá-4",
    "gemini": "Gemini 2.0 Flash",
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
