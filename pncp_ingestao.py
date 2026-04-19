"""
AgroIA-RMC — Ingestão PNCP API (2024 em diante)
================================================
Mestrando: Humberto Vinicius Aparecido de Campos — PPGCA/UEPG

API PNCP — Endpoints de consulta (públicos, sem autenticação):
  Base: https://pncp.gov.br/api/consulta/v1

  Contratações por município:
  GET /contratacoes/publicacao
    ?dataInicial=YYYY-MM-DD
    &dataFinal=YYYY-MM-DD
    &codigoMunicipio=4106902    ← IBGE Curitiba
    &pagina=1
    &tamanhoPagina=50

  Itens de uma contratação:
  GET /contratacoes/{cnpj}/{ano}/{sequencial}/itens
    ?pagina=1&tamanhoPagina=500

  Fornecedores de uma contratação:
  GET /contratacoes/{cnpj}/{ano}/{sequencial}/fornecedores
    (retorna lista de vencedores/participantes)

  Contratos vinculados:
  GET /contratos?cnpjOrgao={cnpj}&ano={ano}&pagina=1&tamanhoPagina=50

CNPJ Prefeitura Curitiba (órgão): 76.417.005/0001-36
CNPJ FAAC (unidade compradora):   73.806.547/0001-79
Código IBGE Curitiba: 4106902

Instale: pip install requests supabase python-dotenv
Execute: python pncp_ingestao.py
"""

import os, re, time, json
from datetime import datetime, date
from dotenv import load_dotenv
import requests
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://rsphlvcekuomvpvjqxqm.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# ── PNCP ─────────────────────────────────────────────────────────────────────
PNCP_BASE    = "https://pncp.gov.br/api/consulta/v1"
COD_CURITIBA = "4106902"          # código IBGE Curitiba
CNPJ_FAAC    = "73806547000179"   # CNPJ FAAC sem formatação
CNPJ_PMC     = "76417005000136"   # CNPJ Prefeitura Municipal de Curitiba

DATA_INICIO  = "2024-01-01"
DATA_FIM     = date.today().strftime("%Y-%m-%d")

DELAY = 0.5   # segundos entre requisições (respeitar rate limit)

HEADERS = {
    "User-Agent": "AgroIA-RMC/1.0 (mestrado PPGCA/UEPG; pesquisa acadêmica)",
    "Accept":     "application/json",
}

# Palavras-chave para filtrar contratações relevantes para AF
PALAVRAS_AF = [
    "hortifrut", "hortifrutigranjeiro", "armazém da família", "armazem da familia",
    "agricultura familiar", "alimentos", "gêneros alimentícios", "generos alimenticios",
    "credenciamento", "paa", "programa de aquisição", "banco de alimentos",
    "olericultura", "orgânico", "organico", "cooperativa", "produtores",
    "frutas", "verduras", "legumes", "abastecimento alimentar",
]

def is_relevante_af(texto: str) -> bool:
    t = (texto or "").lower()
    return any(p in t for p in PALAVRAS_AF)


# ── Supabase ──────────────────────────────────────────────────────────────────

def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def get_supabase(): return create_client(SUPABASE_URL, SUPABASE_KEY)

def norm_cultura(d):
    mapa = {"abacaxi":"abacaxi","banana":"banana","goiaba":"goiaba","laranja":"laranja",
            "limão":"limao","limao":"limao","maçã":"maca","mamão":"mamao","mamao":"mamao",
            "melancia":"melancia","melão":"melao","uva":"uva","morango":"morango",
            "tomate":"tomate","cebola":"cebola","cenoura":"cenoura","batata":"batata",
            "aipim":"aipim","mandioca":"aipim","alface":"alface","couve":"couve",
            "repolho":"repolho","brócolis":"brocolis","brocolis":"brocolis","alho":"alho",
            "beterraba":"beterraba","pimentão":"pimentao","abobrinha":"abobrinha",
            "arroz":"arroz","feijão":"feijao","feijao":"feijao","milho":"milho",
            "queijo":"queijo","leite":"leite","ovos":"ovos","frango":"frango",
            "carne":"carne","pão":"pao","mel":"mel","inhame":"inhame"}
    d = (d or "").lower().strip()
    for k,v in mapa.items():
        if k in d: return v
    return d

def categ(c):
    if c in {"abacaxi","banana","goiaba","laranja","limao","maca","mamao",
             "melancia","melao","uva","morango"}: return "FRUTA"
    if c in {"tomate","cebola","cenoura","batata","aipim","alho","beterraba",
             "pimentao","abobrinha","milho","inhame"}: return "LEGUME"
    if c in {"alface","couve","repolho","brocolis"}: return "FOLHOSA"
    if c in {"queijo","leite"}: return "LATICINIOS"
    if c in {"frango","carne","ovos"}: return "PROTEINA"
    if c in {"arroz","feijao","farinha","mel","pao"}: return "GRAOS"
    return "OUTRO"

def tipo_forn(r):
    r = (r or "").upper()
    if "COOPERATIV" in r: return "COOPERATIVA"
    if "ASSOCIA" in r:    return "ASSOCIACAO"
    if any(x in r for x in ["LTDA","S.A","EIRELI"," ME "," EPP "]): return "EMPRESA"
    return "PESSOA_FISICA"

def classificar_canal(objeto: str) -> str:
    o = (objeto or "").lower()
    if any(x in o for x in ["armazém da família","armazem da familia","hortifrut",
                              "credenciamento de agricultor"]): return "ARMAZEM_FAMILIA"
    if "programa de aquisição de alimentos" in o or " paa " in o: return "PAA"
    if "alimentação escolar" in o or "pnae" in o: return "PNAE"
    if "banco de alimentos" in o: return "BANCO_ALIMENTOS"
    return "OUTRO"


# ── PNCP API ──────────────────────────────────────────────────────────────────

def pncp_get(endpoint: str, params: dict = None) -> dict | list | None:
    """Faz GET na API PNCP e retorna JSON. Trata rate limit."""
    url = f"{PNCP_BASE}{endpoint}"
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=20)
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 429:
            print("    [Rate limit] Aguardando 10s...")
            time.sleep(10)
            return pncp_get(endpoint, params)
        elif r.status_code == 404:
            return None
        else:
            print(f"    [HTTP {r.status_code}] {url}")
            return None
    except Exception as e:
        print(f"    [Erro] {e}")
        return None

def buscar_contratacoes_curitiba(data_ini: str, data_fim: str) -> list[dict]:
    """
    Busca todas as contratações do município de Curitiba no período.
    Filtra apenas as relevantes para agricultura familiar.
    """
    contratacoes = []
    pagina = 1
    tamanho = 50

    print(f"  Buscando contratações Curitiba {data_ini} → {data_fim}...")

    while True:
        dados = pncp_get("/contratacoes/publicacao", {
            "dataInicial":    data_ini,
            "dataFinal":      data_fim,
            "codigoMunicipio": COD_CURITIBA,
            "pagina":         pagina,
            "tamanhoPagina":  tamanho,
        })

        if not dados:
            break

        # Estrutura esperada: {"data": [...], "totalRegistros": N, "totalPaginas": N}
        itens = dados if isinstance(dados, list) else dados.get("data", [])
        total_pag = dados.get("totalPaginas", 1) if isinstance(dados, dict) else 1

        for c in itens:
            objeto = c.get("objetoCompra", "") or c.get("objeto", "")
            orgao  = c.get("orgaoEntidade", {}).get("razaoSocial", "") if isinstance(c.get("orgaoEntidade"), dict) else ""
            unidade = c.get("unidadeOrgao", {}).get("nomeUnidade", "") if isinstance(c.get("unidadeOrgao"), dict) else ""

            # Filtrar: SMSAN/FAAC ou relevante para AF
            eh_smsan = any(kw in (orgao + unidade).upper()
                          for kw in ["SMSAN","FAAC","SEGURANÇA ALIMENTAR","ABASTECIMENTO ALIMENTAR"])
            eh_af    = is_relevante_af(objeto)

            if eh_smsan or eh_af:
                contratacoes.append(c)

        print(f"    Página {pagina}/{total_pag} — {len(itens)} contratações ({len(contratacoes)} relevantes até agora)")

        if pagina >= total_pag or not itens:
            break
        pagina += 1
        time.sleep(DELAY)

    return contratacoes

def buscar_itens_contratacao(cnpj: str, ano: int, sequencial: int) -> list[dict]:
    """Busca itens de uma contratação específica."""
    dados = pncp_get(f"/contratacoes/{cnpj}/{ano}/{sequencial}/itens", {
        "pagina": 1, "tamanhoPagina": 500
    })
    if not dados:
        return []
    return dados if isinstance(dados, list) else dados.get("data", [])

def buscar_resultado_contratacao(cnpj: str, ano: int, sequencial: int) -> list[dict]:
    """Busca resultado/fornecedores de uma contratação."""
    dados = pncp_get(f"/contratacoes/{cnpj}/{ano}/{sequencial}/resultado")
    if not dados:
        return []
    return dados if isinstance(dados, list) else dados.get("data", [])


# ── Mapeamento PNCP → Supabase ────────────────────────────────────────────────

def mapear_licitacao(c: dict) -> dict:
    """Converte contratação PNCP para estrutura da tabela licitacoes."""
    orgao_ent  = c.get("orgaoEntidade", {}) or {}
    unidade    = c.get("unidadeOrgao", {}) or {}
    objeto     = c.get("objetoCompra", "") or c.get("objeto", "")
    modalidade = c.get("modalidadeNome", "") or ""
    tipo_map   = {
        "Pregão Eletrônico": "PE", "Pregão Presencial": "PE",
        "Dispensa": "DS", "Dispensa Eletrônica": "DE",
        "Credenciamento": "CR", "Concorrência": "CO",
        "Inexigibilidade": "IN", "Tomada de Preço": "TP",
    }
    tipo = "OUTRO"
    for k, v in tipo_map.items():
        if k.lower() in modalidade.lower():
            tipo = v
            break

    dt_str = c.get("dataPublicacaoPncp") or c.get("dataAberturaProposta") or ""
    try:
        dt = datetime.fromisoformat(dt_str[:10]).strftime("%Y-%m-%d")
    except:
        dt = None

    # Número de controle PNCP: CNPJ-ANO-SEQUENCIAL
    cnpj_num = re.sub(r"[^\d]", "", orgao_ent.get("cnpj", ""))
    ano      = c.get("anoCompra") or c.get("ano") or 0
    seq      = c.get("sequencialCompra") or c.get("sequencial") or 0
    processo = f"PNCP-{cnpj_num}-{ano}-{seq:06d}"

    return {
        "processo":                    processo,
        "tipo_processo":               tipo,
        "nr_edital":                   str(seq),
        "orgao":                       "SMSAN/FAAC",
        "empresa":                     orgao_ent.get("razaoSocial", ""),
        "setor":                       unidade.get("nomeUnidade", ""),
        "objeto":                      objeto,
        "dt_abertura":                 dt,
        "situacao":                    c.get("situacaoCompraLicitacaoNome", ""),
        "canal":                       classificar_canal(objeto),
        "relevante_af":                is_relevante_af(objeto),
        "total_forn_retiraram_edital": 0,
        "total_forn_participantes":    c.get("quantidadeItens", 0),
        # Guarda metadados PNCP para buscar itens depois
        "_cnpj":    cnpj_num,
        "_ano":     ano,
        "_seq":     seq,
    }

def mapear_item(item: dict, lic_id: int, seq_local: int) -> dict:
    """Converte item PNCP para estrutura da tabela itens_licitacao."""
    desc    = item.get("descricao", "") or item.get("descricaoItem", "")
    cultura = norm_cultura(desc)
    return {
        "licitacao_id":  lic_id,
        "seq":           item.get("numeroItem", seq_local),
        "codigo":        str(item.get("codigoCatalogo", "") or item.get("codigoItem", "")),
        "descricao":     desc,
        "qt_solicitada": float(item.get("quantidadeItem", 0) or 0),
        "unidade_medida": item.get("unidadeMedida", "UNIDADE"),
        "valor_unitario": float(item.get("valorUnitarioEstimado", 0) or 0),
        "valor_total":    float(item.get("valorTotal", 0) or 0),
        "cultura":        cultura,
        "categoria":      categ(cultura),
    }


# ── Gravação Supabase ─────────────────────────────────────────────────────────

def upsert_licitacao(sb: Client, data: dict) -> int | None:
    # Remover campos internos antes de gravar
    row = {k: v for k, v in data.items() if not k.startswith("_")}
    try:
        r = sb.table("licitacoes").upsert(
            row, on_conflict="processo,orgao").execute()
        if r.data: return r.data[0]["id"]
        r2 = sb.table("licitacoes").select("id").eq(
            "processo", row["processo"]).eq("orgao", "SMSAN/FAAC").execute()
        return r2.data[0]["id"] if r2.data else None
    except Exception as e:
        print(f"      [!] licitacao: {e}")
        return None

def upsert_item(sb: Client, item: dict):
    try:
        sb.table("itens_licitacao").upsert(
            item, on_conflict="licitacao_id,seq").execute()
    except Exception as e:
        print(f"      [!] item seq={item.get('seq')}: {e}")

def upsert_fornecedor(sb: Client, cnpj: str, razao: str) -> int | None:
    if not cnpj or not razao: return None
    try:
        r = sb.table("fornecedores").upsert(
            {"cpf_cnpj": cnpj, "razao_social": razao, "tipo": tipo_forn(razao)},
            on_conflict="cpf_cnpj").execute()
        if r.data: return r.data[0]["id"]
        r2 = sb.table("fornecedores").select("id").eq("cpf_cnpj", cnpj).execute()
        return r2.data[0]["id"] if r2.data else None
    except: return None

def upsert_participacao(sb: Client, lic_id: int, forn_id: int):
    try:
        sb.table("participacoes").upsert(
            {"licitacao_id": lic_id, "fornecedor_id": forn_id, "participou": True},
            on_conflict="licitacao_id,fornecedor_id").execute()
    except: pass


# ── Fluxo principal ───────────────────────────────────────────────────────────

def main():
    sb = get_supabase()
    print(f"Supabase: {SUPABASE_URL}")
    print(f"Período PNCP: {DATA_INICIO} → {DATA_FIM}\n")

    # 1. Buscar contratações
    contratacoes = buscar_contratacoes_curitiba(DATA_INICIO, DATA_FIM)
    print(f"\nTotal relevante: {len(contratacoes)} contratações\n")

    if not contratacoes:
        print("Nenhuma contratação encontrada. Verifique os parâmetros.")
        # Salvar exemplo da resposta para debug
        print("\nTestando endpoint diretamente...")
        teste = pncp_get("/contratacoes/publicacao", {
            "dataInicial": DATA_INICIO, "dataFinal": DATA_FIM,
            "codigoMunicipio": COD_CURITIBA, "pagina": 1, "tamanhoPagina": 3,
        })
        print(json.dumps(teste, indent=2, ensure_ascii=False)[:3000] if teste else "Sem resposta")
        return

    # 2. Para cada contratação, buscar itens e fornecedores
    total_lic = total_itens = total_forns = 0

    for i, c in enumerate(contratacoes, 1):
        mapeado = mapear_licitacao(c)
        objeto  = mapeado.get("objeto", "")
        cnpj    = mapeado.pop("_cnpj", "")
        ano     = mapeado.pop("_ano", 0)
        seq     = mapeado.pop("_seq", 0)

        lic_id = upsert_licitacao(sb, mapeado)
        if not lic_id:
            continue
        total_lic += 1

        # Buscar itens
        itens_pncp = buscar_itens_contratacao(cnpj, ano, seq)
        for j, item in enumerate(itens_pncp, 1):
            row = mapear_item(item, lic_id, j)
            upsert_item(sb, row)
            total_itens += 1
        time.sleep(DELAY)

        # Buscar fornecedores/resultado
        resultado = buscar_resultado_contratacao(cnpj, ano, seq)
        n_forns = 0
        for res in resultado:
            # Estrutura pode variar — tentar extrair CNPJ e nome
            forn = res.get("fornecedor", res)
            cnpj_f = re.sub(r"[^\d]", "", forn.get("cnpj", "") or forn.get("cpfCnpj", ""))
            nome_f = forn.get("razaoSocial", "") or forn.get("nome", "")
            if cnpj_f and nome_f:
                fid = upsert_fornecedor(sb, cnpj_f, nome_f)
                if fid:
                    upsert_participacao(sb, lic_id, fid)
                    n_forns += 1
                    total_forns += 1
        time.sleep(DELAY)

        af = " [AF]" if mapeado.get("relevante_af") else ""
        print(f"  [{i:3d}/{len(contratacoes)}] {mapeado['processo']}{af}"
              f" | itens:{len(itens_pncp)} | forn:{n_forns}")
        print(f"    {objeto[:80]}")

    print(f"\n{'='*60}")
    print(f"PNCP concluído!")
    print(f"  Licitações: {total_lic}")
    print(f"  Itens:      {total_itens}")
    print(f"  Fornecedores: {total_forns}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
