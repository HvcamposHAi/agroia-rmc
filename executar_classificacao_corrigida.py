#!/usr/bin/env python3
"""
Executar classificação corrigida de conteúdo agrícola em documentos.
Usa lógica invertida: TRUE se houver conteúdo positivo, FALSE apenas se exclusão + sem conteúdo.
"""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def executar_classificacao():
    """Executar SQL de classificação no Supabase."""

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ SUPABASE_URL ou SUPABASE_KEY não configurados em .env")
        sys.exit(1)

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("🔄 Iniciando classificação corrigida...")
    print("=" * 70)

    # FASE 1: Marcar TRUE (documentos COM conteúdo agrícola positivo)
    print("\n📍 FASE 1: Marcando documentos com conteúdo agrícola POSITIVO...")
    try:
        resultado = sb.rpc(
            "exec_sql",
            {
                "sql": """
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
            }
        ).execute()
        print("   ✅ FASE 1 concluída")
    except Exception as e:
        print(f"   ❌ Erro na FASE 1: {e}")
        sys.exit(1)

    # FASE 2: Marcar FALSE (documentos SEM conteúdo agrícola + exclusão)
    print("\n📍 FASE 2: Marcando documentos SEM conteúdo agrícola...")
    try:
        resultado = sb.rpc(
            "exec_sql",
            {
                "sql": """
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
            }
        ).execute()
        print("   ✅ FASE 2 concluída")
    except Exception as e:
        print(f"   ❌ Erro na FASE 2: {e}")
        sys.exit(1)

    # Verificação: Contar documentos por classificação
    print("\n📊 VERIFICAÇÃO: Distribuição de classificação")
    print("-" * 70)
    try:
        resultado = sb.from_("documentos_licitacao").select("conteudo_agro", count="exact").execute()

        # Contar por categoria
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
        print(f"  ✅ TRUE  (com agro)     : {contagem['true']:4d} ({contagem['true']*100/total:5.1f}%)")
        print(f"  ❌ FALSE (sem agro)     : {contagem['false']:4d} ({contagem['false']*100/total:5.1f}%)")
        print(f"  ❓ NULL  (não classif.) : {contagem['null']:4d} ({contagem['null']*100/total:5.1f}%)")
        print(f"  📈 TOTAL                : {total:4d}")

    except Exception as e:
        print(f"  ⚠️  Erro ao contar: {e}")

    # Verificação: Documentos FALSE (devem ser não-agrícolas)
    print("\n🔍 DIAGNÓSTICO: Documentos marcados como FALSE")
    print("-" * 70)
    try:
        resultado = sb.from_("documentos_licitacao") \
            .select("id,nome_arquivo,conteudo_agro") \
            .eq("conteudo_agro", False) \
            .limit(10) \
            .execute()

        if resultado.data:
            for doc in resultado.data[:10]:
                print(f"  • {doc['nome_arquivo']}")
        else:
            print("  (nenhum documento marcado como FALSE)")
    except Exception as e:
        print(f"  ⚠️  Erro: {e}")

    print("\n" + "=" * 70)
    print("✅ Classificação corrigida concluída!")
    print("\n🎯 Próximas ações:")
    print("  1. Verificar view 'vw_pdf_chunks_agro' foi recriada")
    print("  2. Validar que documentos PE 6/2021, PE 13/2020 estão com conteudo_agro=true")
    print("  3. Validar que documentos não-agrícolas estão com conteudo_agro=false")

if __name__ == "__main__":
    executar_classificacao()
