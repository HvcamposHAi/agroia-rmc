"""
ETAPA 3 - COM RETRY: Coleta com múltiplas tentativas

Estratégia:
1. Roda coleta normal
2. Rastreia quais processos falharam
3. Roda novamente, tentando apenas os que falharam
4. Repete até não haver mais melhorias
"""

import os
import re
import time
import json
import pickle
import unicodedata
from io import BytesIO
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
from supabase import create_client
import requests as req_lib
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

PORTAL_BASE = "http://consultalicitacao.curitiba.pr.gov.br:9090"
DETALHE_URL = f"{PORTAL_BASE}/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
DOWNLOAD_URL = f"{PORTAL_BASE}/ConsultaLicitacoes/pages/download/download.jsf"

ORGAO = "SMSAN/FAAC"
DT_INICIO = "01/01/2019"
DT_FIM = "30/04/2026"
REGS_POR_PAG = 10
MODALIDADE = "PE"

DEBUG = True
HEADLESS = True
SLOW_MO = 0

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── Retry tracking ───────────────────────────────────────────
RETRY_LOG = "retry_failed.json"

def save_retry_list(processos):
    """Salvar lista de processos para retry"""
    with open(RETRY_LOG, "w") as f:
        json.dump(processos, f, indent=2)
    print(f"[retry] Salvos {len(processos)} processos para retry em {RETRY_LOG}")

def load_retry_list():
    """Carregar lista de retry anterior"""
    if os.path.exists(RETRY_LOG):
        with open(RETRY_LOG) as f:
            return json.load(f)
    return []

# ─── Google Drive ─────────────────────────────────────────────

def setup_google_drive():
    if not os.path.exists("token.pickle"):
        print("[!] token.pickle nao encontrado")
        return None
    try:
        with open("token.pickle", "rb") as f:
            creds = pickle.load(f)
        drive_service = build('drive', 'v3', credentials=creds)
        print("[OK] Google Drive conectado")
        return drive_service
    except Exception as e:
        print(f"[!] Erro Google Drive: {e}")
        return None

def upload_google_drive(drive_service, arquivo_bytes, nome_arquivo, folder_id):
    try:
        file_metadata = {'name': nome_arquivo, 'parents': [folder_id]}
        media = MediaIoBaseUpload(BytesIO(arquivo_bytes), mimetype='application/pdf', resumable=True)
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webContentLink').execute()

        drive_service.permissions().create(
            fileId=file['id'],
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()

        return file.get('webContentLink')
    except Exception as e:
        print(f"[gdrive-err] {e}")
        return None

def sanitizar_nome(texto):
    nfd = unicodedata.normalize('NFD', texto)
    sem_acentos = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
    safe = re.sub(r'[^\w\-]', '_', sem_acentos)
    return safe[:100]

# ─── Portal navigation ─────────────────────────────────────────

def preencher_data(page, campo_id, valor):
    campo = page.locator(f'[id="{campo_id}"]')
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except PlaywrightTimeout:
        pass
    try:
        if campo.count() == 0:
            return False
        campo.wait_for(state="visible", timeout=15000)
        campo.click(click_count=3)
        time.sleep(0.2)
        page.keyboard.type(valor, delay=50)
        time.sleep(0.3)
        page.keyboard.press("Tab")
        time.sleep(0.5)
        return True
    except Exception as e:
        if DEBUG:
            print(f"[!] Erro ao preencher {campo_id}: {e}")
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

    selecionar_opcao(page, ORGAO, "Orgao")
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

    if total == 0:
        with open("debug_pesquisa.html", "w", encoding="utf-8") as f:
            f.write(html)

    return total

def extrair_processos_pagina(page):
    soup = BeautifulSoup(page.content(), "lxml")
    processos = []
    visto = set()  # Para remover duplicatas

    for tabela in soup.find_all("table"):
        ths = [th.get_text(strip=True).lower() for th in tabela.find_all("th")]
        if "processo" not in ths or "objeto" not in ths:
            continue

        for idx, tr in enumerate(tabela.find_all("tr")[1:]):
            cols = tr.find_all("td")
            if len(cols) < 2:
                continue

            texto = cols[0].get_text(strip=True)
            if MODALIDADE and not texto.startswith(MODALIDADE + " "):
                continue

            # Pular duplicatas
            if texto in visto:
                continue
            visto.add(texto)

            processos.append({"texto": texto, "index": idx})

    return processos

def abrir_detalhe(page, proc):
    try:
        # Estratégia 1: Procurar todos os links de processo e clicar naquele que matches o texto
        texto = proc['texto']

        # Encontrar a linha que contém este processo
        links = page.locator('a[id*="j_id26"]')

        for i in range(links.count()):
            link = links.nth(i)
            try:
                # Verificar se este link está na mesma linha que o texto esperado
                parent_row = link.locator("xpath=ancestor::tr")
                if parent_row.count() > 0:
                    row_text = parent_row.first.text_content()
                    if texto in row_text:
                        link.click()
                        time.sleep(1.5)
                        try:
                            page.wait_for_load_state("networkidle", timeout=30000)
                        except PlaywrightTimeout:
                            pass
                        return True
            except:
                continue

        # Fallback: Tentar com o índice original
        link_id = f"form:tabela:{proc['index']}:j_id26"
        elem = page.locator(f'[id="{link_id}"]')
        if elem.count() > 0:
            elem.first.click()
            time.sleep(1.5)
            try:
                page.wait_for_load_state("networkidle", timeout=30000)
            except PlaywrightTimeout:
                pass
            return True

        return False
    except Exception as e:
        if DEBUG:
            print(f"[abrir-detalhe-err] {e}")
        return False

def abrir_modal(page):
    try:
        btn = page.locator('[id="form:j_id111"]')
        if btn.count() == 0:
            btn = page.locator('input[value="Documentos da licitacao"]')

        if btn.count() == 0:
            return False

        btn.first.click()
        time.sleep(2)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightTimeout:
            pass
        return True
    except Exception:
        return False

def extrair_documentos(page):
    try:
        html = page.content()
        soup = BeautifulSoup(html, "lxml")
        tabela = soup.find("table", id="form:tabelaDocumentos")

        if not tabela:
            return []

        docs = []
        for i, tr in enumerate(tabela.find_all("tr")[1:]):
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue

            nome = tds[0].get_text(strip=True)
            inp = tds[1].find("input")
            if not inp:
                continue

            inp_id = inp.get("id", "")
            if inp_id:
                docs.append({"nome": nome, "input_id": inp_id, "index": i})

        return docs
    except Exception as e:
        if DEBUG:
            print(f"[docs-err] {e}")
        return []

def baixar_documento(page, doc, licitacao_id, drive_service, folder_id):
    try:
        btn = page.locator(f'[id="{doc["input_id"]}"]')
        if btn.count() == 0:
            return None

        btn.first.click()
        time.sleep(1)

        try:
            page.goto(DOWNLOAD_URL, wait_until="domcontentloaded", timeout=30000)
        except:
            return None

        html = page.content()
        m = re.search(r'javax\.faces\.ViewState"\s+value="([^"]+)"', html)
        if not m:
            return None

        viewstate = m.group(1)
        cookies = {c['name']: c['value'] for c in page.context.cookies()}

        try:
            resp = req_lib.post(
                DOWNLOAD_URL,
                data={
                    "form_download_arquivo_documento": "form_download_arquivo_documento",
                    "form_download_arquivo_documento:j_id_1n": "form_download_arquivo_documento:j_id_1n",
                    "javax.faces.ViewState": viewstate
                },
                cookies=cookies,
                timeout=120,
                verify=False
            )

            if resp.status_code == 200 and "application/pdf" in resp.headers.get("content-type", ""):
                size = len(resp.content) / 1024 / 1024
                print(f"      [pdf] {size:.1f}MB OK")

                nome_safe = sanitizar_nome(doc["nome"])
                url = upload_google_drive(drive_service, resp.content, nome_safe, folder_id)

                if url:
                    print(f"      [gdrive] OK")
                    return {"url": url, "tamanho": len(resp.content), "nome": nome_safe}
        except Exception as e:
            if DEBUG:
                print(f"      [post-err] {e}")

        return None
    except Exception as e:
        if DEBUG:
            print(f"      [download-err] {e}")
        return None

# ─── Main ─────────────────────────────────────────────────────

def main():
    drive_service = setup_google_drive()
    folder_id = GOOGLE_DRIVE_FOLDER_ID

    # Carregar retry list
    retry_processos = load_retry_list()

    if retry_processos:
        print(f"\n[retry] Tentando novamente {len(retry_processos)} processos que falharam...")
        print(f"[note] Sera feita uma busca para ter os links atualizados")
        # Mesmo em retry, precisa fazer a busca para ter os links
        precisa_buscar = True
    else:
        print(f"\n[search] Fazendo busca normal no portal...")
        precisa_buscar = True

    stats = {"docs_baixados": 0, "erros": 0, "processadas": 0, "falhadas": [], "sem_docs": 0}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, slow_mo=SLOW_MO)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        try:
            processos_para_processar = []

            if precisa_buscar:
                # Fazer busca
                page.goto(DETALHE_URL, wait_until='domcontentloaded')
                try:
                    page.wait_for_load_state("networkidle", timeout=20000)
                except PlaywrightTimeout:
                    pass
                time.sleep(1)

                print("[init] Pesquisando...")
                total = fazer_pesquisa(page)
                print(f"[init] Total: {total}")

                num_paginas = (total + REGS_POR_PAG - 1) // REGS_POR_PAG
                print(f"[init] Paginas: {num_paginas}")

                # Extrair processos de todas as páginas
                for page_num in range(1, num_paginas + 1):
                    print(f"\n[page {page_num}] Extraindo...")
                    procs = extrair_processos_pagina(page)
                    processos_para_processar.extend(procs)

                    if page_num < num_paginas:
                        try:
                            btn_next = page.locator("td.rich-datascr-button:not(.rich-datascr-button-dsbld)[onclick*=\"'page': 'next'\"]")
                            if btn_next.count() > 0:
                                try:
                                    btn_next.first.scroll_into_view()
                                    time.sleep(0.5)
                                except:
                                    pass
                                try:
                                    btn_next.first.click(timeout=5000, force=True)
                                except:
                                    try:
                                        page.evaluate("document.querySelector(\"td.rich-datascr-button:not(.rich-datascr-button-dsbld)[onclick*=\\\"'page': 'next'\\\"]\").click()")
                                    except:
                                        pass
                                time.sleep(2)
                                try:
                                    page.wait_for_load_state("networkidle", timeout=40000)
                                except PlaywrightTimeout:
                                    pass
                                time.sleep(1)
                        except:
                            break

                print(f"\n[search] Total extraido: {len(processos_para_processar)} processos")

            # Processar processos
            for idx, proc in enumerate(processos_para_processar, 1):
                print(f"\n[{idx}/{len(processos_para_processar)}] {proc.get('texto', 'N/A')}")

                try:
                    if not abrir_detalhe(page, proc):
                        print(f"  [!] Falha ao abrir")
                        stats["falhadas"].append(proc)
                        stats["erros"] += 1
                        continue

                    if not abrir_modal(page):
                        print(f"  [!] Modal nao abriu")
                        stats["falhadas"].append(proc)
                        stats["erros"] += 1
                        try:
                            page.evaluate('Richfaces.hideModalPanel("form:documentos")')
                        except:
                            pass
                        continue

                    docs = extrair_documentos(page)
                    if not docs:
                        print(f"  [sem_docs]")
                        try:
                            page.evaluate('Richfaces.hideModalPanel("form:documentos")')
                        except:
                            pass
                        continue

                    print(f"  Docs: {len(docs)}")

                    for doc in docs:
                        resultado = baixar_documento(page, doc, 0, drive_service, folder_id)
                        if resultado:
                            stats["docs_baixados"] += 1

                    try:
                        page.evaluate('Richfaces.hideModalPanel("form:documentos")')
                    except:
                        pass

                    stats["processadas"] += 1
                    time.sleep(0.5)

                except Exception as e:
                    print(f"  [!] Erro: {e}")
                    stats["falhadas"].append(proc)
                    stats["erros"] += 1

        finally:
            try:
                browser.close()
            except:
                pass

    print(f"\n{'='*70}")
    print(f"RESUMO (Rodada):")
    print(f"  Processadas: {stats['processadas']}")
    print(f"  Docs baixados: {stats['docs_baixados']}")
    print(f"  Erros: {stats['erros']}")
    print(f"  Falhadas: {len(stats['falhadas'])}")
    print(f"{'='*70}")

    # Salvar para retry se houve falhas
    if stats['falhadas']:
        save_retry_list(stats['falhadas'])
        print(f"\n[info] Execute novamente para fazer retry dos {len(stats['falhadas'])} processos falhados")

if __name__ == "__main__":
    main()
