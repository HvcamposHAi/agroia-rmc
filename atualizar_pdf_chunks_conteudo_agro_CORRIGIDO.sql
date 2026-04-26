-- ============================================================================
-- ATUALIZAR TABELA: documentos_licitacao (VERSÃO CORRIGIDA)
-- Classificação com lógica invertida para evitar false negatives
-- ============================================================================

-- 1️⃣ CRIAR COLUNA (se não existir)
ALTER TABLE documentos_licitacao
ADD COLUMN IF NOT EXISTS conteudo_agro BOOLEAN DEFAULT NULL;

COMMENT ON COLUMN documentos_licitacao.conteudo_agro IS
'Marca se o PDF contém conteúdo agrícola real (alimentos, culturas, etc).
NULL = não verificado/incerto, TRUE = contém agro, FALSE = sem conteúdo agrícola.
Preenchido automaticamente via OCR analysis com lógica: TRUE se houver palavras-chave
agrícolas POSITIVAS, FALSE só se houver exclusão explícita E sem conteúdo positivo.';

-- ============================================================================
-- FASE 1: MARCAR COMO TRUE — Documentos COM palavras-chave agrícolas POSITIVAS
-- ============================================================================
-- Este é o filtro principal: se há QUALQUER evidência de agricultura, marcar TRUE
-- Prioridade: capturar TODOS os documentos com agricultura real
UPDATE documentos_licitacao d
SET conteudo_agro = true
WHERE EXISTS (
  SELECT 1 FROM pdf_chunks pc
  WHERE pc.documento_id = d.id
  AND (
    -- Produtos lácteos (maior categoria)
    pc.chunk_text ILIKE '%LEITE%'
    OR pc.chunk_text ILIKE '%QUEIJO%'
    OR pc.chunk_text ILIKE '%IOGURTE%'
    OR pc.chunk_text ILIKE '%MANTEIGA%'
    OR pc.chunk_text ILIKE '%REQUEIJÃO%'
    OR pc.chunk_text ILIKE '%NATA%'
    OR pc.chunk_text ILIKE '%PÃO DE QUEIJO%'
    -- Grãos e cereais
    OR pc.chunk_text ILIKE '%ARROZ%'
    OR pc.chunk_text ILIKE '%FEIJÃO%'
    OR pc.chunk_text ILIKE '%MILHO%'
    OR pc.chunk_text ILIKE '%TRIGO%'
    OR pc.chunk_text ILIKE '%LENTILHA%'
    OR pc.chunk_text ILIKE '%ERVILHA%'
    OR pc.chunk_text ILIKE '%AVEIA%'
    OR pc.chunk_text ILIKE '%AMENDOIM%'
    OR pc.chunk_text ILIKE '%AMIDO%'
    -- Hortaliças e frutas
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
    -- Temperos e extratos
    OR pc.chunk_text ILIKE '%TEMPERO%'
    OR pc.chunk_text ILIKE '%EXTRATO%'
    -- Termos agrícolas genéricos
    OR pc.chunk_text ILIKE '%culturas agrícolas%'
    OR pc.chunk_text ILIKE '%produtos agrícolas%'
    OR pc.chunk_text ILIKE '%fornecedores agrícolas%'
    OR pc.chunk_text ILIKE '%cooperativas%'
    OR pc.chunk_text ILIKE '%agricultura familiar%'
    -- Canais de distribuição agrícola
    OR pc.chunk_text ILIKE '%PNAE%'
    OR pc.chunk_text ILIKE '%PAA%'
    OR pc.chunk_text ILIKE '%Armazém da Família%'
    OR pc.chunk_text ILIKE '%ARMAZEM DA FAMILIA%'
    OR pc.chunk_text ILIKE '%Banco de Alimentos%'
  )
)
AND (d.conteudo_agro IS NULL OR d.conteudo_agro = false);  -- Apenas documentos não processados ou marcados FALSE

-- ============================================================================
-- FASE 2: MARCAR COMO FALSE — Documentos EXPLICITAMENTE SEM conteúdo agrícola
-- ============================================================================
-- Estratégia: FALSE APENAS se há marcador de exclusão E NENHUMA palavra-chave positiva
UPDATE documentos_licitacao d
SET conteudo_agro = false
WHERE d.conteudo_agro IS NULL  -- Ainda não classificado em FASE 1
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
  -- Verificar que REALMENTE não há palavras-chave positivas
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

-- ============================================================================
-- VERIFICAÇÃO: Contar documentos por classificação
-- ============================================================================

SELECT
  conteudo_agro,
  COUNT(*) as qtd_documentos,
  ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM documentos_licitacao), 1) as pct
FROM documentos_licitacao
GROUP BY conteudo_agro
ORDER BY conteudo_agro DESC;

-- ============================================================================
-- ATUALIZAR VIEW: vw_pdf_chunks_agro com filtro conteudo_agro
-- ============================================================================

DROP VIEW IF EXISTS vw_pdf_chunks_agro CASCADE;

CREATE OR REPLACE VIEW vw_pdf_chunks_agro AS
SELECT
    pc.id,
    pc.licitacao_id,
    pc.documento_id,
    pc.processo,
    pc.nome_doc,
    pc.chunk_index,
    pc.chunk_text,
    pc.embedding,
    pc.tokens_aprox,
    pc.indexado_em,
    l.relevante_af,
    d.nome_arquivo,
    d.conteudo_agro
FROM pdf_chunks pc
INNER JOIN documentos_licitacao d ON pc.documento_id = d.id
INNER JOIN licitacoes l ON d.licitacao_id = l.id
WHERE l.relevante_af = true           -- Licitação é agrícola
  AND (
    d.conteudo_agro = true            -- E documento contém agro CONFIRMADO
    OR d.conteudo_agro IS NULL        -- Ou ainda não foi classificado (incluir na busca)
  );

COMMENT ON VIEW vw_pdf_chunks_agro IS
'Chunks de PDFs agrícolas com garantia DUPLA:
1. Licitação marcada como relevante_af=true
2. Documento contém conteúdo agrícola real (conteudo_agro=true) OU não classificado (NULL)
Exclui documentos com conteudo_agro=false (construção, equipamento IT, etc).
Use para RAG/busca semântica garantindo escopo exclusivamente agrícola.';

-- ============================================================================
-- DIAGNÓSTICO: Listar documentos marcados como FALSE
-- ============================================================================

SELECT
  d.id,
  d.nome_arquivo,
  l.processo,
  d.conteudo_agro,
  COUNT(pc.id) as qtd_chunks,
  SUBSTRING(MAX(pc.chunk_text), 1, 150) as amostra_texto
FROM documentos_licitacao d
LEFT JOIN pdf_chunks pc ON pc.documento_id = d.id
LEFT JOIN licitacoes l ON d.licitacao_id = l.id
WHERE d.conteudo_agro = false
GROUP BY d.id, d.nome_arquivo, l.processo, d.conteudo_agro
ORDER BY qtd_chunks DESC
LIMIT 20;

-- Resultado esperado: Documentos sobre IT, construção, equipamento (sem conteúdo agrícola)

-- ============================================================================
-- DIAGNÓSTICO: Verificar FALSE POSITIVES (documentos agrícolas marcados FALSE)
-- ============================================================================

SELECT
  d.id,
  d.nome_arquivo,
  l.processo,
  d.conteudo_agro,
  COUNT(pc.id) as qtd_chunks,
  -- Amostra que contém palavras agrícolas
  STRING_AGG(DISTINCT (
    CASE
      WHEN pc.chunk_text ILIKE '%LEITE%' THEN 'LEITE'
      WHEN pc.chunk_text ILIKE '%QUEIJO%' THEN 'QUEIJO'
      WHEN pc.chunk_text ILIKE '%ARROZ%' THEN 'ARROZ'
      WHEN pc.chunk_text ILIKE '%FEIJÃO%' THEN 'FEIJÃO'
      WHEN pc.chunk_text ILIKE '%AMENDOIM%' THEN 'AMENDOIM'
      WHEN pc.chunk_text ILIKE '%TOMATE%' THEN 'TOMATE'
      ELSE NULL
    END
  ), ', ') as produtos_agrícolas_detectados
FROM documentos_licitacao d
LEFT JOIN pdf_chunks pc ON pc.documento_id = d.id
LEFT JOIN licitacoes l ON d.licitacao_id = l.id
WHERE d.conteudo_agro = false  -- Marcados como FALSE
  AND l.relevante_af = true    -- Mas de licitações agrícolas
GROUP BY d.id, d.nome_arquivo, l.processo, d.conteudo_agro
HAVING STRING_AGG(DISTINCT (
  CASE
    WHEN pc.chunk_text ILIKE '%LEITE%' THEN 'LEITE'
    WHEN pc.chunk_text ILIKE '%QUEIJO%' THEN 'QUEIJO'
    WHEN pc.chunk_text ILIKE '%ARROZ%' THEN 'ARROZ'
    WHEN pc.chunk_text ILIKE '%FEIJÃO%' THEN 'FEIJÃO'
    WHEN pc.chunk_text ILIKE '%AMENDOIM%' THEN 'AMENDOIM'
    WHEN pc.chunk_text ILIKE '%TOMATE%' THEN 'TOMATE'
    ELSE NULL
  END
), ', ') IS NOT NULL  -- Só mostrar se houver produtos detectados
ORDER BY qtd_chunks DESC;

-- ⚠️ Este query identificará FALSE POSITIVES (documentos incorretamente marcados FALSE)
