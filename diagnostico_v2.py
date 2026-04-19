"""
AgroIA-RMC — Diagnóstico Playwright (versão simplificada)
=========================================================
Execute: python diagnostico_v2.py
"""
import time
from playwright.sync_api import sync_playwright

FORM_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"

def main():
    print("=" * 70)
    print("DIAGNÓSTICO COM PLAYWRIGHT")
    print("=" * 70)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        page = browser.new_page()
        
        # 1. Acessar página
        print("\n[1] Acessando portal...")
        page.goto(FORM_URL, timeout=60000)
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        # 2. Listar todos os selects
        print("\n[2] Identificando selects na página...")
        selects = page.query_selector_all("select")
        for i, sel in enumerate(selects):
            sel_id = sel.get_attribute("id") or "sem-id"
            sel_name = sel.get_attribute("name") or "sem-name"
            options = sel.query_selector_all("option")
            first_opts = [o.inner_text()[:30] for o in options[:3]]
            print(f"    Select {i}: id='{sel_id}' | opções: {first_opts}...")
        
        # 3. Preencher manualmente - aguardar usuário
        print("\n[3] Navegador aberto!")
        print("    INSTRUÇÕES:")
        print("    1. Selecione o órgão 'SMSAN/FAAC' manualmente")
        print("    2. Preencha datas: 01/01/2019 a 31/12/2025")
        print("    3. Clique em 'Pesquisar'")
        print("    4. Clique em uma licitação de ALIMENTOS (ex: Dispensa com 'alimentícios')")
        print("    5. Observe a estrutura da página de detalhe")
        print("    6. Pressione ENTER aqui quando estiver na página de detalhe")
        input("\n    >>> Pressione ENTER quando estiver na página de DETALHE...")
        
        # 4. Capturar HTML da página de detalhe
        print("\n[4] Capturando página de detalhe...")
        
        html = page.content()
        with open("debug_detalhe_manual.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"    HTML salvo: debug_detalhe_manual.html ({len(html)} chars)")
        
        page.screenshot(path="debug_detalhe_manual.png", full_page=True)
        print("    Screenshot: debug_detalhe_manual.png")
        
        # 5. Analisar tabelas
        print("\n[5] Analisando tabelas encontradas...")
        
        tabelas = page.query_selector_all("table")
        print(f"    Total de tabelas: {len(tabelas)}")
        
        for i, t in enumerate(tabelas):
            try:
                # Pegar headers
                headers = t.query_selector_all("th")
                if not headers:
                    continue
                    
                header_texts = [h.inner_text().strip() for h in headers]
                rows = t.query_selector_all("tr")
                
                # Filtrar tabelas relevantes
                header_lower = " ".join(header_texts).lower()
                
                # Tabela de ITENS
                if "seq" in header_lower and ("descrição" in header_lower or "descricao" in header_lower or "código" in header_lower):
                    print(f"\n    ★★★ TABELA DE ITENS (índice {i}) ★★★")
                    print(f"    Headers: {header_texts}")
                    print(f"    Linhas: {len(rows)}")
                    
                    # Mostrar dados
                    for j, row in enumerate(rows[1:6]):  # Primeiras 5 linhas
                        cells = row.query_selector_all("td")
                        if cells:
                            cell_texts = [c.inner_text().strip()[:35] for c in cells]
                            print(f"      [{j+1}] {cell_texts}")
                
                # Tabela de FORNECEDORES
                elif "cpf" in header_lower or "cnpj" in header_lower or "razão social" in header_lower:
                    print(f"\n    ★★★ TABELA DE FORNECEDORES (índice {i}) ★★★")
                    print(f"    Headers: {header_texts}")
                    print(f"    Linhas: {len(rows)}")
                    
                    for j, row in enumerate(rows[1:4]):
                        cells = row.query_selector_all("td")
                        if cells:
                            cell_texts = [c.inner_text().strip()[:35] for c in cells]
                            print(f"      [{j+1}] {cell_texts}")
                
                # Tabela de EMPENHOS
                elif "empenho" in header_lower:
                    print(f"\n    ★★★ TABELA DE EMPENHOS (índice {i}) ★★★")
                    print(f"    Headers: {header_texts}")
                    print(f"    Linhas: {len(rows)}")
                    
                    for j, row in enumerate(rows[1:4]):
                        cells = row.query_selector_all("td")
                        if cells:
                            cell_texts = [c.inner_text().strip()[:35] for c in cells]
                            print(f"      [{j+1}] {cell_texts}")
                            
            except Exception as e:
                pass
        
        # 6. Identificar abas/panels
        print("\n[6] Buscando abas e painéis...")
        
        # RichFaces usa rich-tab-header para abas
        abas = page.query_selector_all(".rich-tab-header, .rich-tabpanel-content, td[class*='tab']")
        print(f"    Elementos de aba: {len(abas)}")
        
        for aba in abas:
            texto = aba.inner_text().strip()[:50]
            classe = aba.get_attribute("class") or ""
            if texto:
                print(f"      - '{texto}' (class: {classe[:30]})")
        
        # 7. Segunda captura após clicar em abas
        print("\n[7] Se existirem abas, clique nelas manualmente e pressione ENTER")
        input("    >>> Pressione ENTER para capturar novamente...")
        
        html2 = page.content()
        with open("debug_detalhe_apos_aba.html", "w", encoding="utf-8") as f:
            f.write(html2)
        print(f"    HTML salvo: debug_detalhe_apos_aba.html ({len(html2)} chars)")
        
        page.screenshot(path="debug_detalhe_apos_aba.png", full_page=True)
        print("    Screenshot: debug_detalhe_apos_aba.png")
        
        # Analisar novamente
        print("\n[8] Re-analisando tabelas após clique em abas...")
        tabelas2 = page.query_selector_all("table")
        
        for i, t in enumerate(tabelas2):
            try:
                headers = t.query_selector_all("th")
                if not headers:
                    continue
                header_texts = [h.inner_text().strip() for h in headers]
                header_lower = " ".join(header_texts).lower()
                rows = t.query_selector_all("tr")
                
                if "seq" in header_lower and len(rows) > 1:
                    print(f"\n    ★ TABELA COM SEQ (índice {i})")
                    print(f"    Headers: {header_texts}")
                    for j, row in enumerate(rows[1:5]):
                        cells = row.query_selector_all("td")
                        if cells:
                            cell_texts = [c.inner_text().strip()[:35] for c in cells]
                            print(f"      [{j+1}] {cell_texts}")
            except:
                pass
        
        print("\n[9] Pressione ENTER para fechar o navegador...")
        input()
        
        browser.close()
    
    print("\n" + "=" * 70)
    print("Diagnóstico concluído!")
    print("Arquivos gerados:")
    print("  - debug_detalhe_manual.html")
    print("  - debug_detalhe_manual.png")
    print("  - debug_detalhe_apos_aba.html")
    print("  - debug_detalhe_apos_aba.png")
    print("=" * 70)

if __name__ == "__main__":
    main()
