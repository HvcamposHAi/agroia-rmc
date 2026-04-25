#!/usr/bin/env python3
"""
Reindexacao completa: Processa TODOS os 180 documentos.
Deleta chunks antigos e regenera do zero.
"""

import os
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client
import anthropic
from sentence_transformers import SentenceTransformer
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient import discovery
import io
import base64
import fitz
from itertools import islice

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

def autenticar_google():
    import pickle
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

def baixar_pdf_drive(service, file_id: str) -> bytes | None:
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
    except:
        return None

def extrair_arquivo_id(url):
    if "/d/" in url:
        return url.split("/d/")[1].split("/")[0]
    return None

def extrair_texto_com_claude(pdf_bytes: bytes, client: anthropic.Anthropic) -> str:
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
                        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_base64}},
                        {"type": "text", "text": """Analisa documentos de licitacoes publicas de alimentos da Regiao Metropolitana de Curitiba.
Extraia APENAS informacoes relevantes a:
- Culturas agricolas (frutas, horticulas, graos, proteina animal, laticeos)
- Itens licitados (descricao, quantidade, unidade, valor)
- Fornecedores e cooperativas
- Valores e precos
- Numero do processo licitatorio
- Canais: PNAE, PAA, Armazem da Familia, Banco de Alimentos, Mesa Solidaria

Ignore informacoes administrativas irrelevantes.
Se nao houver informacoes agricolas relevantes, responda: [SEM CONTEUDO AGRICOLA]

Extraia:"""}
                    ]
                }]
            )
            texto = response.content[0].text.strip()
            if texto and "[SEM CONTEUDO AGRICOLA]" not in texto:
                textos.append(f"[Pagina {page_num + 1}]\n{texto}")
        return "\n\n".join(textos) if textos else ""
    except:
        return ""

def fazer_chunks(texto: str, tamanho: int = 500, sobreposicao: int = 50) -> list[str]:
    palavras = texto.split()
    chunks = []
    for i in range(0, len(palavras), tamanho - sobreposicao):
        chunk_palavras = palavras[i : i + tamanho]
        if len(chunk_palavras) > 10:
            chunks.append(" ".join(chunk_palavras))
    return chunks

def batched(iterable, n):
    iterator = iter(iterable)
    while batch := list(islice(iterator, n)):
        yield batch

print("=== REINDEXACAO COMPLETA (180+ DOCUMENTOS) ===\n")
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

print("1. Limpando chunks antigos...")
try:
    sb.table("pdf_chunks").delete().neq("id", 0).execute()
    print("   [OK] Chunks deletados\n")
except Exception as e:
    print(f"   [AVISO] {e}\n")

print("2. Carregando documentos com URL...")
docs_result = sb.table("documentos_licitacao").select("id, licitacao_id, nome_doc, url_publica").neq("url_publica", None).execute()
documentos = docs_result.data if docs_result.data else []
print(f"   Encontrados: {len(documentos)} documentos\n")

print("3. Inicializando servicos...")
service = autenticar_google()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
modelo = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
print("   [OK]\n")

print(f"4. Processando {len(documentos)} documentos...\n")
chunks_totais = 0
docs_sucesso = 0
erros = {}

for idx, doc in enumerate(documentos, 1):
    doc_id = doc["id"]
    licitacao_id = doc["licitacao_id"]
    nome_doc = doc["nome_doc"]
    url = doc["url_publica"]

    if idx % 30 == 0 or idx <= 10:
        print(f"   [{idx:3}/{len(documentos)}] {nome_doc[:35]:35}", end=" | ", flush=True)

    try:
        lic_result = sb.table("licitacoes").select("processo").eq("id", licitacao_id).single().execute()
        processo = lic_result.data.get("processo", "?") if lic_result.data else "?"
    except:
        processo = "?"

    file_id = extrair_arquivo_id(url)
    if not file_id:
        erros[str(doc_id)] = "file_id"
        if idx % 30 == 0 or idx <= 10:
            print("[ERRO file_id]")
        continue

    pdf_bytes = baixar_pdf_drive(service, file_id)
    if not pdf_bytes:
        erros[str(doc_id)] = "download"
        if idx % 30 == 0 or idx <= 10:
            print("[ERRO download]")
        continue

    texto = extrair_texto_com_claude(pdf_bytes, client)
    if not texto:
        erros[str(doc_id)] = "vazio"
        if idx % 30 == 0 or idx <= 10:
            print("[VAZIO]")
        continue

    chunks = fazer_chunks(texto)
    if not chunks:
        erros[str(doc_id)] = "chunks"
        if idx % 30 == 0 or idx <= 10:
            print("[ERRO chunks]")
        continue

    try:
        embeddings = modelo.encode(chunks, batch_size=32, show_progress_bar=False)
    except Exception as e:
        erros[str(doc_id)] = "embeddings"
        if idx % 30 == 0 or idx <= 10:
            print("[ERRO emb]")
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

    try:
        for lote in batched(registros, 50):
            sb.table("pdf_chunks").insert(lote).execute()
        chunks_totais += len(chunks)
        docs_sucesso += 1
        if idx % 30 == 0 or idx <= 10:
            print(f"[OK {len(chunks):2} chunks]")
    except Exception as e:
        erros[str(doc_id)] = "insert"
        if idx % 30 == 0 or idx <= 10:
            print("[ERRO insert]")

print(f"\n=== RESUMO FINAL ===")
print(f"Documentos processados: {docs_sucesso}/{len(documentos)} ({100*docs_sucesso/len(documentos):.1f}%)")
print(f"Chunks gerados: {chunks_totais}")
print(f"Taxa sucesso: {100*docs_sucesso/len(documentos):.1f}%")

if erros:
    print(f"Erros: {len(erros)}")
    with open("indexacao_erros.json", "w", encoding="utf-8") as f:
        json.dump(erros, f, ensure_ascii=False, indent=2)

print(f"\nFim: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
