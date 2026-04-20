# 🔧 Setup Google Drive - Guia Completo

## Passo 1: Obter Client Secret

1. **Acesse:** https://console.cloud.google.com/
2. **Selecione seu projeto** (já tem um com Client ID: `502831260281-6i6nkqsl4900mf8j740hei442j0pptl3.apps.googleusercontent.com`)
3. **Vá para:** Credenciais → Clique no Client ID
4. **Copie o "Client Secret"**

---

## Passo 2: Criar Pasta no Google Drive

1. **Acesse:** https://drive.google.com/
2. **Clique em "+ Nova Pasta"**
3. **Nome:** `AgroIA-Documentos`
4. **Abra a pasta** e copie o ID da URL:
   ```
   https://drive.google.com/drive/folders/[ESTE-ID-AQUI]
   ```

---

## Passo 3: Configurar .env

Abra `c:/Users/hvcam/Meu Drive/Pessoal/Mestrado/Dissertação/agroia-rmc/.env` e adicione:

```bash
GOOGLE_CLIENT_ID=502831260281-6i6nkqsl4900mf8j740hei442j0pptl3.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=seu-client-secret-aqui
GOOGLE_DRIVE_FOLDER_ID=id-da-pasta-aqui
```

**Exemplo:**
```bash
SUPABASE_URL=https://rsphlvcekuomvpvjqxqm.supabase.co
SUPABASE_KEY=seu-supabase-key-aqui
GOOGLE_CLIENT_ID=502831260281-6i6nkqsl4900mf8j740hei442j0pptl3.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxx...
GOOGLE_DRIVE_FOLDER_ID=1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p
```

---

## Passo 4: Instalar Dependências

```bash
pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

---

## Passo 5: Executar Autenticação

```bash
python setup_google_oauth.py
```

Isso vai:
1. ✅ Abrir navegador
2. ✅ Pedir permissão para Google Drive
3. ✅ Salvar token em `token.pickle`
4. ✅ Gerar `.env` atualizado

---

## Passo 6: Rodar Coleta com Google Drive

```bash
python etapa3_google_drive.py
```

---

## ✅ Pronto!

Agora o script vai:
- ✅ Baixar PDFs do portal (SEM limite de tamanho)
- ✅ Fazer upload para Google Drive
- ✅ Salvar URL pública no banco de dados
- ✅ Processar todas as 32 páginas

---

## 🔗 Próximos Passos

1. Obter Client Secret
2. Criar pasta no Google Drive + copiar ID
3. Atualizar `.env`
4. Rodar `python setup_google_oauth.py`
5. Rodar `python etapa3_google_drive.py`
