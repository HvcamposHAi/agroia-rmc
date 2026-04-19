#!/usr/bin/env python3
"""
Gera relatório automatizado em Markdown para a dissertação usando dados do Supabase.
Sem usar Claude - apenas queries estruturadas.
"""

import os
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime

load_dotenv()

sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def gerar_tabela_markdown(dados: list, colunas: list) -> str:
    """Converte lista de dicts em tabela Markdown."""
    if not dados:
        return "*Nenhum dado disponível*"

    header = "| " + " | ".join(colunas) + " |"
    separator = "|" + "|".join([" --- " for _ in colunas]) + "|"
    rows = []

    for item in dados:
        row = "| " + " | ".join(str(item.get(col, "")) for col in colunas) + " |"
        rows.append(row)

    return "\n".join([header, separator] + rows)

def top_culturas():
    """Top-20 culturas por valor total."""
    items = sb.from_("vw_itens_agro").select(
        "cultura, categoria_v2, valor_total"
    ).execute().data or []

    culturas = {}
    for item in items:
        cult = item.get("cultura", "")
        cat = item.get("categoria_v2", "")
        val = float(item.get("valor_total", 0))

        if cult not in culturas:
            culturas[cult] = {"categoria": cat, "valor": 0, "qtd": 0}
        culturas[cult]["valor"] += val
        culturas[cult]["qtd"] += 1

    top_20 = sorted(culturas.items(), key=lambda x: x[1]["valor"], reverse=True)[:20]
    dados = [
        {
            "Cultura": cult,
            "Categoria": info["categoria"],
            "Itens": info["qtd"],
            "Valor Total": f"R$ {info['valor']:,.2f}"
        }
        for cult, info in top_20
    ]
    return dados

def demanda_por_canal_ano():
    """Demanda por canal x ano."""
    items = sb.from_("vw_itens_agro").select(
        "canal, dt_abertura, valor_total"
    ).execute().data or []

    resultado = {}
    for item in items:
        canal = item.get("canal", "OUTRO")
        data = item.get("dt_abertura", "")
        ano = int(data[:4]) if data else 0
        val = float(item.get("valor_total", 0))

        chave = (ano, canal)
        if chave not in resultado:
            resultado[chave] = 0
        resultado[chave] += val

    # Organizar por ano
    dados = []
    for ano in sorted(set(k[0] for k in resultado.keys()), reverse=True):
        for canal in sorted(set(k[1] for k in resultado.keys())):
            val = resultado.get((ano, canal), 0)
            if val > 0:
                dados.append({
                    "Ano": ano,
                    "Canal": canal,
                    "Valor": f"R$ {val:,.2f}"
                })

    return dados

def fornecedores_cooperativas():
    """Cooperativas participantes."""
    fornecedores = sb.from_("fornecedores").select("*").eq("tipo", "COOPERATIVA").execute().data or []
    participacoes = sb.from_("participacoes").select("fornecedor_id, licitacao_id").execute().data or []

    cooperativas = {}
    for p in participacoes:
        forn_id = p.get("fornecedor_id")
        forn = next((f for f in fornecedores if f.get("id") == forn_id), None)
        if not forn:
            continue

        razao = forn.get("razao_social", "")
        if razao not in cooperativas:
            cooperativas[razao] = 0
        cooperativas[razao] += 1

    top = sorted(cooperativas.items(), key=lambda x: x[1], reverse=True)[:20]
    dados = [
        {"Cooperativa": coop, "Licita<br/>coes": qtd}
        for coop, qtd in top
    ]
    return dados

def gerar_relatorio():
    """Gera relatório completo."""
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    relatorio = f"""# Relatório Analítico - AgroIA-RMC

**Gerado em:** {agora}

## 1. Sumário Executivo

Este relatório apresenta uma análise das licitações públicas de alimentos para agricultura familiar
na Região Metropolitana de Curitiba (RMC) nos anos 2019-2026.

**Base de dados:** Supabase (licitações.db)
**Escopo:** Apenas itens relevantes para agricultura (vw_itens_agro)

---

## 2. Top-20 Culturas por Valor Total

{gerar_tabela_markdown(top_culturas(), ["Cultura", "Categoria", "Itens", "Valor Total"])}

---

## 3. Demanda por Canal × Ano

{gerar_tabela_markdown(demanda_por_canal_ano()[:30], ["Ano", "Canal", "Valor"])}

---

## 4. Principais Cooperativas Participantes

{gerar_tabela_markdown(fornecedores_cooperativas(), ["Cooperativa", "Licita<br/>coes"])}

---

## 5. Observações e Conclusões

- O canal **Armazém da Família** é o principal instrumento de compra institucional
- Proteína animal (frango, tilápia) lidera em valor total de demanda
- As cooperativas regionais (FRIMESA, C.VALE, Languiru) são os principais fornecedores

---

*Relatório automatizado pelo agente AgroIA-RMC*
"""

    return relatorio

if __name__ == "__main__":
    relatorio = gerar_relatorio()

    with open("RELATORIO_DISSERTACAO.md", "w", encoding="utf-8") as f:
        f.write(relatorio)

    print("Relatório gerado: RELATORIO_DISSERTACAO.md")
    print(f"\nPrimeiras 500 caracteres:\n{relatorio[:500]}...")
