# ✅ Checklist de Auditoria - AgroIA-RMC

**Gerado**: 2026-04-21  
**Objetivo**: Rastrear implementação de hotfixes e ações

---

## 🔴 FASE CRÍTICA (Hoje)

- [x] **Auditoria**: Identificar problema (chat retorna resposta vazia)
- [x] **Análise**: Root cause encontrado (BUG-001 no endpoint)
- [x] **Hotfixes**: Implementar 5 hotfixes críticos
  - [x] BUG-001: Response validation
  - [x] BUG-003: Error logging
  - [x] BUG-005: Env validation
  - [x] BUG-002: Agent timeout
  - [x] BUG-006: Input sanitization
- [x] **Documentação**: Criar 4 docs de auditoria
  - [x] AUDITORIA_CODIGO_20260421.md
  - [x] GUIA_TESTE_HOTFIXES.md
  - [x] BACKLOG_ACOES.json
  - [x] RESUMO_AUDITORIA_ACOES.md
  - [x] LISTA_ACOES_PRIORITARIAS.md
  - [x] CHECKLIST_AUDITORIA.md

**Status**: 🟡 AGUARDANDO TESTES

---

## 🔵 TESTES (Próximo - 30 min)

### Teste Unitário
- [ ] `python tests/test_critical_hotfixes.py` executa sem erro
- [ ] Todos os asserts passam
- [ ] Nenhum módulo falta

### Teste API
- [ ] Iniciar servidor: `python -m uvicorn api.main:app --reload`
- [ ] Verificar startup sem RuntimeError
- [ ] Testar `/health`: deve retornar status 200
- [ ] Testar `/chat` com curl: deve retornar JSON com `resposta` não-vazia
- [ ] Verificar logs: deve haver `INFO: Chat response successful`
- [ ] Nenhuma mensagem `ERROR` no servidor

### Teste Frontend
- [ ] Iniciar: `npm --prefix agroia-frontend run dev`
- [ ] Acessar: http://localhost:5173
- [ ] Clicar em sugestão: "Qual a demanda de alface?"
- [ ] ❌ ANTES: "Sem resposta do servidor"
- [ ] ✅ DEPOIS: Texto real da resposta
- [ ] Enviar 3 perguntas diferentes
- [ ] Verificar histórico não corrompe

### Teste de Sanitização
- [ ] Enviar input com `'; DROP TABLE--` → deve ser rejeitado
- [ ] Enviar string longa (500 chars) → deve ser truncada
- [ ] Logs devem mostrar aviso de input malicioso

---

## 🟢 COMMIT (Após testes passarem)

- [ ] `git status` mostrar somente arquivos esperados
- [ ] `git diff api/main.py` revisar mudanças
- [ ] `git diff chat/agent.py` revisar mudanças
- [ ] `git diff chat/tools.py` revisar mudanças
- [ ] Criar commit: 
  ```bash
  git commit -m "fix: implement critical hotfixes for chat API
  
  - BUG-001: Response validation in /chat endpoint
  - BUG-003: Structured error logging
  - BUG-005: Environment variables validation
  - BUG-002: Agent loop timeout (15s)
  - BUG-006: Tool input sanitization
  
  Fixes 'Sem resposta do servidor' error"
  ```
- [ ] Push para branch: `git push origin hotfix/chat-response`
- [ ] Criar PR no GitHub
- [ ] Adicionar descrição em português

---

## 🟡 SEMANA 1 (2026-04-22 a 2026-04-25)

### BUG-004: Connection Pooling
- [ ] Implementar async client em `chat/db.py`
- [ ] Adicionar reconnection logic
- [ ] Testar 20 requisições paralelas
- [ ] Verificar sem timeouts ou deadlocks
- [ ] Commit & PR

### BUG-007: Timeout Validation
- [ ] Verificar timeout=15 está em `client.messages.create()`
- [ ] Testar requisição trava após 15s
- [ ] Log deve mostrar timeout error
- [ ] Commit confirmado

### BUG-008: Auditoria Error Handling
- [ ] Adicionar try/except em `/auditoria/executar`
- [ ] Validar views existem antes de usar
- [ ] Testar com views faltantes
- [ ] Retornar erro 500 com mensagem clara
- [ ] Commit & PR

### BUG-009: Document Views
- [ ] Criar arquivo `VIEWS_REQUIRED.md` listando views críticas
- [ ] Adicionar função `validate_db_schema()` em `chat/db.py`
- [ ] Rodar `criar_views_agro.sql` em staging
- [ ] Documentar que views são pré-requisito para deploy
- [ ] Commit

### Code Quality
- [ ] Executar `pytest tests/test_critical_hotfixes.py`
- [ ] Verificar coverage > 60%
- [ ] Remover comentários deixados para debug
- [ ] Revisar nomes de variáveis (português/inglês consistente)

---

## 🟢 SEMANA 2-3 (2026-04-26+)

### Testing
- [ ] Criar `tests/test_chat_integration.py`
- [ ] Criar `tests/test_tools.py`
- [ ] Executar suite completa: `pytest tests/ -v --cov`
- [ ] Verificar coverage > 80%
- [ ] Setup CI/CD para rodar testes automaticamente

### Monitoring
- [ ] Adicionar `/health/detailed` endpoint
- [ ] Integrar com Sentry (se disponível)
- [ ] Configurar alertas para ERROR logs
- [ ] Testar alertas funcionam

### Documentation
- [ ] Escrever README.md atualizado
- [ ] Swagger docs para todas as APIs
- [ ] Exemplos de curl para cada endpoint
- [ ] Troubleshooting guide

### Performance
- [ ] Testes de carga: 10 requisições simultâneas
- [ ] Testes de carga: 50 requisições em 1 minuto
- [ ] Otimização se necessário

---

## 📊 Métricas

### Antes da Auditoria
- Chat Success Rate: **0%** (sempre "Sem resposta")
- Error Logging: ❌
- Input Validation: ❌
- Test Coverage: ~30%

### Depois dos Hotfixes (Esperado)
- Chat Success Rate: **100%** (resposta real ou fallback)
- Error Logging: ✅ Stack traces completos
- Input Validation: ✅ SQL injection detectado
- Test Coverage: **>80%**

### Métricas em Desenvolvimento
```
✅ Hotfixes implementados:      5/5
⏳ Testes unitários passando:    ?/8
⏳ Testes integração passando:   ?/5
⏳ Testes E2E passando:          ?/3
⏳ Commits com PR:               0/1
⏳ Issues documentadas:          12/12
```

---

## 🎯 Definição de Sucesso

### ✅ Chat Funcional
- [ ] Endpoint `/chat` retorna resposta sempre
- [ ] Resposta não é vazia
- [ ] Resposta é em português
- [ ] Histórico é persistido

### ✅ Segurança
- [ ] Input SQL injection detectado
- [ ] Strings longas truncadas
- [ ] Env vars validadas no startup

### ✅ Observabilidade
- [ ] Logs têm session_id para rastrear
- [ ] Todos os errors têm stack trace
- [ ] Tempo de resposta < 15s

### ✅ Qualidade
- [ ] Tests > 80% coverage
- [ ] Sem warnings ao fazer lint
- [ ] Documentação atualizada

---

## 🚨 Se Algo Quebrar

### Cenário: "Ainda vejo 'Sem resposta do servidor'"
- [ ] Verificar logs do servidor para ERROR
- [ ] Rodar `python tests/test_critical_hotfixes.py` com `-v`
- [ ] Checar se ANTHROPIC_API_KEY é válida
- [ ] Debugar linha por linha em agent.py

### Cenário: Servidor não inicia
- [ ] Verificar `.env` tem todas as variáveis
- [ ] Rodar `cat .env | grep -E "SUPABASE|ANTHROPIC"`
- [ ] Checar se há erro de import: `python api/main.py`

### Cenário: Testes falham
- [ ] Certificar que está em `/c/Users/hvcam/Meu\ Drive/Pessoal/Mestrado/Dissertação/agroia-rmc`
- [ ] Rodar com `python -m pytest tests/` (não só `pytest`)
- [ ] Verificar se DB está acessível: `python -c "from chat.db import get_supabase_client"`

---

## 📋 Documentos de Referência

| Documento | Leia para... |
|-----------|-------------|
| `AUDITORIA_CODIGO_20260421.md` | Análise técnica completa (12 bugs) |
| `GUIA_TESTE_HOTFIXES.md` | Como testar cada hotfix |
| `RESUMO_AUDITORIA_ACOES.md` | Sumário das mudanças |
| `LISTA_ACOES_PRIORITARIAS.md` | Roadmap de implementação |
| `BACKLOG_ACOES.json` | Backlog em JSON (máquina-legível) |
| `CHECKLIST_AUDITORIA.md` | Este documento |

---

## ✍️ Notas Pessoais

**Problemas Comuns Encontrados**:
1. Response handler esperava `data.resposta` mas recebia undefined
2. Agent loop não tinha fallback para empty response
3. Sem logs estruturados → impossível debugar
4. Env vars não validadas → erro opaco

**Soluções Implementadas**:
1. Validação explícita de resposta no endpoint
2. Fallback responses em todos os error paths
3. Logging com session_id para rastreamento
4. Validação env vars no startup

**Próximos Passos Críticos**:
1. Testar hotfixes HOJE
2. Commit para main AMANHÃ
3. Setup CI/CD testes na SEMANA 2

---

## 🎉 Ao Terminar

- [ ] Marcar todos os checkboxes
- [ ] Atualizar timestamp final
- [ ] Criar issue no GitHub se houver bloqueadores
- [ ] Comemorar! 🎊

---

**Iniciado**: 2026-04-21 19:30  
**Último atualizado**: 2026-04-21 20:15  
**Próxima revisão**: 2026-04-22 09:00

---

## 🔄 Template para Atualizar

Copie e cole abaixo quando precisar atualizar status:

```markdown
## 📅 Update 2026-04-22 09:00

### Testes Completados
- [x] Teste unitário: PASSOU
- [x] Teste API: PASSOU
- [ ] Teste Frontend: EM ANDAMENTO

### Issues Encontrados
1. Timeout de 15s insuficiente para query complexa
2. Connection pool não reutiliza conexão

### Próximos Passos
1. Aumentar timeout para 30s
2. Debug connection pool

### Bloqueadores
- NENHUM
```

---

**Status Global**: 🟡 HOTFIXES IMPLEMENTADOS, AGUARDANDO TESTES
