-- Contrato de não impacto (plano v3, E0): devolve a definição das views existentes
-- para scripts/linha_base_contratos.py comparar antes e depois de cada etapa.
-- Só leitura; idempotente. Rodar no SQL Editor do Supabase.

create or replace function public.contrato_viewdefs(nomes text[])
returns table (nome text, definicao text)
language sql
stable
security invoker
as $$
  select c.relname::text, pg_get_viewdef(c.oid, true)
  from pg_class c
  join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public'
    and c.relkind in ('v', 'm')
    and c.relname = any (nomes)
  order by 1;
$$;

revoke all on function public.contrato_viewdefs(text[]) from public, anon;
grant execute on function public.contrato_viewdefs(text[]) to authenticated, service_role;
