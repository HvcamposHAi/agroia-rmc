-- Criar função RPC para executar SQL dinamicamente
CREATE OR REPLACE FUNCTION public.exec_sql(sql_text text)
RETURNS json AS $$
DECLARE
  result json;
BEGIN
  EXECUTE sql_text;
  RETURN json_build_object('sucesso', true, 'mensagem', 'SQL executado com sucesso');
EXCEPTION WHEN OTHERS THEN
  RETURN json_build_object('sucesso', false, 'erro', SQLERRM);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant permissões para anon user (usado pelo Supabase)
GRANT EXECUTE ON FUNCTION public.exec_sql(text) TO anon, authenticated, service_role;
