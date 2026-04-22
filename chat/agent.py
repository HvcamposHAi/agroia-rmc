import json
import os
import logging
import anthropic
from dotenv import load_dotenv
from chat.tools import TOOLS_SCHEMA, executar_tool
from chat.prompts import SYSTEM_PROMPT

load_dotenv()
logger = logging.getLogger(__name__)

def chat(pergunta: str, historico: list[dict] = None) -> dict:
    """
    Executa o agente de chat com loop tool_use.
    Retorna {"resposta": str, "tools_usadas": list[str]}
    Garante sempre retornar um dict com "resposta" válida.
    """
    if historico is None:
        historico = []

    try:
        if not pergunta or not pergunta.strip():
            return {"resposta": "Por favor, faça uma pergunta válida.", "tools_usadas": []}

        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        messages = historico + [{"role": "user", "content": pergunta}]
        tools_usadas = []
        iteracao = 0
        max_iteracoes = 10

        while iteracao < max_iteracoes:
            iteracao += 1
            logger.debug(f"Agent iteration {iteracao}/{max_iteracoes}")

            try:
                response = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=2048,
                    system=SYSTEM_PROMPT,
                    tools=TOOLS_SCHEMA,
                    messages=messages,
                    timeout=30  # Aumentado para 30s (API pode ser lenta)
                )
            except Exception as e:
                logger.error(f"Claude API error: {str(e)}", exc_info=True)
                return {
                    "resposta": "Desculpe, houve um erro ao consultar o assistente. Tente novamente.",
                    "tools_usadas": tools_usadas
                }

            if response.stop_reason == "end_turn":
                texto = ""
                for bloco in response.content:
                    if hasattr(bloco, "text"):
                        texto = bloco.text
                if not texto:
                    logger.warning("Claude returned empty text despite end_turn")
                    texto = "Não consegui gerar uma resposta. Tente reformular sua pergunta."
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
                        logger.debug(f"Executing tool: {bloco.name}")
                        try:
                            resultado = executar_tool(bloco.name, bloco.input)
                            resultado_json = json.dumps(resultado, ensure_ascii=False, default=str)
                        except Exception as e:
                            logger.error(f"Tool {bloco.name} error: {str(e)}")
                            resultado_json = json.dumps({"erro": str(e)}, ensure_ascii=False)

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": bloco.id,
                            "content": resultado_json,
                        })

                messages.append({"role": "user", "content": tool_results})

        logger.warning(f"Reached max iterations {max_iteracoes}")
        return {
            "resposta": "Sua pergunta é muito complexa. Tente dividir em perguntas menores ou mais específicas.",
            "tools_usadas": tools_usadas
        }

    except Exception as e:
        logger.error(f"Unexpected error in chat(): {str(e)}", exc_info=True)
        return {
            "resposta": "Desculpe, ocorreu um erro inesperado. Tente novamente.",
            "tools_usadas": []
        }
