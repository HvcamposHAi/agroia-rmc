# Benchmark de Motores LLM — AgroIA-RMC

Compara 4 motores LLM executando o **mesmo loop agêntico de tool_use** sobre o
**mesmo conjunto de perguntas**, coletando latência, custo, acurácia de ferramenta
(AF@k), consistência e significância estatística. Adaptação metodológica de
Yang et al. (2025) — ver `../benchmark_motores_llm.md` e `../benchmark_metodos_adaptados.md`.

## Isolamento (zero impacto em produção)

Este pacote é **autocontido**. Importa apenas LEITURA de `chat.tools`
(`TOOLS_SCHEMA`, `executar_tool`) e `chat.prompts` (`SYSTEM_PROMPT`). **Nunca**
importa `chat.agent` — reimplementa um mini-loop em `agentic_loop.py`. Não edita
nenhum arquivo de produção. O baseline (Claude) usa o mesmo `model id` e
parâmetros de `chat/agent.py`.

## Motores

| nome (`--motores`) | modelo | chave de API |
|---|---|---|
| `claude`     | claude-haiku-4-5-20251001 (baseline) | `ANTHROPIC_API_KEY` |
| `groq_llama` | llama-3.1-8b-instant (Groq)          | `GROQ_API_KEY` |
| `maritaca`   | sabia-4 (Maritaca; via `MARITACA_MODELO`) | `MARITACA_API_KEY` |
| `gemini`     | gemini-2.0-flash (Google)            | `GOOGLE_API_KEY` |

## Instalação (venv 3.11 dedicada)

```powershell
py -3.11 -m venv .venv-bench
.venv-bench\Scripts\Activate.ps1
pip install -r requirements_benchmark.txt
playwright install   # não necessário p/ o benchmark
```

`.env` (na raiz do projeto) — além das chaves de produção, adicione as dos motores:

```dotenv
GROQ_API_KEY=gsk_...
MARITACA_API_KEY=...
GOOGLE_API_KEY=AIza...
# opcionais:
BENCHMARK_DB_SYNC=false                 # true → espelha no Supabase
BENCHMARK_MAX_TOOL_RESULT_CHARS=4000    # trunca tool_result p/ Sabiá-3 (8k)
```

## Uso

```powershell
# Smoke: 1 pergunta, só Claude
python -m benchmark.benchmark_executor --motores claude --reps 1 --perguntas L02

# Completo: 3 repetições × 4 motores × 30 perguntas
python -m benchmark.benchmark_executor --motores all --reps 3 --perguntas all

# Subconjunto por categoria/conjunto
python -m benchmark.benchmark_executor --motores claude,gemini --reps 3 --perguntas preco
python -m benchmark.benchmark_executor --motores all --reps 3 --perguntas B

# Apenas exportar o resumo mais recente p/ o front
python -m benchmark.benchmark_executor --export-frontend
```

## Saídas (em `metrics/`)

- `benchmark_runs_<run_id>.csv` — uma linha por (motor, questão, repetição); append incremental.
- `benchmark_resumo_<run_id>.json` — agregados por motor/categoria + significância + exemplos.
- `agroia-frontend/public/benchmark/resultados.json` — consolidado p/ a página `/benchmark`.

## Banco (opcional)

Com `BENCHMARK_DB_SYNC=true`, espelha em `benchmark_execucoes` / `benchmark_resultados`.
Rode o DDL de `../sql/benchmark_tables.sql` no SQL Editor do Supabase. O insert é
**não-bloqueante**: falha de banco nunca derruba a coleta (CSV/JSON são autoritativos).

## Métricas

- **AF@1/2/3** — tool esperada nas primeiras k chamadas + parâmetros críticos batendo.
- **Abstenção (conjunto B)** — PNAE/PAA/fora de escopo: acerto = reportar "sem dados"/recusar.
- **Latência p50/p95** — mesma fórmula de `scripts/coletar_baseline.py`.
- **Consistência** — cosseno médio par-a-par das N repetições (`paraphrase-multilingual-MiniLM-L12-v2`).
- **Significância** — t pareado (`scipy.stats.ttest_rel`) + Bonferroni; notação `⁰¹²³`.

> **Nota de domínio:** `licitacoes.canal` só tem ARMAZEM_FAMILIA/BANCO_ALIMENTOS/MESA_SOLIDARIA/OUTRO.
> NÃO existe PNAE/PAA nos dados — por isso essas perguntas são **conjunto B** (abstenção).
