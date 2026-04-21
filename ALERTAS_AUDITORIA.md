# 🚨 Catálogo de Alertas - Auditoria de Documentos Agrícolas

## Estrutura de Alertas

Todos os alertas gerados pela auditoria são categorizados em **3 tipos**:

```
┌─────────────────────────────────────────────┐
│           ALERTAS AUDITORIA                 │
├─────────────────────────────────────────────┤
│ ✗ ERRO_BD                                  │ → Problemas técnicos na BD
│ ⚠️ INCONSISTENCIA_PORTAL                   │ → Falhas no portal/download
│ 🔍 QUALIDADE                                │ → Dados duplicados/inconsistentes
└─────────────────────────────────────────────┘
```

---

## 1️⃣ ERRO_BD - Inconsistências Técnicas na Base de Dados

### Descrição
Problemas identificados **diretamente na base de dados** que indicam falhas de coleta, integridade ou sincronização.

### Tipos de Alerta ERRO_BD

#### 1.1 Licitações Sem Documentos (Genérico)
```json
{
  "tipo": "ERRO_BD",
  "severidade": "MÉDIA",
  "mensagem": "Licitação 000001/2019 sem documentação",
  "processo": "000001/2019",
  "dt_abertura": "2019-01-15",
  "situacao": "Em Andamento"
}
```
**Causa Possível**:
- Coleta não foi executada
- Portal não tinha PDF disponível
- Download falhou silenciosamente

**Ação**:
1. Verificar no portal se PDF existe
2. Se existir, reexecutar `etapa3_producao.py --resume`
3. Se não existir, marcar como "Indisponível"

---

#### 1.2 CRÍTICO: Licitação com Empenho Mas Sem Documentação
```json
{
  "tipo": "ERRO_BD",
  "severidade": "CRÍTICO",
  "mensagem": "CRÍTICO: Licitação 000002/2019 tem 3 empenho(s) mas SEM documentação",
  "processo": "000002/2019",
  "qtd_empenhos": 3,
  "valor_empenhos": 45000.00,
  "status_alerta": "REQUER_ACAO_IMEDIATA"
}
```
**O que significa**:
- A compra foi **executada e paga** (existe empenho)
- MAS **não há documentação coletada** da licitação
- Isso é **inconsistência crítica** — documentos DEVEM existir

**Causa Provável**:
- Coleta foi iniciada mas não completou
- Portal mudou estrutura (breaking change em CSS/selectors)
- Timeout ou erro durante download

**Ação URGENTE**:
1. ✅ Primeiro: Verificar se PDF está no portal
   ```bash
   python diagnostico_portal.py
   ```
2. Se PDF existe: Recolher
   ```bash
   python etapa3_producao.py --limit 1  # Passar processo específico
   ```
3. Se PDF não existe: Escalar para operações (verificar arquivo do portal)

---

#### 1.3 GRAVE: Licitação Finalizada Sem Documentação
```json
{
  "tipo": "ERRO_BD",
  "severidade": "GRAVE",
  "mensagem": "GRAVE: Licitação 000003/2019 finalizada sem documentação",
  "processo": "000003/2019",
  "situacao": "Concluído",
  "qtd_itens_agro": 5,
  "valor_total": 25000.00
}
```
**O que significa**:
- Licitação tem status **"Concluído"** (processo fechado)
- MAS não há PDF coletado
- Documentação pode estar indisponível no portal (Dispensas às vezes não têm docs)

**Causa Provável**:
- Portal removeu o PDF após conclusão
- Arquivo foi movido/deletado no portal
- Portal não disponibiliza docs para certos tipos de processo

**Ação**:
1. Verificar no portal se PDF ainda existe
2. Se não existir: Investigar a razão (tipo de licitação?)
3. Se portal não fornece: Marcar como "Política do Portal"

---

#### 1.4 Documentos Duplicados
```json
{
  "tipo": "ERRO_BD",
  "severidade": "BAIXA",
  "mensagem": "Arquivo 'edital.pdf' duplicado: 2 registros na licitação 000004/2019",
  "licitacao_id": 4,
  "nome_arquivo": "edital.pdf",
  "qtd_registros": 2,
  "paths_diferentes": 2,
  "tamanhos_diferentes": 0
}
```
**Causa Provável**:
- Coleta foi executada 2x sem delete anterior
- Bug em `etapa3_producao.py` causou duplicate insert

**Ação**:
1. Verificar qual registro é mais recente (coletado_em)
2. Deletar o duplicado antigo
3. Executar `FORCAR_REPROCESSAR=True` para relimpeza

---

### 1.5 Tamanho Inconsistente do Mesmo Arquivo
```json
{
  "tipo": "ERRO_BD",
  "severidade": "MÉDIA",
  "mensagem": "Arquivo 'termo_ref.pdf' com 2 tamanhos diferentes: 1024 bytes vs 2048 bytes",
  "licitacao_id": 5,
  "qtd_tamanhos_diferentes": 2
}
```
**Causa Provável**:
- PDF foi atualizado no portal entre coletas
- Versão descomprimida vs comprimida
- Corrupção durante upload

**Ação**:
1. Baixar o arquivo mais recente (maior tamanho = mais recente)
2. Verificar integridade (abrir PDF no Supabase Storage)
3. Se corrompido: Recolher

---

## 2️⃣ INCONSISTENCIA_PORTAL - Falhas de Portal/Download

### Descrição
Inconsistências detectadas entre o **estado esperado no portal** e o que foi **coletado**.

### Tipos de Alerta INCONSISTENCIA_PORTAL

#### 2.1 PDF Deve Existir Mas Não Foi Coletado
```json
{
  "tipo": "INCONSISTENCIA_PORTAL",
  "severidade": "GRAVE",
  "mensagem": "DEVE_TER_DOCS_NO_PORTAL: Licitação 000005/2019 em status 'Concluído' mas sem docs",
  "processo": "000005/2019",
  "situacao": "Concluído",
  "recomendacao": "Validar se PDF está acessível no portal"
}
```
**O que significa**:
- Licitação com status **"Concluído"** OU **"Em Andamento"**
- Portal **deveria** ter PDF
- MAS **não foi coletado**

**Causa Provável**:
- Download falhou silenciosamente (erro de conexão, timeout)
- Modal do PDF não foi detectado
- Portal mudou estrutura HTML/CSS

**Ação**:
1. Acesso manual ao portal:
   ```
   Portal: http://consultalictacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/
   Procurar: processo 000005/2019
   ```
2. Verificar se "Download de Documentos" está acessível
3. Se acessível: Usar `etapa3_producao.py` para recolher
4. Se não acessível: Portal pode estar offline/alterado

---

#### 2.2 Portal Inacessível
```json
{
  "tipo": "INCONSISTENCIA_PORTAL",
  "severidade": "CRÍTICO",
  "mensagem": "Portal inacessível: timeout em 10s para processo 000006/2019",
  "erro": "TIMEOUT: conexão não respondeu",
  "timestamp_erro": "2026-04-21T14:30:45"
}
```
**O que significa**:
- Portal **não respondeu** durante validação Playwright
- Pode indicar problema de rede ou portal offline

**Ação**:
1. Verificar status do portal manualmente
2. Executar `diagnostico_portal.py` para teste isolado
3. Aguardar se portal está em manutenção

---

#### 2.3 Modal de PDF Não Encontrado
```json
{
  "tipo": "INCONSISTENCIA_PORTAL",
  "severidade": "MÉDIA",
  "mensagem": "Modal de PDF não detectado para 000007/2019",
  "processo": "000007/2019",
  "recomendacao": "Verificar se estrutura HTML do portal mudou"
}
```
**O que significa**:
- Licitação existe no portal
- MAS o **modal/link de download** não foi encontrado
- Pode indicar que portal mudou estrutura HTML

**Ação**:
1. Executar `diagnostico_documentos.py` para analisar estrutura
2. Comparar com seletores CSS do `etapa3_producao.py`
3. Se tiver mudado: Atualizar seletores no script

---

## 3️⃣ QUALIDADE - Problemas de Dados/Integridade

### Descrição
Problemas de qualidade detectados nos dados coletados (duplicatas, inconsistências de metadados).

### Tipos de Alerta QUALIDADE

#### 3.1 Arquivo Duplicado (Múltiplos Registros)
```json
{
  "tipo": "QUALIDADE",
  "severidade": "BAIXA",
  "mensagem": "Arquivo 'edital.pdf' aparece 3 vezes na licitação 000008/2019",
  "licitacao_id": 8,
  "qtd_registros": 3,
  "recomendacao": "Revisar e remover duplicatas antigas"
}
```
**Causa Provável**:
- Coleta foi reexecutada sem limpeza
- Bug causou duplicate insert

**Ação**:
1. Identificar qual registro é mais recente
2. Deletar os antigos
3. Verificar se reexecução foi intencional

---

#### 3.2 Path Inconsistente para Mesmo Arquivo
```json
{
  "tipo": "QUALIDADE",
  "severidade": "MÉDIA",
  "mensagem": "Arquivo 'termo_ref.pdf' em 2 paths diferentes no Supabase Storage",
  "nome_arquivo": "termo_ref.pdf",
  "paths_diferentes": 2,
  "recomendacao": "Verificar qual path é correto; deletar arquivo órfão"
}
```
**Causa Provável**:
- Coleta moveu arquivo de localização
- Bug em caminho de storage
- Múltiplas versões do script salvaram em locais diferentes

**Ação**:
1. Verificar path atual em `documentos_licitacao.storage_path`
2. Verificar quais paths existem no Supabase Storage
3. Deletar paths órfãos

---

## 📊 Matriz de Severidade

| Severidade | Tipo | Exemplos | Ação |
|---|---|---|---|
| **CRÍTICO** | ERRO_BD | Empenho sem docs, Corrupção | ⚠️ Investigar hoje |
| **GRAVE** | ERRO_BD / INCONSISTENCIA | Concluída sem docs, Portal offline | ⚠️ Investigar em 24h |
| **MÉDIA** | ERRO_BD / INCONSISTENCIA | Docs faltando, Modal não detectado | 🔍 Verificar |
| **BAIXA** | QUALIDADE | Duplicados, Tamanho inconsistente | 📝 Documentar |

---

## 🔧 Fluxo de Resolução

```
┌─────────────────────────┐
│   ALERTA IDENTIFICADO   │
└────────────┬────────────┘
             │
    ┌────────┴────────┬────────────┬─────────────┐
    │                 │            │             │
    ▼                 ▼            ▼             ▼
  ERRO_BD    INCONSISTENCIA_   QUALIDADE
             PORTAL
    │                 │            │
    ▼                 ▼            ▼
├─Empenho      ├─Portal      ├─Verificar
│  sem docs     │  Inacessível│  duplicação
├─Concluída     ├─Modal não   ├─Revisar
│  sem docs     │  encontrado  │  paths
├─Duplicado     └─Validar     └─Deletar
└─Recolher       no portal      órfãos
```

---

## 🎯 SLA (Service Level Agreement)

| Tipo | Severidade | SLA |
|---|---|---|
| ERRO_BD | CRÍTICO | 4h |
| ERRO_BD | GRAVE | 24h |
| INCONSISTENCIA_PORTAL | GRAVE | 24h |
| QUALIDADE | QUALQUER | 5 dias |

---

## 📈 Métricas a Acompanhar

1. **Alertas CRÍTICOS por semana** (meta: 0)
2. **Alertas GRAVES por mês** (meta: < 5)
3. **Taxa de Cobertura** (meta: > 90%)
4. **Tempo médio de resolução** por severidade

---

## 📝 Exemplos de Relatórios

### Relatório Limpo (Esperado)
```json
{
  "alertas": {
    "ERRO_BD": [],
    "INCONSISTENCIA_PORTAL": [],
    "QUALIDADE": []
  },
  "resumo": {
    "taxa_cobertura_pct": 94.5,
    "alertas_criticos": 0,
    "alertas_graves": 0
  }
}
```
✅ **Ação**: Nenhuma - Sistema operacional normalmente

### Relatório com Alertas
```json
{
  "alertas": {
    "ERRO_BD": [
      "CRÍTICO: Licitação 000005/2019 tem 2 empenho(s) mas SEM documentação"
    ],
    "INCONSISTENCIA_PORTAL": [
      "Portal inacessível: timeout em 10s para processo 000006/2019"
    ],
    "QUALIDADE": [
      "Arquivo 'edital.pdf' duplicado: 2 registros"
    ]
  },
  "resumo": {
    "taxa_cobertura_pct": 87.3,
    "alertas_criticos": 1,
    "alertas_graves": 1
  }
}
```
⚠️ **Ação**: Investigar CRÍTICO em 4h, GRAVE em 24h

---

## 🆘 Contato & Escalação

- **Alertas BD**: Verificar `CLAUDE.md` → Database Schema
- **Alertas Portal**: Executar `diagnostico_portal.py`
- **Alertas Qualidade**: Revisar `etapa3_producao.py`

