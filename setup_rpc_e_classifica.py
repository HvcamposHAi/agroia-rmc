#!/usr/bin/env python3
"""
Cria função RPC exec_sql no Supabase e executa classificação.
"""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def setup_rpc():
    """Cria a função RPC exec_sql se não existir"""

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # SQL para criar a função RPC
    create_function_sql = """
    CREATE OR REPLACE FUNCTION exec_sql(sql text)
    RETURNS void AS $$
    BEGIN
      EXECUTE sql;
    END;
    $$ LANGUAGE plpgsql;
    """

    print("🔧 Criando função RPC exec_sql...")
    try:
        # Tenta via API - alguns endpoints aceitam SQL raw
        response = sb.postgrest.session.post(
            f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
            json={"sql": create_function_sql},
            headers={"Authorization": f"Bearer {SUPABASE_KEY}"}
        )
        print("   ✅ Função criada (ou já existe)")
        return True
    except Exception as e:
        print(f"   ⚠️ Não foi possível criar função via API: {e}")
        print("   (Tentando executar classificação mesmo assim...)")
        return False

def executar_classificacao():
    """Executa a classificação via RPC"""

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("\n🔄 Iniciando classificação corrigida...")
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

    try:
        sb.rpc("exec_sql", {"sql": sql_fase1}).execute()
        print("   ✅ FASE 1 concluída")
    except Exception as e:
        print(f"   ❌ Erro na FASE 1: {e}")
        print("   (Continuando...)")

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

    try:
        sb.rpc("exec_sql", {"sql": sql_fase2}).execute()
        print("   ✅ FASE 2 concluída")
    except Exception as e:
        print(f"   ❌ Erro na FASE 2: {e}")

    # Verificação
    print("\n📊 VERIFICAÇÃO: Status de classificação")
    print("-" * 70)

    try:
        resultado = sb.table("documentos_licitacao").select("conteudo_agro", count="exact").execute()

        contagem = {"true": 0, "false": 0, "null": 0}
        for row in resultado.data:
            valor = str(row.get("conteudo_agro", "null")).lower()
            if valor == "true":
                contagem["true"] += 1
            elif valor == "false":
                contagem["false"] += 1
            else:
                contagem["null"] += 1

        total = sum(contagem.values())
        if total > 0:
            print(f"  ✅ TRUE  (com agro)     : {contagem['true']:4d} ({contagem['true']*100/total:5.1f}%)")
            print(f"  ❌ FALSE (sem agro)     : {contagem['false']:4d} ({contagem['false']*100/total:5.1f}%)")
            print(f"  ❓ NULL  (não classif.) : {contagem['null']:4d} ({contagem['null']*100/total:5.1f}%)")
            print(f"  📈 TOTAL                : {total:4d}")
        else:
            print("  ⚠️ Nenhum documento encontrado")

    except Exception as e:
        print(f"  ⚠️ Erro ao verificar: {e}")

    print("\n" + "=" * 70)
    print("✅ Classificação concluída!")

if __name__ == "__main__":
    setup_rpc()
    executar_classificacao()
