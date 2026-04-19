"""
Diagnóstico: Testar seleção de órgão no formulário de pesquisa
"""
import os
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from dotenv import load_dotenv

load_dotenv()

PORTAL_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
ORGAO = "SMSAN/FAAC"
HEADLESS = False  # Não headless para ver o que está acontecendo
DEBUG = True

def test_organ_selection():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, slow_mo=500)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        try:
            print(f"[1] Acessando {PORTAL_URL}")
            page.goto(PORTAL_URL, wait_until='domcontentloaded')
            time.sleep(2)

            print(f"[2] Aguardando select elementos...")
            try:
                page.wait_for_selector("select", state="visible", timeout=10000)
                print(f"[✓] Select encontrado")
            except PlaywrightTimeout:
                print(f"[!] Timeout aguardando select")
                html = page.content()
                print(f"Page length: {len(html)}")
                with open("test_organ_page.html", "w", encoding="utf-8") as f:
                    f.write(html)
                return

            time.sleep(1)

            print(f"[3] Procurando select com opção '{ORGAO}'")
            selects = page.locator("select")
            num_selects = selects.count()
            print(f"  Total de selects na página: {num_selects}")

            for i in range(num_selects):
                sel = selects.nth(i)
                try:
                    # Tenter obter o name do select
                    select_attr = sel.get_attribute("id")
                    select_name = sel.get_attribute("name")
                    print(f"  Select [{i}] id={select_attr} name={select_name}")

                    # Listar opções
                    options = sel.locator("option")
                    num_options = options.count()
                    print(f"    Opções: {num_options}")

                    for j in range(min(5, num_options)):  # Mostrar primeiras 5
                        opt_text = options.nth(j).get_attribute("innerText") or options.nth(j).text_content()
                        print(f"      [{j}] {opt_text}")

                    # Procurar por SMSAN/FAAC
                    if sel.locator(f'option:has-text("{ORGAO}")').count() > 0:
                        print(f"  ✓ {ORGAO} encontrado no select [{i}]!")
                        sel.select_option(label=ORGAO)
                        time.sleep(2)
                        print(f"  ✓ Órgão selecionado com sucesso!")
                        return True
                except Exception as e:
                    print(f"    Erro ao processar select [{i}]: {e}")

            print(f"[!] {ORGAO} não encontrado em nenhum select")
            return False

        finally:
            browser.close()

if __name__ == "__main__":
    result = test_organ_selection()
    print(f"\nResultado: {result}")
