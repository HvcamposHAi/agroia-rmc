# Guia: Sistema de Atualização de Dados (Manual + Semanal)

## 📋 Visão Geral

O sistema AgroIA-RMC agora oferece:

1. **Coleta Manual**: Clique no botão "Buscar Dados" na página `/coleta` para iniciar uma coleta sob demanda
2. **Coleta Semanal Automática**: Toda segunda-feira às 06:00 (horário local), o sistema busca novos dados automaticamente
3. **Data Dinâmica**: Sempre busca a partir da data mais recente no banco de dados
4. **Progresso em Tempo Real**: Acompanhe o avanço da coleta com KPIs ao vivo (processados, novos, pulados, erros)
5. **Estatísticas de Classificação**: Veja gráficos atualizados de licitações agrícolas vs não-agrícolas por categoria e ano

---

## 🚀 Como Usar

### Coleta Manual (Por Demanda)

1. Acesse `http://localhost:3000/coleta` no frontend
2. Clique no botão verde **"🔍 Buscar Dados"**
3. O sistema:
   - Query `MAX(dt_abertura)` do banco para saber a partir de qual data buscar
   - Abre um navegador Chromium automaticamente
   - Acessa o portal de licitações de Curitiba
   - Filtra por data inicial (mais recente do banco) até hoje
   - Coleta itens, fornecedores e empenhos
4. Acompanhe o progresso em tempo real:
   - Barra de progresso (%)
   - KPIs: processados, novos, pulados, erros
   - Status da etapa (iniciando, coletando, finalizado)

**Para cancelar**: clique no botão **"⛔ Cancelar"** que aparece durante a execução

---

### Coleta Semanal (Automática)

Não precisa fazer nada! O sistema está configurado para:
- Dia: **segunda-feira**
- Horário: **06:00 (local)**
- Frequência: **Semanal**

O job de agendamento é iniciado automaticamente ao rodar o backend:
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

No terminal, você verá:
```
[INFO] APScheduler iniciado com job semanal (seg 06:00)
```

---

## 🏗️ Arquitetura Técnica

### Backend (API FastAPI)

**Novos Endpoints:**

| Endpoint | Método | Descrição |
|---|---|---|
| `/coleta/iniciar` | POST | Inicia coleta manual |
| `/coleta/cancelar` | POST | Cancela coleta em andamento |
| `/coleta/status` | GET | Status atual da coleta |
| `/coleta/stream` | GET | SSE stream do progresso (atualiza a cada 2s) |
| `/coleta/stats` | GET | Estatísticas de classificação agrícola |

**Arquivo novo:** `api/coleta.py`
- `get_data_mais_recente()` - retorna MAX(dt_abertura) como DD/MM/YYYY
- `get_status()` - lê `coleta_status.json`
- `iniciar_coleta()` - lança subprocess com argumentos dinâmicos
- `cancelar_coleta()` - envia SIGTERM ao processo
- `get_stats_classificacao()` - queries Supabase para gráficos
- `configurar_agendamento(app)` - APScheduler BackgroundScheduler

**Arquivo modificado:** `api/main.py`
- Importa funções de `api/coleta.py`
- Adiciona os 5 endpoints acima
- Configura agendamento no event `@app.on_event("startup")`

---

### Backend (Scripts de Coleta)

**Arquivo modificado:** `etapa2_itens_v9.py`

Aceita argumentos via CLI:
```bash
python etapa2_itens_v9.py \
  --dt-inicio 30/04/2026 \
  --dt-fim 26/04/2026 \
  --progress-file coleta_status.json
```

Se não fornecidos:
- `--dt-inicio` usa `MAX(dt_abertura)` do banco
- `--dt-fim` usa data de hoje

Escreve progresso em `coleta_status.json` a cada 10 processos:
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
  "iniciado_em": "2026-04-26T10:15:30.123456",
  "atualizado_em": "2026-04-26T10:16:45.654321",
  "pid": 12345
}
```

---

### Frontend (React + TypeScript)

**Arquivo novo:** `agroia-frontend/src/pages/Coleta.tsx`

Componente com 3 seções:

**1. Status & Controle**
- Card mostrando status (idle/running/completed/cancelled/error)
- Botão "Buscar Dados" (desabilitado durante execução)
- Botão "Cancelar" (visível apenas quando running)
- Próxima execução agendada (seg 06:00)

**2. Progresso em Tempo Real** (aparece quando running)
- Barra de progresso estimada
- Texto da etapa
- 4 KPIs: processados, novos, pulados, erros
- Stream SSE via `EventSource` do endpoint `/coleta/stream`

**3. Estatísticas de Classificação** (sempre visível)
- 3 KPI cards: total licitações, total itens, cobertura agrícola %
- Pie Chart: Licitações Agrícolas vs Não-Agrícolas
- Bar Chart: Top 10 Categorias de Itens
- Bar Chart: Licitações Agrícolas por Ano

**Integração:**
- Rota adicionada em `App.tsx`: `<Route path="/coleta" element={<Coleta />} />`
- Nav item adicionado em `Layout.tsx`: `{ to: '/coleta', icon: '🔄', label: 'Atualização' }`

---

### Chat do Assistente

**Exemplos de Perguntas Atualizados** (`Chat.tsx`):

O chat agora exibe sugestões direcionadas a **produtores rurais interessados em vender para a prefeitura**:

1. "Quais hortaliças a prefeitura mais comprou nos últimos dois anos?"
2. "Qual foi o preço médio pago por kg de alface no PNAE em 2023?"
3. "A prefeitura compra banana da terra? Quanto pagou no último ano?"
4. "Qual programa compra mais de agricultores familiares — PNAE ou Armazém?"
5. "Quantos produtores forneceram alimentos para o PNAE em 2023?"
6. "Quanto a prefeitura gastou com compras de agricultura familiar em 2024?"

---

## 📊 Fluxo de Dados

```
Frontend (/coleta)
  ↓
User clica "Buscar Dados"
  ↓
POST /coleta/iniciar
  ↓
API (api/coleta.py)
  ├─ query MAX(dt_abertura) do Supabase
  ├─ resolve datas (DD/MM/YYYY)
  └─ subprocess.Popen(["python", "etapa2_itens_v9.py", "--dt-inicio", ..., "--progress-file", "coleta_status.json"])
  ↓
etapa2_itens_v9.py (subprocess)
  ├─ Abre Chromium
  ├─ Navega portal Curitiba
  ├─ Filtra licitações SMSAN/FAAC por data
  ├─ Coleta itens, fornecedores, empenhos
  ├─ Escreve coleta_status.json a cada 10 processos
  └─ Finaliza (completo, cancelado ou erro)
  ↓
Frontend (GET /coleta/stream)
  ├─ Conexão SSE para /coleta/stream
  ├─ Recebe status.json a cada 2 segundos
  └─ Atualiza UI em tempo real (barra, KPIs, status)
  ↓
Estatísticas (GET /coleta/stats)
  ├─ Query Supabase ao fim da coleta
  └─ Atualiza gráficos (agrícola %, categorias, anos)
```

---

## 🔄 Agendamento Semanal

O `APScheduler` é inicializado no startup do FastAPI:

```python
@app.on_event("startup")
async def startup_event():
    configurar_agendamento(app)
```

No arquivo `api/coleta.py`:

```python
scheduler = BackgroundScheduler(daemon=True)
trigger = CronTrigger(day_of_week=0, hour=6, minute=0)  # seg 06:00
scheduler.add_job(
    job_coleta_semanal,
    trigger=trigger,
    id="coleta_semanal",
    name="Coleta de dados semanal",
    replace_existing=True
)
scheduler.start()
```

Se já há coleta em andamento, o job verifica e ignora:
```python
def job_coleta_semanal():
    status = get_status()
    if status.get("status") == "running":
        logger.warning("Coleta já em andamento, ignorando")
        return
    sucesso, msg = iniciar_coleta()
    # log resultado
```

---

## ✅ Testes Recomendados

### 1. Testar Progresso em JSON

```bash
cd agroia-rmc
python etapa2_itens_v9.py \
  --dt-inicio 01/01/2019 \
  --dt-fim 02/01/2019 \
  --progress-file test_status.json
```

Verificar se `test_status.json` é criado e atualizado a cada 10 processos.

### 2. Testar Data Dinâmica

```bash
python -c "
from api.coleta import get_data_mais_recente
dt = get_data_mais_recente()
print(f'Última data no banco: {dt}')
"
```

### 3. Testar Endpoint de Status

```bash
curl http://localhost:8000/coleta/status
```

Deve retornar JSON com estrutura de status.

### 4. Testar Endpoint de Stats

```bash
curl http://localhost:8000/coleta/stats
```

Deve retornar contagens e percentuais.

### 5. Testar Stream SSE (no browser)

```javascript
// No console do browser
const source = new EventSource('http://localhost:8000/coleta/stream');
source.onmessage = (e) => console.log(JSON.parse(e.data));
```

### 6. Testar Frontend

- Navegar a `http://localhost:3000/coleta`
- Clicar "Buscar Dados"
- Acompanhar progresso em tempo real
- Verificar se barra, KPIs e status atualizam
- Clicar "Cancelar" e verificar se para

---

## 🐛 Troubleshooting

### "Coleta já em andamento"

Se você receber este erro, significa que há um processo anterior ainda ativo. Verifique:

```bash
# Listar processos Python
ps aux | grep python

# Matar processo específico (Windows)
taskkill /PID <pid> /F

# Ou deletar coleta_status.json e tentar novamente
rm coleta_status.json
```

### Frontend não vê atualizações de progresso

- Verifique se `coleta_status.json` está sendo criado no diretório raiz
- Verifique se o navegador permite EventSource/SSE (check CORS headers)
- Verifique logs do backend: `[INFO]` para SSE connections

### API retorna 400 "Missing API key"

- Verifique se `X-API-Key` header está sendo enviado nas requisições POST
- Verifique se `VITE_API_KEY` está definida no `.env` do frontend

### Agendamento não ativa na segunda-feira

- Verifique fuso horário local: `TZ` env var
- Verifique se o backend está rodando contínuamente
- Verifique logs: `[INFO] APScheduler iniciado...`

---

## 📦 Dependências Adicionadas

```
apscheduler==3.10.4
```

Já incluída em `requirements.txt`. Instale com:

```bash
pip install -r requirements.txt
```

---

## 📝 Resumo de Mudanças

| Arquivo | Tipo | Mudança |
|---------|------|---------|
| `etapa2_itens_v9.py` | Modificado | Adiciona argparse + progresso JSON |
| `api/coleta.py` | Novo | Lógica de coleta, agendamento, stats |
| `api/main.py` | Modificado | Imports + 5 endpoints + startup |
| `agroia-frontend/src/pages/Coleta.tsx` | Novo | UI com progresso + gráficos |
| `agroia-frontend/src/App.tsx` | Modificado | Rota /coleta |
| `agroia-frontend/src/components/Layout.tsx` | Modificado | Nav item "Atualização" |
| `agroia-frontend/src/pages/Chat.tsx` | Modificado | Sugestões para produtores |
| `requirements.txt` | Modificado | Adiciona apscheduler |

---

## 🎯 Próximos Passos Sugeridos

1. Testar coleta manual e acompanhar progresso no frontend
2. Simular agendamento ajustando hora do job para alguns minutos à frente
3. Monitorar logs e status.json durante execução
4. Validar que dados estão sendo classificados corretamente (relevante_agro)
5. Considerar alertas email/SMS ao término da coleta (feature futura)

---

**Desenvolvido com ❤️ para AgroIA-RMC**
