# 🌾 AgroIA-RMC

**Plataforma de Inteligência Artificial para coordenar a oferta da Agricultura Familiar com a demanda institucional pública de alimentos na Região Metropolitana de Curitiba (RMC).**

> Projeto de dissertação do Mestrado em Computação Aplicada — **PPGCA/UEPG**.

[![Python 3.13](https://img.shields.io/badge/Python-3.13-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/React-19-61DAFB)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-8-646CFF)](https://vitejs.dev/)
[![Claude Haiku 4.5](https://img.shields.io/badge/Claude-Haiku%204.5-D97757)](https://www.anthropic.com/)
[![Supabase](https://img.shields.io/badge/Supabase-pgvector-3ECF8E)](https://supabase.com/)

---

## 📑 Índice

1. [Sobre o Projeto](#-sobre-o-projeto)
2. [Escopo: Agricultura Familiar](#-escopo-agricultura-familiar-exclusivamente)
3. [Arquitetura Geral](#-arquitetura-geral)
4. [Stack Tecnológica](#-stack-tecnológica)
5. [Estrutura de Diretórios](#-estrutura-de-diretórios)
6. [Pipeline de Coleta de Dados](#-pipeline-de-coleta-de-dados)
7. [Banco de Dados](#-banco-de-dados-supabase)
8. [Agente Conversacional + RAG](#-agente-conversacional--rag)
9. [API Backend (FastAPI)](#-api-backend-fastapi)
10. [Frontend (React)](#-frontend-react--vite)
11. [Instalação e Configuração](#-instalação-e-configuração)
12. [Como Executar](#-como-executar)
13. [Variáveis de Ambiente](#-variáveis-de-ambiente)
14. [Deploy](#-deploy)
15. [Particularidades do Portal JSF/RichFaces](#-particularidades-do-portal-jsfrichfaces)
16. [Limitações Conhecidas](#-limitações-conhecidas)
17. [Segurança](#-segurança)
18. [Troubleshooting](#-troubleshooting)
19. [Autor e Licença](#-autor)

---

## 🌱 Sobre o Projeto

O **AgroIA-RMC** é uma plataforma de pesquisa que reúne, em um só lugar, todo o ciclo de tratamento de dados sobre as compras públicas de alimentos da agricultura familiar na RMC:

1. **Coleta automatizada (web scraping)** do portal de licitações da Prefeitura de Curitiba (tecnologia JSF/RichFaces), usando Playwright.
2. **Classificação agrícola** dos itens licitados, separando o que é agricultura familiar do que está fora do escopo.
3. **Indexação semântica (RAG)** dos documentos (editais, termos de referência, atas) em PDF, com embeddings vetoriais armazenados no `pgvector`.
4. **Agente conversacional com IA** (Claude Haiku 4.5) capaz de consultar o banco de dados via *tool use* e responder perguntas em linguagem natural.
5. **Painéis analíticos, alertas inteligentes e auditoria de qualidade** dos dados, expostos em uma interface web em React.

O objetivo final é fornecer aos gestores públicos (**SMSAN/FAAC** — Secretaria Municipal de Segurança Alimentar e Nutricional / Fundo de Apoio à Agricultura de Curitiba) e aos pesquisadores uma ferramenta para entender a dinâmica de demanda, identificar riscos de desabastecimento e alta de preços, e qualificar o planejamento das compras institucionais.

---

## 🎯 Escopo: Agricultura Familiar Exclusivamente

> **IMPORTANTE:** Toda análise, consulta e resposta do assistente é restrita a licitações **agrícolas** (`relevante_af = true` / `relevante_agro = true`).

| Item | Valor |
|------|-------|
| Licitações agrícolas no escopo | **~715** (≈ 57,8% do total SMSAN/FAAC) |
| Licitações fora do escopo (não-agrícolas) | ~522 (ignoradas) |
| Período coberto | **30/08/2019 a 08/04/2026** |
| Órgão | SMSAN / FAAC (Curitiba) |
| Canais institucionais | PNAE, PAA, Armazém da Família, Banco de Alimentos, Mesa Solidária |

**Categorias agrícolas válidas** (`categoria_v2`):

- `HORTIFRUTI` — tomate, hortaliças, batata, pepino, mandioca, abóbora, temperos, extratos
- `FRUTAS` — uva, ameixa, goiabada, etc.
- `PROTEINA_ANIMAL` — frango, ovos, carnes
- `LATICINIOS` — leite, queijo, iogurte, manteiga, nata, requeijão
- `GRAOS_CEREAIS` — arroz, feijão, milho, trigo, lentilha, ervilha, aveia, amendoim

Categorias **excluídas** das respostas: `PROCESSADOS_AF` (macarrão, biscoito, farinha industrializada), `NAO_CLASSIFICADO`, `OUTRO`.

---

## 🏗 Arquitetura Geral

```
┌────────────────────────────────────────────────────────────────────────┐
│                      COLETA (Playwright + Python)                        │
│  Portal JSF/RichFaces de Curitiba ──▶ Licitações, Itens, Fornecedores,   │
│  Participações, Empenhos e PDFs (Google Drive + Supabase Storage)        │
└──────────────────────────────────┬───────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     SUPABASE (PostgreSQL + pgvector)                     │
│  Tabelas: licitacoes, itens_licitacao, fornecedores, participacoes,      │
│  empenhos, documentos_licitacao, pdf_chunks (embeddings), conversas      │
│  Views: vw_itens_agro, vw_demanda_agro_ano, vw_cobertura_classificacao   │
└──────────────────────────────────┬───────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      BACKEND — API FastAPI (api/main.py)                 │
│  • /chat e /chat/stream  → Agente Claude Haiku 4.5 + tool use + RAG      │
│  • /alertas              → Alertas de preço/desabastecimento com IA      │
│  • /auditoria/*          → Auditoria e consistência de dados             │
│  • /coleta/*             → Disparo e monitoramento da coleta (SSE)       │
│  Autenticação por API Key (X-API-Key) + CORS restrito                    │
└──────────────────────────────────┬───────────────────────────────────────┘
                                    │  REST + Server-Sent Events (SSE)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                FRONTEND — React 19 + Vite + TailwindCSS                  │
│  Páginas: Chat · Dashboard · Consultas · Alertas · Documentos ·          │
│           Auditoria · Coleta                                             │
│  Deploy: Netlify (SPA)                                                    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🧰 Stack Tecnológica

### Backend / Dados
| Tecnologia | Uso |
|------------|-----|
| **Python 3.13** | Linguagem principal |
| **FastAPI + Uvicorn** | API REST e streaming SSE |
| **Anthropic Claude Haiku 4.5** | Agente conversacional com *tool use* |
| **Supabase (PostgreSQL)** | Banco de dados gerenciado |
| **pgvector** | Busca de similaridade vetorial (RAG) |
| **Playwright (Chromium)** | Web scraping do portal JSF/RichFaces |
| **BeautifulSoup4 / lxml** | Parsing de HTML |
| **sentence-transformers** | Embeddings 384-dim (`paraphrase-multilingual-MiniLM-L12-v2`) |
| **EasyOCR / pdfplumber / PyMuPDF / PyPDF2** | Extração de texto de PDFs (inclui OCR) |
| **APScheduler** | Agendamento da coleta semanal |
| **google-api-python-client** | Upload de PDFs no Google Drive |

### Frontend
| Tecnologia | Uso |
|------------|-----|
| **React 19 + TypeScript** | UI |
| **Vite 8** | Build e dev server |
| **TailwindCSS 4** | Estilização |
| **React Router 7** | Roteamento SPA |
| **Recharts** | Gráficos do Dashboard |
| **react-markdown** | Renderização das respostas do agente |
| **axios** | Cliente HTTP |
| **@supabase/supabase-js** | Acesso direto ao Supabase quando necessário |

---

## 📂 Estrutura de Diretórios

```
agroia-rmc/
├── api/                          # Backend FastAPI
│   ├── main.py                   # App + todos os endpoints
│   └── coleta.py                 # Orquestração da coleta (subprocess + APScheduler)
│
├── chat/                         # Núcleo do agente conversacional
│   ├── agent.py                  # Loop de tool_use (chat + chat_stream)
│   ├── tools.py                  # 4 tools SQL/RAG + cache + sanitização
│   ├── prompts.py                # System prompt do AgroIA
│   └── db.py                     # Cliente Supabase (singleton)
│
├── agroia-frontend/              # Frontend React + Vite
│   ├── src/
│   │   ├── App.tsx               # Rotas
│   │   ├── pages/                # Chat, Dashboard, Consultas, Alertas,
│   │   │                         #   Documentos, Auditoria, Coleta
│   │   ├── components/           # Layout, Sidebar, ResponseRenderer
│   │   └── lib/                  # apiClient.ts, supabaseClient.ts
│   ├── package.json
│   └── netlify.toml (raiz)       # Configuração de deploy
│
├── etapa2_itens_v9.py            # Fase 2: itens, fornecedores, participações, empenhos
├── etapa3_producao.py            # Fase 3: download de PDFs
├── coleta_criticos.py            # Coleta direcionada a processos críticos
│
├── enriquecer_classificacao.py   # Classificação agrícola (categoria + relevância)
├── classificacao_*.py            # Variações de classificação (via API, instruções, etc.)
│
├── indexar_pdfs.py               # OCR + chunking + embeddings → pdf_chunks
├── indexar_agro_apenas.py        # Indexação só de PDFs agrícolas
├── reindexacao_completa.py       # Reindexação completa
├── reconciliar_drive_supabase.py # Reconciliação Google Drive ↔ Supabase
│
├── dados_atualizados.py          # Resumo executivo (sem cache) do banco
├── dados_atualizados_agro.py     # Idem, restrito a agrícolas
├── validar_consistencia.py       # Validação de consistência de dados
│
├── diagnostico_portal.py         # Teste de conectividade do portal
├── verificar_status_db.py        # Contagem de linhas das tabelas
├── teste_busca_rag.py            # Teste da busca semântica
│
├── tests/                        # Testes de integração e hotfixes
├── requirements.txt              # Dependências de produção (coleta + API)
├── requirements_chat.txt         # Dependências do chat/RAG
├── requirements_rag.txt          # Dependências específicas de RAG
├── CLAUDE.md                     # Guia para o Claude Code (regras do portal)
└── README.md                     # Este arquivo
```

---

## 🔄 Pipeline de Coleta de Dados

A coleta é organizada em **três fases**, todas baseadas em automação de navegador com Playwright (o portal exige sessão de navegador real).

### Fase 1 — Licitações
- **Fonte:** busca no portal por intervalo de datas + filtro de órgão.
- **Órgão:** `SMSAN/FAAC` · **Período:** `01/01/2019` a `31/12/2026`.
- **Resultado:** ~1.237 processos de licitação.

### Fase 2 — Itens e Participantes (`etapa2_itens_v9.py`)
Extrai das páginas de detalhe de cada licitação:
- **itens_licitacao** — ~7.882 itens (99,8% de cobertura) com classificação agrícola (`relevante_agro`, `categoria_v2`)
- **fornecedores** — ~3.081 fornecedores
- **participacoes** — ~26.211 lances/participações
- **empenhos** — ~3.473 empenhos (~36% — máximo possível devido aos dados do portal)

```bash
python etapa2_itens_v9.py
# Flags relevantes (no topo do arquivo):
#   FORCAR_REPROCESSAR=False  → True apaga itens existentes antes de recoletar
#   REGS_POR_PAG=5            → registros por página no portal
#   DELAY=2.0                 → segundos entre requisições
```

### Fase 3 — PDFs (`etapa3_producao.py`)
Baixa os documentos das licitações a partir dos modais e salva no **Supabase Storage + Google Drive**.
Implementação baseada em `expect_page()` + `expect_download()` (a abordagem com `requests` falha por validação de sessão).

```bash
python etapa3_producao.py                # do início
python etapa3_producao.py --resume       # retoma do checkpoint
python etapa3_producao.py --limit 100    # coleta 100 processos
```

- **Checkpoint:** `coleta_checkpoint.json`
- **Log:** `coleta_producao.log`

### Coleta orquestrada pela API
A coleta também pode ser disparada e monitorada pela interface web, via endpoints `/coleta/*` (ver [API](#-api-backend-fastapi)), com **agendamento semanal** automático (APScheduler — padrão: segunda-feira às 06:00, configurável).

---

## 🗄 Banco de Dados (Supabase)

### Tabelas principais
| Tabela | Descrição |
|--------|-----------|
| `licitacoes` | Processos de licitação (processo, canal, datas, situação, objeto, `relevante_af`) |
| `itens_licitacao` | Itens solicitados, com classificação agrícola (`relevante_agro`, `categoria_v2`) |
| `fornecedores` | Cooperativas, associações, empresas e pessoas físicas |
| `participacoes` | Lances / participações dos fornecedores |
| `empenhos` | Empenhos (execução de despesa) |
| `documentos_licitacao` | Metadados e status de download dos PDFs |
| `pdf_chunks` | Trechos de texto dos PDFs + embeddings (`vector(384)`) para RAG |
| `conversas` | Histórico das conversas do chat (por `session_id`) |

### Views analíticas
| View | Descrição |
|------|-----------|
| `vw_itens_agro` | Itens classificados como agrícolas (`relevante_agro = true`) |
| `vw_demanda_agro_ano` | Demanda anual por categoria/canal |
| `vw_cobertura_classificacao` | Métricas de cobertura da classificação |

### Esquema RAG (`pdf_chunks`)
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS pdf_chunks (
    id            bigserial PRIMARY KEY,
    licitacao_id  bigint NOT NULL REFERENCES licitacoes(id) ON DELETE CASCADE,
    documento_id  bigint REFERENCES documentos_licitacao(id) ON DELETE SET NULL,
    processo      text NOT NULL,
    nome_doc      text,
    chunk_index   int NOT NULL,
    chunk_text    text NOT NULL,
    embedding     vector(384),
    tokens_aprox  int,
    indexado_em   timestamptz DEFAULT now(),
    UNIQUE (documento_id, chunk_index)
);

CREATE INDEX idx_pdf_chunks_embedding ON pdf_chunks
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX idx_pdf_chunks_processo ON pdf_chunks (processo);
```

---

## 🤖 Agente Conversacional + RAG

O agente vive em `chat/` e roda um **loop de *tool use*** (até 10 iterações) com o modelo `claude-haiku-4-5`. O system prompt (em `chat/prompts.py`) impõe respostas curtas, em tabelas markdown, sempre restritas ao escopo agrícola, e suporta *prompt caching*.

### Tools disponíveis (`chat/tools.py`)
| Tool | Função |
|------|--------|
| `query_itens_agro` | Consulta itens agrícolas com agregações: `detalhado`, `por_cultura`, `por_canal`, `por_ano`, `por_categoria` |
| `query_fornecedores` | Fornecedores e suas participações (filtro por tipo, canal, ano) |
| `query_licitacoes` | Licitações por processo, canal e período (apenas com itens agrícolas) |
| `buscar_chunks_rag` | Busca semântica nos PDFs via embeddings (similaridade de cosseno calculada em Python) |

> Há um alias de compatibilidade `buscar_documentos_vetor` que redireciona para `buscar_chunks_rag`.

### Fluxo RAG
```
Pergunta ──▶ embedding (sentence-transformers, 384-dim)
        ──▶ recupera chunks de pdf_chunks
        ──▶ similaridade de cosseno (numpy)
        ──▶ top-k chunks relevantes (score ≥ min_similaridade)
        ──▶ Claude sintetiza a resposta com o contexto recuperado
```

### Indexação dos PDFs
```bash
python indexar_pdfs.py            # OCR + chunking + embeddings → pdf_chunks
python indexar_agro_apenas.py     # somente PDFs agrícolas
python reindexacao_completa.py    # reindexação completa
python teste_busca_rag.py         # testa a busca semântica
```

### Recursos de robustez
- **Cache em memória** das respostas (TTL 3.600s) com normalização da pergunta.
- **Sanitização de entrada** contra SQL injection básico.
- **Streaming (SSE)** token a token via `chat_stream`.

---

## 🔌 API Backend (FastAPI)

Arquivo: [api/main.py](api/main.py). Autenticação por header **`X-API-Key`** (env `API_SECRET_KEY`); CORS restrito a `ALLOWED_ORIGINS`.

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/` | Documentação/índice da API |
| `GET` | `/health` | Status da conexão com o Supabase |
| `POST` | `/chat` | Pergunta ao agente (com persistência de histórico) |
| `POST` | `/chat/stream` | Versão streaming (SSE) do chat |
| `GET` | `/conversas/{session_id}` | Histórico completo de uma conversa |
| `DELETE` | `/conversas/{session_id}` | Apaga o histórico de uma conversa |
| `POST` | `/alertas` | Gera alertas de preço/desabastecimento/superfaturamento com IA |
| `POST` | `/alertas/stream` | Versão streaming dos alertas (com cache de 30 min) |
| `POST` | `/auditoria/executar` | Auditoria de qualidade (cobertura de docs, empenhos sem docs) |
| `POST` | `/auditoria/executar/stream` | Versão streaming da auditoria |
| `POST` | `/auditoria/chat` | Discute os resultados da auditoria com IA |
| `GET` | `/auditoria/consistencia` | Valida consistência entre Supabase e frontend |
| `POST` | `/coleta/iniciar` | Inicia a coleta manualmente (subprocess) |
| `POST` | `/coleta/cancelar` | Cancela a coleta em andamento (SIGTERM) |
| `GET` | `/coleta/status` | Status atual da coleta |
| `GET` | `/coleta/stream` | Progresso da coleta em tempo real (SSE) |
| `GET` | `/coleta/stats` | Estatísticas de classificação agrícola |
| `GET` | `/coleta/config` | Lê a configuração do agendamento semanal |
| `POST` | `/coleta/config` | Atualiza a configuração do agendamento |
| `GET` | `/docs` | Swagger UI interativa |

**Exemplo de requisição:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_SECRET_KEY" \
  -d '{
    "pergunta": "Qual cultura teve maior demanda em 2022?",
    "session_id": "user-123",
    "historico": []
  }'
```

---

## 🖥 Frontend (React + Vite)

App SPA em [agroia-frontend/](agroia-frontend/), com 7 páginas roteadas por React Router:

| Página | Rota | Função |
|--------|------|--------|
| **Chat** | `/` | Conversa com o agente (streaming, histórico, indicação de tools usadas) |
| **Dashboard** | `/dashboard` | Gráficos de demanda por cultura, categoria, canal e ano (Recharts) |
| **Consultas** | `/consultas` | Consultas estruturadas ao banco |
| **Alertas** | `/alertas` | Alertas inteligentes (alta de preço, desabastecimento, superfaturamento) |
| **Documentos** | `/documentos` | Exploração dos PDFs/documentos das licitações |
| **Auditoria** | `/auditoria` | Painel de qualidade dos dados + chat de auditoria |
| **Coleta** | `/coleta` | Disparo, monitoramento (SSE) e agendamento da coleta |

O cliente HTTP ([apiClient.ts](agroia-frontend/src/lib/apiClient.ts)) injeta automaticamente o header `X-API-Key` e expõe helpers de streaming SSE.

---

## ⚙️ Instalação e Configuração

### Pré-requisitos
- **Python 3.13** (ou 3.9+)
- **Node.js 18+** (para o frontend)
- Chave da **Anthropic API** (`ANTHROPIC_API_KEY`)
- Projeto **Supabase** (PostgreSQL + extensão `pgvector`)
- (Opcional) Pasta no **Google Drive** para armazenar os PDFs

### 1. Clonar e preparar o backend
```bash
git clone https://github.com/HvcamposHAi/agroia-rmc.git
cd agroia-rmc

python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt        # coleta + API
pip install -r requirements_chat.txt   # chat + RAG
playwright install chromium            # navegador para a coleta
```

### 2. Preparar o frontend
```bash
cd agroia-frontend
npm install
```

### 3. Configurar variáveis de ambiente
Crie um arquivo `.env` na raiz (backend) — ver [Variáveis de Ambiente](#-variáveis-de-ambiente).
Para o frontend, crie `agroia-frontend/.env`:
```
VITE_API_URL=http://localhost:8000
VITE_API_SECRET_KEY=<sua-api-secret-key>
VITE_SUPABASE_URL=https://<projeto>.supabase.co
VITE_SUPABASE_ANON_KEY=<anon-key>
```

---

## ▶️ Como Executar

### Backend (API)
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
# Swagger: http://localhost:8000/docs
```

### Frontend (dev)
```bash
cd agroia-frontend
npm run dev
# Abre em http://localhost:5173 (Vite)
```

### Atalho no Windows
```bat
START_SYSTEM.bat        :: sobe API + frontend
INICIAR_DESENVOLVIMENTO.bat
```

### Verificar dados sempre atualizados (sem cache)
```bash
python dados_atualizados.py --resumo                 # resumo executivo
python dados_atualizados.py --licitacoes-recentes 10 # últimas 10 licitações
python dados_atualizados.py --status-coleta          # status da coleta de PDFs
```

### Comandos úteis de diagnóstico
```bash
python diagnostico_portal.py     # testa conectividade do portal
python verificar_status_db.py    # contagem de linhas das tabelas
python validar_consistencia.py   # checa consistência dos dados
```

---

## 🔐 Variáveis de Ambiente

Arquivo `.env` na raiz do projeto (backend):

```env
# Banco de dados
SUPABASE_URL=https://<projeto>.supabase.co
SUPABASE_KEY=<anon-ou-service-key>

# IA
ANTHROPIC_API_KEY=sk-ant-...

# Segurança da API
API_SECRET_KEY=<chave-secreta-para-X-API-Key>
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000

# Google Drive (coleta de PDFs)
GOOGLE_DRIVE_FOLDER_ID=<folder-id>
```

> O backend **valida no startup** a presença de `SUPABASE_URL`, `SUPABASE_KEY`, `ANTHROPIC_API_KEY` e `API_SECRET_KEY` — sem elas, a aplicação não sobe.

---

## 🚀 Deploy

### Frontend → Netlify
Configurado em [netlify.toml](netlify.toml):
```toml
[build]
  base = "agroia-frontend"
  command = "npm run build"
  publish = "dist"

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```
Defina as variáveis `VITE_*` no painel do Netlify.

### Backend
A API FastAPI pode ser publicada em qualquer host que rode Uvicorn (Railway, Render, Fly.io, VM própria). Garanta que `ALLOWED_ORIGINS` inclua o domínio do frontend e que as variáveis de ambiente estejam configuradas.

---

## 🧩 Particularidades do Portal JSF/RichFaces

O portal de origem usa **JSF/RichFaces**, o que exige cuidados específicos (detalhados em [CLAUDE.md](CLAUDE.md)):

- **Seletores CSS com `:`** — IDs como `form:campo` quebram o CSS padrão; use atributo:
  ```python
  # ERRADO:  page.locator("#form:dataInferiorInputDate")
  # CERTO:   page.locator('[id="form:dataInferiorInputDate"]')
  ```
- **Campos de data** — não usam `page.fill()`; requerem triple-click + `keyboard.type()` + **Tab** (o evento `onchange` só dispara no Tab).
- **IDs de tabelas** (página de detalhe):
  - Itens: `form:tabelaItens`
  - Fornecedores: `form:tabelaFornecedoresParticipantes`
  - Empenhos: `form:tabelaEmpenhosProcCompra`
- **Voltar à lista** — a aba "Lista Licitações" não é `<a>`, é um RichFaces tab:
  ```python
  page.locator('[id="form:abaPesquisa_lbl"]').click()
  ```
- **Paginação** — tratada internamente; **não** tente scriptar a paginação manualmente.

---

## ⚠️ Limitações Conhecidas

1. **Empenhos** — cobertura máxima de ~36%: muitas licitações "Concluído" (especialmente Dispensas) simplesmente não têm empenhos registrados no portal.
2. **Download de PDFs** — parte das licitações não permite download direto; os modais são dinâmicos e exigem o contexto completo do Playwright. A cobertura de documentos foi sendo ampliada incrementalmente via `etapa3_producao.py --resume` e `coleta_criticos.py`.
3. **Cobertura temporal de demanda** — o grosso dos dados de demanda concentra-se em **2019–2023**; quando perguntado sobre 2024–2026, o agente informa explicitamente a ausência de dados.
4. **Limite do PostgREST** — consultas sem `ORDER BY` podem ser truncadas em 1.000 linhas; a validação de consistência (`/auditoria/consistencia`) monitora isso.

---

## 🛡 Segurança

- **`.env`, `token.pickle` e credenciais** nunca devem ser commitados (já no `.gitignore`).
- **API protegida** por `X-API-Key` e CORS restrito a origens explícitas.
- **Sanitização** de entradas nas tools antes de montar queries.
- **Validação obrigatória** de variáveis de ambiente no startup.

> ⚠️ **Histórico:** o `.env` já foi commitado por engano no passado, acionando revogação automática de chaves. Caso isso ocorra, rotacione as chaves (Supabase + Anthropic) e limpe o histórico do git (`git-filter-repo`).

---

## 🛠 Troubleshooting

| Problema | Solução |
|----------|---------|
| `Missing required env var: ...` no startup | Conferir `.env` (Supabase, Anthropic, `API_SECRET_KEY`) |
| Frontend recebe 403 | `X-API-Key` ausente/errada — verificar `VITE_API_SECRET_KEY` e `API_SECRET_KEY` |
| CORS bloqueado | Adicionar o domínio em `ALLOWED_ORIGINS` |
| Chat retorna vazio | Verificar se `vw_itens_agro` existe e tem dados no Supabase |
| RAG não encontra nada | Rodar a indexação (`python indexar_pdfs.py`) e checar `pdf_chunks` |
| Timeout na coleta | Portal lento/intermitente — retomar com `python etapa3_producao.py --resume` |
| Dashboard sem dados de 2025-26 | Truncagem do PostgREST — usar consultas com `ORDER BY` (corrigido) |

---

## 👤 Autor

**Humberto Campos**
Mestrado em Computação Aplicada — PPGCA/UEPG
✉️ suporte@hai.expert

---

## 📝 Licença

MIT License — consulte o arquivo `LICENSE` (se presente) para detalhes.

---

## 🔗 Links Úteis

- [Anthropic Claude API](https://docs.anthropic.com/)
- [Supabase Docs](https://supabase.com/docs) · [pgvector](https://github.com/pgvector/pgvector)
- [FastAPI](https://fastapi.tiangolo.com/) · [Playwright Python](https://playwright.dev/python/)
- [React](https://react.dev/) · [Vite](https://vitejs.dev/) · [Recharts](https://recharts.org/)

---

**Status:** 🟢 Em desenvolvimento ativo · Backend (API + coleta + RAG) e Frontend (React) funcionais.
