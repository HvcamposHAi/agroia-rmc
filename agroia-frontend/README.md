# AgroIA-RMC Frontend

Frontend React minimalista para a plataforma AgroIA-RMC de análise de licitações agrícolas públicas.

## 🚀 Stack Tecnológico

- **React 18** com TypeScript
- **Tailwind CSS** para estilização
- **Recharts** para visualizações
- **Supabase** para integração de dados
- **Axios** para chamadas HTTP

## ⚙️ Instalação e Desenvolvimento

### 1. Instalar Dependências
```bash
npm install
```

### 2. Configurar Variáveis de Ambiente

Editar `.env.local`:
```env
VITE_API_URL=http://localhost:8000
VITE_SUPABASE_URL=https://rsphlvcekuomvpvjqxqm.supabase.co
VITE_SUPABASE_ANON_KEY=<sua-chave-anon>
```

### 3. Iniciar Servidor de Desenvolvimento
```bash
npm run dev
```

Servidor rodando em: `http://localhost:5173`

## 📚 Páginas Principais

### 1. Chat (Rota: `/`)
- Integração com Claude Haiku 4.5 via backend FastAPI
- Histórico de conversas persistido em localStorage
- Session management com UUID

### 2. Dashboard (Rota: `/dashboard`)
- 4 cards de métricas principais
- Gráfico de barras: Top-10 culturas
- Gráfico de linhas: Evolução temporal
- Tabela: Fornecedores principais

### 3. Consultas (Rota: `/consultas`)
- Busca por descrição
- Filtros: Cultura, Canal
- Paginação (20 itens por página)

## 🔌 Integração Backend

Backend FastAPI deve estar rodando em `http://localhost:8000` com endpoints:
- `POST /chat` - Enviar mensagem
- `GET /conversas/{session_id}` - Carregar histórico
- `GET /health` - Health check

## 🔧 Comandos

```bash
npm run dev       # Desenvolvim ento
npm run build     # Build para produção
npm run preview   # Preview da build
```

---

**Última atualização:** 2026-04-19
