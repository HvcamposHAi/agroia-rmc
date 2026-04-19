"""
Teste simples de paginação - sem processar nada
"""
import time
from playwright.sync_api import sync_playwright

FORM_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"

def main():
    print("TESTE DE PAGINAÇÃO SIMPLES")
    print("=" * 50)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=200)
        page = browser.new_page()
        
        print("\n[1] Acessando...")
        page.goto(FORM_URL, timeout=60000)
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
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
        
        # Mostrar página atual
        def mostrar_pagina():
            links = page.query_selector_all("a[id*='tabela'][id*='j_id26']")
            atual = page.query_selector("td.rich-datascr-act")
            pag = atual.inner_text().strip() if atual else "?"
            procs = [l.inner_text().strip() for l in links]
            print(f"    Página {pag}: {procs}")
        
        print("\n[3] Página inicial:")
        mostrar_pagina()
        
        # Testar clique na página 2
        print("\n[4] Clicando no '2'...")
        td2 = page.query_selector("td.rich-datascr-inact")
        if td2:
            print(f"    Encontrou TD: '{td2.inner_text().strip()}'")
            td2.click()
            page.wait_for_timeout(3000)
            print("    Após clique:")
            mostrar_pagina()
        else:
            print("    NÃO ENCONTROU td.rich-datascr-inact")
        
        # Testar clique na página 3
        print("\n[5] Clicando no '3'...")
        tds = page.query_selector_all("td.rich-datascr-inact")
        for td in tds:
            if td.inner_text().strip() == "3":
                td.click()
                page.wait_for_timeout(3000)
                print("    Após clique:")
                mostrar_pagina()
                break
        
        print("\n[6] Pressione ENTER para fechar...")
        input()
        browser.close()

if __name__ == "__main__":
    main()
