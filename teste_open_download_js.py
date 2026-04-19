"""
Teste: Chamar open_download() via JavaScript após AJAX
"""

import os
import time
from datetime import datetime
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

PORTAL_URL = 'http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf'

print('=' * 70)
print('TESTE: Chamar open_download() via JavaScript')
print('=' * 70)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=80)
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()

    # Registrar interceptor ANTES de tudo
    arquivo_capturado = {'bytes': None, 'ct': ''}

    def handle_route(route):
        try:
            resp = route.fetch()
            body = resp.body()
            ct = resp.headers.get('content-type', '')
            arquivo_capturado['bytes'] = body
            arquivo_capturado['ct'] = ct
            print(f'[capture] {len(body)} bytes, CT={ct[:40]}')

            # Deixar response passar
            try:
                route.continue_(response=resp)
            except TypeError:
                route.continue_()

        except Exception as e:
            print(f'[capture-err] {e}')
            try:
                route.continue_()
            except:
                pass

    page.context.route('**/download.jsf**', handle_route)
    print('[1] Interceptor registrado')

    page.goto(PORTAL_URL, wait_until='domcontentloaded')
    time.sleep(2)
    print('[2] Portal carregado')

    # Fazer pesquisa
    print('[2B] Fazendo pesquisa SMSAN/FAAC 2024...')
    try:
        page.wait_for_selector("select", state="visible", timeout=20000)
    except:
        pass
    time.sleep(1)

    # Selecionar órgão
    selects = page.locator("select")
    for i in range(selects.count()):
        sel = selects.nth(i)
        try:
            if sel.locator('option:has-text("SMSAN/FAAC")').count() > 0:
                sel.select_option(label='SMSAN/FAAC')
                time.sleep(1)
                break
        except:
            continue

    # Preencher datas
    data_init = page.locator('[id="form:dataInferiorInputDate"]')
    if data_init.count() > 0:
        data_init.click(click_count=3)
        time.sleep(0.2)
        page.keyboard.type('01/01/2024')
        time.sleep(0.3)
        page.keyboard.press('Tab')
        time.sleep(0.5)

    # Pesquisar
    btn_search = page.locator('[id="form:btSearch"], input[value="Pesquisar"]')
    if btn_search.count() > 0:
        btn_search.first.click()
        time.sleep(3)
        try:
            page.wait_for_load_state('networkidle', timeout=30000)
        except:
            pass
        time.sleep(1)

    print('[2C] Pesquisa completada')

    # Navegar para um PE específico
    print('[3] Procurando um PE...')
    links = page.locator("tbody tr a[onclick*='abrirDetalhe']")
    count = links.count()
    print(f'    Encontrados {count} processos')

    # Abrir o primeiro
    if count > 0:
        links.nth(0).click()
        time.sleep(2)
        try:
            page.wait_for_load_state('networkidle', timeout=30000)
        except:
            pass
        print('[4] PE aberto')

        # Abrir modal documentos
        btn_doc = page.locator('[id="form:j_id111"]')
        if btn_doc.count() > 0:
            print('[5] Abrindo modal documentos...')
            btn_doc.first.click()
            time.sleep(2)

            # Procurar botao de download
            btn_dl = page.locator('[id="form:tabelaDocumentos:0:j_id283"]')
            if btn_dl.count() > 0:
                print('[6] Clicando botao de download...')
                btn_dl.first.click()
                time.sleep(1)

                # Aguardar AJAX
                try:
                    page.wait_for_load_state('networkidle', timeout=15000)
                except:
                    pass
                print('[7] AJAX completou (networkidle)')
                time.sleep(1)

                # Chamar open_download() via JavaScript
                print('[8] Chamando open_download via JS...')
                try:
                    page.evaluate("open_download('/ConsultaLicitacoes')")
                    print('[9] open_download() chamado via JS')
                    time.sleep(3)
                except Exception as e:
                    print(f'[!] Erro ao chamar open_download: {e}')

                # Verificar resultado
                if arquivo_capturado['bytes']:
                    tamanho = len(arquivo_capturado['bytes'])
                    eh_pdf = arquivo_capturado['bytes'][:4] == b'%PDF'
                    ct = arquivo_capturado['ct']
                    print(f'\n[RESULTADO] ✓ {tamanho} bytes capturados, PDF={eh_pdf}')
                    if not eh_pdf:
                        preview = arquivo_capturado['bytes'][:100]
                        print(f'    Preview: {preview}')
                else:
                    print('[RESULTADO] ✗ Nenhum arquivo capturado')
            else:
                print('[!] Botao de download nao encontrado')
        else:
            print('[!] Botao documentos nao encontrado')

    browser.close()

print('=' * 70)
