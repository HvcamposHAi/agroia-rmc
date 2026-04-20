#!/usr/bin/env python3
"""
Reconcilia PDFs do Google Drive com Supabase - Versão 2.
Extrai processo do NOME do arquivo e mapeia com ANOS para encontrar em processo_lic_mapping.json
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
    """
    Extrai tipo e número do processo do nome do arquivo.

    Exemplos:
    - "DS_97.pdf" → ("DS", "97")
    - "PE_7.pdf" → ("PE", "7")
    - "D.E._5.pdf" → ("DE", "5")
    - "DISPENSA_104.pdf" → ("DS", "104")
    - "DS_100_-_PARTE_2.pdf" → ("DS", "100")

    Retorna (tipo, numero) ou None se não conseguir extrair.
    """
    nome = nome_arquivo.replace('.pdf', '').replace('.', '_').upper()

    # Padrões a tentar
    patterns = [
        r'D\.?E\.?[_\s]+(\d+)',  # D.E. XX ou DE XX
        r'DS[_\s]+(\d+)',         # DS XX
        r'PE[_\s]+(\d+)',         # PE XX
        r'DT[_\s]+(\d+)',         # DT XX
        r'IN[_\s]+(\d+)',         # IN XX
        r'DISPENSA[_\s]+(\d+)',   # DISPENSA XX → DS
    ]

    # Determinar tipo
    tipo = None
    numero = None

    if re.search(r'D\.?E\.?', nome_arquivo, re.IGNORECASE):
        tipo = "DE"
        match = re.search(r'D\.?E\.?[_\s]+(\d+)', nome_arquivo, re.IGNORECASE)
        if match:
            numero = match.group(1)
    elif 'DISPENSA' in nome:
        tipo = "DS"
        match = re.search(r'DISPENSA[_\s]+(\d+)', nome)
        if match:
            numero = match.group(1)
    elif 'DS' in nome:
        tipo = "DS"
        match = re.search(r'DS[_\s]+(\d+)', nome)
        if match:
            numero = match.group(1)
    elif 'PE' in nome:
        tipo = "PE"
        match = re.search(r'PE[_\s]+(\d+)', nome)
        if match:
            numero = match.group(1)
    elif 'DT' in nome:
        tipo = "DT"
        match = re.search(r'DT[_\s]+(\d+)', nome)
        if match:
            numero = match.group(1)
    elif 'IN' in nome:
        tipo = "IN"
        match = re.search(r'IN[_\s]+(\d+)', nome)
        if match:
            numero = match.group(1)

    if tipo and numero:
        return (tipo, numero)

    return None

def tentar_mapear_processo(tipo: str, numero: str, mapa: dict) -> Optional[int]:
    """
    Tenta mapear (tipo, numero) em processo_lic_mapping.json.

    Tenta anos em ordem decrescente (2024, 2023, 2022, 2021, 2020, 2019).
    Retorna licitacao_id ou None se não encontrar.
    """
    for ano in [2024, 2023, 2022, 2021, 2020, 2019]:
        chave = f"{tipo} {numero}/{ano} - SMSAN/FAAC"
        if chave in mapa:
            return mapa[chave]

    return None

def main():
    print("=== Reconciliacao Drive - Supabase V2 ===\n")

    # 1. Carregar mapeamento
    print("1. Carregando processo_lic_mapping.json...")
    with open("processo_lic_mapping.json", "r", encoding="utf-8") as f:
        mapa_proc_lic = json.load(f)
    print(f"   {len(mapa_proc_lic)} processos carregados\n")

    # 2. Autenticar Google Drive
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

    # Carregar documentos já existentes
    ja_existentes = set()
    try:
        existentes = sb.table("documentos_licitacao").select("url_publica").execute()
        if existentes.data:
            ja_existentes = set(d["url_publica"] for d in existentes.data if d["url_publica"])
        print(f"   {len(ja_existentes)} registros já existem\n")
    except Exception as e:
        print(f"   Aviso: {e}\n")

    # 5. Processar arquivos
    print(f"5. Processando {len(arquivos)} arquivos...\n")
    mapeados = 0
    nao_mapeados = 0
    duplicados = 0
    erros = []

    for idx, arquivo in enumerate(arquivos, 1):
        nome = arquivo["name"]
        url = arquivo["webViewLink"]

        # Pular duplicados
        if url in ja_existentes:
            duplicados += 1
            continue

        # Extrair processo do nome
        resultado = extrair_processo_do_nome(nome)
        if not resultado:
            nao_mapeados += 1
            if idx <= 20:  # Log primeiros 20 não mapeados
                print(f"   [{idx}/{len(arquivos)}] {nome} - [SEM PROCESSO NO NOME]")
            continue

        tipo, numero = resultado
        licitacao_id = tentar_mapear_processo(tipo, numero, mapa_proc_lic)

        if not licitacao_id:
            nao_mapeados += 1
            if idx <= 20:
                print(f"   [{idx}/{len(arquivos)}] {nome} - {tipo} {numero} [NÃO ENCONTRADO]")
            continue

        # Inserir no Supabase
        try:
            sb.table("documentos_licitacao").insert({
                "licitacao_id": licitacao_id,
                "nome_arquivo": nome,
                "nome_doc": nome,
                "url_publica": url,
            }).execute()
            mapeados += 1
            if idx % 50 == 0:
                print(f"   [{idx}/{len(arquivos)}] {mapeados} inseridos...")
        except Exception as e:
            erros.append({"arquivo": nome, "tipo_num": f"{tipo} {numero}", "erro": str(e)})

    print(f"\n=== Resumo ===")
    print(f"Total arquivos no Drive: {len(arquivos)}")
    print(f"Duplicados (já existem): {duplicados}")
    print(f"Mapeados e inseridos: {mapeados}")
    print(f"Não mapeados: {nao_mapeados}")
    if erros:
        print(f"Erros: {len(erros)}")
        for erro in erros[:5]:
            print(f"  - {erro['arquivo']}: {erro['erro']}")

    print(f"\nConcluído: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
