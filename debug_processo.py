"""
Debug detalhado de um único processo
"""
import os
import time
import re
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup

load_dotenv()

PORTAL_BASE = "http://consultalicitacao.curitiba.pr.gov.br:9090"
DETALHE_URL = f"{PORTAL_BASE}/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"

def debug_processo():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        try:
            print("\n[TESTE: PE 21/2019 - Deve ter 1 documento]")
            print("=" * 60)

            # Step 1: Acessar página
            print("\n[1] Acessando portal...")
            page.goto(DETALHE_URL, wait_until='domcontentloaded')
            time.sleep(2)
            print("    OK - Página carregada")

            # Step 2: Procurar link específico
            print("\n[2] Procurando link PE 21/2019...")
            links = page.locator('a[id*="j_id26"]')
            print(f"    Encontrados {links.count()} links de processo")

            # Step 3: Encontrar e clicar no link
            found = False
            for i in range(links.count()):
                link = links.nth(i)
                try:
                    parent_row = link.locator("xpath=ancestor::tr")
                    if parent_row.count() > 0:
                        row_text = parent_row.first.text_content()
                        if "PE 21/2019" in row_text:
                            print(f"    Encontrado no link {i}")
                            print("    Clicando...")
                            link.click()
                            found = True
                            break
                except:
                    continue

            if not found:
                print("    FALHA: Link não encontrado")
                return

            time.sleep(2)
            print("    OK - Clique executado")

            # Step 4: Verificar página de detalhe
            print("\n[3] Verificando página de detalhe...")
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except PlaywrightTimeout:
                print("    WARNING: Timeout esperando networkidle")

            html = page.content()
            with open("debug_detalhe.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("    OK - HTML salvo em debug_detalhe.html")

            # Step 5: Procurar botão modal
            print("\n[4] Procurando botão 'Documentos da licitacao'...")
            modal_btn = page.locator('[id="form:j_id111"]')
            if modal_btn.count() == 0:
                print("    FALHA: Botão j_id111 não encontrado")
                print("    Tentando alternativa...")
                modal_btn = page.locator('input[value="Documentos da licitacao"]')

            if modal_btn.count() > 0:
                print(f"    OK - Botão encontrado ({modal_btn.count()})")

                # Step 6: Clicar no botão
                print("\n[5] Abrindo modal...")
                modal_btn.first.click()
                time.sleep(2)
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except PlaywrightTimeout:
                    print("    WARNING: Timeout esperando modal")

                # Step 7: Procurar tabela de documentos
                print("\n[6] Procurando tabela de documentos...")
                docs_table = page.locator('table[id="form:tabelaDocumentos"]')
                if docs_table.count() > 0:
                    print("    OK - Tabela encontrada")

                    # Step 8: Contar documentos
                    rows = docs_table.locator("tbody tr")
                    num_docs = rows.count()
                    print(f"    Documentos encontrados: {num_docs}")

                    if num_docs > 0:
                        # Mostrar nomes
                        for i in range(min(num_docs, 5)):
                            row = rows.nth(i)
                            texto = row.text_content()
                            print(f"      {i+1}. {texto[:100]}")

                        # Step 9: Procurar primeiro botão de download
                        print("\n[7] Procurando botão de download...")
                        inputs = docs_table.locator("input")
                        print(f"    Inputs encontrados: {inputs.count()}")

                        if inputs.count() > 0:
                            print("    SUCESSO: Pode proceder com download!")
                        else:
                            print("    FALHA: Nenhum botão de download encontrado")

                    else:
                        print("    FALHA: Nenhum documento na tabela")

                    # Salvar HTML do modal
                    html = page.content()
                    with open("debug_modal.html", "w", encoding="utf-8") as f:
                        f.write(html)
                    print("\n    HTML da modal salvo em debug_modal.html")

                else:
                    print("    FALHA: Tabela não encontrada")
                    print("    Salvando HTML para inspeção...")
                    html = page.content()
                    with open("debug_no_table.html", "w", encoding="utf-8") as f:
                        f.write(html)

            else:
                print("    FALHA: Botão de modal não encontrado")
                print("    Salvando HTML para inspeção...")
                html = page.content()
                with open("debug_no_button.html", "w", encoding="utf-8") as f:
                    f.write(html)

            print("\n" + "=" * 60)
            print("Debug concluído - verifique os arquivos .html salvos")

        except Exception as e:
            print(f"\n[ERRO] {e}")
            import traceback
            traceback.print_exc()
        finally:
            browser.close()

if __name__ == "__main__":
    debug_processo()
