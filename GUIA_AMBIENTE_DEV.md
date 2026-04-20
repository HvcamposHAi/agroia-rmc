# 📘 Guia Completo: Ambiente DEV Local e Deploy Online

## 🎯 Objetivo

Este guia mostra como:
1. **Configurar ambiente DEV local** (sua máquina Windows)
2. **Rodar frontend + backend juntos**
3. **Testar tudo localmente**
4. **Deploy online grátis em Vercel**

---

## 📍 PARTE 1: Ambiente DEV Local (Windows)

### Pré-requisitos

Você já tem instalado:
- ✅ Node.js 18+ (necessário para React)
- ✅ Python 3.10+ (necessário para FastAPI)
- ✅ Git (para versionamento)

Para verificar:
```bash
node --version    # Deve ser v18+
python --version  # Deve ser 3.10+
```

---

## 🚀 PARTE 2: Rodar Frontend Local (Desenvolvimento)

### Passo 1: Abrir Terminal (PowerShell ou CMD)

No Windows, abra uma janela de **PowerShell** ou **CMD**.

Navegue até a pasta do projeto:
```bash
cd "C:\Users\hvcam\Meu Drive\Pessoal\Mestrado\Dissertação\agroia-rmc\agroia-frontend"
```

### Passo 2: Instalar Dependências (primeira vez)

```bash
npm install
```

Isso baixa todas as bibliotecas necessárias. Leva 1-2 minutos.

### Passo 3: Rodar Servidor de Desenvolvimento

```bash
npm run dev
```

**Resultado esperado:**
```
  ➜  Local:   http://localhost:5173/
```

⚠️ **IMPORTANTE:** Deixe este terminal **ABERTO E RODANDO**. Ele não deve ser fechado.

### Passo 4: Abrir no Navegador

Abra seu navegador e vá para:
```
http://localhost:5173
```

Você deverá ver a interface do AgroIA-RMC com:
- Sidebar esquerdo (verde "🌾 AgroIA-RMC")
- Chat, Dashboard, Consultas

✅ **Frontend está rodando!**

---

## 🔧 PARTE 3: Rodar Backend Local (API FastAPI)

### Passo 1: Abrir Novo Terminal

Abra **OUTRO terminal** (não feche o anterior com `npm run dev`).

Navegue até a pasta do backend:
```bash
cd "C:\Users\hvcam\Meu Drive\Pessoal\Mestrado\Dissertação\agroia-rmc"
```

### Passo 2: Criar Ambiente Virtual Python

Na pasta `agroia-rmc`, rode:

**No Windows (PowerShell):**
```bash
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Ou no CMD:**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

Você saberá que funcionou quando aparecer `(venv)` no início da linha:
```
(venv) C:\Users\hvcam\Meu Drive\...>
```

### Passo 3: Instalar Dependências Python

```bash
pip install -r requirements.txt
```

Se não houver `requirements.txt`, instale manualmente:
```bash
pip install fastapi uvicorn supabase python-dotenv playwright beautifulsoup4 anthropic
```

### Passo 4: Rodar o Backend

```bash
python api/main.py
```

**Resultado esperado:**
```
INFO:     Application startup complete
INFO:     Uvicorn running on http://127.0.0.1:8000
```

✅ **Backend está rodando na porta 8000!**

---

## ✅ PARTE 4: Testar Integração Local

Agora você tem:
- ✅ Frontend em `http://localhost:5173`
- ✅ Backend em `http://localhost:8000`

### Teste 1: Health Check

Abra outro navegador e visite:
```
http://localhost:8000/health
```

Deve ver:
```json
{"status": "ok"}
```

### Teste 2: Chat no Frontend

1. Vá para `http://localhost:5173`
2. Clique em uma mensagem de exemplo
3. Escreva: "Quais são as top culturas?"
4. Clique em Send

**O que deve acontecer:**
- Loading spinner aparece
- Backend processa (Claude analisa)
- Resposta aparece no chat
- Tools usadas aparecem como badges

### Teste 3: Dashboard

1. Clique em "Dashboard" no sidebar
2. Veja os gráficos carregando dados do Supabase

### Teste 4: Consultas

1. Clique em "Consultas" no sidebar
2. Use filtros para buscar itens
3. Veja paginação funcionando

---

## 🔌 Variáveis de Ambiente Necessárias

### Frontend (.env.local)

Arquivo: `agroia-frontend/.env.local`

```env
VITE_API_URL=http://localhost:8000
VITE_SUPABASE_URL=https://rsphlvcekuomvpvjqxqm.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Backend (.env)

Arquivo: `agroia-rmc/.env`

```env
SUPABASE_URL=https://rsphlvcekuomvpvjqxqm.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
GOOGLE_DRIVE_FOLDER_ID=1234567890abcdef
ANTHROPIC_API_KEY=sk-ant-v4-xxx
```

> ⚠️ Peça estas chaves para o administrador do projeto

---

## 🎯 Fluxo Típico de Desenvolvimento

```
Terminal 1 (nunca fechar)
├─ npm run dev (Frontend em 5173)
│  └─ Edita arquivo .tsx → Hot reload automático
│
Terminal 2 (nunca fechar)
├─ python api/main.py (Backend em 8000)
│  └─ Edita arquivo .py → Precisa reiniciar
│
Terminal 3 (opcional)
├─ Para rodar scripts, verificar git status, etc
```

### Workflow Típico:

1. **Modificar página Chat** → Frontend recarrega automático (5173)
2. **Modificar endpoint FastAPI** → Deve reiniciar `python api/main.py`
3. **Recarregar página** → Ver mudanças refletidas

---

## 🚨 Erros Comuns e Soluções

### ❌ "Port 5173 already in use"
```
Solução: Outro processo está usando a porta
1. Abra Task Manager (Ctrl+Shift+Esc)
2. Procure "node.exe" 
3. Clique com botão direito → End Task
4. Tente npm run dev novamente
```

### ❌ "Cannot GET /chat"
```
Solução: Backend não está rodando
1. Abra Terminal 2
2. Verifique se python api/main.py está rodando
3. Veja se http://localhost:8000/health responde
```

### ❌ "Supabase connection error"
```
Solução: Chave .env.local inválida
1. Verifique VITE_SUPABASE_ANON_KEY em agroia-frontend/.env.local
2. Compare com a chave real do Supabase
3. Reinicie npm run dev
```

### ❌ "TypeError: Cannot read 'data' of undefined"
```
Solução: Banco de dados vazio ou view não existe
1. Verifique se vw_itens_agro existe no Supabase
2. Execute etapa2_itens_v9.py para popular dados
```

---

## 🌐 PARTE 5: Deploy Online Grátis em Vercel

### Por que Vercel?
- ✅ Grátis para projetos open source
- ✅ Deploy automático a cada git push
- ✅ HTTPS gratuito
- ✅ Suporta React + Next.js perfeitamente

### Passo 1: Criar Conta no Vercel

1. Vá para https://vercel.com
2. Clique em "Sign Up"
3. Escolha "GitHub" ou email
4. Confirme email

### Passo 2: Conectar GitHub ao Projeto

Se ainda não está no GitHub:

```bash
cd "C:\Users\hvcam\Meu Drive\Pessoal\Mestrado\Dissertação\agroia-rmc"
git init
git add .
git commit -m "Initial commit: AgroIA-RMC frontend"
git branch -M main
git remote add origin https://github.com/seu-usuario/agroia-rmc.git
git push -u origin main
```

Substitua `seu-usuario` por seu username do GitHub.

### Passo 3: Deploy no Vercel

1. Abra https://vercel.com/dashboard
2. Clique em "Add New..." → "Project"
3. Selecione o repositório `agroia-rmc`
4. Configurações:
   - **Root Directory:** `agroia-frontend`
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`
5. Clique "Deploy"

⏳ Aguarde 2-3 minutos...

✅ **Seu site está online!**

URL será algo como: `https://agroia-rmc.vercel.app`

### Passo 4: Adicionar Variáveis de Ambiente no Vercel

1. Vá para "Settings" do projeto no Vercel
2. Clique em "Environment Variables"
3. Adicione:
   ```
   VITE_API_URL = https://seu-backend.com (ou localhost:8000 se tiver)
   VITE_SUPABASE_URL = https://rsphlvcekuomvpvjqxqm.supabase.co
   VITE_SUPABASE_ANON_KEY = eyJhbGciOiJIUzI1NiI...
   ```
4. Clique "Save"
5. Vá para "Deployments" e clique "Redeploy"

✅ **Frontend online com variáveis corretas!**

---

## 🔗 Deploy Backend (FastAPI)

### Opção 1: Render.com (Recomendado)

1. Vá para https://render.com
2. Sign up com GitHub
3. Clique em "New" → "Web Service"
4. Conecte seu repositório GitHub
5. Configurações:
   - **Name:** agroia-rmc-api
   - **Runtime:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn api.main:app --host 0.0.0.0 --port 8000`
6. Adicione Environment Variables (mesmas do .env)
7. Clique "Deploy"

⏳ Deploy leva 5-10 minutos...

✅ Backend online em: `https://agroia-rmc-api.onrender.com`

### Opção 2: Railway.app

Similar ao Render, mas:
1. Vá para https://railway.app
2. Sign up com GitHub
3. New Project → GitHub repo
4. Adicione `requirements.txt` se não tiver
5. Deploy automático

---

## 📊 Checklist Final

### Local (Antes de Deploy)

- [ ] `npm run dev` roda sem erros na porta 5173
- [ ] `python api/main.py` roda na porta 8000
- [ ] Frontend carrega em `http://localhost:5173`
- [ ] Chat funciona e chama backend
- [ ] Dashboard mostra gráficos
- [ ] Consultas filtra itens
- [ ] Console do navegador sem erros (F12)

### Online

- [ ] Frontend deploy no Vercel
- [ ] Backend deploy no Render/Railway
- [ ] Variáveis de ambiente configuradas
- [ ] CORS habilitado no backend
- [ ] Teste GET /health funciona
- [ ] Chat online funciona

---

## 📚 Links Úteis

- **React Docs:** https://react.dev
- **Vite Docs:** https://vitejs.dev
- **FastAPI Docs:** https://fastapi.tiangolo.com
- **Tailwind Docs:** https://tailwindcss.com
- **Supabase Docs:** https://supabase.com/docs
- **Vercel Docs:** https://vercel.com/docs
- **Render Docs:** https://render.com/docs

---

## 🆘 Precisa de Ajuda?

Se algo não funcionar:

1. **Veja console do navegador:** F12 → Console
2. **Veja terminal do backend:** Procure por "error"
3. **Procure no Google:** Copie a mensagem de erro completa
4. **GitHub Issues:** Procure no repo do projeto

---

**Criado em:** 2026-04-19  
**Última atualização:** 2026-04-19  
**Status:** ✅ Completo e testado
