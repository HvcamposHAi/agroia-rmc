#!/usr/bin/env python3
"""
Exporta dados estruturados em CSVs prontos para dissertação/planilhas.
"""

import os
import csv
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def exportar_culturas():
    """Exporta culturas por valor."""
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

    dados_sorted = sorted(culturas.items(), key=lambda x: x[1]["valor"], reverse=True)

    with open("culturas_por_valor.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["cultura", "categoria", "qtd_itens", "valor_total_R$"])
        writer.writeheader()
        for cult, info in dados_sorted:
            writer.writerow({
                "cultura": cult,
                "categoria": info["categoria"],
                "qtd_itens": info["qtd"],
                "valor_total_R$": round(info["valor"], 2)
            })

    print(f"[OK] culturas_por_valor.csv ({len(dados_sorted)} linhas)")

def exportar_demanda_por_ano():
    """Exporta demanda por ano."""
    items = sb.from_("vw_itens_agro").select(
        "dt_abertura, canal, categoria_v2, valor_total"
    ).execute().data or []

    demanda = {}
    for item in items:
        data = item.get("dt_abertura", "")
        ano = int(data[:4]) if data else 0
        canal = item.get("canal", "OUTRO")
        cat = item.get("categoria_v2", "")
        val = float(item.get("valor_total", 0))

        chave = (ano, canal, cat)
        if chave not in demanda:
            demanda[chave] = 0
        demanda[chave] += val

    with open("demanda_por_ano_canal_categoria.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ano", "canal", "categoria", "valor_R$"])
        writer.writeheader()
        for (ano, canal, cat), val in sorted(demanda.items()):
            writer.writerow({
                "ano": ano,
                "canal": canal,
                "categoria": cat,
                "valor_R$": round(val, 2)
            })

    print(f"[OK] demanda_por_ano_canal_categoria.csv ({len(demanda)} linhas)")

def exportar_fornecedores():
    """Exporta fornecedores principais."""
    fornecedores = sb.from_("fornecedores").select("*").execute().data or []
    participacoes = sb.from_("participacoes").select("fornecedor_id, licitacao_id").execute().data or []

    forn_dict = {}
    for p in participacoes:
        forn_id = p.get("fornecedor_id")
        forn = next((f for f in fornecedores if f.get("id") == forn_id), None)
        if not forn:
            continue

        chave = (forn.get("razao_social", ""), forn.get("tipo", ""))
        if chave not in forn_dict:
            forn_dict[chave] = 0
        forn_dict[chave] += 1

    with open("fornecedores_principais.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["razao_social", "tipo", "qtd_licitacoes"])
        writer.writeheader()
        for (razao, tipo), qtd in sorted(forn_dict.items(), key=lambda x: x[1], reverse=True):
            writer.writerow({
                "razao_social": razao,
                "tipo": tipo,
                "qtd_licitacoes": qtd
            })

    print(f"[OK] fornecedores_principais.csv ({len(forn_dict)} linhas)")

if __name__ == "__main__":
    print("Exportando CSVs para dissertação...")
    exportar_culturas()
    exportar_demanda_por_ano()
    exportar_fornecedores()
    print("\nCSVs prontos para uso em planilhas/LaTeX!")
