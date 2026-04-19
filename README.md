# AgroIA-RMC

**Assistente conversacional alimentado por IA para análise de licitações agrícolas públicas na Região Metropolitana de Curitiba (RMC)**

[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red)](https://streamlit.io/)
[![Claude Haiku](https://img.shields.io/badge/Claude-Haiku%204.5-orange)](https://www.anthropic.com/)

---

## 🌾 Sobre o Projeto

AgroIA-RMC é uma plataforma de pesquisa que integra:

- **Coleta de dados**: Web scraping do portal de licitações de Curitiba (JSF/RichFaces)
- **Análise semântica**: Agente conversacional com Claude Haiku 4.5 + RAG (Retrieval-Augmented Generation)
- **Interface visual**: Dashboard Streamlit com 3 páginas (Chat, Dashboard, Histórico)
- **Exportação**: Relatórios Markdown, CSVs e insights para dissertação

**Escopo**: ~743 itens agrícolas licitados entre 2019-2026 pela SMSAN/FAAC (Curitiba)

---

## 🚀 Começar Rápido

### Pré-requisitos
- Python 3.9+
- Anthropic API key (`ANTHROPIC_API_KEY`)
- Supabase project (banco de dados PostgreSQL)
- Google Drive folder (para PDFs)

### Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/HvcamposHAi/agroia-rmc.git
cd agroia-rmc

# 2. Crie ambiente virtual
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Instale dependências
pip install -r requirements_chat.txt

# 4. Configure variáveis de ambiente
# Crie arquivo .env com:
ANTHROPIC_API_KEY=sk-ant-...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
GOOGLE_DRIVE_FOLDER_ID=your-folder-id
```

### Executar

**Terminal 1 - API FastAPI:**
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 - Interface Streamlit:**
```bash
streamlit run streamlit_app.py
# Abre em http://localhost:8501
```

**Ou execute ambos:**
```bash
# Windows
START_SYSTEM.bat

# Linux/Mac
bash START_SYSTEM.sh  # (criar script se necessário)
```

---

## 📊 Arquitetura

```
agroia-rmc/
├── api/
│   └── main.py                 # FastAPI app (5 endpoints)
├── chat/
│   ├── agent.py                # Claude Haiku loop com tool_use
│   ├── tools.py                # 4 tools SQL + busca vetorial
│   ├── prompts.py              # System prompt
│   └── db.py                   # Cliente Supabase (singleton)
├── streamlit_app.py            # 3 páginas (Chat, Dashboard, Conversas)
├── indexar_pdfs.py             # OCR + embeddings (EasyOCR + Sentence-Transformers)
├── relatorio_dissertacao.py    # Relatório Markdown com tabelas
├── exportar_csv.py             # 3 CSVs para planilhas
├── gerar_insights.py           # Insights com Claude (texto dissertação)
└── requirements_chat.txt       # Dependências
```

---

## 💬 Componentes Principais

### 1. **Agente de Chat (Claude Haiku 4.5)**
Loop agentico com 10 iterações máx + tool_use integrado.

**Tools disponíveis:**
- `query_itens_agro` — buscar itens agrícolas (descrição, valor, cultura)
- `query_fornecedores` — buscar fornecedores e participações
- `query_licitacoes` — buscar processos de licitação
- `buscar_documentos_vetor` — RAG semântico em PDFs (embeddings)

### 2. **API FastAPI (5 endpoints)**

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/health` | GET | Status da API |
| `/chat` | POST | Enviar pergunta, receber resposta com tools |
| `/conversas/{session_id}` | GET | Carregar histórico de conversa |
| `/conversas/{session_id}` | DELETE | Limpar histórico |
| `/docs` | GET | Swagger interactive docs |

**Exemplo:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "pergunta": "Qual é a cultura mais demandada?",
    "session_id": "user-123",
    "historico": []
  }'
```

### 3. **Interface Streamlit (3 páginas)**

#### 💬 Chat
- Campo de input para perguntas
- Histórico visual em bolhas
- Indicador de tools usadas
- Session persistence (carrega histórico anterior)

#### 📊 Dashboard
- Gráfico: Top-10 culturas por valor (bar chart)
- Gráfico: Demanda por ano (line chart)
- Métrica: Valor total

#### 📋 Conversas
- Carrega histórico da sessão
- Botão para limpar histórico
- Exibe todas as mensagens anteriores

### 4. **RAG (Retrieval-Augmented Generation)**

PDFs → OCR (EasyOCR) → Embeddings (Sentence-Transformers 384-dim) → pgvector (Supabase)

```
pdf_chunks table:
  - licitacao_id (FK)
  - processo
  - chunk_text (texto extraído)
  - embedding (vector 384-dim)
  - indexado_em (timestamp)
```

---

## 📈 Dados & Estatísticas

Fonte: `vw_itens_agro` (view SQL)

| Métrica | Valor |
|---------|-------|
| **Itens agrícolas** | 743 |
| **Culturas únicas** | 45+ |
| **Fornecedores** | 326+ |
| **Período** | 2019-2026 |
| **Valor total** | R$ 2.3M+ |

**Top-5 culturas por valor:**
1. Hortaliças (R$ 450k)
2. Frutas (R$ 380k)
3. Grãos (R$ 220k)
4. Proteína animal (R$ 180k)
5. Lácteos (R$ 150k)

---

## 🔧 Scripts de Dissertação

### `relatorio_dissertacao.py`
Gera relatório completo em Markdown.

```bash
python relatorio_dissertacao.py
# Output: RELATORIO_DISSERTACAO.md
```

**Contém:**
- Top-20 culturas por valor (tabela)
- Demanda por canal × ano (tabela)
- Fornecedores principais (tabela)
- Estatísticas gerais

### `exportar_csv.py`
Exporta 3 CSVs prontos para Excel/LaTeX.

```bash
python exportar_csv.py
# Output:
# - culturas_por_valor.csv (63 linhas)
# - demanda_por_ano_canal_categoria.csv (46 linhas)
# - fornecedores_principais.csv (326 linhas)
```

### `gerar_insights.py`
Usa Claude para gerar análise qualitativa dos dados.

```bash
python gerar_insights.py
# Output: INSIGHTS_DISSERTACAO.txt
```

**Contém:**
- Análise de dinâmica de demanda
- Concentração entre canais
- Evolução temporal
- Implicações para políticas agrícolas
- **Pronto para copiar na dissertação**

---

## 🔐 Segurança

- **`.gitignore`** protege: `.env`, `token.pickle`, `SETUP_GOOGLE_DRIVE.md`
- **GitHub Secret Scanning** ativado
- API keys **nunca** commitadas
- Supabase key configurada como "Anon" (row-level security)

---

## 🛠️ Troubleshooting

| Problema | Solução |
|----------|---------|
| `ANTHROPIC_API_KEY not found` | Adicionar em `.env` |
| Streamlit recusa conexão | Verificar se API está rodando em `http://localhost:8000` |
| Histórico não persiste | Executar `criar_tabela_conversas.sql` no Supabase |
| PDFs retornam "Nenhum texto" | OCR falhou; verificar qualidade dos PDFs (imagem vs. texto) |
| Query vazia no chat | Verificar se `vw_itens_agro` existe no Supabase |

---

## 📚 Estrutura de Banco de Dados

**Tabelas principais:**
- `licitacoes` — processos de licitação
- `itens_licitacao` — itens solicitados (7.8k)
- `fornecedores` — empresas fornecedoras (3k+)
- `participacoes` — bids/participações (26k+)
- `conversas` — histórico de chat (criado por `criar_tabela_conversas.sql`)
- `pdf_chunks` — chunks textuais com embeddings (criado por `criar_tabela_pdf_chunks.sql`)

**Views:**
- `vw_itens_agro` — itens classificados como agrícolas (743)
- `vw_demanda_agro_ano` — demanda anual por categoria
- `vw_cobertura_classificacao` — métricas de cobertura

---

## 📖 Documentação Complementar

- `EVOLUCAO_AGENTE.md` — Status de implementação (opções B, C, D, A)
- `CLAUDE.md` — Instruções para Claude Code (coleta de dados, arquitetura portal)
- `START_SYSTEM.bat` — Script de inicialização rápida (Windows)

---

## 👨‍💼 Autor

**Humberto Campos**  
Mestrado em Políticas Públicas - PPGCA/UEPG  
humberto@hai.expert

---

## 📝 Licença

MIT License — veja [LICENSE](LICENSE) para detalhes.

---

## 🔗 Links Úteis

- [Anthropic Claude API](https://docs.anthropic.com/)
- [Supabase Documentation](https://supabase.com/docs)
- [Streamlit Docs](https://docs.streamlit.io/)
- [FastAPI Tutorial](https://fastapi.tiangolo.com/tutorial/)

---

**Status**: 🟢 Pronto para Produção | v1.0 (2026-04-19)
