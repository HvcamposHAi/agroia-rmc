"""
Diagnóstico: Tenta abrir um único processo e mostra o que acontece
"""
import time
from playwright.sync_api import sync_playwright

PORTAL_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()

    try:
        print("[1] Acessando portal...")
        page.goto(PORTAL_URL, wait_until='domcontentloaded')
        time.sleep(2)

        print("[2] Aguardando elementos da página...")
        time.sleep(3)

        # Procurar pelo primeiro link de processo
        print("[3] Procurando links de processo...")
        links = page.locator('a[id*="j_id26"]')
        print(f"    Encontrados {links.count()} links de processo")

        if links.count() > 0:
            print("[4] Clicando no primeiro link...")
            links.first.click()

            print("[5] Aguardando página de detalhe...")
            time.sleep(3)

            # Verificar se modal está disponível
            modal_btn = page.locator('[id="form:j_id111"]')
            print(f"    Botão modal disponível: {modal_btn.count() > 0}")

            # Capturar HTML para análise
            html = page.content()
            with open("test_single_html.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("[6] HTML salvo em test_single_html.html")

            # Tentar abrir modal
            if modal_btn.count() > 0:
                print("[7] Abrindo modal...")
                modal_btn.first.click()
                time.sleep(2)

                # Verificar documentos
                docs_table = page.locator('table[id="form:tabelaDocumentos"]')
                print(f"    Tabela de documentos encontrada: {docs_table.count() > 0}")

                if docs_table.count() > 0:
                    rows = docs_table.locator("tbody tr")
                    print(f"    Linhas encontradas: {rows.count()}")

        else:
            print("[!] Nenhum link de processo encontrado na página")
            print("[!] HTML da página sendo salvo...")
            with open("test_single_no_links.html", "w", encoding="utf-8") as f:
                f.write(page.content())

        print("\n[OK] Teste concluído - verifique os arquivos HTML salvos")
        input("Pressione ENTER para fechar o browser...")

    except Exception as e:
        print(f"[!] Erro: {e}")
    finally:
        browser.close()
