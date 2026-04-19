"""
AgroIA-RMC — Diagnóstico de Paginação (Corrigido)
=================================================
Execute: python diag_paginacao.py
"""
import time
from playwright.sync_api import sync_playwright

FORM_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
ORGAO = "SMSAN/FAAC"

def main():
    print("=" * 60)
    print("DIAGNÓSTICO DE PAGINAÇÃO")
    print("=" * 60)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)
        page = browser.new_page()
        
        print("\n[1] Acessando portal...")
        page.goto(FORM_URL, timeout=60000)
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        # Preencher filtros
        print("\n[2] Preenchendo filtros...")
        page.evaluate("""() => {
            var selects = document.querySelectorAll('select');
            for (var s of selects) {
                for (var opt of s.options) {
                    if (opt.text.includes('SMSAN/FAAC')) {
                        s.value = opt.value;
                        s.dispatchEvent(new Event('change', { bubbles: true }));
                        break;
                    }
                }
            }
        }""")
        time.sleep(1)
        
        page.evaluate("""() => {
            var inputs = document.querySelectorAll('input[type="text"]');
            for (var inp of inputs) {
                if (inp.id && inp.id.includes('dataInferior') && inp.id.includes('Input')) {
                    inp.value = '01/01/2019';
                }
                if (inp.id && inp.id.includes('j_id18') && inp.id.includes('Input')) {
                    inp.value = '31/12/2025';
                }
            }
        }""")
        time.sleep(1)
        
        page.click("input[value='Pesquisar']")
        print("    Pesquisando...")
        page.wait_for_timeout(5000)
        
        # Analisar área de paginação
        print("\n[3] Analisando elementos de paginação...")
        
        # Buscar TDs de paginação
        tds = page.query_selector_all("td[class*='datascr']")
        print(f"\n    TDs com 'datascr': {len(tds)}")
        for i, td in enumerate(tds):
            texto = td.inner_text().strip()
            classe = td.get_attribute("class") or ""
            onclick = td.get_attribute("onclick") or "none"
            print(f"      [{i}] texto='{texto}' class='{classe[:40]}' onclick='{onclick[:50]}...'")
        
        # Buscar spans/divs de paginação
        spans = page.query_selector_all("span[class*='datascr'], div[class*='datascr']")
        print(f"\n    Spans/Divs com 'datascr': {len(spans)}")
        for i, sp in enumerate(spans[:5]):
            texto = sp.inner_text().strip()[:30]
            classe = sp.get_attribute("class") or ""
            print(f"      [{i}] texto='{texto}' class='{classe[:40]}'")
        
        # Buscar tabela de paginação
        pag_table = page.query_selector("table[id*='j_id52']")
        if pag_table:
            print(f"\n    Tabela j_id52 encontrada!")
            inner = pag_table.inner_html()[:500]
            print(f"      HTML: {inner}...")
        
        # Buscar links numéricos
        print("\n    Links com números ou >:")
        links = page.query_selector_all("a")
        for link in links:
            texto = link.inner_text().strip()
            if texto in [">", ">>", "2", "3", "4", "5"]:
                href = link.get_attribute("href") or ""
                onclick = link.get_attribute("onclick") or "none"
                print(f"      '{texto}' onclick='{onclick[:60]}...'")
        
        # Capturar HTML do footer da tabela
        print("\n[4] Capturando HTML do footer...")
        footer = page.query_selector("tfoot, .rich-table-footer")
        if footer:
            html = footer.inner_html()
            with open("debug_footer.html", "w", encoding="utf-8") as f:
                f.write(html)
            print(f"    Salvo: debug_footer.html ({len(html)} chars)")
        
        # Screenshot da área de paginação
        page.screenshot(path="debug_paginacao.png", full_page=True)
        print("    Screenshot: debug_paginacao.png")
        
        print("\n[5] Tente clicar no '2' ou '>' manualmente")
        print("    Depois pressione ENTER...")
        input()
        
        # Ver se mudou
        links = page.query_selector_all("a[id*='tabela'][id*='j_id26']")
        if links:
            print(f"    Primeiro link: {links[0].inner_text().strip()}")
        
        browser.close()

if __name__ == "__main__":
    main()
