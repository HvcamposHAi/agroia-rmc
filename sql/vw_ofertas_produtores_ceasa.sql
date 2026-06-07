-- =============================================================================
-- vw_ofertas_produtores — semear página /ofertas com referências de preço CEASA
-- =============================================================================
-- Estende a view com UNION ALL: (1) ofertas reais de produtores (definição
-- original, 14 colunas) + (2) referências CEASA-PR derivadas AO VIVO de
-- v_prohort_analise. NÃO grava nada nas tabelas base (auditoria/cadastro intactos).
--
-- Reconciliado com a definição real capturada via:
--   SELECT pg_get_viewdef('vw_ofertas_produtores'::regclass, true);
-- (colunas: id, cultura, descricao, quantidade, unidade, disponibilidade,
--  preco_pretendido, status, origem, criado_em, produtor_nome, produtor_tipo,
--  municipio, contato)
--
-- Executar no SQL Editor do Supabase (DDL — não roda via PostgREST/anon).
-- =============================================================================

CREATE OR REPLACE VIEW vw_ofertas_produtores AS
-- ============ BRANCH 1: ofertas reais de produtores (definição original) ============
SELECT
    o.id,
    o.cultura,
    o.descricao,
    o.quantidade,
    o.unidade,
    o.disponibilidade,
    o.preco_pretendido,
    o.status,
    o.origem,
    o.criado_em,
    p.nome      AS produtor_nome,
    p.tipo      AS produtor_tipo,
    p.municipio,
    p.contato
FROM ofertas_produtores o
JOIN produtores p ON p.id = o.produtor_id

UNION ALL

-- ============ BRANCH 2: referências CEASA-PR (ao vivo) ============
SELECT
    (-(row_number() OVER (ORDER BY a.ceasa, a.produto_norm)))::bigint  AS id,
    NULL::text                                                         AS cultura,
    initcap(a.produto_norm)                                            AS descricao,
    NULL::numeric                                                      AS quantidade,
    COALESCE(a.unidade, 'kg')                                          AS unidade,
    ('Referência CEASA-PR · cotação '
        || to_char(a.ultima_cotacao::date, 'DD/MM/YYYY'))             AS disponibilidade,
    round(a.media_30d::numeric, 2)                                     AS preco_pretendido,
    'ATIVA'                                                            AS status,
    'CEASA'                                                            AS origem,
    a.ultima_cotacao::timestamptz                                     AS criado_em,
    ('CEASA ' || CASE a.ceasa
        WHEN 'CURITIBA'      THEN 'Curitiba'
        WHEN 'MARINGA'       THEN 'Maringá'
        WHEN 'CASCAVEL'      THEN 'Cascavel'
        WHEN 'FOZ DO IGUACU' THEN 'Foz do Iguaçu'
        ELSE initcap(a.ceasa)
     END || ' (referência de preço)')                                 AS produtor_nome,
    'REFERENCIA_CEASA'                                                 AS produtor_tipo,
    CASE a.ceasa
        WHEN 'CURITIBA'      THEN 'Curitiba'
        WHEN 'MARINGA'       THEN 'Maringá'
        WHEN 'CASCAVEL'      THEN 'Cascavel'
        WHEN 'FOZ DO IGUACU' THEN 'Foz do Iguaçu'
        ELSE initcap(a.ceasa)
    END                                                                AS municipio,
    NULL::text                                                         AS contato
FROM v_prohort_analise a
WHERE a.ceasa IN ('CURITIBA', 'MARINGA', 'CASCAVEL', 'FOZ DO IGUACU')
  AND a.media_30d IS NOT NULL;

-- =============================================================================
-- E1 — Validação pós-aplicação
-- =============================================================================
-- SELECT count(*) FROM vw_ofertas_produtores WHERE origem = 'CEASA';            -- > 0
-- SELECT municipio, count(*) FROM vw_ofertas_produtores
--   WHERE origem = 'CEASA' GROUP BY municipio ORDER BY municipio;               -- 4 cidades PR
-- SELECT origem, count(*), min(id), max(id) FROM vw_ofertas_produtores
--   GROUP BY origem ORDER BY origem;                                            -- CEASA ids negativos
-- SELECT count(*) FROM ofertas_produtores;                                      -- inalterado

-- =============================================================================
-- ROLLBACK — reverter para só-produtores (definição original)
-- =============================================================================
-- CREATE OR REPLACE VIEW vw_ofertas_produtores AS
--  SELECT o.id, o.cultura, o.descricao, o.quantidade, o.unidade, o.disponibilidade,
--         o.preco_pretendido, o.status, o.origem, o.criado_em,
--         p.nome AS produtor_nome, p.tipo AS produtor_tipo, p.municipio, p.contato
--    FROM ofertas_produtores o
--    JOIN produtores p ON p.id = o.produtor_id;
