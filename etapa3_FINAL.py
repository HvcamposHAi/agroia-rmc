"""
AgroIA-RMC — Coleta FINAL de Documentos (PDFs)
==============================================

SOLUCAO CONFIRMADA:
1. Clique em documento → AJAX (doc_id vai para sessão)
2. GET download.jsf → recebe formulário JSF com ViewState
3. POST download.jsf com ViewState → servidor retorna **PDF REAL**

Teste com PE 156/2023: 80.8 MB de PDF capturado com sucesso!

Execute: python etapa3_FINAL.py
"""

import os
import re
import time
import signal
import unicodedata
from datetime import datetime
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
from supabase import create_client
import requests as req_lib

load_dotenv()

# ─── Configuração ─────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

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

REGS_POR_PAG    = 10
DELAY           = 1.0
DEBUG           = True
HEADLESS        = True
SLOW_MO         = 0
MAX_DOCS_POR_LIC = 5  # máximo de documentos por licitação

BUCKET          = "documentos-licitacoes"
PASTA_LOCAL     = "pdfs"
DELAY_POS_AJAX  = 3.0

INTERROMPIDO = False

def handler_sigint(sig, frame):
    global INTERROMPIDO
    INTERROMPIDO = True
    print("\n[!] Interrupção solicitada...")

signal.signal(signal.SIGINT, handler_sigint)

def sanitizar_nome_arquivo(nome):
    """Remove acentos e caracteres especiais de nomes de arquivo"""
    # Remover acentos
    nfd = unicodedata.normalize('NFD', nome)
    sem_acentos = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
    # Manter apenas caracteres seguros: letras, números, hífens, underscores
    safe = re.sub(r'[^\w\-]', '_', sem_acentos)
    return safe

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── Funções (reutilizadas) ───────────────────────────────────────────────────

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
                    print(f"    OK {debug_label}")
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
    return total


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
        print(f"      Docs: {len(rows)}")

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


# ─── Download com GET+POST (SOLUCAO FINAL) ────────────────────────────────────

def baixar_documento_final(page, doc, processo_id):
    """
    SOLUCAO CONFIRMADA:
    1. Clicar → AJAX
    2. GET download.jsf → FormulárioJSF + ViewState
    3. POST com ViewState → **PDF REAL**
    """

    locator_str = doc["locator_str"]
    nome_doc = doc["nome"]
    doc_id = doc.get("doc_id")

    elem = page.locator(locator_str)
    if elem.count() == 0:
        return None

    print(f"      [click] {nome_doc[:30]}...")

    # Registrar interceptor para popup
    rota_disparou = {"ok": False}

    def abortar_popup(route):
        rota_disparou["ok"] = True
        try:
            route.abort()
        except:
            pass

    page.context.route("**/download/download.jsf**", abortar_popup)

    # Clicar (dispara AJAX e abre popup que será abortado)
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

    # Aguardar AJAX + delay
    print(f"      [wait] AJAX+delay...")
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except PlaywrightTimeout:
        pass
    time.sleep(DELAY_POS_AJAX)

    # GET + POST (SOLUCAO FINAL)
    cookies = {c["name"]: c["value"] for c in page.context.cookies()}

    try:
        # Step 1: GET
        print(f"      [get] download.jsf...")
        r_get = req_lib.get(DOWNLOAD_JSF_URL, cookies=cookies, timeout=30, allow_redirects=True)
        print(f"      [got] {r_get.status_code} {len(r_get.content)}b")

        # Step 2: Extrair ViewState
        m_viewstate = re.search(r'javax\.faces\.ViewState"\s+value="([^"]+)"', r_get.text)
        if not m_viewstate:
            print(f"      [!] ViewState nao encontrado")
            return None

        viewstate = m_viewstate.group(1)
        print(f"      [vs] Extraído ({len(viewstate)} chars)")

        # Step 3: POST
        data_post = {
            'form_download_arquivo_documento': 'form_download_arquivo_documento',
            'form_download_arquivo_documento:bt_download_documento': 'Download',
            'javax.faces.ViewState': viewstate
        }
        print(f"      [post] Submeter...")
        r = req_lib.post(DOWNLOAD_JSF_URL, data=data_post, cookies=cookies, timeout=30, allow_redirects=True)
        ct = r.headers.get("content-type", "")
        size = len(r.content)
        print(f"      [pdf] {r.status_code} {ct[:30]} {size/1024/1024:.1f}MB")

        # Verificar PDF
        eh_pdf = r.status_code == 200 and size > 200 and (
            ct.lower().startswith("application/pdf") or r.content[:4] == b"%PDF"
        )

        if eh_pdf:
            print(f"      [OK] PDF capturado!")

            # Buscar licitacao_id no banco usando o processo
            # processo_id é algo como "PE 156/2023 - SMSAN/FAAC"
            try:
                result = sb.table("licitacoes").select("id").eq("processo", processo_id).limit(1).execute()
                if not result.data:
                    print(f"      [!] Licitação não encontrada: {processo_id}")
                    return None
                licitacao_id = result.data[0]["id"]
            except Exception as e:
                print(f"      [!] Erro ao buscar licitacao_id: {e}")
                return None

            # Salvar localmente
            pasta = os.path.join(PASTA_LOCAL, str(licitacao_id))
            os.makedirs(pasta, exist_ok=True)
            nome_safe = sanitizar_nome_arquivo(nome_doc)
            caminho = os.path.join(pasta, f"{nome_safe}.pdf")
            with open(caminho, "wb") as f:
                f.write(r.content)

            # Fazer upload para Supabase (sem limite de tamanho - captura TODOS os PDFs)
            storage_path = f"{licitacao_id}/{nome_safe}.pdf"
            try:
                sb.storage.from_(BUCKET).upload(
                    storage_path,
                    r.content,
                    {"content-type": "application/pdf", "upsert": "true"}
                )
                print(f"      [upload] OK: {storage_path}")

                # Registrar no banco
                try:
                    sb.table("documentos_licitacao").upsert({
                        "licitacao_id": licitacao_id,
                        "nome_arquivo": nome_safe,
                        "nome_doc": nome_doc,
                        "tamanho_bytes": size,
                        "storage_path": storage_path,
                        "erro": None
                    }).execute()
                except Exception as db_err:
                    # Se for erro de chave duplicada, é ok (arquivo já foi registrado)
                    if "23505" in str(db_err) or "duplicate key" in str(db_err).lower():
                        print(f"      [dup] Arquivo já registrado no banco")
                    else:
                        print(f"      [db-err] {db_err}")

                return {"caminho": caminho, "storage_path": storage_path, "tamanho": size}

            except Exception as e:
                print(f"      [upload-err] {e}")
                return None
        else:
            print(f"      [!] Nao eh PDF")
            return None

    except Exception as e:
        print(f"      [err] {e}")
        return None


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 70)
    print("ETAPA 3 FINAL: Coleta de Documentos - GET+POST JSF")
    print("=" * 70)
    print()

    stats = {"docs_baixados": 0, "erros": 0, "pags_processadas": 0, "docs_pulados": 0}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, slow_mo=SLOW_MO)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        try:
            print("[init] Acessando portal...")
            page.goto(PORTAL_URL, wait_until='domcontentloaded')
            time.sleep(2)

            print("[init] Pesquisando...")
            total = fazer_pesquisa(page)
            print(f"[init] Total: {total}")

            # Processar todas as páginas
            num_paginas = (total + REGS_POR_PAG - 1) // REGS_POR_PAG
            print(f"[init] Páginas a processar: {num_paginas}")

            page_num = 1
            while page_num <= num_paginas:
                if INTERROMPIDO:
                    break

                print(f"\n[page {page_num}] Extraindo processos...")
                processos = extrair_processos_pagina(page)
                print(f"  {len(processos)} processos")

                stats["pags_processadas"] += 1

                for i, proc in enumerate(processos):
                    if INTERROMPIDO:
                        break

                    texto = proc["texto"]

                    if MODALIDADE and not texto.startswith(MODALIDADE + " "):
                        continue

                    print(f"\n  [{i+1}] {texto}")

                    if not abrir_detalhe(page, proc):
                        print(f"    [!] Falha ao abrir")
                        stats["erros"] += 1
                        continue

                    if not abrir_modal_documentos(page):
                        print(f"    [!] Modal nao abriu")
                        stats["erros"] += 1
                        voltar_para_lista(page)
                        continue

                    docs = extrair_documentos_da_modal(page)
                    if not docs:
                        print(f"    [sem_docs]")
                        voltar_para_lista(page)
                        continue

                    # Baixar até MAX_DOCS_POR_LIC documentos
                    for j, doc in enumerate(docs[:MAX_DOCS_POR_LIC]):
                        resultado = baixar_documento_final(page, doc, texto)
                        if resultado:
                            stats["docs_baixados"] += 1
                        else:
                            stats["erros"] += 1

                        # Pequeno delay entre downloads
                        if j < len(docs[:MAX_DOCS_POR_LIC]) - 1:
                            time.sleep(0.5)

                    fechar_modal(page)
                    voltar_para_lista(page)
                    time.sleep(DELAY)

                # Próxima página (RichFaces datascroller)
                if page_num < num_paginas:
                    print(f"\n[page-nav] Ir para página {page_num + 1}/{num_paginas}...")
                    try:
                        # RichFaces: procurar por td com onclick contendo 'page': 'next'
                        # O botão ativo NÃO tem a classe "rich-datascr-button-dsbld"
                        btn_next = page.locator("td.rich-datascr-button:not(.rich-datascr-button-dsbld)[onclick*=\"'page': 'next'\"]")

                        if btn_next.count() > 0:
                            print(f"[page-nav] Botão encontrado, clicando...")
                            btn_next.first.click()
                            time.sleep(2)
                            try:
                                page.wait_for_load_state("networkidle", timeout=20000)
                            except PlaywrightTimeout:
                                pass
                            time.sleep(1)
                            page_num += 1
                        else:
                            print(f"[page-nav] Botão próxima não encontrado ou desativado")
                            break
                    except Exception as e:
                        print(f"[page-nav] Erro ao navegar: {e}")
                        break
                else:
                    break

        finally:
            try:
                page.close()
            except:
                pass
            try:
                browser.close()
            except:
                pass

    print("\n" + "=" * 70)
    print(f"RESUMO:")
    print(f"  Docs baixados: {stats['docs_baixados']}")
    print(f"  Erros: {stats['erros']}")
    print(f"  Pages processadas: {stats['pags_processadas']}")
    print("=" * 70)


if __name__ == "__main__":
    main()
