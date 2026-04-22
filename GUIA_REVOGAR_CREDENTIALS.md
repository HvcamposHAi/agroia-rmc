# 🔐 Guia Passo a Passo: Revogar e Criar Novas Credentials

## 1️⃣ SUPABASE (Banco de Dados)

### Localizar Secret Keys
1. Abra **https://supabase.com/dashboard/project/rsphlvcekuomvpvjqxqm/settings/api-keys**
2. Clique em **"Settings"** (menu esquerdo)
3. Clique em **"API Keys"**

### Seção 1: Secret Keys (REVISAR)
- **Local**: "Secret keys" → "Your project is not accessible via secret keys..."
- ❌ **NENHUMA SECRET KEY ATIVA** (ótimo sinal!)
- Se houver uma ativa com prefixo `sb_secret_`: **DELETE-A**

### Seção 2: Publishable Key (PÚBLICO, OK usar)
- **Local**: "Publishable key" → "default"
- 🟢 `sb_publishable_j883jFkldg-916ab-1aydFQ_1qwm_...` 
- ✅ Pode usar em browser (seguro, read-only)

### ❌ Revogar Chave Comprometida
```
Se você tiver uma chave com prefixo "sb_secret_" em .env:

1. Vá em Settings → API Keys
2. Procure por "Service Role Key" ou "Secret keys"
3. Clique em DELETE ou REVOKE
4. Confirme
5. Nenhuma nova chave é gerada (Supabase usa apenas Publishable + anon keys)
```

### ✅ Usar a Chave Segura
```python
# Seu .env deve ter APENAS:
SUPABASE_URL=https://rsphlvcekuomvpvjqxqm.supabase.co
SUPABASE_KEY=sb_publishable_j883jFkldg-916ab-1aydFQ_1qwm_...
```

---

## 2️⃣ GOOGLE CLOUD (Drive + Gmail)

### Localizar Credentials
1. Abra **https://console.cloud.google.com/apis/credentials?project=agroia-rmc**
2. Clique em **"Credenciais"** (menu esquerdo)

### Seção 1: Chaves de API
- **Local**: "Chaves de API"
- ✅ **Nenhuma chave a ser exibida**
- OK - não estão usando API keys diretas

### Seção 2: IDs do Cliente OAuth 2.0 (ENCONTRADO)
- **Local**: "IDs do cliente OAuth 2.0"
- ⚠️ **"Cliente de computador 1"** criado em **13 de abr. de 2026**
- ID: `502831262681-616n...`

### ❌ Revogar Cliente OAuth Comprometido
```
1. Clique em "Cliente de computador 1"
2. Clique em DELETE (ícone de lixeira)
3. Confirme "Excluir"
```

### ✅ Criar Novo Cliente OAuth 2.0
```
1. Volte para https://console.cloud.google.com/apis/credentials
2. Clique em "+ Criar credenciais"
3. Escolha "ID do cliente OAuth"
4. Tipo: "Aplicativo para computador" (Desktop)
5. Nome: "agroia-rmc-new-2026-04-21"
6. Clique em "Criar"
7. Download JSON (salve em local seguro)
8. Copie o GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET
```

### Localizar GOOGLE_CLIENT_SECRET
```
Após criar nova credencial:

1. Clique em "Cliente de computador 1" (novo)
2. Copie:
   - CLIENT_ID: 502831262681-616n...
   - CLIENT_SECRET: GOCSPX-...
```

---

## 3️⃣ ANTHROPIC (Claude API)

### Localizar API Keys
1. Abra **https://console.anthropic.com/account/keys** (ou https://api.anthropic.com/settings/keys)
2. Você deve estar logado em sua conta

### ❌ Revogar Chave Comprometida
```
1. Procure pela chave com prefixo "sk-ant-api03-..."
2. Se ela tiver mais de alguns dias, DELETE
3. Clique em DELETE ou REVOKE
4. Confirme
```

### ✅ Criar Nova API Key
```
1. Clique em "+ Create Key"
2. Nomeie: "agroia-rmc-new-2026-04-21"
3. Clique em "Create"
4. **COPIE IMEDIATAMENTE** a chave (sk-ant-...)
   - Não será mostrada novamente!
5. Salve em local seguro
```

---

## 📋 Checklist: Ordem de Execução

### Fase 1: Revogar Chaves Antigas (HOJE)
- [ ] **Supabase**: Verificar e deletar Secret Key comprometida (se existir)
- [ ] **Google Cloud**: Deletar "Cliente de computador 1" (OAuth comprometido)
- [ ] **Anthropic**: Deletar chave `sk-ant-api03-dnZo220H...`

### Fase 2: Criar Novas Chaves (HOJE)
- [ ] **Google Cloud**: Criar novo Cliente OAuth 2.0 Desktop
  - Copie: `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET`
- [ ] **Anthropic**: Criar nova API Key
  - Copie: `ANTHROPIC_API_KEY` (sk-ant-...)
- [ ] **Supabase**: Copiar Publishable Key já existente
  - `SUPABASE_URL` e `SUPABASE_KEY` (já estão corretos)

### Fase 3: Atualizar .env Local (HOJE)
```bash
cd "c:/Users/hvcam/Meu Drive/Pessoal/Mestrado/Dissertação/agroia-rmc"

# Editar .env com as NOVAS chaves
nano .env
# ou use VS Code para editar
```

**Conteúdo do novo `.env`:**
```
SUPABASE_URL=https://rsphlvcekuomvpvjqxqm.supabase.co
SUPABASE_KEY=sb_publishable_j883jFkldg-916ab-1aydFQ_1qwm_...
GOOGLE_CLIENT_ID=502831262681-616n...apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-<nova_chave>
GOOGLE_DRIVE_FOLDER_ID=1OvnRid5tsh_zXtCPGBYjbl8Uh3XgVge7
ANTHROPIC_API_KEY=sk-ant-<nova_chave>
API_SECRET_KEY=JjcygLlSmpGHrSyHYMI7CrLxPEVDDF-D_R6KhAa2Ln4
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
```

### Fase 4: Testar Nova Chave
```bash
# Test Supabase connection
python verificar_status_db.py

# Test Anthropic API
python -c "import os; print(os.getenv('ANTHROPIC_API_KEY')[:20])"
```

### Fase 5: Limpar Git (AMANHÃ)
```bash
# Remover .env do histórico
pip install git-filter-repo
git filter-repo --invert-paths --path .env
git push origin --force --all
```

---

## 🚨 Avisos Importantes

### ⚠️ Não Versionado
**Nunca** faça commit de `.env`:
```bash
# Verificar
git status
# Deve mostrar: "modified:   .env" (não staged)

# Garantir que está em .gitignore
grep "^\.env$" .gitignore
# Output: .env
```

### ⚠️ Cópia de Backup
Antes de deletar chaves antigas:
1. Salve as credenciais atuais em um **arquivo local seguro** (não em git)
   ```
   ~/Desktop/agroia_backup_credentials.txt (seguro localmente)
   ```
2. Após 24h (ou quando tiver testado tudo), delete o arquivo

### ✅ Criar `.env.example`
```bash
# Copie .env para .env.example e remova valores
cp .env .env.example
nano .env.example

# Editar: remover valores reais, deixar placeholders
SUPABASE_KEY=your_supabase_key_here
GOOGLE_CLIENT_SECRET=your_google_secret_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

---

## 🔍 Verificação Final

```bash
# Confirmar que .env não será commitado
git status | grep ".env"
# Output: modified:   .env (não staged para commit - OK!)

# Confirmar que .env.example será commitado
git status | grep ".env.example"
# Output: Untracked files: .env.example

# Visualizar o que será commitado
git diff --staged | grep -E "sk-ant|sb_secret|GOCSPX"
# Output: nada (seguro!)
```

---

## 📞 Próximos Passos
1. Execute os passos acima
2. Teste com `python diagnostico_portal.py`
3. Quando tudo estiver funcionando, execute:
   ```bash
   git filter-repo --invert-paths --path .env
   git push origin --force --all
   ```
4. Informe quando terminar para dar sequência ao plano de segurança
