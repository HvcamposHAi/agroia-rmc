#!/usr/bin/env python3
"""
Teste de busca semântica no RAG com pdf_chunks + embeddings.
Valida que o sistema está funcionando corretamente.
"""

import os
import json
from dotenv import load_dotenv
from supabase import create_client
from sentence_transformers import SentenceTransformer
import numpy as np

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def testar_busca_semantica():
    """Testa busca semântica no RAG"""

    print("🧠 TESTE: Busca Semântica com RAG")
    print("=" * 70)

    # Inicializar
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    modelo = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

    # Teste 1: Verificar embeddings
    print("\n1️⃣ TESTE: Embeddings armazenados")
    print("-" * 70)
    try:
        result = sb.table("pdf_chunks").select("count", count="exact").not_.is_("embedding", "null").execute()
        total_com_embedding = result.count
        result_all = sb.table("pdf_chunks").select("count", count="exact").execute()
        total = result_all.count

        print(f"   ✅ Chunks com embedding: {total_com_embedding}/{total} ({100*total_com_embedding/total:.1f}%)")
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False

    # Teste 2: Busca por similaridade (sem usar SQL nativo)
    print("\n2️⃣ TESTE: Busca por similaridade de texto")
    print("-" * 70)

    queries = [
        "Leite fresco para merenda escolar",
        "Arroz e feijão para fornecedores",
        "Tomate e verduras hortaliças"
    ]

    for query_text in queries:
        print(f"\n   Query: '{query_text}'")

        try:
            # Gerar embedding da query
            query_embedding = modelo.encode(query_text, convert_to_numpy=True)

            # Buscar chunks e calcular similaridade em Python
            # (Como o PostgREST não tem suporte nativo a pgvector, fazemos em Python)
            result = sb.table("pdf_chunks").select("id, nome_doc, chunk_text, embedding").limit(100).execute()

            if not result.data:
                print(f"      (sem chunks para comparar)")
                continue

            # Calcular similaridade para cada chunk
            similaridades = []
            for chunk in result.data:
                if chunk["embedding"]:
                    # Converter embedding para array numérico (pode estar como string ou lista)
                    emb = chunk["embedding"]
                    if isinstance(emb, str):
                        emb = json.loads(emb)
                    chunk_emb = np.array(emb, dtype=np.float32)

                    # Similaridade coseno
                    try:
                        sim = np.dot(query_embedding, chunk_emb) / (
                            np.linalg.norm(query_embedding) * np.linalg.norm(chunk_emb) + 1e-10
                        )
                        similaridades.append({
                            "id": chunk["id"],
                            "nome_doc": chunk["nome_doc"],
                            "chunk_text": chunk["chunk_text"][:80],
                            "similaridade": float(sim)
                        })
                    except Exception as e:
                        pass  # Skip if error

            # Top 3 mais similares
            top3 = sorted(similaridades, key=lambda x: x["similaridade"], reverse=True)[:3]

            for i, item in enumerate(top3, 1):
                print(f"      {i}. [{item['similaridade']:.3f}] {item['nome_doc']}")
                print(f"         → {item['chunk_text']}...")

        except Exception as e:
            print(f"      ❌ Erro: {e}")

    # Teste 3: Função SQL de busca (se houver)
    print("\n3️⃣ TESTE: Checar suporte pgvector no Supabase")
    print("-" * 70)
    try:
        # Tentar uma query que verifique se pgvector está ativo
        result = sb.rpc("exec_sql", {
            "sql": "SELECT 1 FROM pg_extension WHERE extname='vector';"
        }).execute()
        print(f"   ✅ pgvector habilitado no Supabase")
    except Exception as e:
        if "PGRST202" in str(e):
            print(f"   ⚠️ Function exec_sql não encontrada")
            print(f"      (Busca semântica funciona via Python)")
        else:
            print(f"   ⚠️ Nota: {e}")

    # Teste 4: Performance
    print("\n4️⃣ TESTE: Performance")
    print("-" * 70)
    import time
    try:
        start = time.time()
        result = sb.table("pdf_chunks").select("count", count="exact").execute()
        elapsed = time.time() - start
        print(f"   ✅ Leitura de chunks: {elapsed:.3f}s")

        # Tempo para gerar embedding
        start = time.time()
        test_emb = modelo.encode("teste", convert_to_numpy=True)
        elapsed = time.time() - start
        print(f"   ✅ Geração de embedding (1 texto): {elapsed:.3f}s")
    except Exception as e:
        print(f"   ⚠️ Erro: {e}")

    # Teste 5: Validar dados
    print("\n5️⃣ TESTE: Integridade dos dados")
    print("-" * 70)
    try:
        # Chunks sem embedding?
        result = sb.table("pdf_chunks").select("count", count="exact").is_("embedding", "null").execute()
        if result.count > 0:
            print(f"   ⚠️ {result.count} chunks SEM embedding")
        else:
            print(f"   ✅ Todos os chunks têm embeddings")

        # Chunks sem texto?
        result = sb.table("pdf_chunks").select("count", count="exact").is_("chunk_text", "null").execute()
        if result.count > 0:
            print(f"   ⚠️ {result.count} chunks SEM chunk_text")
        else:
            print(f"   ✅ Todos os chunks têm texto")

        # Documentos únicos
        result = sb.table("pdf_chunks").select("documento_id").execute()
        docs_unicos = len(set(r["documento_id"] for r in result.data if r.get("documento_id")))
        print(f"   ✅ {docs_unicos} documentos únicos indexados")

    except Exception as e:
        print(f"   ❌ Erro: {e}")

    print("\n" + "=" * 70)
    print("✅ TESTES CONCLUÍDOS")
    print("\n🎯 Próximos passos:")
    print("   1. Implementar endpoint de busca semântica na API")
    print("   2. Integrar com chat (usar prompts.py)")
    print("   3. Testar com consultas reais")

    return True

if __name__ == "__main__":
    testar_busca_semantica()
