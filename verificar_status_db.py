from dotenv import load_dotenv
from supabase import create_client
import os

load_dotenv()
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# Contar documentos coletados
result = sb.table("documentos_licitacao").select("count", count="exact").execute()
total_db = result.count

print(f"Total de documentos no BD: {total_db}")

# Ver alguns registros recentes
result = sb.table("documentos_licitacao").select("licitacao_id, nome_doc, coletado_em").order("id", desc=True).limit(10).execute()
print(f"\n10 documentos mais recentes:")
for row in result.data:
    print(f"  ID Lic: {row['licitacao_id']:4d} | {row['nome_doc'][:40]:40s} | {row['coletado_em'][:10]}")

# Contar licitações com documentos
result = sb.table("documentos_licitacao").select("licitacao_id").execute()
lic_ids = set(row['licitacao_id'] for row in result.data)
print(f"\nLicitações com documentos: {len(lic_ids)}")

# Total de licitações
result = sb.table("licitacoes").select("count", count="exact").execute()
total_lic = result.count
print(f"Total de licitações: {total_lic}")
print(f"Cobertura: {100*len(lic_ids)/total_lic:.1f}%")
