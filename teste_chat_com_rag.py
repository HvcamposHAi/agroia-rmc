#!/usr/bin/env python3
"""
Teste: Chat integrado com RAG.
Valida que o agent consegue usar a ferramenta buscar_chunks_rag
e enriquecer respostas com contexto de documentos.
"""

import sys
from chat.agent import chat

def teste_chat_rag():
    """Testa chat com diferentes perguntas que devem ativar RAG"""

    print("=" * 70)
    print("🧪 TESTE: Chat com RAG Integrado")
    print("=" * 70)

    perguntas_teste = [
        # Pergunta que deve ativar RAG
        {
            "pergunta": "Quais são os requisitos para fornecimento de leite fresco?",
            "esperado": "RAG deve buscar requisitos em documentos"
        },
        # Pergunta de dados (query_itens_agro)
        {
            "pergunta": "Qual foi a demanda por alface em 2022?",
            "esperado": "query_itens_agro"
        },
        # Pergunta mista
        {
            "pergunta": "Quais produtos lácteos foram mais solicitados e qual era o requisito mínimo?",
            "esperado": "Combinação de query_itens_agro + RAG"
        }
    ]

    for idx, teste in enumerate(perguntas_teste, 1):
        pergunta = teste["pergunta"]
        print(f"\n{'─' * 70}")
        print(f"📝 Pergunta {idx}: {pergunta}")
        print(f"   Esperado: {teste['esperado']}")
        print(f"{'─' * 70}")

        try:
            resultado = chat(pergunta, historico=[])

            print(f"\n💬 Resposta:")
            print(f"{resultado['resposta']}")

            print(f"\n🔧 Tools usadas: {resultado.get('tools_usadas', [])}")

            # Validar que RAG foi usado quando apropriado
            if "requisito" in pergunta.lower() or "qualidade" in pergunta.lower():
                if "buscar_chunks_rag" in resultado.get("tools_usadas", []):
                    print("✅ RAG foi chamado (como esperado)")
                else:
                    print("⚠️  RAG não foi chamado (mas poderia ter sido)")

        except Exception as e:
            print(f"❌ Erro: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'=' * 70}")
    print("✅ Testes concluídos!")
    print(f"{'=' * 70}")

if __name__ == "__main__":
    teste_chat_rag()
