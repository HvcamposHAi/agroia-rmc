"""Conversão de schemas de ferramentas e de mensagens entre formatos de provider.

Formato CANÔNICO interno = Anthropic:
  - tools: [{"name","description","input_schema":{...JSON-Schema...}}]
  - messages: [{"role":"user|assistant","content": str | [blocos]}]
      blocos: {"type":"text","text":..}
              {"type":"tool_use","id":..,"name":..,"input":{..}}
              {"type":"tool_result","tool_use_id":..,"content": "<json str>"}

Este módulo converte o canônico para:
  - OpenAI function-calling (Groq, Maritaca)
  - Google GenAI (Gemini)
e normaliza tool_result de volta para cada formato nativo.
"""

from __future__ import annotations

import json


# ---------------------------------------------------------------------------
# TOOLS: Anthropic -> OpenAI
# ---------------------------------------------------------------------------
def anthropic_tools_para_openai(tools_schema: list) -> list:
    """Converte TOOLS_SCHEMA (Anthropic) para o formato de function-calling OpenAI.

    input_schema (JSON-Schema) mapeia 1:1 para `parameters`.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
            },
        }
        for t in tools_schema
    ]


# ---------------------------------------------------------------------------
# TOOLS: Anthropic -> Gemini (google.generativeai)
# ---------------------------------------------------------------------------
_TIPOS_GEMINI = {
    "string": "STRING",
    "integer": "INTEGER",
    "number": "NUMBER",
    "boolean": "BOOLEAN",
    "object": "OBJECT",
    "array": "ARRAY",
}

# Chaves de JSON-Schema que o Schema do Gemini NÃO aceita e devem ser removidas.
_CHAVES_NAO_SUPORTADAS_GEMINI = {
    "additionalProperties", "$schema", "title", "default",
    "examples", "minimum", "maximum", "minLength", "maxLength", "pattern",
}


def _json_schema_para_gemini_dict(prop: dict) -> dict:
    """Converte recursivamente um nó JSON-Schema para o dict aceito pelo Gemini Schema.

    Retorna um dict puro (sem dependência do SDK), para permitir teste offline.
    O GeminiProvider transforma esse dict em genai...Schema na hora do uso.
    """
    if not isinstance(prop, dict):
        return {"type": "STRING"}

    out: dict = {}
    tipo = prop.get("type", "string")
    out["type"] = _TIPOS_GEMINI.get(tipo, "STRING")

    if "description" in prop:
        out["description"] = prop["description"]

    # enum só é suportado em STRING
    if "enum" in prop and out["type"] == "STRING":
        out["enum"] = list(prop["enum"])

    if out["type"] == "OBJECT":
        props = prop.get("properties", {}) or {}
        out["properties"] = {
            k: _json_schema_para_gemini_dict(v) for k, v in props.items()
        }
        # required default [] evita erro de declaração vazia
        out["required"] = list(prop.get("required", []))

    if out["type"] == "ARRAY":
        itens = prop.get("items", {"type": "string"})
        out["items"] = _json_schema_para_gemini_dict(itens)

    # garante que nenhuma chave não suportada vaze
    for k in _CHAVES_NAO_SUPORTADAS_GEMINI:
        out.pop(k, None)
    return out


def anthropic_tools_para_gemini_dict(tools_schema: list) -> list:
    """Converte TOOLS_SCHEMA para uma lista de declarações de função (dicts puros).

    Cada item: {"name","description","parameters": <gemini-schema-dict>}.
    Testável offline; o provider materializa em objetos do SDK.
    """
    decls = []
    for t in tools_schema:
        decls.append({
            "name": t["name"],
            "description": t.get("description", ""),
            "parameters": _json_schema_para_gemini_dict(
                t.get("input_schema", {"type": "object", "properties": {}})
            ),
        })
    return decls


# ---------------------------------------------------------------------------
# MESSAGES: canônico (Anthropic) -> OpenAI
# ---------------------------------------------------------------------------
def canonico_para_openai_messages(system_prompt: str, messages: list) -> list:
    """Converte a lista canônica para o formato de mensagens da OpenAI.

    - system vira {"role":"system","content":..}
    - assistant com tool_use vira message com tool_calls (arguments = string JSON)
    - tool_result vira UMA mensagem {"role":"tool","tool_call_id":..,"content":..}
      por chamada (ordem preservada — Groq é estrito quanto a isso).
    """
    out: list = [{"role": "system", "content": system_prompt}]

    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        # texto simples (pergunta do usuário)
        if isinstance(content, str):
            out.append({"role": role, "content": content})
            continue

        if role == "assistant":
            texto = ""
            tool_calls = []
            for bloco in content:
                btype = _bloco_tipo(bloco)
                if btype == "text":
                    texto += _bloco_get(bloco, "text") or ""
                elif btype == "tool_use":
                    tool_calls.append({
                        "id": _bloco_get(bloco, "id"),
                        "type": "function",
                        "function": {
                            "name": _bloco_get(bloco, "name"),
                            "arguments": json.dumps(
                                _bloco_get(bloco, "input") or {}, ensure_ascii=False
                            ),
                        },
                    })
            assistant_msg: dict = {"role": "assistant", "content": texto or None}
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            out.append(assistant_msg)

        elif role == "user":
            # pode conter tool_result(s)
            tem_tool_result = any(_bloco_tipo(b) == "tool_result" for b in content)
            if tem_tool_result:
                for bloco in content:
                    if _bloco_tipo(bloco) == "tool_result":
                        out.append({
                            "role": "tool",
                            "tool_call_id": _bloco_get(bloco, "tool_use_id"),
                            "content": _bloco_get(bloco, "content") or "",
                        })
            else:
                texto = "".join(
                    (_bloco_get(b, "text") or "") for b in content
                    if _bloco_tipo(b) == "text"
                )
                out.append({"role": "user", "content": texto})

    return out


# ---------------------------------------------------------------------------
# MESSAGES: canônico (Anthropic) -> Gemini (history de dicts)
# ---------------------------------------------------------------------------
def canonico_para_gemini_history(messages: list) -> list:
    """Converte a lista canônica para o history do Gemini (roles user/model).

    Retorna uma lista de dicts {"role": "user|model", "parts": [...]} onde parts
    pode conter texto, function_call (dict) ou function_response (dict). O provider
    materializa em objetos proto do SDK. Gemini não tem role 'system' (vai por
    system_instruction) nem tool_call_id (casa por NOME da função).
    """
    # Gemini casa tool_result por NOME (não há tool_use_id). Como o bloco canônico
    # tool_result só carrega tool_use_id, recuperamos o nome a partir dos blocos
    # tool_use já vistos (id -> nome).
    id_para_nome: dict[str, str] = {}
    history: list = []
    for msg in messages:
        role = "model" if msg["role"] == "assistant" else "user"
        content = msg["content"]

        if isinstance(content, str):
            history.append({"role": role, "parts": [{"text": content}]})
            continue

        parts: list = []
        for bloco in content:
            btype = _bloco_tipo(bloco)
            if btype == "text":
                parts.append({"text": _bloco_get(bloco, "text") or ""})
            elif btype == "tool_use":
                nome = _bloco_get(bloco, "name")
                tid = _bloco_get(bloco, "id")
                if tid:
                    id_para_nome[tid] = nome
                parts.append({"function_call": {
                    "name": nome,
                    "args": _bloco_get(bloco, "input") or {},
                }})
            elif btype == "tool_result":
                # o conteúdo é uma string JSON; embrulha em {"result": ...}
                tid = _bloco_get(bloco, "tool_use_id")
                parts.append({"function_response": {
                    "name": id_para_nome.get(tid, "tool"),
                    "response": {"result": _bloco_get(bloco, "content")},
                }})
        history.append({"role": role, "parts": parts})
    return history


# ---------------------------------------------------------------------------
# Helpers: aceitam tanto dict quanto objeto com atributos (blocos do SDK)
# ---------------------------------------------------------------------------
def _bloco_tipo(bloco) -> str:
    if isinstance(bloco, dict):
        return bloco.get("type", "")
    return getattr(bloco, "type", "")


def _bloco_get(bloco, chave: str):
    if isinstance(bloco, dict):
        return bloco.get(chave)
    return getattr(bloco, chave, None)
