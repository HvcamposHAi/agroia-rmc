"""ClaudeProvider — baseline FIEL ao caminho de produção.

Reproduz exatamente os parâmetros de chat/agent.py:90-97 (model id, max_tokens,
timeout, system com cache_control, tools cru). Usa um cliente Anthropic PRÓPRIO
(não importa chat.agent.get_client) para manter acoplamento zero com produção.
"""

from __future__ import annotations

import os
import time

from benchmark.providers.base import LLMProvider, LLMResponse, ToolCall

# Mesmo id literal de produção (chat/agent.py:91). Mantido como constante auditável.
MODELO_CLAUDE = "claude-haiku-4-5-20251001"


class ClaudeProvider(LLMProvider):
    nome = "claude"
    modelo = MODELO_CLAUDE

    def __init__(self, api_key: str | None = None):
        import anthropic  # import tardio: não exigir a lib se o motor não for usado
        chave = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not chave:
            raise RuntimeError("Defina ANTHROPIC_API_KEY para usar o motor claude.")
        self._client = anthropic.Anthropic(api_key=chave)

    def gerar(self, system_prompt, tools_schema, messages,
              max_tokens=2048, timeout=30) -> LLMResponse:
        t0 = time.monotonic()
        try:
            resp = self._client.messages.create(
                model=MODELO_CLAUDE,
                max_tokens=max_tokens,
                system=[{
                    "type": "text", "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }],
                tools=tools_schema,            # formato Anthropic cru — sem conversão
                messages=messages,             # lista canônica JÁ é Anthropic
                timeout=timeout,
            )
        except Exception as e:  # noqa: BLE001
            return LLMResponse(
                texto=str(e), stop_reason="erro",
                latencia_ms=int((time.monotonic() - t0) * 1000),
            )

        latencia = int((time.monotonic() - t0) * 1000)
        texto = ""
        tool_calls: list[ToolCall] = []
        for bloco in resp.content:
            if getattr(bloco, "type", None) == "text":
                texto += bloco.text
            elif getattr(bloco, "type", None) == "tool_use":
                tool_calls.append(ToolCall(id=bloco.id, nome=bloco.name, inputs=dict(bloco.input)))

        stop = "tool_use" if resp.stop_reason == "tool_use" else (
            "max_tokens" if resp.stop_reason == "max_tokens" else "end_turn"
        )
        usage = getattr(resp, "usage", None)
        return LLMResponse(
            texto=texto,
            stop_reason=stop,
            tool_calls=tool_calls,
            tokens_entrada=getattr(usage, "input_tokens", 0) or 0,
            tokens_saida=getattr(usage, "output_tokens", 0) or 0,
            latencia_ms=latencia,
            raw=resp,
        )
