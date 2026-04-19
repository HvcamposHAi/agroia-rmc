"""
Teste: Verificar se Google Drive API está funcionando
"""

import os
import pickle
from dotenv import load_dotenv
from googleapiclient.discovery import build

load_dotenv()

print("\n" + "="*70)
print("TESTE GOOGLE DRIVE")
print("="*70)

# Carregar token
try:
    with open("token.pickle", "rb") as token:
        creds = pickle.load(token)
    print("[OK] Token carregado com sucesso")
except Exception as e:
    print(f"[!] Erro ao carregar token: {e}")
    exit(1)

# Conectar ao Google Drive
try:
    service = build('drive', 'v3', credentials=creds)
    print("[OK] Conectado ao Google Drive")
except Exception as e:
    print(f"[!] Erro ao conectar: {e}")
    exit(1)

# Obter folder_id
folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
print(f"\n[*] Folder ID: {folder_id}")

# Listar arquivos na pasta
try:
    results = service.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        spaces='drive',
        fields='files(id, name, size)',
        pageSize=10
    ).execute()

    files = results.get('files', [])
    print(f"\n[OK] Arquivos na pasta: {len(files)}")

    if files:
        print("\nArquivos encontrados:")
        for file in files:
            size_mb = int(file.get('size', 0)) / 1024 / 1024
            print(f"  - {file['name']} ({size_mb:.1f} MB)")
    else:
        print("[!] Nenhum arquivo encontrado na pasta!")

except Exception as e:
    print(f"[!] Erro ao listar arquivos: {e}")
    exit(1)

print("\n" + "="*70)
