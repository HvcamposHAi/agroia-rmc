# Análise e Otimização do Projeto AgroIA-RMC

**Data:** 2026-04-21  
**Estado Atual:** 30.7k linhas de código + ~450 scripts de teste/debug + 24 docs de auditoria

---

## 📊 Estado do Projeto

### Inflação de Código
```
✗ 106 arquivos Python na raiz (deveria ser <15)
✗ 24 documentos markdown (deveria ser 1-2 principais + 1 técnico)
✗ Múltiplas versões de scripts: 
  - coleta_auto_v2.py, v3, v4, v5, + coleta_automatica.py + coleta_final.py
  - etapa2_itens_v4 a v9 (6 versões)
  - etapa3_FINAL, etapa3_agro_filtrado, etapa3_com_retry, etc
  - debug_etapa2_v2, v3, v4 + debug_detalhe + debug_pesquisa...
✗ Documentação desorganizada: AUDITORIA_*.md, DIAGNOSTICO_*.md, CHECKLIST_*.md repetindo
```

### Core Funcional (O que REALMENTE existe)
```
✅ API FastAPI (/api/main.py) - Chat RAG para licitações
✅ Chat Agent (/chat/agent.py) - Integração Claude + RAG
✅ Supabase DB (/chat/db.py) - Conexão ao banco
✅ Etapa 2 Principal (etapa2_itens_v9.py) - Extração de itens/fornecedores/empenhos
✅ Etapa 3 Principal (etapa3_producao.py) - Download de PDFs
✅ Classificação Agro (enriquecer_classificacao.py) - ML para categorização
```

---

## 🗑️ O QUE DELETAR (Imediatamente)

### Categoria 1: Scripts de Debug/Teste Obsoletos
**Impacto: 0 funcionalidade perdida**
```
debug_*.py (13 arquivos)
├─ debug_detalhe.py
├─ debug_etapa2.py, debug_etapa2_v2, v3, v4
├─ debug_html.py
├─ debug_pesquisa.py
├─ debug_processo.py
├─ debug_select.py

diag_*.py (7 arquivos)
├─ diag_completo.py
├─ diag_formato.py
├─ diag_paginacao.py

diagnostico_*.py (versões antigas - manter apenas diagnostico_portal.py)
├─ diagnostico_detalhe.py ✗
├─ diagnostico_download.py ✗
├─ diagnostico_playwright.py ✗
├─ diagnostico_v2.py ✗
└─ MANTER: diagnostico_portal.py (verificação de conectividade)
```
**Total: ~25 arquivos**

### Categoria 2: Versões Antigas de Scripts de Coleta
**Impacto: 0 funcionalidade (versão consolidada: etapa2_itens_v9.py, etapa3_producao.py)**
```
Coleta Automática:
├─ coleta_automatica.py ✗
├─ coleta_auto_v2.py ✗
├─ coleta_auto_v3.py ✗
├─ coleta_auto_v4.py ✗
├─ coleta_auto_v5.py ✗
└─ MANTER: coleta_criticos.py (caso especial: 24 licitações críticas)

Etapa 2 (Itens/Fornecedores/Empenhos):
├─ etapa2_corrigido.py ✗
├─ etapa2_detalhes.py ✗
├─ etapa2_itens_playwright.py ✗
├─ etapa2_itens_v4.py ✗
├─ etapa2_itens_v5.py ✗
├─ etapa2_itens_v6.py ✗
├─ etapa2_itens_v7.py ✗
├─ etapa2_itens_v8.py ✗
├─ etapa2_limpar_recoletar.py ✗
├─ etapa2_simples.py ✗
├─ etapa2_v2.py ✗
└─ MANTER: etapa2_itens_v9.py (versão estável)

Etapa 3 (PDFs):
├─ etapa3_agro_filtrado.py ✗
├─ etapa3_agro_simplificado.py ✗
├─ etapa3_coleta_faltantes.py ✗
├─ etapa3_com_retry.py ✗
├─ etapa3_corrigido.py ✗
├─ etapa3_direto.py ✗
├─ etapa3_pdf_valida.py ✗
├─ etapa3_recoletar_faltantes.py ✗
└─ MANTER: etapa3_producao.py (versão estável com checkpoint)
```
**Total: ~30 arquivos**

### Categoria 3: Scripts de Análise Pontuais (Auditoria)
**Impacto: 0 funcionalidade (foram estudos)**
```
auditoria_*.py (2 arquivos)
├─ auditoria_avancada.py ✗
├─ auditoria_documentos_agro.py ✗
├─ auditoria_queries.sql ✗
└─ auditoria_queries_corrigidas.sql ✗

Análises pontuais:
├─ analisar_detalhe.py ✗
├─ analisar_html.py ✗
├─ capturar_detalhe.py ✗
├─ capturar_pagina2.py ✗
├─ check_table_schema.py ✗
├─ encontrar_com_documentos.py ✗
└─ verificar_*.py (todos os verificar_*.py) ✗

Query builders/testers:
└─ teste_*.py (todos) ✗
```
**Total: ~20 arquivos**

### Categoria 4: Documentação Desorganizada
**Impacto: Confusão (consolidar em 2 arquivos)**
```
❌ DELETE ESTAS (repetições/obsoletas):
├─ ALERTAS_AUDITORIA.md (achados já em AUDITORIA_ACHADOS.md)
├─ AUDITORIA_ACHADOS.md (consolidar em README.md)
├─ AUDITORIA_GUIA.md (consolidar em CLAUDE.md)
├─ CHECKLIST_AUDITORIA.md (consolidar em README.md)
├─ DIAGNOSTICO_EMPENHOS.md (obsoleto)
├─ ESTRUTURA_EMPENHOS_DESCOBERTA.md (redundante)
├─ EVOLUCAO_AGENTE.md (histórico, mover a anexo)
├─ FRONTEND_SETUP.md (se frontend estiver parado)
├─ FRONT_INSTRUCTIONS.md (se frontend estiver parado)
├─ GUIA_AMBIENTE_DEV.md (consolidar em README.md)
├─ GUIA_TESTE_HOTFIXES.md (obsoleto)
├─ INSIGHTS_DISSERTACAO.txt (histórico)
├─ LISTA_ACOES_PRIORITARIAS.md (obsoleto)
├─ PROXIMOS_PASSOS.md (obsoleto)
├─ README_FINAL.md (consolidar em README.md)
├─ RELATORIO_COLETA.txt (histórico)
├─ RELATORIO_DISSERTACAO.md (histórico)
├─ REGISTRO_FRONT.md (se frontend parado)
├─ SESSAO_AUDITORIA_RESUMO.md (consolidar)
├─ SETUP_AGENTE.md (consolidar em README.md)
├─ SETUP_GOOGLE_DRIVE.md (consolidar em .env.example)
└─ SYSTEM_STATUS.md (dinâmico, remover)
```
**Total: ~20 documentos → Consolidar em 2**

---

## ✅ O QUE MANTER (Core Essencial)

### Estrutura Base
```
agroia-rmc/
├── api/
│   ├── main.py ✅ (FastAPI, endpoints de chat)
│   └── __init__.py
├── chat/
│   ├── agent.py ✅ (Agente Claude + RAG)
│   ├── db.py ✅ (Conexão Supabase)
│   ├── tools.py ✅ (Ferramentas do agente)
│   ├── prompts.py ✅ (Prompts RAG)
│   └── __init__.py
├── tests/ ✅ (Testes unitários, se existirem)
├── .env ✅ (Variáveis de ambiente)
├── .env.example ✅ (Template seguro)
├── .gitignore ✅
├── CLAUDE.md ✅ (Instruções de projeto - ATUAL)
├── README.md ✅ (Setup + uso)
└── requirements.txt ✅ (Dependências Python)
```

### Scripts de Produção (Apenas 3)
```
✅ etapa2_itens_v9.py
   └─ Extrai: itens, fornecedores, participações, empenhos
   └─ Checkpoint: coleta_checkpoint.json
   └─ Log: coleta_producao.log

✅ etapa3_producao.py
   └─ Download de PDFs do portal
   └─ Checkpoint: coleta_checkpoint.json
   └─ Log: coleta_producao.log

✅ enriquecer_classificacao.py
   └─ Classificação agrícola de itens
```

### Scripts Diagnóstico (Apenas 2)
```
✅ diagnostico_portal.py (teste de conectividade)
✅ verificar_status_db.py (checagem de tabelas)
```

### Configuração Essencial
```
✅ CLAUDE.md (MANTER - está correto)
✅ .env (MANTER - com secrets)
✅ .env.example (CRIAR - sem secrets)
✅ requirements.txt (MANTER/CRIAR)
✅ coleta_checkpoint.json (dados de runtime)
✅ coleta_producao.log (log de runtime)
```

---

## 🎯 Plano de Ação (Implementação)

### Fase 1: Limpeza de Código (30 min)
```bash
# Deletar versões antigas de etapa2
rm etapa2_itens_v{4,5,6,7,8}.py
rm etapa2_corrigido.py etapa2_detalhes.py etapa2_*_v2.py etapa2_simples.py
rm etapa2_limpar_recoletar.py etapa2_itens_playwright.py

# Deletar versões antigas de etapa3
rm etapa3_{agro_filtrado,agro_simplificado,coleta_faltantes,com_retry,corrigido,direto,pdf_valida,recoletar_faltantes}.py

# Deletar coleta automática (usar etapa2_itens_v9)
rm coleta_{auto_v2,auto_v3,auto_v4,auto_v5,automatica,final,headless,itens_empenhos,simples}.py

# Deletar debug
rm debug_*.py diag_*.py

# Deletar diagnósticos antigos (manter apenas diagnostico_portal.py)
rm diagnostico_{detalhe,download,empenhos,playwright,paginacao,v2,tabelas}.py
rm diagnostico_portal_v2.py

# Deletar análises pontuais
rm {analisar,capturar,check_table_schema,encontrar_com_documentos,teste_,verificar_}.py
rm auditoria_{avancada,documentos_agro}.py
```

### Fase 2: Consolidação de Docs (20 min)
```
1. Manter: CLAUDE.md (instruções de projeto)
2. Manter: README.md (setup + guia de uso)
3. Criar: .env.example (template seguro)
4. Deletar: Todos os outros 20 .md
```

### Fase 3: Criar requirements.txt
```bash
fastapi==0.104.1
uvicorn==0.24.0
pydantic==2.5.0
python-dotenv==1.0.0
supabase==2.4.0
anthropic==0.21.0
playwright==1.40.0
beautifulsoup4==4.12.2
google-api-python-client==1.12.1
google-auth-httplib2==0.2.0
google-auth-oauthlib==1.2.0
```

### Fase 4: Criar .env.example
```
SUPABASE_URL=https://rsphlvcekuomvpvjqxqm.supabase.co
SUPABASE_KEY=<your-key-here>
ANTHROPIC_API_KEY=<your-key-here>
GOOGLE_DRIVE_FOLDER_ID=<your-folder-id>
```

---

## 📈 Resultado Esperado

### Antes
```
Code: 30.7k linhas
Scripts: 106 arquivos Python
Docs: 24 markdown
Clutter: ~55 arquivos de teste/debug/versões antigas
Tempo setup: Confuso qual versão usar
```

### Depois
```
Code: ~8-10k linhas (core + API + chat)
Scripts: 5 arquivos Python (3 produção + 2 diagnóstico)
Docs: 3 arquivos (CLAUDE.md, README.md, .env.example)
Clutter: 0 arquivos desnecessários
Tempo setup: Claro e estruturado
Manutenibilidade: ⬆️⬆️⬆️
```

---

## ⚠️ Verificações Antes de Deletar

```python
# 1. Confirmar que etapa2_itens_v9.py está funcional
# 2. Confirmar que etapa3_producao.py tem checkpoint/resume
# 3. Confirmar que coleta_criticos.py é diferente (sim, trata 24 casos críticos)
# 4. Backup git: git add -A && git commit -m "backup: antes da limpeza"
# 5. Verificar que não há refs a arquivos deletados em git
```

---

## 🚀 Próximas Etapas (Após Limpeza)

1. **Revisar API** (`api/main.py`): Remover endpoints desnecessários
2. **Revisar Chat** (`chat/agent.py`): Consolidar tools e prompts
3. **Adicionar testes**: `tests/test_api.py`, `tests/test_agent.py`
4. **CI/CD**: `.github/workflows/test.yml` (opcional)
5. **Documentação técnica**: Atualizar CLAUDE.md com endpoint docs

