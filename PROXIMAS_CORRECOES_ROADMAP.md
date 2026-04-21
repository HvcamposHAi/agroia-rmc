# 🛠️ Próximas Correções - Roadmap Detalhado

**Data**: 2026-04-21  
**Status**: 5/12 bugs corrigidos  
**Próximos**: 7 bugs pendentes  
**Tempo Estimado**: ~15-20 horas de desenvolvimento

---

## 📊 Status Atual

### ✅ Já Corrigidos (5 Bugs)

| ID | Nome | Arquivo | Status |
|----|------|---------|--------|
| BUG-001 | Response Validation | api/main.py | ✅ DONE |
| BUG-003 | Error Logging | api/main.py | ✅ DONE |
| BUG-005 | Env Validation | api/main.py | ✅ DONE |
| BUG-002 | Agent Timeout | chat/agent.py | ✅ DONE |
| BUG-006 | Input Sanitization | chat/tools.py | ✅ DONE |

### ⏳ Pendentes (7 Bugs)

| ID | Nome | Prioridade | Tempo | Status |
|----|------|-----------|-------|--------|
| BUG-004 | Connection Pooling | 🟡 ALTA | 1-2h | TODO |
| BUG-007 | Timeout Validation | 🟡 ALTA | 1h | TODO |
| BUG-008 | Auditoria Error Handling | 🟠 MÉDIA | 1h | TODO |
| BUG-009 | Document Views | 🟠 MÉDIA | 30m | TODO |
| BUG-010 | Session Persistence Tests | 🟠 MÉDIA | 1h | TODO |
| BUG-011 | Documentation | 🟢 BAIXA | 2h | TODO |
| BUG-012 | Inconsistent Messages | 🟢 BAIXA | 1h | TODO |

---

## 🎯 Fase 1: HOJE (Commit & Review)

### Ação: Revisar & Fazer Commit dos Hotfixes

```bash
# 1. Revisar mudanças
git diff api/main.py
git diff chat/agent.py
git diff chat/tools.py

# 2. Stage files
git add api/main.py chat/agent.py chat/tools.py tests/

# 3. Commit
git commit -m "fix: implement critical hotfixes for chat API stability

- BUG-001: Add response validation in /chat endpoint
- BUG-003: Implement structured logging with session_id
- BUG-005: Validate environment variables on startup
- BUG-002: Add timeout (15s) and error handling to agent loop
- BUG-006: Sanitize tool inputs to prevent SQL injection

Fixes 'Sem resposta do servidor' error (GitHub #123)"

# 4. Push
git push origin main
```

---

## 🔵 Fase 2: AMANHÃ (2026-04-22) - HIGH PRIORITY

### BUG-004: Connection Pooling

**Problema**: Single Supabase client reutilizado indefinidamente → timeout após muitas requisições

**Arquivo**: `chat/db.py`

**Antes**:
```python
from dotenv import load_dotenv
from supabase import create_client, Client
import os

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

_client: Client | None = None

def get_supabase_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client
```

**Problema**: Se conexão expirar, não há reconnect.

**Solução**:
```python
from dotenv import load_dotenv
from supabase import create_client, Client
import os
import logging

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

logger = logging.getLogger(__name__)

_client: Client | None = None
_client_created_at: float = 0
CLIENT_TIMEOUT_SECONDS = 3600  # 1 hour

def get_supabase_client() -> Client:
    """Get Supabase client with automatic reconnection."""
    global _client, _client_created_at
    import time
    
    current_time = time.time()
    
    # Reconectar se expirou ou cliente é None
    if _client is None or (current_time - _client_created_at) > CLIENT_TIMEOUT_SECONDS:
        try:
            logger.info("Creating new Supabase connection...")
            _client = create_client(SUPABASE_URL, SUPABASE_KEY)
            _client_created_at = current_time
            logger.info("Supabase connection established")
        except Exception as e:
            logger.error(f"Failed to create Supabase client: {str(e)}", exc_info=True)
            raise
    
    return _client
```

**Testes**:
```python
def test_connection_pooling():
    """Test que conexão é reutilizada"""
    client1 = get_supabase_client()
    client2 = get_supabase_client()
    assert client1 is client2  # Mesma instância

def test_connection_timeout_reconnect():
    """Test que nova conexão é criada após timeout"""
    import time
    client1 = get_supabase_client()
    # Simular timeout mudando a data
    import chat.db
    chat.db._client_created_at -= 3700  # 3700 segundos atrás
    client2 = get_supabase_client()
    # Deveria ter criado nova conexão
    assert client1 is not client2
```

**Tempo Estimado**: 1-2 horas  
**Ganho**: Elimina timeout em requisições longas

---

### BUG-007: Timeout Validation

**Problema**: Precisa validar que timeout 15s está funcionando

**Arquivo**: `tests/test_timeout.py` (novo)

**O que testar**:
```python
import asyncio
import time
from chat.agent import chat

def test_agent_timeout():
    """Testa que agent não fica pendurado mais de 15s"""
    start = time.time()
    
    # Fazer pergunta que demanda processamento
    resultado = chat("Pergunta complexa que levaria muito tempo", [])
    
    elapsed = time.time() - start
    
    # Deve retornar em menos de 15 segundos
    assert elapsed < 15, f"Agent took {elapsed}s (max 15s)"
    
    # Deve ter fallback response
    assert "resposta" in resultado
    assert resultado["resposta"]  # Não vazio
    
    print(f"✅ Agent responded in {elapsed:.2f}s with fallback response")

def test_concurrent_requests_no_timeout():
    """Testa 10 requisições simultâneas sem timeout"""
    import concurrent.futures
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(chat, f"Question {i}", [])
            for i in range(10)
        ]
        
        results = [f.result(timeout=20) for f in futures]
        
        # Todas devem ter respostas
        assert all("resposta" in r for r in results)
        print(f"✅ 10 concurrent requests succeeded")
```

**Tempo Estimado**: 1 hora  
**Ganho**: Confiança que timeout está funcionando

---

## 🟠 Fase 3: SEMANA 1 (2026-04-23 a 2026-04-25) - MEDIUM PRIORITY

### BUG-008: Auditoria Error Handling

**Problema**: Endpoint `/auditoria/executar` falha com 500 se view não existir

**Arquivo**: `api/main.py` (linhas 230-316)

**Antes**:
```python
@app.post("/auditoria/executar")
async def executar_auditoria() -> AuditoriaResultado:
    """Executa auditoria de qualidade dos dados e licitações agrícolas."""
    try:
        sb = get_supabase_client()

        # Direto sem validar se view existe
        r = sb.from_('vw_itens_agro_puros').select(
            'cultura, valor_total, qt_solicitada, dt_abertura'
        ).execute()  # ❌ Erro aqui se view não existe
```

**Solução**:
```python
@app.post("/auditoria/executar")
async def executar_auditoria() -> AuditoriaResultado:
    """Executa auditoria de qualidade dos dados e licitações agrícolas."""
    try:
        sb = get_supabase_client()
        
        # 1. Validar views existem
        required_views = ['vw_itens_agro_puros', 'itens_licitacao', 'documentos_licitacao']
        for view_name in required_views:
            try:
                sb.from_(view_name).select('1').limit(1).execute()
                logger.info(f"✓ View {view_name} exists")
            except Exception as e:
                logger.error(f"✗ View {view_name} missing: {str(e)}")
                raise HTTPException(
                    status_code=503,
                    detail=f"Required database view '{view_name}' not found. Run migration: criar_views_agro.sql"
                )
        
        # 2. Resto do código com try/except detalhado
        try:
            r = sb.from_('vw_itens_agro_puros').select(
                'cultura, valor_total, qt_solicitada, dt_abertura'
            ).execute()
        except Exception as e:
            logger.error(f"Failed to query vw_itens_agro_puros: {str(e)}")
            raise HTTPException(status_code=503, detail="Database query failed")
        
        # ... resto do código com logging em cada passo ...
        
        return AuditoriaResultado(...)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Auditoria error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Auditoria failed")
```

**Teste**:
```python
def test_auditoria_missing_view():
    """Testa erro claro quando view falta"""
    # Simular view inexistente
    # Resultado: deve retornar 503 com mensagem sobre migration
    response = client.post("/auditoria/executar")
    assert response.status_code == 503
    assert "migration" in response.json()["detail"].lower()
```

**Tempo Estimado**: 1 hora  
**Ganho**: Mensagens de erro específicas

---

### BUG-009: Document Views

**Problema**: Views críticas não estão documentadas, precisa rodar SQL manual

**Arquivo**: Novo arquivo `VIEWS_REQUIRED.md`

**Criar**:
```markdown
# Views Críticas - Documentação

## Views Necessárias para Operação

### 1. vw_itens_agro
```sql
CREATE OR REPLACE VIEW vw_itens_agro AS
SELECT 
  i.id, i.licitacao_id, i.descricao, i.categoria_v2,
  l.processo, l.dt_abertura, l.canal,
  i.valor_total, i.qt_solicitada,
  CASE WHEN i.relevante_agro = true THEN 'SIM' ELSE 'NÃO' END as relevante
FROM itens_licitacao i
JOIN licitacoes l ON i.licitacao_id = l.id
WHERE i.relevante_agro = true;
```

### 2. vw_itens_agro_puros
```sql
CREATE OR REPLACE VIEW vw_itens_agro_puros AS
SELECT 
  i.descricao, i.categoria_v2 as cultura,
  SUM(i.valor_total) as valor_total,
  SUM(i.qt_solicitada) as qt_solicitada,
  l.dt_abertura
FROM itens_licitacao i
JOIN licitacoes l ON i.licitacao_id = l.id
WHERE i.relevante_agro = true
GROUP BY i.categoria_v2, l.dt_abertura, i.descricao;
```

## Como Criar as Views

1. Abrir Supabase editor: https://app.supabase.com
2. Ir para: SQL Editor
3. Copiar/colar cada CREATE VIEW acima
4. Executar
5. Validar: SELECT COUNT(*) FROM vw_itens_agro;

## Como Validar

```sql
-- Verificar que views existem
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name LIKE 'vw_%';

-- Deve retornar:
-- vw_itens_agro
-- vw_itens_agro_puros
-- vw_demanda_agro_ano
-- ... outras views
```
```

**Adicionar validação em startup**:
```python
# Em chat/db.py
def validate_db_schema():
    """Valida views essenciais existem"""
    sb = get_supabase_client()
    REQUIRED_VIEWS = [
        "vw_itens_agro",
        "vw_itens_agro_puros",
        "vw_demanda_agro_ano"
    ]
    
    missing = []
    for view in REQUIRED_VIEWS:
        try:
            sb.table(view).select("1").limit(1).execute()
        except:
            missing.append(view)
    
    if missing:
        raise RuntimeError(f"Missing required views: {', '.join(missing)}\nRun: criar_views_agro.sql")
    
    logger.info("✓ All required views validated")

# No api/main.py startup
try:
    validate_db_schema()
except RuntimeError as e:
    logger.error(str(e))
    raise
```

**Tempo Estimado**: 30 minutos  
**Ganho**: Deploy mais seguro (falha early se falta view)

---

### BUG-010: Session Persistence Tests

**Problema**: Histórico de conversa salvo mas não testado

**Arquivo**: `tests/test_session_persistence.py` (novo)

```python
import pytest
from api.main import chat_endpoint, ChatRequest
from chat.db import get_supabase_client

def test_session_history_saved():
    """Testa que histórico é salvo corretamente"""
    session_id = "test-session-12345"
    
    # Pergunta 1
    req1 = ChatRequest(pergunta="Qual a demanda de alface?", session_id=session_id)
    resp1 = chat_endpoint(req1)
    
    # Pergunta 2
    req2 = ChatRequest(pergunta="E de tomate?", session_id=session_id)
    resp2 = chat_endpoint(req2)
    
    # Verificar histórico no banco
    sb = get_supabase_client()
    historia = sb.table("conversas").select("role, content").eq("session_id", session_id).execute()
    
    # Deve ter 4 entradas: user1, assistant1, user2, assistant2
    assert len(historia.data) == 4
    assert historia.data[0]["role"] == "user"
    assert "alface" in historia.data[0]["content"]
    assert historia.data[1]["role"] == "assistant"
    assert historia.data[2]["role"] == "user"
    assert "tomate" in historia.data[2]["content"]

def test_session_history_retrieved():
    """Testa que histórico pode ser recuperado"""
    session_id = "test-session-67890"
    
    # Fazer pergunta
    req = ChatRequest(pergunta="Teste", session_id=session_id)
    chat_endpoint(req)
    
    # Recuperar histórico via endpoint
    from api.main import obter_conversa
    historia = obter_conversa(session_id)
    
    assert len(historia) >= 1
    assert any("Teste" in msg.get("content", "") for msg in historia)

def test_session_history_deleted():
    """Testa que histórico pode ser deletado"""
    session_id = "test-session-delete"
    
    # Fazer pergunta
    req = ChatRequest(pergunta="Para deletar", session_id=session_id)
    chat_endpoint(req)
    
    # Deletar via endpoint
    from api.main import deletar_conversa
    result = deletar_conversa(session_id)
    
    assert result["status"] == "deletado"
    
    # Verificar que foi deletado
    from api.main import obter_conversa
    historia = obter_conversa(session_id)
    assert len(historia) == 0
```

**Tempo Estimado**: 1 hora  
**Ganho**: Confiança em persistência

---

## 🟢 Fase 4: SEMANA 2+ - LOW PRIORITY

### BUG-011: Documentation

**O que documentar**:
- [ ] Swagger docs para /chat endpoint
- [ ] Swagger docs para /auditoria endpoints
- [ ] Exemplos de curl para cada endpoint
- [ ] README.md atualizado
- [ ] Troubleshooting guide

**Arquivo**: Múltiplos

```python
# Em api/main.py - adicionar docstrings
@app.post("/chat")
def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """
    Chat endpoint com suporte a tool use.
    
    **Parâmetros:**
    - pergunta (str): Pergunta do usuário
    - historico (list): Histórico anterior [optional]
    - session_id (str): ID da sessão [optional, gera se não fornecido]
    
    **Resposta:**
    - resposta (str): Resposta do agente
    - tools_usadas (list): Ferramentas utilizadas
    - session_id (str): ID da sessão para histórico
    
    **Exemplo:**
    ```
    POST /chat
    {
      "pergunta": "Qual a demanda de alface em Curitiba?",
      "historico": []
    }
    ```
    
    **Resposta:**
    ```
    {
      "resposta": "Os dados mostram...",
      "tools_usadas": ["query_itens_agro"],
      "session_id": "uuid-aqui"
    }
    ```
    """
```

**Tempo Estimado**: 2 horas  
**Ganho**: Melhor onboarding

---

### BUG-012: Inconsistent Messages

**Problema**: Mensagens misturadas português/inglês

**Arquivo**: `chat/agent.py`, `api/main.py`, `chat/tools.py`

**Auditoria**:
```bash
# Procurar por mensagens em inglês
grep -r "error\|failed\|unexpected\|invalid" --include="*.py" chat/ api/

# Resultado esperado: NENHUMA mensagem em inglês
```

**Correção**:
```python
# ANTES (inglês)
"resposta": "Error: Agent returned empty response"

# DEPOIS (português)
"resposta": "Erro: O agente não retornou uma resposta válida"
```

**Tempo Estimado**: 1 hora  
**Ganho**: UX melhor para usuários portugueses

---

## 📅 Timeline Recomendado

```
2026-04-21 (HOJE)
  ✅ Commit hotfixes 5/5

2026-04-22 (AMANHÃ)
  [ ] BUG-004: Connection pooling       (2h)
  [ ] BUG-007: Timeout validation       (1h)

2026-04-23 (DIA 3)
  [ ] BUG-008: Auditoria error handling (1h)
  [ ] BUG-009: Document views           (30m)

2026-04-24 (DIA 4)
  [ ] BUG-010: Session tests            (1h)
  [ ] Testing & review                  (1h)

2026-04-25 (DIA 5)
  [ ] BUG-011: Documentation            (2h)
  [ ] BUG-012: Consistent messages      (1h)

2026-04-26 (DIA 6)
  [ ] Final testing & validation        (2h)
  [ ] Deploy em staging                 (1h)
```

---

## 🎯 Quick Start - O que fazer AGORA

### Hoje (2026-04-21)

**AÇÃO 1**: Commit dos 5 hotfixes
```bash
git add api/main.py chat/agent.py chat/tools.py tests/
git commit -m "fix: implement critical hotfixes..."
git push origin main
```

**AÇÃO 2**: Code review
- Revisar diffs no GitHub
- Pedir review de colega
- Validar CI/CD passa

**AÇÃO 3**: Deploy em staging
```bash
# Se houver ambiente staging
./scripts/deploy-staging.sh
```

### Amanhã (2026-04-22)

**AÇÃO 1**: Implementar BUG-004
- Abrir `chat/db.py`
- Adicionar timeout & reconnect
- Criar testes

**AÇÃO 2**: Implementar BUG-007
- Criar `tests/test_timeout.py`
- Rodar testes de carga
- Validar timeout funciona

---

## 📋 Checklist de Prioridades

### 🔴 CRÍTICA (Impacto Alto, Fácil)
- [ ] Commit hotfixes HOJE
- [ ] BUG-004: Connection pooling (previne cascade failure)
- [ ] BUG-007: Timeout validation (garante resposta < 15s)

### 🟡 ALTA (Impacto Médio, Médio Esforço)
- [ ] BUG-008: Auditoria error handling
- [ ] BUG-009: Document views

### 🟠 MÉDIA (Qualidade)
- [ ] BUG-010: Session tests
- [ ] BUG-011: Documentation
- [ ] BUG-012: Consistent messages

---

## 📞 Suporte

Se tiver dúvidas durante implementação:

1. **Bug-specific docs**:
   - AUDITORIA_CODIGO_20260421.md (tem detalhes de cada bug)

2. **Implementation examples**:
   - DOCUMENTO_COMPLETO_AUDITORIA.md (seção "Solução Implementada")

3. **Testing guide**:
   - GUIA_TESTE_HOTFIXES.md (como testar cada hotfix)

---

**Próximo Status Update**: 2026-04-22 (após implementar BUG-004, BUG-007)

Boa sorte! 🚀
