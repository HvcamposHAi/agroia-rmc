# 🚀 Setup Frontend AgroIA-RMC

## ✅ O que foi criado

Projeto React + TypeScript + Tailwind CSS com as 3 páginas principais:

### 1. **Chat (rota: `/`)**
   - Integração com backend FastAPI (Claude Haiku 4.5)
   - Session management com UUID
   - Histórico persistido em localStorage
   - Mostra tools utilizadas pelo agente

### 2. **Dashboard (rota: `/dashboard`)**
   - 4 cards de métricas (Valor Total, Total de Itens, Período, Culturas)
   - Gráfico de barras: Top-10 culturas por valor
   - Gráfico de linhas: Evolução temporal de demanda
   - Tabela simulada de fornecedores principais

### 3. **Consultas (rota: `/consultas`)**
   - Busca por descrição
   - Filtros avançados (Cultura, Canal)
   - Paginação (20 itens/página)
   - Cards informativos para cada item

## 📋 Estrutura de Arquivos

```
agroia-frontend/
├── src/
│   ├── components/
│   │   ├── Layout.tsx       # Layout + sidebar
│   │   └── Sidebar.tsx      # Menu navegação
│   ├── pages/
│   │   ├── Chat.tsx
│   │   ├── Dashboard.tsx
│   │   └── Consultas.tsx
│   ├── lib/
│   │   ├── supabaseClient.ts  # Queries Supabase
│   │   └── apiClient.ts       # Chamadas FastAPI
│   ├── App.tsx              # Roteador React Router
│   ├── index.css            # Tailwind + custom styles
│   └── main.tsx
├── .env.local               # Variáveis de ambiente
├── tailwind.config.js
├── vite.config.ts
└── package.json
```

## 🔧 Como Iniciar

### Terminal 1: Servidor Frontend
```bash
cd agroia-frontend
npm run dev
```
Acesso: `http://localhost:5173`

### Terminal 2: Servidor Backend (FastAPI)
```bash
cd ..
python api/main.py
```
Acesso: `http://localhost:8000`

## ⚙️ Próximos Passos Necessários

### 1. **Atualizar `.env.local`**
Verificar e atualizar a chave Supabase anon key:
```env
VITE_API_URL=http://localhost:8000
VITE_SUPABASE_URL=https://rsphlvcekuomvpvjqxqm.supabase.co
VITE_SUPABASE_ANON_KEY=<chave-real-do-supabase>
```

### 2. **Testar Conectividade**
- ✅ Frontend em `http://localhost:5173` (OK)
- ⚠️ Backend em `http://localhost:8000` (verificar)
- ⚠️ Supabase (verificar conexão com `.env.local`)

### 3. **Implementar/Verificar no Backend**

Os seguintes endpoints devem estar prontos:

```python
# POST /chat
{
  "pergunta": "Quais culturas têm maior demanda?",
  "session_id": "uuid-aqui",
  "historico": [...]
}
→ Response: {
    "resposta": "As principais culturas...",
    "tools_usadas": ["query_itens_agro"],
    "session_id": "uuid-aqui"
  }

# GET /conversas/{session_id}
# DELETE /conversas/{session_id}
# GET /health
```

### 4. **Dados do Supabase**

O frontend espera a view `vw_itens_agro` com colunas:
- `id`
- `processo`
- `descricao`
- `cultura`
- `canal`
- `valor_total`
- `dt_abertura`
- `qt_solicitada`

Queries importantes:
```sql
-- Ver top culturas
SELECT cultura, SUM(valor_total) as total 
FROM vw_itens_agro 
GROUP BY cultura 
ORDER BY total DESC 
LIMIT 10;

-- Ver demanda por ano
SELECT EXTRACT(YEAR FROM dt_abertura) as ano, SUM(valor_total)
FROM vw_itens_agro
GROUP BY 1
ORDER BY 1;
```

### 5. **Testes Manuais**

No Chat (`/`):
- [ ] Digitar mensagem e enviar (deve chamar `/chat` do backend)
- [ ] Verificar se response aparece no chat
- [ ] Verificar se tools usadas aparecem como badges
- [ ] Criar nova conversa → deve gerar novo UUID
- [ ] Recarregar página → deve carregar histórico

No Dashboard (`/dashboard`):
- [ ] Verificar se os 4 cards de métricas aparecem
- [ ] Gráfico de barras carrega dados de `vw_itens_agro`
- [ ] Gráfico de linhas mostra evolução temporal
- [ ] Tabela de fornecedores (simulated por enquanto)

Nas Consultas (`/consultas`):
- [ ] Buscar por descrição funciona
- [ ] Filtros de Cultura/Canal funcionam
- [ ] Paginação navega corretamente
- [ ] Clique em "Ver Detalhes" pode abrir modal (futura feature)

## 📦 Dependências Instaladas

- `react-router-dom` - Roteamento
- `@supabase/supabase-js` - Cliente Supabase
- `axios` - HTTP client
- `recharts` - Gráficos
- `lucide-react` - Ícones
- `uuid` - Geração de UUIDs
- `tailwindcss` - Estilos

## 🎨 Design Specs

Paleta de cores conforme FRONT_INSTRUCTIONS.md:
- Primary: `#10b981` (emerald - verde agrícola)
- Secondary: `#3b82f6` (blue)
- Background: `#ffffff`
- Text: `#1f2937` (gray-800)
- Border: `#e5e7eb` (gray-200)

Componentes principais:
- Buttons (primary, secondary, ghost)
- Cards com sombra sutil
- Badges para tools
- Message bubbles (user/assistant)

## 🔐 Segurança

- ✅ Chave Supabase anon key (read-only)
- ✅ RLS policies no Supabase
- ✅ Sem secrets expostos no frontend
- ✅ Validação no backend (FastAPI)

## 🚀 Deploy Futuro

```bash
# Build para produção
npm run build

# Resultado em ./dist/
# Fazer upload para Vercel, Netlify, ou qualquer hosting estático
```

---

**Data de Criação:** 2026-04-19  
**Status:** ✅ Projeto base pronto, aguardando integração com backend
