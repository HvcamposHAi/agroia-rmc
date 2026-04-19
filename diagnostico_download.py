"""
Diagnóstico: Entender exatamente como funciona o clique em documentos
======================================================================
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
    """Preencher campo de data"""
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
    """Selecionar opção em SELECT"""
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
                print(f"    OK {debug_label}")
                return True
        except PlaywrightTimeout:
            continue
    return False

def fazer_pesquisa(page):
    """Fazer pesquisa"""
    print("[Pesquisa] Aguardando elementos...")
    try:
        page.wait_for_selector("select", state="visible", timeout=20000)
    except PlaywrightTimeout:
        pass
    time.sleep(1)

    print("[Pesquisa] Preenchendo filtros...")
    selecionar_opcao(page, ORGAO, "Orgao")
    preencher_data(page, "form:dataInferiorInputDate", DT_INICIO)
    preencher_data(page, "form:j_id18InputDate", DT_FIM)

    print("[Pesquisa] Enviando...")
    btn = page.locator('[id="form:btSearch"], input[value="Pesquisar"]')
    btn.first.click()
    time.sleep(3)
    try:
        page.wait_for_load_state("networkidle", timeout=30000)
    except PlaywrightTimeout:
        pass
    time.sleep(1)

def extrair_processos_pagina(page):
    """Extrair processos"""
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
            print("\n" + "=" * 70)
            print("DIAGNOSTICO: Como funcionam os downloads")
            print("=" * 70)

            # Acessar portal
            print(f"\n[1] Acessando portal...")
            page.goto(PORTAL_URL, wait_until='domcontentloaded')
            time.sleep(2)

            # Fazer pesquisa
            print(f"\n[2] Fazendo pesquisa...")
            fazer_pesquisa(page)

            # Extrair processos
            print(f"\n[3] Extraindo processos...")
            processos = extrair_processos_pagina(page)
            print(f"    Encontrados: {len(processos)} processos")

            if not processos:
                print("[!] Nenhum processo encontrado")
                return

            # Tentar abrir processos até encontrar um com documentos
            print(f"\n[4] Procurando processo com documentos...")
            processo_aberto = None

            for processo in processos[:3]:  # Tentar primeiros 3
                print(f"    Tentando: {processo['texto']}")

                link = page.locator(f"[id=\"{processo['link_id']}\"]")
                if link.count() == 0:
                    print(f"      [!] Link não encontrado")
                    continue

                link.first.click()
                time.sleep(1.5)
                try:
                    page.wait_for_load_state("networkidle", timeout=30000)
                except:
                    pass

                # Abrir modal de documentos
                modal_btn = page.locator('[id="form:j_id111"]')
                if modal_btn.count() == 0:
                    modal_btn = page.locator('input[value="Documentos da licitacao"]')

                if modal_btn.count() > 0:
                    print(f"      [OK] Botão encontrado!")
                    processo_aberto = processo
                    break
                else:
                    print(f"      [!] Sem documentos")
                    # Voltar para lista
                    volta = page.locator('[id="form:abaPesquisa_lbl"]')
                    if volta.count() > 0:
                        volta.first.click()
                        time.sleep(1.5)

            if not processo_aberto:
                print("[!] Nenhum processo com documentos encontrado")
                return

            print(f"\n[5] Abrindo modal de documentos...")

            modal_btn.first.click()
            time.sleep(2)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except PlaywrightTimeout:
                pass

            # Salvar HTML da modal
            print(f"\n[6] Salvando HTML...")
            html = page.content()
            with open("diagnostico_modal.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("    OK - Salvo em diagnostico_modal.html")

            # Analisar estrutura da tabela
            print(f"\n[7] Analisando tabela de documentos...")
            soup = BeautifulSoup(html, "lxml")
            tabela = soup.find("table", id="form:tabelaDocumentos")

            if not tabela:
                print("    [!] Tabela não encontrada no HTML")
            else:
                rows = tabela.find_all("tr")[1:]
                print(f"    Linhas encontradas: {len(rows)}")

                if rows:
                    # Analisar primeira linha
                    primeiro_tr = rows[0]
                    tds = primeiro_tr.find_all("td")
                    print(f"\n    Primeira linha:")
                    for j, td in enumerate(tds):
                        print(f"      Col {j}: {td.get_text(strip=True)[:50]}")

                    # Procurar botão de download
                    print(f"\n    Procurando botões...")
                    inputs = primeiro_tr.find_all("input")
                    print(f"      <input> tags: {len(inputs)}")
                    for inp in inputs:
                        print(f"        ID: {inp.get('id', 'N/A')}")
                        print(f"        Type: {inp.get('type', 'N/A')}")
                        print(f"        Value: {inp.get('value', 'N/A')}")
                        print(f"        onclick: {inp.get('onclick', 'N/A')[:100] if inp.get('onclick') else 'N/A'}")

                    # Procurar links
                    links = primeiro_tr.find_all("a")
                    print(f"      <a> tags: {len(links)}")
                    for link in links:
                        print(f"        href: {link.get('href', 'N/A')}")

            # Tentar clicar no primeiro botão de download
            print(f"\n[8] Tentando clicar em documento...")
            tabela_locator = page.locator('table[id="form:tabelaDocumentos"]')
            if tabela_locator.count() > 0:
                rows = tabela_locator.locator("tbody tr")
                if rows.count() > 0:
                    primeira_linha = rows.nth(0)
                    inputs = primeira_linha.locator("input")

                    print(f"    Inputs encontrados: {inputs.count()}")

                    if inputs.count() > 0:
                        print(f"    Clicando no primeiro input...")

                        # Monitorar requisições de download
                        downloads_capturados = []

                        def handle_download(download):
                            downloads_capturados.append({
                                'name': download.suggested_filename,
                                'path': download.path
                            })
                            print(f"    [DOWNLOAD CAPTURADO] {download.suggested_filename}")

                        page.on("download", handle_download)

                        # Tentar clicar
                        try:
                            with page.expect_download(timeout=10000) as download_info:
                                inputs.first.click()
                                time.sleep(1)
                            download = download_info.value
                            print(f"    [OK] Download capturado: {download.suggested_filename}")
                        except Exception as e:
                            print(f"    [!] Erro: {e}")

                        time.sleep(2)

            print("\n" + "=" * 70)
            print("DIAGNOSTICO CONCLUÍDO")
            print("=" * 70)

        except Exception as e:
            print(f"\n[ERRO] {e}")
            import traceback
            traceback.print_exc()
        finally:
            browser.close()

if __name__ == "__main__":
    main()
