"""
Encontrar processes que definitivamente têm documentos
Vai verificar um número maior de processos até encontrar um com docs
"""
import os
import time
import re
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup

load_dotenv()

PORTAL_URL = (
    "http://consultalicitacao.curitiba.pr.gov.br:9090/"
    "ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
)

ORGAO = "SMSAN/FAAC"
DT_INICIO = "01/01/2019"
DT_FIM = "30/04/2026"

def preencher_data(page, campo_id, valor):
    campo = page.locator(f'[id="{campo_id}"]')
    try:
        campo.wait_for(state="visible", timeout=15000)
        campo.click(click_count=3)
        time.sleep(0.2)
        page.keyboard.type(valor, delay=50)
        time.sleep(0.3)
        page.keyboard.press("Tab")
        time.sleep(0.5)
        return True
    except:
        return False

def selecionar_opcao(page, texto_opcao, debug_label):
    selects = page.locator("select")
    for i in range(selects.count()):
        sel = selects.nth(i)
        try:
            if sel.locator(f'option:has-text("{texto_opcao}")').count() > 0:
                sel.wait_for(state="visible", timeout=10000)
                sel.select_option(label=texto_opcao)
                time.sleep(1)
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except PlaywrightTimeout:
                    pass
                time.sleep(0.5)
                return True
        except PlaywrightTimeout:
            continue
    return False

def fazer_pesquisa(page):
    try:
        page.wait_for_selector("select", state="visible", timeout=20000)
    except PlaywrightTimeout:
        pass
    time.sleep(1)

    selecionar_opcao(page, ORGAO, "Orgao")
    preencher_data(page, "form:dataInferiorInputDate", DT_INICIO)
    preencher_data(page, "form:j_id18InputDate", DT_FIM)

    btn = page.locator('[id="form:btSearch"], input[value="Pesquisar"]')
    btn.first.click()
    time.sleep(3)
    try:
        page.wait_for_load_state("networkidle", timeout=30000)
    except PlaywrightTimeout:
        pass
    time.sleep(1)

def extrair_processos_pagina(page):
    soup = BeautifulSoup(page.content(), "lxml")
    processos = []
    for tabela in soup.find_all("table"):
        ths = [th.get_text(strip=True).lower() for th in tabela.find_all("th")]
        if "processo" not in ths or "objeto" not in ths:
            continue
        for tr in tabela.find_all("tr")[1:]:
            cols = tr.find_all("td")
            if len(cols) < 3:
                continue
            proc_texto = cols[0].get_text(strip=True)
            if not re.match(r"^[A-Z]{2}\s+\d+/\d{4}", proc_texto):
                continue
            link = cols[0].find("a")
            link_id = link.get("id", "") if link else ""
            processos.append({"texto": proc_texto, "link_id": link_id})
        break
    return processos

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        try:
            print("\nProcurando processos com documentos...")
            print("=" * 70)

            page.goto(PORTAL_URL, wait_until='domcontentloaded')
            time.sleep(2)

            fazer_pesquisa(page)

            # Procurar em 50 processos
            processos_testados = 0
            pagina = 0

            while processos_testados < 50:
                processos = extrair_processos_pagina(page)

                if not processos:
                    print("[!] Nenhum processo encontrado")
                    break

                for proc in processos:
                    if processos_testados >= 50:
                        break

                    print(f"\n[{processos_testados + 1}] Testando: {proc['texto']}")

                    link = page.locator(f"[id=\"{proc['link_id']}\"]")
                    if link.count() == 0:
                        print("      [!] Link não encontrado")
                        continue

                    link.first.click()
                    time.sleep(1.5)
                    try:
                        page.wait_for_load_state("networkidle", timeout=30000)
                    except:
                        pass

                    # Procurar botão de documentos
                    modal_btn = page.locator('[id="form:j_id111"]')
                    if modal_btn.count() > 0:
                        # Abrir modal
                        modal_btn.first.click()
                        time.sleep(2)
                        try:
                            page.wait_for_load_state("networkidle", timeout=15000)
                        except:
                            pass

                        # Verificar se há documentos
                        html = page.content()
                        soup = BeautifulSoup(html, "lxml")
                        tabela = soup.find("table", id="form:tabelaDocumentos")

                        if tabela:
                            rows = tabela.find_all("tr")[1:]
                            print(f"      Documentos: {len(rows)}")

                            if len(rows) > 0:
                                print(f"      [ENCONTRADO COM {len(rows)} DOCUMENTOS!!!]")
                                print(f"\n      Primeira linha:")
                                primeiro_tr = rows[0]
                                tds = primeiro_tr.find_all("td")
                                for j, td in enumerate(tds):
                                    print(f"        Col {j}: {td.get_text(strip=True)[:60]}")

                                # Salvar HTML para análise posterior
                                nome_safe = re.sub(r'[/\\:*?"<>|]', '_', proc['texto'])
                                with open(f"encontrado_{nome_safe}.html", "w", encoding="utf-8") as f:
                                    f.write(html)
                                return proc['texto']
                        else:
                            print(f"      [!] Tabela não encontrada")

                        # Fechar modal
                        try:
                            page.evaluate("Richfaces.hideModalPanel('form:documentos')")
                        except:
                            pass
                        time.sleep(1)

                    else:
                        print(f"      [!] Sem botão de documentos")

                    # Voltar para lista
                    volta = page.locator('[id="form:abaPesquisa_lbl"]')
                    if volta.count() > 0:
                        volta.first.click()
                        time.sleep(1.5)

                    processos_testados += 1

                # Próxima página
                proximo = page.locator('a[onclick*="datascroller_next"]').first
                if proximo.count() > 0:
                    proximo.click()
                    time.sleep(2)
                    pagina += 1
                else:
                    break

            print("\n" + "=" * 70)
            print(f"Nenhum processo com documentos encontrado em {processos_testados} testados")

        except Exception as e:
            print(f"[ERRO] {e}")
            import traceback
            traceback.print_exc()
        finally:
            browser.close()

if __name__ == "__main__":
    main()
