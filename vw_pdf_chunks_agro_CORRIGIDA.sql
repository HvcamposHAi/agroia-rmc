-- ============================================================================
-- VIEW: vw_pdf_chunks_agro (CORRIGIDA - Simples e Direto)
-- Retorna chunks APENAS dos 24 documentos agrícolas validados
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
    d.nome_arquivo,
    d.processo as processo_documento
FROM pdf_chunks pc
INNER JOIN vw_licitacoes_agro_documentos d ON pc.documento_id = d.id;

COMMENT ON VIEW vw_pdf_chunks_agro IS
'Chunks dos 24 documentos agrícolas validados em vw_licitacoes_agro_documentos.
Garantia: Apenas chunks de documentos com conteúdo agrícola confirmado.
Use para RAG/busca semântica em contexto exclusivamente agrícola.';

-- ============================================================================
-- VERIFICAÇÃO: Contar chunks e documentos
-- ============================================================================

SELECT
  'Documentos agrícolas' as tipo,
  COUNT(DISTINCT documento_id) as quantidade
FROM vw_pdf_chunks_agro

UNION ALL

SELECT
  'Chunks agrícolas' as tipo,
  COUNT(*) as quantidade
FROM vw_pdf_chunks_agro;

-- Resultado esperado:
-- tipo: "Documentos agrícolas", quantidade: 24
-- tipo: "Chunks agrícolas", quantidade: 44
