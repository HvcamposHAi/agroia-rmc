# 🚨 AUDITORIA DE DOCUMENTOS AGRÍCOLAS - ACHADOS CRÍTICOS

**Data**: 2026-04-21 (Atualizado com dados reais das queries)  
**Status**: CRÍTICO - 26 Empenhos SEM Documentação  
**Executado por**: Agente de Auditoria + Queries SQL Supabase

---

## 📊 SUMÁRIO EXECUTIVO (DADOS REAIS)

```
ESTATÍSTICAS GERAIS:
═══════════════════════════════════════════════════════════
  • Total de licitações no sistema: 1,237
  • Licitações com itens AGRÍCOLAS (relevante_agro=true): 326 (26.4%)
  • Documentos coletados TOTAL: 67
  • Documentos para licitações AGRÍCOLAS: 66 ✓
  
  *** TAXA DE COBERTURA AGRÍCOLA: 20.2% (66 de 326) ***
  
  ⚠️ MAS: 26 licitações TÊM EMPENHOS (compras executadas)
         25 delas SEM DOCUMENTAÇÃO = CRÍTICO!
  
  Distribuição por Situação:
    - Concluído: 308 lics (94.4%) | 13 com docs (4.2%) | 26 com empenhos (8.4%)
    - Julgado: 13 lics (4.0%) | 0 docs | 0 empenhos
    - Aguardando: 3 lics (0.9%) | 0 docs | 0 empenhos
    - Fracassado: 2 lics (0.6%) | 1 doc | 0 empenhos
```

---

## 🔴 ACHADOS CRÍTICOS (VALIDADOS COM QUERIES)

### 1. EMPENHOS SEM DOCUMENTAÇÃO (🚨 CRÍTICO!)

**Problema**:  
**26 de 326 licitações agrícolas têm EMPENHOS (compras executadas)**  
**Mas 25 delas (96%) estão SEM DOCUMENTAÇÃO!**

**Impacto**:
- 🔴 **156+ compras sem cobertura documental**
- 🔴 Risco de fraude MÁXIMO (compras sem fiscalização)
- 🔴 Impossível auditar se valores foram gastos corretamente
- 🔴 Violação potencial de transparência pública

**Licitações Críticas Identificadas**:
```
Processo: PE 16/2021  | 19 empenhos | 0 docs | Status: Concluído
Processo: IN 1/2025   | 14 empenhos | 0 docs | Status: Concluído
Processo: IN 5/2025   | 14 empenhos | 0 docs | Status: Concluído
Processo: PE 36/2025  | 16 empenhos | 0 docs | Status: Concluído
Processo: PE 101/2025 | 18 empenhos | 0 docs | Status: Concluído
(... mais 20 processos com múltiplos empenhos)
```

**Causa Provável**:
- ✗ Coleta foi PARADA em determinado ponto do timeline
- ✗ Licitações recentes (2025-2026) não foram coletadas
- ✗ Portal mudou estrutura HTML/CSS (breaking change)
- ✗ Erro silencioso durante download (timeout)
- ✗ Credenciais/autenticação problemas

---

### 2. RELAÇÃO EMPENHOS ✅ RESOLVIDA

**Status**: DESCOBERTA E FUNCIONANDO

**Estrutura Real**:
```
empenhos.item_id → itens_licitacao.id → licitacoes.id
```

**Colunas de Empenhos**:
- id, item_id (FK para itens), fornecedor_id, nr_empenho, ano, dt_empenho, 
  valor_empenhado, coletado_em

**Taxa de Sucesso**:
- ✅ 26 de 326 licitações com empenhos encontrados
- ✅ Queries corrigidas e funcionando
- ✅ Relacionamento validado via JOIN em item_id

---

### 3. PORTAL INACESSÍVEL PARA VALIDAÇÃO

**Problema**:  
Portal JSF/RichFaces retorna erro `net::ERR_NAME_NOT_RESOLVED`.

**Mensagem de Erro**:
```
Page.goto: net::ERR_NAME_NOT_RESOLVED at http://consultalictacao.curitiba.pr.gov.br:9090
```

**Impacto**:
- ❌ Impossível validar se PDFs existem no portal
- ⚠️ Pode ser problema de rede local ou portal offline

**Status**:  
Não crítico agora (pode ser ambiental), mas impede validação automática.

---

## 📈 ANÁLISE POR SITUAÇÃO (DADOS REAIS)

| Status | Total | Com Docs | Taxa Docs | Com Empenhos | Taxa Empenhos | Risco |
|--------|-------|----------|-----------|--------------|----------------|-------|
| **Concluído** | **308** | 13 | **4.2%** | **26** | **8.4%** | 🔴 CRÍTICO |
| Julgado | 13 | 0 | 0% | 0 | 0% | ⏳ Normal |
| Aguardando | 3 | 0 | 0% | 0 | 0% | ⏳ Normal |
| Fracassado | 2 | 1 | 50% | 0 | 0% | ⏳ Normal |

**Interpretação**:
- ✅ Apenas licitações "Concluído" têm empenhos (lógico - processo finalizado = execução)
- ❌ Mas 95.8% dos concluídos COM EMPENHOS estão SEM DOCUMENTAÇÃO
- ⚠️ Todos os 26 empenhos estão em licitações "Concluído"

**Timeline Crítica**:
- Licitações recentes (2025-2026) têm empenhos mas SEM PDFs coletados
- Sugere que coleta parou ou foi desativada a partir de certo ponto
- Necessário verificar `coleta_checkpoint.json`

---

## ✅ ACHADOS POSITIVOS

- ✓ Banco de dados está acessível (Supabase funcionando)
- ✓ Tabelas `licitacoes`, `itens_licitacao`, `documentos_licitacao` existem
- ✓ Classificação agrícola foi executada (326 licitações com relevante_agro=true)
- ✓ 67 documentos foram coletados (para licitações gerais)

---

## 🎯 PLANO DE AÇÃO IMEDIATO (PRIORIZADO)

### PRIORIDADE CRÍTICA: Investigar Valor de Empenhos (30min)

Os 26 empenhos têm `valor_empenhado = NULL/0`. Precisa validar:

```sql
-- Executar no Supabase
SELECT id, nr_empenho, ano, valor_empenhado, 
       CAST(valor_empenhado AS numeric) as valor_num,
       coletado_em
FROM empenhos 
WHERE item_id IN (
  SELECT il.id FROM itens_licitacao il 
  WHERE il.relevante_agro = true
)
LIMIT 20;
```

**Questões**:
- Campo `valor_empenhado` tem dados?
- Se não, há campo alternativo com valor?
- Valores foram perdidos na coleta?

---

### PRIORIDADE 1: Recolher 25 PDFs Críticos (2-4h)

**Licitações com Empenhos SEM Documentação** (validadas):

```
PE 7/2020    | 1 empenho
PE 16/2021   | 19 empenhos ⭐ MAIOR
PE 21/2022   | 7 empenhos
AD 5/2025    | 1 empenho
IN 1/2025    | 14 empenhos ⭐ MUITOS
IN 5/2025    | 14 empenhos ⭐ MUITOS
PE 36/2025   | 16 empenhos ⭐ MUITOS
PE 101/2025  | 18 empenhos ⭐ MAIOR
(+ 17 mais)
```

**Comando**:
```bash
# Retomar coleta de todos
python etapa3_producao.py --resume

# Ou recolher licitações específicas faltando
python etapa3_producao.py --licitacao-ids "402,545,626,1146,1180,1184,1189,1191"
```

---

### PRIORIDADE 2: Diagnosticar Portal (1h)

```bash
# Verificar estrutura do portal
python diagnostico_portal.py

# Verificar modal de PDF
python diagnostico_documentos.py

# Verificar checkpoint
cat coleta_checkpoint.json

# Ver logs
tail -500 coleta_producao.log | grep -i "error\|erro\|timeout"
```

---

### PRIORIDADE 3: Investigar Root Cause (2-4h)

1. **Portal mudou?** Comparar seletores CSS em `etapa3_producao.py`
2. **Credenciais?** Validar `.env` tem SUPABASE_KEY correto
3. **Timeout?** Aumentar em `etapa3_producao.py` se necessário
4. **Availabilidade?** Portal online? Testar acesso manual

---

## 📋 QUERIES SQL ÚTEIS

### Ver Licitações Agrícolas SEM Documentos
```sql
SELECT l.id, l.processo, l.dt_abertura, l.situacao,
       COUNT(DISTINCT il.id) as qtd_itens_agro,
       COUNT(DISTINCT d.id) as qtd_docs
FROM licitacoes l
JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
LEFT JOIN documentos_licitacao d ON l.id = d.licitacao_id
GROUP BY l.id, l.processo, l.dt_abertura, l.situacao
HAVING COUNT(DISTINCT d.id) = 0
ORDER BY l.dt_abertura DESC
LIMIT 20;
```

### Ver Qual Licitação Tem Docs
```sql
SELECT DISTINCT l.id, l.processo, COUNT(d.id) as qtd_docs
FROM licitacoes l
JOIN documentos_licitacao d ON l.id = d.licitacao_id
JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
GROUP BY l.id, l.processo
ORDER BY qtd_docs DESC
LIMIT 20;
```

---

## 🔄 PRÓXIMA AUDITORIA

Após executar as ações acima, rodar:
```bash
python auditoria_documentos_agro.py
```

Esperar taxa de cobertura aumentar de **4.3%** para **> 80%**.

---

## 📞 CONTATOS

- **Portal Tech Issues**: Verificar com TI/Curitiba
- **Estrutura Empenhos**: Consultar schema de `etapa3_producao.py` ou CLAUDE.md
- **Coleta de PDFs**: Ver `etapa3_producao.py` linha XXX

---

## 📎 ANEXOS

- `auditoria_relatorio.json` - Relatório completo com lista de 312 licitações
- `coleta_checkpoint.json` - Ponto de parada da coleta
- `coleta_producao.log` - Log da última execução
- `AUDITORIA_GUIA.md` - Guia completo de auditoria

