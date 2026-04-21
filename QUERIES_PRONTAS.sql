-- =======================================================================
-- QUERIES PRONTAS PARA COPIAR/COLAR NO SUPABASE SQL EDITOR
-- =======================================================================
-- Estrutura de empenhos descoberta:
-- empenhos.item_id → itens_licitacao.id → licitacoes.id
-- =======================================================================

-- ======== QUERY 1: SUMÁRIO GERAL (Execute isto primeiro!) ========
SELECT
    'Licitacoes Agricolas' as metrica,
    COUNT(DISTINCT il.licitacao_id) as valor
FROM itens_licitacao il
WHERE il.relevante_agro = true

UNION ALL

SELECT 'Documentos Coletados', COUNT(DISTINCT id)
FROM documentos_licitacao

UNION ALL

SELECT 'Licitations com Documentos', COUNT(DISTINCT licitacao_id)
FROM documentos_licitacao

UNION ALL

SELECT 'Empenhos Registrados', COUNT(DISTINCT id)
FROM empenhos

UNION ALL

SELECT
    'Licitacoes Agricolas com Empenhos',
    COUNT(DISTINCT il.licitacao_id)
FROM empenhos e
JOIN itens_licitacao il ON e.item_id = il.id
WHERE il.relevante_agro = true;

-- ======== QUERY 2: CRÍTICO - Empenhos SEM Documentos ========
SELECT
    l.id,
    l.processo,
    l.dt_abertura,
    l.situacao,
    COUNT(DISTINCT il.id) as qtd_itens_agro,
    COUNT(DISTINCT e.id) as qtd_empenhos,
    SUM(e.valor_empenhado)::NUMERIC as valor_empenhado_R$,
    COUNT(DISTINCT d.id) as qtd_docs,
    'CRITICO: Compra SEM documentacao' as severidade
FROM licitacoes l
JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
JOIN empenhos e ON e.item_id = il.id
LEFT JOIN documentos_licitacao d ON l.id = d.licitacao_id
GROUP BY l.id, l.processo, l.dt_abertura, l.situacao
HAVING COUNT(DISTINCT d.id) = 0
ORDER BY valor_empenhado_R$ DESC
LIMIT 50;

-- ======== QUERY 3: Cobertura por Situação (com Empenhos) ========
SELECT
    l.situacao,
    COUNT(DISTINCT l.id) as qtd_licitacoes_agro,
    COUNT(DISTINCT d.licitacao_id) as qtd_com_docs,
    COUNT(DISTINCT CASE WHEN e.id IS NOT NULL THEN l.id END) as qtd_com_empenhos,
    ROUND(100.0 * COUNT(DISTINCT d.licitacao_id) / NULLIF(COUNT(DISTINCT l.id), 0), 1) as taxa_docs_pct,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN e.id IS NOT NULL THEN l.id END) / NULLIF(COUNT(DISTINCT l.id), 0), 1) as taxa_empenhos_pct
FROM licitacoes l
JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
LEFT JOIN documentos_licitacao d ON l.id = d.licitacao_id
LEFT JOIN empenhos e ON e.item_id = il.id
GROUP BY l.situacao
ORDER BY taxa_docs_pct ASC;

-- ======== QUERY 4: Licitações SEM Documentos ========
SELECT
    l.id,
    l.processo,
    l.dt_abertura,
    l.situacao,
    COUNT(DISTINCT il.id) as qtd_itens_agro,
    COUNT(DISTINCT e.id) as qtd_empenhos,
    COALESCE(SUM(e.valor_empenhado)::NUMERIC, 0) as valor_empenhos_R$,
    COUNT(DISTINCT d.id) as qtd_docs
FROM licitacoes l
JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
LEFT JOIN empenhos e ON e.item_id = il.id
LEFT JOIN documentos_licitacao d ON l.id = d.licitacao_id
GROUP BY l.id, l.processo, l.dt_abertura, l.situacao
HAVING COUNT(DISTINCT d.id) = 0
ORDER BY l.dt_abertura DESC
LIMIT 50;

-- ======== QUERY 5: Distribuição Temporal ========
SELECT
    EXTRACT(YEAR FROM l.dt_abertura)::int as ano,
    EXTRACT(MONTH FROM l.dt_abertura)::int as mes,
    COUNT(DISTINCT l.id) as qtd_licitacoes_agro,
    COUNT(DISTINCT d.licitacao_id) as qtd_com_docs,
    COUNT(DISTINCT CASE WHEN e.id IS NOT NULL THEN l.id END) as qtd_com_empenhos,
    ROUND(100.0 * COUNT(DISTINCT d.licitacao_id) / NULLIF(COUNT(DISTINCT l.id), 0), 1) as taxa_docs_pct
FROM licitacoes l
JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
LEFT JOIN documentos_licitacao d ON l.id = d.licitacao_id
LEFT JOIN empenhos e ON e.item_id = il.id
GROUP BY ano, mes
ORDER BY ano DESC, mes DESC;

-- ======== QUERY 6: Análise por Categoria Agrícola ========
SELECT
    il.categoria_v2,
    COUNT(DISTINCT l.id) as qtd_licitacoes_agro,
    COUNT(DISTINCT d.licitacao_id) as qtd_com_docs,
    COUNT(DISTINCT CASE WHEN e.id IS NOT NULL THEN l.id END) as qtd_com_empenhos,
    ROUND(100.0 * COUNT(DISTINCT d.licitacao_id) / NULLIF(COUNT(DISTINCT l.id), 0), 1) as taxa_docs_pct,
    ROUND(SUM(il.valor_total), 2) as valor_licitacao_R$,
    COALESCE(ROUND(SUM(e.valor_empenhado), 2), 0) as valor_empenho_R$
FROM licitacoes l
JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
LEFT JOIN documentos_licitacao d ON l.id = d.licitacao_id
LEFT JOIN empenhos e ON e.item_id = il.id
GROUP BY il.categoria_v2
ORDER BY taxa_docs_pct ASC;

-- ======== QUERY 7: Empenhos por Item (Detalhe) ========
SELECT
    il.id as item_id,
    il.seq,
    il.descricao as item_descricao,
    il.categoria_v2,
    l.processo,
    COUNT(DISTINCT e.id) as qtd_empenhos,
    SUM(e.valor_empenhado)::NUMERIC as valor_empenhado_R$,
    ROUND(il.valor_total, 2) as valor_licitado_R$,
    COUNT(DISTINCT d.id) as qtd_docs
FROM itens_licitacao il
JOIN licitacoes l ON l.id = il.licitacao_id
LEFT JOIN empenhos e ON e.item_id = il.id
LEFT JOIN documentos_licitacao d ON l.id = d.licitacao_id
WHERE il.relevante_agro = true
GROUP BY il.id, il.seq, il.descricao, il.categoria_v2, l.processo
ORDER BY valor_empenhado_R$ DESC
LIMIT 50;

-- ======== QUERY 8: Fornecedores com Empenhos (TOP 20) ========
SELECT
    f.id as fornecedor_id,
    f.nome as fornecedor_nome,
    COUNT(DISTINCT e.id) as qtd_empenhos,
    SUM(e.valor_empenhado)::NUMERIC as valor_total_R$,
    COUNT(DISTINCT l.id) as qtd_licitacoes
FROM fornecedores f
JOIN empenhos e ON f.id = e.fornecedor_id
JOIN itens_licitacao il ON e.item_id = il.id
JOIN licitacoes l ON l.id = il.licitacao_id
WHERE il.relevante_agro = true
GROUP BY f.id, f.nome
ORDER BY valor_total_R$ DESC
LIMIT 20;

-- ======== QUERY 9: Status de Coleta ========
SELECT
    'Licitacoes Agricolas' as categoria,
    COUNT(DISTINCT il.licitacao_id) as total,
    'baseline' as status
FROM itens_licitacao il
WHERE il.relevante_agro = true

UNION ALL

SELECT 'Com Documentos', COUNT(DISTINCT l.id), 'documentado'
FROM licitacoes l
JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
WHERE EXISTS (SELECT 1 FROM documentos_licitacao d WHERE d.licitacao_id = l.id)

UNION ALL

SELECT 'Com Empenhos', COUNT(DISTINCT l.id), 'executada'
FROM licitacoes l
JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
WHERE EXISTS (SELECT 1 FROM empenhos e WHERE e.item_id = il.id)

UNION ALL

SELECT 'Com Docs E Empenhos', COUNT(DISTINCT l.id), 'completa'
FROM licitacoes l
JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
WHERE EXISTS (SELECT 1 FROM documentos_licitacao d WHERE d.licitacao_id = l.id)
AND EXISTS (SELECT 1 FROM empenhos e WHERE e.item_id = il.id);

-- ======== QUERY 10: Resumo em Números ========
WITH lics_agro AS (
    SELECT DISTINCT l.id
    FROM licitacoes l
    JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
),
lics_com_docs AS (
    SELECT DISTINCT l.id
    FROM licitacoes l
    JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
    WHERE EXISTS (SELECT 1 FROM documentos_licitacao d WHERE d.licitacao_id = l.id)
),
lics_com_empenhos AS (
    SELECT DISTINCT l.id
    FROM licitacoes l
    JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
    WHERE EXISTS (SELECT 1 FROM empenhos e WHERE e.item_id = il.id)
)
SELECT
    'Total Licitacoes Agricolas' as metrica,
    (SELECT COUNT(*) FROM lics_agro)::TEXT as valor

UNION ALL SELECT 'Com Documentos', CONCAT((SELECT COUNT(*) FROM lics_com_docs), ' (', ROUND(100.0 * (SELECT COUNT(*) FROM lics_com_docs) / NULLIF((SELECT COUNT(*) FROM lics_agro), 0), 1)::TEXT, '%)')

UNION ALL SELECT 'Com Empenhos', CONCAT((SELECT COUNT(*) FROM lics_com_empenhos), ' (', ROUND(100.0 * (SELECT COUNT(*) FROM lics_com_empenhos) / NULLIF((SELECT COUNT(*) FROM lics_agro), 0), 1)::TEXT, '%)')

UNION ALL SELECT 'Com Docs E Empenhos', (
    SELECT COUNT(*)::TEXT FROM lictiones_agro WHERE id IN (SELECT id FROM lics_com_docs) AND id IN (SELECT id FROM lics_com_empenhos)
);
