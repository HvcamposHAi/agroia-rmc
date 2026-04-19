"""
AgroIA-RMC — Etapa 2 CORRIGIDA: coleta detalhes
===============================================
Versão híbrida:
- Usa requests (como Etapa 1) para listar processos — funciona!
- Usa Playwright apenas para coletar detalhes de cada processo

Execute: python etapa2_corrigido.py
"""
import os, re, asyncio, math, time
from datetime import datetime
from dotenv import load_dotenv
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings, requests
from supabase import create_client
from playwright.async_api import async_playwright

warnings.filterwarnings('ignore', category=XMLParsedAsHTMLWarning)
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
FORM_URL  = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
ORGAO     = "SMSAN/FAAC"
DT_INICIO = "01/01/2019"
DT_FIM    = "31/12/2025"
DELAY     = 1.5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Referer": FORM_URL,
}

# ── Funções auxiliares (mesmas do original) ───────────────────────────────────

def parse_val(t):
    try: return float((t or "0").strip().replace(".","").replace(",","."))
    except: return 0.0

def norm_cultura(d):
    mapa = {"banana":"banana","laranja":"laranja","maçã":"maca","mamão":"mamao",
            "melancia":"melancia","uva":"uva","morango":"morango","tomate":"tomate",
            "cebola":"cebola","cenoura":"cenoura","batata":"batata","aipim":"aipim",
            "mandioca":"aipim","alface":"alface","couve":"couve","repolho":"repolho",
            "brócolis":"brocolis","alho":"alho","beterraba":"beterraba",
            "pimentão":"pimentao","abobrinha":"abobrinha","chuchu":"chuchu",
            "arroz":"arroz","feijão":"feijao","milho":"milho","queijo":"queijo",
            "leite":"leite","ovos":"ovos","frango":"frango","carne":"carne",
            "pão":"pao","mel":"mel","inhame":"inhame","abacaxi":"abacaxi",
            "goiaba":"goiaba","limão":"limao","kiwi":"kiwi"}
    d = (d or "").lower().strip()
    for k, v in mapa.items():
        if k in d: return v
    return d

def categ(c):
    if c in {"abacaxi","banana","goiaba","laranja","limao","maca","mamao",
             "melancia","uva","morango","kiwi"}: return "FRUTA"
    if c in {"tomate","cebola","cenoura","batata","aipim","alho","beterraba",
             "pimentao","abobrinha","chuchu","milho","inhame"}: return "LEGUME"
    if c in {"alface","couve","repolho","brocolis"}: return "FOLHOSA"
    if c in {"queijo","leite"}: return "LATICINIOS"
    if c in {"frango","carne","ovos"}: return "PROTEINA"
    if c in {"arroz","feijao","mel","pao"}: return "GRAOS"
    return "OUTRO"

def tipo_forn(r):
    r = (r or "").upper()
    if "COOPERATIV" in r: return "COOPERATIVA"
    if "ASSOCIA" in r:    return "ASSOCIACAO"
    return "EMPRESA"

def extrair_tudo(html):
    soup = BeautifulSoup(html, "lxml")
    itens, forns, emps = [], [], []
    for t in soup.find_all("table"):
        ths = [th.get_text(strip=True).lower() for th in t.find_all("th")]
        if any(h in ths for h in ["seq", "código", "codigo"]):
            for i, tr in enumerate(t.find_all("tr")[1:]):
                cols = tr.find_all("td")
                if len(cols) < 3: continue
                desc = cols[2].get_text(strip=True) if len(cols) > 2 else ""
                seq  = cols[0].get_text(strip=True)
                itens.append({
                    "seq":            int(seq) if seq.isdigit() else i+1,
                    "codigo":         cols[1].get_text(strip=True) if len(cols) > 1 else "",
                    "descricao":      desc,
                    "qt_solicitada":  parse_val(cols[3].get_text(strip=True)) if len(cols) > 3 else 0,
                    "unidade_medida": cols[4].get_text(strip=True) if len(cols) > 4 else "",
                    "valor_unitario": parse_val(cols[5].get_text(strip=True)) if len(cols) > 5 else 0,
                    "valor_total":    parse_val(cols[6].get_text(strip=True)) if len(cols) > 6 else 0,
                    "cultura":        norm_cultura(desc),
                    "categoria":      categ(norm_cultura(desc)),
                })
        elif any(h in ths for h in ["cpf/cnpj", "cnpj", "razão social", "razao social"]):
            for tr in t.find_all("tr")[1:]:
                cols = tr.find_all("td")
                if len(cols) < 2: continue
                cpf   = cols[0].get_text(strip=True)
                razao = cols[1].get_text(strip=True)
                if len(re.sub(r"[^\d]", "", cpf)) >= 11 and razao:
                    forns.append({"cpf_cnpj": cpf.strip(), "razao_social": razao.strip()})
        elif "data empenho" in " ".join(ths) or "dt. empenho" in " ".join(ths):
            for tr in t.find_all("tr")[1:]:
                cols = tr.find_all("td")
                if len(cols) < 2: continue
                nr = cols[0].get_text(strip=True)
                if nr and nr != "null":
                    ano  = cols[1].get_text(strip=True) if len(cols) > 1 else ""
                    data = cols[2].get_text(strip=True) if len(cols) > 2 else ""
                    try:    dt = datetime.strptime(data, "%d/%m/%Y").strftime("%Y-%m-%d")
                    except: dt = None
                    emps.append({"nr_empenho": nr,
                                 "ano": int(ano) if ano.isdigit() else None,
                                 "dt_empenho": dt})
    return itens, forns, emps

def gravar(sb, lic_id, itens, forns, emps):
    n_i = n_f = 0
    for item in itens:
        item["licitacao_id"] = lic_id
        try:
            sb.table("itens_licitacao").upsert(
                item, on_conflict="licitacao_id,seq").execute()
            n_i += 1
        except: pass
    for forn in forns:
        try:
            r = sb.table("fornecedores").upsert(
                {"cpf_cnpj": forn["cpf_cnpj"], "razao_social": forn["razao_social"],
                 "tipo": tipo_forn(forn["razao_social"])},
                on_conflict="cpf_cnpj").execute()
            fid = r.data[0]["id"] if r.data else None
            if not fid:
                r2 = sb.table("fornecedores").select("id").eq(
                    "cpf_cnpj", forn["cpf_cnpj"]).execute()
                fid = r2.data[0]["id"] if r2.data else None
            if fid:
                sb.table("participacoes").upsert(
                    {"licitacao_id": lic_id, "fornecedor_id": fid, "participou": True},
                    on_conflict="licitacao_id,fornecedor_id").execute()
                n_f += 1
        except: pass
    if emps and itens:
        try:
            r = sb.table("itens_licitacao").select("id").eq(
                "licitacao_id", lic_id).limit(1).execute()
            if r.data:
                for emp in emps:
                    emp["item_id"] = r.data[0]["id"]
                    sb.table("empenhos").insert(emp).execute()
        except: pass
    return n_i, n_f


# ── Funções da Etapa 1 (requests) para listagem ───────────────────────────────

def get_vs(html):
    m = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', html)
    return m.group(1) if m else ""

def extrair_processos_pagina(html):
    """Extrai processos da página atual (lista)."""
    soup = BeautifulSoup(html, "lxml")
    procs = []
    for t in soup.find_all("table"):
        ths = [th.get_text(strip=True).lower() for th in t.find_all("th")]
        if "processo" in ths and "objeto" in ths:
            for tr in t.find_all("tr")[1:]:
                cols = tr.find_all("td")
                if not cols: continue
                proc = cols[0].get_text(strip=True)
                if re.match(r"^[A-Z]{2}\s+\d+/\d{4}", proc):
                    # Extrair também o link_id e id interno do onclick
                    link = cols[0].find("a")
                    if link:
                        link_id = link.get("id", "")
                        onclick = link.get("onclick", "")
                        m_id = re.search(r"'id'\s*:\s*(\d+)", onclick)
                        m_sit = re.search(r"'situacao'\s*:\s*'([^']+)'", onclick)
                        procs.append({
                            "processo": proc,
                            "link_id": link_id,
                            "id_interno": int(m_id.group(1)) if m_id else 0,
                            "situacao": m_sit.group(1) if m_sit else "",
                        })
            break
    return procs

def listar_todos_processos():
    """
    Usa requests (como Etapa 1) para listar TODOS os processos.
    Retorna lista de dicts com processo, link_id, id_interno, situacao.
    """
    print("[1] Listando processos via requests...")
    session = requests.Session()
    session.headers.update(HEADERS)
    
    # GET inicial
    r1 = session.get(FORM_URL, timeout=30)
    vs = get_vs(r1.text)
    
    # Pesquisa
    payload = {
        "AJAXREQUEST": "_viewRoot",
        "form:tabs": "abaPesquisa",
        "form:j_id6": "-1",
        "form:j_id9": ORGAO,
        "form:j_id12": "-1",
        "form:j_id15": "",
        "form:dataInferiorInputDate": DT_INICIO,
        "form:dataInferiorInputCurrentDate": "03/2026",
        "form:j_id18InputDate": DT_FIM,
        "form:j_id18InputCurrentDate": "03/2026",
        "form:fornecedoresEditalOpenedState": "",
        "form:fornecedoresParticipantesOpenedState": "",
        "form:observacoesItemOpenedState": "",
        "form:j_id253": "",
        "form:messagesOpenedState": "",
        "form:waitOpenedState": "",
        "form:empenhosProcCompraOpenedState": "",
        "form:documentosOpenedState": "",
        "form": "form",
        "autoScroll": "",
        "javax.faces.ViewState": vs,
        "form:btSearch": "Pesquisar",
        "ajaxSource": "form:btSearch",
    }
    
    r2 = session.post(FORM_URL, data=payload, timeout=30)
    vs = get_vs(r2.text) or vs
    
    # Total de registros
    m = re.search(r"quantidade registros.*?(\d+)", r2.text, re.I | re.DOTALL)
    total = int(m.group(1)) if m else 0
    total_pags = math.ceil(total / 20) if total else 1
    print(f"    {total} registros | {total_pags} páginas")
    
    # Coletar todas as páginas
    todos = []
    for pag in range(1, total_pags + 1):
        if pag > 1:
            # Navegar para página
            payload_pag = {
                "AJAXREQUEST": "_viewRoot",
                "form:tabs": "abaPesquisa",
                "form:j_id6": "-1",
                "form:j_id9": ORGAO,
                "form:j_id12": "-1",
                "form:j_id15": "",
                "form:dataInferiorInputDate": DT_INICIO,
                "form:dataInferiorInputCurrentDate": "03/2026",
                "form:j_id18InputDate": DT_FIM,
                "form:j_id18InputCurrentDate": "03/2026",
                "form:fornecedoresEditalOpenedState": "",
                "form:fornecedoresParticipantesOpenedState": "",
                "form:observacoesItemOpenedState": "",
                "form:j_id253": "",
                "form:messagesOpenedState": "",
                "form:waitOpenedState": "",
                "form:empenhosProcCompraOpenedState": "",
                "form:documentosOpenedState": "",
                "form": "form",
                "autoScroll": "",
                "javax.faces.ViewState": vs,
                "ajaxSingle": "form:tabelaScroller",
                "form:tabelaScroller": str(pag),
            }
            r = session.post(FORM_URL, data=payload_pag, timeout=30)
            vs = get_vs(r.text) or vs
            html = r.text
        else:
            html = r2.text
        
        procs = extrair_processos_pagina(html)
        todos.extend(procs)
        
        if pag % 10 == 0:
            print(f"    Página {pag}/{total_pags}... ({len(todos)} processos)")
        
        time.sleep(0.5)
    
    print(f"    Total: {len(todos)} processos extraídos\n")
    return todos


# ── Fluxo principal ───────────────────────────────────────────────────────────

async def main():
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Carregar mapa do banco
    print("[0] Carregando licitações do Supabase...")
    dados = sb.table("licitacoes").select("id,processo").eq("orgao", ORGAO).execute().data
    mapa = {d["processo"]: d["id"] for d in dados}
    
    # Verificar quais já têm itens
    r = sb.table("itens_licitacao").select("licitacao_id").execute()
    coletados = {row["licitacao_id"] for row in r.data}
    print(f"    {len(mapa)} no banco | {len(coletados)} coletados\n")

    # Listar TODOS os processos do portal via requests
    processos_portal = listar_todos_processos()
    
    # Filtrar pendentes
    pendentes = []
    for p in processos_portal:
        proc = p["processo"]
        lic_id = mapa.get(proc)
        if lic_id and lic_id not in coletados:
            p["lic_id"] = lic_id
            pendentes.append(p)
    
    print(f"[2] Pendentes para coletar: {len(pendentes)}\n")
    
    if not pendentes:
        print("Nada a coletar!")
        return

    # Coletar detalhes via Playwright
    total_itens = total_forns = total_erros = processados = 0
    
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False, slow_mo=300)
        page = await browser.new_page()
        
        print("[3] Abrindo portal no Playwright...")
        await page.goto(FORM_URL, timeout=30000)
        await page.wait_for_selector("select[name='form:j_id9']", timeout=15000)
        await asyncio.sleep(1.5)
        
        # Fazer a pesquisa inicial
        await page.select_option("select[name='form:j_id9']", value=ORGAO)
        await asyncio.sleep(0.5)
        
        await page.locator("#form\\:dataInferiorInputDate").click()
        await page.keyboard.press("Control+a")
        await page.keyboard.type(DT_INICIO)
        
        await page.locator("#form\\:j_id18InputDate").click()
        await page.keyboard.press("Control+a")
        await page.keyboard.type(DT_FIM)
        
        await page.click("#form\\:btSearch")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)
        
        print(f"\n[4] Coletando detalhes de {len(pendentes)} processos...\n")
        
        for p in pendentes:
            proc = p["processo"]
            lic_id = p["lic_id"]
            
            try:
                # Navegar para a página onde está o processo
                # Primeiro, pesquisar especificamente por ele
                # (ou usar o link_id capturado)
                
                # Tentar clicar no link do processo
                link = page.locator(f"a:text-is('{proc}')")
                if await link.count() == 0:
                    # Processo não está na página atual - pular por enquanto
                    # (implementar navegação de páginas depois)
                    continue
                
                await link.click()
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(1.5)
                
                # Coletar HTML do detalhe
                html_det = await page.content()
                itens, forns, emps = extrair_tudo(html_det)
                n_i, n_f = gravar(sb, lic_id, itens, forns, emps)
                coletados.add(lic_id)
                total_itens += n_i
                total_forns += n_f
                processados += 1
                
                print(f"  [{processados}] {proc} | itens:{n_i} | forn:{n_f}")
                
                # Voltar para lista
                await page.click("a:has-text('Lista Licitações')")
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(1)
                
            except Exception as e:
                total_erros += 1
                print(f"  ERRO {proc}: {str(e)[:60]}")
        
        await browser.close()

    print(f"\n{'='*55}")
    print(f"Concluído!")
    print(f"  Processados:  {processados}")
    print(f"  Itens:        {total_itens}")
    print(f"  Fornecedores: {total_forns}")
    print(f"  Erros:        {total_erros}")
    print(f"{'='*55}")

if __name__ == "__main__":
    asyncio.run(main())
