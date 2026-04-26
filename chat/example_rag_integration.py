"""
Exemplo: Integrar RAG com Chat para respostas contextualizadas.
Mostra como usar chunks de PDF para dar contexto a uma resposta de LLM.
"""

import os
import json
from dotenv import load_dotenv
from supabase import create_client
from sentence_transformers import SentenceTransformer
import anthropic
import numpy as np

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def buscar_contexto_rag(query: str, top_k: int = 5) -> list[str]:
    """
    Busca contexto relevante via RAG para usar em respostas de LLM.
    Retorna lista de chunks de PDF ordenados por relevância.
    """

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    modelo = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

    # Gerar embedding da query
    query_embedding = modelo.encode(query, convert_to_numpy=True).astype(np.float32)

    # Buscar chunks
    result = sb.table("pdf_chunks").select(
        "chunk_text, embedding"
    ).limit(500).execute()

    if not result.data:
        return []

    # Calcular similaridade
    similaridades = []
    for chunk in result.data:
        if not chunk.get("embedding"):
            continue

        try:
            emb = chunk["embedding"]
            if isinstance(emb, str):
                emb = json.loads(emb)

            chunk_emb = np.array(emb, dtype=np.float32)

            # Coseno
            norm_q = np.linalg.norm(query_embedding)
            norm_c = np.linalg.norm(chunk_emb)

            if norm_q > 0 and norm_c > 0:
                sim = np.dot(query_embedding, chunk_emb) / (norm_q * norm_c)

                if sim >= 0.3:  # Mínimo
                    similaridades.append({
                        "text": chunk["chunk_text"],
                        "sim": sim
                    })
        except:
            continue

    # Top-K
    similaridades.sort(key=lambda x: x["sim"], reverse=True)
    return [c["text"] for c in similaridades[:top_k]]

def responder_com_rag(pergunta_usuario: str) -> str:
    """
    Responde pergunta do usuário usando RAG como contexto para Claude.
    """

    print(f"📝 Pergunta: {pergunta_usuario}")
    print("-" * 70)

    # 1. Buscar contexto via RAG
    print("🔍 Buscando contexto em documentos...")
    chunks_contexto = buscar_contexto_rag(pergunta_usuario, top_k=3)

    if not chunks_contexto:
        print("⚠️ Nenhum contexto encontrado")
        contexto_str = "(Nenhum documento relevante encontrado)"
    else:
        print(f"✅ Encontrados {len(chunks_contexto)} chunks relevantes")
        contexto_str = "\n\n".join([
            f"[Documento {i+1}]\n{chunk[:300]}..."
            for i, chunk in enumerate(chunks_contexto)
        ])

    # 2. Enviar para Claude com contexto
    print("\n🧠 Processando com LLM...")

    client = anthropic.Anthropic()

    prompt = f"""Você é o AgroIA, assistente de licitações agrícolas da RMC.

CONTEXTO (extraído de documentos):
{contexto_str}

PERGUNTA DO USUÁRIO:
{pergunta_usuario}

Responda com base no contexto acima. Se o contexto não for suficiente, avise o usuário.
Seja conciso (máximo 3 parágrafos)."""

    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=500,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    resposta = response.content[0].text

    print("\n💬 Resposta:")
    print("=" * 70)
    print(resposta)
    print("=" * 70)

    return resposta

if __name__ == "__main__":
    print("=" * 70)
    print("🌾 AgroIA RAG + Chat - Exemplo de Integração")
    print("=" * 70)
    print()

    # Exemplos de perguntas
    perguntas = [
        "Quais produtos lácteos foram mais licitados?",
        "Qual é o valor médio de leite em licitações?",
        "Quais são os fornecedores de alimentos agrícolas?",
    ]

    # Fazer primeira pergunta como exemplo
    responder_com_rag(perguntas[0])

    print("\n" + "=" * 70)
    print("✅ Exemplo completo!")
    print("=" * 70)
    print("""
Para integrar isso em seu chat:

1. Criar endpoint que receba a pergunta do usuário
2. Chamar buscar_contexto_rag(pergunta)
3. Enviar chunks como contexto para Claude
4. Retornar resposta enriquecida ao usuário

Vantagens do RAG:
✓ Respostas com evidências de documentos reais
✓ Reduce alucinações do LLM
✓ Rastreabilidade (sabe de qual documento veio a resposta)
✓ Performance (busca rápida de contexto relevante)
""")
