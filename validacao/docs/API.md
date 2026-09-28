# API do backend e do agente (Fase 0)

Levantado em 26 e 27/09/2026 a partir de `api/main.py`, `api/benchmark_api.py`,
`chat/agent.py`, `chat/motor_router.py`, `benchmark/` e de execuções reais do Claude Code 2.1.119.

## Backend FastAPI (`https://agroia-rmc.onrender.com`)

Autenticação: cabeçalho `X-API-Key` = `API_SECRET_KEY` (rotas marcadas com "sim").

| Método | Rota | Auth | Uso na validação |
|---|---|---|---|
| GET | `/health` | não | checagem de saúde e aquecimento (partida a frio do Render free: 20 a 60 s) |
| POST | `/chat` | sim | não usada (o benchmark usa o caminho de produção em streaming) |
| POST | `/chat/stream` | sim | Parte B |
| GET | `/config/motor` | não | motores disponíveis e motor ativo global |
| POST | `/config/motor` | sim | troca o motor global (modo `switch_global` da Parte B) |
| POST | `/benchmark/comparar/stream` | sim | não usada (roda o loop do pacote benchmark, não o caminho de produção) |

### `/chat/stream`

Corpo (`ChatRequest`): `pergunta`, `historico` (lista), `session_id`, `idioma` (`pt`|`en`|`es`) e,
acrescentados para a validação (opcionais, padrão = comportamento anterior):

| Campo | Padrão | Efeito |
|---|---|---|
| `motor` | `null` | sobrepõe o switch global (`app_config.motor_ativo`) só nesta requisição; valores de `chat.motor_router.MOTORES`: `claude`, `groq_llama`, `maritaca`, `gemini` |
| `sem_cache` | `false` | não lê nem grava o cache de respostas (`chat/tools.py::_cache`, TTL 1 h, chave = pergunta normalizada, **não** inclui o motor) |
| `rastreio` | `false` | emite `{"tipo": "tool", "nome", "inputs", "resultado"}` por chamada de ferramenta e inclui `motor` (e, nos motores REST, `erro`, `tokens_entrada`, `tokens_saida`, `iteracoes`) no evento `fim` |

Resposta: Server-Sent Events, uma linha `data: {json}` por evento: `status` (progresso),
`token` (texto; nos motores não Claude a resposta vem inteira em um único token), `tool`
(com `rastreio`) e `fim` (`tools_usadas`).

Seleção de motor: `chat.agent.chat_stream` usa `motor` da requisição, senão `get_motor_ativo()`
(cache de 20 s por processo). `claude` usa o streaming nativo da Anthropic
(`claude-haiku-4-5-20251001`, `max_tokens` 2048); os demais passam por
`benchmark.agentic_loop.rodar_loop` com o provider REST correspondente. Nenhum caminho define
temperatura: vale o padrão de cada provedor.

**Deploy necessário:** a Parte B no modo `requisicao` exige que o Render esteja com a versão que
aceita `motor`, `sem_cache` e `rastreio`. Sem ela, o executor aborta com mensagem explícita;
alternativa: `b.modo_motor: switch_global` (troca o motor global e restaura ao final).

### Rotas usadas pelas páginas do frontend (`agroia-rmc.pages.dev`)

Rotas SPA (`agroia-frontend/src/App.tsx`): `/inicio`, `/assistente` (Chat), `/demanda`
(Dashboard e Consultas redirecionam para cá), `/mercado`, `/ofertas`, `/produtor`, `/documentos`,
`/alertas`, `/auditoria`, `/benchmark`, `/coleta`. Demanda, Documentos e Mercado leem o Supabase
direto (supabase-js, chave anônima): `vw_itens_agro`, `vw_licitacoes_agro_documentos`,
`v_prohort_*`, `vw_cruzamento_precos_ceasa`. O Chat usa `/chat/stream`.

## Pacote `benchmark/`

- Dataset: `benchmark/perguntas_benchmark.json`, 30 perguntas (P01 a P10 preço, L01 a L10
  licitação, E01 a E05 edital, G01 a G05 geral); conjunto A = 24, conjunto B = 6 (L06 e G01 a G05).
  Não há gabarito numérico no arquivo: `resultado_esperado` é `nao_vazio`/`qualquer`/`vazio`/`abstencao`.
- AF@k: `benchmark/metricas.py::nivel_af` (ferramenta aceitável entre as k primeiras chamadas e
  parâmetros críticos corretos na primeira ocorrência). A validação reutiliza essa função.
- Motores e rótulos: `benchmark/providers/factory.py`; preços: `benchmark/precos_modelos.py`
  (o arquivo marca o preço do Sabiá-4 como provisório e cita US$ 0,80/US$ 4,00 por 1M tokens para
  o Haiku 4.5; conferir a tabela de preços vigente antes de publicar custos).

## Claude Code como agente (A1 extrator Chrome e A2)

Versão verificada: 2.1.119. Comando efetivo (montado em `validacao/claude_chrome.py`):

```
ENABLE_TOOL_SEARCH=false MCP_CONNECTION_NONBLOCKING=false MCP_TIMEOUT=30000 claude -p --chrome --output-format stream-json --verbose \
  --no-session-persistence --permission-mode dontAsk --model <modelo> --max-turns <n> \
  --allowedTools "mcp__claude-in-chrome__*" --disallowedTools "<lista>"  < prompt.txt
```

Adaptações em relação ao plano, com o motivo:

| Plano | Adotado | Motivo verificado |
|---|---|---|
| `--permission-mode bypassPermissions` | `dontAsk` + `--allowedTools mcp__claude-in-chrome__*` | `bypassPermissions` libera todas as ferramentas; `dontAsk` nega o que não está na lista |
| restringir ferramentas | `--disallowedTools` com as internas e as do Chrome que um usuário não tem | com `--tools ""` o servidor do Chrome não é carregado (lista de ferramentas vazia na inicialização) |
| `--max-turns` | mantido | não aparece no `--help` da 2.1.119, mas é aceito (teste em 26/09/2026) |
| (não previsto) | `ENABLE_TOOL_SEARCH=false` | com a busca sob demanda, a primeira busca de ferramentas ocorre antes da conexão com a extensão e não encontra o Chrome; com a variável, as 18 ferramentas vêm carregadas na inicialização |
| (não previsto) | `MCP_CONNECTION_NONBLOCKING=false` e `MCP_TIMEOUT=30000` | sem elas o servidor do Chrome não estava conectado na inicialização em 4 de 4 testes (27/09/2026); com elas, em 4 de 4 |
| (não previsto) | prompt pela entrada padrão, não como argumento | no Windows o `claude` é um `.cmd` e o `cmd.exe` corta o argumento na 1ª quebra de linha, descartando as flags seguintes (saída em texto, ferramentas internas liberadas) |
| (não previsto) | status `ERRO_INFRA_CHROME` quando o agente termina sem usar o navegador e a inicialização não tinha `claude-in-chrome` conectado | a conexão com a extensão é assíncrona e às vezes chega depois da inicialização |

Ferramentas do servidor `claude-in-chrome` (lista obtida por `ToolSearch` em 26/09/2026):

| Ferramenta | Liberada ao agente | Classificação no parser |
|---|---|---|
| `navigate` | sim | navegar (KLM: digitar URL) |
| `computer` | sim | por `action`: clicar, digitar, tecla, rolar, capturar tela |
| `find`, `read_page`, `get_page_text` | sim | ler página (fora do KLM) |
| `form_input` | sim | digitar |
| `tabs_context_mcp`, `tabs_create_mcp` | sim | instrumentação / nova aba |
| `gif_creator` | sim | instrumentação (não conta como ação) |
| `update_plan` | não | pede aprovação humana do plano na extensão; em execução autônoma o plano é rejeitado e o agente para |
| `resize_window` | sim | outro |
| `javascript_tool`, `read_network_requests`, `read_console_messages` | não | um usuário não dispõe desses meios |
| `shortcuts_execute`, `shortcuts_list`, `switch_browser`, `upload_image` | não | fora do escopo das tarefas |

A extensão também sugere `browser_batch`; o parser expande lotes nas ações contidas.

Formato do log (`--output-format stream-json --verbose`): mensagens `system/init` (modelo,
ferramentas, `mcp_servers` com status), `assistant` (blocos `tool_use`), `user` (blocos
`tool_result`) e `result` (`num_turns`, `usage`, `total_cost_usd`, `result`, `permission_denials`).

Autenticação: a integração com o Chrome exige login de conta (`/login`); não funciona com chave de
API nem com token de `claude setup-token`.
