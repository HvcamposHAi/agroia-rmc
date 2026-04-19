"""
AgroIA-RMC — Teste SIMPLES: Capturar download sem complicacoes
==============================================================

Estrategia SUPER SIMPLES:
1. Usar page.on("response") registrado GLOBALMENTE no inicio
2. Deixar AJAX e download acontecerem naturalmente
3. Capturar response de download.jsf quando chegar
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


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 70)
    print("TESTE SIMPLES: Download Capture via Global Response Listener")
    print("=" * 70)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=80)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        # REGISTRAR RESPONSE LISTENER NO INICIO (globalmente)
        responses_capturadas = []

        def on_response(response):
            url = response.url
            if "download" in url.lower():
                print(f"\n[RESPONSE] {response.status} {url[:80]}")
                ct = response.headers.get("content-type", "")
                print(f"[CT] {ct}")

                try:
                    body = response.body()
                    tamanho = len(body)
                    eh_pdf = body[:4] == b"%PDF" or "pdf" in ct.lower()
                    print(f"[BODY] {tamanho} bytes, PDF={eh_pdf}")

                    responses_capturadas.append({
                        "url": url,
                        "status": response.status,
                        "content_type": ct,
                        "tamanho": tamanho,
                        "eh_pdf": eh_pdf,
                        "primeiros_bytes": body[:50]
                    })
                    print(f"[OK] Response capturada com sucesso!")

                except Exception as e:
                    print(f"[ERR] {e}")

        page.on("response", on_response)
        print("\n[SETUP] Response listener registrado")

        # NAVEGACAO
        print("[SETUP] Acessando portal...")
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
        print(f"\n[TESTE] Abrindo detalhe: {proc['texto']}")
        if not abrir_detalhe(page, proc):
            print("[ERR] Falha ao abrir detalhe")
            browser.close()
            return

        # CLICAR BOTAO DOCUMENTOS
        print("[TESTE] Clicando 'Documentos da licitacao'...")
        btn_doc = page.locator('[id="form:j_id111"]')
        if btn_doc.count() == 0:
            print("[ERR] Botao nao encontrado")
            browser.close()
            return

        btn_doc.first.click()
        time.sleep(2)

        # ENCONTRAR BOTAO DE DOWNLOAD NA TABELA
        print("[TESTE] Procurando botao de download...")
        btn_download = page.locator('[id="form:tabelaDocumentos:0:j_id283"]')
        if btn_download.count() == 0:
            print(f"[ERR] Botao nao encontrado")
            browser.close()
            return

        print("[TESTE] Clicando botao de download...")
        btn_download.first.click()

        # AGUARDAR RESPONSE
        print("[TESTE] Aguardando resposta de download...")
        for i in range(20):
            time.sleep(0.5)
            if responses_capturadas:
                print(f"\n[SUCESSO] Response capturada apos {(i+1)*0.5:.1f}s")
                break
        else:
            print("[TIMEOUT] Nenhuma response capturada apos 10s")

        # RESULTADO
        resultado = {
            "processo": proc['texto'],
            "download_capturado": len(responses_capturadas) > 0,
            "responses": responses_capturadas
        }

        with open("teste_final_simples_resultado.json", "w") as f:
            json.dump(resultado, f, indent=2, ensure_ascii=False)

        print(f"\n[RESULTADO]")
        print(f"  Responses capturadas: {len(responses_capturadas)}")
        if responses_capturadas:
            r = responses_capturadas[0]
            print(f"  Tamanho: {r['tamanho']} bytes")
            print(f"  PDF: {r['eh_pdf']}")
            print(f"  Content-Type: {r['content_type']}")

        browser.close()

    print(f"\n[OK] Resultado salvo em teste_final_simples_resultado.json")


if __name__ == "__main__":
    main()
