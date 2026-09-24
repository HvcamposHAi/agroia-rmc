# Fazer o AgroIA-RMC voltar ao ar — sem pagar

Passo a passo para seguir clicando. Não precisa entender o código.

---

## O que aconteceu, em uma frase

O Render **cortou a banda gratuita de 100 GB para 5 GB por mês** e suspendeu seu
workspace inteiro. Seu app não passou a gastar mais — a régua encolheu 20 vezes.

A cota é do **workspace**, somando seus dois projetos (`agroia-rmc` e
`WhatsApp_Disparo_Auto`). Por isso o plano abaixo **separa os dois**: cada
workspace tem sua própria cota de 5 GB.

---

## Resumo do plano

| Passo | O que faz | Tempo |
|---|---|---|
| 1 | Juntar as correções no GitHub | 2 min |
| 2 | Criar um workspace novo no Render | 3 min |
| 3 | Recriar o serviço lá (cota limpa) | 10 min |
| 4 | Apontar o site para o endereço novo | 5 min |
| 5 | Testar | 2 min |

> 💡 **Alternativa sem fazer nada:** os 5 GB resetam sozinhos no mês seguinte e o
> serviço volta. Se você não tem pressa, basta esperar. Mas vai estourar de novo,
> porque os dois projetos continuam dividindo a mesma cota.

---

# PASSO 1 — Juntar as correções no GitHub

Existe um Pull Request pronto com três coisas que o deploy novo precisa.

**1.1** Abra: https://github.com/HvcamposHAi/agroia-rmc/pull/1

**1.2** Clique no botão verde **Merge pull request**

**1.3** Confirme em **Confirm merge**

Pronto. Isso coloca no seu repositório:

- `requirements-api.txt` — a lista enxuta de dependências (sem isso, o build
  tenta instalar ~2 GB de PyTorch e falha no plano gratuito)
- A chave de API removida do código público
- A busca em PDFs usando o Supabase

---

# PASSO 2 — Criar um workspace novo

**2.1** Acesse https://dashboard.render.com

**2.2** No canto superior esquerdo, clique em **My Workspace** (ao lado do "M")

**2.3** No menu que abrir, clique em **Create New Workspace**

**2.4** Dê o nome: `agroia` (ou o que preferir)

**2.5** Escolha o plano **Hobby** (é o gratuito)

**2.6** Confirme

> ⚠️ **Por que um workspace novo:** o Render **não deixa mover serviços entre
> workspaces** — só recriar. E o workspace novo vem com 5 GB limpos, enquanto o
> antigo continua zerado até o reset.

---

# PASSO 3 — Recriar o serviço

Confira antes: no topo da tela deve aparecer o nome do workspace **novo**, não o
antigo. Se estiver no antigo, o serviço nasce suspenso junto.

**3.1** Clique em **New +** (no topo) → **Web Service**

**3.2** Conecte o repositório **HvcamposHAi/agroia-rmc**

> Se ele não aparecer, clique em **Configure account** e autorize o Render a
> enxergar o repositório.

**3.3** Preencha exatamente assim:

| Campo | Valor |
|---|---|
| Name | `agroia-api` |
| Language | `Python 3` |
| Branch | `main` |
| Build Command | `pip install -r requirements-api.txt` |
| Start Command | `uvicorn api.main:app --host 0.0.0.0 --port $PORT` |
| Instance Type | `Free` |

> ⚠️ **O Build Command é o ponto onde mais se erra.** Tem que ser
> `requirements-api.txt` (com `-api`), não `requirements.txt`. O arquivo sem
> `-api` instala PyTorch e Playwright, que não cabem no plano gratuito.

**3.4** Role até **Environment Variables** e adicione **seis**. Os valores estão
no seu arquivo `.env` (abra com o Bloco de Notas):

| Nome | Onde pegar o valor |
|---|---|
| `SUPABASE_URL` | linha `SUPABASE_URL` do `.env` |
| `SUPABASE_KEY` | linha `SUPABASE_KEY` do `.env` |
| `ANTHROPIC_API_KEY` | linha `ANTHROPIC_API_KEY` do `.env` |
| `API_SECRET_KEY` | linha `API_SECRET_KEY` do `.env` |
| `ALLOWED_ORIGINS` | `https://agroia-rmc.pages.dev` |
| `PYTHON_VERSION` | `3.11.9` |

> 🔑 **Guarde a `API_SECRET_KEY`** — você vai colar o **mesmo valor** no Passo 4.
> Se os dois lados não baterem, o site responde "403".

**3.5** Clique em **Create Web Service** e aguarde o build (3 a 6 minutos).

**3.6** Quando terminar, o Render mostra o endereço no topo, algo como:

```
https://agroia-api.onrender.com
```

**Copie esse endereço — é o Passo 4.**

**3.7** Teste: abra o endereço com `/health` no final:

```
https://agroia-api.onrender.com/health
```

Tem que aparecer: `{"status":"ok","database":"connected"}` ✅

---

# PASSO 4 — Apontar o site para o endereço novo

O endereço mudou, então o site precisa saber disso.

**4.1** Acesse https://dash.cloudflare.com

**4.2** Menu lateral → **Workers & Pages** → projeto **agroia-rmc**

**4.3** Aba **Settings** → **Environment variables** → seção **Production**

**4.4** Ajuste estas duas (edite se já existirem, crie se não):

| Nome | Valor |
|---|---|
| `VITE_API_URL` | o endereço do Passo 3.6 |
| `VITE_API_SECRET_KEY` | a **mesma** `API_SECRET_KEY` do Passo 3.4 |

**4.5** Salve.

**4.6** Vá na aba **Deployments** → no deploy mais recente → botão **...** →
**Retry deployment**

> ⚠️ **Este passo é obrigatório e é o mais esquecido.** As variáveis só entram no
> site quando ele é reconstruído. Sem isso, nada muda.

---

# PASSO 5 — Testar

**5.1** Abra https://agroia-rmc.pages.dev/assistente com **Ctrl + Shift + R**

> O Ctrl+Shift+R ignora a versão antiga guardada no navegador.

**5.2** Faça uma pergunta, por exemplo:
*"Quais hortaliças a prefeitura mais comprou?"*

**5.3** A primeira pergunta pode demorar **até 1 minuto** — o plano gratuito
"dorme" após 15 minutos parado. As seguintes são rápidas.

**5.4** Teste final: peça para alguém abrir o link no celular, no 4G. Se
responder, está no ar de verdade. 🎉

> 🎓 **Antes da banca:** faça uma pergunta qualquer 5 minutos antes, para acordar
> o servidor.

---

## Se der errado

| O que você vê | Causa | Solução |
|---|---|---|
| Build falha com erro de memória / `Killed` | Build Command errado | Passo 3.3 — tem que ser `requirements-api.txt` |
| `ModuleNotFoundError` no log | Faltou o merge do PR | Refaça o Passo 1 e clique em **Manual Deploy** |
| **403** ao perguntar | Chaves diferentes | As do Passo 3.4 e 4.4 têm que ser idênticas |
| Erro com a palavra **CORS** | Origem não autorizada | `ALLOWED_ORIGINS` = `https://agroia-rmc.pages.dev`, sem barra no final |
| Site continua com o erro antigo | Faltou reconstruir | Refaça o Passo 4.6 |
| `Missing required env vars` | Faltou variável | Passo 3.4 — confira as seis |
| Primeira pergunta demora ~1 min | Normal no plano gratuito | Espere |

---

## O que muda no servidor novo

O build enxuto deixa de fora bibliotecas pesadas. O que isso afeta:

| Recurso | No servidor | No seu PC |
|---|---|---|
| Assistente (perguntas sobre licitações, itens, fornecedores) | ✅ | ✅ |
| Páginas Início, Demanda, Ofertas | ✅ | ✅ |
| Busca dentro de PDFs (RAG) | ⚠️ avisa que não está disponível | ✅ |
| Comparador de motores (OpenAI/Gemini) | ⚠️ só Claude | ✅ |
| Coleta de dados | roda pelo GitHub Actions | ✅ |

Nada quebra: os recursos indisponíveis avisam e o resto segue funcionando.

---

## Para não estourar de novo

Depois que estiver no ar, vale acompanhar o consumo:

**Metrics → Bandwidth** do serviço novo, uma vez por mês.

Agora que os projetos estão separados, esse número mostra **só** o AgroIA — o que
finalmente responde se os 5 GB eram dele ou do projeto de WhatsApp.

Se mesmo sozinho ele se aproximar dos 5 GB, o plano B é migrar para o
**Hugging Face Spaces**: gratuito, sem cartão, 16 GB de RAM e sem esse limite de
banda. Me peça o guia se chegar a esse ponto.
