# 🔍 Guia de Auditoria - Consistência PDFs vs Licitações Agrícolas

## Visão Geral

Este agente de auditoria valida a **consistência entre documentos PDFs extraídos e licitações agrícolas**, gerando alertas categorizados para:
- **ERRO_BD**: Inconsistências técnicas na base de dados
- **INCONSISTENCIA_PORTAL**: PDFs indisponíveis/não encontrados no portal
- **QUALIDADE**: Problemas de qualidade nos dados coletados

### Foco
Análise exclusiva de licitações classificadas como `relevante_agro=true` via view **vw_itens_agro**.

---

## 📋 Arquivos Criados

### 1. `auditoria_documentos_agro.py` (Versão Simples)
**Uso**: Análise rápida com validação básica
```bash
python auditoria_documentos_agro.py
```

**O que faz**:
- Conta licitações agrícolas vs documentos coletados
- Identifica licitações sem documentação
- Analisa cobertura de empenhos
- Gera `auditoria_relatorio.json`

**Ideal para**: Verificação rápida de estado da cobertura

---

### 2. `auditoria_avancada.py` (Versão Completa)
**Uso**: Análise profunda com múltiplas fases
```bash
python auditoria_avancada.py
```

**Fases**:
1. **BD**: Executa 6 queries SQL detalhadas no Supabase
   - Sumário de cobertura
   - Taxa de cobertura por situação
   - Licitações sem documentos
   - Empenhos sem documentação
   - Detecção de duplicados
   
2. **PORTAL**: Validação Playwright em amostra de licitações problemáticas
   - Acessa portal JSF/RichFaces
   - Valida acessibilidade
   - Verifica disponibilidade de PDFs

3. **RELATÓRIO**: Consolidação com resumo executivo
   - Estatísticas agregadas
   - Alertas categorizados
   - Recomendações

**Output**: `auditoria_relatorio_YYYYMMDD_HHMMSS.json`

**Ideal para**: Diagnóstico completo e comunicação com stakeholders

---

### 3. `auditoria_queries.sql`
**Uso**: Executar diretamente no Supabase SQL Editor

Contém 10 queries prontas para copiar/colar:
- Q1: Sumário geral
- Q2: Licitações sem documentos (ERRO_BD)
- Q3: Taxa de cobertura por situação
- Q4: Análise por categoria agrícola
- Q5: Inconsistência portal
- Q6: Distribuição temporal
- Q7: Duplicados/qualidade
- Q8: Empenhos vs documentos
- Q9: Sumário executivo de alertas
- Q10: Relatório detalhado (TOP 50)

**Acesso**: 
1. Ir a: https://supabase.com → Projeto → SQL Editor
2. Copiar/colar a query desejada
3. Executar (Ctrl+Enter ou botão "Run")

---

## 🚀 Guia de Uso

### Verificação Rápida (< 1 minuto)
```bash
# Execute a versão simples
python auditoria_documentos_agro.py

# Abra o relatório gerado
cat auditoria_relatorio.json
```

### Diagnóstico Completo (2-5 minutos)
```bash
# Execute a versão avançada
python auditoria_avancada.py

# Verificar sumário
grep -A 20 '"resumo"' auditoria_relatorio_*.json
```

### Análise Detalhada (via SQL)
1. Abra Supabase SQL Editor
2. Execute `Q10: Relatório Detalhado` para ver TOP 50 licitações com problemas
3. Para cada problema, execute `Q2` ou `Q5` para contexto

---

## 📊 Interpretando os Resultados

### Taxa de Cobertura
```
Taxa de Cobertura = (Licitações com Documentos / Licitações Agrícolas) × 100
```
- **> 90%**: Excelente
- **80-90%**: Bom (investigar os 10% faltantes)
- **< 80%**: Preocupante (problemas de coleta ou portal)

### Alertas Críticos
Licitações com **empenhos (compras executadas) mas SEM documentação**:
```json
{
  "processo": "000001/2019",
  "qtd_empenhos": 3,
  "valor_R$": 45000.00,
  "alerta": "CRÍTICO: Compra executada sem documentação"
}
```
**Ação**: Investigar no portal se PDF está disponível ou se download falhou

### Alertas Graves
Licitações **finalizadas (Concluído) mas SEM documentação**:
```json
{
  "processo": "000002/2019",
  "situacao": "Concluído",
  "alerta": "GRAVE: Finalizada sem documentação"
}
```
**Ação**: Verificar se o portal disponibiliza PDF; se sim, recolhê-lo

---

## 🔧 Troubleshooting

### "RPC execute_query não funciona"
As versões Python contêm fallback automático. Se houver erro:
1. Execute as queries SQL direto no Supabase
2. Ou modifique o script para usar `sb.table().select()` diretamente

### "Playwright timeout ao validar portal"
O portal pode estar lento ou offline. Para validar manualmente:
1. Acesse: http://consultalictacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/
2. Procure pela licitação (processo)
3. Verifique se há modal de PDF disponível

### "Nenhuma licitação encontrada"
Verifique:
1. View `vw_itens_agro` existe no Supabase
2. Há itens com `relevante_agro=true` na tabela `itens_licitacao`
```sql
SELECT COUNT(*) FROM itens_licitacao WHERE relevante_agro = true;
```

---

## 📈 Fluxo de Ação Recomendado

```
┌─────────────────────────────┐
│  Executar Auditoria         │
│  (auditoria_avancada.py)    │
└──────────┬──────────────────┘
           │
     ┌─────┴──────┬──────────┐
     │             │          │
     ▼             ▼          ▼
CRÍTICO      GRAVE       QUALIDADE
(Empenho   (Concluído   (Duplicados)
 sem docs)  sem docs)
     │             │          │
     ▼             ▼          ▼
┌──────────────────────────────┐
│ 1. Validar no Portal         │
│ (SQL Q2, Q5)                 │
└──────────┬───────────────────┘
           │
     ┌─────┴──────┐
     │             │
     ▼             ▼
PDF Existe?   Não Existe?
     │             │
     ▼             ▼
Recolher    Marcar como
com         "Não
etapa3_     Disponível
producao    no Portal"
.py
```

---

## 💾 Automatizar Auditoria

### Executar diariamente (Linux/Mac)
```bash
# Adicionar ao crontab
0 6 * * * cd /path/to/agroia-rmc && python auditoria_avancada.py >> audit.log 2>&1
```

### Executar semanalmente (Windows Task Scheduler)
1. Abrir Task Scheduler
2. "Criar Tarefa Básica"
3. Trigger: Semanal (ex: domingo 6am)
4. Action: `C:\python\python.exe C:\path\auditoria_avancada.py`

---

## 📞 Alertas e Notificações

### Enviar Alertas por Email (Implementação Futura)
```python
# No script auditoria_avancada.py, adicionar ao final:
if resumo["alertas_criticos"] > 0:
    enviar_email(
        destinatario="admin@example.com",
        assunto=f"⚠️ {resumo['alertas_criticos']} Licitações com Empenhos Sem Documentação",
        corpo=f"Ver: auditoria_relatorio_{timestamp}.json"
    )
```

---

## 🎯 KPIs Recomendados

1. **Taxa de Cobertura Geral** (meta: > 90%)
   ```sql
   SELECT ROUND(100.0 * COUNT(DISTINCT d.licitacao_id) / 
                NULLIF(COUNT(DISTINCT il.licitacao_id), 0), 1)
   FROM itens_licitacao il
   LEFT JOIN documentos_licitacao d ON il.licitacao_id = d.licitacao_id
   WHERE il.relevante_agro = true;
   ```

2. **Licitações Críticas Sem Docs** (meta: 0)
   ```sql
   SELECT COUNT(DISTINCT l.id)
   FROM licitacoes l
   WHERE EXISTS (SELECT 1 FROM empenhos WHERE licitacao_id = l.id)
   AND NOT EXISTS (SELECT 1 FROM documentos_licitacao WHERE licitacao_id = l.id);
   ```

3. **Tempo Médio Entre Coleta e Conclusão** (meta: < 30 dias)
   ```sql
   SELECT AVG(EXTRACT(DAY FROM l.situacao_data - d.coletado_em))
   FROM licitacoes l
   JOIN documentos_licitacao d ON l.id = d.licitacao_id
   WHERE l.situacao = 'Concluído';
   ```

---

## 📝 Notas Importantes

- **Foco**: A auditoria analisa **apenas licitações com `relevante_agro=true`**
- **Empenhos**: Máx ~36% de cobertura (esperado - Dispensas não têm empenhos no portal)
- **Portal**: PDFs podem estar no portal mas não ter sido baixados (nova coleta necessária)
- **Duplicados**: Investigar antes de deletar - podem ser versões atualizadas do mesmo doc

---

## 📞 Suporte

Para questões sobre:
- **Estrutura de dados**: Ver CLAUDE.md (schema, views)
- **Coleta de PDFs**: Ver etapa3_producao.py (Playwright implementation)
- **Classificação agrícola**: Ver enriquecer_classificacao.py

