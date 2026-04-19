# Setup do Agente de Chat RAG — AgroIA-RMC

## Status de Implementação

✓ **Concluído:**
- [x] Módulo `chat/db.py` — conexão Supabase
- [x] Módulo `chat/prompts.py` — system prompt com restrições de escopo
- [x] Módulo `chat/tools.py` — 4 ferramentas SQL (query_itens_agro, query_fornecedores, query_licitacoes, buscar_documentos_vetor)
- [x] Módulo `chat/agent.py` — loop tool_use com Claude Haiku 4.5
- [x] API `api/main.py` — FastAPI com /chat, /health, /docs
- [x] Script `indexar_pdfs.py` — pipeline de indexação vetorial
- [x] SQL `criar_tabela_pdf_chunks.sql` — schema pgvector
- [x] Arquivo `requirements_chat.txt` — dependências instaladas

### Testes Validados

**Tools SQL:**
- ✓ query_itens_agro (por_categoria, por_canal) retornando dados corretos
- ✓ query_fornecedores (tipo=COOPERATIVA) encontrando 16 cooperativas
- ✓ query_licitacoes retornando 50+ licitações
- ✓ Conexão Supabase funcionando

---

## Próximos Passos

### 1. Configurar ANTHROPIC_API_KEY

O agente Claude precisa da API key. Adicione ao `.env`:

```bash
# .env (no diretório raiz do projeto)
ANTHROPIC_API_KEY=sk-ant-...seu-api-key-aqui...
```

Ou exporte no terminal:

```bash
export ANTHROPIC_API_KEY=sk-ant-...seu-api-key-aqui...
```

### 2. Criar tabela pgvector no Supabase

Execute o SQL em `criar_tabela_pdf_chunks.sql` no Supabase SQL Editor:
- URL: https://supabase.com/dashboard
- Projeto: AgroIA-RMC
- SQL Editor → Nova query
- Cole o conteúdo do arquivo e execute

Isto criará:
- Tabela `pdf_chunks` com coluna `embedding vector(384)`
- Índice HNSW para busca vetorial rápida
- Função RPC `buscar_chunks_similares()`

### 3. Testar o agente interativo

Com ANTHROPIC_API_KEY definida:

```bash
cd "c:/Users/hvcam/Meu Drive/Pessoal/Mestrado/Dissertação/agroia-rmc"

python -c "
from chat.agent import chat

# Teste 1: Query de volumes
resultado = chat('Quais culturas têm maior valor total?')
print('Q:', 'Quais culturas têm maior valor total?')
print('R:', resultado['resposta'])
print('Tools:', resultado['tools_usadas'])

# Teste 2: Query de fornecedores
print('\\n---\\n')
resultado = chat('Quais cooperativas participaram em 2023?')
print('Q:', 'Quais cooperativas participaram em 2023?')
print('R:', resultado['resposta'])
"
```

### 4. Iniciar a API FastAPI

```bash
cd "c:/Users/hvcam/Meu Drive/Pessoal/Mestrado/Dissertação/agroia-rmc"
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Acesso:
- **Chat:** POST http://localhost:8000/chat
- **Docs:** http://localhost:8000/docs
- **Health:** http://localhost:8000/health

### 5. Testar endpoint /chat

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "pergunta": "Qual o volume de alface demandado em 2023?",
    "historico": []
  }'
```

Resposta esperada:
```json
{
  "resposta": "Em 2023, foram demandados X kg de alface em Y licitações...",
  "tools_usadas": ["query_itens_agro"],
  "session_id": "abc-123-..."
}
```

### 6. Indexar PDFs (opcional — para RAG completo)

Os PDFs do Google Drive já estão salvos em `documentos_licitacao.url_publica`. Para ativar a busca vetorial em documentos:

```bash
python indexar_pdfs.py
```

Isto:
- Baixa PDFs do Google Drive
- Extrai texto com pdfplumber
- Gera embeddings com paraphrase-multilingual-MiniLM-L12-v2
- Popula tabela `pdf_chunks` no Supabase

Após indexação, a tool `buscar_documentos_vetor` funcionará e o agente poderá responder:
- "O que diz o edital do processo DE 4/2019?"
- "Quais são os requisitos para cooperativas?"

---

## Verificação Rápida de Status

```bash
cd "c:/Users/hvcam/Meu Drive/Pessoal/Mestrado/Dissertação/agroia-rmc"

# 1. Verificar que módulos importam
python -c "from chat.agent import chat; from chat.tools import query_itens_agro; print('✓ Imports OK')"

# 2. Verificar Supabase
python -c "from chat.db import get_supabase_client; sb = get_supabase_client(); print('✓ Supabase OK')"

# 3. Verificar ANTHROPIC_API_KEY
python -c "import os; print('✓ API Key OK' if os.getenv('ANTHROPIC_API_KEY') else '✗ API Key não definida')"

# 4. Testar uma tool
python -c "from chat.tools import query_itens_agro; r = query_itens_agro(agregacao='por_categoria'); print(f'✓ {len(r)} categorias encontradas')"
```

---

## Estrutura Final do Projeto

```
agroia-rmc/
├── .env                           # ADICIONAR: ANTHROPIC_API_KEY
├── criar_tabela_pdf_chunks.sql   # Executar no Supabase
├── requirements_chat.txt
├── indexar_pdfs.py
├── chat/
│   ├── __init__.py
│   ├── db.py
│   ├── prompts.py
│   ├── tools.py
│   └── agent.py
├── api/
│   ├── __init__.py
│   └── main.py
└── SETUP_AGENTE.md               # Este arquivo
```

---

## Troubleshooting

**Erro: "Could not resolve authentication method"**
- Solução: Defina ANTHROPIC_API_KEY no .env ou exporte no terminal

**Erro: "Function buscar_chunks_similares not found"**
- Solução: Execute `criar_tabela_pdf_chunks.sql` no Supabase SQL Editor

**Tool retorna lista vazia**
- Verifique filtros (ano, canal, tipo)
- Confirme que dados existem em vw_itens_agro

**Indexação de PDFs falha**
- Certifique-se que token.pickle existe (criado por etapa3_producao.py)
- PDFs devem estar no Google Drive com url_publica preenchida no Supabase

---

## Próximas Melhorias (Futuro)

- [ ] Persistência de histórico de conversa (session storage)
- [ ] Rate limiting e autenticação API
- [ ] Logging detalhado de queries e respostas
- [ ] Métricas de uso (quantas perguntas, quais tools mais usadas)
- [ ] Cache de embeddings para PDFs (evitar reprocessamento)
- [ ] Interface web (frontend Streamlit ou React)
