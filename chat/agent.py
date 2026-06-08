import json
import os
import time
import threading
import logging
import anthropic
from typing import Generator
from dotenv import load_dotenv
from chat.tools import TOOLS_SCHEMA, executar_tool
from chat.prompts import SYSTEM_PROMPT

load_dotenv()
logger = logging.getLogger(__name__)

# Feature flag: quando 'false' (default) o pipeline de expansão nem executa,
# preservando o comportamento original do agente.
USE_QUERY_EXPANSION = os.getenv("USE_QUERY_EXPANSION", "false").lower() == "true"

_anthropic_client: anthropic.Anthropic | None = None

def get_client() -> anthropic.Anthropic:
	global _anthropic_client
	if _anthropic_client is None:
		_anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
	return _anthropic_client

def _registrar_log(dados: dict) -> None:
	"""Registra um turno em log_consultas_agente de forma não-bloqueante.

	O insert roda em thread daemon; qualquer falha é silenciada para que o
	log NUNCA quebre o fluxo principal do chat (F-04).
	"""
	def _run():
		try:
			from chat.db import get_supabase_client
			get_supabase_client().table("log_consultas_agente").insert(dados).execute()
		except Exception:
			pass

	try:
		threading.Thread(target=_run, daemon=True).start()
	except Exception:
		pass

def chat(pergunta: str, historico: list[dict] = None, system_prompt: str = SYSTEM_PROMPT,
         tools: list = None) -> dict:
    """
    Executa o agente de chat com loop tool_use.
    Retorna {"resposta": str, "tools_usadas": list[str]}
    Garante sempre retornar um dict com "resposta" válida.
    system_prompt permite usar um prompt focado (ex.: PRECOS_SYSTEM_PROMPT) sem duplicar o loop.
    tools permite restringir o conjunto de tools (default: TOOLS_SCHEMA = comportamento atual).
    """
    if historico is None:
        historico = []
    if tools is None:
        tools = TOOLS_SCHEMA

    try:
        if not pergunta or not pergunta.strip():
            return {"resposta": "Por favor, faça uma pergunta válida.", "tools_usadas": []}

        # === SWITCH GLOBAL DE MOTOR ===
        # Com motor != claude, delega ao loop agêntico fiel (benchmark.agentic_loop),
        # usando o MESMO system_prompt e tools. Com claude (default), segue o
        # caminho de produção abaixo, byte-idêntico ao histórico.
        try:
            from chat.motor_router import get_motor_ativo, resolver_provider
            _motor = get_motor_ativo()
            if _motor != "claude":
                provider = resolver_provider(_motor)
                from benchmark.agentic_loop import rodar_loop
                _res = rodar_loop(provider, pergunta, system_prompt=system_prompt, tools_schema=tools)
                if _res.erro:
                    logger.error(f"Motor {_motor} erro: {_res.erro}")
                    return {"resposta": "Desculpe, houve um erro ao consultar o assistente. Tente novamente.",
                            "tools_usadas": _res.tools_usadas}
                return {"resposta": _res.resposta, "tools_usadas": _res.tools_usadas}
        except Exception as e:
            logger.warning(f"Switch de motor falhou ({e}); usando Claude (default).")

        # === QUERY AGENT (opcional, guardado por feature flag) ===
        # Expande a pergunta com termos canônicos/filtros do domínio e injeta um
        # hint curto no contexto. Em qualquer falha, degrada para a pergunta original.
        inicio_total = time.time()
        expansion = None
        pergunta_efetiva = pergunta
        if USE_QUERY_EXPANSION:
            try:
                from chat.query_agent import expandir_consulta
                expansion = expandir_consulta(pergunta)
                if expansion.get("contexto_hint"):
                    pergunta_efetiva = f"{pergunta}\n\n{expansion['contexto_hint']}"
            except Exception as e:
                logger.warning(f"Query expansion falhou, usando pergunta original: {e}")
                expansion = None

        client = get_client()
        messages = historico + [{"role": "user", "content": pergunta_efetiva}]
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
                    system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
                    tools=tools,
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
                if USE_QUERY_EXPANSION:
                    _registrar_log({
                        "session_id": None,
                        "consulta_original": pergunta,
                        "consulta_expandida": pergunta_efetiva if expansion else None,
                        "intencao_detectada": (expansion or {}).get("intencao"),
                        "termos_expandidos": (expansion or {}).get("termos_expandidos"),
                        "filtros_sugeridos": (expansion or {}).get("filtros_sugeridos"),
                        "tools_usadas": tools_usadas,
                        "retornou_dados": len(tools_usadas) > 0,
                        "num_tools": len(tools_usadas),
                        "resposta_gerada": texto[:500],
                        "motor_llm": "claude-haiku-4-5",
                        "latencia_query_agent_ms": (expansion or {}).get("latencia_ms"),
                        "latencia_total_ms": int((time.time() - inicio_total) * 1000),
                        "grupo_experimento": os.getenv("GRUPO_EXPERIMENTO", "pos_implementacao"),
                        "is_baseline": os.getenv("GRUPO_EXPERIMENTO", "") == "baseline",
                    })
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

def chat_stream(pergunta: str, historico: list[dict] = None, system_prompt: str = SYSTEM_PROMPT,
                tools: list = None) -> Generator[dict, None, None]:
    """
    Streaming version of chat. Yields SSE events:
    - {"tipo": "status", "msg": str} — Progress updates
    - {"tipo": "token", "texto": str} — LLM response tokens
    - {"tipo": "fim", "tools_usadas": list[str]} — Final event
    tools permite restringir o conjunto de tools (default: TOOLS_SCHEMA = comportamento atual).
    """
    if historico is None:
        historico = []
    if tools is None:
        tools = TOOLS_SCHEMA

    try:
        if not pergunta or not pergunta.strip():
            yield {"tipo": "token", "texto": "Por favor, faça uma pergunta válida."}
            yield {"tipo": "fim", "tools_usadas": []}
            return

        # === SWITCH GLOBAL DE MOTOR (não-streaming p/ não-Claude) ===
        # Claude mantém o streaming nativo abaixo (intacto). Outros motores rodam o
        # loop agêntico completo e emitem a resposta inteira de uma vez.
        try:
            from chat.motor_router import get_motor_ativo, resolver_provider
            from benchmark.providers.factory import ROTULOS
            _motor = get_motor_ativo()
            if _motor != "claude":
                yield {"tipo": "status", "msg": f"🔄 Consultando {ROTULOS.get(_motor, _motor)}..."}
                provider = resolver_provider(_motor)
                from benchmark.agentic_loop import rodar_loop
                _res = rodar_loop(provider, pergunta, system_prompt=system_prompt, tools_schema=tools)
                if _res.erro:
                    logger.error(f"Motor {_motor} erro: {_res.erro}")
                    yield {"tipo": "token", "texto": "⚠️ Desculpe, houve um erro ao consultar o assistente. Tente novamente."}
                else:
                    yield {"tipo": "token", "texto": _res.resposta}
                yield {"tipo": "fim", "tools_usadas": _res.tools_usadas}
                return
        except Exception as e:
            logger.warning(f"Switch de motor (stream) falhou ({e}); usando Claude (default).")

        client = get_client()
        yield {"tipo": "status", "msg": "🔍 Analisando sua pergunta..."}

        messages = historico + [{"role": "user", "content": pergunta}]
        tools_usadas = []
        iteracao = 0
        max_iteracoes = 10

        while iteracao < max_iteracoes:
            iteracao += 1
            logger.debug(f"Agent iteration {iteracao}/{max_iteracoes}")

            try:
                with client.messages.stream(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=2048,
                    system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
                    tools=tools,
                    messages=messages,
                    timeout=30
                ) as stream:
                    resposta_texto = ""
                    tool_calls = []

                    for event in stream:
                        if event.type == "content_block_delta":
                            if hasattr(event.delta, "text"):
                                texto = event.delta.text
                                resposta_texto += texto
                                yield {"tipo": "token", "texto": texto}

                    response = stream.get_final_message()

                    if response.stop_reason == "end_turn":
                        yield {"tipo": "fim", "tools_usadas": tools_usadas}
                        return

                    if response.stop_reason == "tool_use":
                        yield {"tipo": "status", "msg": "📊 Consultando o banco de dados..."}
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
                        continue

            except Exception as e:
                logger.error(f"Claude API error: {str(e)}", exc_info=True)
                yield {"tipo": "token", "texto": "⚠️ Desculpe, houve um erro ao consultar o assistente. Tente novamente."}
                yield {"tipo": "fim", "tools_usadas": tools_usadas}
                return

        logger.warning(f"Reached max iterations {max_iteracoes}")
        yield {"tipo": "token", "texto": "Sua pergunta é muito complexa. Tente dividir em perguntas menores ou mais específicas."}
        yield {"tipo": "fim", "tools_usadas": tools_usadas}

    except Exception as e:
        logger.error(f"Unexpected error in chat_stream(): {str(e)}", exc_info=True)
        yield {"tipo": "token", "texto": "Desculpe, ocorreu um erro inesperado. Tente novamente."}
        yield {"tipo": "fim", "tools_usadas": []}
