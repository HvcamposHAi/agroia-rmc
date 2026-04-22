# 🔒 Guia de Segurança de Credenciais - AgroIA-RMC

## ⚠️ CRÍTICO: Credenciais Comprometidas Detectadas

### Problema Identificado
O arquivo `.env` contendo credenciais **foi commitado múltiplas vezes** no histórico do git:
- `ANTHROPIC_API_KEY` (sk-ant-api03-...)
- `SUPABASE_KEY` (sb_secret_...)
- `GOOGLE_CLIENT_SECRET`
- `API_SECRET_KEY`

**Por isso suas chaves são revogadas constantemente**: plataformas como Anthropic, Google e Supabase detectam automaticamente quando credenciais aparecem em repositórios públicos/compartilhados e as revogam como medida de segurança.

---

## ✅ Solução: Limpar Histórico Git + Proteger Futuro

### Passo 1: Revogar Todas as Chaves (URGENTE)
Execute imediatamente no Anthropic, Google Cloud e Supabase:
1. **Anthropic**: https://console.anthropic.com/account/keys → Delete old key → Create new key
2. **Google**: https://console.cloud.google.com/credentials → Delete compromised key → Create new
3. **Supabase**: Dashboard → Settings → API Keys → Rotate key

### Passo 2: Remover Credenciais do Histórico Git
Use `git-filter-repo` (alternativa segura a `git filter-branch`):

```bash
# 1. Instale git-filter-repo
pip install git-filter-repo

# 2. Remova .env do histórico
cd "c:/Users/hvcam/Meu Drive/Pessoal/Mestrado/Dissertação/agroia-rmc"
git filter-repo --invert-paths --path .env

# 3. Force push para origin (CUIDADO: rescreve histórico)
git push origin --force --all
```

### Passo 3: Impedir Futuros Commits de Credenciais

#### ✅ Setup Correto Agora:

**Arquivo: `.env` (NÃO versionado)**
```
SUPABASE_URL=https://rsphlvcekuomvpvjqxqm.supabase.co
SUPABASE_KEY=<nova_chave_revogada>
GOOGLE_CLIENT_ID=502831260281-6i6nkqsl4900mf8j740hei442j0pptl3.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=<nova_chave_revogada>
GOOGLE_DRIVE_FOLDER_ID=1OvnRid5tsh_zXtCPGBYjbl8Uh3XgVge7
ANTHROPIC_API_KEY=sk-ant-<nova_chave_revogada>
API_SECRET_KEY=<nova_chave_revogada>
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
```

**Arquivo: `.env.example` (SIM, versionado - template público)**
```
SUPABASE_URL=https://rsphlvcekuomvpvjqxqm.supabase.co
SUPABASE_KEY=your_supabase_key_here
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here
GOOGLE_DRIVE_FOLDER_ID=your_folder_id_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
API_SECRET_KEY=your_api_secret_key_here
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
```

### Passo 4: Verificar .gitignore (JÁ ESTÁ CORRETO)
Seu `.gitignore` já inclui:
```
# Environment & Secrets
.env
.env.local
.env.*.local
```
✅ Perfeito! Apenas garanta que `.env` nunca é commitado.

### Passo 5: Git Hooks para Prevenir Acidentes
Crie arquivo `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Previne commit de .env ou chaves expostas

if git diff --cached | grep -E "sk-ant|sb_secret|GOCSPX|API_SECRET"; then
    echo "❌ ERRO: Arquivo contém credenciais sensíveis!"
    echo "Remova as credenciais ou use .env não versionado"
    exit 1
fi

if git diff --cached --name-only | grep -E "^\.env$"; then
    echo "❌ ERRO: Não commite .env diretamente!"
    echo "Use .env.example em vez disso"
    exit 1
fi
```

Tornar executável:
```bash
chmod +x .git/hooks/pre-commit
```

---

## 🏗️ Fluxo de Trabalho Seguro para o Projeto

### Localmente (seu computador)
1. Crie `.env` com suas credenciais reais
2. Nunca commite `.env`
3. Use `python etapa2_itens_v9.py` (lê `.env` automaticamente)

### Em CI/CD ou Servidor
Configure variáveis de ambiente no serviço:
- **GitHub Actions**: Secrets → `SUPABASE_KEY`, `ANTHROPIC_API_KEY`, etc.
- **Vercel/Render**: Environment variables no painel
- **Docker**: Use `ARG` em tempo de build, nunca hardcode

Exemplo para GitHub Actions (`.github/workflows/collect.yml`):
```yaml
jobs:
  collect:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run collection
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
        run: python etapa2_itens_v9.py
```

---

## 📋 Checklist de Implementação

- [ ] **Revogar todas as chaves antigas** (Anthropic, Google, Supabase)
- [ ] **Gerar novas credenciais** e guardar em local seguro
- [ ] **Executar `git filter-repo`** para limpar histórico
- [ ] **Force push** para origin
- [ ] **Atualizar `.env`** localmente com novas chaves
- [ ] **Criar `.env.example`** template
- [ ] **Configurar pre-commit hook**
- [ ] **Testar**: `python diagnostico_portal.py` com nova chave

---

## 🔍 Verificar se Está Seguro

```bash
# Verifica se .env foi commitado
git log --all --name-status | grep ".env"

# Verifica se há chaves no histórico
git log --all --patch | grep -E "sk-ant|sb_secret|GOCSPX" | wc -l
# Se output > 0: ainda há exposição, precisa filtrar

# Verifica .gitignore
cat .gitignore | grep "^\.env"
# Deve mostrar: .env
```

---

## 📚 Referências
- [GitHub: Removing Sensitive Data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
- [git-filter-repo Official](https://github.com/newren/git-filter-repo)
- [OWASP: Secrets Management](https://owasp.org/www-community/Sensitive_Data_Exposure)
