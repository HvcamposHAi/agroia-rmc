#!/usr/bin/env python3
"""
Classificação de conteúdo agrícola para documentos.
Usa conexão PostgreSQL direta ao Supabase.
"""

import os
import sys
from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def get_db_connection():
    """Conecta ao PostgreSQL do Supabase"""
    # Extrai host da URL (ex: rsphlvcekuomvpvjqxqm.supabase.co)
    url_parts = SUPABASE_URL.replace("https://", "").split(".")
    host = f"{url_parts[0]}.supabase.co"

    conn = psycopg2.connect(
        host=host,
        user="postgres",
        password=SUPABASE_KEY,
        database="postgres",
        port=5432,
        sslmode="require"
    )
    return conn

def executar_classificacao():
    """Executa classificação com lógica invertida: TRUE se houver agro, FALSE se exclusão + sem agro"""

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        print("🔄 Iniciando classificação corrigida...")
        print("=" * 70)

        # FASE 1: Marcar TRUE (documentos COM conteúdo agrícola positivo)
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
            cur.execute(sql_fase1)
            conn.commit()
            rows_fase1 = cur.rowcount
            print(f"   ✅ FASE 1 concluída - {rows_fase1} documentos marcados como TRUE")
        except Exception as e:
            conn.rollback()
            print(f"   ❌ Erro na FASE 1: {e}")
            return False

        # FASE 2: Marcar FALSE (documentos SEM conteúdo agrícola + exclusão)
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
            cur.execute(sql_fase2)
            conn.commit()
            rows_fase2 = cur.rowcount
            print(f"   ✅ FASE 2 concluída - {rows_fase2} documentos marcados como FALSE")
        except Exception as e:
            conn.rollback()
            print(f"   ❌ Erro na FASE 2: {e}")
            return False

        # Verificação: Contar por classificação
        print("\n📊 VERIFICAÇÃO: Distribuição de classificação")
        print("-" * 70)

        sql_verificacao = """
SELECT
  conteudo_agro,
  COUNT(*) as qtd_documentos,
  ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM documentos_licitacao), 1) as pct
FROM documentos_licitacao
GROUP BY conteudo_agro
ORDER BY conteudo_agro DESC;
        """

        try:
            cur.execute(sql_verificacao)
            resultados = cur.fetchall()

            for row in resultados:
                status_icon = "✅" if row[0] == True else ("❌" if row[0] == False else "❓")
                status_label = "TRUE (com agro)" if row[0] == True else ("FALSE (sem agro)" if row[0] == False else "NULL (não classif.)")
                print(f"  {status_icon} {status_label:20s}: {row[1]:4d} ({row[2]:5.1f}%)")
        except Exception as e:
            print(f"  ⚠️ Erro ao contar: {e}")

        # Diagnóstico: Documentos FALSE
        print("\n🔍 DIAGNÓSTICO: Exemplos de documentos marcados como FALSE")
        print("-" * 70)

        sql_false_docs = """
SELECT
  d.id,
  d.nome_arquivo,
  COUNT(pc.id) as qtd_chunks
FROM documentos_licitacao d
LEFT JOIN pdf_chunks pc ON pc.documento_id = d.id
WHERE d.conteudo_agro = false
GROUP BY d.id, d.nome_arquivo
ORDER BY qtd_chunks DESC
LIMIT 5;
        """

        try:
            cur.execute(sql_false_docs)
            false_docs = cur.fetchall()

            if false_docs:
                for doc in false_docs:
                    print(f"  • {doc[1]} ({doc[2]} chunks)")
            else:
                print("  (nenhum documento marcado como FALSE)")
        except Exception as e:
            print(f"  ⚠️ Erro: {e}")

        cur.close()
        conn.close()

        print("\n" + "=" * 70)
        print("✅ Classificação corrigida concluída com sucesso!")
        return True

    except Exception as e:
        print(f"❌ Erro de conexão: {e}")
        return False

if __name__ == "__main__":
    sucesso = executar_classificacao()
    sys.exit(0 if sucesso else 1)
