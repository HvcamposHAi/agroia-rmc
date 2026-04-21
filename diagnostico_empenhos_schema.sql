-- =======================================================================
-- DIAGNÓSTICO: Descobrir estrutura real da tabela EMPENHOS
-- =======================================================================
-- Execute no Supabase SQL Editor para entender como empenhos se relaciona

-- Q1: Ver todas as colunas de empenhos
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'empenhos'
ORDER BY ordinal_position;

-- Q2: Ver primeiras 5 linhas para entender a estrutura
SELECT * FROM empenhos LIMIT 5;

-- Q3: Ver colunas de licitacoes (para comparação)
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'licitacoes'
ORDER BY ordinal_position;

-- Q4: Procurar relacionamento entre empenhos e licitações
-- Usando uma busca por padrão comum (numero, ano de processo)
SELECT
    e.id as empenho_id,
    e.numero as numero_empenho,
    e.ano as ano_empenho,
    l.id as licitacao_id,
    l.processo,
    l.dt_abertura
FROM empenhos e
LEFT JOIN licitacoes l ON
    -- Tentativa 1: Correspondência de ano
    EXTRACT(YEAR FROM e.data_empenho) = EXTRACT(YEAR FROM l.dt_abertura)
    OR
    -- Tentativa 2: Se houver campo de processo em empenhos
    CAST(e.numero AS TEXT) LIKE CONCAT('%', CAST(l.id AS TEXT), '%')
LIMIT 10;

-- Q5: Verificar se há tabela intermediária relacionando empenhos-licitacoes
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
AND (table_name LIKE '%empenho%' OR table_name LIKE '%licitacao%');
