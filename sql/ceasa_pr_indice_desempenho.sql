-- Desempenho da view v_ceasa_pr_variedades (painel de variedades da página Mercado).
-- Com a carga retroativa (~785 mil linhas desde 07/2021), a CTE "ult" (max(data_coleta) por
-- unidade e descrição) varre a tabela: consulta filtrada leva 1–3 s e a sem filtro estoura o
-- tempo limite. Este índice atende a CTE e as séries por descrição. Aditivo e idempotente.
create index if not exists idx_ceasa_pr_unid_desc_data
    on ceasa_pr_cotacoes (unidade, descricao, data_coleta desc);
