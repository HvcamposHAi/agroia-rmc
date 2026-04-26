-- ============================================================================
-- QUERY: Demanda Agrícola por Ano/Canal/Categoria/Cultura
-- ESCOPO: APENAS AGRICULTURA (relevante_af=true)
-- NOTA: participacoes nao tem relacao direta com itens
--       Usa valores dos itens (valor_total), nao participacoes
-- ============================================================================

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
