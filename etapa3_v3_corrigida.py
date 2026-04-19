"""
AgroIA-RMC — Coleta de Documentos (PDFs) - v3 CORRIGIDA
======================================================

MUDANÇA: Implementa abort+requests com DELAY ADEQUADO após networkidle

O problema anterior era que requests.get() retornava HTML de erro mesmo após
networkidle. Possível causa: o servidor precisa de tempo ADICIONAL para processar
o AJAX request e registrar o document ID na sessão.

Solução: adicionar delay_pos_ajax = 3 segundos APÓS networkidle completar.

Execute: python etapa3_v3_corrigida.py
"""

import os
import re
import time
import signal
from datetime import datetime
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
from supabase import create_client
import requests as req_lib

load_dotenv()

# ─── Configuração ─────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://rsphlvcekuomvpvjqxqm.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

PORTAL_URL = (
    "http://consultalicitacao.curitiba.pr.gov.br:9090/"
    "ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
)
DOWNLOAD_JSF_URL = (
    "http://consultalicitacao.curitiba.pr.gov.br:9090/"
    "ConsultaLicitacoes/pages/download/download.jsf"
)

ORGAO      = "SMSAN/FAAC"
DT_INICIO  = "01/01/2024"
DT_FIM     = "31/12/2024"
MODALIDADE = "PE"

REGS_POR_PAG    = 5
DELAY           = 2.0
DEBUG           = True
HEADLESS        = False
SLOW_MO         = 80

BUCKET          = "documentos-licitacoes"
PASTA_LOCAL     = "pdfs"

# CHAVE CORRIGIDA: Delay após networkidle para o servidor processar AJAX
DELAY_POS_AJAX  = 3.0  # ← MUDANÇA: 3 segundos APÓS networkidle

FORCAR_REDOWNLOAD = False
TOTAL_DESCONHECIDO = -1

INTERROMPIDO = False

def handler_sigint(sig, frame):
    global INTERROMPIDO
    INTERROMPIDO = True
    print("\n[!] Interrupção solicitada...")

signal.signal(signal.SIGINT, handler_sigint)

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── Funções de navegação (reutilizadas do etapa3_documentos.py) ─────────────

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


def _selecionar_opcao(page, texto_opcao, debug_label):
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
                if DEBUG:
                    print(f"    OK {debug_label}: {texto_opcao}")
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

    _selecionar_opcao(page, ORGAO, "Orgao")
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

    html = page.content()
    m = re.search(r"quantidade registros.*?(\d+)</label>", html, re.I | re.DOTALL)
    total = int(m.group(1)) if m else 0
    return total if total > 0 else TOTAL_DESCONHECIDO


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


def abrir_modal_documentos(page):
    btn = page.locator('[id="form:j_id111"]')
    if btn.count() == 0:
        btn = page.locator('input[value="Documentos da licitacao"]')
    if btn.count() == 0:
        return False

    try:
        btn.first.click()
        time.sleep(2)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightTimeout:
            pass
        time.sleep(0.5)
        return True
    except Exception:
        return False


def extrair_documentos_da_modal(page):
    html = page.content()
    soup = BeautifulSoup(html, "lxml")
    tabela = soup.find("table", id="form:tabelaDocumentos")

    if not tabela:
        return []

    documentos = []
    rows = tabela.find_all("tr")[1:]

    if DEBUG:
        print(f"      Docs na tabela: {len(rows)}")

    for i, tr in enumerate(rows):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue

        nome_doc = tds[0].get_text(strip=True)
        col_arq = tds[1]

        inp = col_arq.find("input")
        if not inp:
            continue

        inp_id = inp.get("id", "")
        onclick = inp.get("onclick", "")

        m_id = re.search(r"'id'\s*:\s*(\d+)", onclick)
        doc_id = int(m_id.group(1)) if m_id else None

        if inp_id:
            locator_str = f'[id="{inp_id}"]'
        else:
            locator_str = f'[id="form:tabelaDocumentos"] tr:nth-child({i+2}) input'

        documentos.append({
            "nome": nome_doc,
            "locator_str": locator_str,
            "doc_id": doc_id,
            "row_index": i,
        })

        if DEBUG:
            print(f"        * {nome_doc} | id={doc_id}")

    return documentos


def fechar_modal(page):
    try:
        fechar = page.locator('img[onclick*="hideModalPanel(\'form:documentos\')"]')
        if fechar.count() > 0:
            fechar.first.click()
            time.sleep(0.5)
            return
        page.evaluate("Richfaces.hideModalPanel('form:documentos')")
        time.sleep(0.5)
    except:
        pass


# ─── Download com abort + requests (CORRIGIDO) ────────────────────────────────

def baixar_documento_v3(page, doc, lic_id):
    """
    Estratégia CORRIGIDA:
    1. Clicar documento → AJAX (doc_id → sessão)
    2. Aguardar networkidle
    3. ESPERAR DELAY_POS_AJAX segundos adicional ← MUDANÇA
    4. requests.get(download.jsf) com cookies
    """

    locator_str = doc["locator_str"]
    nome_doc = doc["nome"]
    doc_id = doc.get("doc_id")

    elem = page.locator(locator_str)
    if elem.count() == 0:
        if DEBUG:
            print(f"        [!] Elemento nao encontrado")
        return None

    print(f"      [click] Clicando '{nome_doc[:30]}'...")

    # Passo 1: Registrar interceptor
    rota_disparou = {"ok": False}

    def abortar_popup(route):
        rota_disparou["ok"] = True
        try:
            route.abort()
        except:
            pass

    page.context.route("**/download/download.jsf**", abortar_popup)

    # Passo 2: Clicar botao (dispara AJAX)
    try:
        with page.context.expect_page(timeout=60000) as nova_pag_info:
            elem.first.click()

        nova_pag = nova_pag_info.value
        time.sleep(1.5)
        try:
            nova_pag.close()
        except:
            pass

    except PlaywrightTimeout:
        print(f"      [!] Popup timeout")
        return None
    except Exception as e:
        print(f"      [!] Erro: {e}")
        return None
    finally:
        try:
            page.context.unroute("**/download/download.jsf**")
        except:
            pass

    if not rota_disparou["ok"]:
        print(f"      [!] Popup nao tentou download.jsf")
        return None

    # Passo 3: Aguardar AJAX + delay ADICIONAL
    print(f"      [wait] Aguardando AJAX...")
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except PlaywrightTimeout:
        print(f"      [wait] Timeout")
        pass

    # ← MUDANÇA CRITICA: Delay adicional para servidor processar AJAX
    print(f"      [wait] Delay extra {DELAY_POS_AJAX}s...")
    time.sleep(DELAY_POS_AJAX)

    # Passo 4: requests.get() + POST para submeter formulário JSF
    print(f"      [req] Fazendo GET download.jsf...")
    cookies = {c["name"]: c["value"] for c in page.context.cookies()}

    try:
        # Step 1: GET (recebe página com formulário)
        r_get = req_lib.get(DOWNLOAD_JSF_URL, cookies=cookies, timeout=30, allow_redirects=True)
        print(f"      [get] {r_get.status_code} {len(r_get.content)}b")

        # Step 2: Extrair ViewState do formulário
        import re as regex
        m_viewstate = regex.search(r'javax\.faces\.ViewState"\s+value="([^"]+)"', r_get.text)
        if m_viewstate:
            viewstate = m_viewstate.group(1)
            print(f"      [form] ViewState extraído ({len(viewstate)} chars)")

            # Step 3: POST para submeter formulário
            data_post = {
                'form_download_arquivo_documento': 'form_download_arquivo_documento',
                'form_download_arquivo_documento:bt_download_documento': 'Download',
                'javax.faces.ViewState': viewstate
            }
            print(f"      [post] Submeter formulário...")
            r = req_lib.post(DOWNLOAD_JSF_URL, data=data_post, cookies=cookies, timeout=30, allow_redirects=True)
            ct = r.headers.get("content-type", "")
            size = len(r.content)
            print(f"      [resp] {r.status_code} {ct[:40]} {size}b")
        else:
            print(f"      [!] ViewState nao encontrado no HTML")
            return None

        # Verificar se PDF
        eh_pdf = r.status_code == 200 and size > 200 and (
            ct.lower().startswith("application/pdf") or r.content[:4] == b"%PDF"
        )

        if eh_pdf:
            print(f"      [OK] PDF capturado! {size} bytes")
            pasta = os.path.join(PASTA_LOCAL, str(lic_id))
            os.makedirs(pasta, exist_ok=True)

            nome_safe = re.sub(r'[^\w]', '_', nome_doc)
            caminho = os.path.join(pasta, f"{nome_safe}.pdf")

            with open(caminho, "wb") as f:
                f.write(r.content)

            return {"caminho": caminho, "tamanho": size, "nome": nome_safe}
        else:
            print(f"      [!] Nao eh PDF (provavel erro de sessao)")
            # Salvar HTML para analise
            if size < 5000:  # se pequeno, eh provavel erro page
                try:
                    html_error = r.text
                    pasta = os.path.join(PASTA_LOCAL, "erros")
                    os.makedirs(pasta, exist_ok=True)
                    nome_safe = re.sub(r'[^\w]', '_', nome_doc)
                    caminho_err = os.path.join(pasta, f"{nome_safe}_erro.html")
                    with open(caminho_err, "w", encoding="utf-8") as f:
                        f.write(html_error)
                    print(f"      [debug] HTML erro salvo em {caminho_err}")
                    # Tentar extrair mensagem de erro
                    if '<title>' in html_error:
                        m = re.search(r'<title>([^<]+)</title>', html_error)
                        if m:
                            print(f"      [debug] Titulo: {m.group(1)}")
                except:
                    pass
            return None

    except Exception as e:
        print(f"      [!] Erro requests: {e}")
        return None


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 70)
    print("ETAPA 3 v3: Coleta de Documentos - CORRIGIDA com DELAY")
    print("=" * 70)
    print(f"Delay pos AJAX: {DELAY_POS_AJAX}s")
    print()

    stats = {"docs_baixados": 0, "erros": 0}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, slow_mo=SLOW_MO)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        print("[init] Acessando portal...")
        page.goto(PORTAL_URL, wait_until='domcontentloaded')
        time.sleep(2)

        print("[init] Pesquisando...")
        total = fazer_pesquisa(page)
        print(f"[init] Total: {total}")

        # Testar apenas primeira página
        print(f"\n[page 1] Extraindo processos...")
        processos = extrair_processos_pagina(page)
        print(f"  {len(processos)} processos encontrados")

        # Processar cada um
        for i, proc in enumerate(processos):
            if INTERROMPIDO:
                break

            texto = proc["texto"]

            # Filtro modalidade
            if MODALIDADE and not texto.startswith(MODALIDADE + " "):
                continue

            print(f"\n  [{i+1}] {texto}")

            if not abrir_detalhe(page, proc):
                print(f"    [!] Falha ao abrir")
                stats["erros"] += 1
                continue

            # Abrir modal
            if not abrir_modal_documentos(page):
                print(f"    [!] Modal nao abriu")
                stats["erros"] += 1
                voltar_para_lista(page)
                continue

            # Extrair docs
            docs = extrair_documentos_da_modal(page)
            if not docs:
                print(f"    [sem_docs]")
                voltar_para_lista(page)
                continue

            # Baixar primeiro doc
            doc = docs[0]
            resultado = baixar_documento_v3(page, doc, i)
            if resultado:
                stats["docs_baixados"] += 1
            else:
                stats["erros"] += 1

            # Fechar e voltar
            fechar_modal(page)
            voltar_para_lista(page)
            time.sleep(DELAY)

        browser.close()

    print("\n" + "=" * 70)
    print(f"Docs baixados: {stats['docs_baixados']}")
    print(f"Erros: {stats['erros']}")
    print("=" * 70)


if __name__ == "__main__":
    main()
