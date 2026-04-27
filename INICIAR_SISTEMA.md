# 🚀 Guia Rápido: Iniciar o Sistema AgroIA-RMC

## Status da Implementação

✅ **Implementação 100% Completa e Testada**

- [x] Backend (FastAPI) com novos endpoints
- [x] Frontend (React) com página de coleta
- [x] Agendamento semanal (APScheduler)
- [x] Progresso em tempo real (SSE)
- [x] Estatísticas de classificação agrícola
- [x] Testes de integração (4/4 PASSOU)
- [x] Build frontend (dist/ pronto)

---

## 📋 Pré-requisitos

- Python 3.13+ instalado
- Node.js 18+ instalado
- Arquivo `.env` configurado com:
  - `SUPABASE_URL`
  - `SUPABASE_KEY`
  - `ANTHROPIC_API_KEY`
  - `API_SECRET_KEY`
  - `ALLOWED_ORIGINS`

---

## ⚡ Iniciar em 2 Etapas

### Terminal 1: Iniciar Backend

```bash
cd "c:/Users/hvcam/Meu Drive/Pessoal/Mestrado/Dissertação/agroia-rmc"

# Opção A: Com Uvicorn (produção)
uvicorn api.main:app --host 0.0.0.0 --port 8000

# Opção B: Com Reload (desenvolvimento)
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Esperado ao iniciar:**
```
[INFO] APScheduler iniciado com job semanal (seg 06:00)
[INFO] Application startup complete
[INFO] Uvicorn running on http://0.0.0.0:8000
```

### Terminal 2: Iniciar Frontend

```bash
cd "c:/Users/hvcam/Meu Drive/Pessoal/Mestrado/Dissertação/agroia-rmc/agroia-frontend"

# Opção A: Modo Desenvolvimento
npm run dev
# Acesse: http://localhost:5173

# Opção B: Modo Produção (usar dist/)
npm run preview
# Acesse: http://localhost:4173
```

---

## 🌐 Acessar o Sistema

| Componente | URL | Descrição |
|---|---|---|
| **Frontend** | http://localhost:3000 | Interface principal (após configurar proxy) |
| **API Docs** | http://localhost:8000/docs | Swagger UI com todos endpoints |
| **Página Coleta** | http://localhost:3000/coleta | Nova página de atualização |
| **Chat** | http://localhost:3000/ | Chat com produtores |

---

## 🔄 Fluxo de Uso

### 1. Coleta Manual

1. Abra `http://localhost:3000/coleta`
2. Clique **"🔍 Buscar Dados"**
3. Acompanhe progresso em tempo real:
   - Barra de progresso (%)
   - KPIs: processados, novos, pulados, erros
   - Status da etapa
4. Gráficos atualizam ao fim da coleta

### 2. Coleta Semanal (Automática)

- Dispara automaticamente **segunda-feira às 06:00**
- Nenhuma ação necessária
- Progresso visível em tempo real se você acessar a página

### 3. Chat com Produtores

- Página inicial mostra 6 exemplos de perguntas
- Produtores rurais podem perguntar:
  - Quais hortaliças a prefeitura compra?
  - Qual preço médio de alface?
  - Qual programa paga mais?
  - Etc.

---

## 🔌 Endpoints Disponíveis

### Coleta

| Método | Endpoint | Autenticação | Descrição |
|---|---|---|---|
| POST | `/coleta/iniciar` | X-API-Key | Iniciar coleta manual |
| POST | `/coleta/cancelar` | X-API-Key | Cancelar coleta em andamento |
| GET | `/coleta/status` | — | Status atual (JSON) |
| GET | `/coleta/stream` | — | Stream SSE do progresso |
| GET | `/coleta/stats` | — | Estatísticas de classificação |

### Exemplo: Iniciar Coleta via cURL

```bash
curl -X POST http://localhost:8000/coleta/iniciar \
  -H "X-API-Key: sua_chave_aqui" \
  -H "Content-Type: application/json"
```

### Exemplo: Obter Status

```bash
curl http://localhost:8000/coleta/status
```

Resposta:
```json
{
  "status": "idle",
  "etapa": "nenhuma",
  "processados": 0,
  "novos": 0,
  "pulados": 0,
  "erros": 0,
  "atualizado_em": "2026-04-27T..."
}
```

---

## 📊 Estrutura de Dados

### Arquivo de Progresso: `coleta_status.json`

Escrito a cada 10 processos durante coleta:

```json
{
  "status": "running",
  "etapa": "coletando",
  "processados": 45,
  "novos": 12,
  "pulados": 33,
  "erros": 0,
  "itens_coletados": 234,
  "fornecedores": 5,
  "empenhos": 78,
  "iniciado_em": "2026-04-27T10:15:30.123456",
  "atualizado_em": "2026-04-27T10:16:45.654321",
  "pid": 12345
}
```

---

## 🛠️ Configuração de Proxy (Frontend)

Se o frontend estiver em porta diferente (ex: 3000 em produção), crie `agroia-frontend/vite.config.ts`:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  }
})
```

---

## 🐛 Troubleshooting

### Backend não inicia

```bash
# Verificar se porta 8000 está livre
netstat -ano | findstr :8000

# Matar processo na porta 8000 (Windows)
taskkill /PID <PID> /F
```

### Frontend não conecta ao backend

- Verificar `VITE_API_URL` em `.env` do frontend
- Verificar CORS em `api/main.py` (varável `ALLOWED_ORIGINS`)
- Verificar `X-API-Key` header nas requisições

### Coleta retorna erro "PID não encontrado"

- Verificar se `coleta_status.json` existe
- Deletar arquivo e tentar novamente
- Checar permissões da pasta

### SSE não recebe eventos

- Verificar console do browser (DevTools F12)
- Verificar se servidor está rodando
- Testar com: `curl http://localhost:8000/coleta/status`

---

## 📈 Monitorar Agendamento

Para verificar se o job semanal está configurado:

```bash
# Verificar logs do backend
# Procure por: "[INFO] APScheduler iniciado com job semanal (seg 06:00)"

# Simular job em poucos minutos (para teste)
# Editar api/coleta.py linha ~180:
# trigger = CronTrigger(day_of_week=0, hour=6, minute=30)  # Seg 06:30
# trigger = CronTrigger(minute=*/2)  # A cada 2 minutos (para teste)
```

---

## 📚 Documentação Relacionada

- [GUIA_COLETA_DADOS.md](GUIA_COLETA_DADOS.md) - Arquitetura técnica completa
- [CLAUDE.md](CLAUDE.md) - Instruções do projeto
- [test_coleta_integration.py](test_coleta_integration.py) - Testes de integração
- API Docs: http://localhost:8000/docs (Swagger)

---

## ✅ Checklist Final

Antes de colocar em produção:

- [ ] `.env` está configurado com todas variáveis
- [ ] Backend inicia sem erros
- [ ] Frontend build foi bem-sucedido (`npm run build`)
- [ ] Testes passaram (`python test_coleta_integration.py`)
- [ ] Página `/coleta` carrega sem erro
- [ ] Botão "Buscar Dados" funciona e mostra progresso
- [ ] Chat mostra exemplos para produtores rurais
- [ ] Gráficos carregam com dados reais do Supabase

---

## 🎯 Próximas Melhorias (Sugeridas)

- [ ] Alertas por email ao fim da coleta
- [ ] Dashboard com histórico de coletas
- [ ] Exportar dados em CSV/Excel
- [ ] API de webhooks para notificações
- [ ] Modo offline com sincronização

---

**Desenvolvido com ❤️ para AgroIA-RMC**

*Última atualização: 27/04/2026*
