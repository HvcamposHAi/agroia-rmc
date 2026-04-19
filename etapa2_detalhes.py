"""
AgroIA-RMC — Etapa 2: Detalhes dos processos → Supabase (v3 - Playwright)
=========================================================================
Usa Playwright headless para capturar HTML completo do detalhe
(requests puro retorna HTML parcial sem o conteúdo renderizado pelo JS).

Execute: python etapa2_detalhes.py
"""

import os, re, asyncio, math
from datetime import datetime
from dotenv import load_dotenv
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings
from supabase import create_client, Client
from playwright.async_api import async_playwright

warnings.filterwarnings('ignore', category=XMLParsedAsHTMLWarning)
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://rsphlvcekuomvpvjqxqm.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

FORM_URL  = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
ORGAO     = "SMSAN/FAAC"
DT_INICIO = "01/01/2019"
DT_FIM    = "31/12/2025"
DELAY     = 1.0
TIPOS_COM_DETALHE = {"CR", "AD", "PE", "DS", "DE", "DT", "CH", "CP"}

# ── Utilitários ───────────────────────────────────────────────────────────────

def get_supabase(): return create_client(SUPABASE_URL, SUPABASE_KEY)

def parse_val(t):
    try: return float((t or "0").strip().replace(".","").replace(",","."))
    except: return 0.0

def norm_cultura(d):
    mapa = {"abacaxi":"abacaxi","banana":"banana","goiaba":"goiaba","kiwi":"kiwi",
            "laranja":"laranja","limão":"limao","limao":"limao","maçã":"maca",
            "mamão":"mamao","mamao":"mamao","melancia":"melancia","melão":"melao",
            "uva":"uva","morango":"morango","tomate":"tomate","cebola":"cebola",
            "cenoura":"cenoura","batata":"batata","aipim":"aipim","mandioca":"aipim",
            "alface":"alface","couve":"couve","repolho":"repolho",
            "brócolis":"brocolis","brocolis":"brocolis","alho":"alho",
            "beterraba":"beterraba","pimentão":"pimentao","abobrinha":"abobrinha",
            "chuchu":"chuchu","vagem":"vagem","arroz":"arroz",
            "feijão":"feijao","feijao":"feijao","milho":"milho","farinha":"farinha",
            "queijo":"queijo","leite":"leite","ovos":"ovos","frango":"frango",
            "carne":"carne","pão":"pao","pao":"pao","mel":"mel",
            "inhame":"inhame","gengibre":"gengibre","rabanete":"rabanete",
            "moranga":"moranga","abobora":"abobora","abóbora":"abobora"}
    d = (d or "").lower().strip().rstrip(",.")
    for k,v in mapa.items():
        if k in d: return v
    return d

def categ(c):
    if c in {"abacaxi","banana","goiaba","kiwi","laranja","limao","maca",
             "mamao","melancia","melao","uva","morango"}: return "FRUTA"
    if c in {"tomate","cebola","cenoura","batata","aipim","alho","beterraba",
             "pimentao","abobrinha","chuchu","vagem","milho","inhame",
             "gengibre","rabanete","moranga","abobora"}: return "LEGUME"
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

def get_data():
    n = datetime.now()
    return f"{n.month:02d}/{n.year}"

# ── Extração de HTML ──────────────────────────────────────────────────────────

def extrair_itens(html):
    soup  = BeautifulSoup(html, "lxml")
    itens = []
    for t in soup.find_all("table"):
        ths = [th.get_text(strip=True).lower() for th in t.find_all("th")]
        if any(h in ths for h in ["seq","código","codigo"]):
            for i, tr in enumerate(t.find_all("tr")[1:]):
                cols = tr.find_all("td")
                if len(cols) < 3: continue
                desc    = cols[2].get_text(strip=True) if len(cols) > 2 else ""
                cultura = norm_cultura(desc)
                seq_txt = cols[0].get_text(strip=True)
                itens.append({
                    "seq":            int(seq_txt) if seq_txt.isdigit() else i+1,
                    "codigo":         cols[1].get_text(strip=True) if len(cols) > 1 else "",
                    "descricao":      desc,
                    "qt_solicitada":  parse_val(cols[3].get_text(strip=True)) if len(cols) > 3 else 0,
                    "unidade_medida": cols[4].get_text(strip=True) if len(cols) > 4 else "KILOGRAMA",
                    "valor_unitario": parse_val(cols[5].get_text(strip=True)) if len(cols) > 5 else 0,
                    "valor_total":    parse_val(cols[6].get_text(strip=True)) if len(cols) > 6 else 0,
                    "cultura":        cultura,
                    "categoria":      categ(cultura),
                })
            break
    return itens

def extrair_fornecedores(html):
    soup  = BeautifulSoup(html, "lxml")
    forns = []
    for t in soup.find_all("table"):
        ths_lower = [th.get_text(strip=True).lower() for th in t.find_all("th")]
        if any(h in ths_lower for h in ["cpf/cnpj","cnpj","razão social","razao social"]):
            for tr in t.find_all("tr")[1:]:
                cols = tr.find_all("td")
                if len(cols) < 2: continue
                cpf_cnpj     = cols[0].get_text(strip=True)
                razao_social = cols[1].get_text(strip=True)
                cnpj_limpo   = re.sub(r"[^\d]", "", cpf_cnpj)
                if len(cnpj_limpo) >= 11 and razao_social:
                    forns.append({
                        "cpf_cnpj":    re.sub(r"[^\d./\-]", "", cpf_cnpj).strip(),
                        "razao_social": razao_social.strip(),
                    })
    return forns

def extrair_empenhos(html):
    soup = BeautifulSoup(html, "lxml")
    emps = []
    for t in soup.find_all("table"):
        ths_lower = [th.get_text(strip=True).lower() for th in t.find_all("th")]
        if "data empenho" in " ".join(ths_lower) or "dt. empenho" in " ".join(ths_lower):
            for tr in t.find_all("tr")[1:]:
                cols = tr.find_all("td")
                if len(cols) < 2: continue
                nr   = cols[0].get_text(strip=True)
                ano  = cols[1].get_text(strip=True) if len(cols) > 1 else ""
                data = cols[2].get_text(strip=True) if len(cols) > 2 else ""
                if nr and nr != "null":
                    try:
                        dt = datetime.strptime(data.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
                    except:
                        dt = None
                    emps.append({
                        "nr_empenho": nr,
                        "ano":        int(ano) if ano.isdigit() else None,
                        "dt_empenho": dt,
                    })
            break
    return emps

# ── Gravação Supabase ─────────────────────────────────────────────────────────

def gravar_itens(sb, lic_id, itens):
    if not itens: return 0
    vistos = {}
    for item in itens:
        item["licitacao_id"] = lic_id
        vistos[item["seq"]]  = item
    n = 0
    for item in vistos.values():
        try:
            sb.table("itens_licitacao").upsert(
                item, on_conflict="licitacao_id,seq").execute()
            n += 1
        except: pass
    return n

def upsert_fornecedor(sb, cpf_cnpj, razao_social):
    if not cpf_cnpj or not razao_social: return None
    try:
        r = sb.table("fornecedores").upsert(
            {"cpf_cnpj": cpf_cnpj, "razao_social": razao_social,
             "tipo": tipo_forn(razao_social)},
            on_conflict="cpf_cnpj").execute()
        if r.data: return r.data[0]["id"]
        r2 = sb.table("fornecedores").select("id").eq("cpf_cnpj", cpf_cnpj).execute()
        return r2.data[0]["id"] if r2.data else None
    except: return None

def gravar_participacao(sb, lic_id, forn_id):
    try:
        sb.table("participacoes").upsert(
            {"licitacao_id": lic_id, "fornecedor_id": forn_id, "participou": True},
            on_conflict="licitacao_id,fornecedor_id").execute()
    except: pass

def gravar_empenho(sb, item_id, emp):
    try:
        emp["item_id"] = item_id
        sb.table("empenhos").insert(emp).execute()
    except: pass

def ja_tem_itens(sb, lic_id):
    try:
        r = sb.table("itens_licitacao").select("id").eq(
            "licitacao_id", lic_id).limit(1).execute()
        return len(r.data) > 0
    except: return False

# ── Playwright: indexar links ─────────────────────────────────────────────────

async def indexar_links_playwright(page) -> dict:
    """Percorre todas as páginas e coleta {processo: {link_id, id_interno, situacao}}."""
    from bs4 import BeautifulSoup as BS
    indice = {}

    # Pesquisar
    await page.select_option("select[name='form:j_id9']", label=ORGAO)
    await asyncio.sleep(1.0)
    await page.fill("#form\\:dataInferiorInputDate", DT_INICIO)
    await page.fill("#form\\:j_id18InputDate", DT_FIM)
    await asyncio.sleep(0.5)
    await page.click("#form\\:btSearch")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(2)

    # Total de páginas
    html  = await page.content()
    m     = re.search(r"quantidade registros.*?(\d+)</label>", html, re.I|re.DOTALL)
    total = int(m.group(1)) if m else 0
    npag  = math.ceil(total / 5)
    print(f"    {total} registros | {npag} páginas")

    def extrair_links_html(h):
        s    = BS(h, "lxml")
        regs = []
        for t in s.find_all("table"):
            ths = [th.get_text(strip=True).lower() for th in t.find_all("th")]
            if "processo" in ths and "objeto" in ths:
                for tr in t.find_all("tr")[1:]:
                    cols = tr.find_all("td")
                    if not cols: continue
                    proc = cols[0].get_text(strip=True)
                    if not re.match(r"^[A-Z]{2}\s+\d+/\d{4}", proc): continue
                    link = cols[0].find("a")
                    if not link: continue
                    onclick  = link.get("onclick","")
                    m_id     = re.search(r"'id'\s*:\s*(\d+)", onclick)
                    m_sit    = re.search(r"'situacao'\s*:\s*'([^']+)'", onclick)
                    regs.append({
                        "processo":   proc,
                        "link_id":    link.get("id",""),
                        "id_interno": int(m_id.group(1)) if m_id else 0,
                        "situacao":   m_sit.group(1) if m_sit else "",
                    })
                break
        return regs

    for lnk in extrair_links_html(html):
        lnk["pagina"] = 1
        indice[lnk["processo"]] = lnk

    pagina_atual = 1
    for pag in range(2, npag + 1):
        try:
            btn = page.locator(f"td.rich-datascr-inact:has-text('{pag}')")
            if await btn.count() == 0:
                prox = page.locator("td.rich-datascr-button >> nth=-1")
                if await prox.count() > 0:
                    await prox.first.click()
                    await page.wait_for_load_state("networkidle")
                    await asyncio.sleep(1)
                btn = page.locator(f"td.rich-datascr-inact:has-text('{pag}')")
            if await btn.count() > 0:
                await btn.first.click()
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(0.8)
                pagina_atual = pag
            for lnk in extrair_links_html(await page.content()):
                lnk["pagina"] = pagina_atual
                indice[lnk["processo"]] = lnk
        except:
            pass
        if pag % 25 == 0:
            print(f"    Indexando... p.{pag}/{npag} ({len(indice)} links)")

    return indice

# ── Fluxo principal ───────────────────────────────────────────────────────────

async def main(apenas_af=False, max_processos=None):
    sb = get_supabase()

    print("[1] Carregando licitações do Supabase...")
    q = sb.table("licitacoes").select(
        "id,processo,tipo_processo,relevante_af").eq("orgao", ORGAO)
    if apenas_af:
        q = q.eq("relevante_af", True)
    todas = q.order("id").execute().data
    com_detalhe = [l for l in todas if l["tipo_processo"] in TIPOS_COM_DETALHE]
    if max_processos:
        com_detalhe = com_detalhe[:max_processos]
    print(f"    {len(com_detalhe)} processos a detalhar")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, slow_mo=200)
        page    = await browser.new_page(
            user_agent="Mozilla/5.0 (AgroIA-RMC PPGCA/UEPG research)")

        print("\n[2] Abrindo portal e indexando links...")
        await page.goto(FORM_URL, timeout=30000)
        await page.wait_for_selector("select[name='form:j_id9']", timeout=15000)
        await asyncio.sleep(1.5)

        indice = await indexar_links_playwright(page)
        print(f"    {len(indice)} links indexados\n")

        print("[3] Coletando detalhes...\n")
        total_itens = total_forns = total_pulados = total_erros = 0

        for i, lic in enumerate(com_detalhe, 1):
            lic_id   = lic["id"]
            processo = lic["processo"]

            if ja_tem_itens(sb, lic_id):
                total_pulados += 1
                continue

            info = indice.get(processo)
            if not info or not info.get("id_interno"):
                continue

            try:
                # Navegar para a página onde o processo está
                pag_proc = info.get("pagina", 1)
                btn = page.locator(f"td.rich-datascr-inact:has-text('{pag_proc}')")
                btn_act = page.locator(f"td.rich-datascr-act:has-text('{pag_proc}')")
                if await btn.count() > 0:
                    await btn.first.click()
                    await page.wait_for_load_state("networkidle")
                    await asyncio.sleep(0.8)
                elif await btn_act.count() == 0:
                    # pagina nao visivel, avançar bloco
                    prox = page.locator("td.rich-datascr-button >> nth=-1")
                    if await prox.count() > 0:
                        await prox.first.click()
                        await page.wait_for_load_state("networkidle")
                        await asyncio.sleep(1)
                    btn = page.locator(f"td.rich-datascr-inact:has-text('{pag_proc}')")
                    if await btn.count() > 0:
                        await btn.first.click()
                        await page.wait_for_load_state("networkidle")
                        await asyncio.sleep(0.8)

                link = page.locator(f"a:has-text('{processo}')")
                if await link.count() > 0:
                    await link.first.click()
                    await page.wait_for_load_state("networkidle")
                    await asyncio.sleep(DELAY)

                    html_det = await page.content()

                    itens        = extrair_itens(html_det)
                    fornecedores = extrair_fornecedores(html_det)
                    empenhos     = extrair_empenhos(html_det)

                    n_itens = gravar_itens(sb, lic_id, itens)
                    total_itens += n_itens

                    for forn in fornecedores:
                        fid = upsert_fornecedor(sb, forn["cpf_cnpj"], forn["razao_social"])
                        if fid:
                            gravar_participacao(sb, lic_id, fid)
                            total_forns += 1

                    if empenhos and itens:
                        r = sb.table("itens_licitacao").select("id").eq(
                            "licitacao_id", lic_id).limit(1).execute()
                        if r.data:
                            for emp in empenhos:
                                gravar_empenho(sb, r.data[0]["id"], emp)

                    af = " [AF]" if lic.get("relevante_af") else ""
                    print(f"  [{i:4d}/{len(com_detalhe)}] {processo}{af}"
                          f" | itens:{n_itens} | forn:{len(fornecedores)}"
                          f" | emp:{len(empenhos)}")

                    # Voltar para a lista
                    await page.go_back()
                    await page.wait_for_load_state("networkidle")
                    await asyncio.sleep(0.8)

            except Exception as e:
                total_erros += 1
                print(f"  [{i:4d}] ERRO {processo}: {e}")

            if i % 50 == 0:
                print(f"\n  --- {i} processados ---\n")
                await asyncio.sleep(2)

        await browser.close()

    print(f"\n{'='*60}")
    print(f"Concluído! itens:{total_itens} | fornecedores:{total_forns}"
          f" | pulados:{total_pulados} | erros:{total_erros}")
    print(f"{'='*60}")


if __name__ == "__main__":
    # Teste com 10 processos:
    asyncio.run(main(max_processos=10))

    # Apenas relevantes para AF:
    # asyncio.run(main(apenas_af=True))

    # Todos:
    # asyncio.run(main())
