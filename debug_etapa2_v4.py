"""
AgroIA-RMC — Diagnóstico do Matching (v4)
=========================================
Identifica por que o scraper não está processando registros.

Execute: python debug_etapa2_v4.py
"""

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

print("=" * 60)
print("DIAGNÓSTICO DO MATCHING — AgroIA-RMC")
print("=" * 60)

# 1. Licitações que JÁ TÊM itens (já coletadas)
print("\n[1] Licitações que JÁ TÊM itens coletados:")
r_itens = sb.table("itens_licitacao").select("licitacao_id").execute()
ids_com_itens = set(x["licitacao_id"] for x in r_itens.data if x.get("licitacao_id"))
print(f"    IDs com itens: {len(ids_com_itens)}")

if ids_com_itens:
    # Buscar detalhes dessas licitações
    r_coletadas = sb.table("licitacoes").select("id, processo, situacao").in_("id", list(ids_com_itens)[:10]).execute()
    print("    Exemplos de licitações já coletadas:")
    for x in r_coletadas.data:
        print(f"      ID={x['id']} | {x['processo']} | {x['situacao']}")

# 2. Licitações PENDENTES (sem itens)
print("\n[2] Licitações PENDENTES (sem itens):")
r_todas = sb.table("licitacoes").select("id, processo, situacao, tipo_processo").limit(1000).execute()
ids_todas = set(x["id"] for x in r_todas.data)
ids_pendentes = ids_todas - ids_com_itens
print(f"    Total: {len(r_todas.data)} | Com itens: {len(ids_com_itens)} | Pendentes: {len(ids_pendentes)}")

# Mostrar alguns pendentes
pendentes = [x for x in r_todas.data if x["id"] in ids_pendentes][:15]
print("    Exemplos de pendentes:")
for x in pendentes[:10]:
    print(f"      ID={x['id']} | {x['processo']} | {x['situacao']}")

# 3. Distribuição por tipo de processo (modalidade)
print("\n[3] Distribuição por tipo de processo:")
tipos = {}
for x in r_todas.data:
    t = x.get("tipo_processo", "?")
    tipos[t] = tipos.get(t, 0) + 1
for t, qtd in sorted(tipos.items(), key=lambda x: -x[1]):
    print(f"      {t}: {qtd}")

# 4. Distribuição por situação
print("\n[4] Distribuição por situação:")
situacoes = {}
for x in r_todas.data:
    s = x.get("situacao", "?")
    situacoes[s] = situacoes.get(s, 0) + 1
for s, qtd in sorted(situacoes.items(), key=lambda x: -x[1]):
    print(f"      {s}: {qtd}")

# 5. Verificar estrutura da tabela itens_licitacao
print("\n[5] Estrutura da tabela 'itens_licitacao':")
r_item = sb.table("itens_licitacao").select("*").limit(1).execute()
if r_item.data:
    print(f"    Colunas: {list(r_item.data[0].keys())}")
    print("    Exemplo:")
    for k, v in r_item.data[0].items():
        if v is not None:
            v_str = str(v)[:50] + "..." if len(str(v)) > 50 else str(v)
            print(f"      {k}: {v_str}")

# 6. Análise do problema
print("\n" + "=" * 60)
print("ANÁLISE")
print("=" * 60)

# Verificar se os pendentes têm tipos que deveriam ser coletados
TIPOS_COM_DETALHE = {"CR", "AD", "PE", "DS", "DE", "DT", "CH", "CP"}
pendentes_coletiveis = [x for x in pendentes if x.get("tipo_processo") in TIPOS_COM_DETALHE]
print(f"\nPendentes com tipo que TEM detalhe: {len(pendentes_coletiveis)}")
if pendentes_coletiveis:
    print("Exemplos:")
    for x in pendentes_coletiveis[:5]:
        print(f"  {x['processo']} | {x['situacao']}")

# Verificar situações
print(f"\nSituações dos pendentes:")
sit_pend = {}
for x in pendentes:
    s = x.get("situacao", "?")
    sit_pend[s] = sit_pend.get(s, 0) + 1
for s, qtd in sorted(sit_pend.items(), key=lambda x: -x[1]):
    print(f"  {s}: {qtd}")

print("\n" + "=" * 60)
print("CONCLUSÃO")
print("=" * 60)
print(f"""
- Total no banco: {len(r_todas.data)}
- Já coletados (com itens): {len(ids_com_itens)}
- Pendentes: {len(ids_pendentes)}

O scraper etapa2_simples.py mostra:
  "5 registros | 1 páginas" no portal
  "Processados: 0"

HIPÓTESES:
1. Os 5 do portal são os mesmos 5 já coletados → nada a fazer
2. O matching entre portal e banco está falhando
3. A pesquisa no portal está com filtro restritivo (ex: só 2025)

Para confirmar, verifique:
- Se o scraper pesquisa TODO o período (2019-2025)
- Se o matching compara corretamente o campo 'processo'
""")
