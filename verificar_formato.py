from dotenv import load_dotenv
from supabase import create_client
import os

load_dotenv()
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# Check columns
try:
    result = sb.table("licitacoes").select("*").limit(1).execute()
    print("Colunas da tabela 'licitacoes':")
    if result.data:
        for key in result.data[0].keys():
            print(f"  - {key}")

        # Mostrar primeiro registro
        print(f"\nPrimeiro registro:")
        for key, val in result.data[0].items():
            if isinstance(val, str) and len(str(val)) < 100:
                print(f"  {key}: {val}")
except Exception as e:
    print(f"Erro: {e}")

# Procurar especificamente por registros com "DE" ou "2019"
print("\nProcurando registros com 'DE 4':")
try:
    result = sb.table("licitacoes").select("*").ilike("id_processo", "%DE 4%").limit(5).execute()
    if result.data:
        for row in result.data:
            print(f"  {row}")
except:
    pass

# Try different column names
print("\nTentando diferentes colnames para processo/numero:")
for colname in ["id_processo", "processo", "edital", "num_edital", "numero"]:
    try:
        result = sb.table("licitacoes").select("id, " + colname).limit(2).execute()
        print(f"  ✓ '{colname}' existe!")
        for row in result.data:
            print(f"    ID: {row['id']}, {colname}: {row[colname]}")
    except:
        pass
