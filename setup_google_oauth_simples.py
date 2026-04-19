"""
Setup Google OAuth - Versão Simples (sem servidor local)
Gera token que será reutilizado automaticamente
"""

import os
from dotenv import load_dotenv, set_key
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import pickle
import json
import webbrowser

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def setup_google_oauth_simples():
    """Fazer autenticação OAuth simples"""

    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("[!] GOOGLE_CLIENT_ID ou GOOGLE_CLIENT_SECRET não configurado")
        return False

    # Criar arquivo de configuração
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"]  # Out-of-band (copiar/colar código)
        }
    }

    with open("oauth_config.json", "w") as f:
        json.dump(client_config, f)

    print("\n" + "="*70)
    print("AUTENTICAÇÃO GOOGLE DRIVE")
    print("="*70)
    print("\n[1] Uma janela do navegador vai abrir")
    print("[2] Clique em 'Permitir' para autorizar acesso ao Google Drive")
    print("[3] Copie o CÓDIGO que aparece")
    print("[4] Cole o código aqui\n")

    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            "oauth_config.json",
            scopes=SCOPES,
            redirect_uri="urn:ietf:wg:oauth:2.0:oob"
        )

        # Abrir navegador
        auth_url, _ = flow.authorization_url()
        webbrowser.open(auth_url)

        print(f"[*] Abrindo: {auth_url}\n")

        # Pedir código manualmente
        code = input("[?] Cole o CÓDIGO de autorização aqui: ").strip()

        if not code:
            print("[!] Código vazio!")
            return False

        # Trocar código por credenciais
        flow.fetch_token(code=code)
        creds = flow.credentials

        # Salvar token
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

        print("\n[OK] Autenticação concluída com sucesso! ✓")
        print("[OK] Token salvo em: token.pickle")
        print("[OK] Você pode agora rodar: python etapa3_google_drive.py\n")

        # Limpar arquivo temporário
        if os.path.exists("oauth_config.json"):
            os.remove("oauth_config.json")

        return True

    except Exception as e:
        print(f"\n[!] Erro: {e}")
        if os.path.exists("oauth_config.json"):
            os.remove("oauth_config.json")
        return False

if __name__ == "__main__":
    setup_google_oauth_simples()
