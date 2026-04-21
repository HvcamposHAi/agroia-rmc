# Registro de Desenvolvimento — AgroIA-RMC
**Data:** 19–20 de abril de 2026  
**Projeto:** Dissertação de Mestrado — PPGCA/UEPG  
**Orientador:** Prof. Jonathan de Matos  
**Aluno:** Humberto Vinicius Aparecido de Campos  

---

## Sumário

1. [Contexto e Objetivo](#1-contexto-e-objetivo)
2. [Configuração do Ambiente de Desenvolvimento](#2-configuração-do-ambiente-de-desenvolvimento)
3. [Deploy do Frontend no Cloudflare Pages](#3-deploy-do-frontend-no-cloudflare-pages)
4. [Deploy do Backend no Render](#4-deploy-do-backend-no-render)
5. [Redesign da Interface — Tema Agrícola](#5-redesign-da-interface--tema-agrícola)
6. [Dashboard com Filtros e Estatísticas](#6-dashboard-com-filtros-e-estatísticas)
7. [Consultas com Filtros Avançados e Limpeza de Dados](#7-consultas-com-filtros-avançados-e-limpeza-de-dados)
8. [Tela de Alertas Inteligentes com IA](#8-tela-de-alertas-inteligentes-com-ia)
9. [Visualizador de PDFs das Licitações](#9-visualizador-de-pdfs-das-licitações)
10. [Arquitetura Final do Sistema](#10-arquitetura-final-do-sistema)
11. [Problemas Resolvidos e Lições Aprendidas](#11-problemas-resolvidos-e-lições-aprendidas)

---

## 1. Contexto e Objetivo

O AgroIA-RMC é uma plataforma multiagente de IA para coordenação entre oferta da agricultura familiar e demanda institucional pública na Região Metropolitana de Curitiba (RMC). O foco desta sessão foi construir e publicar o artefato funcional da dissertação: uma aplicação web completa com frontend React, backend FastAPI e banco de dados Supabase.

**Stack tecnológica utilizada:**
- Frontend: React + TypeScript + Vite + Tailwind (Nunito + Fraunces via Google Fonts)
- Backend: FastAPI (Python 3.11) + Anthropic Claude Haiku
- Banco de dados: Supabase (PostgreSQL)
- Hospedagem frontend: Cloudflare Pages (gratuito)
- Hospedagem backend: Render (gratuito, plano Free)
- Fonte de dados: Portal de licitações da SMSAN/FAAC (2019–2026)

---

## 2. Configuração do Ambiente de Desenvolvimento

### Guias criados

Foram criados dois guias de referência para o ambiente de desenvolvimento:

**`GUIA_AMBIENTE_DEV.md`** — Cobre:
- Pré-requisitos (Node.js 18+, Python 3.10+, Git)
- Execução local do frontend (`npm run dev` na porta 5173)
- Execução local do backend (`python api/main.py` na porta 8000)
- Variáveis de ambiente necessárias (`.env.local` para o frontend, `.env` para o backend)
- Checklist de testes locais
- Instruções de deploy no Vercel e Render

**`FRONTEND_SETUP.md`** — Cobre:
- Estrutura de arquivos do projeto React
- Dependências instaladas (react-router-dom, supabase, recharts, lucide-react, uuid)
- Endpoints esperados do backend
- Schema da view `vw_itens_agro`
- Especificações de design (paleta de cores)

### Alternativas de servidor avaliadas

#### Critérios de seleção

Para um protótipo acadêmico de dissertação de mestrado, os critérios prioritários foram:

1. **Custo zero** — sem cartão de crédito obrigatório nem cobrança por uso básico
2. **Deploy automático via GitHub** — integração contínua sem etapas manuais a cada atualização
3. **HTTPS gratuito** — URL pública com certificado SSL para demonstração
4. **Suporte à stack** — React/Vite para frontend, Python/FastAPI para backend
5. **Relevância acadêmica** — uso de infraestrutura profissional real, não apenas localhost

---

#### Frontend: Cloudflare Pages vs. alternativas

| Plataforma | Gratuito | Cartão | CDN | Deploy auto | Decisão |
|---|---|---|---|---|---|
| **Cloudflare Pages** | ✅ ilimitado | ❌ não exige | ✅ global (300 cidades) | ✅ via GitHub | **Adotado** |
| Vercel | ✅ projetos pessoais | ❌ não exige | ✅ global | ✅ via GitHub | Considerado |
| Netlify | ✅ 100 GB/mês | ❌ não exige | ✅ | ✅ via GitHub | Considerado |
| GitHub Pages | ✅ ilimitado | ❌ não exige | ⚠️ limitado | ✅ via Actions | Considerado |

**Por que Cloudflare Pages foi escolhido em vez de Vercel:**

O projeto já utilizava o painel do Cloudflare para gestão do domínio `hai.expert`. A integração com uma conta já existente eliminou a necessidade de criar e gerenciar uma conta adicional. Além disso, o Cloudflare Pages oferece CDN em mais de 300 cidades ao redor do mundo sem custo adicional — superior ao Vercel no plano gratuito — o que é relevante para demonstração do sistema a gestores públicos em qualquer localidade do Brasil.

Do ponto de vista acadêmico, o Cloudflare é uma infraestrutura amplamente utilizada em produção por grandes organizações, o que fortalece o argumento de que o AgroIA-RMC foi construído sobre tecnologias de nível empresarial, não apenas ferramentas experimentais.

**Dificuldade encontrada:** A interface do Cloudflare não distingue claramente entre "Workers" (funções serverless em JavaScript) e "Pages" (sites estáticos). O fluxo padrão de criação direciona para Workers, o que causou falha inicial de deploy. A solução foi navegar para o fluxo específico de Pages via link secundário na interface.

---

#### Backend: Render vs. alternativas

| Plataforma | Gratuito | Cartão | Python | Sleep | Decisão |
|---|---|---|---|---|---|
| **Render** | ✅ 750h/mês | ❌ não exige | ✅ nativo | ⚠️ após 15min | **Adotado** |
| Railway | ✅ $5 crédito/mês | ✅ **exige** | ✅ nativo | ❌ não dorme | Descartado |
| Fly.io | ✅ 3 VMs | ❌ não exige | ✅ via Docker | ❌ não dorme | Considerado |
| Google Cloud Run | ✅ 2M req/mês | ✅ **exige** | ✅ via container | ❌ não dorme | Futuro (créditos) |
| Heroku | ❌ pago | ✅ exige | ✅ nativo | — | Descartado |

**Por que Railway foi descartado:**

O Railway estava documentado na arquitetura original do projeto (`GUIA_AMBIENTE_DEV.md`) como opção recomendada para o backend. No entanto, durante a tentativa de deploy, verificou-se que o plano gratuito exige cadastro de cartão de crédito para ativação — mesmo que não haja cobrança imediata. Para um contexto acadêmico onde o objetivo é demonstrar o artefato sem comprometer dados financeiros pessoais, essa exigência foi considerada um impeditivo.

**Por que Render foi adotado:**

O Render oferece 750 horas de compute gratuito por mês sem exigir cartão de crédito — suficiente para demonstrações acadêmicas contínuas durante todo o período de defesa da dissertação. O deploy é automático a cada push no GitHub, e a detecção de Python é automática via `requirements.txt`.

**Limitação conhecida e aceita:** No plano gratuito, o servidor hiberna após 15 minutos de inatividade e leva até 50 segundos para acordar na primeira requisição. Para uma dissertação de mestrado, essa latência inicial é aceitável — ela ocorre apenas na primeira chamada após período de inatividade, e pode ser documentada como limitação do protótipo, não do sistema em si.

**Dificuldade encontrada:** O Render utiliza Python 3.14 por padrão (versão mais recente disponível), que é incompatível com o `pydantic-core` porque esse pacote precisa compilar extensões em Rust, e o sistema de arquivos do ambiente de build do Render é somente leitura. A solução foi fixar Python 3.11.9 via arquivo `.python-version` e variável de ambiente `PYTHON_VERSION=3.11.9`.

---

#### Decisão arquitetural final

A combinação **Cloudflare Pages + Render** foi adotada por três razões principais:

1. **Custo zero real** — ambos gratuitos sem cartão de crédito, viabilizando o protótipo sem dependência de financiamento externo
2. **Separação de responsabilidades** — frontend estático (CDN global) separado do backend Python (container gerenciado), seguindo boas práticas de arquitetura de microsserviços
3. **Relevância para a dissertação** — a escolha de infraestrutura cloud profissional (não apenas localhost) demonstra que o AgroIA-RMC é um artefato funcional real, não apenas um mockup, fortalecendo a argumentação da seção de resultados

A migração futura para Google Cloud (via créditos acadêmicos solicitados pelo Prof. Jonathan) está prevista e seria a infraestrutura ideal para a versão de produção do sistema.

---

## 3. Deploy do Frontend no Cloudflare Pages

### Problema inicial

O Cloudflare criou um **Worker** (JavaScript serverless) em vez de um **Pages** (site estático), pois o fluxo de criação não foi identificado corretamente na interface.

**Erro recebido:**
```
Could not detect a directory containing static files (e.g. html, css and js)
```

**Causa:** O Cloudflare tentou executar `npx wrangler deploy` (deploy de Worker) em vez de compilar o projeto React.

### Solução

Navegar para o fluxo correto: `Workers & Pages → Create → Looking to deploy Pages? Get started → Import an existing Git repository`.

### Configuração correta do build

| Campo | Valor |
|---|---|
| Framework preset | `React (Vite)` |
| Root directory | `agroia-frontend` |
| Build command | `npm run build` |
| Build output directory | `dist` |
| Node version | `18` |

### Variáveis de ambiente configuradas

```
VITE_API_URL           = https://agroia-rmc.onrender.com
VITE_SUPABASE_URL      = https://rsphlvcekuomvpvjqxqm.supabase.co
VITE_SUPABASE_ANON_KEY = <chave anon do Supabase>
```

### Erros de TypeScript corrigidos durante o deploy

1. **`Type '{ children: Element; }' has no properties in common`** — O `Layout.tsx` não aceitava a prop `children`. Corrigido adicionando `{ children?: ReactNode }` na assinatura da função.

2. **`'LineChart' is declared but its value is never read`** — Imports não utilizados do Recharts. Corrigido removendo `LineChart` e `Line`.

3. **`Formatter<ValueType, NameType>` type mismatch** — O formatter do Tooltip do Recharts não aceitava `number`. Corrigido usando `(v) => [fmt(Number(v ?? 0)), 'Valor']`.

4. **`Property 'finally' does not exist on type 'PromiseLike<void>'`** — O Supabase JS retorna `PromiseLike` que não suporta `.finally()`. Corrigido convertendo para `async/await` com `try/finally`.

5. **Pasta `agroia-frontend` não encontrada** — O commit inicial não incluía a pasta. Resolvido após push com a pasta criada pelo Claude Code.

**URL final:** `https://agroia-rmc.pages.dev`

---

## 4. Deploy do Backend no Render

### Problema: Python 3.14 incompatível

O Render usou Python 3.14 (versão padrão mais recente), mas o `pydantic-core` precisava compilar do código fonte (via Rust/Maturin) e falhou por sistema de arquivos somente leitura.

**Erro:**
```
error: failed to create directory `/usr/local/cargo/registry/cache/...`
Caused by: Read-only file system (os error 30)
```

**Solução:** Criar arquivo `.python-version` na raiz com `3.11.9` e adicionar a variável de ambiente `PYTHON_VERSION=3.11.9` no Render.

### Problema: Conflito de versões no requirements.txt

Versões fixas causavam conflito entre `anthropic==0.28.0` e `langchain-anthropic==0.1.23` (que exigia `anthropic>=0.30.0`).

**Solução:** Remover versões fixas do `requirements.txt`, deixando o pip resolver automaticamente:

```
fastapi
uvicorn[standard]
pydantic
python-dotenv
supabase
anthropic>=0.30.0
langchain
langchain-anthropic
langchain-community
```

### Configuração no Render

| Campo | Valor |
|---|---|
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn api.main:app --host 0.0.0.0 --port $PORT` |
| Instance Type | Free |

### Variáveis de ambiente

```
SUPABASE_URL      = https://rsphlvcekuomvpvjqxqm.supabase.co
SUPABASE_KEY      = <chave service_role>
ANTHROPIC_API_KEY = <chave Anthropic>
PYTHON_VERSION    = 3.11.9
```

**URL final:** `https://agroia-rmc.onrender.com`

> ⚠️ **Limitação do plano gratuito:** O servidor hiberna após 15 minutos de inatividade e leva até 50 segundos para acordar na primeira requisição.

---

## 5. Redesign da Interface — Tema Agrícola

### Decisão de design

O design original era genérico (fundo branco frio, fonte Inter, sidebar simples). Foi substituído por um tema **colorido e amigável para agricultores**, inspirado na identidade visual da agricultura familiar brasileira.

### Paleta de cores implementada

```css
--verde:        #3a7d44  /* Verde-campo (cor primária) */
--verde-claro:  #5aad66
--verde-fundo:  #eaf5ec
--amarelo:      #f5a623  /* Amarelo-sol (accent) */
--amarelo-claro:#fef3d8
--terra:        #8b5e3c  /* Terra (secundário) */
--terra-claro:  #f5ede5
--ceu:          #4a9eda  /* Céu-azul */
--ceu-claro:    #e8f4fd
--branco:       #fffdf9  /* Branco creme (não frio) */
```

### Tipografia

- **Nunito** — corpo de texto (arredondado, amigável, acessível)
- **Fraunces** — títulos e valores numéricos (serif expressivo, peso visual)
- Importação via Google Fonts

### Componentes criados/redesenhados

**`index.css`** — Sistema completo de design com:
- Layout de duas colunas (sidebar + main)
- Sidebar verde com nav items, badge ativo dourado, card de usuário no rodapé
- Cards de métricas com faixas coloridas superiores
- Bolhas de chat diferenciadas (usuário: verde / assistente: branco)
- Filtros e selects estilizados
- Cards de itens de licitação com badges coloridos
- Paginação com botões de navegação
- Spinner de carregamento

**`Layout.tsx`** — Sidebar com:
- Logo 🌾 com badge amarelo
- Navegação com ícones em caixinhas
- Badge "🌱 Sistema Ativo" no topbar
- Card "Gestor SMSAN / Curitiba – PR" no rodapé

**`Chat.tsx`** — Interface de chat com:
- Tela de boas-vindas com 6 sugestões de perguntas
- Bolhas diferenciadas por papel (user/assistant)
- Spinner durante processamento
- Textarea com envio por Enter
- Indicador de rodapé com fonte dos dados

---

## 6. Dashboard com Filtros e Estatísticas

### Funcionalidades implementadas

**Filtros dinâmicos reativos** (sem recarregamento de dados):
- Ano (2019–2026)
- Canal (ARMAZEM_FAMILIA, PNAE, PAA, etc.)
- Cultura (todas as 90+ culturas identificadas)
- Botão "Limpar" quando filtros ativos
- Contador de itens selecionados em tempo real

**6 cards de métricas:**

| Métrica | Descrição |
|---|---|
| Valor Total | Soma dos valores com valor por extenso |
| Total de Itens | Contagem de registros filtrados |
| Culturas Distintas | Count de tipos únicos |
| Ticket Médio | Valor médio por item licitado |
| Preço Médio/kg | Calculado como valor_total / qt_solicitada |
| Canais Ativos | Número de canais com dados no filtro |

**Gráficos implementados:**
- **Barras** — Top N culturas por valor (seletor Top 5 / 10 / 20)
- **Pizza** — Distribuição percentual por canal com cores distintas por canal
- **Área** — Evolução temporal (muda automaticamente entre anual e mensal quando um ano é selecionado)

**Cores por canal:**
```javascript
ARMAZEM_FAMILIA: '#3a7d44'  // verde
PNAE:            '#f5a623'  // amarelo
PAA:             '#4a9eda'  // azul
BANCO_ALIMENTOS: '#8b5e3c'  // terra
```

---

## 7. Consultas com Filtros Avançados e Limpeza de Dados

### Problema de inconsistência nos dados

A coluna `cultura` era preenchida manualmente pelo scraper, gerando classificações incorretas — ex.: itens de MACARRÃO classificados como MAÇÃ.

### Solução 1: Correção na origem (SQL)

Script `normalizar_cultura.sql` com UPDATE baseado em palavras-chave da coluna `descricao`:

```sql
UPDATE itens_licitacao
SET cultura = CASE
  WHEN upper(descricao) LIKE '%MACARRAO%' THEN 'MACARRÃO'
  WHEN upper(descricao) LIKE '%MACARRÃO%' THEN 'MACARRÃO'
  WHEN upper(descricao) LIKE '%FRANGO%'   THEN 'FRANGO'
  -- ... 80+ regras de mapeamento
  ELSE cultura
END
WHERE cultura IS NOT NULL;
```

**Resultado após a normalização** (principais culturas):

| Cultura | Itens | Valor Total |
|---|---|---|
| OUTRO | 5.025 | R$ 494,8M |
| LEITE | 209 | R$ 109,5M |
| ÓLEO | 40 | R$ 54,1M |
| QUEIJO | 106 | R$ 50,2M |
| ARROZ | 132 | R$ 47,7M |
| MACARRÃO | 161 | R$ 22,6M |
| MAÇÃ | 4 | R$ 8.760 |

A separação MACARRÃO/MAÇÃ confirma a correção da normalização.

### Solução 2: Normalização no frontend

A busca textual normaliza acentos para comparação:
```typescript
const q = busca.toLowerCase()
  .normalize('NFD')
  .replace(/[\u0300-\u036f]/g, '')
```
Assim "maca" encontra tanto MAÇÃ quanto MACARRÃO.

### Filtros avançados implementados

- **Busca textual** — descrição, processo ou cultura (com normalização de acentos)
- **Cultura** — dropdown com todas as culturas
- **Canal** — ARMAZEM_FAMILIA, PNAE, PAA, etc.
- **Ano** — série 2019–2026
- **Valor mínimo e máximo** — range de valores em R$
- Painel colapsável (oculto por padrão, indicador de quantos filtros ativos)

### Ordenação interativa

Botões de ordenação com toggle asc/desc:
- 📅 Data (padrão: mais recente primeiro)
- 💰 Valor
- ⚖️ Quantidade (kg)
- 🔤 Nome

### Informações por card de item

- Badge de cultura (verde) e canal (azul)
- Data da licitação
- Número do processo
- Quantidade em kg
- **Preço calculado por kg** (≈ R$ X,XX/kg) — dado derivado automaticamente
- Valor total em destaque

---

## 8. Tela de Alertas Inteligentes com IA

### Arquitetura

O usuário clica em "Analisar Dados" → frontend chama `POST /alertas` no backend → backend agrega dados do Supabase → envia para Claude Haiku → retorna JSON estruturado com alertas → frontend renderiza.

### Endpoint `/alertas` (backend)

```python
@app.post("/alertas")
async def gerar_alertas():
    # 1. Busca dados da vw_itens_agro
    # 2. Agrega por cultura e ano (preço médio, qtd, última compra)
    # 3. Filtra categorias não alimentares
    # 4. Envia para Claude Haiku com prompt estruturado
    # 5. Extrai e retorna JSON
```

**Categorias ignoradas na análise:**
`OUTRO, SERVIÇO, LOCAÇÃO, LIMPEZA, INFORMÁTICA, EQUIPAMENTO, SACOLA, EMBALAGEM, BANDEJA, ETIQUETA`

### Prompt do Claude Haiku

O modelo analisa o histórico e identifica três tipos de alertas:

1. **ALTA_PRECO** — variação de preço/kg acima de 20% entre anos consecutivos
2. **DESABASTECIMENTO** — culturas sem compras nos últimos 12 meses
3. **SUPERFATURAMENTO** — preço/kg acima de 50% da média histórica da cultura

### Estrutura de resposta

```json
{
  "alertas": [
    {
      "tipo": "SUPERFATURAMENTO",
      "severidade": "ALTA",
      "cultura": "PERA",
      "titulo": "Superfaturamento extremo - Valores anômalos detectados",
      "descricao": "Preços extremamente fora da realidade...",
      "recomendacao": "Auditoria imediata de todas as compras de PERA..."
    }
  ],
  "resumo": "Análise identificou riscos críticos..."
}
```

### Problemas técnicos resolvidos

**Erro 500 — JSON malformado:**

O Claude Haiku retornava JSON cortado no meio (char 4991) porque `max_tokens=2000` era insuficiente. Solução:
- Aumentar `max_tokens` para 4000
- Extração robusta do JSON (encontra `{` e `}` mais externos)
- Remoção de blocos markdown antes do parse

```python
inicio = texto.find('{')
fim = texto.rfind('}')
if inicio != -1 and fim != -1:
    texto = texto[inicio:fim+1]
return json.loads(texto)
```

### Interface da tela de alertas

- Resumo narrativo gerado pela IA
- 4 cards contadores (Alta de Preço, Desabastecimento, Superfaturamento, Total)
- Cards clicáveis que filtram por tipo
- Filtros de severidade (Alta / Média / Baixa)
- Cards individuais com borda colorida por tipo, badge de severidade, descrição detalhada e recomendação

### Resultado real da primeira análise

A IA detectou alertas genuinamente relevantes:
- PERA com preço de R$ 1.090.000/kg (erro de unidade no scraper — kg vs unidade/dúzia)
- Alta de preço acumulada >20% em TILÁPIA, MANDIOCA, PEPINO entre 2019–2022
- Risco de desabastecimento em TOMATE e SARDINHA (última compra há mais de 8 meses)

---

## 9. Visualizador de PDFs das Licitações

### Estrutura de dados

**Tabela `documentos_licitacao`:**

| Coluna | Tipo | Descrição |
|---|---|---|
| id | bigint | PK |
| licitacao_id | bigint | FK para licitacoes |
| nome_arquivo | text | Nome do arquivo PDF |
| nome_doc | text | Nome descritivo do documento |
| storage_path | text | Caminho de armazenamento |
| url_publica | text | URL do Google Drive |
| tamanho_bytes | bigint | Tamanho do arquivo |
| coletado_em | timestamp | Data de coleta |

**Total de registros:** 57 documentos (Google Drive)

### Problema: URLs do Google Drive

As URLs no formato `/view` não podem ser embutidas em `<iframe>`. Necessário converter para o formato `/preview`:

```typescript
const toEmbedUrl = (url: string): string => {
  const matchView = url.match(/drive\.google\.com\/file\/d\/([^/]+)\//)
  if (matchView) 
    return `https://drive.google.com/file/d/${matchView[1]}/preview`
  const matchUc = url.match(/drive\.google\.com\/uc\?id=([^&]+)/)
  if (matchUc) 
    return `https://drive.google.com/file/d/${matchUc[1]}/preview`
  return url
}
```

### Problemas de RLS (Row Level Security)

Duas tabelas tinham RLS ativa sem policies de leitura pública:

```sql
-- Liberar leitura pública para a chave anon
CREATE POLICY "leitura_publica_documentos"
ON documentos_licitacao FOR SELECT TO anon USING (true);

CREATE POLICY "leitura_publica_licitacoes"
ON licitacoes FOR SELECT TO anon USING (true);
```

### Problema: Campo `modalidade` vazio

A coluna `modalidade` estava `null` para todos os registros linkados a documentos. Alternativa: usar `tipo_processo` que contém dados reais (DE, DS, PE, etc.).

### Filtros implementados

- **Busca textual** — nome do documento, processo ou objeto (normalização de acentos)
- **Ano** — filtro por ano de abertura da licitação
- **Mês** — filtro por mês (Jan–Dez)
- **Tipo de processo** — DE, DS, PE, etc.
- **Situação** — Concluído, Fracassado, Empenhado, etc. (com cores)
- **Canal** — ARMAZEM_FAMILIA, OUTRO, etc.

### Modal de visualização

- Header com nome do documento, processo, data e tipo
- Trecho do objeto da licitação
- `<iframe>` com URL de preview do Google Drive em tela cheia
- Botão de download (URL de download direto)
- Botão fechar

### Cores por situação

```typescript
const situacaoCor = (s: string) => {
  if (sl.includes('vencedor') || sl.includes('empenhado'))
    return { bg: 'var(--verde-fundo)', cor: 'var(--verde)' }     // verde
  if (sl.includes('fracassado') || sl.includes('cancelado'))
    return { bg: '#fef2f2', cor: '#b91c1c' }                      // vermelho
  return { bg: 'var(--amarelo-claro)', cor: '#b45309' }            // amarelo
}
```

---

## 10. Arquitetura Final do Sistema

```
┌─────────────────────────────────────────────────────┐
│              Cloudflare Pages (CDN global)           │
│         https://agroia-rmc.pages.dev                 │
│                                                      │
│  React + TypeScript + Vite                          │
│  ┌──────────┬───────────┬──────────┬─────────────┐  │
│  │ Chat     │ Dashboard │ Consultas│ Alertas IA  │  │
│  │          │           │          │             │  │
│  │ Assistente│ Filtros  │ Filtros  │ POST/alertas│  │
│  │ Agrícola │ Gráficos  │ Avançados│ Cards       │  │
│  └──────────┴───────────┴──────────┴─────────────┘  │
│  ┌────────────────────────────────────────────────┐  │
│  │         Documentos das Licitações              │  │
│  │  Filtros + Preview Google Drive (iframe)       │  │
│  └────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────┘
                     │ VITE_API_URL
                     ▼
┌─────────────────────────────────────────────────────┐
│              Render (Python Free Tier)               │
│         https://agroia-rmc.onrender.com              │
│                                                      │
│  FastAPI + Uvicorn (Python 3.11)                    │
│  ┌──────────┬──────────────────────────────────┐    │
│  │ POST     │ Recebe pergunta + histórico       │    │
│  │ /chat    │ → chat.agent (LangChain)          │    │
│  │          │ → Consulta Supabase               │    │
│  │          │ → Responde via Claude Haiku        │    │
│  ├──────────┼──────────────────────────────────┤    │
│  │ POST     │ Agrega dados por cultura/ano      │    │
│  │ /alertas │ → Claude Haiku analisa riscos     │    │
│  │          │ → Retorna JSON estruturado         │    │
│  ├──────────┼──────────────────────────────────┤    │
│  │ GET      │ Verifica conexão Supabase         │    │
│  │ /health  │                                   │    │
│  └──────────┴──────────────────────────────────┘    │
└────────────────────┬────────────────────────────────┘
                     │ SUPABASE_KEY
                     ▼
┌─────────────────────────────────────────────────────┐
│              Supabase (PostgreSQL)                   │
│     https://rsphlvcekuomvpvjqxqm.supabase.co        │
│                                                      │
│  Tabelas principais:                                 │
│  ├── licitacoes          (1.237 registros)           │
│  ├── itens_licitacao     (~7.900 registros)          │
│  ├── fornecedores                                    │
│  ├── participacoes                                   │
│  ├── empenhos                                        │
│  ├── documentos_licitacao (57 PDFs → Google Drive)   │
│  └── conversas           (histórico do chat)         │
│                                                      │
│  Views:                                              │
│  └── vw_itens_agro       (view principal do frontend)│
└─────────────────────────────────────────────────────┘
```

### Fluxo de dados da view `vw_itens_agro`

A view centraliza os dados para o frontend, expondo:
`id, processo, descricao, cultura, canal, valor_total, dt_abertura, qt_solicitada`

---

## 11. Problemas Resolvidos e Lições Aprendidas

### Cloudflare: Worker vs Pages

**Problema:** A interface do Cloudflare não deixa claro a distinção entre Workers (serverless JS) e Pages (site estático). O fluxo padrão cria Workers.

**Solução:** Usar o link "Looking to deploy Pages? Get started" na tela de criação de Workers.

### Render: Versão do Python

**Problema:** O Render usa Python 3.14 por padrão, incompatível com pacotes que compilam extensões Rust.

**Solução:** Arquivo `.python-version` + variável de ambiente `PYTHON_VERSION=3.11.9`.

### Supabase: RLS sem policies

**Problema:** Tabelas com RLS ativa retornam 0 registros para a chave `anon` sem políticas de SELECT.

**Lição:** Sempre verificar RLS ao criar novas tabelas. Comando de diagnóstico:
```sql
SELECT tablename, rowsecurity FROM pg_tables WHERE tablename = 'sua_tabela';
```

### Google Drive: Embedding de PDFs

**Problema:** URLs no formato `/view` e `/uc?export=download` são bloqueadas pelo X-Frame-Options do Google.

**Solução:** Converter para `/preview` que permite embedding:
```
https://drive.google.com/file/d/{ID}/preview
```

### Normalização de cultura via SQL

**Problema:** ~5.000 itens classificados como "OUTRO" e inconsistências entre culturas similares.

**Solução:** Script de UPDATE com 80+ regras de mapeamento por palavras-chave na descrição. Resultado: MACARRÃO separado de MAÇÃ, proteínas e grãos corretamente classificados.

### Claude Haiku: JSON truncado

**Problema:** `max_tokens=2000` insuficiente para 15 alertas detalhados, causando JSON inválido.

**Solução:** `max_tokens=4000` + extração por `rfind('}')` + remoção de blocos markdown antes do parse.

---

## Referências de Arquivos Criados/Modificados

| Arquivo | Tipo | Descrição |
|---|---|---|
| `agroia-frontend/src/index.css` | CSS | Sistema de design completo |
| `agroia-frontend/src/App.tsx` | React | Roteador com todas as rotas |
| `agroia-frontend/src/components/Layout.tsx` | React | Sidebar + topbar |
| `agroia-frontend/src/pages/Chat.tsx` | React | Interface de chat com IA |
| `agroia-frontend/src/pages/Dashboard.tsx` | React | Dashboard com filtros e gráficos |
| `agroia-frontend/src/pages/Consultas.tsx` | React | Busca avançada de licitações |
| `agroia-frontend/src/pages/Alertas.tsx` | React | Tela de alertas inteligentes |
| `agroia-frontend/src/pages/Documentos.tsx` | React | Visualizador de PDFs |
| `api/main.py` | Python | Backend FastAPI com endpoints /chat e /alertas |
| `requirements.txt` | Config | Dependências Python sem versões fixas |
| `.python-version` | Config | Fixa Python 3.11.9 no Render |
| `normalizar_cultura.sql` | SQL | Script de limpeza da coluna cultura |

---

*Documento gerado em 20/04/2026 — AgroIA-RMC / PPGCA-UEPG*
