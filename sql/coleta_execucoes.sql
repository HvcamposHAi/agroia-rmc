-- Tabela de HISTÓRICO de execuções da coleta (uma linha por execução finalizada).
-- Alimenta o card "Última Atualização" e o histórico na página /coleta.
-- Escrita por:
--   * etapa2_itens_v9.py  → registrar_execucao() (sucesso / cancelamento / erro fatal)
--   * api/coleta.py       → auto-cura de status travado (status="error", etapa="timeout")
-- Lida por: api/coleta.py → get_ultima_execucao() / get_historico_execucoes()
--           (ordenadas por finalizado_em desc).
--
-- A tabela já existe em produção; este arquivo é o schema VERSIONADO/replicável
-- (create ... if not exists é não-destrutivo). dt_inicio/dt_fim são TEXT no
-- formato "DD/MM/AAAA" — mesmo formato que o código grava (não converter p/ date).
--
-- Rodar no Supabase SQL Editor.

create table if not exists coleta_execucoes (
    id              bigint generated always as identity primary key,
    iniciado_em     timestamptz,
    finalizado_em   timestamptz not null default now(),
    duracao_seg     integer,
    status          text not null,                 -- completed | error | cancelled
    etapa           text,                          -- finalizado | timeout | ...
    origem          text default 'manual',         -- manual | schedule | auto-cura
    dt_inicio       text,                          -- "DD/MM/AAAA"
    dt_fim          text,                          -- "DD/MM/AAAA"
    processados     integer default 0,
    novos           integer default 0,
    pulados         integer default 0,
    erros           integer default 0,
    itens_coletados integer default 0,
    fornecedores    integer default 0,
    empenhos        integer default 0,
    erro_resumo     text,
    erro_detalhes   jsonb default '[]'::jsonb,
    criado_em       timestamptz default now()
);

-- As consultas ordenam sempre por finalizado_em desc (última execução / histórico).
create index if not exists idx_coleta_execucoes_finalizado
    on coleta_execucoes (finalizado_em desc);
