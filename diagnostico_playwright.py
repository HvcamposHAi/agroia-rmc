"""
AgroIA-RMC — Diagnóstico com Playwright (clica nas abas)
========================================================
Usa Playwright para carregar a página de detalhe e clicar
nas abas de Itens e Fornecedores.

Execute: python diagnostico_playwright.py
"""
import re
import time
from playwright.sync_api import sync_playwright

FORM_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
ORGAO = "SMSAN/FAAC"

def main():
    print("=" * 70)
    print("DIAGNÓSTICO COM PLAYWRIGHT")
    print("=" * 70)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        page = browser.new_page()
        
        # 1. Acessar página
        print("\n[1] Acessando portal...")
        page.goto(FORM_URL, timeout=60000)
        page.wait_for_load_state("networkidle")
        
        # 2. Preencher filtros
        print("[2] Preenchendo filtros...")
        page.select_option("select[id='form:j_id9']", value=ORGAO)
        page.fill("input[id='form:dataInferiorInputDate']", "01/01/2019")
        page.fill("input[id='form:j_id18InputDate']", "31/12/2025")
        
        # 3. Pesquisar
        print("[3] Pesquisando...")
        page.click("input[id='form:btSearch']")
        page.wait_for_timeout(3000)
        
        # 4. Clicar no primeiro processo (que tenha produtos alimentícios)
        print("[4] Buscando licitação de produtos alimentícios...")
        
        # Procurar por links de processos
        links = page.query_selector_all("a[id^='form:tabela:']")
        print(f"    Encontrados {len(links)} processos")
        
        # Clicar no primeiro link
        if links:
            primeiro = links[0]
            texto = primeiro.inner_text()
            print(f"    Clicando em: {texto}")
            primeiro.click()
            page.wait_for_timeout(3000)
        
        # 5. Analisar abas disponíveis
        print("\n[5] Analisando abas da página de detalhe...")
        
        # Buscar todas as abas (geralmente são <td> com onclick ou <a> dentro de panel)
        abas = page.query_selector_all("td.rich-tab-header, .rich-tabpanel-content, a[onclick*='tab']")
        print(f"    Elementos de aba encontrados: {len(abas)}")
        
        # Buscar por texto específico de abas
        page_content = page.content()
        
        # Procurar por padrões comuns de abas
        aba_patterns = [
            "Itens da Licitação",
            "Itens",
            "Documentos",
            "Fornecedores",
            "Empenhos",
            "Licitação"
        ]
        
        for pattern in aba_patterns:
            if pattern.lower() in page_content.lower():
                print(f"    ✓ Encontrado texto: '{pattern}'")
        
        # 6. Tentar clicar na aba de Itens
        print("\n[6] Tentando acessar aba de Itens...")
        
        # Diferentes seletores possíveis para a aba de itens
        seletores_itens = [
            "text='Itens da Licitação'",
            "text='Itens'",
            "td:has-text('Itens')",
            "[onclick*='itens']",
            "a:has-text('Itens')",
        ]
        
        aba_clicada = False
        for sel in seletores_itens:
            try:
                el = page.query_selector(sel)
                if el:
                    print(f"    Tentando seletor: {sel}")
                    el.click()
                    page.wait_for_timeout(2000)
                    aba_clicada = True
                    break
            except:
                pass
        
        if not aba_clicada:
            print("    Nenhuma aba de itens encontrada com seletores padrão")
        
        # 7. Salvar screenshot e HTML
        print("\n[7] Salvando diagnóstico...")
        page.screenshot(path="debug_detalhe_screenshot.png", full_page=True)
        print("    Screenshot: debug_detalhe_screenshot.png")
        
        with open("debug_detalhe_playwright.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        print("    HTML: debug_detalhe_playwright.html")
        
        # 8. Listar todas as tabelas visíveis
        print("\n[8] Analisando tabelas visíveis...")
        
        tabelas = page.query_selector_all("table")
        print(f"    Total de tabelas: {len(tabelas)}")
        
        for i, t in enumerate(tabelas):
            try:
                headers = t.query_selector_all("th")
                header_texts = [h.inner_text().strip()[:20] for h in headers[:5]]
                rows = t.query_selector_all("tr")
                
                if header_texts and len(rows) > 1:
                    print(f"\n    Tabela {i}: {len(rows)} linhas")
                    print(f"    Headers: {header_texts}")
                    
                    # Verificar se é tabela de itens
                    header_lower = [h.lower() for h in header_texts]
                    if any(x in header_lower for x in ['seq', 'código', 'codigo', 'descrição', 'descricao']):
                        print(f"    *** POSSÍVEL TABELA DE ITENS ***")
                        
                        # Mostrar primeiras linhas
                        for j, row in enumerate(rows[1:4]):  # Primeiras 3 linhas de dados
                            cells = row.query_selector_all("td")
                            cell_texts = [c.inner_text().strip()[:25] for c in cells[:6]]
                            print(f"      Linha {j+1}: {cell_texts}")
            except:
                pass
        
        # 9. Aguardar para inspeção manual
        print("\n[9] Navegador aberto para inspeção manual...")
        print("    Pressione ENTER para fechar.")
        input()
        
        browser.close()
    
    print("\n" + "=" * 70)
    print("Diagnóstico concluído!")
    print("=" * 70)

if __name__ == "__main__":
    main()
