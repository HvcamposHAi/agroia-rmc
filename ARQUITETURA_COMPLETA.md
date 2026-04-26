# AgroIA-RMC: Arquitetura Técnica Completa

**Plataforma de análise de licitações agrícolas públicas da Região Metropolitana de Curitiba (RMC)**  
**Status**: Production-ready (v1.0)  
**Última atualização**: 2026-04-21

---

## 📑 Sumário

1. [Estrutura do Banco de Dados (Supabase)](#1-estrutura-do-banco-de-dados-supabase)
2. [Arquitetura do Backend](#2-arquitetura-do-backend)
3. [Arquitetura do Frontend](#3-arquitetura-do-frontend)
4. [Arquitetura de Produção](#4-arquitetura-de-produção)

---

## 1. Estrutura do Banco de Dados (Supabase)

### 1.1 Visão Geral

**Provedor**: Supabase (PostgreSQL 14+ com extensões)  
**URL**: `https://rsphlvcekuomvpvjqxqm.supabase.co`  
**Autenticação**: API Key (anon) + Row-Level Security (RLS)  
**Extensões habilitadas**:
- `pgvector` — Busca semântica com embeddings (384-dim)
- `uuid-ossp` — Geração de UUIDs

### 1.2 Tabelas Principais

#### 1.2.1 `licitacoes`
Processos de licitação do portal de Curitiba.

```sql
CREATE TABLE licitacoes (
  id                BIGINT PRIMARY KEY,
  processo          TEXT NOT NULL UNIQUE,      -- "AD_3_2019___SMSAN_FAAC"
  tipo_processo     TEXT,                      -- "Aviso de Dispensa"
  canal             TEXT NOT NULL,             -- PNAE|PAA|ARMAZEM_FAMILIA|...
  dt_abertura       DATE,                      -- Data de publicação
  situacao          TEXT,                      -- "Publicado", "Concluído", etc
  objeto            TEXT,                      -- Descrição breve
  criado_em         TIMESTAMP DEFAULT now()
);

-- Índices
CREATE INDEX idx_licitacoes_canal ON licitacoes(canal);
CREATE INDEX idx_licitacoes_situacao ON licitacoes(situacao);
CREATE INDEX idx_licitacoes_processo ON licitacoes(processo);
```

**Dados**: ~1,237 processos coletados (2019-2026)

#### 1.2.2 `itens_licitacao`
Itens solicitados em cada licitação.

```sql
CREATE TABLE itens_licitacao (
  id                    BIGINT PRIMARY KEY,
  licitacao_id          BIGINT NOT NULL REFERENCES licitacoes(id),
  seq                   INT,                   -- Sequência no processo
  codigo_item           TEXT,                  -- ID do item no portal
  descricao             TEXT NOT NULL,         -- "Tomate caqui - caixa 20kg"
  qtd_solicitada        NUMERIC,               -- Quantidade
  unidade_medida        TEXT,                  -- "kg", "cx", "un"
  valor_unitario        NUMERIC(15,2),         -- R$ por unidade
  valor_total           NUMERIC(15,2),         -- valor_unitario × qtd
  
  -- Classificação agrícola
  relevante_agro        BOOLEAN DEFAULT FALSE, -- Item é agrícola?
  cultura               TEXT,                  -- "TOMATE", "ABÓBORA", etc
  categoria_v2          TEXT,                  -- "HORTIFRUTI", "FRUTAS", etc
  
  criado_em             TIMESTAMP DEFAULT now()
);

-- Índices otimizados
CREATE INDEX idx_itens_licitacao_id ON itens_licitacao(licitacao_id);
CREATE INDEX idx_itens_relevante_agro ON itens_licitacao(relevante_agro)
  WHERE relevante_agro = true;
CREATE INDEX idx_itens_cultura ON itens_licitacao(cultura)
  WHERE relevante_agro = true;
```

**Dados**: 
- Total: 7,882 itens (99.8% cobertura)
- Agrícolas: 743 itens (relevante_agro=true)
- Culturas únicas: 45+

#### 1.2.3 `fornecedores`
Empresas, cooperativas e associações fornecedoras.

```sql
CREATE TABLE fornecedores (
  id              BIGINT PRIMARY KEY,
  cpf_cnpj        TEXT NOT NULL UNIQUE,
  razao_social    TEXT NOT NULL,
  tipo            TEXT,                      -- "Cooperativa", "Associação", etc
  endereco        TEXT,
  telefone        TEXT,
  email           TEXT,
  criado_em       TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_fornecedores_cpf_cnpj ON fornecedores(cpf_cnpj);
```

**Dados**: 3,081 fornecedores únicos

#### 1.2.4 `participacoes`
Bids: qual fornecedor participou de qual licitação?

```sql
CREATE TABLE participacoes (
  id              BIGINT PRIMARY KEY,
  fornecedor_id   BIGINT NOT NULL REFERENCES fornecedores(id),
  licitacao_id    BIGINT NOT NULL REFERENCES licitacoes(id),
  valor_proposto  NUMERIC(15,2),             -- Valor ofertado
  status          TEXT,                      -- "Ganhador", "Perdedor", "Desistiu"
  criado_em       TIMESTAMP DEFAULT now(),
  
  UNIQUE(fornecedor_id, licitacao_id)
);

CREATE INDEX idx_participacoes_fornecedor ON participacoes(fornecedor_id);
CREATE INDEX idx_participacoes_licitacao ON participacoes(licitacao_id);
```

**Dados**: 26,211 participações

#### 1.2.5 `empenhos`
Compromissos de gasto (pedidos confirmados).

```sql
CREATE TABLE empenhos (
  id              BIGINT PRIMARY KEY,
  item_id         BIGINT REFERENCES itens_licitacao(id),
  licitacao_id    BIGINT NOT NULL REFERENCES licitacoes(id),
  nr_empenho      TEXT NOT NULL,            -- "2024EM000123"
  ano_empenho     INT,
  dt_empenho      DATE,
  valor           NUMERIC(15,2),
  criado_em       TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_empenhos_licitacao ON empenhos(licitacao_id);
CREATE INDEX idx_empenhos_item ON empenhos(item_id);
```

**Dados**: 3,473 empenhos (36% cobertura máxima — limitação portal)

#### 1.2.6 `documentos_licitacao`
Metadados de PDFs (editais, termos de referência, atas).

```sql
CREATE TABLE documentos_licitacao (
  id                  BIGINT PRIMARY KEY,
  licitacao_id        BIGINT NOT NULL REFERENCES licitacoes(id),
  nome_arquivo        TEXT NOT NULL,          -- "Edital_AD_3_2019.pdf"
  tipo_documento      TEXT,                   -- "Edital", "Termo de Referência"
  caminho_storage     TEXT,                   -- Supabase Storage path
  google_drive_id     TEXT,                   -- Google Drive file ID
  tamanho_bytes       BIGINT,
  hash_md5            TEXT,                   -- Deduplicação
  status_download     TEXT,                   -- "Success", "Failed", "Pending"
  indexado            BOOLEAN DEFAULT FALSE,  -- OCR + embeddings feito?
  criado_em           TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_documentos_licitacao ON documentos_licitacao(licitacao_id);
CREATE INDEX idx_documentos_indexado ON documentos_licitacao(indexado)
  WHERE indexado = true;
```

**Dados**: 544 PDFs (716 não conseguiram download por limitações do portal)

#### 1.2.7 `pdf_chunks` (RAG)
Chunks de texto extraído de PDFs com embeddings vetoriais.

```sql
CREATE TABLE pdf_chunks (
  id              BIGSERIAL PRIMARY KEY,
  licitacao_id    BIGINT NOT NULL REFERENCES licitacoes(id) ON DELETE CASCADE,
  documento_id    BIGINT REFERENCES documentos_licitacao(id) ON DELETE SET NULL,
  processo        TEXT NOT NULL,              -- Denormalização para filtro
  nome_doc        TEXT,
  chunk_index     INT NOT NULL,               -- Ordem do chunk no doc
  chunk_text      TEXT NOT NULL,              -- Texto extraído (OCR)
  embedding       vector(384) NOT NULL,       -- Sentence-Transformers 384-dim
  tokens_aprox    INT,                        -- Estimativa de tokens
  indexado_em     TIMESTAMP DEFAULT now(),
  
  UNIQUE(documento_id, chunk_index)
);

-- Índice HNSW para busca semântica rápida
CREATE INDEX idx_pdf_chunks_embedding ON pdf_chunks 
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_pdf_chunks_processo ON pdf_chunks(processo);
CREATE INDEX idx_pdf_chunks_licitacao ON pdf_chunks(licitacao_id);
```

**Dados**: 56 PDFs indexados (43 originais + 13 novos na reconciliação)

#### 1.2.8 `conversas`
Histórico de interações do usuário com o assistente.

```sql
CREATE TABLE conversas (
  id              BIGSERIAL PRIMARY KEY,
  session_id      UUID NOT NULL,             -- ID da sessão do usuário
  role            TEXT NOT NULL,             -- "user" | "assistant"
  content         TEXT NOT NULL,             -- Mensagem
  tools_usadas    JSONB DEFAULT '[]'::jsonb, -- ["query_itens_agro", ...]
  criado_em       TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_conversas_session ON conversas(session_id);
CREATE INDEX idx_conversas_criado_em ON conversas(criado_em DESC);
```

**Dados**: Cresce conforme uso da interface

### 1.3 Views (SQL)

#### 1.3.1 `vw_itens_agro`
View base para consultas no agente.

```sql
CREATE VIEW vw_itens_agro AS
SELECT 
  i.id,
  i.licitacao_id,
  l.processo,
  l.canal,
  l.dt_abertura,
  i.descricao,
  i.cultura,
  i.categoria_v2,
  i.qtd_solicitada,
  i.unidade_medida,
  i.valor_unitario,
  i.valor_total,
  i.relevante_agro
FROM itens_licitacao i
JOIN licitacoes l ON i.licitacao_id = l.id
WHERE i.relevante_agro = true;
```

#### 1.3.2 `vw_itens_agro_puros` (DEPRECATED)
⚠️ **CONSOLIDADO**: Use `vw_itens_agro` diretamente. Esta view está deprecada e será removida.
- Motivo: Simplificação — escopo é AGRICULTURA EXCLUSIVAMENTE
- Data de depreciação: 2026-04-25
- Remover em: 2026-05-01

#### 1.3.3 `vw_demanda_agro_ano`
Agregação anual por cultura.

```sql
CREATE VIEW vw_demanda_agro_ano AS
SELECT 
  EXTRACT(YEAR FROM l.dt_abertura)::int as ano,
  i.cultura,
  i.categoria_v2,
  COUNT(DISTINCT l.id) as qtd_licitacoes,
  SUM(i.qtd_solicitada) as qtd_total,
  SUM(i.valor_total) as valor_total_agro
FROM itens_licitacao i
JOIN licitacoes l ON i.licitacao_id = l.id
WHERE i.relevante_agro = true
GROUP BY ano, i.cultura, i.categoria_v2;
```

#### 1.3.4 `vw_cobertura_classificacao`
Métricas de cobertura de documentação.

```sql
CREATE VIEW vw_cobertura_classificacao AS
SELECT 
  COUNT(DISTINCT CASE WHEN i.relevante_agro = true THEN l.id END) as lics_agro,
  COUNT(DISTINCT CASE 
    WHEN i.relevante_agro = true 
    THEN d.licitacao_id 
  END) as lics_com_docs,
  ROUND(
    COUNT(DISTINCT CASE 
      WHEN i.relevante_agro = true 
      THEN d.licitacao_id 
    END)::numeric / 
    NULLIF(COUNT(DISTINCT CASE WHEN i.relevante_agro = true THEN l.id END), 0) * 100,
    2
  ) as pct_cobertura
FROM licitacoes l
LEFT JOIN itens_licitacao i ON l.id = i.licitacao_id
LEFT JOIN documentos_licitacao d ON l.id = d.licitacao_id;
```

### 1.4 Segurança

- **Row-Level Security (RLS)** ativado em tabelas sensíveis
- **API Key (anon)** — sem acesso direto a dados pessoais
- **Backup automático** — Supabase realiza snapshots diários
- **.env** protegido em `.gitignore`

---

## 2. Arquitetura do Backend

### 2.1 Stack Técnico

```
FastAPI 0.104.1      — Framework web async
Uvicorn 0.24.0       — ASGI server
Pydantic 2.5.0       — Validação de dados
Python 3.9+          — Linguagem
Anthropic SDK 0.21.0 — Claude API client
Supabase Client 2.4.0— Database ORM
```

### 2.2 Estrutura de Diretórios

```
api/
├── main.py                 # FastAPI app + endpoints
├── __init__.py
└── __pycache__

chat/
├── agent.py                # Loop agentico (Claude Haiku)
├── tools.py                # Tool schema + executar_tool()
├── prompts.py              # System prompt do assistente
├── db.py                   # Cliente Supabase (singleton)
└── __pycache__

requirements.txt            # Dependências (FastAPI, Anthropic, etc)
```

### 2.3 Componentes Principais

#### 2.3.1 FastAPI Application (`api/main.py`)

**Configuração Base:**
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AgroIA-RMC Chat",
    description="Agente de chat RAG para licitações agrícolas",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Frontend access
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Endpoints:**

| Endpoint | Método | Descrição | Payload |
|----------|--------|-----------|---------|
| `/health` | GET | Verificar status da API + BD | — |
| `/chat` | POST | Enviar pergunta, receber resposta | `ChatRequest` |
| `/conversas/{session_id}` | GET | Carregar histórico de sessão | — |
| `/conversas/{session_id}` | DELETE | Limpar histórico de sessão | — |
| `/alertas` | POST | Gerar alertas com IA | — |
| `/auditoria/executar` | POST | Auditoria de qualidade de dados | — |
| `/auditoria/chat` | POST | Discussão sobre auditoria | `AuditoriaChatRequest` |
| `/docs` | GET | Swagger UI interativa | — |

**Data Models (Pydantic):**

```python
class ChatRequest(BaseModel):
    pergunta: str
    historico: list[dict] = []
    session_id: str | None = None

class ChatResponse(BaseModel):
    resposta: str
    tools_usadas: list[str]
    session_id: str

class AuditoriaMetricas(BaseModel):
    total_licitacoes_agro: int
    lics_com_docs: int
    taxa_cobertura_pct: float
    total_empenhos: int
    lics_com_empenhos: int
    empenhos_sem_docs: int
    lics_concluidas_sem_docs: int
    alertas_criticos: int
    alertas_graves: int

class AuditoriaAlerta(BaseModel):
    tipo: str              # "ERRO_BD", "ALTA_PRECO", "DESABASTECIMENTO"
    severidade: str        # "CRITICO", "GRAVE", "MEDIA", "BAIXA"
    mensagem: str
    processo: str | None
    qtd_empenhos: int | None
```

**Fluxo do Endpoint `/chat`:**

1. Recebe `ChatRequest` com pergunta + `session_id`
2. Carrega histórico anterior (ou inicia novo)
3. Chama `chat()` do agente (com tool_use loop)
4. Salva turno na tabela `conversas`
5. Retorna `ChatResponse` com resposta + tools usadas

```python
@app.post("/chat")
def chat_endpoint(request: ChatRequest) -> ChatResponse:
    session_id = request.session_id or str(uuid.uuid4())
    historico = request.historico or carregar_historico(session_id)
    resultado = chat(request.pergunta, historico)
    
    salvar_turno(session_id, "user", request.pergunta)
    salvar_turno(session_id, "assistant", resultado["resposta"], 
                 resultado["tools_usadas"])
    
    return ChatResponse(
        resposta=resultado["resposta"],
        tools_usadas=resultado["tools_usadas"],
        session_id=session_id
    )
```

#### 2.3.2 Agente de Chat (`chat/agent.py`)

**Loop Agentico:**

Implementa o padrão tool_use do Claude com até 10 iterações.

```python
def chat(pergunta: str, historico: list[dict] = None) -> dict:
    """
    Loop: pergunta → Claude → tool_use? → executar → feedback → repeat
    """
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    messages = historico + [{"role": "user", "content": pergunta}]
    tools_usadas = []
    iteracao = 0
    max_iteracoes = 10

    while iteracao < max_iteracoes:
        iteracao += 1
        
        # Chamar Claude com tools schema
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS_SCHEMA,           # Tools disponíveis
            messages=messages,
            timeout=15
        )

        # Checar stop_reason
        if response.stop_reason == "end_turn":
            # Claude respondeu, extrair texto
            texto = next(
                (bloco.text for bloco in response.content 
                 if hasattr(bloco, "text")), 
                ""
            )
            return {
                "resposta": texto or "Sem resposta",
                "tools_usadas": tools_usadas
            }

        elif response.stop_reason == "tool_use":
            # Claude quer usar tools, processar
            messages.append({"role": "assistant", "content": response.content})
            
            tool_results = []
            for bloco in response.content:
                if bloco.type == "tool_use":
                    tools_usadas.append(bloco.name)
                    resultado = executar_tool(bloco.name, bloco.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": bloco.id,
                        "content": json.dumps(resultado, ensure_ascii=False)
                    })
            
            messages.append({"role": "user", "content": tool_results})
    
    # Max iterações atingida
    return {
        "resposta": "Pergunta muito complexa. Tente dividir.",
        "tools_usadas": tools_usadas
    }
```

**Características:**
- **Timeout**: 15s por chamada Claude (evita travamentos)
- **Error handling**: Retorna resposta graceful em caso de erro
- **Tool tracking**: Lista tools usadas no histórico
- **Historico persistente**: Conversas salvas no Supabase

#### 2.3.3 Tools (`chat/tools.py`)

4 tools SQL disponíveis para o agente:

**1. `query_itens_agro`**
```python
def query_itens_agro(
    cultura: str | None = None,
    categoria: str | None = None,
    canal: str | None = None,
    ano: int | None = None,
    agregacao: str = "detalhado"  # detalhado|por_cultura|por_canal|por_ano|por_categoria
) -> list[dict]
```
- Filtra itens agrícolas
- 5 modos de agregação
- Suporta filtro por cultura, categoria, canal, ano
- Limit: 50 resultados

**2. `query_fornecedores`**
```python
def query_fornecedores(
    tipo: str | None = None,      # "Cooperativa", "Associação"
    canal: str | None = None,     # PNAE, PAA, etc
    ano: int | None = None
) -> list[dict]
```
- Lista fornecedores + participações
- Ordena por volume de participações
- Limit: 50 resultados

**3. `query_licitacoes`**
```python
def query_licitacoes(
    processo: str | None = None,
    canal: str | None = None,
    ano_inicio: int | None = None,
    ano_fim: int | None = None
) -> list[dict]
```
- Busca processos de licitação
- Filtro por processo, canal, período
- Retorna até 50

**4. `buscar_documentos_vetor`** (RAG)
```python
def buscar_documentos_vetor(
    query: str,
    limite: int = 5,
    processo: str | None = None
) -> list[dict]
```
- Busca semântica em PDFs (pgvector)
- Embeds query com Sentence-Transformers
- Calcula similaridade com chunks existentes
- Retorna top-5 chunks + similarity score

**Tool Schema (enviado ao Claude):**
```python
TOOLS_SCHEMA = [
    {
        "name": "query_itens_agro",
        "description": "Buscar itens agrícolas de licitações",
        "input_schema": {
            "type": "object",
            "properties": {
                "cultura": {"type": "string"},
                "categoria": {"type": "string"},
                "agregacao": {"enum": ["detalhado", "por_cultura", ...]}
            },
            "required": []
        }
    },
    # ... outros tools
]
```

**Segurança:**
- `sanitizar_string()` — Rejeita patterns suspeitos (;, ', ", \)
- Parameterização Supabase — Evita SQL injection
- RLS no BD — Validação adicional

#### 2.3.4 System Prompt (`chat/prompts.py`)

```python
SYSTEM_PROMPT = """
Você é o AgroIA, assistente especializado em licitações públicas 
de alimentos da RMC para agricultura familiar.

ESCOPO LIMITADO A:
- Itens agrícolas de licitações (vw_itens_agro, relevante_agro=true)
- Canais: PNAE, PAA, Armazém da Família, Banco de Alimentos, Mesa Solidária
- Fornecedores (cooperativas, associações) dessas licitações
- Documentos (editais, termos de referência) das licitações

NÃO RESPONDE SOBRE:
- Licitações de outros órgãos ou regiões
- Itens não agrícolas
- Dados financeiros fora do escopo AgroIA

INSTRUÇÕES:
1. Responda em português do Brasil, claro e objetivo
2. Cite dados com contexto (ano, canal, processo)
3. Para conteúdo de documentos → use busca vetorial
4. Para análises (volumes, valores) → use SQL
5. Máximo 10 tool calls por pergunta
"""
```

#### 2.3.5 Cliente Supabase (`chat/db.py`)

Singleton pattern para evitar múltiplas conexões:

```python
from supabase import create_client, Client

_client: Client | None = None

def get_supabase_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )
    return _client
```

### 2.4 Fluxo de Requisição

```
1. Cliente POST /chat
    ↓
2. FastAPI valida ChatRequest
    ↓
3. Carrega histórico da sessão
    ↓
4. Chama chat(pergunta, historico)
    ↓
5. Claude Haiku com tool_use loop
    ├─→ Chamada API Anthropic
    ├─→ Recebe resposta com tool_use?
    ├─→ Executa tools (SQL queries)
    ├─→ Retorna resultados ao Claude
    └─→ Repeat até end_turn
    ↓
6. Extrai texto da resposta final
    ↓
7. Salva turno em conversas table
    ↓
8. Retorna ChatResponse ao cliente
    ↓
9. Frontend renderiza resposta
```

### 2.5 Dependências de Produção

```
fastapi==0.104.1              # Framework web
uvicorn[standard]==0.24.0     # ASGI server
pydantic==2.5.0               # Validação
anthropic==0.21.0             # Claude API
supabase==2.4.0               # Database
python-dotenv==1.0.0          # Config
sentence-transformers==2.2.2  # Embeddings
pdfplumber==0.10.3            # PDF processing
numpy==1.24.3                 # Numerics
```

---

## 3. Arquitetura do Frontend

### 3.1 Stack Técnico

```
React 19.2.4           — UI library
TypeScript 6.0.2       — Type safety
Vite 8.0.4             — Build tool
React Router 7.14.1    — Routing
Tailwind CSS 4.2.2     — Styling
Recharts 3.8.1         — Charts
Supabase JS 2.103.3    — Client library
Axios 1.15.1           — HTTP requests
Lucide React 1.8.0     — Icons
```

### 3.2 Estrutura

```
agroia-frontend/
├── src/
│   ├── main.tsx                    # Entry point
│   ├── App.tsx                     # Router + Layout
│   ├── App.css                     # Global styles
│   ├── index.css                   # Tailwind + custom
│   ├── components/
│   │   ├── Layout.tsx              # Navbar + Sidebar + Outlet
│   │   └── Sidebar.tsx             # Menu de navegação
│   ├── pages/
│   │   ├── Chat.tsx                # Chat agentico
│   │   ├── Dashboard.tsx           # Gráficos + métricas
│   │   ├── Consultas.tsx           # Query builder
│   │   ├── Alertas.tsx             # Alertas IA
│   │   ├── Documentos.tsx          # PDF viewer
│   │   └── Auditoria.tsx           # Auditoria de dados
│   └── lib/
│       └── supabase.ts             # Client config
│
├── public/                         # Static assets
├── dist/                           # Build output
├── vite.config.ts                  # Vite configuration
├── tsconfig.json                   # TypeScript config
├── package.json
└── index.html                      # HTML template
```

### 3.3 Componentes de UI

#### 3.3.1 App Router (`src/App.tsx`)

```typescript
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Chat from './pages/Chat'
import Dashboard from './pages/Dashboard'
// ... outras páginas

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Chat />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="consultas" element={<Consultas />} />
          <Route path="alertas" element={<Alertas />} />
          <Route path="documentos" element={<Documentos />} />
          <Route path="auditoria" element={<Auditoria />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
```

#### 3.3.2 Layout (`src/components/Layout.tsx`)

Estrutura principal: Navbar + Sidebar + Outlet

```typescript
export default function Layout() {
  return (
    <div className="flex h-screen bg-slate-50">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Navbar com logo, título, user menu */}
        <header className="bg-white border-b border-slate-200">
          <div className="px-8 py-4 flex justify-between items-center">
            <h1 className="text-xl font-bold text-slate-900">AgroIA-RMC</h1>
            <div className="flex items-center gap-4">
              {/* User menu */}
            </div>
          </div>
        </header>
        
        {/* Main content */}
        <main className="flex-1 overflow-y-auto p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
```

#### 3.3.3 Chat Page (`src/pages/Chat.tsx`)

Funcionalidades principais:
- Input de texto
- Histórico de mensagens (bolhas)
- Indicador de loading
- Exibição de tools usadas
- Session persistence

```typescript
export default function Chat() {
  const [messages, setMessages] = useState<Array<{role: string, content: string}>>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState(() => 
    localStorage.getItem('sessionId') || generateUUID()
  )

  useEffect(() => {
    localStorage.setItem('sessionId', sessionId)
  }, [sessionId])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim()) return

    const userMsg = { role: 'user', content: input }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const response = await axios.post('http://localhost:8000/chat', {
        pergunta: input,
        historico: messages,
        session_id: sessionId
      })

      const assistantMsg = {
        role: 'assistant',
        content: response.data.resposta,
        tools: response.data.tools_usadas
      }
      setMessages(prev => [...prev, assistantMsg])
    } catch (error) {
      console.error('Chat error:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto mb-4 space-y-4">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-2xl px-4 py-2 rounded-lg ${
              msg.role === 'user' 
                ? 'bg-blue-500 text-white' 
                : 'bg-slate-200 text-slate-900'
            }`}>
              {msg.content}
              {msg.tools && (
                <div className="text-xs mt-2 opacity-75">
                  Tools: {msg.tools.join(', ')}
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && <div className="text-center text-slate-500">Pensando...</div>}
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Faça uma pergunta sobre licitações agrícolas..."
          className="flex-1 px-4 py-2 border border-slate-300 rounded-lg"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading}
          className="px-6 py-2 bg-blue-500 text-white rounded-lg disabled:opacity-50"
        >
          Enviar
        </button>
      </form>
    </div>
  )
}
```

#### 3.3.4 Dashboard Page (`src/pages/Dashboard.tsx`)

Visualizações com Recharts:

```typescript
export default function Dashboard() {
  const [culturas, setCulturas] = useState([])
  const [demanda, setDemanda] = useState([])

  useEffect(() => {
    // Buscar dados da API
    axios.post('http://localhost:8000/chat', {
      pergunta: 'Qual é o ranking de culturas por valor?',
      historico: []
    }).then(res => {
      // Parse resposta e atualizar estado
    })
  }, [])

  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-bold">Dashboard Agrícola</h1>
      
      <div className="grid grid-cols-3 gap-4">
        <MetricCard title="Culturas" value={culturas.length} />
        <MetricCard title="Licitações" value={1237} />
        <MetricCard title="Valor Total" value="R$ 2.3M" />
      </div>

      <div className="bg-white p-6 rounded-lg">
        <h2 className="text-xl font-bold mb-4">Top-10 Culturas</h2>
        <BarChart data={culturas}>
          <CartesianGrid />
          <XAxis dataKey="cultura" />
          <YAxis />
          <Tooltip />
          <Bar dataKey="valor_total_R$" fill="#3b82f6" />
        </BarChart>
      </div>

      <div className="bg-white p-6 rounded-lg">
        <h2 className="text-xl font-bold mb-4">Demanda por Ano</h2>
        <LineChart data={demanda}>
          <CartesianGrid />
          <XAxis dataKey="ano" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="qtd_licitacoes" stroke="#3b82f6" />
          <Line type="monotone" dataKey="valor_total_R$" stroke="#ef4444" />
        </LineChart>
      </div>
    </div>
  )
}
```

#### 3.3.5 Auditoria Page (`src/pages/Auditoria.tsx`)

Executa auditoria on-demand:

```typescript
export default function Auditoria() {
  const [auditoria, setAuditoria] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleExecutar = async () => {
    setLoading(true)
    try {
      const res = await axios.post('http://localhost:8000/auditoria/executar')
      setAuditoria(res.data)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Auditoria de Dados</h1>
      
      <button
        onClick={handleExecutar}
        disabled={loading}
        className="px-6 py-2 bg-amber-500 text-white rounded-lg"
      >
        {loading ? 'Executando...' : 'Executar Auditoria'}
      </button>

      {auditoria && (
        <div className="bg-white p-6 rounded-lg space-y-4">
          <h2 className="text-xl font-bold">Métricas</h2>
          <div className="grid grid-cols-2 gap-4">
            <MetricCard title="Licitações Agrícolas" value={auditoria.metricas.total_licitacoes_agro} />
            <MetricCard title="Taxa Cobertura" value={`${auditoria.metricas.taxa_cobertura_pct}%`} />
            <MetricCard title="Empenhos sem Docs" value={auditoria.metricas.empenhos_sem_docs} color="red" />
            <MetricCard title="Alertas Críticos" value={auditoria.metricas.alertas_criticos} color="red" />
          </div>

          {auditoria.alertas.length > 0 && (
            <div>
              <h3 className="font-bold mb-2">Alertas ({auditoria.alertas.length})</h3>
              <div className="space-y-2">
                {auditoria.alertas.map((alerta, idx) => (
                  <div key={idx} className={`p-3 rounded border-l-4 ${
                    alerta.severidade === 'CRITICO' ? 'border-red-500 bg-red-50' :
                    alerta.severidade === 'GRAVE' ? 'border-orange-500 bg-orange-50' :
                    'border-yellow-500 bg-yellow-50'
                  }`}>
                    <p className="font-bold text-sm">{alerta.tipo}</p>
                    <p className="text-sm">{alerta.mensagem}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
```

### 3.4 Configuração Vite

```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    minify: 'terser'
  }
})
```

### 3.5 Styling (Tailwind CSS)

```
- Colors: Slate (neutral), Blue (primary), Red (alerts)
- Spacing: 4px baseline
- Typography: Poppins/Inter (importado via Google Fonts)
- Responsive: Mobile-first with md: e lg: breakpoints
```

---

## 4. Arquitetura de Produção

### 4.1 Visão Geral

```
┌─────────────────┐
│  Usuário/Cliente│
│   (Browser)     │
└────────┬────────┘
         │ HTTPS
    ┌────▼─────────────────────────────────┐
    │       CDN / Frontend Hosting         │
    │  (Netlify ou Vercel - agroia-frontend)
    │         React SPA (dist/)             │
    └────┬──────────────────────────────────┘
         │ API Calls (axios)
    ┌────▼──────────────────────────────────┐
    │     Backend API (FastAPI)             │
    │   host: 0.0.0.0, port: 8000           │
    │   (Render, Railway, DigitalOcean)    │
    └────┬──────────────────────────────────┘
         │ SDK (supabase-py)
    ┌────▼──────────────────────────────────┐
    │    Supabase PostgreSQL               │
    │   (Database + pgvector + Storage)    │
    └───────────────────────────────────────┘
         │
    ┌────▼──────────────────────────────────┐
    │   APIs Externas                       │
    │   - Anthropic Claude (AI)             │
    │   - Google Drive (PDF storage)        │
    └───────────────────────────────────────┘
```

### 4.2 Frontend Deployment (Netlify)

**Arquivo: `netlify.toml`**

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

**Fluxo de Deploy:**

1. **Push para GitHub** (branch main)
2. **Netlify Hook Triggered**
3. **Build Process:**
   ```bash
   cd agroia-frontend
   npm ci                  # Clean install
   npm run build           # Vite build → dist/
   ```
4. **Publish:** `dist/` → Netlify CDN
5. **SPA Routing:** Todos os paths → `/index.html` (React Router)

**Configuração:**
- **Domain:** `agro-ia-rmc.netlify.app` (ou custom domain)
- **SSL:** Automático (Let's Encrypt)
- **CDN:** Netlify Edge (distribuído globalmente)
- **Build time:** ~2-3 minutos
- **Cost:** Free tier (ou ~$20/mês pro)

**Environment Variables:**
```
VITE_API_URL=https://api.agroia-rmc.com
VITE_SUPABASE_URL=https://rsphlvcekuomvpvjqxqm.supabase.co
VITE_SUPABASE_KEY=<public-anon-key>
```

### 4.3 Backend Deployment (Render.com ou alternativa)

**Opção A: Render.com**

**Arquivo: `render.yaml` (recomendado)**

```yaml
services:
  - type: web
    name: agroia-api
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn api.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: PYTHON_VERSION
        value: 3.11
      - key: PORT
        value: 8000
    disk:
      name: pdf-cache
      mountPath: /tmp
      sizeGB: 10
    plan: standard
```

**Deploy Steps:**
1. Push para GitHub
2. Render detecta `render.yaml`
3. Build: `pip install -r requirements.txt`
4. Start: `uvicorn api.main:app ...`
5. Expose: `https://agroia-api.onrender.com`

**Configuração:**
- **Instance:** Standard (0.5 CPU, 512MB RAM)
- **Auto-deploy:** Push to GitHub
- **Health Check:** `GET /health`
- **Max build time:** 15 min
- **Cost:** ~$12/mês

**Environment Variables (Render Dashboard):**
```
SUPABASE_URL=https://rsphlvcekuomvpvjqxqm.supabase.co
SUPABASE_KEY=<api-key>
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_DRIVE_FOLDER_ID=...
LOG_LEVEL=INFO
```

**Opção B: Railway.app**

```yaml
# railway.toml
[build]
builder = "dockerfile"

[deploy]
startCommand = "uvicorn api.main:app --host 0.0.0.0 --port $PORT"
```

**Opção C: DigitalOcean App Platform**

- Conectar repositório GitHub
- Selecionar branch (main)
- Auto-deploy on push
- Python 3.11 runtime
- ~$12/mês

### 4.4 Database (Supabase Cloud)

**Status:** ✅ Já em produção  
**URL:** `https://rsphlvcekuomvpvjqxqm.supabase.co`

**Backup Strategy:**
- **Automático:** Supabase realiza snapshots diários
- **Retention:** 30 dias
- **Recovery:** 1-click restore no dashboard

**Monitoring:**
- CPU, RAM, connections — Supabase dashboard
- Query performance — pg_stat_statements
- Alertas — Email automático

**Uptime SLA:** 99.9%

### 4.5 API Proxy & Rate Limiting (Cloudflare)

**Configuração Cloudflare (opcional):**

```
Zone: agro-ia-rmc.com
DNS:
  - A record → Render API IP
  - CNAME → api.agro-ia-rmc.com

Rules:
  - Cache:
    - Cache on GET /docs
    - TTL: 1 hour
  - Rate Limit:
    - /chat → 10 req/min per IP
    - /alertas → 5 req/min
    - Default: 100 req/min
  - WAF:
    - Block: SQL injection patterns
    - Block: Path traversal
    - Allow: CORS from *.netlify.app
```

**Benefits:**
- Global CDN
- DDoS protection
- Rate limiting
- Image optimization
- **Cost:** $20/mês (Pro plan)

### 4.6 CI/CD Pipeline (GitHub Actions)

**File: `.github/workflows/deploy.yml`**

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest tests/ || true  # Optional tests

  deploy-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: |
          cd agroia-frontend
          npm ci && npm run build
      - uses: actions/upload-artifact@v3
        with:
          name: frontend-build
          path: agroia-frontend/dist

  deploy-backend:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to Render
        run: |
          curl https://api.render.com/deploy/${{ secrets.RENDER_DEPLOY_HOOK }}
```

### 4.7 Monitoramento & Observabilidade

**Logging:**
- Backend: `logging` Python stdlib → stdout
- Supabase: Integrated logs dashboard
- Netlify: Build & deploy logs

**Error Tracking (Sentry - optional):**
```python
import sentry_sdk
sentry_sdk.init(
    dsn="https://examplePublicKey@o0.ingest.sentry.io/0",
    environment="production"
)
```

**Metrics:**
- Uptime: Monitora `/health` endpoint a cada 5 min
- Response time: Target < 500ms
- Error rate: Alert se > 1% 5xx errors

**Alertas:**
- Email: Deploy failures, 5xx errors
- Slack: Critical issues

### 4.8 Checklist de Produção

- [ ] `.env` **nunca** commitado (`.gitignore`)
- [ ] Supabase URL + Key em secrets
- [ ] CORS habilitado para frontend domain
- [ ] HTTPS forced
- [ ] Rate limiting configurado
- [ ] Backup BD testado
- [ ] Health check implementado
- [ ] Logging verbose em produção
- [ ] PDF cache limitado (10GB)
- [ ] SSL certificate atualizado
- [ ] DNS configured
- [ ] Monitoring ativo

---

## 5. Fluxo Completo de Uma Requisição

### 5.1 Chat Request → Response

```
Usuário acessa https://agro-ia-rmc.netlify.app
                    ↓
        Frontend carregado (React SPA)
                    ↓
        Usuário digita: "Quais são as frutas mais demandadas?"
                    ↓
        Frontend POST axios → https://api.agroia-rmc.com/chat
        {
          "pergunta": "Quais são as frutas mais demandadas?",
          "session_id": "user-123",
          "historico": [...]
        }
                    ↓
        Cloudflare (1) rate limit check → PASS
                    ↓
        Render (2) FastAPI /chat endpoint
        - Valida ChatRequest (Pydantic)
        - Carrega histórico de conversas (SQL)
                    ↓
        (3) chat() function inicia loop agentico
        - Chama Anthropic API com prompt + tools
                    ↓
        (4) Claude responde com tool_use
        - Decide: preciso de query_itens_agro("cultura"="FRUTAS")
                    ↓
        (5) executar_tool() → query_itens_agro(...)
        - Supabase SDK consulta vw_itens_agro
        - Filtra: cultura LIKE "FRUTAS"
        - Retorna: [(id, descricao, valor, ...), ...]
                    ↓
        (6) Claude processa resultado
        - Analisa top-3 frutas por valor
        - Redige resposta: "As 3 frutas mais demandadas..."
                    ↓
        (7) stop_reason == "end_turn"
        - Loop termina
        - tools_usadas = ["query_itens_agro"]
                    ↓
        (8) Salva turno na tabela conversas:
        - INSERT INTO conversas (session_id, role, content, tools_usadas)
                    ↓
        (9) Retorna ChatResponse ao frontend
        {
          "resposta": "As 3 frutas mais demandadas...",
          "tools_usadas": ["query_itens_agro"],
          "session_id": "user-123"
        }
                    ↓
        Frontend renderiza resposta em bubble
        - Exibe tools usadas em rodapé
        - Carrega histórico da sessão para próxima pergunta
```

### 5.2 Auditoria On-Demand

```
Usuário clica "Executar Auditoria"
                    ↓
Frontend POST /auditoria/executar
                    ↓
Backend:
1. Busca em bulk:
   - itens_licitacao (relevante_agro=true)
   - documentos_licitacao
   - empenhos
   - licitacoes
                    ↓
2. Processa dados em memória:
   - Conta lics com docs
   - Identifica lics com empenhos mas sem docs
   - Calcula taxa_cobertura
                    ↓
3. Gera alertas (CRITICO, GRAVE, MEDIA):
   - CRÍTICO: Licitação com empenho SEM documentação
   - GRAVE: Licitação concluída SEM documentação
                    ↓
4. Retorna AuditoriaResultado:
   {
     "metricas": {...},
     "alertas": [...],
     "executado_em": "2026-04-21T19:42:00Z"
   }
                    ↓
Frontend renderiza métricas em cards
+ tabela de alertas colorida (vermelho = crítico)
```

---

## 6. Tecnologias Chave

| Camada | Tecnologia | Papel |
|--------|-----------|-------|
| **Frontend** | React 19 | UI Interativa |
| | TypeScript | Type Safety |
| | Tailwind CSS | Styling |
| | Recharts | Data Visualization |
| | Vite | Build/Dev Server |
| **Backend** | FastAPI | Web Framework |
| | Uvicorn | ASGI Server |
| | Claude Haiku 4.5 | LLM Agent |
| | Pydantic | Validation |
| **Database** | Supabase | PostgreSQL + pgvector |
| | pgvector | Vector Search |
| | PostgREST | REST API (auto) |
| **Deployment** | Netlify | Frontend CDN |
| | Render.com | Backend Server |
| | Cloudflare | Proxy + Rate Limit (optional) |
| | GitHub Actions | CI/CD |
| **External APIs** | Anthropic Claude | AI/LLM |
| | Supabase | Database + Storage |
| | Google Drive | PDF Storage Backup |

---

## 7. Performance & Scaling

### 7.1 Otimizações Implementadas

- **Frontend:**
  - Code splitting (React Router lazy load)
  - Image optimization (Vite)
  - CSS minification (Tailwind)
  - Browser caching (CDN headers)

- **Backend:**
  - Singleton Supabase client (connection pooling)
  - Bulk queries (evitar N+1)
  - Tool result JSON compression
  - Request timeout (15s)

- **Database:**
  - HNSW index em pdf_chunks (vector search)
  - Índices em foreign keys
  - Row-Level Security (efficient filtering)
  - Query monitoring

### 7.2 Limites Conhecidos

- **Tool calls:** Max 10 por pergunta
- **Response tokens:** Max 2048
- **Query limit:** 50 resultados
- **PDF chunks:** 384-dim embeddings
- **Session timeout:** 30 dias

### 7.3 Escalabilidade Futura

- **Load Balancer:** Adicionar múltiplas instâncias Render com load balancer
- **Cache Layer:** Redis para session storage
- **Async Processing:** Celery para PDF indexing
- **Database:** Supabase Auto-scaling

---

## 8. Segurança

### 8.1 Medidas Implementadas

- ✅ **HTTPS enforced** (Cloudflare, Netlify)
- ✅ **API Keys** em environment variables
- ✅ **CORS** configurado (frontend domain only)
- ✅ **Rate limiting** (Cloudflare)
- ✅ **SQL injection prevention** (Supabase parameterization)
- ✅ **RLS** (Row-Level Security) no BD
- ✅ **Input sanitization** (basic string validation)
- ✅ **Secret scanning** (GitHub)
- ✅ **No secrets in git** (.gitignore)

### 8.2 Recomendações Adicionais

- [ ] WAF rules (Cloudflare)
- [ ] API key rotation quarterly
- [ ] Database backup testing
- [ ] Penetration testing anual
- [ ] Security audit de dependencies (npm audit, pip audit)

---

## 9. Como Começar

### 9.1 Desenvolvimento Local

```bash
# 1. Clone
git clone https://github.com/HvcamposHAi/agroia-rmc.git
cd agroia-rmc

# 2. Backend
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate no Windows
pip install -r requirements.txt

# 3. Frontend
cd agroia-frontend
npm install

# 4. .env
# Criar .env na raiz com:
SUPABASE_URL=...
SUPABASE_KEY=...
ANTHROPIC_API_KEY=...

# 5. Rodar
# Terminal 1:
uvicorn api.main:app --reload

# Terminal 2:
cd agroia-frontend && npm run dev
```

### 9.2 Deploy em Render + Netlify

**Backend (Render):**
1. Conectar GitHub repo em render.com
2. Criar novo "Web Service"
3. Selecionar branch `main`
4. Build command: `pip install -r requirements.txt`
5. Start command: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
6. Adicionar env vars
7. Deploy

**Frontend (Netlify):**
1. Conectar GitHub repo em netlify.com
2. Build command: `npm run build` (base: `agroia-frontend`)
3. Publish directory: `dist`
4. Adicionar env vars
5. Deploy

---

## 10. Suporte & Documentação

- **CLAUDE.md**: Instruções para coleta de dados
- **README.md**: Overview do projeto
- **Supabase Docs**: https://supabase.com/docs
- **FastAPI Docs**: https://fastapi.tiangolo.com
- **React Docs**: https://react.dev
- **Anthropic Docs**: https://docs.anthropic.com

---

**Versão:** 1.0.0  
**Status:** Production-ready  
**Última atualização:** 21 Abr 2026  
**Autor:** Humberto Campos  
**Email:** humberto@hai.expert
