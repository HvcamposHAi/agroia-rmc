"""
AgroIA-RMC — Teste: Download via requests APOS AJAX completar
============================================================

Estrategia CORRIGIDA (aprendido do diagnostico):
1. Clicar botao de download (triggers AJAX request)
2. Aguardar AJAX completar (resposta volta)
3. Servidor ja tem document ID na sessao
4. AGORA fazer requests.get() com cookies da sessao Playwright
5. PDF deve vir corretamente

A chave é: AJAX must complete ANTES de requests.get()!
"""

import os
import time
import json
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
import requests
from dotenv import load_dotenv

load_dotenv()

PORTAL_URL = (
    "http://consultalicitacao.curitiba.pr.gov.br:9090/"
    "ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
)
DOWNLOAD_URL = (
    "http://consultalicitacao.curitiba.pr.gov.br:9090/"
    "ConsultaLicitacoes/pages/download/download.jsf"
)

ORGAO      = "SMSAN/FAAC"
DT_INICIO  = "01/01/2024"
DT_FIM     = "31/12/2024"

def preencher_data(page, campo_id, valor):
    campo = page.locator(f'[id="{campo_id}"]')
    if campo.count() == 0:
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
                sel.select_option(label=texto_opcao)
                time.sleep(1)
                return True
        except:
            continue
    return False


def fazer_pesquisa(page):
    try:
        page.wait_for_selector("select", state="visible", timeout=20000)
    except:
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
    except:
        return 0
    btn.first.click()
    time.sleep(3)
    try:
        page.wait_for_load_state("networkidle", timeout=30000)
    except:
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
            if not proc_texto.startswith("PE "):
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
    except:
        return False


def testar_download_com_requests(page, proc_text):
    """
    1. Clicar botao de download (AJAX)
    2. Aguardar AJAX completar
    3. Usar requests com cookies
    """

    print(f"\n[TESTE] {proc_text}")

    # Encontrar botao
    btn_doc = page.locator('[id="form:j_id111"]')
    if btn_doc.count() == 0:
        print("[ERR] Botao 'Documentos' nao encontrado")
        return None

    # Abrir modal
    print("[1] Abrindo modal...")
    btn_doc.first.click()
    time.sleep(2)

    # Encontrar botao de download
    print("[2] Procurando botao de download...")
    btn_download = page.locator('[id="form:tabelaDocumentos:0:j_id283"]')
    if btn_download.count() == 0:
        print("[ERR] Botao de download nao encontrado")
        return None

    # Debug: verificar estado do botao
    print("[2B] Verificando botao...")
    try:
        is_visible = btn_download.first.is_visible()
        is_enabled = btn_download.first.is_enabled()
        print(f"    Visivel: {is_visible}, Habilitado: {is_enabled}")
    except Exception as e:
        print(f"    Erro ao verificar: {e}")

    # Fazer scroll se necessario
    try:
        btn_download.first.scroll_into_view_if_needed()
        print("[2C] Scroll feito")
    except:
        pass

    # Registrar requests para monitorar o que esta sendo enviado
    requests_capturados = []
    def on_request(request):
        url = request.url
        if "consultaProcessoDetalhada" in url or "download" in url:
            requests_capturados.append({"url": url, "method": request.method})
            print(f"    [REQ] {request.method} {url[:80]}")

    page.on("request", on_request)

    # Clicar botao de download (dispara AJAX)
    print("[3] Clicando botao de download (AJAX)...")
    try:
        btn_download.first.click(force=True)
        print("[3B] Click realizado (force=True)")
    except Exception as e:
        print(f"[3ERR] Erro ao clicar: {e}")

    # Aguardar estabilidade da pagina apos AJAX
    print("[4] Aguardando página ficar estável...")
    time.sleep(1)  # Dar tempo minimo
    try:
        # networkidle aguarda que nao haja mais requests em voo
        page.wait_for_load_state("networkidle", timeout=15000)
        print(f"[AJAX] Page estavel (networkidle)")
        print(f"[AJAX] {len(requests_capturados)} requisições capturadas")
    except PlaywrightTimeout:
        print(f"[AJAX] Timeout networkidle, continuando...")
        print(f"[AJAX] {len(requests_capturados)} requisições capturadas antes do timeout")
        time.sleep(2)

    page.remove_listener("request", on_request)

    # Agora que AJAX completou e server tem doc ID na sessao,
    # fazer requests.get() com cookies
    print("[5] Fazendo requests.get() com cookies da sessao...")

    cookies_dict = {c["name"]: c["value"] for c in page.context.cookies()}
    print(f"    Cookies: JSESSIONID={cookies_dict.get('JSESSIONID', 'N/A')[:20]}...")

    try:
        resp = requests.get(DOWNLOAD_URL, cookies=cookies_dict, timeout=30, allow_redirects=True)
        print(f"    Status: {resp.status_code}")
        print(f"    Content-Type: {resp.headers.get('content-type', 'N/A')}")
        print(f"    Size: {len(resp.content)} bytes")

        # Verificar se eh PDF
        eh_pdf = resp.headers.get('content-type', '').lower().startswith('application/pdf') or resp.content[:4] == b"%PDF"
        eh_html = "text/html" in resp.headers.get('content-type', '')

        print(f"    PDF: {eh_pdf}")
        print(f"    HTML: {eh_html}")

        if eh_pdf:
            print("[SUCESSO] PDF capturado!")
            return {
                "processo": proc_text,
                "status": resp.status_code,
                "content_type": resp.headers.get('content-type', ''),
                "tamanho": len(resp.content),
                "eh_pdf": True
            }
        else:
            print("[WARN] Resposta nao eh PDF")
            print(f"    Primeiros 200 bytes: {resp.content[:200]}")
            return {
                "processo": proc_text,
                "status": resp.status_code,
                "content_type": resp.headers.get('content-type', ''),
                "tamanho": len(resp.content),
                "eh_pdf": False,
                "primeiros_bytes": resp.content[:200].decode('utf-8', errors='ignore')
            }

    except Exception as e:
        print(f"[ERR] {e}")
        return {
            "processo": proc_text,
            "erro": str(e)
        }


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 70)
    print("TESTE: Download via requests APOS AJAX")
    print("=" * 70)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=80)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        # NAVEGACAO
        print("\n[SETUP] Acessando portal...")
        page.goto(PORTAL_URL, wait_until="domcontentloaded")
        time.sleep(2)

        print("[SETUP] Fazendo pesquisa...")
        fazer_pesquisa(page)

        print("[SETUP] Extraindo processos...")
        processos = extrair_processos_pagina(page)
        if not processos:
            print("[ERR] Nenhum processo PE encontrado")
            browser.close()
            return

        print(f"[SETUP] Encontrados {len(processos)} processos PE")

        # ABRIR PRIMEIRO PROCESSO
        proc = processos[0]
        print(f"\n[SETUP] Abrindo detalhe: {proc['texto']}")
        if not abrir_detalhe(page, proc):
            print("[ERR] Falha ao abrir detalhe")
            browser.close()
            return

        # TESTAR DOWNLOAD
        resultado = testar_download_com_requests(page, proc['texto'])

        # SALVAR
        with open("teste_requests_resultado.json", "w") as f:
            json.dump(resultado, f, indent=2, ensure_ascii=False)

        print(f"\n[RESULTADO]")
        if resultado:
            for k, v in resultado.items():
                if k != "primeiros_bytes":
                    print(f"  {k}: {v}")

        browser.close()

    print(f"\n[OK] Resultado salvo em teste_requests_resultado.json")


if __name__ == "__main__":
    main()
