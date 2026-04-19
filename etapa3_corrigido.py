"""
AgroIA-RMC — Coleta Corrigida de Documentos
============================================

FLUXO ENTENDIDO:
1. Clicar em documento → AJAX com document ID (17466 no exemplo)
2. AJAX completa → server registra doc_id na sessão
3. Callback AJAX chama open_download() → abre nova janela com download.jsf
4. Playwright captura a nova aba/download via expect_page() ou expect_download()

Execute: python etapa3_corrigido.py
"""

import os
import time
import re
import pickle
import unicodedata
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
from supabase import create_client
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

load_dotenv()

# ─── Config ───────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

PORTAL_URL = (
    "http://consultalicitacao.curitiba.pr.gov.br:9090/"
    "ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
)

ORGAO = "SMSAN/FAAC"
DT_INICIO = "01/01/2019"
DT_FIM = "30/04/2026"

DEBUG = True
HEADLESS = True
PASTA_DOWNLOADS = "pdfs_downloads"

Path(PASTA_DOWNLOADS).mkdir(exist_ok=True)

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── Google Drive ──────────────────────────────────────────────────────────

def setup_google_drive():
    """Setup Google Drive via token.pickle"""
    if not os.path.exists("token.pickle"):
        print("[!] token.pickle não encontrado")
        return None
    try:
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
        drive_service = build('drive', 'v3', credentials=creds)
        print("[OK] Google Drive conectado")
        return drive_service
    except Exception as e:
        print(f"[!] Erro Google Drive: {e}")
        return None

def upload_para_google_drive(drive_service, caminho, nome, folder_id):
    """Upload arquivo para Google Drive e retorna URL pública"""
    try:
        file_metadata = {
            'name': nome,
            'parents': [folder_id] if folder_id else []
        }
        media = MediaFileUpload(caminho, mimetype='application/pdf')
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()

        file_id = file.get('id')
        drive_service.permissions().create(
            fileId=file_id,
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()

        web_link = file.get('webViewLink')
        print(f"        [OK] Upload: {web_link[:50]}...")
        return web_link
    except Exception as e:
        print(f"        [!] Erro upload: {e}")
        return None

# ─── Portal Helpers ───────────────────────────────────────────────────────

def preencher_data(page, campo_id, valor):
    """Preencher campo de data"""
    campo = page.locator(f'[id="{campo_id}"]')
    try:
        campo.wait_for(state="visible", timeout=15000)
        campo.click(click_count=3)
        time.sleep(0.2)
        page.keyboard.type(valor, delay=50)
        time.sleep(0.3)
        page.keyboard.press("Tab")
        time.sleep(0.5)
        return True
    except:
        return False

def selecionar_opcao(page, texto_opcao):
    """Selecionar em select HTML"""
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
                except:
                    pass
                time.sleep(0.5)
                return True
        except PlaywrightTimeout:
            continue
    return False

def fazer_pesquisa(page):
    """Pesquisar licitações"""
    print("[Pesquisa] Aguardando...")
    try:
        page.wait_for_selector("select", state="visible", timeout=20000)
    except:
        pass
    time.sleep(1)

    print("[Pesquisa] Preenchendo...")
    selecionar_opcao(page, ORGAO)
    preencher_data(page, "form:dataInferiorInputDate", DT_INICIO)
    preencher_data(page, "form:j_id18InputDate", DT_FIM)

    print("[Pesquisa] Enviando...")
    btn = page.locator('[id="form:btSearch"], input[value="Pesquisar"]')
    if btn.count() == 0:
        return 0
    btn.first.wait_for(state="visible", timeout=15000)
    btn.first.click()
    time.sleep(3)
    try:
        page.wait_for_load_state("networkidle", timeout=30000)
    except:
        pass

    html = page.content()
    m = re.search(r"quantidade registros.*?(\d+)</label>", html, re.I | re.DOTALL)
    total = int(m.group(1)) if m else 0
    print(f"[Pesquisa] Total: {total}")
    return total

def extrair_processos(page):
    """Extrair processos da página"""
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

def abrir_processo(page, processo):
    """Abrir página de detalhe"""
    link = page.locator(f'[id="{processo["link_id"]}"]')
    if link.count() == 0:
        return False
    link.first.click()
    time.sleep(1.5)
    try:
        page.wait_for_load_state("networkidle", timeout=30000)
    except:
        pass
    return True

def voltar_para_lista(page):
    """Voltar para listagem"""
    aba = page.locator('[id="form:abaPesquisa_lbl"]')
    if aba.count() > 0:
        aba.first.click()
        time.sleep(1.5)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass

def coletar_documentos(page, drive_service):
    """Coletar documentos do modal"""
    docs_coletados = 0

    # Abrir modal
    btn = page.locator('[id="form:j_id111"]')
    if btn.count() == 0:
        return docs_coletados

    btn.first.click()
    time.sleep(2)
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except:
        pass
    time.sleep(0.5)

    # Extrair documentos
    html = page.content()
    soup = BeautifulSoup(html, "lxml")
    tabela = soup.find("table", id="form:tabelaDocumentos")

    if not tabela:
        try:
            page.evaluate("Richfaces.hideModalPanel('form:documentos')")
        except:
            pass
        return docs_coletados

    rows = tabela.find_all("tr")[1:]
    print(f"      Documentos: {len(rows)}")

    # Processar cada documento
    for i, tr in enumerate(rows[:5]):  # Máximo 5 docs por licitação
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue

        nome_doc = tds[0].get_text(strip=True)
        col_arq = tds[1]
        inp = col_arq.find("input")

        if not inp:
            continue

        inp_id = inp.get("id", "")
        if not inp_id:
            continue

        print(f"        [{i+1}] {nome_doc[:30]}...")

        # Clicar e capturar download
        try:
            elem = page.locator(f'[id="{inp_id}"]')
            if elem.count() == 0:
                continue

            # Esperá por nova página (popup com download.jsf)
            with page.context.expect_page(timeout=10000) as nova_pag_info:
                elem.first.click()
                time.sleep(0.5)

            nova_pag = nova_pag_info.value
            print(f"        [Popup] {nova_pag.url}")

            # Aguardar carregamento da nova página
            time.sleep(1)
            try:
                nova_pag.wait_for_load_state("networkidle", timeout=10000)
            except:
                pass

            # Capturar download na nova página
            try:
                with nova_pag.expect_download(timeout=10000) as download_info:
                    # Pode precisar clicar em algo ou a página auto-baixa
                    # Procurar por botão de download
                    btns = nova_pag.locator("button, input[type='button'], input[type='submit']")
                    if btns.count() > 0:
                        print(f"        [Click] Botão encontrado ({btns.count()})")
                        btns.first.click()

                    time.sleep(3)  # Dar tempo para iniciar download

                download = download_info.value
                print(f"        [OK] Baixado: {download.suggested_filename}")

                # Salvar localmente
                nome_safe = re.sub(r'[^\w\-_.]', '_', nome_doc)
                nome_arquivo = f"{nome_safe}.pdf"
                caminho_local = os.path.join(PASTA_DOWNLOADS, nome_arquivo)

                download.save_as(caminho_local)

                # Upload Google Drive
                if drive_service and GOOGLE_DRIVE_FOLDER_ID:
                    url = upload_para_google_drive(
                        drive_service,
                        caminho_local,
                        nome_arquivo,
                        GOOGLE_DRIVE_FOLDER_ID
                    )
                    if url:
                        docs_coletados += 1
                else:
                    docs_coletados += 1

            except PlaywrightTimeout:
                print(f"        [!] Timeout no download")
            except Exception as e:
                print(f"        [!] Erro download: {e}")
            finally:
                try:
                    nova_pag.close()
                except:
                    pass

        except Exception as e:
            print(f"        [!] Erro: {e}")

    # Fechar modal
    try:
        page.evaluate("Richfaces.hideModalPanel('form:documentos')")
    except:
        pass
    time.sleep(0.5)

    return docs_coletados

# ─── Main ──────────────────────────────────────────────────────────────────

def main():
    drive_service = setup_google_drive()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        stats = {
            'processos_abertos': 0,
            'docs_coletados': 0,
            'erros': 0
        }

        try:
            print("\n" + "=" * 70)
            print("COLETA DE DOCUMENTOS - VERSÃO CORRIGIDA")
            print("=" * 70)

            print(f"\n[1] Acessando portal...")
            page.goto(PORTAL_URL, wait_until='domcontentloaded')
            time.sleep(2)

            print(f"\n[2] Pesquisando...")
            total = fazer_pesquisa(page)

            if total == 0:
                print("[!] Nenhuma licitação encontrada")
                return

            print(f"\n[3] Coletando documentos...")

            processos = extrair_processos(page)
            print(f"    Encontrados: {len(processos)} processos na página")

            # Processar primeiros 5 processos
            for idx, proc in enumerate(processos[:5]):
                print(f"\n  [{idx+1}] {proc['texto']}")

                if not abrir_processo(page, proc):
                    print(f"      [!] Falha ao abrir")
                    stats['erros'] += 1
                    continue

                stats['processos_abertos'] += 1

                docs = coletar_documentos(page, drive_service)
                stats['docs_coletados'] += docs

                print(f"      [Total] {docs} documentos")

                voltar_para_lista(page)
                time.sleep(1)

            # Resumo
            print("\n" + "=" * 70)
            print("RESUMO")
            print("=" * 70)
            print(f"Processos abertos: {stats['processos_abertos']}")
            print(f"Documentos coletados: {stats['docs_coletados']}")
            print(f"Erros: {stats['erros']}")

        except Exception as e:
            print(f"\n[ERRO] {e}")
            import traceback
            traceback.print_exc()
        finally:
            browser.close()

if __name__ == "__main__":
    main()
