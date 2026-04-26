-- ============================================================================
-- CREATE VIEW: vw_pdf_chunks_agro
-- Filtra chunks de PDFs apenas de licitações agrícolas (relevante_af=true)
-- Uso: RAG (Retrieval-Augmented Generation) com contexto agrícola exclusivo
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
    d.nome_arquivo
FROM pdf_chunks pc
INNER JOIN documentos_licitacao d ON pc.documento_id = d.id
INNER JOIN licitacoes l ON d.licitacao_id = l.id
WHERE l.relevante_af = true;  -- ✅ FILTRO CRÍTICO: APENAS AGRICULTURA

-- Comentário para documentação
COMMENT ON VIEW vw_pdf_chunks_agro IS
'Chunks de PDFs apenas de licitações agrícolas (relevante_af=true).
Use esta view para RAG/busca semântica em contexto agrícola exclusivamente.
Garante que respostas baseadas em documentos respeitam escopo do projeto.';

-- Índice para busca semântica rápida (herdado de pdf_chunks, aplicável à view)
-- SELECT pc.id, pc.chunk_text, pc.embedding
-- FROM vw_pdf_chunks_agro pc
-- WHERE pc.embedding <-> query_embedding < 0.3
-- ORDER BY pc.embedding <-> query_embedding
-- LIMIT 5;

-- ============================================================================
-- VERIFICAÇÃO: Contar chunks agrícolas vs totais
-- ============================================================================

-- Chunks agrícolas (via view)
SELECT COUNT(*) as chunks_agro FROM vw_pdf_chunks_agro;

-- Chunks totais (incluindo não-agrícolas)
SELECT COUNT(*) as chunks_totais FROM pdf_chunks;

-- Proporção
SELECT
    (SELECT COUNT(*) FROM vw_pdf_chunks_agro)::numeric /
    NULLIF((SELECT COUNT(*) FROM pdf_chunks), 0) * 100 as pct_chunks_agro;
