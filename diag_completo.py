"""
Diagnóstico COMPLETO: Comparar TODOS os processos
"""
import os
from dotenv import load_dotenv
from supabase import create_client
from playwright.sync_api import sync_playwright
import time

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
FORM_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"

def main():
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    print("=" * 60)
    print("DIAGNÓSTICO COMPLETO")
    print("=" * 60)
    
    # Buscar TODOS os processos do banco
    print("\n[1] Carregando processos do BANCO...")
    dados = sb.table("licitacoes").select("processo").eq("orgao", "SMSAN/FAAC").execute()
    banco = set(d['processo'] for d in dados.data)
    print(f"    {len(banco)} processos no banco")
    
    # Mostrar distribuição por ano
    anos = {}
    for proc in banco:
        match = proc.split("/")
        if len(match) >= 2:
            ano = match[1].split()[0]
            anos[ano] = anos.get(ano, 0) + 1
    print(f"    Distribuição por ano: {dict(sorted(anos.items()))}")
    
    # Buscar processos do portal (todas as páginas)
    print("\n[2] Carregando processos do PORTAL (pode demorar)...")
    
    portal = set()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        page.goto(FORM_URL, timeout=60000)
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        # Preencher filtros
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
        page.wait_for_timeout(4000)
        
        # Navegar por todas as páginas
        pagina = 1
        max_paginas = 249
        
        while pagina <= max_paginas:
            links = page.query_selector_all("a[id*='tabela'][id*='j_id26']")
            for link in links:
                proc = link.inner_text().strip()
                portal.add(proc)
            
            if pagina % 20 == 0:
                print(f"    Página {pagina}/{max_paginas}... ({len(portal)} processos)")
            
            # Próxima página
            tds = page.query_selector_all("td.rich-datascr-inact")
            clicou = False
            for td in tds:
                num = td.inner_text().strip()
                if num.isdigit() and int(num) == pagina + 1:
                    td.click()
                    page.wait_for_timeout(1500)
                    clicou = True
                    break
            
            if not clicou:
                # Tentar botão >
                btns = page.query_selector_all("td.rich-datascr-button")
                for btn in btns:
                    onclick = btn.get_attribute("onclick") or ""
                    if "onscroll" in onclick:
                        btn.click()
                        page.wait_for_timeout(1500)
                        clicou = True
                        break
            
            if not clicou:
                break
            
            pagina += 1
        
        browser.close()
    
    print(f"    {len(portal)} processos no portal")
    
    # Comparar
    print("\n[3] Comparação:")
    comum = banco & portal
    so_banco = banco - portal
    so_portal = portal - banco
    
    print(f"    Em comum:      {len(comum)}")
    print(f"    Só no banco:   {len(so_banco)}")
    print(f"    Só no portal:  {len(so_portal)}")
    
    if so_banco:
        print(f"\n    Exemplos SÓ NO BANCO (não no portal):")
        for proc in list(so_banco)[:10]:
            print(f"      '{proc}'")
    
    if so_portal:
        print(f"\n    Exemplos SÓ NO PORTAL (não no banco):")
        for proc in list(so_portal)[:10]:
            print(f"      '{proc}'")

if __name__ == "__main__":
    main()
