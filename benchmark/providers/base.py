"""Abstração comum dos motores LLM (base do padrão Strategy).

A lista de mensagens CANÔNICA do loop é sempre no formato Anthropic
(role: user/assistant; content: str OU lista de blocos text/tool_use/tool_result).
Cada provider concreto converte essa lista canônica para o seu formato nativo na
entrada e normaliza a resposta nativa para `LLMResponse` na saída. Assim a chamada
a `executar_tool` permanece IDÊNTICA em todos os motores — requisito de um
benchmark justo.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    """Uma chamada de ferramenta normalizada, independente de provider."""
    id: str
    nome: str
    inputs: dict


@dataclass
class LLMResponse:
    """Resposta normalizada de um turno do motor.

    stop_reason normalizado para um vocabulário comum:
        "end_turn"  — o motor finalizou com texto
        "tool_use"  — o motor pediu uma ou mais ferramentas
        "max_tokens"— truncado por limite de saída
        "erro"      — falha de API/parse (texto carrega a mensagem)
    """
    texto: str
    stop_reason: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tokens_entrada: int = 0
    tokens_saida: int = 0
    latencia_ms: int = 0
    tokens_estimados: bool = False  # True quando o SDK não reportou usage
    raw: object = None              # resposta crua p/ auditoria/debug


class LLMProvider(ABC):
    """Interface comum a todos os motores LLM avaliados no benchmark."""

    nome: str = "base"      # claude | groq_llama | maritaca | gemini
    modelo: str = ""        # id exato do modelo

    @abstractmethod
    def gerar(
        self,
        system_prompt: str,
        tools_schema: list,
        messages: list,
        max_tokens: int = 2048,
        timeout: int = 30,
    ) -> LLMResponse:
        """Executa UM turno do motor e retorna a resposta normalizada.

        `messages` está no formato canônico (Anthropic). O provider é responsável
        por converter para o formato nativo e por normalizar a resposta de volta.
        Falhas de rede/SDK NÃO devem levantar: capture e retorne
        LLMResponse(stop_reason="erro", texto=str(e)).
        """
        raise NotImplementedError
