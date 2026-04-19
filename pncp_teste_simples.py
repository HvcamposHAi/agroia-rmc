"""
Teste PNCP - busca pelo processo específico da SMSAN
Execute: python pncp_teste_simples.py
"""
import requests, json, time

BASE    = "https://pncp.gov.br/api/consulta/v1"
HEADERS = {"User-Agent": "AgroIA-RMC/1.0", "Accept": "application/json"}

def get(url, params=None, timeout=30):
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
        print(f"  [{r.status_code}] {r.url[:120]}")
        if r.status_code == 200:
            d = r.json()
            print(json.dumps(d, indent=2, ensure_ascii=False)[:1000])
            return d
        else:
            print(f"  Erro: {r.text[:300]}")
        return None
    except Exception as e:
        print(f"  ERRO {e.__class__.__name__}: {str(e)[:80]}")
        return None

# ── 1. Buscar pelo número de controle PNCP conhecido ─────────────────────────
# O edital CP 002/2025 SMSAN menciona PNCP. Tentar buscar com palavra-chave
print("=== 1. Buscar credenciamento SMSAN 2025 por modalidade 10 ===")
d = get(f"{BASE}/contratacoes/publicacao", {
    "dataInicial": "20250101",
    "dataFinal":   "20251231",
    "codigoModalidadeContratacao": 10,  # Credenciamento
    "uf": "PR",
    "pagina": 1,
    "tamanhoPagina": 50,
})
time.sleep(1)

# Filtrar Curitiba nos resultados
if d and isinstance(d, dict):
    total = d.get("totalRegistros", 0)
    print(f"\nTotal PR credenciamentos 2025: {total}")
    curitiba = []
    for c in (d.get("data") or []):
        orgao = c.get("orgaoEntidade", {}) or {}
        unidade = c.get("unidadeOrgao", {}) or {}
        municipio = unidade.get("municipioNome", "") or ""
        razao = orgao.get("razaoSocial", "") or ""
        cnpj  = orgao.get("cnpj", "") or ""
        if "CURITIBA" in (municipio + razao).upper() or cnpj.startswith("764170") or cnpj.startswith("738065"):
            curitiba.append(c)
            print(f"\n  *** CURITIBA ***")
            print(f"  CNPJ: {cnpj}")
            print(f"  Razão: {razao}")
            print(f"  Unidade: {unidade.get('nomeUnidade','')}")
            print(f"  Município: {municipio}")
            print(f"  Objeto: {c.get('objetoCompra','')[:80]}")
            print(f"  Ano/Seq: {c.get('anoCompra')}/{c.get('sequencialCompra')}")
            print(f"  Controle: {c.get('numeroControlePNCP','')}")

print(f"\nTotal Curitiba: {len(curitiba)}")

# ── 2. Se achou, buscar os itens ─────────────────────────────────────────────
if curitiba:
    c = curitiba[0]
    cnpj = c.get("orgaoEntidade", {}).get("cnpj", "")
    ano  = c.get("anoCompra")
    seq  = c.get("sequencialCompra")
    print(f"\n=== 2. Itens de {cnpj}/{ano}/{seq} ===")
    get(f"{BASE}/contratacoes/{cnpj}/{ano}/{seq}/itens",
        {"pagina": 1, "tamanhoPagina": 20})
    time.sleep(1)
    print(f"\n=== 3. Resultado/Fornecedores ===")
    get(f"{BASE}/contratacoes/{cnpj}/{ano}/{seq}/resultado")
else:
    # ── 3. Tentar SMAP/FAAC CNPJ direto ─────────────────────────────────────
    print("\n=== 2. Tentar SMAP CNPJ 27029184000179 (achado antes) ===")
    # O CNPJ 27029184000179 é SMAP (Secretaria Municipal de Admin/Planejamento)
    # Curitiba pode usar um CNPJ diferente por secretaria
    # Tentar outros CNPJs conhecidos de secretarias de Curitiba
    for cnpj in ["27029184000179", "76417005000136", "73806547000179"]:
        print(f"\n  CNPJ {cnpj}:")
        get(f"{BASE}/orgaos/{cnpj}", timeout=10)
        time.sleep(1)

print("\n=== FIM ===")
