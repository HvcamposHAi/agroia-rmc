"""Providers LLM via REST puro (somente `requests`, já dependência de produção).

Usados pelo switch global de motor (chat/motor_router) e pelo comparador ao vivo
(api/benchmark_api), que rodam no Render. Evitam os SDKs `openai` e
`google-generativeai` (este arrasta protobuf/grpcio, com risco de conflito na
imagem de produção). Implementam a MESMA interface LLMProvider.gerar(), então
`benchmark.agentic_loop.rodar_loop` funciona sem alteração.

Claude continua no SDK `anthropic` (já em produção) via ClaudeProvider.
"""

from __future__ import annotations

import json
import os
import time

import requests

from benchmark.providers.base import LLMProvider, LLMResponse, ToolCall
from benchmark.schema_adapter import (
    anthropic_tools_para_openai,
    anthropic_tools_para_gemini_dict,
    canonico_para_openai_messages,
    canonico_para_gemini_history,
)

GROQ_BASE_URL_PADRAO = "https://api.groq.com/openai/v1"
MARITACA_BASE_URL_PADRAO = "https://chat.maritaca.ai/api"
GEMINI_MODELO = "gemini-2.0-flash"


def _redigir_chave(msg: str, chave: str) -> str:
    """Remove a chave de API de mensagens de erro (evita vazamento na UI/logs)."""
    texto = str(msg)
    if chave and chave in texto:
        texto = texto.replace(chave, "***")
    return texto


# ---------------------------------------------------------------------------
# Groq + Maritaca — endpoints compatíveis com OpenAI (/chat/completions)
# ---------------------------------------------------------------------------
class OpenAICompatRestProvider(LLMProvider):
    def __init__(self, api_key: str, base_url: str, modelo: str, nome: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.modelo = modelo
        self.nome = nome

    def gerar(self, system_prompt, tools_schema, messages,
              max_tokens=2048, timeout=30) -> LLMResponse:
        t0 = time.monotonic()
        payload = {
            "model": self.modelo,
            "messages": canonico_para_openai_messages(system_prompt, messages),
            "max_tokens": max_tokens,
        }
        if tools_schema:
            payload["tools"] = anthropic_tools_para_openai(tools_schema)
        try:
            r = requests.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}",
                         "Content-Type": "application/json"},
                json=payload, timeout=timeout,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:  # noqa: BLE001 — contrato base.py: nunca levanta
            return LLMResponse(texto=_redigir_chave(e, self.api_key), stop_reason="erro",
                               latencia_ms=int((time.monotonic() - t0) * 1000))

        latencia = int((time.monotonic() - t0) * 1000)
        try:
            choice = data["choices"][0]
            msg = choice.get("message", {}) or {}
        except (KeyError, IndexError, TypeError):
            return LLMResponse(texto="resposta inesperada do provider", stop_reason="erro",
                               latencia_ms=latencia, raw=data)

        tool_calls: list[ToolCall] = []
        for tc in (msg.get("tool_calls") or []):
            fn = tc.get("function", {}) or {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except (json.JSONDecodeError, TypeError):
                args = {}
            tool_calls.append(ToolCall(id=tc.get("id", ""), nome=fn.get("name", ""), inputs=args))

        finish = choice.get("finish_reason")
        if tool_calls or finish == "tool_calls":
            stop = "tool_use"
        elif finish == "length":
            stop = "max_tokens"
        else:
            stop = "end_turn"

        usage = data.get("usage") or {}
        return LLMResponse(
            texto=msg.get("content") or "",
            stop_reason=stop,
            tool_calls=tool_calls,
            tokens_entrada=usage.get("prompt_tokens", 0) or 0,
            tokens_saida=usage.get("completion_tokens", 0) or 0,
            latencia_ms=latencia,
            raw=data,
        )


# ---------------------------------------------------------------------------
# Gemini — generateContent via REST (sem SDK)
# ---------------------------------------------------------------------------
def _para_rest_parts(history: list) -> list:
    """Converte o history (snake_case do schema_adapter) para o shape REST do Gemini.

    function_call -> functionCall ; function_response -> functionResponse.
    """
    out = []
    for turno in history:
        parts = []
        for p in turno.get("parts", []):
            if "text" in p:
                parts.append({"text": p["text"]})
            elif "function_call" in p:
                fc = p["function_call"]
                parts.append({"functionCall": {"name": fc.get("name"), "args": fc.get("args", {})}})
            elif "function_response" in p:
                fr = p["function_response"]
                parts.append({"functionResponse": {"name": fr.get("name"),
                                                    "response": fr.get("response", {})}})
        out.append({"role": turno.get("role", "user"), "parts": parts})
    return out


class GeminiRestProvider(LLMProvider):
    nome = "gemini"
    modelo = GEMINI_MODELO

    def __init__(self, api_key: str, modelo: str | None = None):
        self.api_key = api_key
        self.modelo = modelo or GEMINI_MODELO

    def gerar(self, system_prompt, tools_schema, messages,
              max_tokens=2048, timeout=30) -> LLMResponse:
        t0 = time.monotonic()
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.modelo}:generateContent?key={self.api_key}")
        body = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": _para_rest_parts(canonico_para_gemini_history(messages)),
            "generationConfig": {"maxOutputTokens": max_tokens},
        }
        if tools_schema:
            body["tools"] = [{"function_declarations": anthropic_tools_para_gemini_dict(tools_schema)}]
        try:
            r = requests.post(url, json=body, timeout=timeout,
                              headers={"Content-Type": "application/json"})
            r.raise_for_status()
            data = r.json()
        except Exception as e:  # noqa: BLE001
            return LLMResponse(texto=_redigir_chave(e, self.api_key), stop_reason="erro",
                               latencia_ms=int((time.monotonic() - t0) * 1000))

        latencia = int((time.monotonic() - t0) * 1000)
        texto = ""
        tool_calls: list[ToolCall] = []
        try:
            partes = data["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError):
            partes = []
        for i, part in enumerate(partes):
            fc = part.get("functionCall")
            if fc and fc.get("name"):
                tool_calls.append(ToolCall(
                    id=f"gemini_{fc['name']}_{i}",
                    nome=fc["name"],
                    inputs=dict(fc.get("args", {}) or {}),
                ))
            elif part.get("text"):
                texto += part["text"]

        stop = "tool_use" if tool_calls else "end_turn"
        usage = data.get("usageMetadata", {}) or {}
        return LLMResponse(
            texto=texto,
            stop_reason=stop,
            tool_calls=tool_calls,
            tokens_entrada=usage.get("promptTokenCount", 0) or 0,
            tokens_saida=usage.get("candidatesTokenCount", 0) or 0,
            latencia_ms=latencia,
            raw=data,
        )


# ---------------------------------------------------------------------------
# Factory dos providers "ao vivo" (servidor). NÃO altera factory.py (offline).
# ---------------------------------------------------------------------------
def get_live_provider(nome: str) -> LLMProvider:
    """Instancia o provider REST/SDK do motor. Levanta RuntimeError se faltar chave."""
    nome = (nome or "").strip().lower()
    if nome == "claude":
        from benchmark.providers.claude import ClaudeProvider
        return ClaudeProvider()  # SDK anthropic (já em produção)
    if nome == "groq_llama":
        chave = os.getenv("GROQ_API_KEY")
        if not chave:
            raise RuntimeError("Defina GROQ_API_KEY para usar o motor groq_llama.")
        return OpenAICompatRestProvider(
            api_key=chave, base_url=os.getenv("GROQ_BASE_URL", GROQ_BASE_URL_PADRAO),
            modelo="llama-3.1-8b-instant", nome="groq_llama")
    if nome == "maritaca":
        chave = os.getenv("MARITACA_API_KEY")
        if not chave:
            raise RuntimeError("Defina MARITACA_API_KEY para usar o motor maritaca.")
        return OpenAICompatRestProvider(
            api_key=chave, base_url=os.getenv("MARITACA_BASE_URL", MARITACA_BASE_URL_PADRAO),
            modelo=os.getenv("MARITACA_MODELO", "sabia-4"), nome="maritaca")
    if nome == "gemini":
        chave = os.getenv("GOOGLE_API_KEY")
        if not chave:
            raise RuntimeError("Defina GOOGLE_API_KEY para usar o motor gemini.")
        return GeminiRestProvider(api_key=chave)
    raise ValueError(f"Motor desconhecido: {nome!r}")
