"""
AgroIA-RMC — Teste: Download via context.route (interceptar download.jsf)
=========================================================================

Estrategia CORRIGIDA:
1. Registrar route para interceptar request de download.jsf
2. Deixar AJAX request completar normalmente (servidor guarda doc ID na sessao)
3. Deixar open_download() navegar normalmente para download.jsf
4. Route handler intercepta a RESPONSE e captura os bytes
5. Deixar response passar (route.continue())

Este script testa com 1 licitacao real PE.
"""

import os
import time
import json
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

PORTAL_URL = (
    "http://consultalicitacao.curitiba.pr.gov.br:9090/"
    "ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
)

ORGAO      = "SMSAN/FAAC"
DT_INICIO  = "01/01/2024"
DT_FIM     = "31/12/2024"
HEADLESS   = False
SLOW_MO    = 80

def preencher_data(page, campo_id, valor):
    campo = page.locator(f'[id="{campo_id}"]')
    if campo.count() == 0:
        return False
    try:
        campo.wait_for(state="visible", timeout=15000)
    except PlaywrightTimeout:
        return False
    campo.click(click_count=3)
    time.sleep(0.2)
    page.keyboard.type(valor, delay=50)
    time.sleep(0.3)
    page.keyboard.press("Tab")
    time.sleep(0.5)
    return True


def _selecionar_opcao(page, texto_opcao):
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

    _selecionar_opcao(page, ORGAO)
    preencher_data(page, "form:dataInferiorInputDate", DT_INICIO)
    preencher_data(page, "form:j_id18InputDate", DT_FIM)

    btn = page.locator('[id="form:btSearch"], input[value="Pesquisar"]')
    if btn.count() == 0:
        return 0
    try:
        btn.first.wait_for(state="visible", timeout=15000)
    except PlaywrightTimeout:
        return 0
    btn.first.click()
    time.sleep(3)
    try:
        page.wait_for_load_state("networkidle", timeout=30000)
    except PlaywrightTimeout:
        pass
    time.sleep(1)
    return 1


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
            if not proc_texto.startswith("PE "):  # Apenas PE para teste
                continue
            link = cols[0].find("a")
            link_id = link.get("id", "") if link else ""
            processos.append({"texto": proc_texto, "link_id": link_id})
        break
    return processos


def abrir_detalhe(page, processo):
    link_id = processo.get("link_id", "")
    if not link_id:
        return False
    try:
        elem = page.locator(f'[id="{link_id}"]')
        if elem.count() == 0:
            return False
        elem.first.click()
        time.sleep(1.5)
        page.wait_for_load_state("networkidle", timeout=30000)
        return True
    except Exception:
        return False


def voltar_para_lista(page):
    try:
        aba = page.locator('[id="form:abaPesquisa_lbl"]')
        if aba.count() > 0:
            aba.first.click()
            time.sleep(1.5)
            page.wait_for_load_state("networkidle", timeout=15000)
            return True
    except:
        pass
    return False


def testar_download_route(page, processo_nome):
    """
    ESTRATEGIA VIA CONTEXT.ROUTE:
    1. Registrar handler para interceptar request a download.jsf
    2. Handler captura response SEM abortar
    3. Deixa request passar normalmente
    """

    print(f"\n  [TESTE] Testando download para: {processo_nome}")

    btn_doc = page.locator('[id="form:j_id111"]')
    print(f"  [DBG] Botao encontrado: {btn_doc.count()}")

    if btn_doc.count() == 0:
        print(f"  [ERR] Botao nao encontrado")
        return None

    resultado = {
        "processo": processo_nome,
        "tempo_inicio": datetime.now().isoformat(),
        "download_interceptado": False,
        "tamanho_bytes": 0,
        "content_type": "",
        "eh_pdf": False,
        "eh_html": False,
        "erro": None
    }

    # Estado compartilhado para capturar a resposta
    respostas_capturadas = []

    def handle_download_route(route):
        """Intercepta request a download.jsf - deixa passar normalmente"""
        url = route.request.url
        if "download" in url.lower():
            print(f"  [route] Request interceptado: {url[:80]}")
            respostas_capturadas.append({"url": url, "interceptado": True})

        # Deixar request passar normalmente (sem fazer fetch)
        try:
            route.continue_()
        except Exception as e:
            try:
                route.abort()
            except:
                pass

    try:
        # Registrar listeners para monitorar TODAS as requisicoes
        todas_requests = []
        todas_responses = []

        def log_request(request):
            url = request.url
            todas_requests.append({"url": url, "method": request.method})

        def log_response(response):
            url = response.url
            todas_responses.append({"url": url, "status": response.status})

        page.on("request", log_request)
        page.on("response", log_response)

        # Response listener especifico para download.jsf
        def handle_download_response(response):
            if "download" in response.url.lower():
                print(f"  [resp] Download response: {response.status} {response.url[:80]}")
                ct = response.headers.get("content-type", "")
                print(f"  [resp] Content-Type: {ct}")
                try:
                    body = response.body()
                    eh_pdf = ct.lower().startswith("application/pdf") or body[:4] == b"%PDF"
                    eh_html = "text/html" in ct or body[:100].startswith(b"<!DOCTYPE") or body[:100].startswith(b"<html")
                    respostas_capturadas.append({
                        "url": response.url,
                        "status": response.status,
                        "content_type": ct,
                        "tamanho": len(body),
                        "eh_pdf": eh_pdf,
                        "eh_html": eh_html
                    })
                    print(f"  [resp] OK: {len(body)} bytes, PDF={eh_pdf}")
                except Exception as e:
                    print(f"  [resp] Erro ao ler: {e}")

        page.on("response", handle_download_response)

        # Registrar route ANTES de clicar (match qualquer coisa em /download/)
        print(f"  [1] Registrando route handler para download...")
        page.context.route("**/pages/download/**", handle_download_route)
        page.context.route("**/download.jsf**", handle_download_route)

        # Passo 1: Clicar botao "Documentos da licitacao" para abrir modal
        print(f"  [2] Clicando botao para abrir modal...")
        btn_doc.first.click()

        # Aguardar modal e tabela carregarem
        print(f"  [2] Aguardando modal carregar...")
        try:
            page.wait_for_selector('[id="form:documentos"]', state="visible", timeout=10000)
            print(f"    Modal encontrado")
        except PlaywrightTimeout:
            print(f"    Timeout esperando modal visivel")

        try:
            page.wait_for_selector('[id="form:tabelaDocumentos"]', state="visible", timeout=10000)
            print(f"    Tabela encontrada")
        except PlaywrightTimeout:
            print(f"    Timeout esperando tabela")

        time.sleep(1)

        # Passo 2: Procurar botao de download no modal
        print(f"  [3] Procurando botao de download...")
        btn_download = page.locator('[id="form:tabelaDocumentos:0:j_id283"]')
        print(f"    [id=form:tabelaDocumentos:0:j_id283]: {btn_download.count()}")

        if btn_download.count() == 0:
            # Procurar qualquer input type=image no modal
            btn_download = page.locator('div[id="form:documentos"] input[type="image"]')
            print(f"    inputs type=image em modal: {btn_download.count()}")

        if btn_download.count() == 0:
            # Procurar todos os inputs no modal
            todos_inputs = page.locator('[id="form:documentos"] input')
            print(f"    todos os inputs no modal: {todos_inputs.count()}")
            if todos_inputs.count() > 0:
                btn_download = todos_inputs.filter(has_role="button").first
                if btn_download.count() == 0:
                    btn_download = todos_inputs.first
                print(f"    usando primeiro input: count={btn_download.count()}")

        if btn_download.count() == 0:
            print(f"  [ERR] Nenhum botao de download encontrado no modal")
            # Salvar HTML para debug
            with open("debug_modal_nao_encontrado.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            raise Exception("Modal ou botao de download nao encontrados")

        # Verificar se open_download existe
        try:
            tem_open_download = page.evaluate('typeof open_download')
            print(f"  [DBG] Tipo de open_download: {tem_open_download}")
        except Exception as e:
            print(f"  [DBG] Erro ao verificar open_download: {e}")

        print(f"  [3] Clicando botao de download dentro do modal...")
        btn_download.first.click()

        # Aguardar responses
        print(f"  [4] Aguardando responses...")
        for i in range(20):  # Aguardar ate 10 segundos
            time.sleep(0.5)
            if respostas_capturadas:
                print(f"  [4] Response capturada apos {(i+1)*0.5:.1f}s")
                break
        else:
            print(f"  [4] Timeout - nenhuma response capturada")

        # Debug: imprimir todas as requests/responses
        print(f"\n  [DEBUG] Total de requests: {len(todas_requests)}")
        for req in todas_requests[-5:]:  # Ultimas 5
            print(f"    REQ: {req['method']} {req['url'][:100]}")
        print(f"  [DEBUG] Total de responses: {len(todas_responses)}")
        for resp in todas_responses[-5:]:  # Ultimas 5
            print(f"    RESP: {resp['status']} {resp['url'][:100]}")

        # Processar respostas
        if respostas_capturadas:
            resultado["download_interceptado"] = True
            resp = respostas_capturadas[0]
            resultado["tamanho_bytes"] = resp.get("tamanho", 0)
            resultado["content_type"] = resp.get("content_type", "")
            resultado["eh_pdf"] = resp.get("eh_pdf", False)
            resultado["eh_html"] = resp.get("eh_html", False)
            print(f"  [4] OK! Capturado: {resultado['tamanho_bytes']} bytes, PDF={resultado['eh_pdf']}")
        else:
            print(f"  [4] Nenhuma response de download interceptada")

    except Exception as e:
        resultado["erro"] = str(e)
        print(f"  [ERR] {e}")

    finally:
        # Remover route
        try:
            page.context.unroute("**/download/download.jsf**")
        except:
            pass

    resultado["tempo_fim"] = datetime.now().isoformat()
    return resultado


def main():
    with sync_playwright() as p:
        print("=" * 70)
        print("TESTE: Download via context.route (ESTRATEGIA CORRIGIDA)")
        print("=" * 70)

        browser = p.chromium.launch(headless=HEADLESS, slow_mo=SLOW_MO)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        print(f"\n[SETUP] Acessando portal...")
        page.goto(PORTAL_URL, wait_until="domcontentloaded")
        time.sleep(2)

        print(f"[SETUP] Fazendo pesquisa...")
        fazer_pesquisa(page)

        print(f"[SETUP] Extraindo processos...")
        processos = extrair_processos_pagina(page)
        if not processos:
            print("[ERR] Nenhum processo PE encontrado")
            browser.close()
            return

        print(f"[SETUP] Encontrados {len(processos)} processos PE")

        # Testar primeiro PE
        proc = processos[0]
        print(f"\n[TESTE] Abrindo detalhe: {proc['texto']}")
        if not abrir_detalhe(page, proc):
            print("[ERR] Falha ao abrir detalhe")
            browser.close()
            return

        # Executar teste
        resultado = testar_download_route(page, proc['texto'])

        # Salvar resultado
        with open("teste_download_route_resultado.json", "w") as f:
            json.dump(resultado, f, indent=2, ensure_ascii=False)

        print(f"\n[RESULTADO]")
        print(f"  Download interceptado: {resultado['download_interceptado']}")
        if resultado['download_interceptado']:
            print(f"  Tamanho: {resultado['tamanho_bytes']} bytes")
            print(f"  Content-Type: {resultado['content_type']}")
            print(f"  eh_pdf: {resultado['eh_pdf']}")
            print(f"  eh_html: {resultado['eh_html']}")
        if resultado['erro']:
            print(f"  Erro: {resultado['erro']}")

        browser.close()

    print(f"\n[OK] Resultado salvo em teste_download_route_resultado.json")

if __name__ == "__main__":
    main()
