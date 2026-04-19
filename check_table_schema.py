from dotenv import load_dotenv
from supabase import create_client
import os

load_dotenv()
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

try:
    result = sb.table("documentos_licitacao").select("*").limit(1).execute()
    if result.data:
        print("Colunas da tabela 'documentos_licitacao':")
        for col in result.data[0].keys():
            val = result.data[0][col]
            print(f"  {col}: {type(val).__name__} = {val}")
    else:
        print("Tabela vazia - inserindo 1 registro de teste para ver schema")
except Exception as e:
    print(f"Erro: {e}")
