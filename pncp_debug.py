"""
Debug PNCP API - testa vários formatos de parâmetros para encontrar o correto.
Execute: python pncp_debug.py
"""
import requests, json

BASE = "https://pncp.gov.br/api/consulta/v1"
HEADERS = {"User-Agent": "AgroIA-RMC/1.0", "Accept": "application/json"}

def get(endpoint, params):
    url = f"{BASE}{endpoint}"
    r = requests.get(url, params=params, headers=HEADERS, timeout=20)
    print(f"  [{r.status_code}] {r.url[:120]}")
    if r.status_code == 200:
        d = r.json()
        print(f"  Resposta: {json.dumps(d, ensure_ascii=False)[:500]}")
        return d
    else:
        print(f"  Erro: {r.text[:300]}")
        return None

print("=== TESTE 1: data sem hífen + UF ===")
get("/contratacoes/publicacao", {
    "dataInicial": "20240101",
    "dataFinal":   "20240131",
    "uf":          "PR",
    "pagina":      1,
    "tamanhoPagina": 5,
})

print("\n=== TESTE 2: data sem hífen + codigoMunicipio ===")
get("/contratacoes/publicacao", {
    "dataInicial":     "20240101",
    "dataFinal":       "20240131",
    "codigoMunicipio": "4106902",
    "pagina":          1,
    "tamanhoPagina":   5,
})

print("\n=== TESTE 3: apenas datas ===")
get("/contratacoes/publicacao", {
    "dataInicial": "20240101",
    "dataFinal":   "20240105",
    "pagina":      1,
    "tamanhoPagina": 3,
})

print("\n=== TESTE 4: por CNPJ do órgão (SMSAN/FAAC) ===")
# CNPJ FAAC: 73.806.547/0001-79
get("/contratacoes/publicacao", {
    "dataInicial":    "20240101",
    "dataFinal":      "20241231",
    "cnpjOrgao":      "73806547000179",
    "pagina":         1,
    "tamanhoPagina":  5,
})

print("\n=== TESTE 5: por CNPJ Prefeitura de Curitiba ===")
# CNPJ PMC: 76.417.005/0001-36
get("/contratacoes/publicacao", {
    "dataInicial":    "20240101",
    "dataFinal":      "20241231",
    "cnpjOrgao":      "76417005000136",
    "pagina":         1,
    "tamanhoPagina":  5,
})

print("\n=== TESTE 6: endpoint de contratos ===")
get("/contratos", {
    "dataInicial": "20240101",
    "dataFinal":   "20240131",
    "pagina":      1,
    "tamanhoPagina": 3,
})

print("\n=== TESTE 7: listar endpoints disponíveis ===")
# Tentar o swagger JSON
import requests
r = requests.get("https://pncp.gov.br/api/consulta/v3/api-docs",
                 headers=HEADERS, timeout=10)
print(f"  [{r.status_code}] api-docs")
if r.status_code == 200:
    docs = r.json()
    paths = list(docs.get("paths", {}).keys())
    print(f"  Endpoints ({len(paths)}):")
    for p in paths[:20]:
        print(f"    {p}")

print("\n=== TESTE 8: endpoint compras por CNPJ direto ===")
# Formato: /orgaos/{cnpj}/compras
get("/orgaos/76417005000136/compras", {
    "pagina": 1, "tamanhoPagina": 5,
    "dataInicial": "20240101", "dataFinal": "20241231",
})
