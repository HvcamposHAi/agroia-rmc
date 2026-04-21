-- =========================================================================
-- AUDITORIA DE DOCUMENTOS AGRÍCOLAS - AgroIA-RMC
-- =========================================================================
-- Execute estas queries no Supabase SQL Editor para análise detalhada
-- Foco: Consistência entre PDFs extraídos e licitações agrícolas

-- =========================================================================
-- QUERY 1: SUMÁRIO GERAL DE COBERTURA
-- =========================================================================
-- Mostra: total de licitações agrícolas, documentos, empenhos e taxas
SELECT
    'Licitações Agrícolas' as metrica,
    COUNT(DISTINCT il.licitacao_id) as valor
FROM itens_licitacao il
WHERE il.relevante_agro = true

UNION ALL

SELECT
    'Documentos Coletados',
    COUNT(DISTINCT id)
FROM documentos_licitacao

UNION ALL

SELECT
    'Licitações com Documentos',
    COUNT(DISTINCT licitacao_id)
FROM documentos_licitacao

UNION ALL

SELECT
    'Empenhos Registrados',
    COUNT(DISTINCT id)
FROM empenhos

UNION ALL

SELECT
    'Licitações Agrícolas com Empenhos',
    COUNT(DISTINCT e.licitacao_id)
FROM empenhos e
WHERE e.licitacao_id IN (
    SELECT DISTINCT il.licitacao_id
    FROM itens_licitacao il
    WHERE il.relevante_agro = true
);

-- =========================================================================
-- QUERY 2: LICITAÇÕES AGRÍCOLAS SEM DOCUMENTOS (ERRO_BD)
-- =========================================================================
-- Identifica licitações que deveriam ter documentos mas não têm
SELECT
    'ERRO_BD' as tipo_alerta,
    l.id,
    l.processo,
    l.dt_abertura,
    l.situacao,
    l.objeto,
    COUNT(DISTINCT il.id) as qtd_itens_agro,
    COUNT(DISTINCT d.id) as qtd_docs,
    COUNT(DISTINCT e.id) as qtd_empenhos,
    CASE
        WHEN COUNT(DISTINCT d.id) = 0 AND COUNT(DISTINCT e.id) > 0 THEN
            'CRÍTICO: Tem empenhos mas sem documentos'
        WHEN COUNT(DISTINCT d.id) = 0 AND l.situacao = 'Concluído' THEN
            'GRAVE: Finalizada sem documentação'
        ELSE
            'Sem documentação'
    END as severidade
FROM licitacoes l
JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
LEFT JOIN documentos_licitacao d ON l.id = d.licitacao_id
LEFT JOIN empenhos e ON l.id = e.licitacao_id
GROUP BY l.id, l.processo, l.dt_abertura, l.situacao, l.objeto
HAVING COUNT(DISTINCT d.id) = 0
ORDER BY l.dt_abertura DESC;

-- =========================================================================
-- QUERY 3: TAXA DE COBERTURA POR SITUAÇÃO
-- =========================================================================
-- Analisa cobertura de documentos por status da licitação
SELECT
    l.situacao,
    COUNT(DISTINCT l.id) as qtd_licitacoes_agro,
    COUNT(DISTINCT d.licitacao_id) as qtd_com_docs,
    ROUND(
        100.0 * COUNT(DISTINCT d.licitacao_id) / NULLIF(COUNT(DISTINCT l.id), 0),
        1
    ) as taxa_cobertura_pct,
    COUNT(DISTINCT e.licitacao_id) as qtd_com_empenhos
FROM licitacoes l
JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
LEFT JOIN documentos_licitacao d ON l.id = d.licitacao_id
LEFT JOIN empenhos e ON l.id = e.licitacao_id
GROUP BY l.situacao
ORDER BY taxa_cobertura_pct ASC;

-- =========================================================================
-- QUERY 4: ANÁLISE POR CATEGORIA AGRÍCOLA
-- =========================================================================
-- Mostra cobertura de documentos por categoria de produto
SELECT
    il.categoria_v2,
    COUNT(DISTINCT l.id) as qtd_licitacoes_agro,
    COUNT(DISTINCT d.licitacao_id) as qtd_com_docs,
    ROUND(
        100.0 * COUNT(DISTINCT d.licitacao_id) / NULLIF(COUNT(DISTINCT l.id), 0),
        1
    ) as taxa_cobertura_pct,
    ROUND(SUM(il.valor_total), 2) as valor_total_R$,
    COUNT(DISTINCT CASE WHEN d.id IS NULL THEN l.id END) as sem_documentos
FROM licitacoes l
JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
LEFT JOIN documentos_licitacao d ON l.id = d.licitacao_id
GROUP BY il.categoria_v2
ORDER BY taxa_cobertura_pct ASC;

-- =========================================================================
-- QUERY 5: INCONSISTÊNCIA PORTAL - LICITAÇÕES COM MODAL MAS SEM DOWNLOAD
-- =========================================================================
-- Identifica licitações onde o portal indica documentos mas não foram baixados
SELECT
    'INCONSISTENCIA_PORTAL' as tipo_alerta,
    l.id,
    l.processo,
    l.dt_abertura,
    l.situacao,
    COUNT(DISTINCT il.id) as qtd_itens,
    COUNT(DISTINCT d.id) as qtd_docs_coletados,
    CASE
        WHEN l.situacao IN ('Concluído', 'Em Andamento') AND COUNT(DISTINCT d.id) = 0
        THEN 'DEVE_TER_DOCS_NO_PORTAL'
        ELSE 'VERIFICAR'
    END as requer_validacao_portal
FROM licitacoes l
JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
LEFT JOIN documentos_licitacao d ON l.id = d.licitacao_id
WHERE l.situacao IN ('Concluído', 'Em Andamento')
GROUP BY l.id, l.processo, l.dt_abertura, l.situacao
HAVING COUNT(DISTINCT d.id) = 0
ORDER BY l.dt_abertura DESC;

-- =========================================================================
-- QUERY 6: DISTRIBUIÇÃO TEMPORAL DE COBERTURA
-- =========================================================================
-- Analisa cobertura de documentos ao longo do tempo
SELECT
    EXTRACT(YEAR FROM l.dt_abertura)::int as ano,
    EXTRACT(MONTH FROM l.dt_abertura)::int as mes,
    COUNT(DISTINCT l.id) as qtd_licitacoes_agro,
    COUNT(DISTINCT d.licitacao_id) as qtd_com_docs,
    ROUND(
        100.0 * COUNT(DISTINCT d.licitacao_id) / NULLIF(COUNT(DISTINCT l.id), 0),
        1
    ) as taxa_cobertura_pct,
    MIN(d.coletado_em) as primeira_coleta,
    MAX(d.coletado_em) as ultima_coleta
FROM licitacoes l
JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
LEFT JOIN documentos_licitacao d ON l.id = d.licitacao_id
GROUP BY ano, mes
ORDER BY ano DESC, mes DESC;

-- =========================================================================
-- QUERY 7: DOCUMENTOS DUPLICADOS OU INCONSISTENTES
-- =========================================================================
-- Identifica possíveis problemas de qualidade nos dados de documentos
SELECT
    'ERRO_BD' as tipo_alerta,
    licitacao_id,
    nome_arquivo,
    COUNT(*) as qtd_registros,
    COUNT(DISTINCT storage_path) as qtd_paths_diferentes,
    COUNT(DISTINCT tamanho_bytes) as qtd_tamanhos_diferentes,
    CASE
        WHEN COUNT(*) > 1 THEN 'DUPLICADO'
        WHEN COUNT(DISTINCT storage_path) > 1 THEN 'PATHS_INCONSISTENTES'
        WHEN COUNT(DISTINCT tamanho_bytes) > 1 THEN 'TAMANHOS_INCONSISTENTES'
    END as tipo_problema
FROM documentos_licitacao
GROUP BY licitacao_id, nome_arquivo
HAVING COUNT(*) > 1 OR COUNT(DISTINCT storage_path) > 1 OR COUNT(DISTINCT tamanho_bytes) > 1
ORDER BY qtd_registros DESC;

-- =========================================================================
-- QUERY 8: EMPENHOS VS DOCUMENTOS - CORRELAÇÃO
-- =========================================================================
-- Identifica licitações com empenhos mas sem documentação
SELECT
    'ERRO_BD' as tipo_alerta,
    l.id,
    l.processo,
    l.dt_abertura,
    l.situacao,
    COUNT(DISTINCT e.id) as qtd_empenhos,
    SUM(CAST(e.valor AS numeric)) as valor_empenhos,
    COUNT(DISTINCT d.id) as qtd_docs,
    'CRÍTICO: Compra executada sem documentação' as severidade
FROM licitacoes l
JOIN empenhos e ON l.id = e.licitacao_id
JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
LEFT JOIN documentos_licitacao d ON l.id = d.licitacao_id
GROUP BY l.id, l.processo, l.dt_abertura, l.situacao
HAVING COUNT(DISTINCT d.id) = 0
ORDER BY valor_empenhos DESC;

-- =========================================================================
-- QUERY 9: SUMÁRIO EXECUTIVO DE ALERTAS
-- =========================================================================
-- Agregado de todos os problemas identificados
SELECT
    'ERRO_BD: Licitações sem docs' as categoria_alerta,
    COUNT(*) as qtd_problemas,
    SUM(CASE WHEN situacao = 'Concluído' THEN 1 ELSE 0 END) as com_status_concluido,
    ROUND(
        100.0 * SUM(CASE WHEN situacao = 'Concluído' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0),
        1
    ) as pct_concluidas
FROM (
    SELECT DISTINCT l.id, l.situacao
    FROM licitacoes l
    JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
    WHERE NOT EXISTS (
        SELECT 1 FROM documentos_licitacao d WHERE d.licitacao_id = l.id
    )
) sq

UNION ALL

SELECT
    'INCONSISTENCIA_PORTAL: Sem docs no portal',
    COUNT(*) as qtd_problemas,
    SUM(CASE WHEN situacao IN ('Concluído', 'Em Andamento') THEN 1 ELSE 0 END),
    ROUND(
        100.0 * SUM(CASE WHEN situacao IN ('Concluído', 'Em Andamento') THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0),
        1
    )
FROM (
    SELECT DISTINCT l.id, l.situacao
    FROM licitacoes l
    JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
    WHERE NOT EXISTS (
        SELECT 1 FROM documentos_licitacao d WHERE d.licitacao_id = l.id
    )
    AND l.situacao IN ('Concluído', 'Em Andamento')
) sq;

-- =========================================================================
-- QUERY 10: RELATÓRIO DETALHADO - TOP 50 LICITAÇÕES COM PROBLEMAS
-- =========================================================================
-- Lista completa das licitações que necessitam intervenção
SELECT
    l.id,
    l.processo,
    l.dt_abertura::date,
    l.situacao,
    l.objeto,
    COUNT(DISTINCT il.id) as qtd_itens_agro,
    SUM(il.valor_total) as valor_total_R$,
    COUNT(DISTINCT d.id) as qtd_docs,
    COUNT(DISTINCT e.id) as qtd_empenhos,
    CASE
        WHEN COUNT(DISTINCT d.id) = 0 AND COUNT(DISTINCT e.id) > 0 THEN
            'CRÍTICO: Empenho sem docs'
        WHEN COUNT(DISTINCT d.id) = 0 AND l.situacao = 'Concluído' THEN
            'GRAVE: Concluída sem docs'
        WHEN COUNT(DISTINCT d.id) = 0 AND l.situacao = 'Em Andamento' THEN
            'GRAVE: Em andamento sem docs'
        ELSE
            'Sem documentação'
    END as alerta
FROM licitacoes l
JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
LEFT JOIN documentos_licitacao d ON l.id = d.licitacao_id
LEFT JOIN empenhos e ON l.id = e.licitacao_id
GROUP BY l.id, l.processo, l.dt_abertura, l.situacao, l.objeto
HAVING COUNT(DISTINCT d.id) = 0
ORDER BY
    CASE
        WHEN COUNT(DISTINCT e.id) > 0 THEN 1
        WHEN l.situacao = 'Concluído' THEN 2
        ELSE 3
    END,
    COUNT(DISTINCT il.id) DESC
LIMIT 50;
