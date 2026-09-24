-- Cotações da CEASA/PR POR VARIEDADE (ex.: TANGERINA PONKAN × MURKOTE × MONTENEGRINA).
--
-- Por quê: o PROHORT/CONAB (prohort_precos) só publica ~48 produtos genéricos
-- ("TANGERINA", "TOMATE"), sem variedade. A própria CEASA/PR publica ~770 códigos
-- produto+variedade+classificação+embalagem, com o "preço mais comum" do dia em
-- Curitiba, Maringá, Londrina, Foz do Iguaçu e Cascavel. Fonte:
--   https://celepar7.pr.gov.br/ceasa/cotprod_evolucao.asp  (FONTE: CEASA/PR)
-- Coletor: chat/ceasa_pr_collector.py  ·  Workflow: .github/workflows/ceasa_pr.yml
--
-- Tabela ADITIVA: não altera prohort_precos nem as views v_prohort_*.
-- Rodar no Supabase SQL Editor. Idempotente.

create table if not exists ceasa_pr_cotacoes (
    id            bigserial primary key,
    data_coleta   date    not null,
    unidade       text    not null,   -- CURITIBA | MARINGA | LONDRINA | FOZ DO IGUACU | CASCAVEL
    descricao     text    not null,   -- texto bruto da fonte: "TANGERINA PONKAN MEDIA cx 20 kg"
    produto       text    not null,   -- 1ª palavra, minúscula sem acento: "tangerina"
    variedade     text,               -- restante do nome: "ponkan media" (null = sem variedade)
    embalagem     text,               -- "cx 20 kg" | "kg" | "bj 200 g" | "cx c/ 30 dz"
    peso_kg       numeric,            -- kg por embalagem quando dedutível (20 | 1 | 0.2), senão null
    preco         numeric not null,   -- preço mais comum do dia, R$ por EMBALAGEM
    preco_kg      numeric,            -- preco / peso_kg (null se peso desconhecido)
    criado_em     timestamptz default now(),
    unique (data_coleta, unidade, descricao)
);

create index if not exists idx_ceasa_pr_prod on ceasa_pr_cotacoes (produto, unidade, data_coleta desc);

-- Leitura pública (frontend usa a chave anon); escrita só pelo coletor (service_role ignora RLS).
alter table ceasa_pr_cotacoes enable row level security;
drop policy if exists ceasa_pr_leitura on ceasa_pr_cotacoes;
create policy ceasa_pr_leitura on ceasa_pr_cotacoes for select to anon, authenticated using (true);

-- Resumo por variedade × embalagem × unidade: última cotação + estatísticas de 30 dias.
-- Janela ancorada na última data da própria linha (a fonte não cota todo dia/toda variedade).
create or replace view v_ceasa_pr_variedades as
with ult as (
    select unidade, descricao, max(data_coleta) as ultima_data
    from ceasa_pr_cotacoes
    group by unidade, descricao
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
join ult u on u.unidade = c.unidade and u.descricao = c.descricao
where c.data_coleta > u.ultima_data - 30
group by c.unidade, c.produto, c.variedade, c.embalagem, c.descricao, u.ultima_data;

grant select on ceasa_pr_cotacoes    to anon, authenticated;
grant select on v_ceasa_pr_variedades to anon, authenticated;

-- Status da última coleta (linha única id=1), mesmo padrão de prohort_status.
create table if not exists ceasa_pr_status (
    id               smallint primary key default 1,
    finalizado_em    timestamptz,
    data_max         date,
    linhas_inseridas integer,
    status           text,     -- 'ok' | 'sem_dados' | 'erro' | 'idle'
    erro             text,
    constraint ceasa_pr_status_singleton check (id = 1)
);
insert into ceasa_pr_status (id, status) values (1, 'idle') on conflict (id) do nothing;
alter table ceasa_pr_status enable row level security;
drop policy if exists ceasa_pr_status_leitura on ceasa_pr_status;
create policy ceasa_pr_status_leitura on ceasa_pr_status for select to anon, authenticated using (true);
grant select on ceasa_pr_status to anon, authenticated;
