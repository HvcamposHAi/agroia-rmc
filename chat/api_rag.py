"""
API de RAG para AgroIA.
Endpoint para busca semântica em documentos agrícolas.
"""

import os
import json
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from supabase import create_client
from sentence_transformers import SentenceTransformer
from typing import Optional

load_dotenv()

app = FastAPI(title="AgroIA RAG API", version="1.0")

# Inicializar cliente Supabase e modelo
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
sb = create_client(SUPABASE_URL, SUPABASE_KEY)
modelo = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

# Modelos de requisição/resposta
class BuscaRAGRequest(BaseModel):
    query: str
    top_k: int = 5
    min_similarity: float = 0.3

class ChunkResultado(BaseModel):
    id: int
    documento_id: int
    nome_doc: str
    processo: str
    chunk_text: str
    similaridade: float
    chunk_index: int

class BuscaRAGResponse(BaseModel):
    query: str
    total_resultados: int
    chunks: list[ChunkResultado]
    tempo_processamento_ms: float

@app.get("/health")
async def health():
    """Health check"""
    return {"status": "ok", "sistema": "AgroIA RAG"}

@app.post("/rag/buscar", response_model=BuscaRAGResponse)
async def buscar_rag(request: BuscaRAGRequest):
    """
    Busca semântica em documentos agrícolas via RAG.

    ### Parâmetros:
    - **query**: Texto para buscar (ex: "Leite para merenda escolar")
    - **top_k**: Número de resultados (default 5)
    - **min_similarity**: Mínimo de similaridade (0-1, default 0.3)

    ### Resposta:
    Lista de chunks ordenados por similaridade semântica
    """

    import time
    start = time.time()

    try:
        # Validar entrada
        if not request.query or len(request.query.strip()) < 3:
            raise HTTPException(
                status_code=400,
                detail="Query deve ter pelo menos 3 caracteres"
            )

        if request.top_k < 1 or request.top_k > 50:
            raise HTTPException(
                status_code=400,
                detail="top_k deve estar entre 1 e 50"
            )

        # Gerar embedding da query
        query_embedding = modelo.encode(request.query, convert_to_numpy=True)
        query_embedding = query_embedding.astype(np.float32)

        # Carregar chunks do banco (limitar para performance)
        result = sb.table("pdf_chunks").select(
            "id, documento_id, nome_doc, processo, chunk_text, embedding, chunk_index"
        ).limit(500).execute()

        if not result.data:
            return BuscaRAGResponse(
                query=request.query,
                total_resultados=0,
                chunks=[],
                tempo_processamento_ms=round((time.time() - start) * 1000, 2)
            )

        # Calcular similaridade para cada chunk
        similaridades = []
        for chunk in result.data:
            if not chunk.get("embedding"):
                continue

            try:
                # Converter embedding (pode estar como string ou lista)
                emb = chunk["embedding"]
                if isinstance(emb, str):
                    emb = json.loads(emb)

                chunk_emb = np.array(emb, dtype=np.float32)

                # Similaridade coseno
                norm_query = np.linalg.norm(query_embedding)
                norm_chunk = np.linalg.norm(chunk_emb)

                if norm_query > 0 and norm_chunk > 0:
                    sim = np.dot(query_embedding, chunk_emb) / (norm_query * norm_chunk)

                    if sim >= request.min_similarity:
                        similaridades.append({
                            "id": chunk["id"],
                            "documento_id": chunk["documento_id"],
                            "nome_doc": chunk["nome_doc"],
                            "processo": chunk["processo"],
                            "chunk_text": chunk["chunk_text"],
                            "chunk_index": chunk["chunk_index"],
                            "similaridade": float(sim)
                        })
            except Exception:
                continue  # Skip problematic chunks

        # Ordenar por similaridade e pegar top_k
        similaridades.sort(key=lambda x: x["similaridade"], reverse=True)
        top_chunks = similaridades[:request.top_k]

        # Montar resposta
        chunks_response = [
            ChunkResultado(
                id=c["id"],
                documento_id=c["documento_id"],
                nome_doc=c["nome_doc"],
                processo=c["processo"],
                chunk_text=c["chunk_text"],
                similaridade=c["similaridade"],
                chunk_index=c["chunk_index"]
            )
            for c in top_chunks
        ]

        tempo_ms = round((time.time() - start) * 1000, 2)

        return BuscaRAGResponse(
            query=request.query,
            total_resultados=len(top_chunks),
            chunks=chunks_response,
            tempo_processamento_ms=tempo_ms
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro na busca: {str(e)}"
        )

@app.get("/rag/stats")
async def stats_rag():
    """Estatísticas do sistema RAG"""
    try:
        # Total de chunks
        result_chunks = sb.table("pdf_chunks").select("count", count="exact").execute()
        total_chunks = result_chunks.count

        # Chunks com embedding
        result_emb = sb.table("pdf_chunks").select("count", count="exact").not_.is_("embedding", "null").execute()
        chunks_com_emb = result_emb.count

        # Documentos únicos
        result_docs = sb.table("pdf_chunks").select("documento_id").execute()
        docs_unicos = len(set(r["documento_id"] for r in result_docs.data if r.get("documento_id")))

        return {
            "total_chunks": total_chunks,
            "chunks_com_embeddings": chunks_com_emb,
            "documentos_unicos": docs_unicos,
            "cobertura_embeddings": round(chunks_com_emb / total_chunks * 100, 1) if total_chunks > 0 else 0,
            "modelo": "paraphrase-multilingual-MiniLM-L12-v2",
            "dimensao_embedding": 384,
            "status": "operacional"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
