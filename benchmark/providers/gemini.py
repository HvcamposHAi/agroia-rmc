"""GeminiProvider — Gemini 2.0 Flash via google-generativeai.

Particularidades tratadas:
- roles user/model (não há 'assistant'/'system'); system vai por system_instruction.
- tool_result casa por NOME da função (não há tool_call_id).
- function_call.args é um proto.Map → convertido p/ dict puro recursivamente.
- Schema do Gemini não aceita várias chaves de JSON-Schema (ver schema_adapter).
"""

from __future__ import annotations

import os
import time

from benchmark.providers.base import LLMProvider, LLMResponse, ToolCall
from benchmark.schema_adapter import (
    anthropic_tools_para_gemini_dict,
    canonico_para_gemini_history,
)

MODELO_GEMINI = "gemini-2.0-flash"


def _proto_para_python(valor):
    """Converte recursivamente valores proto (Map/RepeatedComposite) para Python puro."""
    # dict-like
    if hasattr(valor, "items"):
        return {k: _proto_para_python(v) for k, v in valor.items()}
    # list-like (mas não string)
    if hasattr(valor, "__iter__") and not isinstance(valor, (str, bytes)):
        return [_proto_para_python(v) for v in valor]
    return valor


class GeminiProvider(LLMProvider):
    nome = "gemini"
    modelo = MODELO_GEMINI

    def __init__(self, api_key: str | None = None):
        import google.generativeai as genai  # import tardio
        chave = api_key or os.getenv("GOOGLE_API_KEY")
        if not chave:
            raise RuntimeError("Defina GOOGLE_API_KEY para usar o motor gemini.")
        genai.configure(api_key=chave)
        self._genai = genai

    def _materializar_tools(self, tools_schema):
        from google.generativeai.types import FunctionDeclaration, Tool
        decls_dict = anthropic_tools_para_gemini_dict(tools_schema)
        decls = [
            FunctionDeclaration(
                name=d["name"], description=d["description"], parameters=d["parameters"]
            )
            for d in decls_dict
        ]
        return [Tool(function_declarations=decls)]

    def gerar(self, system_prompt, tools_schema, messages,
              max_tokens=2048, timeout=30) -> LLMResponse:
        t0 = time.monotonic()
        try:
            tools = self._materializar_tools(tools_schema) if tools_schema else None
            model = self._genai.GenerativeModel(
                model_name=MODELO_GEMINI,
                system_instruction=system_prompt,
                tools=tools,
            )
            history = canonico_para_gemini_history(messages)
            resp = model.generate_content(
                history,
                generation_config={"max_output_tokens": max_tokens},
                request_options={"timeout": timeout},
            )
        except Exception as e:  # noqa: BLE001
            return LLMResponse(
                texto=str(e), stop_reason="erro",
                latencia_ms=int((time.monotonic() - t0) * 1000),
            )

        latencia = int((time.monotonic() - t0) * 1000)
        texto = ""
        tool_calls: list[ToolCall] = []
        try:
            partes = resp.candidates[0].content.parts
        except (AttributeError, IndexError):
            partes = []

        for i, part in enumerate(partes):
            fc = getattr(part, "function_call", None)
            if fc and getattr(fc, "name", None):
                tool_calls.append(ToolCall(
                    id=f"gemini_{fc.name}_{i}",
                    nome=fc.name,
                    inputs=_proto_para_python(getattr(fc, "args", {}) or {}),
                ))
            elif getattr(part, "text", None):
                texto += part.text

        stop = "tool_use" if tool_calls else "end_turn"
        usage = getattr(resp, "usage_metadata", None)
        return LLMResponse(
            texto=texto,
            stop_reason=stop,
            tool_calls=tool_calls,
            tokens_entrada=getattr(usage, "prompt_token_count", 0) or 0,
            tokens_saida=getattr(usage, "candidates_token_count", 0) or 0,
            latencia_ms=latencia,
            raw=resp,
        )
