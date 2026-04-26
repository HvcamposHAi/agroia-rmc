-- ============================================================================
-- ATUALIZAR TABELA: documentos_licitacao (VERSÃO FINAL - CORRIGIDA)
-- Classificação com lógica aprimorada para evitar false positives
-- ============================================================================

-- RESETAR coluna (limpar classificações anteriores incorretas)
UPDATE documentos_licitacao
SET conteudo_agro = NULL;

-- ============================================================================
-- FASE 1: MARCAR COMO FALSE — Documentos COM marcador de exclusão explícito
-- ============================================================================
-- Estratégia: Se há "[SEM CONTEÚDO AGRÍCOLA]", marcar FALSE IMEDIATAMENTE
-- Prioridade: Excluir documentos admininstrativos/não-agrícolas de forma definitiva
UPDATE documentos_licitacao d
SET conteudo_agro = false
WHERE EXISTS (
  SELECT 1 FROM pdf_chunks pc
  WHERE pc.documento_id = d.id
  AND (
    pc.chunk_text ILIKE '%SEM CONTEÚDO AGRÍCOLA%'
    OR pc.chunk_text ILIKE '%sem conteúdo agrícola%'
    OR pc.chunk_text ILIKE '%[SEM CONTEUDO AGRICOLA]%'
    OR pc.chunk_text ILIKE '%não há informação sobre culturas agrícolas%'
    OR pc.chunk_text ILIKE '%não contém informações sobre culturas agrícolas%'
    OR pc.chunk_text ILIKE '%fora do escopo de análise de alimentos%'
    OR pc.chunk_text ILIKE '%materiais de construção%'
    OR pc.chunk_text ILIKE '%equipamento administrativo%'
    OR pc.chunk_text ILIKE '%equipamento de IT%'
    OR pc.chunk_text ILIKE '%equipamento de informática%'
  )
);

-- ============================================================================
-- FASE 2: MARCAR COMO TRUE — Documentos COM PRODUTOS AGRÍCOLAS ESPECÍFICOS
-- ============================================================================
-- Estratégia: Buscar por nomes ESPECÍFICOS de produtos alimentares/agrícolas
-- Esses são o sinal mais confiável de documento agrícola
-- Não inclui nomes de programas/canais (PNAE, PAA, Armazém) para evitar false positives
UPDATE documentos_licitacao d
SET conteudo_agro = true
WHERE d.conteudo_agro IS NULL  -- Não foi marcado FALSE em FASE 1
AND EXISTS (
  SELECT 1 FROM pdf_chunks pc
  WHERE pc.documento_id = d.id
  AND (
    -- ===== PRODUTOS LÁCTEOS (específicos) =====
    pc.chunk_text ILIKE '%LEITE%'
    OR pc.chunk_text ILIKE '%QUEIJO%'
    OR pc.chunk_text ILIKE '%IOGURTE%'
    OR pc.chunk_text ILIKE '%MANTEIGA%'
    OR pc.chunk_text ILIKE '%REQUEIJÃO%'
    OR pc.chunk_text ILIKE '%NATA%'
    OR pc.chunk_text ILIKE '%PÃO DE QUEIJO%'
    -- ===== GRÃOS E CEREAIS (específicos) =====
    OR pc.chunk_text ILIKE '%ARROZ%'
    OR pc.chunk_text ILIKE '%FEIJÃO%'
    OR pc.chunk_text ILIKE '%MILHO%'
    OR pc.chunk_text ILIKE '%TRIGO%'
    OR pc.chunk_text ILIKE '%LENTILHA%'
    OR pc.chunk_text ILIKE '%ERVILHA%'
    OR pc.chunk_text ILIKE '%AVEIA%'
    OR pc.chunk_text ILIKE '%AMENDOIM%'
    -- ===== HORTALIÇAS E FRUTAS (específicas) =====
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
    -- ===== TERMOS AGRÍCOLAS GENÉRICOS (menos específicos) =====
    OR pc.chunk_text ILIKE '%culturas agrícolas%'
    OR pc.chunk_text ILIKE '%produtos agrícolas%'
    OR pc.chunk_text ILIKE '%fornecedores agrícolas%'
    OR pc.chunk_text ILIKE '%cooperativas%'
    OR pc.chunk_text ILIKE '%agricultura familiar%'
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
-- ATUALIZAR VIEW: vw_pdf_chunks_agro com novo filtro
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
    d.conteudo_agro = true            -- E documento contém produtos agrícolas
    OR d.conteudo_agro IS NULL        -- Ou ainda não foi classificado
  );

COMMENT ON VIEW vw_pdf_chunks_agro IS
'Chunks de PDFs agrícolas com garantia DUPLA:
1. Licitação marcada como relevante_af=true
2. Documento contém nomes de produtos agrícolas ESPECÍFICOS (LEITE, ARROZ, TOMATE, etc)
Exclui documentos com [SEM CONTEÚDO AGRÍCOLA] ou equipamento/construção.
Use para RAG/busca semântica garantindo escopo exclusivamente agrícola.';

-- ============================================================================
-- DIAGNÓSTICO: Documentos marcados como FALSE (devem ser não-agrícolas)
-- ============================================================================

SELECT
  d.id,
  d.nome_arquivo,
  l.processo,
  COUNT(pc.id) as qtd_chunks,
  SUBSTRING(MAX(pc.chunk_text), 1, 150) as amostra_texto,
  CASE
    WHEN MAX(pc.chunk_text) ILIKE '%SEM CONTEÚDO AGRÍCOLA%' THEN '✓ Marker explícito'
    ELSE '⚠️ Sem marker explícito'
  END as marcador
FROM documentos_licitacao d
LEFT JOIN pdf_chunks pc ON pc.documento_id = d.id
LEFT JOIN licitacoes l ON d.licitacao_id = l.id
WHERE d.conteudo_agro = false
GROUP BY d.id, d.nome_arquivo, l.processo
ORDER BY qtd_chunks DESC
LIMIT 20;

-- ============================================================================
-- DIAGNÓSTICO: Documentos marcados como TRUE (verificar se são realmente agrícolas)
-- ============================================================================

SELECT
  d.id,
  d.nome_arquivo,
  l.processo,
  COUNT(pc.id) as qtd_chunks,
  -- Detectar quais palavras-chave agrícolas foram encontradas
  STRING_AGG(DISTINCT (
    CASE
      WHEN pc.chunk_text ILIKE '%LEITE%' THEN 'LEITE'
      WHEN pc.chunk_text ILIKE '%QUEIJO%' THEN 'QUEIJO'
      WHEN pc.chunk_text ILIKE '%ARROZ%' THEN 'ARROZ'
      WHEN pc.chunk_text ILIKE '%FEIJÃO%' THEN 'FEIJÃO'
      WHEN pc.chunk_text ILIKE '%TOMATE%' THEN 'TOMATE'
      WHEN pc.chunk_text ILIKE '%ALFACE%' THEN 'ALFACE'
      WHEN pc.chunk_text ILIKE '%BATATA%' THEN 'BATATA'
      WHEN pc.chunk_text ILIKE '%AMENDOIM%' THEN 'AMENDOIM'
      WHEN pc.chunk_text ILIKE '%culturas agrícolas%' THEN 'culturas_agr'
      WHEN pc.chunk_text ILIKE '%agriculture familiar%' THEN 'agr_familiar'
      ELSE NULL
    END
  ), ', ') as palavras_chave_detectadas
FROM documentos_licitacao d
LEFT JOIN pdf_chunks pc ON pc.documento_id = d.id
LEFT JOIN licitacoes l ON d.licitacao_id = l.id
WHERE d.conteudo_agro = true
GROUP BY d.id, d.nome_arquivo, l.processo
ORDER BY qtd_chunks DESC
LIMIT 20;

-- ============================================================================
-- DIAGNÓSTICO: Verificar se há FALSE NEGATIVES (agrícolas marcados como FALSE)
-- ============================================================================

SELECT
  d.id,
  d.nome_arquivo,
  l.processo,
  COUNT(pc.id) as qtd_chunks,
  -- Buscar por produtos agrícolas mesmo em docs marcados FALSE
  STRING_AGG(DISTINCT (
    CASE
      WHEN pc.chunk_text ILIKE '%LEITE%' THEN 'LEITE'
      WHEN pc.chunk_text ILIKE '%QUEIJO%' THEN 'QUEIJO'
      WHEN pc.chunk_text ILIKE '%ARROZ%' THEN 'ARROZ'
      WHEN pc.chunk_text ILIKE '%FEIJÃO%' THEN 'FEIJÃO'
      WHEN pc.chunk_text ILIKE '%TOMATE%' THEN 'TOMATE'
      WHEN pc.chunk_text ILIKE '%AMENDOIM%' THEN 'AMENDOIM'
      ELSE NULL
    END
  ), ', ') as produtos_agrícolas_encontrados
FROM documentos_licitacao d
LEFT JOIN pdf_chunks pc ON pc.documento_id = d.id
LEFT JOIN licitacoes l ON d.licitacao_id = l.id
WHERE d.conteudo_agro = false
  AND l.relevante_af = true
GROUP BY d.id, d.nome_arquivo, l.processo
HAVING STRING_AGG(DISTINCT (
  CASE
    WHEN pc.chunk_text ILIKE '%LEITE%' THEN 'LEITE'
    WHEN pc.chunk_text ILIKE '%QUEIJO%' THEN 'QUEIJO'
    WHEN pc.chunk_text ILIKE '%ARROZ%' THEN 'ARROZ'
    WHEN pc.chunk_text ILIKE '%FEIJÃO%' THEN 'FEIJÃO'
    WHEN pc.chunk_text ILIKE '%TOMATE%' THEN 'TOMATE'
    WHEN pc.chunk_text ILIKE '%AMENDOIM%' THEN 'AMENDOIM'
    ELSE NULL
  END
), ', ') IS NOT NULL
ORDER BY qtd_chunks DESC;

-- ⚠️ Este query identificará FALSE NEGATIVES (documentos incorretamente marcados FALSE)
