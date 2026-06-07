#!/usr/bin/env python3
"""Coleta de métricas baseline vs. pós-implementação (experimento da dissertação).

Envia um conjunto padronizado de consultas ao endpoint /chat e salva um resumo
em metrics/. O próprio backend (chat/agent.py) grava o log estruturado em
log_consultas_agente quando USE_QUERY_EXPANSION=true; este script salva também
um JSON local com latência/HTTP medidos do lado cliente.

Contrato REAL do endpoint: POST /chat {pergunta, historico} + header X-API-Key,
resposta {resposta, tools_usadas, session_id}.

Uso:
    # Antes do deploy (flag OFF no servidor):
    python scripts/coletar_baseline.py baseline
    # Após ativar USE_QUERY_EXPANSION=true:
    python scripts/coletar_baseline.py pos_implementacao
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("BACKEND_URL", "https://agroia-rmc.onrender.com")
API_KEY = os.getenv("API_SECRET_KEY", "")
HEAD = {"X-API-Key": API_KEY}

# 30 consultas padrão — mesmas no baseline E no pós (comparação justa).
CONSULTAS_PADRAO = [
    # PRECO
    {"id": "P01", "texto": "qual o preço da alface hoje na ceasa de curitiba"},
    {"id": "P02", "texto": "quanto custa cenoura na ceasa"},
    {"id": "P03", "texto": "preço do tomate em curitiba"},
    {"id": "P04", "texto": "cotação da couve manteiga"},
    {"id": "P05", "texto": "quanto está valendo a beterraba"},
    {"id": "P06", "texto": "valor do chuchu no mercado hoje"},
    {"id": "P07", "texto": "preço batata doce ceasa curitiba"},
    {"id": "P08", "texto": "cotação da banana para venda"},
    {"id": "P09", "texto": "qual o preço do pimentão essa semana"},
    {"id": "P10", "texto": "quanto tá pagando por quilo de mandioca"},
    # LICITACAO
    {"id": "L01", "texto": "quanto de alface a merenda comprou em 2025"},
    {"id": "L02", "texto": "volume de cenoura comprado pelo armazém da família"},
    {"id": "L03", "texto": "quais culturas a merenda escolar compra mais"},
    {"id": "L04", "texto": "quanto a prefeitura de curitiba comprou de tomate"},
    {"id": "L05", "texto": "volume de couve nas licitações do armazém da família"},
    {"id": "L06", "texto": "quais são as compras do paa em 2025"},
    {"id": "L07", "texto": "quanto de batata foi licitado pela merenda"},
    {"id": "L08", "texto": "me mostre as aquisições de banana deste ano"},
    {"id": "L09", "texto": "qual o maior volume comprado em um processo"},
    {"id": "L10", "texto": "compras de hortifruti pela merenda escolar"},
    # EDITAL
    {"id": "E01", "texto": "quais editais foram publicados pelo armazém da família em 2025"},
    {"id": "E02", "texto": "resultado do chamamento público de hortifruti"},
    {"id": "E03", "texto": "quais processos licitatórios estão ativos"},
    {"id": "E04", "texto": "me mostre o edital de credenciamento de 2025"},
    {"id": "E05", "texto": "chamamento público agricultura familiar curitiba"},
    # GERAL
    {"id": "G01", "texto": "bom dia"},
    {"id": "G02", "texto": "como faço para me cadastrar como fornecedor"},
    {"id": "G03", "texto": "o que é o programa paa"},
    {"id": "G04", "texto": "quais documentos preciso para participar do chamamento"},
    {"id": "G05", "texto": "como planto alface no inverno"},
]


def executar_consulta(client: httpx.Client, consulta: dict) -> dict:
    inicio = time.time()
    try:
        r = client.post(
            f"{BASE_URL}/chat",
            json={"pergunta": consulta["texto"], "historico": []},
            headers=HEAD,
            timeout=40,
        )
        latencia = int((time.time() - inicio) * 1000)
        sucesso = r.status_code == 200
        resposta = ""
        tools = []
        if sucesso:
            data = r.json()
            resposta = data.get("resposta", "")
            tools = data.get("tools_usadas", [])
        tem_dados = any(ch.isdigit() for ch in resposta) and len(resposta) > 30
        return {
            "consulta_id": consulta["id"],
            "consulta": consulta["texto"],
            "status_http": r.status_code,
            "sucesso_http": sucesso,
            "latencia_ms": latencia,
            "tools_usadas": tools,
            "tem_dados_estruturados": tem_dados,
            "tamanho_resposta": len(resposta),
            "resposta": resposta[:300],
        }
    except Exception as e:
        return {
            "consulta_id": consulta["id"],
            "consulta": consulta["texto"],
            "erro": str(e),
            "latencia_ms": int((time.time() - inicio) * 1000),
            "sucesso_http": False,
        }


def coletar(grupo: str) -> dict:
    print(f"\n{'='*60}\nCOLETA — GRUPO: {grupo.upper()} | {BASE_URL}\n{'='*60}\n")
    resultados = []
    with httpx.Client() as client:
        for i, consulta in enumerate(CONSULTAS_PADRAO, 1):
            print(f"[{i:02d}/{len(CONSULTAS_PADRAO)}] {consulta['id']} — {consulta['texto'][:50]}...")
            resultados.append(executar_consulta(client, consulta))
            time.sleep(2.0)  # não sobrecarregar o Render

    latencias = sorted(r["latencia_ms"] for r in resultados if "latencia_ms" in r)
    n = len(latencias)
    p50 = latencias[int(n * 0.5)] if n else 0
    p95 = latencias[min(int(n * 0.95), n - 1)] if n else 0
    sucessos = sum(1 for r in resultados if r.get("sucesso_http"))
    com_dados = sum(1 for r in resultados if r.get("tem_dados_estruturados"))

    resumo = {
        "grupo": grupo,
        "total": len(CONSULTAS_PADRAO),
        "sucesso_http_pct": round(100 * sucessos / len(CONSULTAS_PADRAO), 1),
        "tsr_pct": round(100 * com_dados / len(CONSULTAS_PADRAO), 1),
        "latencia_p50_ms": p50,
        "latencia_p95_ms": p95,
        "latencia_media_ms": round(sum(latencias) / n, 0) if n else 0,
        "coletado_em": datetime.now().isoformat(),
    }

    metrics_dir = Path("metrics")
    metrics_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    arquivo = metrics_dir / f"metricas_{grupo}_{stamp}.json"
    arquivo.write_text(
        json.dumps({"resumo": resumo, "detalhes": resultados}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n{'='*60}\nRESUMO — {grupo.upper()}")
    print(f"  Sucesso HTTP:       {resumo['sucesso_http_pct']}%")
    print(f"  TSR (proxy dados):  {resumo['tsr_pct']}%")
    print(f"  Latência P50:       {resumo['latencia_p50_ms']} ms")
    print(f"  Latência P95:       {resumo['latencia_p95_ms']} ms")
    print(f"  Salvo em:           {arquivo}")
    print(f"{'='*60}\n")
    return resumo


if __name__ == "__main__":
    grupo = sys.argv[1] if len(sys.argv) > 1 else "baseline"
    if grupo not in ("baseline", "pos_implementacao"):
        print("Uso: python scripts/coletar_baseline.py [baseline|pos_implementacao]")
        sys.exit(1)
    coletar(grupo)
