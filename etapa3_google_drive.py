"""
AgroIA-RMC — Coleta FINAL de Documentos (PDFs) com Google Drive
================================================================

NOVA ESTRATÉGIA:
1. Clicar em documento → AJAX (doc_id vai para sessão)
2. GET download.jsf → recebe formulário JSF com ViewState
3. POST download.jsf com ViewState → servidor retorna PDF REAL
4. Upload para Google Drive (sem limite de tamanho)
5. Salvar URL pública no banco de dados

Execute: python etapa3_google_drive.py
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

# Google Drive
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
import io

load_dotenv()

# ─── Configuração ─────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", None)

PORTAL_URL = (
    "http://consultalicitacao.curitiba.pr.gov.br:9090/"
    "ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
)
DOWNLOAD_JSF_URL = (
    "http://consultalicitacao.curitiba.pr.gov.br:9090/"
    "ConsultaLicitacoes/pages/download/download.jsf"
)

ORGAO      = "SMSAN/FAAC"
DT_INICIO  = "01/01/2019"
DT_FIM     = "30/04/2026"
MODALIDADE = "PE"

REGS_POR_PAG    = 10
DELAY           = 1.0
DEBUG           = True
HEADLESS        = True
SLOW_MO         = 0
MAX_DOCS_POR_LIC = 5

BUCKET          = "documentos-licitacoes"
PASTA_LOCAL     = "pdfs"
DELAY_POS_AJAX  = 3.0

INTERROMPIDO = False

def handler_sigint(sig, frame):
    global INTERROMPIDO
    INTERROMPIDO = True
    print("\n[!] Interrupcao solicitada...")

signal.signal(signal.SIGINT, handler_sigint)

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── Google Drive Setup ────────────────────────────────────────────────────────

def setup_google_drive():
    """Configurar Google Drive API usando token.pickle"""
    import pickle

    # Tentar carregar token.pickle
    if not os.path.exists("token.pickle"):
        print("[!] token.pickle não encontrado")
        print("[!] Execute primeiro: python setup_google_drive_direto.py")
        return None

    try:
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)

        drive_service = build('drive', 'v3', credentials=creds)
        print("[OK] Google Drive conectado via token.pickle")
        return drive_service
    except Exception as e:
        print(f"[!] Erro ao conectar Google Drive: {e}")
        return None

def upload_para_google_drive(drive_service, arquivo_bytes, nome_arquivo, folder_id):
    """Upload de arquivo para Google Drive"""
    try:
        file_metadata = {
            'name': nome_arquivo,
            'parents': [folder_id] if folder_id else []
        }

        media = MediaIoBaseUpload(
            io.BytesIO(arquivo_bytes),
            mimetype='application/pdf',
            resumable=True
        )

        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink, webContentLink'
        ).execute()

        file_id = file.get('id')
        # Tornar arquivo público
        drive_service.permissions().create(
            fileId=file_id,
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()

        url_publica = file.get('webContentLink')  # Link direto para download
        return file_id, url_publica

    except Exception as e:
        print(f"[!] Erro ao upload Google Drive: {e}")
        return None, None

# ─── Funções (reutilizadas) ───────────────────────────────────────────────────

def sanitizar_nome_arquivo(nome):
    """Remove acentos e caracteres especiais de nomes de arquivo"""
    nfd = unicodedata.normalize('NFD', nome)
    sem_acentos = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
    safe = re.sub(r'[^\w\-]', '_', sem_acentos)
    return safe

def preencher_data(page, campo_id, valor):
    campo = page.locator(f'[id="{campo_id}"]')
    try:
        # Aguardar página carregar antes de contar
        page.wait_for_load_state("networkidle", timeout=10000)
    except PlaywrightTimeout:
        pass  # Continuar mesmo se timeout

    try:
        if campo.count() == 0:
            return False
    except Exception as e:
        print(f"[!] Erro ao contar campo {campo_id}: {e}")
        return False

    try:
        campo.wait_for(state="visible", timeout=15000)
    except PlaywrightTimeout:
        return False

    try:
        campo.click(click_count=3)
        time.sleep(0.2)
        page.keyboard.type(valor, delay=50)
        time.sleep(0.3)
        page.keyboard.press("Tab")
        time.sleep(0.5)
        return True
    except Exception as e:
        print(f"[!] Erro ao preencher {campo_id}: {e}")
        return False

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

    # Debug: se não encontrar, tenta outros padrões
    if total == 0:
        print(f"[debug] Padrão 'quantidade registros' não encontrado")
        # Salvar HTML para análise
        with open("debug_busca.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[debug] HTML salvo em debug_busca.html")
        # Tenta padrão alternativo
        m2 = re.search(r"(\d+)\s*registros", html, re.I)
        if m2:
            total = int(m2.group(1))
            print(f"[debug] Encontrado com padrão alternativo: {total}")
        else:
            print(f"[debug] Nenhum padrão encontrou resultados")

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

# ─── Download com GET+POST + Google Drive ──────────────────────────────────

def baixar_documento_final(page, doc, processo_id, drive_service, google_folder_id):
    """
    SOLUCAO CONFIRMADA:
    1. Clicar → AJAX
    2. GET download.jsf → FormulárioJSF + ViewState
    3. POST com ViewState → **PDF REAL**
    4. Upload para Google Drive
    5. Salvar URL no banco de dados
    """

    locator_str = doc["locator_str"]
    nome_doc = doc["nome"]
    doc_id = doc.get("doc_id")

    elem = page.locator(locator_str)
    if elem.count() == 0:
        return None

    print(f"      [click] {nome_doc[:30]}...")

    rota_disparou = {"ok": False}

    def abortar_popup(route):
        rota_disparou["ok"] = True
        try:
            route.abort()
        except:
            pass

    page.context.route("**/download/download.jsf**", abortar_popup)

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

    print(f"      [wait] AJAX+delay...")
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except PlaywrightTimeout:
        pass
    time.sleep(DELAY_POS_AJAX)

    # GET + POST (SOLUCAO FINAL)
    cookies = {c["name"]: c["value"] for c in page.context.cookies()}

    try:
        print(f"      [get] download.jsf...")
        r_get = req_lib.get(DOWNLOAD_JSF_URL, cookies=cookies, timeout=30, allow_redirects=True)
        print(f"      [got] {r_get.status_code} {len(r_get.content)}b")

        m_viewstate = re.search(r'javax\.faces\.ViewState"\s+value="([^"]+)"', r_get.text)
        if not m_viewstate:
            print(f"      [!] ViewState nao encontrado")
            return None

        viewstate = m_viewstate.group(1)
        print(f"      [vs] Extraído ({len(viewstate)} chars)")

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

        eh_pdf = r.status_code == 200 and size > 200 and (
            ct.lower().startswith("application/pdf") or r.content[:4] == b"%PDF"
        )

        if eh_pdf:
            print(f"      [OK] PDF capturado!")

            # Buscar licitacao_id
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

            # Upload para Google Drive
            url_publica = None
            if drive_service and google_folder_id:
                try:
                    file_id, url_publica = upload_para_google_drive(
                        drive_service,
                        r.content,
                        f"{licitacao_id}_{nome_safe}.pdf",
                        google_folder_id
                    )
                    if url_publica:
                        print(f"      [gdrive] OK: {url_publica[:50]}...")
                except Exception as e:
                    print(f"      [gdrive-err] {e}")
            else:
                print(f"      [local] Salvo em: {caminho}")

            # Registrar no banco
            try:
                sb.table("documentos_licitacao").upsert({
                    "licitacao_id": licitacao_id,
                    "nome_arquivo": nome_safe,
                    "nome_doc": nome_doc,
                    "tamanho_bytes": size,
                    "storage_path": url_publica or caminho,
                    "url_publica": url_publica,
                    "erro": None
                }).execute()
                print(f"      [db] Registrado")
                return {"caminho": caminho, "url_publica": url_publica, "tamanho": size}

            except Exception as db_err:
                if "23505" in str(db_err) or "duplicate key" in str(db_err).lower():
                    # Se já existe, fazer UPDATE para registrar a URL do Google Drive
                    try:
                        sb.table("documentos_licitacao").update({
                            "url_publica": url_publica,
                            "storage_path": url_publica or caminho,
                            "tamanho_bytes": size,
                            "erro": None
                        }).eq("licitacao_id", licitacao_id).eq("nome_arquivo", nome_safe).execute()
                        print(f"      [dup] Atualizado com Google Drive URL")
                        return {"caminho": caminho, "url_publica": url_publica, "tamanho": size}
                    except Exception as update_err:
                        print(f"      [dup-update-err] {update_err}")
                        return {"caminho": caminho, "url_publica": url_publica, "tamanho": size}
                else:
                    print(f"      [db-err] {db_err}")
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
    print("ETAPA 3 FINAL: Coleta de Documentos - GET+POST JSF + Google Drive")
    print("=" * 70)
    print()

    # Setup Google Drive
    drive_service = setup_google_drive()
    google_folder_id = GOOGLE_DRIVE_FOLDER_ID

    stats = {"docs_baixados": 0, "erros": 0, "pags_processadas": 0}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, slow_mo=SLOW_MO)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        try:
            print("[init] Acessando portal...")
            page.goto(PORTAL_URL, wait_until='domcontentloaded')
            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except PlaywrightTimeout:
                pass  # Continuar mesmo se timeout
            time.sleep(1)
            time.sleep(2)

            print("[init] Pesquisando...")
            total = fazer_pesquisa(page)
            print(f"[init] Total: {total}")

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

                    try:
                        if not abrir_detalhe(page, proc):
                            print(f"    [!] Falha ao abrir")
                            stats["erros"] += 1
                            continue

                        if not abrir_modal_documentos(page):
                            print(f"    [!] Modal nao abriu")
                            stats["erros"] += 1
                            try:
                                voltar_para_lista(page)
                            except:
                                pass
                            continue

                        docs = extrair_documentos_da_modal(page)
                        if not docs:
                            print(f"    [sem_docs]")
                            try:
                                voltar_para_lista(page)
                            except:
                                pass
                            continue

                        for j, doc in enumerate(docs[:MAX_DOCS_POR_LIC]):
                            resultado = baixar_documento_final(page, doc, texto, drive_service, google_folder_id)
                            if resultado:
                                stats["docs_baixados"] += 1
                            else:
                                stats["erros"] += 1

                            if j < len(docs[:MAX_DOCS_POR_LIC]) - 1:
                                time.sleep(0.5)

                        try:
                            fechar_modal(page)
                            voltar_para_lista(page)
                        except:
                            pass
                        time.sleep(DELAY)
                    except Exception as e:
                        print(f"    [!] Erro ao processar licitação: {e}")
                        stats["erros"] += 1
                        try:
                            voltar_para_lista(page)
                        except:
                            pass

                # Próxima página
                if page_num < num_paginas:
                    print(f"\n[page-nav] Ir para página {page_num + 1}/{num_paginas}...")
                    try:
                        btn_next = page.locator("td.rich-datascr-button:not(.rich-datascr-button-dsbld)[onclick*=\"'page': 'next'\"]")
                        if btn_next.count() > 0:
                            print(f"[page-nav] Botão encontrado, tentando clicar...")
                            # Tentar scroll para o botão ficar visível
                            try:
                                btn_next.first.scroll_into_view()
                                time.sleep(0.5)
                            except:
                                pass

                            # Tentar clicar diretamente
                            try:
                                btn_next.first.click(timeout=5000, force=True)
                                print(f"[page-nav] Clicado!")
                                time.sleep(2)
                                try:
                                    page.wait_for_load_state("networkidle", timeout=40000)
                                except PlaywrightTimeout:
                                    pass
                                time.sleep(1)
                                page_num += 1
                            except Exception as click_err:
                                # Se clicar falhar, tentar via JavaScript
                                print(f"[page-nav] Click falhou, tentando JavaScript...")
                                try:
                                    page.evaluate("document.querySelector(\"td.rich-datascr-button:not(.rich-datascr-button-dsbld)[onclick*=\\\"'page': 'next'\\\"]\").click()")
                                    print(f"[page-nav] JavaScript click OK")
                                    time.sleep(2)
                                    try:
                                        page.wait_for_load_state("networkidle", timeout=40000)
                                    except PlaywrightTimeout:
                                        pass
                                    time.sleep(1)
                                    page_num += 1
                                except Exception as js_err:
                                    print(f"[page-nav] JavaScript também falhou: {js_err}")
                                    print(f"[page-nav] Continuando mesmo assim...")
                                    # Continuar para próxima página
                                    page_num += 1
                        else:
                            print(f"[page-nav] Botão próxima não encontrado ou desativado")
                            break
                    except Exception as e:
                        print(f"[page-nav] Erro ao navegar: {str(e)[:100]}")
                        print(f"[page-nav] Tentando reload da página...")
                        try:
                            page.reload(wait_until='domcontentloaded', timeout=30000)
                        except:
                            pass
                        print(f"[page-nav] Continuando para próxima...")
                        page_num += 1
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
