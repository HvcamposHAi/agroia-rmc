-- Clima histórico e índices de apoio à projeção de preços (plano v3, E4).
-- Aditivo e idempotente; nenhuma tabela existente é alterada.
-- Rodar no SQL Editor do Supabase. Escrita só pelo coletor (service_role).
--
--   clima_regiao   regiões produtoras (pontos de grade) — lista definitiva vem de E3 (P8/P9)
--   clima_diario   NASA POWER diário por região
--   indice_enso    ONI mensal (NOAA) — média móvel de 3 meses, atribuída ao mês central
--   ipca_mensal    IPCA número-índice (IBGE/SIDRA, tabela 1737, variável 2266) — deflator
--   clima_status   última execução do coletor (id = 1)

create table if not exists clima_regiao (
    id          text primary key,              -- ex.: 'pr_colombo'
    nome        text not null,
    uf          char(2) not null,
    lat         numeric(7,4) not null check (lat between -90 and 90),
    lon         numeric(7,4) not null check (lon between -180 and 180),
    provisoria  boolean not null default true, -- false só depois da validação de E3
    observacao  text,
    criado_em   timestamptz default now()
);

create table if not exists clima_diario (
    regiao_id     text not null references clima_regiao(id) on delete cascade,
    data          date not null,
    chuva_mm      numeric,   -- PRECTOTCORR
    tmax_c        numeric,   -- T2M_MAX
    tmin_c        numeric,   -- T2M_MIN
    tmed_c        numeric,   -- T2M
    umidade_rel   numeric,   -- RH2M (%)
    umidade_solo  numeric,   -- GWETROOT (0 a 1, zona de raízes)
    fonte         text not null default 'NASA POWER',
    criado_em     timestamptz default now(),
    primary key (regiao_id, data)
);
create index if not exists idx_clima_diario_data on clima_diario (data desc);

create table if not exists indice_enso (
    mes   date primary key,      -- primeiro dia do mês central da média de 3 meses
    oni   numeric not null
);

create table if not exists ipca_mensal (
    mes            date primary key,   -- primeiro dia do mês
    numero_indice  numeric not null    -- base dez/1993 = 100
);

create table if not exists clima_status (
    id                int primary key default 1 check (id = 1),
    finalizado_em     timestamptz,
    data_max          date,
    linhas_inseridas  int,
    status            text check (status in ('ok', 'sem_dados', 'erro', 'idle')),
    erro              text
);
insert into clima_status (id, status) values (1, 'idle') on conflict (id) do nothing;

-- Regiões iniciais PROVISÓRIAS: cinturão verde da RMC, que abastece a CEASA Curitiba de
-- folhosas e brássicas. Coordenadas da sede municipal (a grade do POWER é de 0,5°).
insert into clima_regiao (id, nome, uf, lat, lon, observacao) values
    ('pr_curitiba',     'Curitiba',              'PR', -25.4284, -49.2733, 'referência da CEASA Curitiba'),
    ('pr_colombo',      'Colombo',               'PR', -25.2925, -49.2262, 'cinturão verde da RMC'),
    ('pr_sjp',          'São José dos Pinhais',  'PR', -25.5302, -49.2061, 'cinturão verde da RMC'),
    ('pr_mandirituba',  'Mandirituba',           'PR', -25.7769, -49.3256, 'cinturão verde da RMC'),
    ('pr_araucaria',    'Araucária',             'PR', -25.5859, -49.4047, 'cinturão verde da RMC')
on conflict (id) do nothing;

-- RLS: leitura pública; sem política de escrita (só service_role grava).
alter table clima_regiao  enable row level security;
alter table clima_diario  enable row level security;
alter table indice_enso   enable row level security;
alter table ipca_mensal   enable row level security;
alter table clima_status  enable row level security;

drop policy if exists clima_regiao_leitura on clima_regiao;
create policy clima_regiao_leitura on clima_regiao for select to anon, authenticated using (true);
drop policy if exists clima_diario_leitura on clima_diario;
create policy clima_diario_leitura on clima_diario for select to anon, authenticated using (true);
drop policy if exists indice_enso_leitura on indice_enso;
create policy indice_enso_leitura on indice_enso for select to anon, authenticated using (true);
drop policy if exists ipca_mensal_leitura on ipca_mensal;
create policy ipca_mensal_leitura on ipca_mensal for select to anon, authenticated using (true);
drop policy if exists clima_status_leitura on clima_status;
create policy clima_status_leitura on clima_status for select to anon, authenticated using (true);

grant select on clima_regiao, clima_diario, indice_enso, ipca_mensal, clima_status to anon, authenticated;
