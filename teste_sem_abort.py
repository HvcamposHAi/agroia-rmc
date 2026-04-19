"""
Teste SEM abort: Deixar popup abrir naturalmente e capturar response via page.on
"""

import os, time
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

PORTAL_URL = 'http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf'

print('TESTE SEM ABORT: Deixar popup abrir e capturar resposta')
print('=' * 70)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=80)
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()

    # REGISTRAR LISTENER GLOBAL ANTES DE TUDO
    pdf_capturado = []

    def on_response(response):
        if 'download.jsf' in response.url:
            ct = response.headers.get('content-type', '')
            try:
                body = response.body()
                tamanho = len(body)
                eh_pdf = body[:4] == b'%PDF'
                pdf_capturado.append({'tamanho': tamanho, 'pdf': eh_pdf, 'ct': ct})
                print(f'[response] {tamanho}b, PDF={eh_pdf}, CT={ct[:30]}')
            except Exception as e:
                print(f'[response-err] {e}')

    page.on('response', on_response)
    print('[1] Listener registrado')

    # Navegar e processar
    page.goto(PORTAL_URL, wait_until='domcontentloaded')
    time.sleep(2)
    print('[2] Portal carregado')

    # Pesquisa rápida
    print('[3] Fazendo pesquisa...')
    try:
        page.wait_for_selector("select", state="visible", timeout=20000)
    except:
        pass
    time.sleep(1)

    # Selecionar órgão
    selects = page.locator("select")
    if selects.count() > 0:
        selects.nth(0).select_option(index=1)
        time.sleep(1)

    # Clicar pesquisar
    btn = page.locator('[id="form:btSearch"]')
    if btn.count() == 0:
        btn = page.locator('input[value="Pesquisar"]')
    if btn.count() > 0:
        btn.first.click()
        time.sleep(3)
        try:
            page.wait_for_load_state('networkidle', timeout=30000)
        except:
            pass

    print('[3B] Pesquisa completa')

    # Ir direto para um PE
    links = page.locator('tbody tr a[onclick*="abrirDetalhe"]')
    if links.count() > 0:
        print('[4] Abrindo primeiro PE...')
        links.nth(0).click()
        time.sleep(2)
        try:
            page.wait_for_load_state('networkidle', timeout=30000)
        except:
            pass

        # Abrir documentos
        btn_doc = page.locator('[id="form:j_id111"]')
        if btn_doc.count() > 0:
            print('[5] Abrindo modal...')
            btn_doc.first.click()
            time.sleep(2)

            # Clicar primeiro documento
            btn_dl = page.locator('[id="form:tabelaDocumentos:0:j_id283"]')
            if btn_dl.count() > 0:
                print('[6] Clicando documento...')
                btn_dl.first.click()
                time.sleep(1)

                # Aguardar AJAX
                try:
                    page.wait_for_load_state('networkidle', timeout=15000)
                except:
                    pass
                time.sleep(1)

                print('[7] Aguardando response de download.jsf...')
                for i in range(20):
                    time.sleep(0.5)
                    if pdf_capturado:
                        print(f'[8] PDF capturado apos {(i+1)*0.5:.1f}s!')
                        break
                else:
                    print('[8] Timeout - nenhuma response')

    print('\n' + '=' * 70)
    print(f'PDFs capturados: {len(pdf_capturado)}')
    if pdf_capturado:
        for p in pdf_capturado:
            print(f'  {p}')

    browser.close()
