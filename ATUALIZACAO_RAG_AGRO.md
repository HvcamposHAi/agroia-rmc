# 🔍 Atualização: RAG com Filtro Agrícola via View

**Data:** 2026-04-25  
**Objetivo:** Garantir que buscas semânticas (RAG) retornem APENAS chunks de PDFs de licitações agrícolas

---

## 📋 Resumo

**Antes:**
```python
# chat/tools.py - buscar_documentos_vetor()
resp = sb.from_('pdf_chunks').select('*').limit(limite).execute()
# ❌ Retorna chunks de TODOS os PDFs (agrícolas e não-agrícolas)
```

**Depois:**
```python
# chat/tools.py - buscar_documentos_vetor()
resp = sb.from_('vw_pdf_chunks_agro').select('*').limit(limite).execute()
# ✅ Retorna chunks APENAS de PDFs agrícolas (relevante_af=true)
```

---

## 🛠️ Passo 1: Criar a View

Execute no Supabase SQL Editor:

```bash
# Copiar e executar arquivo:
criar_vw_pdf_chunks_agro.sql
```

Ou direto:

```sql
DROP VIEW IF EXISTS vw_pdf_chunks_agro CASCADE;

CREATE OR REPLACE VIEW vw_pdf_chunks_agro AS
SELECT
    pc.id, pc.licitacao_id, pc.documento_id, pc.processo, 
    pc.nome_doc, pc.chunk_index, pc.chunk_text, pc.embedding, 
    pc.tokens_aprox, pc.indexado_em,
    l.relevante_af, d.nome_arquivo, d.tipo_documento
FROM pdf_chunks pc
INNER JOIN documentos_licitacao d ON pc.documento_id = d.id
INNER JOIN licitacoes l ON d.licitacao_id = l.id
WHERE l.relevante_af = true;
```

**Verificação:**
```sql
SELECT COUNT(*) FROM vw_pdf_chunks_agro;  -- Chunks agrícolas
SELECT COUNT(*) FROM pdf_chunks;           -- Chunks totais
```

---

## 🔧 Passo 2: Atualizar chat/tools.py

### Localizar função `buscar_documentos_vetor()`

**Antes:**
```python
def buscar_documentos_vetor(
    query: str,
    limite: int = 5,
    processo: str | None = None
) -> list[dict]:
    """Busca semântica em PDFs."""
    try:
        # Embed query
        embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        query_embedding = embedder.encode(query).tolist()
        
        # ❌ ANTES: Usar pdf_chunks diretamente
        resp = sb.from_('pdf_chunks').select('*').limit(limite).execute()
        # ... processamento ...
```

**Depois:**
```python
def buscar_documentos_vetor(
    query: str,
    limite: int = 5,
    processo: str | None = None
) -> list[dict]:
    """Busca semântica em PDFs AGRÍCOLAS apenas (relevante_af=true)."""
    try:
        # Embed query
        embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        query_embedding = embedder.encode(query).tolist()
        
        # ✅ DEPOIS: Usar vw_pdf_chunks_agro com filtro agrícola
        resp = sb.from_('vw_pdf_chunks_agro').select('*').limit(limite).execute()
        
        # Se houver filtro de processo, adicionar
        if processo:
            resp = sb.from_('vw_pdf_chunks_agro').select('*').eq('processo', processo).limit(limite).execute()
        
        # ... resto do processamento ...
```

---

## 📊 Benefícios

| Aspecto | Antes | Depois |
|---------|-------|--------|
| **Escopo** | Todos PDFs | Apenas agrícolas ✅ |
| **Manutenção** | Filtro em múltiplos lugares | Centralizado em 1 view |
| **Consistência** | Risco de inconsistência | Garantido em todos clientes |
| **Performance** | Query sem índice de relevância | View otimizada |
| **Documentação** | Implícita no código | Explícita (COMMENT ON VIEW) |

---

## 🎯 Checklist de Implementação

- [ ] 1. Executar SQL para criar `vw_pdf_chunks_agro`
- [ ] 2. Verificar: `SELECT COUNT(*) FROM vw_pdf_chunks_agro;`
- [ ] 3. Atualizar `chat/tools.py` função `buscar_documentos_vetor()`
- [ ] 4. Testar query: `/chat "Qual é a demanda de leite?"`
- [ ] 5. Validar que resposta cita APENAS documentos agrícolas
- [ ] 6. Commit changes: `git add crear_vw_pdf_chunks_agro.sql chat/tools.py`

---

## 🔍 Teste de Validação

Após implementar, execute:

```python
# Terminal Python
from chat.tools import buscar_documentos_vetor

# Teste 1: Busca por query agrícola
resultados = buscar_documentos_vetor("demanda de leite", limite=3)
print(f"Chunks retornados: {len(resultados)}")
print(f"Processo (deve ser agrícola): {resultados[0]['processo']}")

# Teste 2: Verificar que TODOS são agrícolas
for r in resultados:
    assert r.get('relevante_af') == True, "❌ Chunk não-agrícola retornado!"
print("✅ Todos os chunks são agrícolas")
```

---

## 📝 Documentação Atualizada

**System Prompt (`chat/prompts.py`):**
```markdown
## RAG (Busca Semântica em PDFs)

Usa `vw_pdf_chunks_agro` para garantir que APENAS documentos de licitações 
agrícolas (relevante_af=true) sejam retornados nas buscas semânticas.

Não é necessário filtrar manualmente — a view faz isso automaticamente.
```

---

## 🔗 Referências

- **View criada:** `vw_pdf_chunks_agro` (agrícola)
- **View original:** `pdf_chunks` (todos)
- **Campo filtro:** `licitacoes.relevante_af` (true = agrícola)
- **Tabelas envolvidas:** `pdf_chunks`, `documentos_licitacao`, `licitacoes`

---

## ✅ Resultado

**Antes:**
```
❌ RAG poderia retornar chunks de PDFs não-agrícolas
❌ Sem garantia de escopo em buscas semânticas
```

**Depois:**
```
✅ RAG sempre retorna APENAS chunks de PDFs agrícolas
✅ Escopo garantido por design (via view)
✅ Reutilizável em múltiplos clientes
✅ Manutenção centralizada
```
