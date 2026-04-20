#!/usr/bin/env python3
"""
Reconciliacao V2 Melhorada: Processa TODOS os 189 PDFs com processo no nome.
Usa UPSERT para evitar duplicatas e melhora extração de processo.
"""

import os
import json
import pickle
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from supabase import create_client
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient import discovery

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

def autenticar_google():
    """Autentica com Google Drive."""
    token_file = Path("token.pickle")
    creds = None

    if token_file.exists():
        with open(token_file, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_file, "wb") as f:
            pickle.dump(creds, f)

    return discovery.build("drive", "v3", credentials=creds)

def extrair_processo_do_nome(nome_arquivo: str) -> Optional[tuple[str, str]]:
    """Extrai tipo e número do processo do nome do arquivo com múltiplos padrões."""
    nome_upper = nome_arquivo.upper()

    patterns = [
        (r'D\.?E\.?[\s_]+(\d+)', 'DE'),
        (r'\bDS[\s_]+(\d+)', 'DS'),
        (r'\bPE[\s_]+(\d+)', 'PE'),
        (r'\bDT[\s_]+(\d+)', 'DT'),
        (r'\bIN[\s_]+(\d+)', 'IN'),
        (r'DISPENSA[\s_]+(\d+)', 'DS'),
    ]

    for pattern, tipo in patterns:
        match = re.search(pattern, nome_upper)
        if match:
            numero = match.group(1)
            return (tipo, numero)

    return None

def tentar_mapear_processo(tipo: str, numero: str, mapa: dict) -> Optional[int]:
    """Tenta mapear (tipo, numero) em processo_lic_mapping.json."""
    for ano in [2024, 2023, 2022, 2021, 2020, 2019]:
        chave = f"{tipo} {numero}/{ano} - SMSAN/FAAC"
        if chave in mapa:
            return mapa[chave]
    return None

def main():
    print("=== Reconciliacao V2 Melhorada ===\n")

    # 1. Carregar mapeamento
    print("1. Carregando processo_lic_mapping.json...")
    with open("processo_lic_mapping.json", "r", encoding="utf-8") as f:
        mapa_proc_lic = json.load(f)
    print(f"   {len(mapa_proc_lic)} processos carregados\n")

    # 2. Autenticar
    print("2. Autenticando Google Drive...")
    service = autenticar_google()
    print("   [OK]\n")

    # 3. Listar PDFs do Drive
    print("3. Listando PDFs do Google Drive...")
    resultados = service.files().list(
        q=f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and mimeType='application/pdf'",
        spaces="drive",
        fields="files(id, name, webViewLink)",
        pageSize=1000
    ).execute()
    arquivos = resultados.get("files", [])
    print(f"   Encontrados {len(arquivos)} PDFs\n")

    # 4. Conectar Supabase
    print("4. Conectando Supabase...")
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    ja_existentes = set()
    try:
        existentes = sb.table("documentos_licitacao").select("url_publica").execute()
        if existentes.data:
            ja_existentes = set(d["url_publica"] for d in existentes.data if d["url_publica"])
        print(f"   {len(ja_existentes)} registros já existem\n")
    except Exception as e:
        print(f"   Aviso: {e}\n")

    # 5. Filtrar arquivos com processo no nome
    print("5. Filtrando arquivos com processo no nome...")
    arquivos_com_processo = []
    for a in arquivos:
        if extrair_processo_do_nome(a["name"]) is not None:
            if a["webViewLink"] not in ja_existentes:
                arquivos_com_processo.append(a)

    print(f"   {len(arquivos_com_processo)} novos arquivos com processo\n")

    if not arquivos_com_processo:
        print("   Nenhum arquivo novo para processar.\n")
        return

    # 6. Processar
    print(f"6. Processando {len(arquivos_com_processo)} arquivos...\n")
    mapeados = 0
    nao_mapeados = 0
    erros = []

    for idx, arquivo in enumerate(arquivos_com_processo, 1):
        nome = arquivo["name"]
        url = arquivo["webViewLink"]

        resultado = extrair_processo_do_nome(nome)
        if not resultado:
            nao_mapeados += 1
            continue

        tipo, numero = resultado
        licitacao_id = tentar_mapear_processo(tipo, numero, mapa_proc_lic)

        if not licitacao_id:
            nao_mapeados += 1
            if idx <= 20:
                print(f"   [{idx}/{len(arquivos_com_processo)}] {nome[:40]} - {tipo} {numero} [NAO ENCONTRADO]")
            continue

        # Inserir ou atualizar no Supabase
        try:
            sb.table("documentos_licitacao").upsert({
                "licitacao_id": licitacao_id,
                "nome_arquivo": nome,
                "nome_doc": nome,
                "url_publica": url,
            }, on_conflict="licitacao_id,nome_arquivo").execute()

            mapeados += 1
            if idx % 50 == 0 or idx <= 20:
                print(f"   [{idx}/{len(arquivos_com_processo)}] {tipo} {numero} [OK]")
        except Exception as e:
            erro_msg = str(e)
            erros.append({"arquivo": nome, "tipo_num": f"{tipo} {numero}", "erro": erro_msg[:100]})

    print(f"\n=== Resumo V2 Melhorada ===")
    print(f"Total arquivos processados: {len(arquivos_com_processo)}")
    print(f"Inseridos/atualizados: {mapeados}")
    print(f"Nao mapeados: {nao_mapeados}")
    if erros:
        print(f"Erros: {len(erros)}")
        for erro in erros[:5]:
            print(f"  - {erro['arquivo'][:40]}: {erro['erro']}")

    print(f"\nConcluido: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
