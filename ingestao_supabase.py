"""
AgroIA-RMC — Ingestão via requests (sem Playwright)
====================================================
Mestrando: Humberto Vinicius Aparecido de Campos — PPGCA/UEPG

Payload confirmado via DevTools:
  AJAXREQUEST          = _viewRoot
  form:tabs            = abaPesquisa
  form:j_id6           = -1   (modalidade = todas)
  form:j_id9           = SMSAN/FAAC
  form:j_id12          = -1   (situação = todas)
  form:j_id15          = (vazio)
  form:dataInferiorInputDate        = 01/01/2019
  form:dataInferiorInputCurrentDate = 03/2026
  form:j_id18InputDate              = 31/12/2025
  form:j_id18InputCurrentDate       = 03/2026
  form                 = form
  autoScroll           = (vazio)
  javax.faces.ViewState = (obtido dinamicamente via GET)

Instale: pip install requests beautifulsoup4 lxml supabase python-dotenv
"""

import os, re, math, time
from datetime import datetime
from dotenv import load_dotenv
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings
warnings.filterwarnings('ignore', category=XMLParsedAsHTMLWarning)
import requests
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://rsphlvcekuomvpvjqxqm.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

BASE_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes"
FORM_URL = f"{BASE_URL}/pages/consulta/consultaProcessoDetalhada.jsf"

ORGAO     = "SMSAN/FAAC"
DT_INICIO = "01/01/2019"
DT_FIM    = "31/12/2025"
REGS_POR_PAGINA = 5
DELAY = 1.0   # segundos entre requisições

HEADERS = {
    "User-Agent":   "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept":       "text/html,application/xhtml+xml,*/*",
    "Referer":      FORM_URL,
}

def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# ── Classificadores ───────────────────────────────────────────────────────────

def classificar_tipo(p):
    for s in ["CR","AD","PE","DS","DE","DT","DM","CH","CP","IN","FN","PP","PL","RE","RD","SG","TP","LE","PQ","CO","CN","CE"]:
        if p.upper().startswith(s): return s
    return "OUTRO"

def classificar_canal(o):
    o = (o or "").lower()
    if any(x in o for x in ["armazém da família","armazem da familia","hortifrutigranjeiro","hortifruti","credenciamento de agricultor"]): return "ARMAZEM_FAMILIA"
    if "programa de aquisição de alimentos" in o or " paa " in o: return "PAA"
    if "alimentação escolar" in o or "pnae" in o or "merenda" in o: return "PNAE"
    if "banco de alimentos" in o: return "BANCO_ALIMENTOS"
    if "mesa solidária" in o or "mesa solidaria" in o: return "MESA_SOLIDARIA"
    return "OUTRO"

def is_af(o):
    return any(p in (o or "").lower() for p in ["agricultura familiar","hortifrutigranjeiro","hortifruti","armazém da família","armazem da familia","credenciamento de agricultor","paa","programa de aquisição","olericultura","orgânico","organico","cooperativa","associação de produtores"])

def tipo_forn(r):
    r = (r or "").upper()
    if "COOPERATIV" in r: return "COOPERATIVA"
    if "ASSOCIA" in r: return "ASSOCIACAO"
    if any(x in r for x in ["LTDA","S.A","EIRELI"," ME "," EPP "]): return "EMPRESA"
    return "PESSOA_FISICA"

def norm_cultura(d):
    mapa = {"abacaxi":"abacaxi","banana":"banana","goiaba":"goiaba","kiwi":"kiwi","laranja":"laranja","limão":"limao","limao":"limao","maçã":"maca","maca":"maca","mamão":"mamao","mamao":"mamao","melancia":"melancia","melão":"melao","uva":"uva","morango":"morango","tomate":"tomate","cebola":"cebola","cenoura":"cenoura","batata":"batata","aipim":"aipim","mandioca":"aipim","alface":"alface","couve":"couve","repolho":"repolho","brócolis":"brocolis","brocolis":"brocolis","alho":"alho","beterraba":"beterraba","arroz":"arroz","feijão":"feijao","feijao":"feijao","milho":"milho","farinha":"farinha","café":"cafe"}
    d = (d or "").lower().strip().rstrip(",.")
    for k,v in mapa.items():
        if k in d: return v
    return d

def categ(c):
    if c in {"abacaxi","banana","goiaba","kiwi","laranja","limao","maca","mamao","melancia","melao","uva","morango"}: return "FRUTA"
    if c in {"tomate","cebola","cenoura","batata","aipim","alho","beterraba","pimentao","milho"}: return "LEGUME"
    if c in {"alface","couve","repolho","brocolis"}: return "FOLHOSA"
    if c in {"arroz","feijao","farinha","cafe"}: return "GRAOS"
    return "OUTRO"

def parse_data(t):
    try: return datetime.strptime((t or "").strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except: return None

def parse_val(t):
    try: return float((t or "0").strip().replace(".","").replace(",","."))
    except: return 0.0

# ── Sessão HTTP ───────────────────────────────────────────────────────────────

def criar_sessao():
    s = requests.Session()
    s.headers.update(HEADERS)
    return s

def obter_viewstate(session, html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    tag = soup.find("input", {"name": "javax.faces.ViewState"})
    return tag["value"] if tag else ""

def get_data_atual():
    """Retorna mês/ano atual no formato MM/YYYY para os campos CurrentDate."""
    now = datetime.now()
    return f"{now.month:02d}/{now.year}"

# ── Requisições ───────────────────────────────────────────────────────────────

def post_pesquisa(session, viewstate: str, pagina: int = 1) -> str:
    """
    Envia o POST de pesquisa.
    Para paginação, usa o parâmetro form:j_id253 com o número da página.
    """
    data_atual = get_data_atual()

    payload = {
        "AJAXREQUEST":                        "_viewRoot",
        "form:tabs":                          "abaPesquisa",
        "form:j_id6":                         "-1",
        "form:j_id9":                         ORGAO,
        "form:j_id12":                        "-1",
        "form:j_id15":                        "",
        "form:dataInferiorInputDate":         DT_INICIO,
        "form:dataInferiorInputCurrentDate":  data_atual,
        "form:j_id18InputDate":               DT_FIM,
        "form:j_id18InputCurrentDate":        data_atual,
        "form:fornecedoresEditalOpenedState": "",
        "form:fornecedoresParticipantesOpenedState": "",
        "form:observacoesItemOpenedState":    "",
        "form:j_id253":                       "",
        "form:messagesOpenedState":           "",
        "form:waitOpenedState":               "",
        "form:empenhosProcCompraOpenedState": "",
        "form:documentosOpenedState":         "",
        "form":                               "form",
        "autoScroll":                         "",
        "javax.faces.ViewState":              viewstate,
        # Parâmetro obrigatório: ID do botão que disparou a action
        "form:btSearch":                      "Pesquisar",
        # Parâmetro Ajax4jsf: componente a ser re-renderizado
        "ajaxSource":                         "form:btSearch",
    }

    # Para páginas > 1: RichFaces DataScroller
    # Payload confirmado via Playwright interceptor:
    #   ajaxSingle            = form:tabela:j_id52
    #   form:tabela:j_id52    = <numero_pagina>
    #   AJAX:EVENTS_COUNT     = 1
    if pagina > 1:
        del payload["form:btSearch"]
        del payload["ajaxSource"]
        payload["ajaxSingle"]         = "form:tabela:j_id52"
        payload["form:tabela:j_id52"] = str(pagina)
        payload["AJAX:EVENTS_COUNT"]  = "1"
    resp = session.post(FORM_URL, data=payload, timeout=30)
    return resp.text

def clicar_processo(session, viewstate: str, id_processo: str) -> str:
    """Abre o detalhe de um processo pelo seu link."""
    payload = {
        "AJAXREQUEST":           "_viewRoot",
        "form:tabs":             "abaPesquisa",
        "form":                  "form",
        "autoScroll":            "",
        id_processo:             id_processo,
        "javax.faces.ViewState": viewstate,
    }
    resp = session.post(FORM_URL, data=payload, timeout=30)
    return resp.text

# ── Extração HTML ─────────────────────────────────────────────────────────────

def extrair_total(html: str) -> int:
    # Busca no HTML bruto — número está dentro de tag <label> após 'quantidade registros'
    # Estrutura real: quantidade registros:</label></td><td><label>1238</label>
    m = re.search(r"quantidade registros.*?(\d+)</label>", html, re.I | re.DOTALL)
    if m:
        return int(m.group(1))
    # Fallback: buscar no texto plano (sem tags)
    texto = BeautifulSoup(html, "lxml").get_text()
    m2 = re.search(r"quantidade registros[\s:]*?(\d+)", texto, re.I)
    return int(m2.group(1)) if m2 else 0

def extrair_lista(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    regs = []
    for t in soup.find_all("table"):
        ths = [th.get_text(strip=True).lower() for th in t.find_all("th")]
        if "processo" in ths and "objeto" in ths:
            for tr in t.find_all("tr")[1:]:
                cols = tr.find_all("td")
                if len(cols) < 3: continue
                proc = cols[0].get_text(strip=True)
                if not re.match(r"^[A-Z]{2}\s+\d+/\d{4}", proc): continue
                link = cols[0].find("a")
                # ID do link JSF para abrir detalhe
                link_id = ""
                if link:
                    link_id = link.get("id","") or link.get("onclick","")
                regs.append({
                    "processo":    proc,
                    "objeto":      cols[1].get_text(strip=True),
                    "dt_abertura": cols[2].get_text(strip=True),
                    "situacao":    cols[3].get_text(strip=True) if len(cols) > 3 else "",
                    "link_id":     link_id,
                })
            break
    return regs

def extrair_detalhe(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    d = {"itens": [], "fornecedores": []}
    texto = soup.get_text(" ", strip=True)
    for campo, pat in [("total_forn_retiraram", r"Retiraram o Edital[:\s]+(\d+)"),
                        ("total_forn_participantes", r"Fornecedores Participantes[:\s]+(\d+)")]:
        m = re.search(pat, texto, re.I)
        d[campo] = int(m.group(1)) if m else 0
    for t in soup.find_all("table"):
        ths = [th.get_text(strip=True).lower() for th in t.find_all("th")]
        if any(h in ths for h in ["seq","código","codigo"]):
            for i, tr in enumerate(t.find_all("tr")[1:]):
                cols = tr.find_all("td")
                if len(cols) < 3: continue
                desc = cols[2].get_text(strip=True) if len(cols) > 2 else ""
                c    = norm_cultura(desc)
                seq  = cols[0].get_text(strip=True)
                d["itens"].append({
                    "seq":            int(seq) if seq.isdigit() else i+1,
                    "codigo":         cols[1].get_text(strip=True) if len(cols) > 1 else "",
                    "descricao":      desc,
                    "qt_solicitada":  parse_val(cols[3].get_text(strip=True)) if len(cols) > 3 else 0,
                    "unidade_medida": cols[4].get_text(strip=True) if len(cols) > 4 else "KILOGRAMA",
                    "valor_unitario": parse_val(cols[5].get_text(strip=True)) if len(cols) > 5 else 0,
                    "valor_total":    parse_val(cols[6].get_text(strip=True)) if len(cols) > 6 else 0,
                    "cultura":        c,
                    "categoria":      categ(c),
                })
            break
    return d

# ── Gravação Supabase ─────────────────────────────────────────────────────────

def upsert_licitacao(sb, reg, det):
    obj  = reg.get("objeto","")
    tipo = classificar_tipo(reg["processo"])
    data = {
        "processo":                    reg["processo"],
        "tipo_processo":               tipo,
        "orgao":                       ORGAO,
        "objeto":                      obj,
        "empresa":                     "Fundo de Abastecimento Alimentar de Curitiba",
        "dt_abertura":                 parse_data(reg.get("dt_abertura","")),
        "situacao":                    reg.get("situacao",""),
        "total_forn_retiraram_edital": det.get("total_forn_retiraram",0),
        "total_forn_participantes":    det.get("total_forn_participantes",0),
        "canal":                       classificar_canal(obj),
        "relevante_af":                is_af(obj),
    }
    try:
        r = sb.table("licitacoes").upsert(data, on_conflict="processo,orgao").execute()
        if r.data: return r.data[0]["id"]
        r2 = sb.table("licitacoes").select("id").eq("processo", reg["processo"]).eq("orgao", ORGAO).execute()
        return r2.data[0]["id"] if r2.data else None
    except Exception as e:
        print(f"\n      [!] licitacao: {e}")
        return None

def gravar_itens(sb, lic_id, itens):
    if not itens: return
    vistos = {}
    for item in itens:
        item["licitacao_id"] = lic_id
        vistos[item["seq"]] = item
    for item in vistos.values():
        try:
            sb.table("itens_licitacao").upsert(item, on_conflict="licitacao_id,seq").execute()
        except Exception as e:
            print(f"\n      [!] item seq={item.get('seq')}: {e}")

# ── Fluxo principal ───────────────────────────────────────────────────────────

def ingerir(max_paginas: int = None):
    sb      = get_supabase()
    session = criar_sessao()
    print(f"Supabase: {SUPABASE_URL}\n")

    # 1. GET inicial para obter ViewState
    print("[1] Obtendo ViewState...")
    resp = session.get(FORM_URL, timeout=30)
    viewstate = obter_viewstate(session, resp.text)
    if not viewstate:
        print("[!] ViewState não encontrado. Abortando.")
        return
    print(f"    ViewState obtido ({len(viewstate)} chars)")

    # 2. POST de pesquisa
    print(f"[2] Pesquisando: {ORGAO} | {DT_INICIO} → {DT_FIM}")
    html = post_pesquisa(session, viewstate, pagina=1)
    viewstate = obter_viewstate(session, html) or viewstate  # atualiza se mudou

    total_reg = extrair_total(html)
    if total_reg == 0:
        # Salvar HTML para debug
        with open("debug_pesquisa.html","w",encoding="utf-8") as f: f.write(html)
        print(f"[!] 0 registros. HTML salvo em debug_pesquisa.html")
        return

    total_pag = math.ceil(total_reg / REGS_POR_PAGINA)
    if max_paginas:
        total_pag = min(total_pag, max_paginas)

    print(f"[3] Total: {total_reg} registros | {total_pag} páginas\n")

    total_gravados = 0

    for pagina_atual in range(1, total_pag + 1):

        if pagina_atual > 1:
            time.sleep(DELAY)
            html = post_pesquisa(session, viewstate, pagina=pagina_atual)
            viewstate = obter_viewstate(session, html) or viewstate

        regs = extrair_lista(html)
        print(f"  Página {pagina_atual}/{total_pag} — {len(regs)} processos", end="")

        gravados_pag = 0
        for reg in regs:
            # Por ora, grava a licitação sem entrar no detalhe
            # (detalhe será implementado em script separado)
            lic_id = upsert_licitacao(sb, reg, {})
            if lic_id:
                total_gravados += 1
                gravados_pag += 1

        print(f" → {gravados_pag} gravados")
        time.sleep(DELAY)

    print(f"\n{'='*55}")
    print(f"Etapa 1 concluída: {total_gravados} licitações gravadas")
    print(f"Próximo: executar etapa2_detalhes.py para popular itens e fornecedores")
    print(f"{'='*55}")


if __name__ == "__main__":
    # Teste com 5 páginas (25 processos)
    # Para ingestão completa: max_paginas=None
    ingerir(max_paginas=None)
