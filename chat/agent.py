import json
import os
import anthropic
from dotenv import load_dotenv
from chat.tools import TOOLS_SCHEMA, executar_tool
from chat.prompts import SYSTEM_PROMPT

load_dotenv()

def chat(pergunta: str, historico: list[dict] = None) -> dict:
    """
    Executa o agente de chat com loop tool_use.
    Retorna {"resposta": str, "tools_usadas": list[str]}
    """
    if historico is None:
        historico = []

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    messages = historico + [{"role": "user", "content": pergunta}]
    tools_usadas = []
    iteracao = 0
    max_iteracoes = 10

    while iteracao < max_iteracoes:
        iteracao += 1

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS_SCHEMA,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            texto = ""
            for bloco in response.content:
                if hasattr(bloco, "text"):
                    texto = bloco.text
            return {
                "resposta": texto,
                "tools_usadas": tools_usadas
            }

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for bloco in response.content:
                if bloco.type == "tool_use":
                    tools_usadas.append(bloco.name)
                    try:
                        resultado = executar_tool(bloco.name, bloco.input)
                        resultado_json = json.dumps(resultado, ensure_ascii=False, default=str)
                    except Exception as e:
                        resultado_json = json.dumps({"erro": str(e)}, ensure_ascii=False)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": bloco.id,
                        "content": resultado_json,
                    })

            messages.append({"role": "user", "content": tool_results})

    return {
        "resposta": "Atingi o limite de iterações. Desculpe, não consegui processar sua pergunta completamente.",
        "tools_usadas": tools_usadas
    }
