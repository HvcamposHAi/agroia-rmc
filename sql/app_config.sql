-- =============================================================================
-- app_config — configuração global da aplicação (linha única id=1).
-- Guarda o MOTOR LLM ATIVO usado por todos os agentes (Assistente, preços,
-- produtor, alertas, auditoria, RAG/PDF). Trocado pela UI via POST /config/motor.
-- Executar MANUALMENTE no SQL Editor do Supabase.
-- =============================================================================

create table if not exists public.app_config (
    id            smallint primary key default 1,
    motor_ativo   text not null default 'claude',
    atualizado_em timestamptz not null default now(),
    constraint app_config_singleton check (id = 1)
);

-- Linha inicial (motor = claude = comportamento atual de produção).
insert into public.app_config (id, motor_ativo) values (1, 'claude')
on conflict (id) do nothing;

-- A API lê e escreve via SUPABASE_KEY. Para o POST /config/motor gravar,
-- mantenha RLS DESABILITADA nesta tabela (conteúdo não sensível: só o nome do
-- motor), OU crie uma policy permissiva. Por padrão, tabelas criadas assim ficam
-- sem RLS (acesso liberado para a chave usada pela API).

-- Validação:
--   select * from public.app_config;     -- deve retornar 1 linha (id=1, motor_ativo='claude')
-- Trocar manualmente (exemplo):
--   update public.app_config set motor_ativo='gemini', atualizado_em=now() where id=1;
-- Rollback:
--   drop table if exists public.app_config;
