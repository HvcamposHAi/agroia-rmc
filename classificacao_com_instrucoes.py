#!/usr/bin/env python3
"""
Manual: Execute a classificação copiando SQL no Supabase SQL Editor.
"""

import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

print("""
🔴 ATENÇÃO: Função RPC não existe ainda

Para completar a classificação, você precisa:

1. Abra https://app.supabase.com/project/rsphlvcekuomvpvjqxqm/sql/new
2. Copie E EXECUTE este SQL (sequencialmente, em 3 passos):

""")

print("=" * 80)
print("PASSO 1: Criar função RPC")
print("=" * 80)
print("""
CREATE OR REPLACE FUNCTION public.exec_sql(sql_text text)
RETURNS json AS $$
DECLARE
  result json;
BEGIN
  EXECUTE sql_text;
  RETURN json_build_object('sucesso', true);
EXCEPTION WHEN OTHERS THEN
  RETURN json_build_object('sucesso', false, 'erro', SQLERRM);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION public.exec_sql(text) TO anon, authenticated, service_role;
""")

print("=" * 80)
print("PASSO 2: Fase 1 - Marcar TRUE (com conteúdo agrícola)")
print("=" * 80)
print("""
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
""")

print("=" * 80)
print("PASSO 3: Fase 2 - Marcar FALSE (sem agro, mas com marcador explícito)")
print("=" * 80)
print("""
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
""")

print("=" * 80)
print("PASSO 4: Verificar resultado")
print("=" * 80)
print("""
SELECT
  conteudo_agro,
  COUNT(*) as qtd_documentos,
  ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM documentos_licitacao), 1) as pct
FROM documentos_licitacao
GROUP BY conteudo_agro
ORDER BY conteudo_agro DESC;
""")

print("=" * 80)
print("""
💡 Link rápido: https://app.supabase.com/project/rsphlvcekuomvpvjqxqm/sql/new

⏱️ Tempo estimado: 30 segundos para executar todo o SQL

✅ Quando terminar, execute: python dados_atualizados.py --resumo
""")
