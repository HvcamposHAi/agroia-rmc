# 🔍 Auditoria de Código - AgroIA-RMC

**Data:** 2026-04-21  
**Versão:** 1.0  
**Status:** 🔴 CRÍTICO - API retornando respostas vazias

---

## 📋 Resumo Executivo

Após análise profunda do código, **identificamos erro crítico no fluxo chat**: o endpoint `/chat` não está retornando o campo `resposta` esperado, causando a mensagem "Sem resposta do servidor" no frontend.

**Achado Principal**: Na linha 45 de `Chat.tsx`, quando `data.resposta` é undefined, a aplicação exibe a mensagem de erro.

**Causas Raiz Identificadas**:
1. ✗ Falta de validação de resposta da API  
2. ✗ Tratamento de exceção inadequado em `agent.py`  
3. ✗ Ausência de logging estruturado  
4. ✗ Sem testes automatizados para fluxo end-to-end  

---

## 🐛 Issues Identificadas

### **CRÍTICO** 🔴

#### [BUG-001] Response Handler Missing Validation
- **Localização**: `api/main.py:103-117` + `agroia-frontend/src/pages/Chat.tsx:44-45`
- **Descrição**: Endpoint retorna JSON mas `resposta` pode ser vazia/undefined
- **Sintoma**: Mensagem "Sem resposta do servidor" mesmo com 200 OK
- **Causa**: Função `chat()` pode falhar silenciosamente, retornando dict vazio
- **Severidade**: CRÍTICA
- **Impacto**: Aplicação não funcional

```python
# Código problemático (api/main.py:108)
resultado = chat(request.pergunta, historico)
# Se chat() falhar, resultado pode ser None ou dict vazio
```

#### [BUG-002] Exception Masking in Agent Loop
- **Localização**: `chat/agent.py:24-69`
- **Descrição**: Loop de tool_use não tem timeout, pode travar indefinidamente
- **Sintoma**: Request timeout sem resposta
- **Causa**: Sem proteção contra loops infinitos entre tools
- **Severidade**: CRÍTICA
- **Impacto**: API fica não responsiva

```python
# Problema: max_iteracoes=10 pode ser insuficiente para queries complexas
# Sem timeout global, requisição fica pendente
```

#### [BUG-003] Missing Error Logging
- **Localização**: `api/main.py:102-117`
- **Descrição**: Exceções capturadas mas não logadas
- **Sintoma**: Impossível debugar erros em produção
- **Causa**: Exception handler retorna apenas `str(e)` sem contexto
- **Severidade**: CRÍTICA
- **Impacto**: Impossível investigar falhas

---

### **ALTO** 🟡

#### [BUG-004] Database Connection Pool Not Managed
- **Localização**: `chat/db.py:10-16`
- **Descrição**: Single global client sem conexão pool ou reconnect
- **Sintoma**: Connection timeout após muitas requisições
- **Causa**: Supabase client reutilizado indefinidamente sem refresh
- **Severidade**: ALTO
- **Impacto**: API falha sob carga

#### [BUG-005] Missing Env Validation
- **Localização**: `api/main.py:1-12`, `chat/db.py:1-16`
- **Descrição**: `.env` não validado no startup
- **Sintoma**: Erro opaco "no attribute SUPABASE_URL" em produção
- **Causa**: Sem verificação de variáveis necessárias
- **Severidade**: ALTO
- **Impacto**: Deploy quebra silenciosamente

```python
# chat/db.py não valida se URLs estão definidas
SUPABASE_URL = os.getenv("SUPABASE_URL")  # Pode ser None
```

#### [BUG-006] Tool Input Validation Missing
- **Localização**: `chat/tools.py:5-132`
- **Descrição**: Tools aceitam input arbitrário sem validação
- **Sintoma**: SQL injection possível via `ilike()` sem sanitização
- **Causa**: Parâmetros passados diretamente para queries
- **Severidade**: ALTO  
- **Impacto**: Segurança, injeção de SQL

#### [BUG-007] Missing Response Timeout
- **Localização**: `chat/agent.py:27-33`
- **Descrição**: `client.messages.create()` sem timeout
- **Sintoma**: Request pendente se Claude API ficar lenta
- **Causa**: FastAPI timeout padrão pode ser > do que esperado
- **Severidade**: ALTO
- **Impacto**: UX degradada, server resource leak

---

### **MÉDIO** 🟠

#### [BUG-008] Incomplete Error Handling in Auditoria
- **Localização**: `api/main.py:230-316`
- **Descrição**: Auditoria executa queries sem verificação de schema
- **Sintoma**: Erro 500 se view `vw_itens_agro_puros` não existir
- **Causa**: Sem verificação prévia de views
- **Severidade**: MÉDIO
- **Impacto**: Endpoint auditoria inutilizável

#### [BUG-009] View Assumptions Not Documented
- **Localização**: `chat/tools.py`, `api/main.py:142-149`
- **Descrição**: Código assume views existem sem garantia
- **Sintoma**: "Relation not found" errors
- **Causa**: Views criadas manualmente, sem migration
- **Severidade**: MÉDIO
- **Impacto**: Deploy frágil

#### [BUG-010] No Session Persistence Testing
- **Localização**: `api/main.py:75-100`
- **Descrição**: Histórico de conversa salvo sem testes
- **Sintoma**: Histórico pode ser inconsistente ou corrompido
- **Causa**: Sem validação de dados antes de inserir
- **Severidade**: MÉDIO
- **Impacto**: Conversa degradada após múltiplas trocas

---

### **BAIXO** 🟢

#### [BUG-011] Documentation Missing
- **Localização**: Todo o projeto
- **Descrição**: Funções sem docstrings, APIs não documentadas
- **Sintoma**: Dificuldade em manutenção
- **Causa**: Código escrito sem padrão de documentação
- **Severidade**: BAIXO
- **Impacto**: Onboarding lento

#### [BUG-012] Inconsistent Error Messages
- **Localização**: `chat/tools.py:268`, `api/main.py:73, 100, 117`
- **Descrição**: Mensagens de erro inconsistentes (português/inglês)
- **Severidade**: BAIXO
- **Impacto**: UX confusa

---

## 📊 Backlog de Issues

| ID | Título | Prioridade | Status | Assignee | ETA |
|---|---|---|---|---|---|
| BUG-001 | Response Handler Missing Validation | 🔴 CRÍTICA | TODO | - | 2026-04-22 |
| BUG-002 | Exception Masking in Agent Loop | 🔴 CRÍTICA | TODO | - | 2026-04-22 |
| BUG-003 | Missing Error Logging | 🔴 CRÍTICA | TODO | - | 2026-04-22 |
| BUG-004 | Database Connection Pool | 🟡 ALTO | TODO | - | 2026-04-23 |
| BUG-005 | Missing Env Validation | 🟡 ALTO | TODO | - | 2026-04-23 |
| BUG-006 | Tool Input Validation | 🟡 ALTO | TODO | - | 2026-04-24 |
| BUG-007 | Missing Response Timeout | 🟡 ALTO | TODO | - | 2026-04-24 |
| BUG-008 | Incomplete Error Handling Auditoria | 🟠 MÉDIO | TODO | - | 2026-04-25 |
| BUG-009 | View Assumptions Not Documented | 🟠 MÉDIO | TODO | - | 2026-04-25 |
| BUG-010 | No Session Persistence Testing | 🟠 MÉDIO | TODO | - | 2026-04-26 |

---

## 🛠️ Ações Recomendadas (Roadmap)

### **Fase 1: Hotfix Críticos (2026-04-22)**
Objetivo: Estabilizar API e fazer chat responder

**1.1** [BUG-001] Adicionar validação de resposta no endpoint
```python
# api/main.py - linha 108
if not resultado or "resposta" not in resultado:
    raise HTTPException(status_code=500, detail="Agent returned empty response")
```

**1.2** [BUG-003] Implementar logging estruturado
```python
import logging
logger = logging.getLogger(__name__)

@app.post("/chat")
def chat_endpoint(request: ChatRequest) -> ChatResponse:
    try:
        # ...
    except Exception as e:
        logger.error(f"Chat error for question '{request.pergunta}'", exc_info=True)
        raise
```

**1.3** [BUG-005] Validar `.env` no startup
```python
# api/main.py - adicionar antes de app = FastAPI()
from chat.db import SUPABASE_URL, SUPABASE_KEY
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing required env vars: SUPABASE_URL, SUPABASE_KEY")
```

**Testes para Validação**:
- ✅ `test_chat_endpoint_with_valid_question()`
- ✅ `test_chat_endpoint_with_empty_history()`
- ✅ `test_api_startup_with_missing_env()`

---

### **Fase 2: Melhorias de Robustez (2026-04-23 a 2026-04-24)**
Objetivo: Evitar crashes e timeouts

**2.1** [BUG-002] Adicionar timeout e proteção contra loops
```python
# chat/agent.py
import asyncio

async def chat_with_timeout(pergunta: str, historico, timeout=30):
    """Chat com timeout global"""
    try:
        return await asyncio.wait_for(
            chat(pergunta, historico),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        return {
            "resposta": "Sua pergunta é complexa demais. Tente simplificar.",
            "tools_usadas": []
        }
```

**2.2** [BUG-004] Implementar connection pooling
```python
# chat/db.py - usar supabase async client com pool
from supabase.async_client import AsyncClient

async def get_supabase_client() -> AsyncClient:
    # Com retry automático
```

**2.3** [BUG-007] Adicionar timeout ao client.messages.create()
```python
# chat/agent.py - linha 27
response = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=2048,
    system=SYSTEM_PROMPT,
    tools=TOOLS_SCHEMA,
    messages=messages,
    timeout=15  # ← NOVO
)
```

**Testes para Validação**:
- ✅ `test_chat_timeout_after_30s()`
- ✅ `test_db_reconnect_on_connection_fail()`
- ✅ `test_tool_execution_timeout()`

---

### **Fase 3: Segurança & Validação (2026-04-24 a 2026-04-25)**
Objetivo: Prevenir injeção e garantir dados válidos

**3.1** [BUG-006] Sanitizar inputs de tools
```python
# chat/tools.py
from urllib.parse import quote

def query_itens_agro(cultura: str | None = None, **kwargs):
    if cultura:
        # Validar string segura
        cultura = str(cultura).strip()[:100]  # Max 100 chars
        if not cultura.isalnum():
            raise ValueError("Cultura deve conter apenas letras e números")
    # ...
```

**3.2** [BUG-009] Documentar e validar views
```python
# chat/db.py - novo
REQUIRED_VIEWS = [
    "vw_itens_agro",
    "vw_itens_agro_puros",
    "vw_demanda_agro_ano"
]

def validate_db_schema():
    """Valida views essenciais existem"""
    sb = get_supabase_client()
    for view in REQUIRED_VIEWS:
        try:
            sb.table(view).select("1").limit(1).execute()
        except Exception:
            raise RuntimeError(f"View {view} not found in database")
```

**Testes para Validação**:
- ✅ `test_sql_injection_attempt_rejected()`
- ✅ `test_required_views_exist()`
- ✅ `test_input_validation_boundary_cases()`

---

### **Fase 4: Observabilidade & Testes (2026-04-26+)**
Objetivo: Detectar e prevenir regressões

**4.1** Implementar health checks detalhados
```python
# api/main.py
@app.get("/health/detailed")
def health_detailed():
    checks = {
        "database": check_db(),
        "views": check_views(),
        "anthropic_key": bool(os.getenv("ANTHROPIC_API_KEY")),
        "google_drive": check_drive_access(),
        "uptime_seconds": get_uptime()
    }
    status = "ok" if all(checks.values()) else "degraded"
    return {"status": status, "checks": checks}
```

**4.2** Adicionar suite de testes automatizados
```bash
# tests/test_chat_integration.py
pytest tests/ -v --cov=api --cov=chat
```

**4.3** Monitoramento e alertas
```python
# Integrar com observabilidade (Sentry/Datadog)
import sentry_sdk
sentry_sdk.init(dsn=os.getenv("SENTRY_DSN"))
```

---

## 📈 Matriz de Riscos

```
Severidade │ Frequência │ Risco Total │ Exemplos
───────────┼───────────┼─────────────┼──────────────────
CRÍTICA    │ SEMPRE    │ 🔴🔴🔴     │ BUG-001, BUG-002
ALTA       │ FREQUENTE │ 🔴🔴      │ BUG-004, BUG-006
MÉDIA      │ OCASIONAL │ 🔴        │ BUG-008, BUG-009
BAIXA      │ RARA      │ 🟡        │ BUG-011, BUG-012
```

---

## 🧪 Plano de Testes

### Testes Unitários Necessários (Fase 1-2)
```python
# tests/test_agent.py
- test_chat_returns_valid_response()
- test_chat_handles_empty_history()
- test_chat_tool_execution()
- test_chat_timeout_protection()
- test_chat_malformed_tool_response()

# tests/test_tools.py
- test_query_itens_agro_with_filters()
- test_query_itens_agro_sql_injection_attempt()
- test_tool_input_validation()

# tests/test_api.py
- test_chat_endpoint_happy_path()
- test_chat_endpoint_error_handling()
- test_health_endpoint()
```

### Testes Integração (Fase 2-3)
```python
# tests/integration/test_end_to_end.py
- test_user_question_to_response(question="Qual a demanda de alface?")
- test_session_history_persistence()
- test_chat_with_multiple_tools()
- test_concurrent_requests()
```

### Testes de Carga (Fase 3-4)
```bash
# Testar API sob 10+ requisições simultâneas
locust -f tests/load_test.py --host=http://localhost:8000
```

---

## 📅 Timeline de Implementação

| Fase | Período | Tarefas | Estimativa |
|------|---------|---------|-----------|
| **1** | 2026-04-22 | BUG-001, BUG-003, BUG-005 | 4h |
| **2** | 2026-04-23~24 | BUG-002, BUG-004, BUG-007 | 6h |
| **3** | 2026-04-24~25 | BUG-006, BUG-008, BUG-009 | 5h |
| **4** | 2026-04-26+ | Tests, Monitoring, Docs | 8h |
| **TOTAL** | | | **23h** |

---

## 🎯 Critérios de Sucesso

- ✅ Chat endpoint retorna `resposta` válida 100% das vezes
- ✅ Sem requests pendentes (timeout < 15s)
- ✅ Sem erros não tratados (logging completo)
- ✅ API passa em suite de testes (coverage > 80%)
- ✅ Documentação atualizada
- ✅ Deploy testing em staging antes de prod

---

## 📝 Notas

1. **Debugging do erro atual**: Verifique logs de `/chat` endpoint com logging.DEBUG
2. **Views críticas**: Rodar `criar_views_agro.sql` antes de deploy
3. **Rate limiting**: Considerar implementar rate limiting do lado do servidor
4. **Async/Await**: Considerar reescrever em async para melhor escalabilidade

---

**Próximos Passos Imediatos:**
1. Implementar validação de resposta (BUG-001) ← HOJE
2. Adicionar logging (BUG-003) ← HOJE
3. Validar env vars (BUG-005) ← HOJE
4. Rodar testes manuais de chat ← HOJE
