-- Status da última coleta PROHORT/CONAB (linha única id=1).
-- Fonte da "última atualização" exibida na página Mercado (Preços de Mercado — CEASAs).
-- O chat/prohort_collector.py faz upsert nesta linha ao fim de cada execução (best-effort:
-- falha aqui NÃO interrompe a ingestão de preços em prohort_precos).
-- Espelha o padrão de sql/coleta_status.sql (singleton id=1).
--
-- Rodar no Supabase SQL Editor. Idempotente.

create table if not exists prohort_status (
    id               smallint primary key default 1,
    finalizado_em    timestamptz,        -- instante real da ingestão (última atualização)
    data_max         date,               -- data de preço mais recente ingerida
    data_min         date,               -- data de preço mais antiga vista nesta execução
    linhas_inseridas integer,
    modo             text,               -- 'diario' | 'backfill'
    status           text,               -- 'ok' | 'sem_dados' | 'erro' | 'idle'
    erro             text,
    atualizado_em    timestamptz default now(),
    constraint prohort_status_singleton check (id = 1)
);

-- Linha inicial (idle) — evita 404 antes da 1ª coleta
insert into prohort_status (id, status) values (1, 'idle')
on conflict (id) do nothing;
