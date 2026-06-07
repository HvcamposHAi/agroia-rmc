"""Mini-loop agêntico provider-agnóstico para o benchmark.

Espelha a semântica de chat.agent.chat() (chat/agent.py:85-163) sem tocar nele:
mesma serialização de tool_result, mesmo tratamento de erro de tool, mesmo cap de
iterações. A diferença é que o turno do LLM passa por um LLMProvider abstrato, o que
permite trocar o motor mantendo a chamada a executar_tool IDÊNTICA.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

# Imports SOMENTE-LEITURA de produção (nunca chat.agent).
from chat.tools import TOOLS_SCHEMA, executar_tool
from chat.prompts import SYSTEM_PROMPT

from benchmark.providers.base import LLMProvider


@dataclass
class ExecucaoResultado:
    """Resultado de rodar uma pergunta ponta-a-ponta por um motor."""
    resposta: str = ""
    tools_usadas: list[str] = field(default_factory=list)
    tool_calls_detalhe: list[dict] = field(default_factory=list)  # [{nome, inputs}]
    iteracoes: int = 0
    latencia_total_ms: int = 0
    latencia_por_iter_ms: list[int] = field(default_factory=list)
    tokens_entrada: int = 0
    tokens_saida: int = 0
    tokens_estimados: bool = False
    stop_reason_final: str = ""
    tool_result_truncado: bool = False
    erro: str | None = None


def rodar_loop(
    provider: LLMProvider,
    pergunta: str,
    system_prompt: str = SYSTEM_PROMPT,
    tools_schema: list | None = None,
    max_iteracoes: int = 10,
    timeout: int = 30,
    max_tool_result_chars: int | None = None,
) -> ExecucaoResultado:
    """Roda o loop tool_use para `pergunta` usando `provider`.

    max_tool_result_chars: se definido, trunca o JSON de cada tool_result a esse
    tamanho (usado p/ motores de janela curta, ex.: Sabiá-3 8k). Marca o resultado.
    """
    if tools_schema is None:
        tools_schema = TOOLS_SCHEMA

    res = ExecucaoResultado()
    inicio_total = time.monotonic()

    if not pergunta or not pergunta.strip():
        res.resposta = "Por favor, faça uma pergunta válida."
        res.stop_reason_final = "end_turn"
        return res

    # Lista canônica (formato Anthropic).
    messages: list = [{"role": "user", "content": pergunta}]
    iteracao = 0

    try:
        while iteracao < max_iteracoes:
            iteracao += 1
            resp = provider.gerar(
                system_prompt=system_prompt,
                tools_schema=tools_schema,
                messages=messages,
                max_tokens=2048,
                timeout=timeout,
            )
            res.latencia_por_iter_ms.append(int(resp.latencia_ms))
            res.tokens_entrada += int(resp.tokens_entrada or 0)
            res.tokens_saida += int(resp.tokens_saida or 0)
            if resp.tokens_estimados:
                res.tokens_estimados = True

            if resp.stop_reason == "erro":
                res.erro = resp.texto or "erro desconhecido no provider"
                res.stop_reason_final = "erro"
                res.iteracoes = iteracao
                res.latencia_total_ms = int((time.monotonic() - inicio_total) * 1000)
                return res

            if resp.stop_reason in ("end_turn", "max_tokens") and not resp.tool_calls:
                res.resposta = resp.texto or ""
                res.stop_reason_final = resp.stop_reason
                res.iteracoes = iteracao
                res.latencia_total_ms = int((time.monotonic() - inicio_total) * 1000)
                return res

            # Há chamadas de ferramenta — reconstrói o turno assistant canônico.
            assistant_blocos: list = []
            if resp.texto:
                assistant_blocos.append({"type": "text", "text": resp.texto})
            for tc in resp.tool_calls:
                assistant_blocos.append({
                    "type": "tool_use", "id": tc.id, "name": tc.nome, "input": tc.inputs,
                })
            messages.append({"role": "assistant", "content": assistant_blocos})

            # Executa cada tool — IDÊNTICO a produção (chat/agent.py:144-155).
            tool_results: list = []
            for tc in resp.tool_calls:
                res.tools_usadas.append(tc.nome)
                res.tool_calls_detalhe.append({"nome": tc.nome, "inputs": tc.inputs})
                try:
                    resultado = executar_tool(tc.nome, tc.inputs)
                    resultado_json = json.dumps(resultado, ensure_ascii=False, default=str)
                except Exception as e:  # noqa: BLE001 — espelha produção
                    resultado_json = json.dumps({"erro": str(e)}, ensure_ascii=False)

                if max_tool_result_chars and len(resultado_json) > max_tool_result_chars:
                    resultado_json = resultado_json[:max_tool_result_chars] + '..."[truncado]"'
                    res.tool_result_truncado = True

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": resultado_json,
                })
            messages.append({"role": "user", "content": tool_results})

        # Atingiu o teto de iterações.
        res.resposta = (
            "Sua pergunta é muito complexa. Tente dividir em perguntas menores ou mais específicas."
        )
        res.stop_reason_final = "max_iteracoes"
        res.iteracoes = iteracao
        res.latencia_total_ms = int((time.monotonic() - inicio_total) * 1000)
        return res

    except Exception as e:  # noqa: BLE001 — loop nunca deve crashar o executor
        res.erro = str(e)
        res.stop_reason_final = "erro"
        res.iteracoes = iteracao
        res.latencia_total_ms = int((time.monotonic() - inicio_total) * 1000)
        return res
