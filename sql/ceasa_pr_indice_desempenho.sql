-- Correção de desempenho do painel de variedades da página Mercado (VariedadesCeasaPR.tsx).
-- Com a carga retroativa (~785 mil linhas desde 07/2021), a consulta do painel
-- (v_ceasa_pr_variedades?produto=eq.tomate&unidade=eq.CURITIBA) estoura o tempo limite da
-- chave anon e devolve HTTP 500: a CTE "ult" agrupava a tabela inteira antes do filtro.
-- Aditivo e idempotente; as colunas da view não mudam (o painel continua igual).

-- 1) Índice para a última data por descrição e para as séries por descrição
create index if not exists idx_ceasa_pr_unid_desc_data
    on ceasa_pr_cotacoes (unidade, descricao, data_coleta desc);

-- 2) View com "produto" na CTE: o filtro produto + unidade chega às duas leituras e usa
--    o índice idx_ceasa_pr_prod (produto, unidade, data_coleta desc)
create or replace view v_ceasa_pr_variedades as
with ult as (
    select unidade, produto, descricao, max(data_coleta) as ultima_data
    from ceasa_pr_cotacoes
    group by unidade, produto, descricao
)
select
    c.unidade,
    c.produto,
    c.variedade,
    c.embalagem,
    c.descricao,
    max(c.peso_kg)                                             as peso_kg,
    u.ultima_data,
    max(c.preco)    filter (where c.data_coleta = u.ultima_data) as ultimo_preco,
    max(c.preco_kg) filter (where c.data_coleta = u.ultima_data) as ultimo_preco_kg,
    round(avg(c.preco), 2)                                     as media_30d,
    min(c.preco)                                               as min_30d,
    max(c.preco)                                               as max_30d,
    round(avg(c.preco_kg), 2)                                  as media_kg_30d,
    count(*)                                                   as cotacoes_30d
from ceasa_pr_cotacoes c
join ult u on u.unidade = c.unidade and u.produto = c.produto and u.descricao = c.descricao
where c.data_coleta > u.ultima_data - 30
group by c.unidade, c.produto, c.variedade, c.embalagem, c.descricao, u.ultima_data;

grant select on v_ceasa_pr_variedades to anon, authenticated;

-- 3) Conferência (deve voltar em menos de 1 s e listar os tipos de tomate):
-- explain analyze select * from v_ceasa_pr_variedades where produto = 'tomate' and unidade = 'CURITIBA';
