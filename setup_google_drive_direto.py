"""
Google Drive Setup - Versão Corrigida
Usa redirect_uri local correto
"""

import os
import sys
import json
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import pickle

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def main():
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
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "redirect_uris": ["http://localhost:8080/", "http://localhost:8080"]
        }
    }

    with open("oauth_config.json", "w") as f:
        json.dump(client_config, f)

    print("\n" + "="*70)
    print("SETUP GOOGLE DRIVE - AUTENTICAÇÃO")
    print("="*70)

    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            "oauth_config.json",
            scopes=SCOPES
        )

        print("\n[*] Abrindo navegador para autenticação...")
        print("[*] Por favor, faça login com sua conta Google")
        print("[*] Clique em 'Permitir' quando solicitado\n")

        # Usar servidor local com retry
        try:
            creds = flow.run_local_server(port=8080, open_browser=True)
        except:
            # Se porta 8080 falhar, tenta 8081
            try:
                creds = flow.run_local_server(port=8081, open_browser=True)
            except:
                # Se ambas falharem, usa out-of-band
                print("\n[!] Porta local não disponível, usando modo manual...\n")
                auth_url, _ = flow.authorization_url()
                print(f"[*] Acesse este link: {auth_url}\n")
                code = input("[?] Cole o CÓDIGO de autorização: ").strip()
                flow.fetch_token(code=code)
                creds = flow.credentials

        # Salvar token
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

        print("\n" + "="*70)
        print("[OK] AUTENTICAÇÃO CONCLUÍDA COM SUCESSO! ✓")
        print("[OK] Token salvo em: token.pickle")
        print("[OK] Pronto para rodar: python etapa3_google_drive.py")
        print("="*70 + "\n")

        # Limpar
        if os.path.exists("oauth_config.json"):
            os.remove("oauth_config.json")

        return True

    except Exception as e:
        print(f"\n[!] Erro: {e}")
        print(f"\n[!] Se o problema persistir:")
        print("[!] 1. Verifique se Client ID e Secret estão corretos")
        print("[!] 2. Vá para: https://myaccount.google.com/permissions")
        print("[!] 3. Remova 'AgroIA-RMC' e tente novamente\n")

        if os.path.exists("oauth_config.json"):
            os.remove("oauth_config.json")
        return False

if __name__ == "__main__":
    main()
