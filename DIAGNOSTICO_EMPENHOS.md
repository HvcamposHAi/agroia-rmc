# Diagnóstico: Estrutura da Tabela EMPENHOS

## Problema Identificado

Ao executar queries que tentam correlacionar empenhos com licitações, recebemos:

```
ERROR: 42703: column e.licitacao_id does not exist
LINE 42: COUNT(DISTINCT e.licitacao_id)
```

**Isso significa**: A tabela `empenhos` **NÃO TEM** uma coluna `licitacao_id`.

---

## 🔍 Como Diagnosticar (Supabase)

### PASSO 1: Ver Estrutura Exata de EMPENHOS

Execute no **Supabase SQL Editor**:

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'empenhos'
ORDER BY ordinal_position;
```

**O que você verá**: Lista completa de colunas (ex: id, numero, ano, data_empenho, valor, etc)

---

### PASSO 2: Ver Dados Reais

```sql
SELECT * FROM empenhos LIMIT 5;
```

**O que você verá**: Primeiras 5 linhas com valores reais

---

### PASSO 3: Identificar a Relação

Procure por estas padrões possíveis:

#### Opção A: Coluna de Número/Processo
```sql
-- Se empenhos tem coluna 'processo' ou 'numero_processo'
SELECT DISTINCT numero, ano, processo FROM empenhos LIMIT 10;
```

#### Opção B: Coluna de ID de Licitação Escondida
```sql
-- Procurar por variações de nomes
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'empenhos'
AND (column_name ILIKE '%lic%' OR column_name ILIKE '%processo%' OR column_name ILIKE '%id%');
```

#### Opção C: Tabela Intermediária
```sql
-- Ver se existe tabela de relacionamento
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name ILIKE '%empenho%licita%';
```

---

## 📋 Estruturas Possíveis

### Cenário 1: Relacionamento via Número/Ano
```
empenhos.numero + empenhos.ano ↔ licitacoes.processo
```

**Query corrigida seria**:
```sql
SELECT l.id, l.processo, e.numero, e.ano, e.valor
FROM licitacoes l
JOIN empenhos e ON 
    CONCAT(e.numero, '/', e.ano) LIKE CONCAT('%', l.processo, '%')
```

### Cenário 2: Campo Customizado
```
empenhos.licitacao_processo ↔ licitacoes.processo
```

**Query corrigida seria**:
```sql
SELECT l.id, l.processo, e.licitacao_processo, e.valor
FROM licitacoes l
JOIN empenhos e ON l.processo = e.licitacao_processo
```

### Cenário 3: Sem Relacionamento Direto
```
empenhos é dados puros de BPMN/SAP (independente de licitacoes)
```

**Implicação**: Não há forma de correlacionar! Dados de empenhos não conectam a licitações.

---

## 🎯 Ações Recomendadas

### IMEDIATAMENTE:

1. **Executar a Query de Diagnóstico** acima (PASSO 1)
2. **Compartilhar as colunas encontradas**
3. **Executar PASSO 2** para ver dados de exemplo

### Depois de Descobrir a Estrutura:

- [ ] Atualizar `auditoria_queries_corrigidas.sql` com JOIN correto
- [ ] Reexecutar queries para encontrar empenhos correlacionados
- [ ] Atualizar documentação de schema em CLAUDE.md

---

## 💡 Exemplo: Se Empenhos Tiver Coluna 'processo'

```sql
-- Query corrigida que funcionaria:
SELECT
    l.id,
    l.processo,
    e.numero as numero_empenho,
    e.valor,
    SUM(il.valor_total) as valor_licitacao
FROM licitacoes l
JOIN empenhos e ON l.processo = e.processo
JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
LEFT JOIN documentos_licitacao d ON l.id = d.licitacao_id
GROUP BY l.id, l.processo, e.numero, e.valor
ORDER BY e.valor DESC;
```

---

## 📝 Checklist

- [ ] Executou PASSO 1 (Ver colunas)?
- [ ] Encontrou coluna que relaciona com licitacoes?
- [ ] Executou PASSO 2 (Ver dados)?
- [ ] Teste JOIN proposto?
- [ ] Atualizar queries?

---

## 🔗 Arquivos de Suporte

- `diagnostico_empenhos_schema.sql` - Queries prontas para diagnosticar
- `auditoria_queries_corrigidas.sql` - Queries que funcionam SEM empenhos

