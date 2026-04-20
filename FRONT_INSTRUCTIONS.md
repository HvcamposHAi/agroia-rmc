# Instruções Lovable - AgroIA-RMC Frontend

## 📋 Visão Geral do Projeto

Criar um frontend minimalista e clean para **AgroIA-RMC** — uma plataforma de análise de licitações agrícolas públicas com agente de chat IA integrado.

**Stack:**
- Framework: React 18+ (TypeScript recomendado)
- UI: Tailwind CSS + shadcn/ui
- Banco: Supabase (autenticação + dados)
- Backend API: FastAPI em `http://localhost:8000`
- Chat IA: Claude Haiku 4.5 (via backend)

---

## 🎨 Design System

**Paleta de Cores:**
- **Primary**: Verde agrícola `#10b981` (emerald-500)
- **Secondary**: Azul claro `#3b82f6` (blue-500)
- **Background**: Branco `#ffffff` + Cinza claro `#f9fafb` (gray-50)
- **Text**: Cinza escuro `#1f2937` (gray-800)
- **Border**: Cinza médio `#e5e7eb` (gray-200)
- **Alert/Error**: Vermelho `#ef4444` (red-500)

**Tipografia:**
- Heading 1: 32px, bold
- Heading 2: 24px, semibold
- Body: 14px, regular
- Small: 12px, regular

**Espaçamento:**
- Padding global: 16px-24px
- Gap entre cards: 16px
- Border radius: 8px
- Box shadow: subtle (0 1px 3px rgba(0,0,0,0.1))

---

## 🏗️ Estrutura de Páginas

### Página 1: Chat (Rota: `/`)
**Layout:** Sidebar esquerdo + Chat principal à direita

#### Sidebar (left, 280px, sticky)
```
┌─────────────────────────┐
│ 🌾 AgroIA-RMC           │ ← Logo + título
│ Assistente Agrícola     │
├─────────────────────────┤
│ [+ Nova Conversa]       │ ← Botão criar conversa
├─────────────────────────┤
│ ℹ️ Histórico             │
│ Conversas Recentes:     │
│ • "Culturas 2024"       │ ← Clicável, carrega conversa
│ • "Top fornecedores"    │
│ • "Demanda por canal"   │
├─────────────────────────┤
│ ⚙️ Configurações         │
│ User: user@example.com  │ ← Logout link
└─────────────────────────┘
```

#### Chat Principal (right, flex)
```
┌─────────────────────────────────────┐
│ 💬 Chat - AgroIA-RMC                │ ← Título
├─────────────────────────────────────┤
│                                     │
│ [User bubble right-aligned]         │
│ "Quais são as top culturas?"        │
│                                     │
│ [Assistant bubble left-aligned]     │
│ "As principais culturas são:        │
│  1. Hortaliças - R$ 450k            │
│  2. Frutas - R$ 380k                │ ← Usa dados de vw_itens_agro
│  ..."                               │
│ 🔧 Tools: query_itens_agro          │ ← Indicator
│                                     │
│ [User input area at bottom]         │
├─────────────────────────────────────┤
│ [📎 Attach] [Text input...] [Send▶]│
└─────────────────────────────────────┘
```

**Comportamento:**
- Carregar histórico ao abrir conversa (GET `/conversas/{session_id}`)
- Enviar mensagem ao pressionar Enter ou clicar em Send (POST `/chat`)
- Mostrar loading spinner enquanto aguarda resposta
- Auto-scroll para nova mensagem
- Salvar session_id em localStorage
- Cards de conversas "recentes" clicáveis

---

### Página 2: Dashboard (Rota: `/dashboard`)
**Layout:** Grid 2 colunas (ou 1 coluna em mobile)

#### Top Section
```
┌──────────────────────────────────────────────┐
│ 📊 Dashboard - Análise Agrícola              │
│ Atualizando dados em tempo real...           │
└──────────────────────────────────────────────┘
```

#### Cards de Métricas (grid 4 colunas)
```
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ Total    │ │ Culturas │ │ Fornecedores │ Período│
│ R$ 2.3M  │ │ 45+      │ │ 326+    │ 2019-26 │
│ Itens    │ │ Única    │ │ Ativos  │         │
│ 743      │ │ Cultivas │ │         │         │
└──────────┘ └──────────┘ └──────────┘ └──────────┘
```

#### Gráfico 1: Top-10 Culturas por Valor (Coluna 1, altura 400px)
```
┌─────────────────────────────┐
│ 🏆 Top-10 Culturas por Valor│
├─────────────────────────────┤
│                             │
│  R$  [████████████] Horta   │ 450k
│      [██████████░] Frutas   │ 380k
│      [██████░░░░░] Grãos    │ 220k
│      [█████░░░░░░] Proteína │ 180k
│      [███░░░░░░░░] Lácteos  │ 150k
│      ...                    │
│                             │
└─────────────────────────────┘
```
**Dados:** Query `SELECT cultura, SUM(valor_total) FROM vw_itens_agro GROUP BY cultura ORDER BY 2 DESC LIMIT 10`

#### Gráfico 2: Demanda por Ano (Coluna 2, altura 400px)
```
┌─────────────────────────────┐
│ 📈 Evolução Temporal        │
├─────────────────────────────┤
│   R$                        │
│   500k │   ╱╲   ╱           │
│   400k │  ╱  ╲╱  ╲   ╱     │
│   300k │ ╱        ╲ ╱      │
│   200k │                   │
│   ──────┼───────────────    │
│        2019 2021 2023 2026  │
│                             │
└─────────────────────────────┘
```
**Dados:** Query `SELECT EXTRACT(YEAR FROM dt_abertura) as ano, SUM(valor_total) FROM vw_itens_agro GROUP BY 1 ORDER BY 1`

#### Tabela: Top-5 Fornecedores (Full width, height auto)
```
┌─────────────────────────────────────────────┐
│ 🏢 Fornecedores Principais                  │
├──────────────┬──────────────┬────────────────┤
│ Fornecedor   │ Participações│ Valor Total    │
├──────────────┼──────────────┼────────────────┤
│ Coop A       │ 145          │ R$ 580,000.00  │
│ Agro B       │ 89           │ R$ 340,000.00  │
│ Farm C       │ 67           │ R$ 210,000.00  │
│ ...          │ ...          │ ...            │
└──────────────┴──────────────┴────────────────┘
```
**Dados:** Supabase view ou query JOIN em `vw_itens_agro` + `fornecedores`

---

### Página 3: Consulta de Licitações (Rota: `/consultas`)
**Layout:** Filters no topo + Tabela/Cards abaixo

#### Filtros (sticky top, background white)
```
┌───────────────────────────────────────────────────┐
│ 🔍 Consultar Licitações                           │
├───────────────────────────────────────────────────┤
│ [Buscar por descrição...] [Filtro ▼] [Reset]    │
├───────────────────────────────────────────────────┤
│ Filtros Avançados:                               │
│ ┌─────────────┬─────────────┬─────────────────┐ │
│ │ Cultura:    │ Canal:      │ Período:        │ │
│ │ [Todas ▼]   │ [Todas ▼]   │ [2019-2026]     │ │
│ │             │             │                 │ │
│ └─────────────┴─────────────┴─────────────────┘ │
│ [Aplicar Filtros] [Limpar]                      │
└───────────────────────────────────────────────────┘
```

#### Resultados (Tabela ou Cards)
```
┌─────────────────────────────────────────────────┐
│ Resultados: 743 itens encontrados               │
├─────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────┐   │
│ │ 📋 Processo: 001/2024                    │   │
│ │ Descrição: Aquisição de hortaliças       │   │
│ │ Cultura: Hortaliças                      │   │
│ │ Valor: R$ 25,000.00                      │   │
│ │ Canal: SMSAN                             │   │
│ │ Data: 15/03/2024                         │   │
│ │ [Ver Detalhes →]                         │   │
│ └──────────────────────────────────────────┘   │
│ ┌──────────────────────────────────────────┐   │
│ │ ...próximo item                          │   │
│ └──────────────────────────────────────────┘   │
│                                                  │
│ [← Anterior] Página 1 de 25 [Próximo →]        │
└─────────────────────────────────────────────────┘
```

**Dados:** Query `SELECT * FROM vw_itens_agro WHERE [filters] LIMIT 20 OFFSET [page*20]`

**Paginação:** 20 itens por página

---

## 🔌 Integração Backend

### Conexão com FastAPI

**Base URL:** `http://localhost:8000` (ou ENV var `REACT_APP_API_URL`)

**Endpoints a chamar:**

#### 1. Chat
```
POST /chat
Headers: Content-Type: application/json
Body: {
  "pergunta": string,
  "session_id": string (uuid),
  "historico": Array<{role, content, tools}>
}
Response: {
  "resposta": string,
  "tools_usadas": string[],
  "session_id": string
}
```

#### 2. Carregar Histórico
```
GET /conversas/{session_id}
Response: Array<{
  id: number,
  role: "user" | "assistant",
  content: string,
  tools_usadas: string[]?,
  criado_em: string
}>
```

#### 3. Deletar Conversas
```
DELETE /conversas/{session_id}
Response: { success: boolean }
```

#### 4. Health Check
```
GET /health
Response: { status: "ok" }
```

---

## 🗄️ Integração Supabase

### Conexão
```typescript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  process.env.REACT_APP_SUPABASE_URL!,
  process.env.REACT_APP_SUPABASE_ANON_KEY!
)
```

### Queries Recomendadas

#### Dashboard - Top 10 culturas
```typescript
const { data } = await supabase
  .from('vw_itens_agro')
  .select('cultura, valor_total')
  .order('valor_total', { ascending: false })
  .limit(10)

// Agrupar/somar no frontend
```

#### Dashboard - Demanda por ano
```typescript
const { data } = await supabase
  .from('vw_itens_agro')
  .select('dt_abertura, valor_total')
  .order('dt_abertura')
```

#### Consultas - Todos os itens com filtro
```typescript
let query = supabase
  .from('vw_itens_agro')
  .select('*')

if (cultura !== 'Todas') query = query.eq('cultura', cultura)
if (canal !== 'Todas') query = query.eq('canal', canal)

const { data } = await query
  .range(offset, offset + 19) // Paginação
  .order('dt_abertura', { ascending: false })
```

#### Dropdowns - Valores únicos
```typescript
// Culturas
const { data: culturas } = await supabase
  .from('vw_itens_agro')
  .select('cultura', { count: 'exact' })
  .distinct()
  .order('cultura')

// Canais
const { data: canais } = await supabase
  .from('vw_itens_agro')
  .select('canal')
  .distinct()
  .order('canal')
```

---

## 🎯 Funcionalidades Específicas

### Session Management
- Gerar UUID único para nova conversa (usar `crypto.randomUUID()`)
- Salvar `session_id` em localStorage como `agroia_session`
- Carregar histórico ao abrir conversa salva
- Listar conversas recentes (últimas 5) no sidebar

### Loading States
- Spinner circular verde ao enviar mensagem
- Disabled input enquanto aguarda resposta
- Toast de erro se API falhar

### Responsividade
- **Desktop (>1024px):** Layout 3 colunas (sidebar + chat + conversas)
- **Tablet (768-1024px):** Sidebar colapsável, chat full-width
- **Mobile (<768px):** Menu hambúrguer, layout stacked

### Dark Mode (Opcional)
- Toggle no header
- Usar `next-themes` ou Tailwind dark mode
- Cores ajustadas para modo escuro

---

## 🎭 Componentes shadcn/ui Sugeridos

- `Button` — Para botões (Send, Filtrar, etc.)
- `Card` — Para cards de métricas e itens
- `Dialog` — Para modais (Ver detalhes licitação)
- `DropdownMenu` — Para dropdowns de filtro
- `Input` — Para inputs de texto
- `Textarea` — Para input do chat
- `Select` — Para selects de filtro
- `Badge` — Para labels (tools usadas, status)
- `Skeleton` — Para loading placeholders
- `Toast` — Para notificações

---

## 📱 Fluxo de Uso Esperado

1. **Usuário abre `/`** → Carrega último session_id ou cria novo
2. **Escreve pergunta** (ex: "Quais culturas têm maior demanda?")
3. **Clica Send** → POST /chat com pergunta
4. **Backend** → Claude Haiku chama tools, retorna resposta
5. **Frontend** → Exibe resposta + tools usadas
6. **Usuário clica "Dashboard"** → Carrega gráficos (dados de Supabase)
7. **Usuário clica "Consultas"** → Filtra tabela vw_itens_agro
8. **Clica conversa anterior** → GET /conversas/{session_id}, carrega histórico

---

## ✅ Checklist Implementação

- [ ] Layout base (navbar, sidebar, main content)
- [ ] Página Chat com integração FastAPI
- [ ] Session management (UUID + localStorage)
- [ ] Histórico de mensagens (carregar + salvar)
- [ ] Página Dashboard com 2 gráficos + tabela
- [ ] Página Consultas com filtros e paginação
- [ ] Conexão Supabase para todas as queries
- [ ] Loading states e error handling
- [ ] Responsividade (mobile, tablet, desktop)
- [ ] Dark mode (opcional)
- [ ] Deploy em Vercel ou similar

---

## 🔐 Variáveis de Ambiente (.env.local)

```
REACT_APP_API_URL=http://localhost:8000
REACT_APP_SUPABASE_URL=https://rsphlvcekuomvpvjqxqm.supabase.co
REACT_APP_SUPABASE_ANON_KEY=<sua-chave-anon>
```

---

## 🎨 Exemplos de Cards Chat

**User Message:**
```
┌─────────────────────────────────┐
│ (right-aligned, fundo azul)     │
│ Quais culturas têm maior valor? │
└─────────────────────────────────┘
```

**Assistant Message:**
```
┌────────────────────────────────────┐
│ (left-aligned, fundo cinza)        │
│ As culturas com maior valor são:   │
│                                    │
│ 1. Hortaliças: R$ 450,000.00       │
│ 2. Frutas: R$ 380,000.00           │
│ 3. Grãos: R$ 220,000.00            │
│                                    │
│ 🔧 Tools: query_itens_agro         │
└────────────────────────────────────┘
```

---

## 📝 Notas Finais

1. **Escopo de dados**: SEMPRE filtrar por `vw_itens_agro` apenas (não incluir itens não-agrícolas)
2. **Minimalismo**: Remover elementos desnecessários, máximo 3 cores principais
3. **Performance**: Lazy load gráficos, debounce buscas
4. **UX**: Mensagens de erro claras, loading estados visíveis
5. **Segurança**: Usar Supabase RLS policies, nunca expor API keys no cliente

---

**Status**: Pronto para implementação em Lovable  
**Criado**: 2026-04-19  
**Escopo**: Frontend completo (Chat + Dashboard + Consultas)
