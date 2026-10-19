-- Pauta de referência do Sacolão da Família e do Sacolão Móvel (plano v3, E2).
-- Aditivo e idempotente; nenhuma tabela existente é alterada. Rodar no SQL Editor do Supabase.
-- Conteúdo vem de chat/pauta_dados.py (fonte única) via scripts/seed_pauta_175.py.
--
--   pauta_ato         ato normativo da pauta (ex.: Portaria SMSAN 175/2026)
--   pauta_referencia  uma linha por estação × subgrupo × espécie candidata

create table if not exists pauta_ato (
    id              text primary key,                 -- ex.: 'smsan-175-2026'
    ato             text not null,                    -- ex.: 'Portaria 175'
    orgao           text not null,
    numero          int  not null,
    ano             int  not null,
    data            date not null,
    diario_oficial  int,
    sumula          text,
    fonte           text,
    vigente         boolean not null default true,
    criado_em       timestamptz default now()
);

create table if not exists pauta_referencia (
    id              bigserial primary key,
    ato_id          text not null references pauta_ato(id) on delete cascade,
    estacao         text not null check (estacao in ('outono_inverno', 'primavera_verao')),
    ordem_subgrupo  smallint not null check (ordem_subgrupo between 1 and 5),
    grupo           text not null,
    subgrupo        text not null,
    minimo          smallint not null check (minimo > 0),
    especie         text not null,
    variedade       text not null default '',          -- '' = sem variedade (chave única)
    texto_original  text not null,                     -- exatamente como no anexo do ato
    observacao      text,                              -- interpretação feita na transcrição
    validar_smsan   boolean not null default false,    -- interpretação a confirmar (P7)
    validado_por    text,
    validado_em     timestamptz,
    criado_em       timestamptz default now(),
    unique (ato_id, estacao, especie, variedade)
);
create index if not exists idx_pauta_referencia_ato on pauta_referencia (ato_id, estacao, ordem_subgrupo);

-- RLS: leitura pública; sem política de escrita (só service_role grava).
alter table pauta_ato        enable row level security;
alter table pauta_referencia enable row level security;

drop policy if exists pauta_ato_leitura on pauta_ato;
create policy pauta_ato_leitura on pauta_ato for select to anon, authenticated using (true);
drop policy if exists pauta_referencia_leitura on pauta_referencia;
create policy pauta_referencia_leitura on pauta_referencia for select to anon, authenticated using (true);

grant select on pauta_ato, pauta_referencia to anon, authenticated;
