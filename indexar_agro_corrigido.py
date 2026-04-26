#!/usr/bin/env python3
"""
Indexacao OTIMIZADA: Apenas 24 documentos agricolas.
Usa vw_licitacoes_agro_documentos que já tem os docs validados.
Tempo estimado: 30 minutos.
"""

import os
import json
import pickle
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
                        {"type": "text", "text": """Analisa documento de licitacao publica de alimentos (RMC - Curitiba).
Extraia APENAS conteudo relevante:
- Culturas agricolas (frutas, horticulas, graos, proteina animal, laticeos)
- Itens licitados (descricao, quantidade, unidade, valor)
- Fornecedores e cooperativas
- Valores e precos
- Numero do processo licitatorio
- Canais: PNAE, PAA, Armazem da Familia, Banco de Alimentos

Ignore informacoes administrativas.
Se nao houver conteudo agricola, responda: [SEM CONTEUDO AGRICOLA]
Extraia:"""}
                    ]
                }]
            )
            texto = response.content[0].text.strip()
            if texto and "[SEM CONTEUDO AGRICOLA]" not in texto:
                textos.append(f"[Pagina {page_num + 1}]\n{texto}")
        return "\n\n".join(textos) if textos else ""
    except Exception as e:
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

print("=== INDEXACAO AGRICOLA APENAS (24 DOCUMENTOS) ===\n")
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

print("1. Carregando documentos agricolas validados...")
try:
    agro_docs = sb.table("vw_licitacoes_agro_documentos").select("id, licitacao_id, nome_arquivo, processo").execute()
    documentos = agro_docs.data if agro_docs.data else []
    print(f"   Encontrados: {len(documentos)} documentos agricolas\n")
except Exception as e:
    print(f"   Erro ao carregar: {e}\n")
    documentos = []

if not documentos:
    print("Nenhum documento agrícola encontrado!")
    exit(1)

print("2. Carregando URLs publicas dos documentos...")
doc_ids = [d["id"] for d in documentos]
try:
    urls_result = sb.table("documentos_licitacao").select("id, url_publica").in_("id", doc_ids).execute()
    urls_map = {d["id"]: d.get("url_publica") for d in urls_result.data}
    print(f"   {len(urls_map)} URLs carregadas\n")
except Exception as e:
    print(f"   Erro: {e}\n")
    urls_map = {}

print("3. Limpando chunks antigos desses documentos...")
try:
    for doc_id in doc_ids:
        sb.table("pdf_chunks").delete().eq("documento_id", doc_id).execute()
    print(f"   Deletados chunks antigos\n")
except Exception as e:
    print(f"   Aviso: {e}\n")

print("4. Inicializando servicos...")
try:
    service = autenticar_google()
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    modelo = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    print("   [OK]\n")
except Exception as e:
    print(f"   Erro de autenticacao: {e}\n")
    exit(1)

print(f"5. Processando {len(documentos)} documentos agricolas...\n")
chunks_totais = 0
docs_sucesso = 0
erros = {}

for idx, doc in enumerate(documentos, 1):
    doc_id = doc["id"]
    licitacao_id = doc["licitacao_id"]
    nome_doc = doc["nome_arquivo"]
    processo = doc.get("processo", "?")
    url = urls_map.get(doc_id)

    print(f"   [{idx:2}/{len(documentos)}] {nome_doc[:40]:40}", end=" | ", flush=True)

    if not url:
        erros[str(doc_id)] = "sem_url"
        print("[ERRO: sem URL]")
        continue

    file_id = extrair_arquivo_id(url)
    if not file_id:
        erros[str(doc_id)] = "file_id"
        print("[ERRO: file_id]")
        continue

    pdf_bytes = baixar_pdf_drive(service, file_id)
    if not pdf_bytes:
        erros[str(doc_id)] = "download"
        print("[ERRO: download]")
        continue

    texto = extrair_texto_com_claude(pdf_bytes, client)
    if not texto:
        erros[str(doc_id)] = "vazio"
        print("[VAZIO]")
        continue

    chunks = fazer_chunks(texto)
    if not chunks:
        erros[str(doc_id)] = "chunks"
        print("[ERRO: chunks]")
        continue

    try:
        embeddings = modelo.encode(chunks, batch_size=32, show_progress_bar=False)
    except Exception as e:
        erros[str(doc_id)] = f"embeddings: {str(e)[:20]}"
        print("[ERRO: embeddings]")
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
        print(f"[OK {len(chunks):2} chunks]")
    except Exception as e:
        erros[str(doc_id)] = f"insert: {str(e)[:20]}"
        print(f"[ERRO: insert]")

print(f"\n=== RESUMO FINAL ===")
print(f"Documentos processados: {docs_sucesso}/{len(documentos)} ({100*docs_sucesso/len(documentos):.1f}%)")
print(f"Chunks gerados: {chunks_totais}")

if erros:
    print(f"Erros: {len(erros)}")
    print("\nDetalhes dos erros:")
    for doc_id, erro in list(erros.items())[:5]:
        print(f"  - Doc {doc_id}: {erro}")
    if len(erros) > 5:
        print(f"  ... e mais {len(erros) - 5} erros")
    with open("indexacao_erros.json", "w", encoding="utf-8") as f:
        json.dump(erros, f, ensure_ascii=False, indent=2)

print(f"\n✅ Indexacao concluida: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"\n🎯 Proximos passos:")
print(f"   1. Verificar chunks gerados: python dados_atualizados.py --resumo")
print(f"   2. Testar busca semantica (RAG)")
