-- Tabela de STATUS AO VIVO da coleta (linha única id=1).
-- Fonte compartilhada lida pelo backend (Render) para mostrar o progresso da coleta
-- independentemente de onde ela roda (GitHub Actions, máquina local, etc.).
-- O etapa2_itens_v9.py faz upsert nesta linha a cada atualização de progresso.
--
-- Rodar no Supabase SQL Editor.

create table if not exists coleta_status (
    id            smallint primary key default 1,
    dados         jsonb not null,
    atualizado_em timestamptz default now(),
    constraint coleta_status_singleton check (id = 1)
);

-- Linha inicial (idle)
insert into coleta_status (id, dados)
values (
    1,
    '{"status":"idle","etapa":"nenhuma","processados":0,"novos":0,"pulados":0,
      "erros":0,"itens_coletados":0,"fornecedores":0,"empenhos":0,
      "iniciado_em":null,"atualizado_em":null,"pid":null,"run_id":null}'::jsonb
)
on conflict (id) do nothing;
