# 📊 Referência Rápida - Contexto Agrícola para o Agente

**Data de Atualização:** 2026-04-25  
**Escopo:** AGRICULTURA EXCLUSIVAMENTE (relevante_agro=true)  
**Período de Dados:** 2019-2023 (coleta interrompida)

---

## 🎯 Resumo Executivo

| Métrica | Valor |
|---------|-------|
| **Total de Licitações Agrícolas** | 715 |
| **Total de Itens Agrícolas** | 7.882+ |
| **Período Histórico** | 2019-2023 |
| **Maior Categoria** | LATICINIOS (leite, queijo, etc.) |
| **Canal Principal** | ARMAZEM_FAMILIA (>90%) |

---

## 📈 Categorias Agrícolas Válidas

### 1️⃣ LATICINIOS (Maior demanda)
**Culturas principais:** Leite, Queijo, Iogurte, Manteiga, Nata, Requeijão, Pão de Queijo

**Estatísticas 2019-2023:**
- **2022 (pico):** 9 licitações, 5.5M+ litros de leite
- **Valor recorrente:** R$ 3-14M por ano
- **Tendência:** Queda em 2023 (retração de ~50%)

---

### 2️⃣ GRAOS_CEREAIS (Segunda maior)
**Culturas principais:** Arroz, Feijão, Milho, Trigo, Lentilha, Ervilha, Aveia, Amendoim, Amido

**Estatísticas 2019-2023:**
- **Volume estável** ao longo dos anos
- **Arroz:** Cultura mais demandada (pasta o arroz tem maior demanda)
- **Feijão:** Segunda cultura mais demandada
- **Padrão:** Volumes em centenas de milhares de pacotes

---

### 3️⃣ HORTIFRUTI (Terceira maior)
**Culturas principais:** Tomate, Hortaliças, Batata, Pepino, Mandioca, Abóbora, Tempero, Extratos

**Estatísticas 2019-2023:**
- **Extrato de Tomate:** Item de alto valor (R$ 300K-1.3M por licitação)
- **Hortaliças:** Volume alto, distribuído em várias licitações
- **Tempero:** Produto consistente ao longo dos anos

---

### 4️⃣ FRUTAS (Menor volume)
**Culturas principais:** Uva, Ameixa, Goiabada

**Estatísticas 2019-2023:**
- **Presença consistente mas minoritária**
- **2020:** Uva e Ameixa aparecem (~7K-9K valor total)
- **2022:** Goiabada aparece (R$ 59.8K)

---

## 📅 Tendências por Ano

| Ano | Status | Principal Insight |
|-----|--------|-------------------|
| **2019** | Início | Primeiras licitações coletadas |
| **2020** | Expansão | Crescimento em leite, arroz, feijão |
| **2021** | Manutenção | Demanda estável, diversificação de produtos |
| **2022** | PICO 📈 | Maior volume absoluto em quase todas categorias |
| **2023** | Retração 📉 | ~50% de queda vs 2022 |
| **2024-2026** | ❌ Sem dados | Coleta não realizada |

---

## 🚨 ALERTAS CRÍTICOS

### ⚠️ Dados Desatualizados
- **Último dado:** 2023
- **Falta de coleta:** 2024-2026 (período recente de 18 meses)
- **Resposta quando perguntado sobre 2024-2026:** "Não temos dados de demanda agrícola para 2024-2026. A última coleta foi em 2023."

### ⚠️ Queda de Demanda em 2023
- **Comparativo 2022 → 2023:** Redução significativa em LATICINIOS e outros
- **Possíveis causas:** Não investigadas (pode ser: sazonalidade, interrupção de coleta, mudanças políticas, etc.)

---

## 🔍 Como Usar as Views

### vw_demanda_agro_ano
**Campos:** ano, canal, categoria_v2, cultura, unidade_medida, qtd_licitacoes, qtd_itens, volume_total, valor_total_r$

**Quando usar:**
- Análises por período
- Comparações entre categorias
- Distribuição por canal
- Tendências ao longo dos anos

**Exemplo de pergunta:**
> "Qual era a demanda de leite em 2021 vs 2022?"
> ↓ Responder com dados de vw_demanda_agro_ano filtrados

### vw_itens_agro
**Campos:** id, licitacao_id, seq, codigo, descricao, qt_solicitada, unidade_medida, valor_unitario, valor_total, cultura, categoria_v2, processo, dt_abertura, canal

**Quando usar:**
- Detalhes de processos específicos
- Análise de valores unitários
- Identificação de fornecedores
- Filtros complexos por data, canal, valor

**Exemplo de pergunta:**
> "Quais foram os itens de queijo em 2023?"
> ↓ Responder com dados de vw_itens_agro

---

## 📍 Canais de Distribuição

| Canal | % das Licitações | Descrição |
|-------|-----------------|-----------|
| **ARMAZEM_FAMILIA** | >90% | Principal canal de distribuição |
| **OUTRO** | <5% | Canais variados (2023) |
| **PNAE, PAA, BANCO_ALIMENTOS, MESA_SOLIDARIA** | <5% | Presentes mas minoritários |

**Nota:** Quando perguntado "para qual canal?", assumir ARMAZEM_FAMILIA se não especificado.

---

## ✅ Checklist de Resposta

Sempre verificar:

- [ ] Resposta inclui **APENAS** itens com `relevante_agro=true`
- [ ] Categorias estão entre: LATICINIOS, GRAOS_CEREAIS, HORTIFRUTI, FRUTAS
- [ ] Se período é 2024-2026, mencionar: "Não temos dados coletados"
- [ ] Se período é 2019-2023, pode usar dados das views
- [ ] Tabela tem **máximo 6 linhas**
- [ ] Valores formatados com separador: R$ 1.234.567 (não 1234567)
- [ ] Unidades consideradas (LITRO, PACOTE, KILOGRAMA, etc.)
- [ ] Insight em 1-2 linhas (não parágrafos longos)

---

## 🔗 Referências de Contexto

- **Arquivo de contexto completo:** `agente_contexto_agro.json`
- **System prompt atualizado:** `chat/prompts.py`
- **Dados brutos:** 
  - vw_demanda_agro_ano (100 registros)
  - vw_itens_agro (7.882+ registros)

---

**Próxima Ação Recomendada:** Retomar coleta de dados no portal Curitiba para cobrir 2024-2026
