"""Base comum para motores expostos via API compatível com OpenAI (Groq, Maritaca)."""

from __future__ import annotations

import json
import time

from benchmark.providers.base import LLMProvider, LLMResponse, ToolCall
from benchmark.schema_adapter import (
    anthropic_tools_para_openai,
    canonico_para_openai_messages,
)


class OpenAICompatProvider(LLMProvider):
    """Provider genérico para endpoints OpenAI-compatible (function calling)."""

    def __init__(self, api_key: str, base_url: str, modelo: str, nome: str):
        from openai import OpenAI  # import tardio
        self.nome = nome
        self.modelo = modelo
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def gerar(self, system_prompt, tools_schema, messages,
              max_tokens=2048, timeout=30) -> LLMResponse:
        t0 = time.monotonic()
        oai_messages = canonico_para_openai_messages(system_prompt, messages)
        oai_tools = anthropic_tools_para_openai(tools_schema) if tools_schema else None
        try:
            resp = self._client.chat.completions.create(
                model=self.modelo,
                messages=oai_messages,
                tools=oai_tools,
                max_tokens=max_tokens,
                timeout=timeout,
            )
        except Exception as e:  # noqa: BLE001
            return LLMResponse(
                texto=str(e), stop_reason="erro",
                latencia_ms=int((time.monotonic() - t0) * 1000),
            )

        latencia = int((time.monotonic() - t0) * 1000)
        choice = resp.choices[0]
        msg = choice.message

        tool_calls: list[ToolCall] = []
        if getattr(msg, "tool_calls", None):
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except (json.JSONDecodeError, TypeError):
                    args = {}
                tool_calls.append(ToolCall(id=tc.id, nome=tc.function.name, inputs=args))

        finish = choice.finish_reason
        if tool_calls or finish == "tool_calls":
            stop = "tool_use"
        elif finish == "length":
            stop = "max_tokens"
        else:
            stop = "end_turn"

        usage = getattr(resp, "usage", None)
        return LLMResponse(
            texto=msg.content or "",
            stop_reason=stop,
            tool_calls=tool_calls,
            tokens_entrada=getattr(usage, "prompt_tokens", 0) or 0,
            tokens_saida=getattr(usage, "completion_tokens", 0) or 0,
            latencia_ms=latencia,
            raw=resp,
        )
