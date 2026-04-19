"""
AgroIA-RMC — Diagnóstico Etapa 2 (v3)
=====================================
Descobre a estrutura real da tabela antes de consultar.

Execute: python debug_etapa2_v3.py
"""

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

print("=" * 60)
print("DIAGNÓSTICO ETAPA 2 — AgroIA-RMC")
print("=" * 60)

# 1. Total de licitações no banco
r_total = sb.table("licitacoes").select("id", count="exact").execute()
total = r_total.count if r_total.count else len(r_total.data)
print(f"\n[1] Total de licitações no banco: {total}")

# 2. Descobrir estrutura da tabela
print("\n[2] Estrutura da tabela 'licitacoes':")
r_sample = sb.table("licitacoes").select("*").limit(1).execute()
if r_sample.data:
    campos = list(r_sample.data[0].keys())
    print(f"    Colunas ({len(campos)}):")
    for c in sorted(campos):
        valor = r_sample.data[0][c]
        tipo = type(valor).__name__ if valor is not None else "null"
        print(f"      - {c}: {tipo}")
    
    # Mostrar um registro de exemplo
    print("\n[3] Exemplo de registro:")
    for k, v in r_sample.data[0].items():
        if v is not None:
            v_str = str(v)[:60] + "..." if len(str(v)) > 60 else str(v)
            print(f"      {k}: {v_str}")
else:
    print("    [!] Tabela vazia")

# 3. Verificar tabelas relacionadas
print("\n[4] Verificando tabelas relacionadas:")

tabelas = ["itens_licitacao", "fornecedores", "participacoes", "empenhos"]
for tabela in tabelas:
    try:
        r = sb.table(tabela).select("id", count="exact").execute()
        qtd = r.count if r.count else len(r.data)
        print(f"    {tabela}: {qtd} registros")
    except Exception as e:
        print(f"    {tabela}: [ERRO] {e}")

# 4. Identificar campo que marca coleta de detalhes
print("\n[5] Campos candidatos para controle de coleta:")
if r_sample.data:
    for c in campos:
        if "coleta" in c.lower() or "detalhe" in c.lower() or "data" in c.lower():
            print(f"    → {c}")

# 5. Verificar se há algum campo de "processo" ou identificador
print("\n[6] Campos de identificação do processo:")
if r_sample.data:
    for c in campos:
        if "processo" in c.lower() or "numero" in c.lower() or "modalidade" in c.lower() or "ano" in c.lower():
            print(f"    → {c}: {r_sample.data[0][c]}")

print("\n" + "=" * 60)
print("PRÓXIMO PASSO")
print("=" * 60)
print("""
Com base na estrutura acima, identifique:
1. Qual campo contém o número do processo
2. Qual campo marca se os detalhes já foram coletados
3. Se as tabelas de itens/fornecedores existem

Me envie o output para ajustarmos o scraper.
""")
