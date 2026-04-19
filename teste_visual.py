"""
AgroIA-RMC — Teste Visual de Captura
====================================
Este script aguarda você navegar MANUALMENTE até a página
que mostra a tabela com LEITE, MANDIOCA, etc.

IMPORTANTE: Só pressione ENTER quando você VER na tela:
- Seq | Código | Descrição | Qt. Solicitada | UN | Valor
- LEITE, MANDIOCA/AIPIM, etc.

Execute: python teste_visual.py
"""
import time
from playwright.sync_api import sync_playwright

FORM_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"

def main():
    print("=" * 70)
    print("TESTE VISUAL DE CAPTURA")
    print("=" * 70)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)
        page = browser.new_page()
        
        print("\n[1] Abrindo portal...")
        page.goto(FORM_URL, timeout=60000)
        page.wait_for_load_state("networkidle")
        
        print("\n" + "=" * 70)
        print("INSTRUÇÕES - FAÇA MANUALMENTE NO NAVEGADOR:")
        print("=" * 70)
        print("""
1. Selecione o órgão: SMSAN/FAAC
2. Preencha as datas: 01/01/2019 a 31/12/2025
3. Clique em PESQUISAR
4. Na lista, encontre e clique em: DS 73/2019 - SMSAN/FAAC
   (é uma dispensa com objeto "Aquisição de produtos alimentícios")
5. AGUARDE a página carregar completamente
6. VERIFIQUE que você consegue VER na tela:
   - A tabela com colunas: Seq | Código | Descrição | Qt. Solicitada
   - Os itens: LEITE, MANDIOCA/AIPIM
   
SÓ PRESSIONE ENTER QUANDO VOCÊ ESTIVER VENDO A TABELA DE ITENS!
        """)
        print("=" * 70)
        
        input("\n>>> Pressione ENTER quando VOCÊ ESTIVER VENDO a tabela com LEITE, MANDIOCA...")
        
        print("\n[2] Capturando página atual...")
        
        # Salvar screenshot
        page.screenshot(path="captura_visual.png", full_page=True)
        print("    Screenshot: captura_visual.png")
        
        # Salvar HTML
        html = page.content()
        with open("captura_visual.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"    HTML: captura_visual.html ({len(html)} chars)")
        
        # Verificar se LEITE está no HTML
        print("\n[3] Verificando conteúdo...")
        
        if "LEITE" in html.upper():
            print("    ✓ 'LEITE' encontrado no HTML!")
        else:
            print("    ✗ 'LEITE' NÃO encontrado no HTML")
            print("    >>> Você tem certeza que a tabela de itens estava visível?")
        
        if "MANDIOCA" in html.upper() or "AIPIM" in html.upper():
            print("    ✓ 'MANDIOCA/AIPIM' encontrado no HTML!")
        else:
            print("    ✗ 'MANDIOCA/AIPIM' NÃO encontrado no HTML")
        
        if "89.06.06" in html:
            print("    ✓ Código '89.06.06' encontrado!")
        else:
            print("    ✗ Código '89.06.06' NÃO encontrado")
        
        # Contar tabelas
        tabelas = page.query_selector_all("table")
        print(f"\n    Total de tabelas: {len(tabelas)}")
        
        # Buscar texto visível na página
        print("\n[4] Texto visível na página (primeiros 2000 chars):")
        texto = page.inner_text("body")[:2000]
        print("-" * 40)
        print(texto)
        print("-" * 40)
        
        print("\n[5] Pressione ENTER para fechar...")
        input()
        
        browser.close()
    
    print("\nArquivos gerados:")
    print("  - captura_visual.png (screenshot)")
    print("  - captura_visual.html (HTML)")
    print("\nEnvie esses arquivos para análise se o LEITE não foi encontrado.")

if __name__ == "__main__":
    main()
