-- =============================================================
-- VIEWS AGROPECUÁRIAS — AgroIA-RMC
-- Rodar no Supabase SQL Editor para criar as views permanentes.
-- Ficam visíveis no Table Editor junto com vw_balanco_oferta_demanda etc.
-- =============================================================

-- ──────────────────────────────────────────────────────────────
-- VIEW 1: Itens agrícolas com contexto completo
--         Substitui a query Q2 — use: SELECT * FROM vw_itens_agro
-- ──────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW vw_itens_agro AS
SELECT
    l.id            AS licitacao_id,
    l.processo,
    l.canal,
    l.dt_abertura,
    l.situacao,
    il.id           AS item_id,
    il.seq,
    il.descricao,
    il.cultura,
    il.categoria_v2,
    il.qt_solicitada,
    il.unidade_medida,
    il.valor_unitario,
    il.valor_total
FROM itens_licitacao il
JOIN licitacoes l ON l.id = il.licitacao_id
WHERE il.relevante_agro = true
ORDER BY l.dt_abertura, l.processo, il.seq;

-- ──────────────────────────────────────────────────────────────
-- VIEW 1b: Itens agrícolas PUROS (sem processados)
--          Filtra apenas categorias naturais
--          use: SELECT * FROM vw_itens_agro_puros
-- ──────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW vw_itens_agro_puros AS
SELECT
    l.id            AS licitacao_id,
    l.processo,
    l.canal,
    l.dt_abertura,
    l.situacao,
    il.id           AS item_id,
    il.seq,
    il.descricao,
    il.cultura,
    il.categoria_v2,
    il.qt_solicitada,
    il.unidade_medida,
    il.valor_unitario,
    il.valor_total
FROM itens_licitacao il
JOIN licitacoes l ON l.id = il.licitacao_id
WHERE il.relevante_agro = true
  AND il.categoria_v2 IN ('FRUTAS', 'HORTIFRUTI', 'PROTEINA_ANIMAL', 'GRAOS_CEREAIS', 'LATICINIOS')
ORDER BY l.dt_abertura, l.processo, il.seq;

-- ──────────────────────────────────────────────────────────────
-- VIEW 2: Demanda por cultura × canal × ano
--         Substitui a query Q3 — use: SELECT * FROM vw_demanda_agro_ano
-- ──────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW vw_demanda_agro_ano AS
SELECT
    EXTRACT(YEAR FROM l.dt_abertura)::int           AS ano,
    l.canal,
    il.categoria_v2,
    il.cultura,
    il.unidade_medida,
    COUNT(DISTINCT l.id)                            AS qtd_licitacoes,
    COUNT(*)                                        AS qtd_itens,
    ROUND(SUM(il.qt_solicitada)::numeric, 2)        AS volume_total,
    ROUND(SUM(il.valor_total)::numeric, 2)          AS valor_total_R$
FROM itens_licitacao il
JOIN licitacoes l ON l.id = il.licitacao_id
WHERE il.relevante_agro = true
GROUP BY
    ano,
    l.canal,
    il.categoria_v2,
    il.cultura,
    il.unidade_medida
ORDER BY ano, l.canal, valor_total_R$ DESC;

-- ──────────────────────────────────────────────────────────────
-- VIEW 3: Cobertura de classificação (diagnóstico rápido)
--         use: SELECT * FROM vw_cobertura_classificacao
-- ──────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW vw_cobertura_classificacao AS
SELECT
    COUNT(*)                                                           AS total_itens,
    SUM(CASE WHEN relevante_agro             THEN 1 ELSE 0 END)       AS itens_agro,
    SUM(CASE WHEN categoria_v2 = 'HORTIFRUTI'       THEN 1 ELSE 0 END) AS hortifruti,
    SUM(CASE WHEN categoria_v2 = 'FRUTAS'           THEN 1 ELSE 0 END) AS frutas,
    SUM(CASE WHEN categoria_v2 = 'PROTEINA_ANIMAL'  THEN 1 ELSE 0 END) AS proteina_animal,
    SUM(CASE WHEN categoria_v2 = 'GRAOS_CEREAIS'    THEN 1 ELSE 0 END) AS graos_cereais,
    SUM(CASE WHEN categoria_v2 = 'LATICINIOS'       THEN 1 ELSE 0 END) AS laticinios,
    SUM(CASE WHEN categoria_v2 = 'PROCESSADOS_AF'   THEN 1 ELSE 0 END) AS processados_af,
    SUM(CASE WHEN categoria_v2 = 'INSUMOS_NAO_AGRO' THEN 1 ELSE 0 END) AS insumos_nao_agro,
    SUM(CASE WHEN categoria_v2 = 'NAO_CLASSIFICADO' THEN 1 ELSE 0 END) AS nao_classificado,
    ROUND(
        100.0 * SUM(CASE WHEN relevante_agro THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0),
        1
    )                                                                   AS pct_agro
FROM itens_licitacao;

-- ──────────────────────────────────────────────────────────────
-- VIEW 4: Documentos de licitações agrícolas
--         Retorna documentos apenas para licitações que têm itens
--         relevantes à agricultura (relevante_agro = true)
--         use: SELECT * FROM vw_licitacoes_agro_documentos
-- ──────────────────────────────────────────────────────────────
DROP VIEW IF EXISTS vw_licitacoes_agro_documentos CASCADE;

CREATE VIEW vw_licitacoes_agro_documentos AS
SELECT DISTINCT
    d.id,
    d.licitacao_id,
    d.nome_arquivo,
    d.nome_doc,
    d.url_publica,
    d.tamanho_bytes,
    d.coletado_em,
    d.storage_path,
    l.processo,
    l.tipo_processo,
    l.objeto,
    l.dt_abertura,
    l.situacao,
    l.canal
FROM documentos_licitacao d
JOIN licitacoes l ON l.id = d.licitacao_id
WHERE EXISTS (
    SELECT 1 FROM itens_licitacao il
    WHERE il.licitacao_id = l.id
    AND il.relevante_agro = true
)
ORDER BY d.coletado_em DESC;
