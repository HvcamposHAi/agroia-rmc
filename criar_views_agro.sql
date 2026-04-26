-- ============================================================================
-- VIEWS PARA ESCOPO AGRÍCOLA - AgroIA-RMC
-- Cria views que filtram APENAS licitações com relevante_af = true
--
-- Execução: Copiar e colar no SQL Editor do Supabase
-- ============================================================================

-- ============================================================================
-- 1. VIEW: vw_licitacoes_agro
-- Apenas licitações relevantes para agricultura
-- ============================================================================
CREATE OR REPLACE VIEW vw_licitacoes_agro AS
SELECT
    *
FROM licitacoes
WHERE relevante_af = true
ORDER BY dt_abertura DESC;

COMMENT ON VIEW vw_licitacoes_agro IS 'Apenas licitações agrícolas (relevante_af=true) - Escopo do projeto AgroIA-RMC';

-- ============================================================================
-- 2. VIEW: vw_itens_agro
-- Itens apenas de licitações agrícolas
-- ============================================================================
CREATE OR REPLACE VIEW vw_itens_agro AS
SELECT
    i.*
FROM itens_licitacao i
INNER JOIN licitacoes l ON i.licitacao_id = l.id
WHERE l.relevante_af = true
ORDER BY l.dt_abertura DESC, i.seq;

COMMENT ON VIEW vw_itens_agro IS 'Itens de licitações agrícolas (join com vw_licitacoes_agro)';

-- ============================================================================
-- 3. VIEW: vw_fornecedores_agro
-- Fornecedores que participaram de licitações agrícolas
-- ============================================================================
CREATE OR REPLACE VIEW vw_fornecedores_agro AS
SELECT DISTINCT
    f.*
FROM fornecedores f
INNER JOIN participacoes p ON f.id = p.fornecedor_id
INNER JOIN itens_licitacao i ON p.item_id = i.id
INNER JOIN licitacoes l ON i.licitacao_id = l.id
WHERE l.relevante_af = true
ORDER BY f.nome;

COMMENT ON VIEW vw_fornecedores_agro IS 'Fornecedores que participaram de licitações agrícolas';

-- ============================================================================
-- 4. VIEW: vw_participacoes_agro
-- Participações/bids apenas em licitações agrícolas
-- ============================================================================
CREATE OR REPLACE VIEW vw_participacoes_agro AS
SELECT
    p.*,
    l.processo,
    l.dt_abertura,
    i.seq as item_seq,
    i.descricao as item_descricao,
    f.nome as fornecedor_nome
FROM participacoes p
INNER JOIN itens_licitacao i ON p.item_id = i.id
INNER JOIN licitacoes l ON i.licitacao_id = l.id
INNER JOIN fornecedores f ON p.fornecedor_id = f.id
WHERE l.relevante_af = true
ORDER BY l.dt_abertura DESC, i.seq;

COMMENT ON VIEW vw_participacoes_agro IS 'Participações/bids em licitações agrícolas com contexto completo';

-- ============================================================================
-- 5. VIEW: vw_empenhos_agro
-- Empenhos (compromissos) apenas de licitações agrícolas
-- ============================================================================
CREATE OR REPLACE VIEW vw_empenhos_agro AS
SELECT
    e.*,
    l.processo,
    l.dt_abertura
FROM empenhos e
INNER JOIN licitacoes l ON e.licitacao_id = l.id
WHERE l.relevante_af = true
ORDER BY l.dt_abertura DESC;

COMMENT ON VIEW vw_empenhos_agro IS 'Empenhos (compromissos) de licitações agrícolas';

-- ============================================================================
-- 6. VIEW: vw_documentos_agro
-- Documentos PDFs apenas de licitações agrícolas
-- ============================================================================
CREATE OR REPLACE VIEW vw_documentos_agro AS
SELECT
    d.*,
    l.processo,
    l.dt_abertura,
    l.objeto as licitacao_objeto
FROM documentos_licitacao d
INNER JOIN licitacoes l ON d.licitacao_id = l.id
WHERE l.relevante_af = true
ORDER BY l.dt_abertura DESC, d.coletado_em DESC;

COMMENT ON VIEW vw_documentos_agro IS 'Documentos PDFs de licitações agrícolas (apenas 2.2% de cobertura)';

-- ============================================================================
-- 7. VIEW: vw_resumo_agro
-- Resumo executivo do escopo agrícola
-- ============================================================================
CREATE OR REPLACE VIEW vw_resumo_agro AS
SELECT
    (SELECT COUNT(*) FROM vw_licitacoes_agro) as total_licitacoes_agro,
    (SELECT COUNT(*) FROM vw_itens_agro) as total_itens_agro,
    (SELECT COUNT(*) FROM vw_fornecedores_agro) as total_fornecedores_agro,
    (SELECT COUNT(*) FROM vw_participacoes_agro) as total_participacoes_agro,
    (SELECT COUNT(*) FROM vw_empenhos_agro) as total_empenhos_agro,
    (SELECT COUNT(*) FROM vw_documentos_agro) as total_documentos_agro,
    (SELECT MIN(dt_abertura) FROM vw_licitacoes_agro) as data_minima,
    (SELECT MAX(dt_abertura) FROM vw_licitacoes_agro) as data_maxima,
    (SELECT COUNT(DISTINCT licitacao_id) FROM vw_documentos_agro) as licitacoes_com_documentos,
    ROUND(
        (SELECT COUNT(DISTINCT licitacao_id) FROM vw_documentos_agro)::numeric /
        (SELECT COUNT(*) FROM vw_licitacoes_agro)::numeric * 100,
        1
    ) as cobertura_documentos_pct;

COMMENT ON VIEW vw_resumo_agro IS 'Resumo executivo do escopo agrícola - use para dashboards e relatórios';

-- ============================================================================
-- 8. VIEW: vw_licitacoes_agro_recentes
-- Últimas 20 licitações agrícolas (para assistente)
-- ============================================================================
CREATE OR REPLACE VIEW vw_licitacoes_agro_recentes AS
SELECT
    processo,
    dt_abertura,
    objeto,
    situacao,
    (SELECT COUNT(*) FROM itens_licitacao WHERE licitacao_id = licitacoes.id) as qtd_itens,
    (SELECT COUNT(*) FROM documentos_licitacao WHERE licitacao_id = licitacoes.id) as qtd_documentos
FROM licitacoes
WHERE relevante_af = true
ORDER BY dt_abertura DESC
LIMIT 20;

COMMENT ON VIEW vw_licitacoes_agro_recentes IS 'Últimas 20 licitações agrícolas com contagem de itens e documentos';

-- ============================================================================
-- VERIFICAÇÃO: Executar queries de teste
-- ============================================================================

-- Teste 1: Total de licitações agrícolas
-- SELECT * FROM vw_resumo_agro;

-- Teste 2: Últimas licitações
-- SELECT * FROM vw_licitacoes_agro_recentes;

-- Teste 3: Itens agrícolas
-- SELECT COUNT(*) FROM vw_itens_agro;

-- Teste 4: Documentos agrícolas
-- SELECT * FROM vw_documentos_agro;

-- ============================================================================
-- FIM DO SCRIPT
-- ============================================================================
--
-- Próximas ações:
-- 1. Atualizar dados_atualizados_agro.py para usar essas views
-- 2. Configurar agente para sempre usar vw_* ao invés de tabelas brutas
-- 3. Criar índices nas views se necessário (performance)
--
-- ============================================================================
