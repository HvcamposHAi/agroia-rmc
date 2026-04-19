-- =============================================================
-- Tabela de histórico de conversas por session_id
-- Execute no Supabase SQL Editor
-- =============================================================

CREATE TABLE IF NOT EXISTS conversas (
    id          bigserial PRIMARY KEY,
    session_id  text NOT NULL,
    role        text NOT NULL CHECK (role IN ('user', 'assistant')),
    content     text NOT NULL,
    tools_usadas text[],
    criado_em   timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_conversas_session ON conversas (session_id, criado_em);
CREATE INDEX IF NOT EXISTS idx_conversas_tempo ON conversas (criado_em DESC);
