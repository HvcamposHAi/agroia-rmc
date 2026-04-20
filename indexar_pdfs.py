#!/usr/bin/env python3
"""
Script para indexar PDFs do Google Drive em pgvector no Supabase.
Gera embeddings de chunks de texto e salva com busca semântica.
"""

import io
import os
import json
import pickle
import base64
from pathlib import Path
from datetime import datetime
from typing import Iterator
from itertools import islice
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv
from supabase import create_client, Client
import anthropic
import fitz
from sentence_transformers import SentenceTransformer
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient import discovery

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

def autenticar_google():
    """Autentica com Google Drive usando token.pickle."""
    token_file = Path("token.pickle")
    creds = None

    if token_file.exists():
        with open(token_file, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(token_file, "wb") as f:
            pickle.dump(creds, f)

    return discovery.build("drive", "v3", credentials=creds)

def extrair_file_id(url_publica: str) -> str | None:
    """Extrai file ID de URL do Google Drive."""
    if "drive.google.com" not in url_publica:
        return None

    if "/d/" in url_publica:
        parts = url_publica.split("/d/")
        if len(parts) > 1:
            return parts[1].split("/")[0]

    parsed = urlparse(url_publica)
    if "id=" in parsed.query:
        params = parse_qs(parsed.query)
        ids = params.get("id", [])
        if ids:
            return ids[0]

    return None

def baixar_pdf_drive(service, file_id: str) -> bytes | None:
    """Baixa PDF do Google Drive."""
    try:
        request = service.files().get_media(fileId=file_id)
        pdf_bytes = io.BytesIO()
        from googleapiclient.http import MediaIoBaseDownload
        downloader = MediaIoBaseDownload(pdf_bytes, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        pdf_bytes.seek(0)
        return pdf_bytes.read()
    except Exception as e:
        print(f"Erro ao baixar {file_id}: {e}")
        return None

def extrair_texto_com_claude(pdf_bytes: bytes, client: anthropic.Anthropic) -> str:
    """Extrai texto de PDF usando Claude Vision com prompt contextualizado."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        textos = []

        for page_num in range(min(10, len(doc))):
            page = doc[page_num]
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            img_base64 = base64.standard_b64encode(img_bytes).decode("utf-8")

            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1000,
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
                            "text": """Analisa documentos de licitacoes publicas de alimentos da Regiao Metropolitana de Curitiba.

Extraia APENAS informacoes relevantes a:
- Culturas agricolas (frutas, horticulas, graos, proteina animal, laticeos)
- Itens licitados (descricao, quantidade, unidade, valor)
- Fornecedores e cooperativas
- Valores e precos
- Numero do processo licitatorio
- Canais: PNAE, PAA, Armazem da Familia, Banco de Alimentos, Mesa Solidaria

Ignore informacoes administrativas irrelevantes.
Se nao houver informacoes agricolas relevantes, responda: [SEM CONTEUDO AGRICOLA]

Extraia:"""
                        }
                    ]
                }]
            )

            texto = response.content[0].text.strip()
            if texto and "[SEM CONTEUDO AGRICOLA]" not in texto:
                textos.append(f"[Pagina {page_num + 1}]\n{texto}")

        return "\n\n".join(textos) if textos else ""
    except Exception as e:
        print(f"Erro na extracao com Claude: {e}")
        return ""

def fazer_chunks(texto: str, tamanho: int = 500, sobreposicao: int = 50) -> list[str]:
    """Cria chunks de ~500 palavras com sobreposição de 50 palavras."""
    palavras = texto.split()
    chunks = []

    for i in range(0, len(palavras), tamanho - sobreposicao):
        chunk_palavras = palavras[i : i + tamanho]
        if len(chunk_palavras) > 10:
            chunks.append(" ".join(chunk_palavras))

    return chunks

def batched(iterable, n):
    """Retorna lotes de n itens do iterável."""
    iterator = iter(iterable)
    while batch := list(islice(iterator, n)):
        yield batch

def indexar_pdfs():
    """Pipeline completo de indexação."""
    print("=== AgroIA PDF Indexing ===")
    print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("\n1. Carregando lista de documentos com URL pública...")
    docs_result = sb.table("documentos_licitacao").select(
        "id, licitacao_id, nome_doc, url_publica"
    ).neq("url_publica", None).limit(1000).execute()

    documentos = docs_result.data if docs_result.data else []
    print(f"   Encontrados {len(documentos)} documentos com URL")

    if len(documentos) == 0:
        print("   Nenhum documento encontrado!")
        return

    print("\n2. Carregando documentos já indexados...")
    ja_indexados = set()
    try:
        indexados_result = sb.table("pdf_chunks").select("documento_id").execute()
        ja_indexados = set(d["documento_id"] for d in indexados_result.data if indexados_result.data)
    except Exception as e:
        print(f"   Nota: tabela pdf_chunks pode não existir ainda: {e}")

    documentos_novos = [d for d in documentos if d["id"] not in ja_indexados]
    print(f"   {len(ja_indexados)} já indexados, {len(documentos_novos)} novos")

    if len(documentos_novos) == 0:
        print("   Nenhum documento novo para indexar!")
        return

    print("\n3. Inicializando Google Drive, Claude Vision e modelo de embeddings...")
    try:
        service = autenticar_google()
        print("   [OK] Google Drive autenticado")
    except Exception as e:
        print(f"   [ERRO] Erro na autenticacao Google: {e}")
        return

    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        print("   [OK] Claude Haiku Vision configurado")
    except Exception as e:
        print(f"   [ERRO] Erro ao configurar Claude: {e}")
        return

    modelo = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    print("   [OK] Modelo de embeddings carregado")

    erros_json = Path("indexacao_erros.json")
    erros = {}

    print(f"\n4. Processando {len(documentos_novos)} documentos...")
    chunks_totais = 0
    docs_sucesso = 0

    for idx, doc in enumerate(documentos_novos, 1):
        doc_id = doc["id"]
        licitacao_id = doc["licitacao_id"]
        nome_doc = doc["nome_doc"]
        url = doc["url_publica"]

        print(f"\n   [{idx}/{len(documentos_novos)}] {nome_doc} (ID: {doc_id})")

        try:
            lic_result = sb.table("licitacoes").select("processo").eq("id", licitacao_id).single().execute()
            processo = lic_result.data.get("processo", "?") if lic_result.data else "?"
        except Exception:
            processo = "?"

        file_id = extrair_file_id(url)
        if not file_id:
            print(f"      [ERRO] Nao consegui extrair file_id de: {url}")
            erros[str(doc_id)] = "file_id invalido"
            continue

        pdf_bytes = baixar_pdf_drive(service, file_id)
        if not pdf_bytes:
            print(f"      [ERRO] Erro ao baixar PDF")
            erros[str(doc_id)] = "erro no download"
            continue

        print(f"      Extraindo com Claude Vision...", end="", flush=True)
        texto = extrair_texto_com_claude(pdf_bytes, client)
        if not texto:
            print(f" [VAZIO]")
            erros[str(doc_id)] = "texto vazio"
            continue
        print(f" [OK]")

        chunks = fazer_chunks(texto)
        if not chunks:
            print(f"      [ERRO] Nenhum chunk gerado")
            erros[str(doc_id)] = "chunking falhou"
            continue

        print(f"      → {len(chunks)} chunks, {len(texto)} caracteres")

        print(f"      Gerando embeddings...", end="", flush=True)
        try:
            embeddings = modelo.encode(chunks, batch_size=32, show_progress_bar=False)
            print(" [OK]")
        except Exception as e:
            print(f" [ERRO] {e}")
            erros[str(doc_id)] = str(e)
            continue

        registros = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            registros.append({
                "licitacao_id": licitacao_id,
                "documento_id": doc_id,
                "processo": processo,
                "nome_doc": nome_doc,
                "chunk_index": i,
                "chunk_text": chunk,
                "embedding": embedding.tolist(),
                "tokens_aprox": len(chunk) // 4,
            })

        print(f"      Salvando no Supabase...", end="", flush=True)
        try:
            for lote in batched(registros, 50):
                sb.table("pdf_chunks").upsert(
                    lote,
                    on_conflict="documento_id,chunk_index"
                ).execute()
            print(f" [OK]")
            chunks_totais += len(chunks)
            docs_sucesso += 1
        except Exception as e:
            print(f" [ERRO] {e}")
            erros[str(doc_id)] = f"upsert falhou: {str(e)}"

    print(f"\n=== Resumo ===")
    print(f"Documentos processados: {docs_sucesso}/{len(documentos_novos)}")
    print(f"Chunks gerados: {chunks_totais}")
    print(f"Sucesso taxa: {100 * docs_sucesso / len(documentos_novos):.1f}%")

    if erros:
        print(f"\nErros encontrados ({len(erros)}):")
        with open(erros_json, "w", encoding="utf-8") as f:
            json.dump(erros, f, ensure_ascii=False, indent=2)
        print(f"Detalhes salvos em {erros_json}")

    print(f"\nFim: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    indexar_pdfs()
