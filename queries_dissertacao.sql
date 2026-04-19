-- =============================================================
-- QUERIES ANALÍTICAS — AgroIA-RMC / Dissertação
-- PRÉ-REQUISITO: migracao_classificacao.sql + enriquecer_classificacao.py
-- =============================================================

-- ──────────────────────────────────────────────────────────────
-- Q1. Licitações relevantes para agropecuária (nível licitação)
--     Critério: pertence a um dos 5 canais institucionais OU
--               foi marcada como relevante_af pelo objeto.
-- ──────────────────────────────────────────────────────────────
SELECT
    id,
    processo,
    tipo_processo,
    objeto,
    canal,
    dt_abertura,
    situacao,
    total_forn_retiraram_edital,
    total_forn_participantes
FROM licitacoes
WHERE canal <> 'OUTRO'
   OR relevante_af = true
ORDER BY dt_abertura;

-- ──────────────────────────────────────────────────────────────
-- Q2. Itens agrícolas com contexto completo
--     Usa a flag relevante_agro definida pelo enriquecer_classificacao.py
-- ──────────────────────────────────────────────────────────────
SELECT
    l.processo,
    l.canal,
    l.dt_abertura,
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
-- Q3. Volume e valor por cultura × canal × ano
--     Base para análise de demanda histórica da dissertação
-- ──────────────────────────────────────────────────────────────
SELECT
    EXTRACT(YEAR FROM l.dt_abertura)::int          AS ano,
    l.canal,
    il.categoria_v2,
    il.cultura,
    COUNT(DISTINCT l.id)                           AS qtd_licitacoes,
    COUNT(*)                                       AS qtd_itens,
    il.unidade_medida,
    ROUND(SUM(il.qt_solicitada)::numeric, 2)       AS volume_total,
    ROUND(SUM(il.valor_total)::numeric, 2)         AS valor_total_R$
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
-- Q4. Sazonalidade mensal por cultura (demanda ao longo do ano)
--     Mostra em quais meses cada cultura é mais demandada
-- ──────────────────────────────────────────────────────────────
SELECT
    EXTRACT(YEAR  FROM l.dt_abertura)::int         AS ano,
    EXTRACT(MONTH FROM l.dt_abertura)::int         AS mes,
    il.cultura,
    l.canal,
    ROUND(SUM(il.qt_solicitada)::numeric, 2)       AS volume_mensal,
    ROUND(SUM(il.valor_total)::numeric, 2)         AS valor_mensal_R$
FROM itens_licitacao il
JOIN licitacoes l ON l.id = il.licitacao_id
WHERE il.relevante_agro = true
GROUP BY ano, mes, il.cultura, l.canal
ORDER BY ano, mes, il.cultura;

-- ──────────────────────────────────────────────────────────────
-- Q5. Fornecedores agrícolas (cooperativas e associações)
--     Quem participa dos processos dos 5 canais
-- ──────────────────────────────────────────────────────────────
SELECT
    f.cpf_cnpj,
    f.razao_social,
    f.tipo,
    COUNT(DISTINCT p.licitacao_id)                 AS qtd_licitacoes,
    array_agg(DISTINCT l.canal ORDER BY l.canal)   AS canais
FROM fornecedores f
JOIN participacoes p ON p.fornecedor_id = f.id
JOIN licitacoes l    ON l.id = p.licitacao_id
WHERE (l.canal <> 'OUTRO' OR l.relevante_af = true)
  AND f.tipo IN ('COOPERATIVA', 'ASSOCIACAO')
GROUP BY f.cpf_cnpj, f.razao_social, f.tipo
ORDER BY qtd_licitacoes DESC;

-- ──────────────────────────────────────────────────────────────
-- Q6. Cobertura de classificação — diagnóstico de qualidade
--     Deve ser rodada após o enriquecer_classificacao.py
-- ──────────────────────────────────────────────────────────────
SELECT
    COUNT(*)                                                          AS total_itens,
    SUM(CASE WHEN relevante_agro             THEN 1 ELSE 0 END)      AS itens_agro,
    SUM(CASE WHEN categoria_v2 = 'HORTIFRUTI'      THEN 1 ELSE 0 END) AS hortifruti,
    SUM(CASE WHEN categoria_v2 = 'FRUTAS'          THEN 1 ELSE 0 END) AS frutas,
    SUM(CASE WHEN categoria_v2 = 'GRAOS_CEREAIS'   THEN 1 ELSE 0 END) AS graos,
    SUM(CASE WHEN categoria_v2 = 'LATICINIOS'      THEN 1 ELSE 0 END) AS laticinios,
    SUM(CASE WHEN categoria_v2 = 'PROTEINA_ANIMAL' THEN 1 ELSE 0 END) AS proteina,
    SUM(CASE WHEN categoria_v2 = 'PROCESSADOS_AF'  THEN 1 ELSE 0 END) AS processados,
    SUM(CASE WHEN categoria_v2 = 'INSUMOS_NAO_AGRO'THEN 1 ELSE 0 END) AS insumos_excluidos,
    SUM(CASE WHEN categoria_v2 = 'NAO_CLASSIFICADO'THEN 1 ELSE 0 END) AS sem_classificacao,
    ROUND(
        100.0 * SUM(CASE WHEN relevante_agro THEN 1 ELSE 0 END) / COUNT(*),
        1
    )                                                                  AS pct_agro
FROM itens_licitacao;

-- ──────────────────────────────────────────────────────────────
-- Q7. Documentos das licitações agrícolas
--     Para alimentar a base vetorial RAG do AgroIA-RMC
-- ──────────────────────────────────────────────────────────────
SELECT
    l.processo,
    l.canal,
    l.dt_abertura,
    d.nome_doc,
    d.nome_arquivo,
    d.url_publica,
    d.tamanho_bytes
FROM documentos_licitacao d
JOIN licitacoes l ON l.id = d.licitacao_id
WHERE (l.canal <> 'OUTRO' OR l.relevante_af = true)
  AND d.url_publica IS NOT NULL
ORDER BY l.dt_abertura DESC, l.processo, d.nome_doc;

-- ──────────────────────────────────────────────────────────────
-- Q8. Valor total contratado por canal × ano (visão macro)
--     Evidencia a assimetria de informação da dissertação
-- ──────────────────────────────────────────────────────────────
SELECT
    EXTRACT(YEAR FROM l.dt_abertura)::int          AS ano,
    l.canal,
    COUNT(DISTINCT l.id)                           AS qtd_licitacoes,
    SUM(il.valor_total)                            AS valor_total_R$,
    COUNT(DISTINCT f.id)                           AS qtd_fornecedores_distintos
FROM licitacoes l
LEFT JOIN itens_licitacao il ON il.licitacao_id = l.id AND il.relevante_agro = true
LEFT JOIN participacoes p    ON p.licitacao_id = l.id
LEFT JOIN fornecedores f     ON f.id = p.fornecedor_id
WHERE l.canal <> 'OUTRO'
GROUP BY ano, l.canal
ORDER BY ano, l.canal;

-- ──────────────────────────────────────────────────────────────
-- Q9. Top-20 culturas por valor total acumulado (2019–2026)
-- ──────────────────────────────────────────────────────────────
SELECT
    il.cultura,
    il.categoria_v2,
    COUNT(*)                                       AS qtd_itens,
    ROUND(SUM(il.valor_total)::numeric, 2)         AS valor_total_R$,
    ROUND(AVG(il.valor_unitario)::numeric, 4)      AS preco_medio_unit
FROM itens_licitacao il
WHERE il.relevante_agro = true
GROUP BY il.cultura, il.categoria_v2
ORDER BY valor_total_R$ DESC
LIMIT 20;

-- ──────────────────────────────────────────────────────────────
-- Q10. Licitações com itens NÃO classificados (auditoria)
--      Útil para identificar descrições novas que precisam ser
--      adicionadas ao dicionário do enriquecer_classificacao.py
-- ──────────────────────────────────────────────────────────────
SELECT
    l.processo,
    l.canal,
    il.descricao,
    COUNT(*) AS ocorrencias,
    ROUND(SUM(il.valor_total)::numeric, 2) AS valor_total_R$
FROM itens_licitacao il
JOIN licitacoes l ON l.id = il.licitacao_id
WHERE il.categoria_v2 = 'NAO_CLASSIFICADO'
  AND (l.canal <> 'OUTRO' OR l.relevante_af = true)
GROUP BY l.processo, l.canal, il.descricao
ORDER BY ocorrencias DESC
LIMIT 100;
