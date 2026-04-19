"""
AgroIA-RMC — Diagnóstico detalhado de TODAS as tabelas
======================================================
Execute: python diagnostico_tabelas.py
"""
import time
from playwright.sync_api import sync_playwright

FORM_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"

def main():
    print("=" * 70)
    print("DIAGNÓSTICO DETALHADO DE TABELAS")
    print("=" * 70)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        page = browser.new_page()
        
        print("\n[1] Acessando portal...")
        page.goto(FORM_URL, timeout=60000)
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        print("\n[2] Navegue até a DS 73/2019 e pressione ENTER...")
        input("    >>> ")
        
        print("\n[3] Listando TODAS as tabelas...\n")
        
        tabelas = page.query_selector_all("table")
        
        for idx, tabela in enumerate(tabelas):
            # Pegar HTML interno resumido
            inner = tabela.inner_html()[:200] if tabela.inner_html() else ""
            
            # Pegar headers
            headers = tabela.query_selector_all("th")
            header_texts = [h.inner_text().strip()[:20] for h in headers] if headers else []
            
            # Pegar primeira linha de dados
            rows = tabela.query_selector_all("tr")
            first_data = []
            if len(rows) > 1:
                cells = rows[1].query_selector_all("td")
                first_data = [c.inner_text().strip()[:20] for c in cells[:5]]
            
            # Pegar classes da tabela
            classe = tabela.get_attribute("class") or ""
            tabela_id = tabela.get_attribute("id") or ""
            
            print(f"--- TABELA {idx} ---")
            print(f"    ID: {tabela_id}")
            print(f"    Class: {classe}")
            print(f"    Headers ({len(headers)}): {header_texts}")
            print(f"    Rows: {len(rows)}")
            print(f"    First data: {first_data}")
            print()
        
        # Buscar especificamente por texto "Seq" na página
        print("\n[4] Buscando elementos com texto 'Seq'...")
        elementos_seq = page.query_selector_all("text=Seq")
        print(f"    Encontrados: {len(elementos_seq)}")
        for el in elementos_seq:
            parent = el.evaluate("el => el.parentElement ? el.parentElement.tagName : 'none'")
            texto = el.inner_text()[:50]
            print(f"      - '{texto}' (parent: {parent})")
        
        # Buscar por "Código"
        print("\n[5] Buscando elementos com texto 'Código'...")
        elementos_cod = page.query_selector_all("text=Código")
        print(f"    Encontrados: {len(elementos_cod)}")
        for el in elementos_cod[:5]:
            parent = el.evaluate("el => el.parentElement ? el.parentElement.tagName : 'none'")
            texto = el.inner_text()[:50]
            print(f"      - '{texto}' (parent: {parent})")
        
        # Buscar por "LEITE"
        print("\n[6] Buscando texto 'LEITE' na página...")
        elementos_leite = page.query_selector_all("text=LEITE")
        print(f"    Encontrados: {len(elementos_leite)}")
        for el in elementos_leite[:5]:
            parent = el.evaluate("el => el.parentElement ? el.parentElement.tagName : 'none'")
            grandparent = el.evaluate("el => el.parentElement && el.parentElement.parentElement ? el.parentElement.parentElement.tagName : 'none'")
            texto = el.inner_text()[:50]
            print(f"      - '{texto}' (parent: {parent}, grandparent: {grandparent})")
        
        # Buscar por rich-table (RichFaces)
        print("\n[7] Buscando tabelas RichFaces (rich-table)...")
        rich_tables = page.query_selector_all(".rich-table, [class*='rich-table']")
        print(f"    Encontradas: {len(rich_tables)}")
        for i, rt in enumerate(rich_tables):
            rt_id = rt.get_attribute("id") or ""
            rt_class = rt.get_attribute("class") or ""
            rows = rt.query_selector_all("tr")
            print(f"      [{i}] ID: {rt_id[:40]} | Class: {rt_class[:30]} | Rows: {len(rows)}")
        
        # Salvar HTML completo
        print("\n[8] Salvando HTML completo...")
        html = page.content()
        with open("debug_ds73_completo.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"    Salvo: debug_ds73_completo.html ({len(html)} chars)")
        
        print("\n[9] Pressione ENTER para fechar...")
        input()
        
        browser.close()

if __name__ == "__main__":
    main()
