"""
AgroIA-RMC — Validação de Dados no Supabase (Python)
====================================================
Alternativa ao SQL para validar os dados carregados.

Execute: python validar_dados.py
"""

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

def contar(tabela):
    r = sb.table(tabela).select("id", count="exact").execute()
    return r.count if r.count else len(r.data)

def separador(titulo):
    print(f"\n{'='*60}")
    print(f" {titulo}")
    print('='*60)

# ============================================================================
separador("1. RESUMO GERAL")
# ============================================================================

tabelas = ["licitacoes", "itens_licitacao", "fornecedores", "participacoes", "empenhos"]
for t in tabelas:
    try:
        qtd = contar(t)
        print(f"  {t}: {qtd:,}")
    except Exception as e:
        print(f"  {t}: ERRO - {e}")

# ============================================================================
separador("2. STATUS DE COLETA")
# ============================================================================

# IDs com itens
r_itens = sb.table("itens_licitacao").select("licitacao_id").execute()
ids_com_itens = set(x["licitacao_id"] for x in r_itens.data if x.get("licitacao_id"))

# Total de licitações
r_lic = sb.table("licitacoes").select("id").execute()
ids_todas = set(x["id"] for x in r_lic.data)

coletados = len(ids_com_itens)
pendentes = len(ids_todas) - coletados
total = len(ids_todas)

print(f"  Com detalhes coletados: {coletados:,} ({100*coletados/total:.1f}%)")
print(f"  Pendentes de coleta:    {pendentes:,} ({100*pendentes/total:.1f}%)")
print(f"  Total:                  {total:,}")

# ============================================================================
separador("3. LICITAÇÕES POR ANO")
# ============================================================================

r = sb.table("licitacoes").select("dt_abertura, relevante_af").execute()
por_ano = {}
for x in r.data:
    dt = x.get("dt_abertura")
    if dt:
        ano = dt[:4]
        if ano not in por_ano:
            por_ano[ano] = {"total": 0, "af": 0}
        por_ano[ano]["total"] += 1
        if x.get("relevante_af"):
            por_ano[ano]["af"] += 1

for ano in sorted(por_ano.keys()):
    d = por_ano[ano]
    print(f"  {ano}: {d['total']:4} licitações | {d['af']:3} relevantes AF")

# ============================================================================
separador("4. LICITAÇÕES POR MODALIDADE")
# ============================================================================

r = sb.table("licitacoes").select("tipo_processo, relevante_af").execute()
por_tipo = {}
for x in r.data:
    t = x.get("tipo_processo", "?")
    if t not in por_tipo:
        por_tipo[t] = {"total": 0, "af": 0}
    por_tipo[t]["total"] += 1
    if x.get("relevante_af"):
        por_tipo[t]["af"] += 1

for t, d in sorted(por_tipo.items(), key=lambda x: -x[1]["total"]):
    print(f"  {t:4}: {d['total']:4} | AF: {d['af']:3}")

# ============================================================================
separador("5. LICITAÇÕES POR SITUAÇÃO")
# ============================================================================

r = sb.table("licitacoes").select("situacao").execute()
por_sit = {}
for x in r.data:
    s = x.get("situacao", "?")
    por_sit[s] = por_sit.get(s, 0) + 1

for s, qtd in sorted(por_sit.items(), key=lambda x: -x[1]):
    print(f"  {s:25}: {qtd:4}")

# ============================================================================
separador("6. LICITAÇÕES POR CANAL")
# ============================================================================

r = sb.table("licitacoes").select("canal, relevante_af").execute()
por_canal = {}
for x in r.data:
    c = x.get("canal", "?")
    if c not in por_canal:
        por_canal[c] = {"total": 0, "af": 0}
    por_canal[c]["total"] += 1
    if x.get("relevante_af"):
        por_canal[c]["af"] += 1

for c, d in sorted(por_canal.items(), key=lambda x: -x[1]["total"]):
    print(f"  {c:20}: {d['total']:4} | AF: {d['af']:3}")

# ============================================================================
separador("7. ITENS POR CATEGORIA")
# ============================================================================

r = sb.table("itens_licitacao").select("categoria, licitacao_id").execute()
por_cat = {}
for x in r.data:
    c = x.get("categoria", "?")
    if c not in por_cat:
        por_cat[c] = {"total": 0, "lics": set()}
    por_cat[c]["total"] += 1
    por_cat[c]["lics"].add(x.get("licitacao_id"))

for c, d in sorted(por_cat.items(), key=lambda x: -x[1]["total"]):
    print(f"  {c:15}: {d['total']:4} itens | {len(d['lics']):3} licitações")

# ============================================================================
separador("8. TOP 15 CULTURAS")
# ============================================================================

r = sb.table("itens_licitacao").select("cultura").execute()
por_cultura = {}
for x in r.data:
    c = x.get("cultura", "")
    if c:
        por_cultura[c] = por_cultura.get(c, 0) + 1

for c, qtd in sorted(por_cultura.items(), key=lambda x: -x[1])[:15]:
    print(f"  {c:20}: {qtd:4}")

# ============================================================================
separador("9. FORNECEDORES POR TIPO")
# ============================================================================

r = sb.table("fornecedores").select("tipo").execute()
por_tipo_f = {}
for x in r.data:
    t = x.get("tipo", "?")
    por_tipo_f[t] = por_tipo_f.get(t, 0) + 1

for t, qtd in sorted(por_tipo_f.items(), key=lambda x: -x[1]):
    print(f"  {t:15}: {qtd:4}")

# ============================================================================
separador("10. LICITAÇÕES RELEVANTES AGRICULTURA FAMILIAR")
# ============================================================================

r = sb.table("licitacoes").select("processo, tipo_processo, canal, objeto").eq("relevante_af", True).limit(15).execute()
print(f"  Total: {len([x for x in sb.table('licitacoes').select('id').eq('relevante_af', True).execute().data])}")
print("\n  Exemplos:")
for x in r.data[:10]:
    obj = (x.get("objeto") or "")[:50]
    print(f"    {x['processo']} | {x['canal']} | {obj}...")

# ============================================================================
separador("11. AMOSTRA DE PENDENTES")
# ============================================================================

pendentes_ids = ids_todas - ids_com_itens
if pendentes_ids:
    r = sb.table("licitacoes").select("processo, tipo_processo, situacao").in_("id", list(pendentes_ids)[:10]).execute()
    for x in r.data:
        print(f"  {x['processo']} | {x['tipo_processo']} | {x['situacao']}")

# ============================================================================
separador("12. AMOSTRA DE COLETADOS")
# ============================================================================

if ids_com_itens:
    for lic_id in list(ids_com_itens)[:5]:
        r_lic = sb.table("licitacoes").select("processo").eq("id", lic_id).execute()
        r_itens = sb.table("itens_licitacao").select("id").eq("licitacao_id", lic_id).execute()
        r_part = sb.table("participacoes").select("id").eq("licitacao_id", lic_id).execute()
        proc = r_lic.data[0]["processo"] if r_lic.data else "?"
        print(f"  {proc} | {len(r_itens.data)} itens | {len(r_part.data)} fornecedores")

# ============================================================================
separador("RESUMO EXECUTIVO")
# ============================================================================

print(f"""
  Licitações no banco:        {total:,}
  Com detalhes coletados:     {coletados:,} ({100*coletados/total:.1f}%)
  Pendentes de coleta:        {pendentes:,}
  
  Total de itens:             {contar('itens_licitacao'):,}
  Total de fornecedores:      {contar('fornecedores'):,}
  Total de participações:     {contar('participacoes'):,}
  Total de empenhos:          {contar('empenhos'):,}
  
  Relevantes Agric. Familiar: {sum(1 for x in sb.table('licitacoes').select('id').eq('relevante_af', True).execute().data):,}
""")

print("=" * 60)
