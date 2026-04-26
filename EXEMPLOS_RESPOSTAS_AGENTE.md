# 💬 Exemplos de Respostas do Agente com Contexto Agrícola

Usando as views `vw_demanda_agro_ano` e `vw_itens_agro` como fonte de dados

---

## Exemplo 1: Demanda por Categoria

**Pergunta do usuário:**
> "Qual é a demanda agrícola por categoria nos últimos anos?"

**Resposta esperada:**

```
🌾 Ótimo! Aqui está a demanda agrícola por categoria em 2022 (ano de pico):

| Categoria | Qtd Licitações | Volume Total | Valor Total |
|-----------|----------------|--------------|------------|
| LATICINIOS | 20+ | 8.2M (litros/unidades) | R$ 35.2M |
| GRAOS_CEREAIS | 18+ | 3.5M (pacotes) | R$ 21.8M |
| HORTIFRUTI | 15+ | 2.1M (unidades) | R$ 8.9M |
| FRUTAS | 3+ | 45K (unidades) | R$ 0.2M |

### Destaque
**LATICINIOS lidera amplamente**, representando ~55% do valor total de demanda agrícola. 
**2023 viu queda de ~50%** — dados 2024-2026 não coletados ainda.

Quer ver a evolução de uma categoria específica (leite, arroz, etc.)?
```

---

## Exemplo 2: Demanda Específica de Produto

**Pergunta do usuário:**
> "Qual foi a demanda de leite em 2021 e 2022?"

**Resposta esperada:**

```
📦 Perfeito! Aqui está a demanda de LEITE (categoria LATICINIOS):

| Ano | Qtd Licitações | Volume (Litros) | Valor Total |
|-----|----------------|-----------------|------------|
| 2021 | 3 | 1.113.500 | R$ 3.519.305 |
| 2022 | 9 | 5.455.000 | R$ 14.659.000 |

### Insight
**2022 foi o pico** com 5,4 milhões de litros — **praticamente 5x a demanda de 2021**. 
A demanda caiu para R$ 526.500 em 2023.

Quer saber mais sobre outros produtos lácteos ou comparar com arroz/feijão?
```

---

## Exemplo 3: Produtos Mais Demandados (Top 5)

**Pergunta do usuário:**
> "Quais são os produtos agrícolas mais demandados?"

**Resposta esperada:**

```
📈 Excelente! Aqui estão os TOP 5 produtos mais demandados (valor acumulado 2019-2023):

| Cultura | Categoria | Qtd Itens | Valor Total | Unidade |
|---------|-----------|-----------|------------|---------|
| LEITE | LATICINIOS | 50+ | R$ 22.9M | LITRO |
| QUEIJO | LATICINIOS | 40+ | R$ 16.7M | PACOTE/KG |
| ARROZ | GRAOS_CEREAIS | 35+ | R$ 12.3M | PACOTE |
| FEIJÃO | GRAOS_CEREAIS | 30+ | R$ 8.5M | PACOTE |
| EXTRATO DE TOMATE | HORTIFRUTI | 8+ | R$ 3.2M | LATA |

### Destaque
**Leite domina**, representando ~30% do valor total. Produtos lácteos e grãos representam ~85% da demanda.

Quer filtrar por ano, canal (ARMAZEM_FAMILIA, PNAE) ou categoria específica?
```

---

## Exemplo 4: Resposta para Período Sem Dados

**Pergunta do usuário:**
> "Qual é a demanda agrícola em 2025?"

**Resposta esperada:**

```
❌ Infelizmente, **não temos dados de demanda agrícola para 2025** (nem 2024-2026).

A coleta de dados foi interrompida após 2023. O último período que temos informação é **2023**, 
que mostrou uma queda significativa vs 2022 (~50% de redução).

### Dados disponíveis:
- **2019-2023:** Histórico completo (vw_demanda_agro_ano, vw_itens_agro)
- **2024-2026:** Não coletados

📌 **Recomendação:** Retomar a coleta de dados no portal Curitiba para cobrir o período recente.

Quer análises dos dados de 2019-2023 ou detalhes sobre algum produto específico?
```

---

## Exemplo 5: Comparação Entre Períodos

**Pergunta do usuário:**
> "A demanda de hortaliças aumentou ou diminuiu ao longo dos anos?"

**Resposta esperada:**

```
🥬 Ótimo! Aqui está a tendência de HORTIFRUTI (hortaliças, tomate, batata, etc.):

| Ano | Qtd Licitações | Volume Total | Valor Total |
|-----|----------------|--------------|------------|
| 2020 | 8 | 234.6K | R$ 814.5K |
| 2021 | 13 | 287.4K | R$ 931.2K |
| 2022 | 20 | 512.8K | R$ 2.184.4K |
| 2023 | 6 | 124.5K | R$ 289.3K |

### Análise
**2022 foi o pico** com 512K unidades. Houve **crescimento consistente de 2020-2022**, 
mas **queda severa em 2023** (~76% de redução), acompanhando queda geral de demanda.

Itens como **EXTRATO DE TOMATE** tiveram maior impacto no valor total.

Quer ver o detalhe de qual hortaliça específica (tomate, batata, pepino)?
```

---

## Exemplo 6: Análise por Canal

**Pergunta do usuário:**
> "Como está distribuída a demanda entre os diferentes canais?"

**Resposta esperada:**

```
📍 Perfeito! Aqui está a distribuição por canal em 2022:

| Canal | Qtd Licitações | Valor Total | % do Total |
|-------|----------------|------------|-----------|
| ARMAZEM_FAMILIA | 68 | R$ 57.8M | 92% |
| OUTRO | 4 | R$ 4.2M | 7% |
| PNAE | 1 | R$ 0.6M | <1% |
| PAA | 0 | — | — |

### Insight
**ARMAZEM_FAMILIA domina completamente** com >90% das licitações em todos os anos. 
Outros canais (PNAE, PAA, BANCO_ALIMENTOS) têm presença mínima.

A demanda é estruturada principalmente por um único canal, reduzindo diversificação.

Quer detalhes sobre as licitações do ARMAZEM_FAMILIA?
```

---

## Exemplo 7: Quando Usuário Pede Algo Fora do Escopo

**Pergunta do usuário:**
> "Qual é a demanda de macarrão e produtos processados?"

**Resposta esperada:**

```
🚫 Desculpa, mas **macarrão e produtos processados estão fora do escopo** deste sistema.

Aqui focamos **APENAS em agricultura primária e produtos agrícolas puros** (relevante_agro=true):
- ✅ LEITE fresco, QUEIJO, IOGURTE (LATICINIOS)
- ✅ ARROZ, FEIJÃO, MILHO (GRAOS_CEREAIS)
- ✅ TOMATE fresco, ALFACE, BATATA (HORTIFRUTI)
- ❌ Macarrão, biscoito, farinha (processados)
- ❌ Atum enlatado, carne processada (proteínas industrializadas)

📌 Este é um sistema especializado em **licitações públicas de agricultura familiar** da RMC.

Quer informações sobre produtos agrícolas válidos (leite, frutas, vegetais, grãos)?
```

---

## Exemplo 8: Resposta Detalhada com Contexto Histórico

**Pergunta do usuário:**
> "Resume para mim a situação da demanda agrícola em 2022 vs 2023"

**Resposta esperada:**

```
📊 Excelente pergunta! Aqui está o comparativo:

| Métrica | 2022 | 2023 | Variação |
|---------|------|------|----------|
| Total Licitações | 75+ | 18 | -76% |
| LATICINIOS (valor) | R$ 35.2M | R$ 7.8M | -78% |
| GRAOS_CEREAIS (qtd) | 3.5M | 0.8M | -77% |
| HORTIFRUTI (valor) | R$ 2.2M | R$ 0.3M | -86% |

### Análise Crítica
**2022 foi o ano de pico** em praticamente todas as categorias. Representou:
- Maior volume de leite (5.4M litros)
- Maior diversidade de produtos
- Maior valor total contratado

**2023 viu queda severa** — possíveis causas (não investigadas):
- Sazonalidade na coleta
- Mudanças em políticas públicas
- Interrupção parcial de coleta
- Redução real de demanda

⚠️ **Crítico:** Sem dados 2024-2026, não sabemos se a queda continuou ou recuperou.

Quer investigar alguma categoria específica em mais detalhe?
```

---

## 🎯 Padrões de Resposta

### ✅ Sempre fazer:
1. Tabela markdown com dados principais
2. Insight em 1-2 linhas (não parágrafos)
3. Pergunta ou sugestão ao final
4. Formato: R$ 1.234.567 (com separador)
5. Máximo 6 linhas de dados

### ❌ Nunca fazer:
1. Listas inline: "LEITE | 5M | ... QUEIJO | 2M | ..."
2. Parágrafos descritivos longos
3. Incluir categorias não-agrícolas
4. Fazer múltiplas tabelas
5. Pedir informações ("qual período você quer?") — assumir contexto

---

## 📚 Referências Usadas

- **vw_demanda_agro_ano**: 100 registros (período 2019-2023)
- **vw_itens_agro**: 7.882+ registros (detalhes de cada item licitado)
- **Contexto**: `agente_contexto_agro.json`
- **System Prompt**: `chat/prompts.py` (atualizado 2026-04-25)
