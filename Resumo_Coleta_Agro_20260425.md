# Resumo da Coleta - Escopo AGRICULTURA EXCLUSIVAMENTE
## AgroIA-RMC: Licitações Agrícolas da SMSAN-FAAC

**Data do Relatório:** 25 de Abril de 2026  
**Período de Escopo:** 30/08/2019 a 08/04/2026  
**Órgão:** SMSAN/FAAC  
**Escopo:** ✅ **APENAS AGRICULTURA (relevante_af=true)**  
**Status:** ✅ **COLETA COMPLETA PARA ESCOPO AGRÍCOLA**

---

## 📊 Resumo Executivo - AGRICULTURA

| Métrica | Resultado |
|---------|-----------|
| **Licitações Agrícolas Coletadas** | 715 |
| **Período Real** | 30/08/2019 a 08/04/2026 |
| **Licitação Mais Recente** | PE 26/2026 (08/04/2026) |
| **Documentos PDFs (Agrícolas)** | 16 |
| **Cobertura de PDFs** | 2,2% (16 de 715) |
| **Status** | ⚠️ PDFs desfocados (90,6% são não-agrícolas) |

---

## 🌾 Escopo do Projeto

### Licitações Totais vs Agrícolas

```
SMSAN/FAAC Total:                1.237 licitações
├─ AGRÍCOLAS (relevante_af=true):    715 (57,8%) ✅ ESCOPO
└─ NÃO-AGRÍCOLAS:                    522 (42,2%) ❌ FORA DO ESCOPO
```

### Distribuição de Licitações Agrícolas por Ano

| Ano | Quantidade | Observação |
|-----|-----------|-----------|
| 2019 | 7 | Início parcial (agosto) |
| 2020 | 28 | Baixa atividade |
| 2021 | 27 | Baixa atividade |
| 2022 | 108 | 🔼 Crescimento |
| 2023 | 133 | 🔼 Forte crescimento |
| 2024 | 193 | 🔼 Pico máximo |
| 2025 | 173 | Mantém nível alto |
| 2026 | 46 | Até 08/04/2026 |

**Total 2022-2026:** 653 licitações (91,3% do volume agrícola)

---

## 📄 Status da Coleta de Documentos (PDFs)

### Problema Identificado ⚠️

A coleta de PDFs **foi desfocada** do escopo agrícola:

```
Total de PDFs Coletados:         171 documentos
├─ Em licitações AGRÍCOLAS:       16 (9,4%) ✅ Relevante
└─ Em licitações NÃO-AGRÍCOLAS:  155 (90,6%) ❌ Fora do escopo
```

### Cobertura Real (Agrícola)

- **Licitações agrícolas com documentos:** 16 de 715 (2,2%)
- **Documentos por licitação agrícola:** 1,0 em média
- **Potencial:** Apenas 2,2% das licitações agrícolas têm PDFs indexados

---

## 🎯 Conclusões

### ✅ Pontos Positivos

1. **Coleta de Licitações:** 100% das 715 licitações agrícolas coletadas
2. **Período Completo:** Dados de 30/08/2019 a 08/04/2026
3. **Dados Estruturados:** Itens (etapa 2) com 99,8% de cobertura
4. **Distribuição Equilibrada:** Crescimento consistente ano a ano

### ⚠️ Problemas Identificados

1. **PDFs Desfocados:** 90,6% dos documentos coletados são de licitações não-agrícolas
2. **Cobertura Mínima:** Apenas 2,2% de cobertura de PDFs para escopo agrícola
3. **Necessidade de Re-coleta:** Focar esforços apenas em licitações com `relevante_af=true`

---

## 🔄 Recomendações

### Curto Prazo (Imediato)

1. **Filtrar Dados Existentes:**
   - Descartar os 155 PDFs de licitações não-agrícolas
   - Manter apenas 16 PDFs relevantes

2. **Usar Script Correto:**
   ```bash
   python dados_atualizados_agro.py --resumo
   ```
   Para sempre consultar dados com `relevante_af=true`

3. **Atualizar Documentação:**
   - CLAUDE.md atualizado com escopo agrícola
   - Dashboard deve filtrar automaticamente por agricultura

### Médio Prazo

1. **Re-coleta de PDFs:**
   - Criar `etapa3_producao_agro.py` que processa apenas `relevante_af=true`
   - Target: 50%+ de cobertura de PDFs para licitações agrícolas

2. **Processamento de Conteúdo:**
   - Extrair texto dos 16 PDFs existentes
   - Indexar chunks textuais para busca semântica (RAG)

### Longo Prazo

1. **Monitoramento Contínuo:**
   - Configurar coleta incremental apenas de licitações agrícolas
   - Ignorar automaticamente licitações não-agrícolas

2. **Análise Agrícola:**
   - Classificar licitações por categoria de produto (frutas, hortifruti, proteína, etc.)
   - Análise de demanda agrícola por produto/categoria

---

## 📋 Dados para Referência

### Últimas 5 Licitações Agrícolas

| Processo | Data | Objeto |
|----------|------|--------|
| PE 26/2026 | 08/04/2026 | AQUISIÇÃO DE AVEIA, FARINHA DE ROSCA, FÓRMULAS INFANTIS... |
| PE 27/2026 | 06/04/2026 | AQUISIÇÃO DE BEBIDA LÁCTEA, LINGUIÇA, QUEIJO MUSSARELA... |
| PE 25/2026 | 25/03/2026 | AQUISIÇÃO DE COXINHA DA ASA, MARGARINA COM SAL... |
| PE 24/2026 | 25/03/2026 | AQUISIÇÃO DE BEBIDA LÁCTEA, MANTEIGA, NATA, POSTA... |
| AD 2/2026 | 25/03/2026 | AQUISIÇÃO DE CAFÉ, COM PRODUTOS PRÉ-QUALIFICADOS... |

---

## ✅ Checklist do Projeto

- [x] Coleta de 715 licitações agrícolas
- [x] Itens com 99,8% de cobertura
- [x] Fornecedores e participações indexados
- [x] Empenhos coletados (36% possível)
- [ ] PDFs com cobertura adequada (PENDENTE - apenas 2,2%)
- [ ] Análise de demanda agrícola por categoria
- [ ] Dashboard agrícola com filtros

---

## 🛠️ Scripts Disponíveis

| Script | Função |
|--------|--------|
| `dados_atualizados_agro.py --resumo` | Resumo agrícola sempre atualizado |
| `dados_atualizados_agro.py --licitacoes-recentes 10` | Últimas licitações agrícolas |
| `dados_atualizados_agro.py --status-coleta` | Status de PDFs agrícolas |
| `etapa2_itens_v9.py` | Coleta de itens (reutilizar para agrícolas) |
| `etapa3_producao.py --resume` | Coleta de PDFs (em progresso) |

---

## 🔍 Próxima Ação

**Entender se:**
1. Os 16 PDFs agrícolas atuais são suficientes, OU
2. Precisamos re-coletar focando exclusivamente em `relevante_af=true`

Se a resposta for (2), criar `etapa3_producao_agro.py` que filtra apenas licitações agrícolas antes de tentar download de PDFs.

---

*Documento Gerado: 25/04/2026 às 23:42 UTC*  
*Escopo: AGRICULTURA EXCLUSIVAMENTE (relevante_af=true)*  
*Última Coleta: 25/04/2026 (dados ao vivo do Supabase)*
