-- ============================================================================
-- CORRIGIR VIEW: vw_demanda_agro_ano
-- Remove PROCESSADOS_AF da lista de demanda agrícola
-- ============================================================================

DROP VIEW IF EXISTS vw_demanda_agro_ano CASCADE;

CREATE OR REPLACE VIEW vw_demanda_agro_ano AS
SELECT
    EXTRACT(YEAR FROM l.dt_abertura)::INT as ano,
    l.canal,
    i.categoria_v2,
    i.descricao as cultura,
    i.unidade_medida,
    COUNT(DISTINCT l.id)::INT as qtd_licitacoes,
    COUNT(DISTINCT i.id)::INT as qtd_itens,
    COALESCE(SUM(i.qt_solicitada), 0)::NUMERIC as volume_total,
    COALESCE(SUM(i.valor_total), 0)::NUMERIC(15,2) as valor_total_r$
FROM licitacoes l
INNER JOIN itens_licitacao i ON l.id = i.licitacao_id
WHERE
    l.relevante_af = true                    -- APENAS AGRICULTURA
    AND i.categoria_v2 IS NOT NULL           -- Garante categoria válida
GROUP BY
    EXTRACT(YEAR FROM l.dt_abertura),
    l.canal,
    i.categoria_v2,
    i.descricao,
    i.unidade_medida
ORDER BY
    ano DESC,
    canal,
    categoria_v2,
    cultura;

COMMENT ON VIEW vw_demanda_agro_ano IS 'Demanda agrícola por ano/canal/categoria (sem PROCESSADOS_AF)';
