-- ============================================================================
-- DROP VIEW: vw_itens_agro_puros
-- MOTIVO: Consolidação - uso exclusivo de vw_itens_agro
-- DATA: 2026-04-25
-- ============================================================================

-- Verificar dependências antes de deletar
-- SELECT * FROM information_schema.views WHERE table_name = 'vw_itens_agro_puros';

-- Deletar a view com CASCADE para remover dependências
DROP VIEW IF EXISTS vw_itens_agro_puros CASCADE;

-- Confirmar sucesso
SELECT 'View vw_itens_agro_puros deletada com sucesso' as resultado;

-- Verificar que vw_itens_agro ainda existe
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name = 'vw_itens_agro';
