-- =============================================================
-- DIAGNÓSTICO: Distribuição e cobertura da classificação atual
-- Rodar no Supabase SQL Editor ANTES de qualquer migração
-- =============================================================

-- 1a. Licitações por canal (quantas são de cada programa)
SELECT
    canal,
    COUNT(*)                                              AS qtd_licitacoes,
    SUM(CASE WHEN relevante_af THEN 1 ELSE 0 END)        AS marcadas_af,
    SUM(CASE WHEN situacao = 'Concluído' THEN 1 ELSE 0 END) AS concluidas
FROM licitacoes
GROUP BY canal
ORDER BY qtd_licitacoes DESC;

-- 1b. Licitações por tipo_processo × canal
SELECT
    tipo_processo,
    canal,
    COUNT(*) AS qtd
FROM licitacoes
GROUP BY tipo_processo, canal
ORDER BY canal, qtd DESC;

-- 1c. Distribuição de itens por cultura atual (com valor total)
SELECT
    cultura,
    COUNT(*)                                     AS qtd_itens,
    COUNT(DISTINCT licitacao_id)                 AS qtd_licitacoes,
    ROUND(SUM(valor_total)::numeric, 2)          AS valor_total_R$,
    ROUND(AVG(valor_unitario)::numeric, 4)       AS valor_unit_medio
FROM itens_licitacao
GROUP BY cultura
ORDER BY qtd_itens DESC;

-- 1d. Itens com cultura = 'OUTRO' — amostra de descrições distintas
--     Use este resultado para expandir norm_cultura no enriquecer_classificacao.py
SELECT
    UPPER(TRIM(descricao))                       AS descricao_upper,
    COUNT(*)                                     AS ocorrencias,
    ROUND(SUM(valor_total)::numeric, 2)          AS valor_total_R$
FROM itens_licitacao
WHERE cultura = 'OUTRO'
GROUP BY UPPER(TRIM(descricao))
ORDER BY ocorrencias DESC
LIMIT 300;

-- 1e. Itens por canal da licitação (join) — mostra o que está sendo coletado em cada programa
SELECT
    l.canal,
    il.cultura,
    COUNT(*)                              AS qtd_itens,
    ROUND(SUM(il.valor_total)::numeric, 2) AS valor_total_R$
FROM itens_licitacao il
JOIN licitacoes l ON l.id = il.licitacao_id
GROUP BY l.canal, il.cultura
ORDER BY l.canal, qtd_itens DESC;

-- 1f. Licitações SEM itens coletados (pendentes de coleta na Etapa 2)
SELECT
    l.id,
    l.processo,
    l.tipo_processo,
    l.canal,
    l.situacao,
    l.dt_abertura
FROM licitacoes l
WHERE NOT EXISTS (
    SELECT 1 FROM itens_licitacao il WHERE il.licitacao_id = l.id
)
ORDER BY l.dt_abertura DESC;

-- 1g. Licitações Concluídas SEM empenhos (candidatas ao modo FORCAR_EMPENHOS)
SELECT
    l.id,
    l.processo,
    l.canal,
    l.dt_abertura,
    COUNT(il.id) AS qtd_itens
FROM licitacoes l
JOIN itens_licitacao il ON il.licitacao_id = l.id
WHERE l.situacao = 'Concluído'
  AND NOT EXISTS (
      SELECT 1 FROM empenhos e WHERE e.item_id = il.id
  )
GROUP BY l.id, l.processo, l.canal, l.dt_abertura
ORDER BY l.dt_abertura DESC;

-- 1h. Fornecedores por tipo (cooperativas vs empresas vs pessoas físicas)
SELECT
    tipo,
    COUNT(*) AS qtd_fornecedores,
    COUNT(DISTINCT p.licitacao_id) AS qtd_participacoes
FROM fornecedores f
JOIN participacoes p ON p.fornecedor_id = f.id
GROUP BY tipo
ORDER BY qtd_fornecedores DESC;
