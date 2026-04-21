-- =========================================================================
-- AUDITORIA DE DOCUMENTOS AGRÍCOLAS - QUERIES CORRIGIDAS
-- =========================================================================
-- VERSÃO CORRIGIDA: Sem referência a empenhos.licitacao_id (coluna não existe)
-- Foco: Consistência entre PDFs extraídos e licitações agrícolas

-- =========================================================================
-- QUERY 1: SUMÁRIO GERAL DE COBERTURA
-- =========================================================================
-- Mostra: total de licitações agrícolas, documentos, empenhos e taxas
SELECT
    'Licitacoes Agricolas' as metrica,
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
    'Licitations com Documentos',
    COUNT(DISTINCT licitacao_id)
FROM documentos_licitacao

UNION ALL

SELECT
    'Empenhos Registrados',
    COUNT(DISTINCT id)
FROM empenhos;

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
    ROUND(SUM(il.valor_total), 2) as valor_total_R$
FROM licitacoes l
JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
LEFT JOIN documentos_licitacao d ON l.id = d.licitacao_id
GROUP BY l.id, l.processo, l.dt_abertura, l.situacao, l.objeto
HAVING COUNT(DISTINCT d.id) = 0
ORDER BY l.dt_abertura DESC
LIMIT 50;

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
    ) as taxa_cobertura_pct
FROM licitacoes l
JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
LEFT JOIN documentos_licitacao d ON l.id = d.licitacao_id
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
-- QUERY 5: LICITAÇÕES FINALIZADO SEM DOCUMENTAÇÃO
-- =========================================================================
-- Prioridade: licitações que foram concluídas mas não têm docs
SELECT
    'INCONSISTENCIA_PORTAL' as tipo_alerta,
    l.id,
    l.processo,
    l.dt_abertura,
    COUNT(DISTINCT il.id) as qtd_itens,
    COUNT(DISTINCT d.id) as qtd_docs_coletados
FROM licitacoes l
JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
LEFT JOIN documentos_licitacao d ON l.id = d.licitacao_id
WHERE l.situacao IN ('Concluido', 'Concluído', 'Em Andamento')
GROUP BY l.id, l.processo, l.dt_abertura
HAVING COUNT(DISTINCT d.id) = 0
ORDER BY l.dt_abertura DESC
LIMIT 50;

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
    ) as taxa_cobertura_pct
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
-- QUERY 8: VERIFICAR ESTRUTURA DE EMPENHOS
-- =========================================================================
-- Entender como empenhos se relaciona com licitações
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'empenhos'
ORDER BY ordinal_position;

-- =========================================================================
-- QUERY 9: AMOSTRA DE DADOS DE EMPENHOS
-- =========================================================================
SELECT * FROM empenhos LIMIT 5;

-- =========================================================================
-- QUERY 10: SUMÁRIO FINAL - COBERTURA GERAL
-- =========================================================================
SELECT
    'LICITACOES_AGRICOLAS' as categoria,
    COUNT(DISTINCT l.id) as total
FROM licitacoes l
JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true

UNION ALL

SELECT
    'COM_DOCUMENTOS',
    COUNT(DISTINCT l.id)
FROM licitacoes l
JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
WHERE EXISTS (SELECT 1 FROM documentos_licitacao d WHERE d.licitacao_id = l.id)

UNION ALL

SELECT
    'SEM_DOCUMENTOS',
    COUNT(DISTINCT l.id)
FROM licitacoes l
JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
WHERE NOT EXISTS (SELECT 1 FROM documentos_licitacao d WHERE d.licitacao_id = l.id);
