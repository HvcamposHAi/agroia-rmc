"""
AgroIA-RMC — Diagnóstico Etapa 2
================================
Identifica por que o scraper está retornando 0 processados.

Execute: python debug_etapa2.py
"""

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("[ERRO] Variáveis SUPABASE_URL e SUPABASE_KEY não definidas no .env")
    exit(1)

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

print("=" * 60)
print("DIAGNÓSTICO ETAPA 2 — AgroIA-RMC")
print("=" * 60)

# 1. Total de licitações no banco
r_total = sb.table("licitacoes").select("id", count="exact").execute()
total = r_total.count if r_total.count else len(r_total.data)
print(f"\n[1] Total de licitações no banco: {total}")

# 2. Licitações JÁ COLETADAS (com detalhes)
r_coletados = sb.table("licitacoes").select(
    "numero_processo, ano_processo, cod_modalidade, situacao"
).not_.is_("data_coleta_detalhes", "null").limit(15).execute()

print(f"\n[2] Licitações JÁ COLETADAS (com detalhes): {len(r_coletados.data)}")
if r_coletados.data:
    print("    Exemplos:")
    for x in r_coletados.data[:10]:
        print(f"      {x['cod_modalidade']} {x['numero_processo']}/{x['ano_processo']} — {x.get('situacao','')}")

# 3. Licitações PENDENTES (sem detalhes)
r_pendentes = sb.table("licitacoes").select(
    "numero_processo, ano_processo, cod_modalidade, situacao"
).is_("data_coleta_detalhes", "null").limit(15).execute()

print(f"\n[3] Licitações PENDENTES (sem detalhes): {len(r_pendentes.data)}")
if r_pendentes.data:
    print("    Exemplos:")
    for x in r_pendentes.data[:10]:
        print(f"      {x['cod_modalidade']} {x['numero_processo']}/{x['ano_processo']} — {x.get('situacao','')}")

# 4. Distribuição por ano (pendentes)
print("\n[4] Distribuição de PENDENTES por ano:")
for ano in range(2019, 2027):
    r = sb.table("licitacoes").select("id", count="exact").eq("ano_processo", ano).is_("data_coleta_detalhes", "null").execute()
    qtd = r.count if r.count else len(r.data)
    if qtd > 0:
        print(f"      {ano}: {qtd} pendentes")

# 5. Verificar se há itens na tabela itens_licitacao
r_itens = sb.table("itens_licitacao").select("id", count="exact").execute()
qtd_itens = r_itens.count if r_itens.count else len(r_itens.data)
print(f"\n[5] Total de ITENS na tabela itens_licitacao: {qtd_itens}")

# 6. Verificar fornecedores
r_forn = sb.table("fornecedores").select("id", count="exact").execute()
qtd_forn = r_forn.count if r_forn.count else len(r_forn.data)
print(f"\n[6] Total de FORNECEDORES na tabela: {qtd_forn}")

# 7. Verificar se o campo data_coleta_detalhes existe
print("\n[7] Verificando estrutura da tabela licitacoes...")
r_sample = sb.table("licitacoes").select("*").limit(1).execute()
if r_sample.data:
    campos = list(r_sample.data[0].keys())
    tem_data_coleta = "data_coleta_detalhes" in campos
    print(f"    Campo 'data_coleta_detalhes' existe: {tem_data_coleta}")
    if not tem_data_coleta:
        print("    [!] PROBLEMA: Campo não existe — o script não consegue marcar como coletado")
        print("    Campos disponíveis:", campos)
else:
    print("    [!] Tabela vazia ou erro de acesso")

print("\n" + "=" * 60)
print("CONCLUSÃO")
print("=" * 60)

if total == 0:
    print("→ Banco VAZIO. Execute primeiro a Etapa 1 (lista de licitações).")
elif len(r_pendentes.data) == 0:
    print("→ Todas as licitações JÁ TÊM detalhes. Nada a processar.")
elif not tem_data_coleta:
    print("→ Campo 'data_coleta_detalhes' não existe na tabela.")
    print("  Execute o SQL para criar a coluna:")
    print("  ALTER TABLE licitacoes ADD COLUMN data_coleta_detalhes TIMESTAMPTZ;")
else:
    print(f"→ Há {len(r_pendentes.data)}+ licitações pendentes.")
    print("  O problema está no MATCHING entre portal e banco.")
    print("  Verifique se o scraper está encontrando os processos corretos.")

print()
