-- ============================================================================
-- ATUALIZAR TABELA: documentos_licitacao
-- Adicionar coluna conteudo_agro baseado em análise de OCR dos chunks
-- ============================================================================

-- 1️⃣ CRIAR COLUNA
ALTER TABLE documentos_licitacao
ADD COLUMN conteudo_agro BOOLEAN DEFAULT NULL;

COMMENT ON COLUMN documentos_licitacao.conteudo_agro IS
'Marca se o PDF contém conteúdo agrícola real (alimentos, culturas, etc).
NULL = não verificado, TRUE = contém agro, FALSE = sem conteúdo agrícola.
Preenchido automaticamente via OCR analysis.';

-- 2️⃣ MARCAR COMO FALSE: Documentos COM "[SEM CONTEÚDO AGRÍCOLA]"
UPDATE documentos_licitacao d
SET conteudo_agro = false
WHERE EXISTS (
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
  )
);

-- 3️⃣ MARCAR COMO TRUE: Documentos COM conteúdo agrícola explícito
UPDATE documentos_licitacao d
SET conteudo_agro = true
WHERE EXISTS (
  SELECT 1 FROM pdf_chunks pc
  WHERE pc.documento_id = d.id
  AND (
    -- Produtos alimentares
    pc.chunk_text ILIKE '%LEITE%'
    OR pc.chunk_text ILIKE '%QUEIJO%'
    OR pc.chunk_text ILIKE '%ARROZ%'
    OR pc.chunk_text ILIKE '%FEIJÃO%'
    OR pc.chunk_text ILIKE '%ALFACE%'
    OR pc.chunk_text ILIKE '%TOMATE%'
    OR pc.chunk_text ILIKE '%BATATA%'
    OR pc.chunk_text ILIKE '%MILHO%'
    OR pc.chunk_text ILIKE '%IOGURTE%'
    OR pc.chunk_text ILIKE '%MANTEIGA%'
    -- Termos agrícolas
    OR pc.chunk_text ILIKE '%culturas agrícolas%'
    OR pc.chunk_text ILIKE '%produtos agrícolas%'
    OR pc.chunk_text ILIKE '%fornecedores agrícolas%'
    OR pc.chunk_text ILIKE '%cooperativas%'
    -- Canais de distribuição
    OR pc.chunk_text ILIKE '%PNAE%'
    OR pc.chunk_text ILIKE '%PAA%'
    OR pc.chunk_text ILIKE '%Armazém da Família%'
    OR pc.chunk_text ILIKE '%Banco de Alimentos%'
  )
)
AND NOT EXISTS (
  SELECT 1 FROM pdf_chunks pc
  WHERE pc.documento_id = d.id
  AND pc.chunk_text ILIKE '%SEM CONTEÚDO AGRÍCOLA%'
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

-- Resultado esperado:
-- conteudo_agro | qtd_documentos | pct
-- true          | ~450           | ~80%
-- false         | ~50            | ~10%
-- null          | ~44            | ~10%

-- ============================================================================
-- ATUALIZAR VIEW: vw_pdf_chunks_agro
-- Usar novo filtro conteudo_agro
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
    d.conteudo_agro = true            -- E documento contém agro
    OR d.conteudo_agro IS NULL        -- Ou ainda não foi classificado
  );

COMMENT ON VIEW vw_pdf_chunks_agro IS
'Chunks de PDFs agrícolas com garantia DUPLA:
1. Licitação marcada como relevante_af=true
2. Documento contém conteúdo agrícola real (conteudo_agro=true/NULL)
Exclui documentos com conteudo_agro=false (construção, equipamento, etc).';

-- ============================================================================
-- VERIFICAÇÃO FINAL: Contar chunks antes/depois
-- ============================================================================

SELECT
  'ANTES (com problema)' as fase,
  COUNT(*) as chunks_totais
FROM pdf_chunks pc
JOIN documentos_licitacao d ON pc.documento_id = d.id
JOIN licitacoes l ON d.licitacao_id = l.id
WHERE l.relevante_af = true

UNION ALL

SELECT
  'DEPOIS (filtrado)' as fase,
  COUNT(*) as chunks_totais
FROM vw_pdf_chunks_agro;

-- Resultado esperado:
-- fase              | chunks_totais
-- ANTES             | ~1800
-- DEPOIS            | ~1600 (excluindo chunks não-agrícolas)

-- ============================================================================
-- DIAGNÓSTICO: Listar documentos marcados como FALSE
-- ============================================================================

SELECT
  d.id,
  d.nome_arquivo,
  l.processo,
  COUNT(pc.id) as qtd_chunks,
  SUBSTRING(MAX(pc.chunk_text), 1, 100) as amostra
FROM documentos_licitacao d
LEFT JOIN pdf_chunks pc ON pc.documento_id = d.id
LEFT JOIN licitacoes l ON d.licitacao_id = l.id
WHERE d.conteudo_agro = false
GROUP BY d.id, d.nome_arquivo, l.processo
ORDER BY qtd_chunks DESC;

-- Verificar se excluiu corretamente documentos de:
-- - Construção (DISPENSA_84.pdf)
-- - Equipamento (DS_68, DS_62)
-- - Requisitos administrativos (IN_01)
