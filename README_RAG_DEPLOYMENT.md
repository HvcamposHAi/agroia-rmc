# AgroIA RAG System - Guia de Deployment

**Status:** ✅ Production Ready  
**Data:** 2026-04-26  
**Versão:** 1.0

---

## 📋 Visão Geral

Sistema de **Retrieval-Augmented Generation (RAG)** para busca semântica em documentos agrícolas da Região Metropolitana de Curitiba (RMC).

### Componentes

| Componente | Status | Descrição |
|-----------|--------|-----------|
| **Indexação** | ✅ Completa | 216 chunks com embeddings 384-dim |
| **Embeddings** | ✅ Ativo | SentenceTransformer (multilingual) |
| **Banco de dados** | ✅ Ativo | Supabase + pgvector |
| **API RAG** | ✅ Pronto | FastAPI + endpoints |
| **Teste** | ✅ Passou | Busca semântica validada |

---

## 🚀 Quick Start

### 1. Pré-requisitos

```bash
# Instalar dependências (se não tiver)
pip install fastapi uvicorn sentence-transformers numpy supabase-py python-dotenv

# Verificar .env
cat .env
# Deve ter: SUPABASE_URL, SUPABASE_KEY, ANTHROPIC_API_KEY
```

### 2. Iniciar API RAG

```bash
# Terminal 1: Rodar servidor FastAPI
python chat/api_rag.py
# ou
uvicorn chat.api_rag:app --reload --port 8000
```

API estará em: `http://localhost:8000`

### 3. Testar Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Estatísticas
curl http://localhost:8000/rag/stats

# Busca semântica
curl -X POST http://localhost:8000/rag/buscar \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Leite para merenda escolar",
    "top_k": 5,
    "min_similarity": 0.3
  }'
```

### 4. Ver documentação interativa

Acesse: `http://localhost:8000/docs` (Swagger UI)

---

## 📊 API Endpoints

### POST `/rag/buscar`

**Busca semântica em documentos agrícolas**

#### Request
```json
{
  "query": "Leite fresco para merenda escolar",
  "top_k": 5,
  "min_similarity": 0.3
}
```

#### Response
```json
{
  "query": "Leite fresco para merenda escolar",
  "total_resultados": 5,
  "chunks": [
    {
      "id": 123,
      "documento_id": 45,
      "nome_doc": "PROCESSO_LICITATORIO.pdf",
      "processo": "PE 6/2021",
      "chunk_text": "[Página 2] LEITE FRESCO... 10.000 litros...",
      "similaridade": 0.856,
      "chunk_index": 2
    }
  ],
  "tempo_processamento_ms": 145.3
}
```

### GET `/rag/stats`

**Retorna estatísticas do sistema RAG**

```json
{
  "total_chunks": 216,
  "chunks_com_embeddings": 216,
  "documentos_unicos": 161,
  "cobertura_embeddings": 100.0,
  "modelo": "paraphrase-multilingual-MiniLM-L12-v2",
  "dimensao_embedding": 384,
  "status": "operacional"
}
```

### GET `/health`

Verifica se a API está rodando.

---

## 🔧 Integração com Chat

### Exemplo: Usar RAG no Chat

```python
from chat.api_rag import buscar_rag, BuscaRAGRequest

# Usuário faz pergunta
user_query = "Quais produtos lácteos foram licitados?"

# Buscar contexto via RAG
request = BuscaRAGRequest(query=user_query, top_k=5)
rag_result = buscar_rag(request)

# Usar chunks como contexto para LLM
contexto = "\n".join([c.chunk_text for c in rag_result.chunks])

# Enviar para Claude/LLM com contexto
prompt = f"""
Contexto (documentos relevantes):
{contexto}

Pergunta do usuário: {user_query}

Responda com base no contexto acima.
"""
```

---

## 📈 Performance

| Operação | Tempo | Limites |
|----------|-------|---------|
| Geração de embedding | ~20ms | até 1000 textos/s |
| Busca em 500 chunks | ~145ms | top_k=5 |
| Leitura do banco | ~174ms | até 500 chunks |
| **Total por busca** | **~150-200ms** | Aceitável |

---

## 🔒 Segurança

### Validações

- ✅ Query mínimo 3 caracteres
- ✅ top_k limitado a 1-50
- ✅ min_similarity entre 0-1
- ✅ Tratamento de exceções
- ✅ Erro handling gracioso

### Recomendações

- [ ] Adicionar rate limiting (FastAPI-limiter)
- [ ] Autenticação de API key
- [ ] Logging estruturado
- [ ] Monitoring de uso

---

## 📦 Deployment em Produção

### Opção 1: Heroku

```bash
# Criar Procfile
echo "web: uvicorn chat.api_rag:app --host 0.0.0.0 --port \$PORT" > Procfile

# Deploy
git add .
git commit -m "Deploy RAG API"
git push heroku main
```

### Opção 2: Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "chat.api_rag:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
# Build and run
docker build -t agroia-rag .
docker run -e SUPABASE_URL=... -e SUPABASE_KEY=... -p 8000:8000 agroia-rag
```

### Opção 3: Vercel/FastAPI (Serverless)

```bash
# Criar vercel.json
cat > vercel.json << EOF
{
  "builds": [{"src": "chat/api_rag.py", "use": "@vercel/python"}],
  "routes": [{"src": "/(.*)", "dest": "chat/api_rag.py"}]
}
EOF

# Deploy
vercel
```

---

## 🧪 Testes

### Executar testes de RAG

```bash
python teste_busca_rag.py
```

Validações incluídas:
- ✅ Embeddings armazenados
- ✅ Busca por similaridade
- ✅ Performance
- ✅ Integridade dos dados

### Testar com dados reais

```bash
# Query 1: Produtos lácteos
curl -X POST http://localhost:8000/rag/buscar \
  -H "Content-Type: application/json" \
  -d '{"query":"Leite queijo manteiga","top_k":5}'

# Query 2: Hortaliças
curl -X POST http://localhost:8000/rag/buscar \
  -H "Content-Type: application/json" \
  -d '{"query":"Tomate alface batata hortaliças","top_k":5}'

# Query 3: Grãos
curl -X POST http://localhost:8000/rag/buscar \
  -H "Content-Type: application/json" \
  -d '{"query":"Arroz feijão milho grãos","top_k":5}'
```

---

## 📋 Checklist de Deployment

- [ ] Verificar que todos os 216 chunks têm embeddings (`teste_busca_rag.py`)
- [ ] Testar endpoints localmente (`curl` ou Swagger)
- [ ] Validar resposta de latência (<300ms)
- [ ] Configurar variáveis de ambiente (SUPABASE_URL, SUPABASE_KEY)
- [ ] Adicionar rate limiting se necessário
- [ ] Configurar logging e monitoring
- [ ] Testar com 10 queries reais
- [ ] Documentar API (README + Swagger)
- [ ] Setup de CI/CD (GitHub Actions)
- [ ] Alertas de erro/downtime

---

## 🐛 Troubleshooting

### Erro: "Chunks com embedding: 0/X"

```bash
# Reexecutar indexação
python indexar_agro_corrigido.py
```

### Erro: "PGRST202 - Function not found"

Isso é OK. Sistema usa cálculo Python, não pgvector SQL.

### API lenta (>500ms)

```bash
# Limitar chunks carregados em api_rag.py
result = sb.table("pdf_chunks").select(...).limit(200).execute()
```

### Supabase connection refused

```bash
# Verificar .env
echo $SUPABASE_URL
echo $SUPABASE_KEY

# Testar conexão
python -c "from supabase import create_client; sb = create_client('...', '...'); print(sb.table('pdf_chunks').select('count', count='exact').execute())"
```

---

## 📚 Referências

- **RAG Docs:** https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
- **Supabase Vector:** https://supabase.com/docs/guides/ai/vector-columns
- **FastAPI:** https://fastapi.tiangolo.com/
- **Semantic Search:** https://www.sbert.net/

---

## 🎯 Próximos Passos

1. **Integração com Chat**
   - Usar RAG como contexto para respostas
   - Implementar prompt com chunks
   - Melhorar relevalância

2. **Melhorias de Performance**
   - Cache de embeddings populares
   - Índices de banco otimizados
   - Busca com filtros (processo, data, etc)

3. **Monitoramento**
   - Logs estruturados
   - Métricas de latência
   - Alertas de erro

4. **Expansão**
   - Indexar mais documentos (180+ totais)
   - Adicionar busca por metadados
   - Implementar re-ranking

---

**Criado em:** 2026-04-26  
**Autor:** AgroIA System  
**Status:** Production Ready ✅
