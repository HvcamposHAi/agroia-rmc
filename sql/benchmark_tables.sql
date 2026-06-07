-- =============================================================================
-- Benchmark de motores LLM — tabelas OPCIONAIS de durabilidade.
-- Executar MANUALMENTE no SQL Editor do Supabase.
-- NÃO afeta nenhuma tabela de produção. A fonte autoritativa continua sendo
-- os arquivos CSV/JSON em metrics/ (sync no banco é só espelho, BENCHMARK_DB_SYNC=true).
-- =============================================================================

-- Uma linha por invocação do benchmark_executor (run).
CREATE TABLE IF NOT EXISTS benchmark_execucoes (
    run_id        uuid PRIMARY KEY,
    dt_inicio     timestamptz NOT NULL DEFAULT now(),
    dt_fim        timestamptz,
    motores       text[]      NOT NULL,        -- {'claude','groq_llama','maritaca','gemini'}
    n_repeticoes  integer     NOT NULL,
    n_perguntas   integer     NOT NULL,
    versao_dataset text,
    observacao    text
);

-- Uma linha por (run, motor, questao, repeticao).
CREATE TABLE IF NOT EXISTS benchmark_resultados (
    id                 bigserial PRIMARY KEY,
    run_id             uuid        NOT NULL REFERENCES benchmark_execucoes(run_id) ON DELETE CASCADE,
    motor              text        NOT NULL,   -- claude | groq_llama | maritaca | gemini
    modelo             text        NOT NULL,   -- id exato (claude-haiku-4-5-20251001, ...)
    questao_id         text        NOT NULL,   -- P01, L02, ...
    categoria          text        NOT NULL,   -- preco | licitacao | edital | geral
    conjunto           text        NOT NULL,   -- A | B
    repeticao          integer     NOT NULL,
    dt_execucao        timestamptz NOT NULL DEFAULT now(),
    latencia_ms        integer,
    iteracoes          integer,
    tokens_entrada     integer,
    tokens_saida       integer,
    custo_usd          numeric(12,6),
    tool_esperada      text,
    tools_usadas       jsonb,                  -- ["query_itens_agro", ...]
    tool_calls_detalhe jsonb,                  -- [{"nome":..,"inputs":{...}}]
    af_nivel           integer,                -- 0=falhou, 1=AF@1, 2=AF@2, 3=AF@3
    abstencao_correta  boolean,
    tool_result_truncado boolean DEFAULT false,
    status             text        NOT NULL DEFAULT 'ok',  -- ok | erro
    erro               text,
    resposta           text,
    UNIQUE (run_id, motor, questao_id, repeticao)
);

CREATE INDEX IF NOT EXISTS idx_bench_res_run   ON benchmark_resultados (run_id);
CREATE INDEX IF NOT EXISTS idx_bench_res_motor ON benchmark_resultados (motor, questao_id);

-- ---------------------------------------------------------------------------
-- Validação rápida após uma execução:
--   SELECT motor, count(*) AS n, round(avg(latencia_ms)) AS lat_media,
--          round(100.0*sum((af_nivel=1)::int)/count(*),1) AS af1_pct
--     FROM benchmark_resultados WHERE run_id = '<run_id>'
--    GROUP BY motor ORDER BY motor;
--
-- Rollback (remove as duas tabelas):
--   DROP TABLE IF EXISTS benchmark_resultados;
--   DROP TABLE IF EXISTS benchmark_execucoes;
-- ---------------------------------------------------------------------------
