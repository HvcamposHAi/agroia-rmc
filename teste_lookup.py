from dotenv import load_dotenv
from supabase import create_client
import os

load_dotenv()
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

processos = ["DE 4/2019 - SMSAN/FAAC", "DE 5/2019 - SMSAN/FAAC", "AD 3/2019 - SMSAN/FAAC"]

results = []
for proc in processos:
    try:
        result = sb.table("licitacoes").select("id, processo").eq("processo", proc).execute()
        if result.data:
            results.append(f"{proc} => ID {result.data[0]['id']}")
        else:
            results.append(f"{proc} => NOT FOUND")
    except Exception as e:
        results.append(f"{proc} => ERROR: {str(e)}")

for line in results:
    print(line)
