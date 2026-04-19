"""
AgroIA-RMC — Etapa 2: coleta detalhes via Playwright
=====================================================
headless=False — browser visível (pode minimizar)
Pesquisa uma vez, percorre todas as páginas coletando detalhes.

Execute: python etapa2_simples.py
"""
import os, re, asyncio, math
from datetime import datetime
from dotenv import load_dotenv
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings
from supabase import create_client
from playwright.async_api import async_playwright

warnings.filterwarnings('ignore', category=XMLParsedAsHTMLWarning)
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://rsphlvcekuomvpvjqxqm.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
FORM_URL  = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
ORGAO     = "SMSAN/FAAC"
DT_INICIO = "01/01/2019"
DT_FIM    = "31/12/2025"

# ── Extração ──────────────────────────────────────────────────────────────────

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

def ja_coletado(sb, lic_id):
    try:
        r = sb.table("itens_licitacao").select("id").eq(
            "licitacao_id", lic_id).limit(1).execute()
        return len(r.data) > 0
    except: return False

def extrair_processos_da_pagina(html):
    soup  = BeautifulSoup(html, "lxml")
    procs = []
    for t in soup.find_all("table"):
        ths = [th.get_text(strip=True).lower() for th in t.find_all("th")]
        if "processo" in ths and "objeto" in ths:
            for tr in t.find_all("tr")[1:]:
                cols = tr.find_all("td")
                if not cols: continue
                proc = cols[0].get_text(strip=True)
                if re.match(r"^[A-Z]{2}\s+\d+/\d{4}", proc):
                    procs.append(proc)
            break
    return procs

# ── Fluxo principal ───────────────────────────────────────────────────────────

async def main():
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("[1] Carregando licitações do Supabase...")
    dados = sb.table("licitacoes").select("id,processo").eq(
        "orgao", ORGAO).order("id").execute().data
    mapa = {d["processo"]: d["id"] for d in dados}
    r = sb.table("itens_licitacao").select("licitacao_id").execute()
    coletados = {row["licitacao_id"] for row in r.data}
    pendentes = [p for p, lid in mapa.items() if lid not in coletados]
    print(f"    {len(mapa)} no banco | {len(coletados)} coletados | {len(pendentes)} pendentes\n")

    if not pendentes:
        print("Tudo coletado!")
        return

    total_itens = total_forns = total_erros = processados = 0

    async with async_playwright() as pw:
        # headless=False: igual ao teste que funcionou
        browser = await pw.chromium.launch(headless=False, slow_mo=300)
        page    = await browser.new_page()

        # ── Pesquisa inicial — idêntica ao capturar_pagina2.py ────────────
        print("[2] Abrindo portal...")
        await page.goto(FORM_URL, timeout=30000)
        await page.wait_for_selector("select[name='form:j_id9']", timeout=15000)
        await asyncio.sleep(1.5)

        print("    Selecionando SMSAN/FAAC...")
        await page.select_option("select[name='form:j_id9']", label=ORGAO)
        await asyncio.sleep(1)

        print("    Preenchendo datas...")
        await page.click("#form\\:dataInferiorInputDate", click_count=3)
        await page.keyboard.type(DT_INICIO)
        await asyncio.sleep(0.5)
        await page.click("#form\\:j_id18InputDate", click_count=3)
        await page.keyboard.type(DT_FIM)
        await asyncio.sleep(0.5)

        print("    Pesquisando...")
        await page.click("#form\\:btSearch")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2.5)

        html = await page.content()
        m = re.search(r"quantidade registros.*?(\d+)", html, re.I | re.DOTALL)
        total_portal = int(m.group(1)) if m else 0
        total_pags   = math.ceil(total_portal / 5) if total_portal else 1
        print(f"    {total_portal} registros | {total_pags} páginas\n")
        print("[3] Coletando...\n")

        pagina_atual = 1

        while pagina_atual <= total_pags:
            # Extrair processos da página atual
            html_lista = await page.content()
            procs_pagina = extrair_processos_da_pagina(html_lista)

            if not procs_pagina:
                print(f"  Página {pagina_atual}: sem processos")
                break

            for proc in procs_pagina:
                lic_id = mapa.get(proc)
                if not lic_id or lic_id in coletados:
                    continue

                try:
                    # Clicar no link — igual ao que funcionou
                    await page.click(f"a:text-is('{proc}')")
                    await page.wait_for_load_state("networkidle")
                    await asyncio.sleep(1.5)

                    # Coletar HTML do detalhe
                    html_det = await page.content()
                    itens, forns, emps = extrair_tudo(html_det)
                    n_i, n_f = gravar(sb, lic_id, itens, forns, emps)
                    coletados.add(lic_id)
                    total_itens  += n_i
                    total_forns  += n_f
                    processados  += 1

                    print(f"  [{processados}/{len(pendentes)}] {proc}"
                          f" | itens:{n_i} | forn:{n_f} | emp:{len(emps)}")

                    # Voltar usando o link "Lista Licitações" no topo da página
                    await page.click("a:has-text('Lista Licitações')")
                    await page.wait_for_load_state("networkidle")
                    await asyncio.sleep(1.5)

                except Exception as e:
                    total_erros += 1
                    print(f"  ERRO {proc}: {str(e)[:80]}")

            # Avançar para próxima página
            if pagina_atual < total_pags:
                try:
                    # Clicar no número da próxima página no datascroller
                    next_pag = pagina_atual + 1
                    btn = page.locator(f"td.rich-datascr-inact >> text='{next_pag}'").first
                    if await btn.count():
                        await btn.click()
                    else:
                        # Tentar botão >
                        btn = page.locator("td.rich-datascr-button").last
                        await btn.click()
                    await page.wait_for_load_state("networkidle")
                    await asyncio.sleep(1.5)
                    pagina_atual += 1
                    print(f"\n  --- Página {pagina_atual}/{total_pags} ---\n")
                except Exception as e:
                    print(f"  Erro ao avançar página: {e}")
                    break
            else:
                break

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
