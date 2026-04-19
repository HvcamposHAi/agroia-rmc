"""
Setup Google OAuth - Autenticação simples para Google Drive
Gera token que será reutilizado automaticamente
"""

import os
from dotenv import load_dotenv, set_key
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import pickle

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def setup_google_oauth():
    """Fazer autenticação OAuth e salvar token"""

    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("[!] GOOGLE_CLIENT_ID ou GOOGLE_CLIENT_SECRET não configurado")
        print("[!] Configure em .env:")
        print('    GOOGLE_CLIENT_ID="seu-client-id"')
        print('    GOOGLE_CLIENT_SECRET="seu-client-secret"')
        return False

    # Criar arquivo de credenciais OAuth
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost:8080/"]
        }
    }

    # Salvar configuração temporária
    with open("oauth_config.json", "w") as f:
        import json
        json.dump(client_config, f)

    print("[*] Iniciando autenticação Google...")
    print("[*] Uma janela do navegador será aberta")
    print("[*] Clique em 'Permitir' para dar acesso ao Google Drive")

    flow = InstalledAppFlow.from_client_secrets_file(
        "oauth_config.json",
        scopes=SCOPES,
        redirect_uri="http://localhost:8080/"
    )

    creds = flow.run_local_server(port=8080)

    # Salvar token para uso futuro
    with open("token.pickle", "wb") as token:
        pickle.dump(creds, token)

    # Atualizar .env
    set_key(".env", "GOOGLE_OAUTH_TOKEN", "token.pickle")

    print("[OK] Autenticação concluída!")
    print("[OK] Token salvo em: token.pickle")
    print("[OK] Você pode agora rodar: python etapa3_google_drive.py")

    # Limpar arquivo temporário
    os.remove("oauth_config.json")

    return True

if __name__ == "__main__":
    setup_google_oauth()
