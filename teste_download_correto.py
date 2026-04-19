"""
AgroIA-RMC — Teste: Download correto via context.expect_page + response listener
===============================================================================

Estratégia CORRETA (aprendida do diagnóstico):
1. Deixa AJAX request completar (não aborta) → servidor guarda doc ID na sessão
2. Deixa popup abrir normalmente
3. Registra listener NO POPUP para interceptar response de download.jsf
4. Captura bytes do PDF
5. Fecha popup

Este script testa a estratégia com 1 licitação real.
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


def testar_download_correto(page, processo_nome):
    """
    ESTRATEGIA CORRETA:
    1. Deixa AJAX completar (NÃO aborta)
    2. Usa expect_page para capturar popup
    3. Registra response listener NO POPUP
    4. Captura resposta de download.jsf quando chegar
    """

    print(f"\n  [TESTE] Testando download para: {processo_nome}")

    # Encontrar o botão de documentos
    btn_doc = page.locator('[id="form:j_id111"]')
    print(f"  [DBG] Botao [id=form:j_id111] encontrado: {btn_doc.count()}")

    if btn_doc.count() == 0:
        btn_doc = page.locator('input[value="Documentos da licitacao"]')
        print(f"  [DBG] Botao [value=Documentos da licitacao] encontrado: {btn_doc.count()}")

    if btn_doc.count() == 0:
        print(f"  [ERR] Botao nao encontrado em nenhum seletor")
        # Tentar encontrar qualquer input de tipo image
        todos_inputs = page.locator('input[type="image"]')
        print(f"  [DBG] Inputs de tipo image encontrados: {todos_inputs.count()}")
        if todos_inputs.count() > 0:
            btn_doc = todos_inputs.first
            print(f"  [DBG] Usando primeiro input type=image")
        else:
            return None

    resultado = {
        "processo": processo_nome,
        "tempo_inicio": datetime.now().isoformat(),
        "popup_capturado": False,
        "response_capturada": False,
        "tamanho_bytes": 0,
        "content_type": "",
        "erro": None
    }

    print(f"  [1] Preparando para capturar popup...")

    try:
        # Usar expect_page para capturar o popup que sera aberto
        with page.context.expect_page(timeout=60000) as nova_pag_info:
            # Clicar DENTRO do expect_page (mas antes de acessar nova_pag)
            btn_doc.first.click()

        # Agora o popup foi capturado
        nova_pag = nova_pag_info.value
        resultado["popup_capturado"] = True
        print(f"  [2] Popup capturado! Registrando listener...")

        # Agora registrar listener no popup para respostas que chegarem
        responses_capturadas = []

        def handle_response_popup(response):
            url_lower = response.url.lower()
            print(f"    [popup] Response: {response.status} {url_lower[:80]}...")
            if "download" in url_lower:
                try:
                    ct = response.headers.get("content-type", "")
                    print(f"    [popup] Content-Type: {ct}")
                    # Tentar ler corpo SEM chamar response.body() direto
                    # Usar response.all_headers() e tamanho
                    try:
                        body = response.body()
                        responses_capturadas.append({
                            "url": response.url,
                            "status": response.status,
                            "content_type": ct,
                            "tamanho": len(body),
                            "eh_pdf": ct.lower().startswith("application/pdf") or body[:4] == b"%PDF",
                            "eh_html": "text/html" in ct or body[:100].startswith(b"<!DOCTYPE") or body[:100].startswith(b"<html")
                        })
                        print(f"    [popup] Corpo: {len(body)} bytes, PDF={responses_capturadas[-1]['eh_pdf']}")
                    except Exception as e:
                        print(f"    [popup] Erro ao ler corpo: {e}")
                except Exception as e:
                    print(f"    [popup] Erro na resposta: {e}")

        nova_pag.on("response", handle_response_popup)
        print(f"  [3] Listener registrado no popup, aguardando responses...")

        # Aguardar responses chegarem
        for i in range(10):
            time.sleep(0.5)
            if responses_capturadas:
                break

        # Tentar ler conteudo do popup se nada foi capturado
        if not responses_capturadas:
            print(f"  [3] Tentando ler conteudo do popup...")
            try:
                nova_pag.wait_for_load_state("domcontentloaded", timeout=5000)
                html = nova_pag.content()
                print(f"  [DBG] HTML do popup: {len(html)} chars")
            except Exception as e:
                print(f"  [DBG] Erro ao ler popup: {e}")

        # Verificar responses capturadas
        if responses_capturadas:
            resultado["response_capturada"] = True
            resp = responses_capturadas[0]
            resultado["tamanho_bytes"] = resp.get("tamanho", 0)
            resultado["content_type"] = resp.get("content_type", "")
            print(f"  [4] Response capturada: {resultado['tamanho_bytes']} bytes")
            print(f"      Content-Type: {resultado['content_type']}")
            print(f"      eh_pdf: {resp.get('eh_pdf', False)}")
            print(f"      eh_html: {resp.get('eh_html', False)}")
        else:
            print(f"  [4] Nenhuma response de download capturada")

        nova_pag.close()

    except Exception as e:
        resultado["erro"] = str(e)
        print(f"  [ERR] {e}")

    resultado["tempo_fim"] = datetime.now().isoformat()
    return resultado


def main():
    with sync_playwright() as p:
        print("=" * 70)
        print("TESTE: Download via popup + response listener (ESTRATEGIA CORRETA)")
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
        resultado = testar_download_correto(page, proc['texto'])

        # Salvar resultado
        with open("teste_download_resultado.json", "w") as f:
            json.dump(resultado, f, indent=2, ensure_ascii=False)

        print(f"\n[RESULTADO]")
        print(f"  Popup capturado: {resultado['popup_capturado']}")
        print(f"  Response capturada: {resultado['response_capturada']}")
        if resultado['response_capturada']:
            print(f"  Tamanho: {resultado['tamanho_bytes']} bytes")
            print(f"  Type: {resultado['content_type']}")
        if resultado['erro']:
            print(f"  Erro: {resultado['erro']}")

        browser.close()

    print(f"\n[OK] Resultado salvo em teste_download_resultado.json")

if __name__ == "__main__":
    main()
