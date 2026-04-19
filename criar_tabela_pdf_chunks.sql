-- =============================================================
-- Tabela pdf_chunks com pgvector para RAG
-- Execute no Supabase SQL Editor
-- =============================================================

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS pdf_chunks (
    id            bigserial PRIMARY KEY,
    licitacao_id  bigint NOT NULL REFERENCES licitacoes(id) ON DELETE CASCADE,
    documento_id  bigint REFERENCES documentos_licitacao(id) ON DELETE SET NULL,
    processo      text NOT NULL,
    nome_doc      text,
    chunk_index   int NOT NULL,
    chunk_text    text NOT NULL,
    embedding     vector(384),
    tokens_aprox  int,
    indexado_em   timestamptz DEFAULT now(),
    UNIQUE (documento_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_pdf_chunks_embedding
    ON pdf_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_pdf_chunks_processo ON pdf_chunks (processo);

CREATE OR REPLACE FUNCTION buscar_chunks_similares(
    query_embedding vector(384),
    limite          int   DEFAULT 5,
    processo_filtro text  DEFAULT NULL
)
RETURNS TABLE (
    id bigint,
    licitacao_id bigint,
    processo text,
    nome_doc text,
    chunk_index int,
    chunk_text text,
    similaridade float
)
LANGUAGE sql STABLE AS $$
    SELECT
        pc.id,
        pc.licitacao_id,
        pc.processo,
        pc.nome_doc,
        pc.chunk_index,
        pc.chunk_text,
        1 - (pc.embedding <=> query_embedding) AS similaridade
    FROM pdf_chunks pc
    WHERE processo_filtro IS NULL
       OR pc.processo ILIKE '%' || processo_filtro || '%'
    ORDER BY pc.embedding <=> query_embedding
    LIMIT limite;
$$;
