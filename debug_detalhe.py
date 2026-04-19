"""
DEBUG: Ver conteúdo da página de detalhe
"""
import os
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

FORM_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"

def main():
    print("=" * 50)
    print("DEBUG: CONTEÚDO DA PÁGINA DE DETALHE")
    print("=" * 50)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        page = browser.new_page()
        
        print("\nAcessando portal...")
        page.goto(FORM_URL, timeout=60000)
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        # Filtros
        print("Preenchendo filtros...")
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
                    inp.value = '31/12/2026';
                }
            }
        }""")
        time.sleep(1)
        
        page.click("input[value='Pesquisar']")
        page.wait_for_timeout(4000)
        
        # Clicar no primeiro link
        print("\nClicando no primeiro link...")
        links = page.query_selector_all("a[id*='tabela'][id*='j_id26']")
        primeiro = links[0].inner_text().strip()
        print(f"Processo: {primeiro}")
        links[0].click()
        page.wait_for_timeout(3000)
        
        # Capturar texto
        texto = page.inner_text("body")
        
        # Salvar texto completo
        with open("debug_detalhe.txt", "w", encoding="utf-8") as f:
            f.write(texto)
        print(f"\nTexto completo salvo: debug_detalhe.txt ({len(texto)} chars)")
        
        # Mostrar área dos itens
        print("\n" + "=" * 50)
        print("BUSCANDO ÁREA DE ITENS:")
        print("=" * 50)
        
        linhas = texto.split("\n")
        
        # Procurar "páginas"
        idx_paginas = -1
        for i, linha in enumerate(linhas):
            if linha.strip() == "páginas":
                idx_paginas = i
                print(f"\nEncontrou 'páginas' na linha {i}")
                print("Linhas após 'páginas':")
                for j in range(i+1, min(i+15, len(linhas))):
                    print(f"  [{j}] '{linhas[j]}'")
                break
        
        if idx_paginas == -1:
            print("\n'páginas' NÃO ENCONTRADO!")
            print("\nProcurando 'Itens'...")
            for i, linha in enumerate(linhas):
                if "Itens" in linha or "itens" in linha:
                    print(f"  [{i}] '{linha}'")
        
        # Procurar tabela de itens no HTML
        print("\n" + "=" * 50)
        print("VERIFICANDO SE HÁ TABELA DE ITENS:")
        print("=" * 50)
        
        html = page.content()
        if "tabelaItens" in html:
            print("  ✓ Encontrou 'tabelaItens' no HTML")
        else:
            print("  ✗ Não encontrou 'tabelaItens'")
        
        if "Seq" in texto and "Código" in texto:
            print("  ✓ Encontrou headers 'Seq' e 'Código'")
        else:
            print("  ✗ Não encontrou headers de tabela")
        
        # Verificar se é uma licitação sem itens (tipo Adesão)
        if "Adesão" in primeiro or "AD " in primeiro:
            print("\n⚠️  Esta é uma licitação tipo ADESÃO - pode não ter itens!")
        
        print("\nPressione ENTER para fechar...")
        input()
        browser.close()

if __name__ == "__main__":
    main()
