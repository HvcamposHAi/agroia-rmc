-- =============================================================
-- MIGRAÇÃO: Novas colunas de classificação agropecuária
-- Rodar no Supabase SQL Editor UMA ÚNICA VEZ
-- Após isso, executar enriquecer_classificacao.py para popular
-- =============================================================

-- 1. Adicionar coluna categoria_v2 (substitui o campo "categoria" que estava sempre 'OUTRO')
ALTER TABLE itens_licitacao
    ADD COLUMN IF NOT EXISTS categoria_v2 text NOT NULL DEFAULT 'NAO_CLASSIFICADO';

-- 2. Adicionar flag de relevância agropecuária por item
ALTER TABLE itens_licitacao
    ADD COLUMN IF NOT EXISTS relevante_agro boolean NOT NULL DEFAULT false;

-- 3. Índices para performance nas queries analíticas
CREATE INDEX IF NOT EXISTS idx_itens_cultura
    ON itens_licitacao (cultura);

CREATE INDEX IF NOT EXISTS idx_itens_categoria_v2
    ON itens_licitacao (categoria_v2);

CREATE INDEX IF NOT EXISTS idx_itens_relevante_agro
    ON itens_licitacao (relevante_agro);

CREATE INDEX IF NOT EXISTS idx_licitacoes_canal
    ON licitacoes (canal);

CREATE INDEX IF NOT EXISTS idx_licitacoes_relevante_af
    ON licitacoes (relevante_af);

CREATE INDEX IF NOT EXISTS idx_itens_licitacao_id
    ON itens_licitacao (licitacao_id);

-- 4. Verificação pós-migração
SELECT
    column_name,
    data_type,
    column_default,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'itens_licitacao'
  AND column_name IN ('cultura', 'categoria', 'categoria_v2', 'relevante_agro')
ORDER BY column_name;
