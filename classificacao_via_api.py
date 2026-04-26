#!/usr/bin/env python3
"""
Classificação de conteúdo agrícola usando API REST Supabase.
Executa SQL via HTTP POST ao endpoint rpc.
"""

import os
import sys
import json
from dotenv import load_dotenv
import requests

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def executar_sql(sql_query):
    """Executa query SQL via Supabase RPC usando função SQL inline"""

    # Tenta criar função temporária
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    # URL do RPC endpoint
    url = f"{SUPABASE_URL}/rest/v1/rpc/exec_sql"

    payload = {"sql": sql_query}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=300)
        if response.status_code in [200, 201]:
            return True, response.json()
        else:
            return False, f"Status {response.status_code}: {response.text}"
    except Exception as e:
        return False, str(e)

def executar_classificacao():
    """Executa classificação com lógica invertida"""

    print("🔄 Iniciando classificação corrigida via API REST...")
    print("=" * 70)

    # FASE 1: Marcar TRUE
    print("\n📍 FASE 1: Marcando documentos com conteúdo agrícola POSITIVO...")

    sql_fase1 = """
UPDATE documentos_licitacao d
SET conteudo_agro = true
WHERE EXISTS (
  SELECT 1 FROM pdf_chunks pc
  WHERE pc.documento_id = d.id
  AND (
    pc.chunk_text ILIKE '%LEITE%'
    OR pc.chunk_text ILIKE '%QUEIJO%'
    OR pc.chunk_text ILIKE '%IOGURTE%'
    OR pc.chunk_text ILIKE '%MANTEIGA%'
    OR pc.chunk_text ILIKE '%REQUEIJÃO%'
    OR pc.chunk_text ILIKE '%NATA%'
    OR pc.chunk_text ILIKE '%PÃO DE QUEIJO%'
    OR pc.chunk_text ILIKE '%ARROZ%'
    OR pc.chunk_text ILIKE '%FEIJÃO%'
    OR pc.chunk_text ILIKE '%MILHO%'
    OR pc.chunk_text ILIKE '%TRIGO%'
    OR pc.chunk_text ILIKE '%LENTILHA%'
    OR pc.chunk_text ILIKE '%ERVILHA%'
    OR pc.chunk_text ILIKE '%AVEIA%'
    OR pc.chunk_text ILIKE '%AMENDOIM%'
    OR pc.chunk_text ILIKE '%AMIDO%'
    OR pc.chunk_text ILIKE '%TOMATE%'
    OR pc.chunk_text ILIKE '%ALFACE%'
    OR pc.chunk_text ILIKE '%BATATA%'
    OR pc.chunk_text ILIKE '%PEPINO%'
    OR pc.chunk_text ILIKE '%MANDIOCA%'
    OR pc.chunk_text ILIKE '%ABÓBORA%'
    OR pc.chunk_text ILIKE '%UVA%'
    OR pc.chunk_text ILIKE '%AMEIXA%'
    OR pc.chunk_text ILIKE '%GOIABADA%'
    OR pc.chunk_text ILIKE '%EXTRATO DE TOMATE%'
    OR pc.chunk_text ILIKE '%TEMPERO%'
    OR pc.chunk_text ILIKE '%EXTRATO%'
    OR pc.chunk_text ILIKE '%culturas agrícolas%'
    OR pc.chunk_text ILIKE '%produtos agrícolas%'
    OR pc.chunk_text ILIKE '%fornecedores agrícolas%'
    OR pc.chunk_text ILIKE '%cooperativas%'
    OR pc.chunk_text ILIKE '%agricultura familiar%'
    OR pc.chunk_text ILIKE '%PNAE%'
    OR pc.chunk_text ILIKE '%PAA%'
    OR pc.chunk_text ILIKE '%Armazém da Família%'
    OR pc.chunk_text ILIKE '%ARMAZEM DA FAMILIA%'
    OR pc.chunk_text ILIKE '%Banco de Alimentos%'
  )
)
AND (d.conteudo_agro IS NULL OR d.conteudo_agro = false);
    """

    sucesso, resultado = executar_sql(sql_fase1)
    if sucesso:
        print("   ✅ FASE 1 concluída")
    else:
        print(f"   ⚠️ Nota: {resultado}")
        print("   (Continuando mesmo assim...)")

    # FASE 2: Marcar FALSE
    print("\n📍 FASE 2: Marcando documentos SEM conteúdo agrícola...")

    sql_fase2 = """
UPDATE documentos_licitacao d
SET conteudo_agro = false
WHERE d.conteudo_agro IS NULL
AND EXISTS (
  SELECT 1 FROM pdf_chunks pc
  WHERE pc.documento_id = d.id
  AND (
    pc.chunk_text ILIKE '%SEM CONTEÚDO AGRÍCOLA%'
    OR pc.chunk_text ILIKE '%sem conteúdo agrícola%'
    OR pc.chunk_text ILIKE '%não há informação sobre culturas agrícolas%'
    OR pc.chunk_text ILIKE '%não contém informações sobre culturas agrícolas%'
    OR pc.chunk_text ILIKE '%fora do escopo de análise de alimentos%'
    OR pc.chunk_text ILIKE '%materiais de construção%'
    OR pc.chunk_text ILIKE '%equipamento administrativo%'
    OR pc.chunk_text ILIKE '%equipamento de IT%'
    OR pc.chunk_text ILIKE '%servidor%'
    OR pc.chunk_text ILIKE '%licenças de software%'
  )
)
AND NOT EXISTS (
  SELECT 1 FROM pdf_chunks pc
  WHERE pc.documento_id = d.id
  AND (
    pc.chunk_text ILIKE '%LEITE%'
    OR pc.chunk_text ILIKE '%QUEIJO%'
    OR pc.chunk_text ILIKE '%IOGURTE%'
    OR pc.chunk_text ILIKE '%ARROZ%'
    OR pc.chunk_text ILIKE '%FEIJÃO%'
    OR pc.chunk_text ILIKE '%MILHO%'
    OR pc.chunk_text ILIKE '%TOMATE%'
    OR pc.chunk_text ILIKE '%ALFACE%'
    OR pc.chunk_text ILIKE '%BATATA%'
    OR pc.chunk_text ILIKE '%PEPINO%'
    OR pc.chunk_text ILIKE '%MANDIOCA%'
    OR pc.chunk_text ILIKE '%ABÓBORA%'
    OR pc.chunk_text ILIKE '%UVA%'
    OR pc.chunk_text ILIKE '%AMENDOIM%'
    OR pc.chunk_text ILIKE '%MANTEIGA%'
    OR pc.chunk_text ILIKE '%REQUEIJÃO%'
    OR pc.chunk_text ILIKE '%culturas agrícolas%'
    OR pc.chunk_text ILIKE '%agricultura familiar%'
    OR pc.chunk_text ILIKE '%PNAE%'
    OR pc.chunk_text ILIKE '%PAA%'
  )
);
    """

    sucesso, resultado = executar_sql(sql_fase2)
    if sucesso:
        print("   ✅ FASE 2 concluída")
    else:
        print(f"   ⚠️ Nota: {resultado}")

    # Verificação via API REST
    print("\n📊 VERIFICAÇÃO: Status de classificação")
    print("-" * 70)

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }

    try:
        # Contar TRUE
        url_true = f"{SUPABASE_URL}/rest/v1/documentos_licitacao?conteudo_agro=eq.true&select=count"
        r_true = requests.get(url_true, headers=headers)
        count_true = r_true.headers.get("content-range", "0").split("/")[1] if "content-range" in r_true.headers else "?"

        # Contar FALSE
        url_false = f"{SUPABASE_URL}/rest/v1/documentos_licitacao?conteudo_agro=eq.false&select=count"
        r_false = requests.get(url_false, headers=headers)
        count_false = r_false.headers.get("content-range", "0").split("/")[1] if "content-range" in r_false.headers else "?"

        # Contar NULL
        url_null = f"{SUPABASE_URL}/rest/v1/documentos_licitacao?conteudo_agro=is.null&select=count"
        r_null = requests.get(url_null, headers=headers)
        count_null = r_null.headers.get("content-range", "0").split("/")[1] if "content-range" in r_null.headers else "?"

        print(f"  ✅ TRUE  (com agro)     : {count_true}")
        print(f"  ❌ FALSE (sem agro)     : {count_false}")
        print(f"  ❓ NULL  (não classif.) : {count_null}")

    except Exception as e:
        print(f"  ⚠️ Erro ao verificar: {e}")

    print("\n" + "=" * 70)
    print("✅ Classificação concluída!")
    print("\n🎯 Próximas ações:")
    print("  1. Verificar se documentos críticos foram classificados corretamente")
    print("  2. Retomar coleta de PDFs com: python etapa3_producao.py --resume")

if __name__ == "__main__":
    executar_classificacao()
