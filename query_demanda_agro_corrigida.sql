-- ============================================================================
-- QUERY: Demanda Agrícola por Ano/Canal/Categoria/Cultura
-- ESCOPO: APENAS AGRICULTURA (relevante_af=true)
-- FILTRO: Remove PROCESSADOS_AF (não é produção agrícola primária)
-- ============================================================================

SELECT
    EXTRACT(YEAR FROM l.dt_abertura)::INT as ano,
    l.canal,
    i.categoria_v2,
    i.descricao as cultura,
    i.unidade_medida,
    COUNT(DISTINCT l.id) as qtd_licitacoes,
    COUNT(DISTINCT i.id) as qtd_itens,
    COALESCE(SUM(p.quantidade), 0) as volume_total,
    COALESCE(SUM(p.quantidade * p.valor_unitario), 0)::NUMERIC(15,2) as valor_total_r$
FROM licitacoes l
INNER JOIN itens_licitacao i ON l.id = i.licitacao_id
LEFT JOIN participacoes p ON i.id = p.item_id
WHERE
    l.relevante_af = true                    -- ✅ APENAS AGRICULTURA
    AND i.categoria_v2 != 'PROCESSADOS_AF'   -- ❌ REMOVE PROCESSADOS
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

-- ============================================================================
-- VERIFICAÇÃO: Contar categorias na base agrícola
-- ============================================================================

-- Distribuição de categorias AGRÍCOLAS (sem processados)
SELECT
    categoria_v2,
    COUNT(*) as qtd_itens,
    COUNT(DISTINCT licitacao_id) as qtd_licitacoes
FROM itens_licitacao i
INNER JOIN licitacoes l ON i.licitacao_id = l.id
WHERE l.relevante_af = true
GROUP BY categoria_v2
ORDER BY qtd_itens DESC;

-- ============================================================================
-- RESUMO: Demanda Agrícola Total (sem processados)
-- ============================================================================

SELECT
    'TOTAL AGRÍCOLA' as categoria,
    COUNT(DISTINCT l.id) as qtd_licitacoes,
    COUNT(DISTINCT i.id) as qtd_itens,
    COALESCE(SUM(p.quantidade), 0)::NUMERIC(15,0) as volume_total,
    COALESCE(SUM(p.quantidade * p.valor_unitario), 0)::NUMERIC(15,2) as valor_total_r$
FROM licitacoes l
INNER JOIN itens_licitacao i ON l.id = i.licitacao_id
LEFT JOIN participacoes p ON i.id = p.item_id
WHERE
    l.relevante_af = true
    AND i.categoria_v2 != 'PROCESSADOS_AF'
    AND i.categoria_v2 IS NOT NULL;

-- ============================================================================
-- IMPACTO: Comparar com/sem processados
-- ============================================================================

WITH agro_sem_processados AS (
    SELECT
        COUNT(DISTINCT l.id) as licitacoes,
        COUNT(DISTINCT i.id) as itens,
        COALESCE(SUM(p.quantidade * p.valor_unitario), 0) as valor
    FROM licitacoes l
    INNER JOIN itens_licitacao i ON l.id = i.licitacao_id
    LEFT JOIN participacoes p ON i.id = p.item_id
    WHERE l.relevante_af = true
        AND i.categoria_v2 != 'PROCESSADOS_AF'
        AND i.categoria_v2 IS NOT NULL
),
agro_com_processados AS (
    SELECT
        COUNT(DISTINCT l.id) as licitacoes,
        COUNT(DISTINCT i.id) as itens,
        COALESCE(SUM(p.quantidade * p.valor_unitario), 0) as valor
    FROM licitacoes l
    INNER JOIN itens_licitacao i ON l.id = i.licitacao_id
    LEFT JOIN participacoes p ON i.id = p.item_id
    WHERE l.relevante_af = true
)
SELECT
    'SEM PROCESSADOS' as filtro,
    a.licitacoes, a.itens, a.valor::NUMERIC(15,2) as valor_r$
FROM agro_sem_processados a
UNION ALL
SELECT
    'COM PROCESSADOS' as filtro,
    b.licitacoes, b.itens, b.valor::NUMERIC(15,2) as valor_r$
FROM agro_com_processados b;
