"""
Diagnóstico: Comparar formato dos processos
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
    print("DIAGNÓSTICO: FORMATO DOS PROCESSOS")
    print("=" * 60)
    
    # Buscar processos do banco
    print("\n[1] Processos no BANCO (primeiros 10):")
    dados = sb.table("licitacoes").select("processo").eq("orgao", "SMSAN/FAAC").limit(10).execute()
    for d in dados.data:
        print(f"    '{d['processo']}'")
    
    # Buscar processos do portal
    print("\n[2] Processos no PORTAL (primeiros 10):")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)
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
        
        links = page.query_selector_all("a[id*='tabela'][id*='j_id26']")
        for link in links:
            print(f"    '{link.inner_text().strip()}'")
        
        browser.close()
    
    # Comparar
    print("\n[3] Comparação:")
    banco = set(d['processo'] for d in dados.data)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(FORM_URL, timeout=60000)
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
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
        
        links = page.query_selector_all("a[id*='tabela'][id*='j_id26']")
        portal = set(link.inner_text().strip() for link in links)
        
        browser.close()
    
    # Intersecção
    comum = banco & portal
    so_banco = banco - portal
    so_portal = portal - banco
    
    print(f"    Em comum: {len(comum)}")
    print(f"    Só no banco: {len(so_banco)}")
    print(f"    Só no portal: {len(so_portal)}")
    
    if so_banco:
        print(f"\n    Exemplos só no banco: {list(so_banco)[:3]}")
    if so_portal:
        print(f"    Exemplos só no portal: {list(so_portal)[:3]}")

if __name__ == "__main__":
    main()
