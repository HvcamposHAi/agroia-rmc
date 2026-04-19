"""
AgroIA-RMC — Coleta Automática (Headless)
=========================================
Executa automaticamente sem interação.

Execute: python coleta_headless.py
"""
import os
import re
import time
import signal
from datetime import datetime
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from supabase import create_client

load_dotenv()

sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
ORGAO = "SMSAN/FAAC"

parar = False
def handler(sig, frame):
    global parar
    parar = True
signal.signal(signal.SIGINT, handler)

def parse_num(t):
    try: return float(t.replace(".", "").replace(",", "."))
    except: return 0.0

def cultura(desc):
    d = desc.lower()
    for k, v in {"leite":"leite","banana":"banana","laranja":"laranja","maçã":"maca",
                 "mamão":"mamao","melancia":"melancia","uva":"uva","morango":"morango",
                 "tomate":"tomate","cebola":"cebola","cenoura":"cenoura","batata":"batata",
                 "aipim":"aipim","mandioca":"aipim","alface":"alface","couve":"couve",
                 "repolho":"repolho","alho":"alho","beterraba":"beterraba","milho":"milho",
                 "queijo":"queijo","ovos":"ovos","ovo":"ovos","frango":"frango","carne":"carne",
                 "arroz":"arroz","feijão":"feijao","feijao":"feijao","mel":"mel"}.items():
        if k in d: return v
    m = re.findall(r'[a-záéíóúâêîôûãõç]+', d)
    return m[0] if m else "outro"

def categ(c):
    if c in {"banana","laranja","maca","mamao","melancia","uva","morango"}: return "FRUTA"
    if c in {"tomate","cebola","cenoura","batata","aipim","alho","beterraba","milho"}: return "LEGUME"
    if c in {"alface","couve","repolho"}: return "FOLHOSA"
    if c in {"leite","queijo"}: return "LATICINIOS"
    if c in {"frango","carne","ovos"}: return "PROTEINA"
    if c in {"arroz","feijao"}: return "GRAOS"
    return "OUTRO"

def extrair_itens(texto):
    itens = []
    linhas = texto.split("\n")
    inicio = -1
    for i, l in enumerate(linhas):
        if l.strip() == "páginas":
            inicio = i + 1
            break
    if inicio == -1:
        return itens
    
    pat = re.compile(r'^(\d+)\s+(\d{10,15})\s+(.+?)\s+([\d.]+,\d{2})\s+(\S+)\s+([\d.]+,\d{4})\s+Empenhos')
    for i in range(inicio, len(linhas)):
        l = linhas[i].strip()
        if l.startswith("Fornecedores") or l.startswith("Documentos"):
            break
        m = pat.match(l)
        if m:
            c = cultura(m.group(3))
            itens.append({
                "seq": int(m.group(1)),
                "codigo": m.group(2),
                "descricao": m.group(3).strip().rstrip(","),
                "qt_solicitada": parse_num(m.group(4)),
                "unidade_medida": m.group(5),
                "valor_unitario": parse_num(m.group(6)),
                "valor_total": parse_num(m.group(4)) * parse_num(m.group(6)),
                "cultura": c,
                "categoria": categ(c),
            })
    return itens

def gravar(lic_id, itens):
    n = 0
    for it in itens:
        it["licitacao_id"] = lic_id
        try:
            sb.table("itens_licitacao").upsert(it, on_conflict="licitacao_id,seq").execute()
            n += 1
        except: pass
    return n

def main():
    global parar
    
    print("AgroIA-RMC — Coleta Headless")
    print("=" * 40)
    
    # Carregar mapa
    dados = sb.table("licitacoes").select("id,processo").eq("orgao", ORGAO).execute().data
    mapa = {d["processo"]: d["id"] for d in dados}
    print(f"Licitações no banco: {len(mapa)}")
    
    # Verificar coletadas (código numérico = dados válidos)
    r = sb.table("itens_licitacao").select("licitacao_id,codigo").execute()
    coletados = set(x["licitacao_id"] for x in r.data if x.get("codigo") and x["codigo"].isdigit())
    pendentes = {p: lid for p, lid in mapa.items() if lid not in coletados}
    print(f"Já coletadas: {len(coletados)} | Pendentes: {len(pendentes)}")
    
    if not pendentes:
        print("Nada a fazer.")
        return
    
    stats = {"ok": 0, "itens": 0, "sem": 0, "err": 0}
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # False para debug inicial
        page = browser.new_page()
        page.set_default_timeout(60000)
        
        page.goto(URL)
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        # Filtros
        page.evaluate("""() => {
            document.querySelectorAll('select').forEach(s => {
                [...s.options].forEach(o => {
                    if (o.text.includes('SMSAN/FAAC')) { s.value = o.value; s.dispatchEvent(new Event('change', {bubbles:true})); }
                });
            });
            document.querySelectorAll('input[type="text"]').forEach(inp => {
                if (inp.id.includes('dataInferior') && inp.id.includes('Input')) inp.value = '01/01/2019';
                if (inp.id.includes('j_id18') && inp.id.includes('Input')) inp.value = '31/12/2026';
            });
        }""")
        time.sleep(1)
        page.click("input[value='Pesquisar']")
        page.wait_for_timeout(4000)
        
        pagina = 1
        
        while not parar:
            links = page.query_selector_all("a[id*='tabela'][id*='j_id26']")
            if not links:
                break
            
            procs = [(l.inner_text().strip(), l) for l in links]
            pendentes_pag = [(proc, link) for proc, link in procs if proc in pendentes]
            
            if pendentes_pag:
                print(f"Pág {pagina}: {len(pendentes_pag)} pendentes")
            
            for proc, _ in pendentes_pag:
                if parar:
                    break
                
                lic_id = pendentes[proc]
                
                try:
                    # Re-buscar link (DOM pode ter mudado)
                    links = page.query_selector_all("a[id*='tabela'][id*='j_id26']")
                    link = next((l for l in links if l.inner_text().strip() == proc), None)
                    if not link:
                        continue
                    
                    link.click()
                    page.wait_for_timeout(2500)
                    
                    itens = extrair_itens(page.inner_text("body"))
                    
                    if itens:
                        n = gravar(lic_id, itens)
                        stats["ok"] += 1
                        stats["itens"] += n
                        del pendentes[proc]
                        print(f"  [{stats['ok']:4}] {proc}: {n} itens")
                    else:
                        stats["sem"] += 1
                    
                    # Voltar
                    btn = page.query_selector("input[value='Página Inicial']")
                    if btn:
                        btn.click()
                        page.wait_for_timeout(1500)
                    
                except Exception as e:
                    stats["err"] += 1
                    try:
                        page.query_selector("input[value='Página Inicial']").click()
                        page.wait_for_timeout(1500)
                    except:
                        pass
            
            if parar:
                break
            
            # Próxima página
            pag_atual = page.query_selector("td.rich-datascr-act")
            if not pag_atual:
                break
            
            num_atual = int(pag_atual.inner_text().strip())
            avancou = False
            
            for td in page.query_selector_all("td.rich-datascr-inact"):
                try:
                    if int(td.inner_text().strip()) == num_atual + 1:
                        td.click()
                        page.wait_for_timeout(2000)
                        avancou = True
                        break
                except:
                    pass
            
            if not avancou:
                for btn in page.query_selector_all("td.rich-datascr-button"):
                    if "onscroll" in (btn.get_attribute("onclick") or ""):
                        btn.click()
                        page.wait_for_timeout(2000)
                        avancou = True
                        break
            
            if not avancou:
                break
            
            pagina += 1
        
        browser.close()
    
    print(f"\nResumo: {stats['ok']} processadas, {stats['itens']} itens, {stats['sem']} sem itens, {stats['err']} erros")
    print(f"Pendentes: {len(pendentes)}")

if __name__ == "__main__":
    main()
