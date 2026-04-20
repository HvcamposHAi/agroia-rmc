#!/usr/bin/env python3
"""
Reconcilia PDFs do Google Drive com Supabase usando Claude Vision.
Passo 1: Gera TXT com nome_arquivo | numero_processo
Passo 2: Atualiza Supabase a partir do TXT
"""

import os
import json
import pickle
import base64
import io
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from supabase import create_client
import anthropic
import fitz
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient import discovery

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
MAPEAMENTO_TXT = "drive_mapeamento_procesos.txt"

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

def extrair_processo_claude(pdf_stream: io.BytesIO, cliente: anthropic.Anthropic) -> str | None:
    """Extrai numero do processo usando Claude Vision (stream apenas)."""
    try:
        pdf_stream.seek(0)
        doc = fitz.open(stream=pdf_stream.read(), filetype="pdf")
        if len(doc) == 0:
            return None

        page = doc[0]
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        img_base64 = base64.standard_b64encode(img_bytes).decode("utf-8")
        doc.close()

        response = cliente.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": img_base64
                        }
                    },
                    {
                        "type": "text",
                        "text": """Qual e o numero do processo licitatorio?
Formatos: D.E. 4/2019, PE 001/2020, DS 77, DISPENSA 84, AD 3/2019
Responda APENAS o numero, nada mais. Se nao encontrar, responda: NAO_ENCONTRADO"""
                    }
                ]
            }]
        )

        resultado = response.content[0].text.strip()
        if resultado and resultado != "NAO_ENCONTRADO":
            return resultado
        return None
    except Exception as e:
        print(f"      Erro: {e}")
        return None

def passo1_gerar_mapeamento(service, cliente):
    """Passo 1: Gera arquivo TXT com mapeamento arquivo -> processo."""
    print("=== PASSO 1: Gerar Mapeamento (arquivo → processo) ===\n")

    print("1. Listando PDFs no Google Drive...")
    try:
        resultados = service.files().list(
            q=f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and mimeType='application/pdf'",
            spaces="drive",
            fields="files(id, name, webViewLink)",
            pageSize=1000
        ).execute()
        arquivos = resultados.get("files", [])
        print(f"   Encontrados {len(arquivos)} PDFs\n")
    except Exception as e:
        print(f"   [ERRO] {e}\n")
        return

    print("2. Carregando mapeamento existente...")
    mapeamento_existente = {}
    if Path(MAPEAMENTO_TXT).exists():
        with open(MAPEAMENTO_TXT, "r", encoding="utf-8") as f:
            for linha in f:
                if " | " in linha:
                    nome, proc = linha.strip().split(" | ", 1)
                    mapeamento_existente[nome] = proc
        print(f"   {len(mapeamento_existente)} entradas carregadas\n")
    else:
        print(f"   Arquivo {MAPEAMENTO_TXT} nao existe (criando novo)\n")

    print("3. Processando PDFs nao mapeados...\n")
    novos = 0
    ja_existentes = 0
    sem_processo = 0

    with open(MAPEAMENTO_TXT, "a", encoding="utf-8") as f:
        for idx, arquivo in enumerate(arquivos, 1):
            nome = arquivo["name"]
            file_id = arquivo["id"]

            if nome in mapeamento_existente:
                ja_existentes += 1
                continue

            print(f"   [{idx}/{len(arquivos)}] {nome}...", end="", flush=True)

            try:
                request = service.files().get_media(fileId=file_id)
                pdf_stream = io.BytesIO()
                from googleapiclient.http import MediaIoBaseDownload
                downloader = MediaIoBaseDownload(pdf_stream, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()

                numero = extrair_processo_claude(pdf_stream, cliente)
                if numero:
                    f.write(f"{nome} | {numero}\n")
                    f.flush()
                    print(f" [{numero}]")
                    novos += 1
                else:
                    print(f" [SEM PROCESSO]")
                    sem_processo += 1
            except Exception as e:
                print(f" [ERRO: {e}]")

    print(f"\n=== Resumo Passo 1 ===")
    print(f"Ja existentes: {ja_existentes}")
    print(f"Novos mapeados: {novos}")
    print(f"Sem processo identificavel: {sem_processo}")
    print(f"Arquivo gerado: {MAPEAMENTO_TXT}\n")

def passo2_atualizar_supabase():
    """Passo 2: Atualiza Supabase usando o arquivo TXT gerado."""
    print("=== PASSO 2: Atualizar Supabase ===\n")

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("1. Carregando mapeamento processo -> licitacao_id...")
    try:
        with open("processo_lic_mapping.json", "r", encoding="utf-8") as f:
            mapa_proc_lic = json.load(f)
        print(f"   {len(mapa_proc_lic)} mapeamentos carregados\n")
    except FileNotFoundError:
        print("   [ERRO] processo_lic_mapping.json nao encontrado\n")
        return

    print("2. Carregando registros ja existentes...")
    ja_existentes = set()
    try:
        existentes = sb.table("documentos_licitacao").select("url_publica").execute()
        if existentes.data:
            ja_existentes = set(d["url_publica"] for d in existentes.data if d["url_publica"])
        print(f"   {len(ja_existentes)} registros ja existem\n")
    except Exception as e:
        print(f"   Aviso: {e}\n")

    if not Path(MAPEAMENTO_TXT).exists():
        print(f"[ERRO] {MAPEAMENTO_TXT} nao encontrado. Execute Passo 1 primeiro.\n")
        return

    print("3. Lendo TXT e inserindo no Supabase...")
    inseridos = 0
    duplicados = 0
    sem_mapeamento = 0
    erros = []

    with open(MAPEAMENTO_TXT, "r", encoding="utf-8") as f:
        linhas = f.readlines()

    for idx, linha in enumerate(linhas, 1):
        if " | " not in linha:
            continue

        nome_arquivo, numero_processo = linha.strip().split(" | ", 1)
        licitacao_id = mapa_proc_lic.get(numero_processo)

        if not licitacao_id:
            sem_mapeamento += 1
            continue

        web_view_link = f"https://drive.google.com/file/d/ARQUIVO_ID/view"

        try:
            sb.table("documentos_licitacao").insert({
                "licitacao_id": licitacao_id,
                "nome_doc": nome_arquivo,
                "url_publica": web_view_link,
            }).execute()
            inseridos += 1
            if idx % 20 == 0:
                print(f"   [{idx}/{len(linhas)}] {inseridos} inseridos...")
        except Exception as e:
            erros.append({"arquivo": nome_arquivo, "processo": numero_processo, "erro": str(e)})

    print(f"\n=== Resumo Passo 2 ===")
    print(f"Linhas processadas: {len(linhas)}")
    print(f"Inseridos: {inseridos}")
    print(f"Sem mapeamento (processo nao existe): {sem_mapeamento}")
    if erros:
        print(f"Erros: {len(erros)}")
        for erro in erros[:3]:
            print(f"  - {erro['arquivo']}: {erro['erro']}")

def main():
    print("AgroIA PDF Reconciliacao - Passo 1 & 2\n")

    service = autenticar_google()
    cliente = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    passo1_gerar_mapeamento(service, cliente)
    passo2_atualizar_supabase()

    print(f"Concluido: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
