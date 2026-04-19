#!/usr/bin/env python3
"""
Usa Claude para gerar insights analíticos sobre os dados.
Cria texto pronto para inserir na dissertação.
"""

import os
import json
from dotenv import load_dotenv
from supabase import create_client
import anthropic

load_dotenv()

sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def coletar_dados_resumo() -> dict:
    """Coleta resumo dos dados para análise."""
    items = sb.from_("vw_itens_agro").select("*").execute().data or []

    culturas = {}
    canais = {}
    anos = {}

    for item in items:
        # Por cultura
        cult = item.get("cultura", "")
        if cult not in culturas:
            culturas[cult] = 0
        culturas[cult] += float(item.get("valor_total", 0))

        # Por canal
        canal = item.get("canal", "")
        if canal not in canais:
            canais[canal] = 0
        canais[canal] += float(item.get("valor_total", 0))

        # Por ano
        data = item.get("dt_abertura", "")
        ano = int(data[:4]) if data else 0
        if ano not in anos:
            anos[ano] = 0
        anos[ano] += float(item.get("valor_total", 0))

    return {
        "total_itens": len(items),
        "top_culturas": sorted(culturas.items(), key=lambda x: x[1], reverse=True)[:5],
        "canais": sorted(canais.items(), key=lambda x: x[1], reverse=True),
        "anos": sorted(anos.items()),
        "valor_total": sum(culturas.values())
    }

def gerar_insights_claude(dados: dict) -> str:
    """Usa Claude para gerar análise dos dados."""
    prompt = f"""Você é um pesquisador de políticas agrícolas analisando dados de licitações públicas
de alimentos para agricultura familiar em Curitiba, Brasil (2019-2026).

DADOS:
- Total de itens licitados: {dados['total_itens']}
- Valor total: R$ {dados['valor_total']:,.2f}

Top-5 Culturas por Valor:
{json.dumps([{'cultura': c[0], 'valor': f'R$ {c[1]:,.2f}'} for c in dados['top_culturas']], ensure_ascii=False, indent=2)}

Canais Institucionais:
{json.dumps([{'canal': c[0], 'valor': f'R$ {c[1]:,.2f}'} for c in dados['canais']], ensure_ascii=False, indent=2)}

Evolução Temporal (2019-2026):
{json.dumps([{'ano': ano, 'valor': f'R$ {val:,.2f}'} for ano, val in dados['anos']], ensure_ascii=False, indent=2)}

Gere 3-4 parágrafos de análise conclusiva para dissertação de mestrado sobre:
1. Dinâmica de demanda por cultura
2. Concentração entre canais de compra
3. Evolução temporal
4. Implicações para políticas de agricultura familiar

Escreva em português acadêmico, sem markdown, pronto para inserir na dissertação.
"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text

if __name__ == "__main__":
    print("Coletando dados...")
    dados = coletar_dados_resumo()

    print(f"  Total itens: {dados['total_itens']}")
    print(f"  Valor total: R$ {dados['valor_total']:,.2f}")
    print(f"  Período: {dados['anos'][0][0]}-{dados['anos'][-1][0]}")

    print("\nGerando insights com Claude...")
    insights = gerar_insights_claude(dados)

    with open("INSIGHTS_DISSERTACAO.txt", "w", encoding="utf-8") as f:
        f.write(insights)

    print("\n" + "="*60)
    print("INSIGHTS GERADOS:")
    print("="*60)
    print(insights)
    print("="*60)
    print("\nSalvo em: INSIGHTS_DISSERTACAO.txt")
