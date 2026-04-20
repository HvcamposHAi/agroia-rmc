#!/usr/bin/env python3
"""
Reconciliacao V3: Trata arquivos com nomes genéricos usando Claude Vision.
Extrai número do processo da primeira página do PDF via Claude Vision.
"""

import os
import json
import pickle
import io
import base64
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

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
PROCESSO_MAPPING_FILE = "reconciliar_v3_procesos.json"

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

def baixar_pdf_stream(service, file_id: str) -> Optional[io.BytesIO]:
    """Baixa PDF como stream de memória."""
    try:
        request = service.files().get_media(fileId=file_id)
        pdf_bytes = io.BytesIO()
        from googleapiclient.http import MediaIoBaseDownload
        downloader = MediaIoBaseDownload(pdf_bytes, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        pdf_bytes.seek(0)
        return pdf_bytes
    except Exception as e:
        print(f"      [ERRO download] {e}")
        return None

def extrair_processo_claude(pdf_stream: io.BytesIO, cliente: anthropic.Anthropic) -> Optional[tuple[str, str]]:
    """
    Extrai tipo e numero do processo usando Claude Vision.
    Retorna (tipo, numero) ou None.
    """
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
                        "text": """Qual e o tipo e numero do processo licitatorio?
Formatos esperados: DS 70, PE 7, D.E. 8, DT 1, IN 1, DISPENSA 84
Responda APENAS em formato: TIPO NUMERO (ex: DS 70, PE 7)
Se nao encontrar, responda: NAO_ENCONTRADO"""
                    }
                ]
            }]
        )

        resultado = response.content[0].text.strip()
        if resultado and resultado != "NAO_ENCONTRADO":
            # Extrair tipo e numero do resultado
            match = re.match(r'([A-Z]+\.?E?\.?)\s+(\d+)', resultado)
            if match:
                tipo = match.group(1).replace('.', '').replace('E', '')
                if tipo == 'D':
                    tipo = 'DE'
                numero = match.group(2)
                return (tipo, numero)
        return None
    except Exception as e:
        print(f"      [ERRO Claude] {e}")
        return None

def tentar_mapear_processo(tipo: str, numero: str, mapa: dict) -> Optional[int]:
    """Tenta mapear (tipo, numero) em processo_lic_mapping.json."""
    for ano in [2024, 2023, 2022, 2021, 2020, 2019]:
        chave = f"{tipo} {numero}/{ano} - SMSAN/FAAC"
        if chave in mapa:
            return mapa[chave]
    return None

def main():
    print("=== Reconciliacao V3: Claude Vision para nomes genéricos ===\n")

    # 1. Carregar mapeamento
    print("1. Carregando processo_lic_mapping.json...")
    with open("processo_lic_mapping.json", "r", encoding="utf-8") as f:
        mapa_proc_lic = json.load(f)
    print(f"   {len(mapa_proc_lic)} processos carregados\n")

    # 2. Autenticar
    print("2. Autenticando Google Drive e Claude...")
    service = autenticar_google()
    cliente = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
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

    # 5. Filtrar apenas arquivos com nomes genéricos (contem "PROCESSO")
    print("5. Filtrando arquivos com nomes genéricos...")
    arquivos_genericos = [a for a in arquivos if "PROCESSO" in a["name"].upper() and a["webViewLink"] not in ja_existentes]
    print(f"   {len(arquivos_genericos)} arquivos genéricos para processar\n")

    if not arquivos_genericos:
        print("   Nenhum arquivo genérico para processar.\n")
        return

    # 6. Processar com Claude Vision
    print(f"6. Processando {len(arquivos_genericos)} arquivos com Claude Vision...\n")

    mapeados = 0
    claude_sucesso = 0
    nao_encontrados = 0
    erros = []

    for idx, arquivo in enumerate(arquivos_genericos, 1):
        nome = arquivo["name"]
        file_id = arquivo["id"]
        url = arquivo["webViewLink"]

        print(f"   [{idx}/{len(arquivos_genericos)}] {nome[:50]}...", end="", flush=True)

        # Baixar PDF
        pdf_stream = baixar_pdf_stream(service, file_id)
        if not pdf_stream:
            print(" [ERRO download]")
            nao_encontrados += 1
            continue

        # Extrair com Claude Vision
        resultado = extrair_processo_claude(pdf_stream, cliente)
        if not resultado:
            print(" [SEM PROCESSO]")
            nao_encontrados += 1
            continue

        tipo, numero = resultado
        licitacao_id = tentar_mapear_processo(tipo, numero, mapa_proc_lic)

        if not licitacao_id:
            print(f" [{tipo} {numero} NAO ENCONTRADO]")
            nao_encontrados += 1
            continue

        # Inserir no Supabase
        try:
            sb.table("documentos_licitacao").insert({
                "licitacao_id": licitacao_id,
                "nome_arquivo": nome,
                "nome_doc": nome,
                "url_publica": url,
            }).execute()
            print(f" [{tipo} {numero}]")
            mapeados += 1
            claude_sucesso += 1
        except Exception as e:
            erro_msg = str(e)
            if "duplicate key" in erro_msg.lower():
                print(f" [JA EXISTE]")
            else:
                print(f" [ERRO INSERT]")
                erros.append({"arquivo": nome, "erro": erro_msg})

    print(f"\n=== Resumo V3 ===")
    print(f"Total arquivos genéricos: {len(arquivos_genericos)}")
    print(f"Claude conseguiu extrair: {claude_sucesso}")
    print(f"Mapeados e inseridos: {mapeados}")
    print(f"Não encontrados/sem processo: {nao_encontrados}")
    if erros:
        print(f"Erros: {len(erros)}")
        for erro in erros[:3]:
            print(f"  - {erro['arquivo']}: {erro['erro'][:60]}...")

    print(f"\nConcluido: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
