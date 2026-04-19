"""
ETAPA 3 SIMPLIFICADA: Coleta de PDFs baseada em vw_itens_agro
Busca apenas processos que estão na view de itens da AgroIA
"""

import os
import re
import time
import requests
import pickle
import unicodedata
from dotenv import load_dotenv
from supabase import create_client
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from io import BytesIO

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
PORTAL_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/searchLicitacao.jsf"

# Config
HEADLESS = True
SLOW_MO = 0
DEBUG = True

# Inicializar Supabase
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── Google Drive Setup ────────────────────────────────────────────────────────

def setup_google_drive():
    """Configurar Google Drive API usando token.pickle"""
    if not os.path.exists("token.pickle"):
        print("[!] token.pickle não encontrado")
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
            'parents': [folder_id]
        }

        media = MediaIoBaseUpload(
            BytesIO(arquivo_bytes),
            mimetype='application/pdf',
            resumable=True
        )

        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webContentLink'
        ).execute()

        # Dar permissão de leitura pública
        drive_service.permissions().create(
            fileId=file['id'],
            body={'role': 'reader', 'type': 'anyone'}
        ).execute()

        return file.get('webContentLink')
    except Exception as e:
        print(f"[gdrive-err] {e}")
        return None

# ─── Funções do Portal ────────────────────────────────────────────────────────

def sanitizar_nome_arquivo(texto):
    """Sanitizar nome de arquivo removendo caracteres especiais"""
    sem_acentos = unicodedata.normalize('NFD', texto)
    sem_acentos = ''.join(c for c in sem_acentos if unicodedata.category(c) != 'Mn')
    safe = re.sub(r'[^\w\-]', '_', sem_acentos)
    return safe[:100]

def abrir_detalhe_processo(page, numero_processo, linha_index):
    """Abrir página de detalhe de um processo"""
    try:
        link_id = f"form:tabela:{linha_index}:j_id26"
        elem = page.locator(f'[id="{link_id}"]')
        if elem.count() == 0:
            return False
        elem.first.click()
        time.sleep(1.5)
        try:
            page.wait_for_load_state("networkidle", timeout=30000)
        except PlaywrightTimeout:
            pass
        return True
    except Exception:
        return False

def abrir_modal_documentos(page):
    """Abrir modal de documentos"""
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
    """Extrair lista de documentos do modal"""
    from bs4 import BeautifulSoup

    html = page.content()
    soup = BeautifulSoup(html, "lxml")
    tabela = soup.find("table", id="form:tabelaDocumentos")

    if not tabela:
        return []

    documentos = []
    rows = tabela.find_all("tr")[1:]

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
        if not inp_id:
            continue

        documentos.append({
            "nome": nome_doc,
            "input_id": inp_id,
            "index": i
        })

    return documentos

def baixar_documento(page, doc, numero_processo, drive_service, folder_id):
    """Baixar documento via GET+POST JSF"""
    try:
        # 1. Clicar no documento para armazenar na sessão
        btn_doc = page.locator(f'[id="{doc["input_id"]}"]')
        if btn_doc.count() == 0:
            return None

        btn_doc.first.click()
        time.sleep(1)

        # 2. GET request para obter a forma com ViewState
        try:
            page.goto("http://consultalicitacao.curitiba.pr.gov.br:9090/download.jsf",
                     wait_until="domcontentloaded", timeout=30000)
        except:
            return None

        html = page.content()
        m = re.search(r'javax\.faces\.ViewState"\s+value="([^"]+)"', html)
        if not m:
            print(f"      [!] ViewState não encontrado")
            return None

        viewstate = m.group(1)

        # 3. POST request para download
        session_cookies = page.context.cookies()
        cookies = {c['name']: c['value'] for c in session_cookies}

        try:
            resp = requests.post(
                "http://consultalicitacao.curitiba.pr.gov.br:9090/download.jsf",
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
                print(f"      [pdf] 200 {resp.headers.get('content-type')} {size:.1f}MB")
                print(f"      [OK] PDF capturado!")

                # Upload para Google Drive
                nome_safe = sanitizar_nome_arquivo(doc["nome"])
                url_publica = upload_para_google_drive(
                    drive_service, resp.content, nome_safe, folder_id
                )

                if url_publica:
                    print(f"      [gdrive] OK: {url_publica[:50]}...")
                    return {
                        "url": url_publica,
                        "tamanho": int(len(resp.content)),
                        "nome": nome_safe
                    }
            else:
                print(f"      [!] Erro: Status {resp.status_code}")
                return None

        except Exception as e:
            print(f"      [!] Erro no POST: {e}")
            return None

    except Exception as e:
        print(f"      [!] Erro ao baixar: {e}")
        return None

def voltar_para_lista(page):
    """Voltar para a lista de licitações"""
    try:
        btn = page.locator('[id="form:abaPesquisa_lbl"]')
        if btn.count() > 0:
            btn.first.click()
            time.sleep(2)
            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except PlaywrightTimeout:
                pass
            return True
    except:
        pass
    return False

def fechar_modal(page):
    """Fechar modal de documentos"""
    try:
        page.evaluate('if (window.Richfaces) Richfaces.hideModalPanel("form:documentos")')
        time.sleep(0.5)
    except:
        pass

# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 70)
    print("ETAPA 3 SIMPLIFICADA: Coleta baseada em vw_itens_agro")
    print("=" * 70)
    print()

    # Setup Google Drive
    drive_service = setup_google_drive()
    google_folder_id = GOOGLE_DRIVE_FOLDER_ID

    # Buscar licitações da view
    print("[init] Buscando licitações de vw_itens_agro...")
    result = sb.table("vw_itens_agro").select("licitacao_id, processo").execute()

    # Extrair licitacao_id únicos
    licitacoes = {}
    for row in result.data:
        lic_id = row['licitacao_id']
        if lic_id not in licitacoes:
            licitacoes[lic_id] = row['processo']

    print(f"[init] Encontradas {len(licitacoes)} licitações únicas")
    print(f"[init] Processando...")
    print()

    stats = {"docs_baixados": 0, "erros": 0, "processadas": 0}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, slow_mo=SLOW_MO)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        try:
            # Acessar portal
            page.goto(PORTAL_URL, wait_until='domcontentloaded')
            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except PlaywrightTimeout:
                pass
            time.sleep(2)

            # Processar cada licitação
            for i, (lic_id, nome_processo) in enumerate(licitacoes.items(), 1):
                print(f"[{i}/{len(licitacoes)}] {nome_processo}")

                try:
                    # Navegar usando a caixa de pesquisa
                    search_box = page.locator('input[id*="pesquisa"]')
                    if search_box.count() > 0:
                        search_box.first.fill(str(lic_id))
                        time.sleep(0.5)
                        search_box.first.press("Enter")
                        time.sleep(3)

                    # Abrir primeiro resultado
                    btn_detalhe = page.locator('a[href*="searchLicitacao"], input[value="Abrir"]')
                    if btn_detalhe.count() > 0:
                        btn_detalhe.first.click()
                        time.sleep(2)

                    # Abrir modal
                    if not abrir_modal_documentos(page):
                        print(f"  [!] Modal não abriu")
                        stats["erros"] += 1
                        voltar_para_lista(page)
                        continue

                    # Extrair documentos
                    docs = extrair_documentos_da_modal(page)
                    if not docs:
                        print(f"  [sem_docs]")
                        voltar_para_lista(page)
                        continue

                    # Baixar cada documento
                    for doc in docs:
                        resultado = baixar_documento(page, doc, nome_processo, drive_service, google_folder_id)

                        if resultado:
                            # Registrar no banco
                            try:
                                sb.table("documentos_licitacao").insert({
                                    "licitacao_id": lic_id,
                                    "nome_arquivo": resultado["nome"],
                                    "nome_doc": doc["nome"],
                                    "tamanho_bytes": resultado["tamanho"],
                                    "url_publica": resultado["url"],
                                    "storage_path": resultado["url"],
                                    "erro": None
                                }).execute()
                                stats["docs_baixados"] += 1
                            except Exception as e:
                                if "23505" not in str(e):
                                    print(f"      [db-err] {e}")

                    fechar_modal(page)
                    voltar_para_lista(page)
                    time.sleep(1)
                    stats["processadas"] += 1

                except Exception as e:
                    print(f"  [!] Erro: {e}")
                    stats["erros"] += 1
                    try:
                        voltar_para_lista(page)
                    except:
                        pass

        finally:
            browser.close()

    print("\n" + "=" * 70)
    print("RESUMO:")
    print(f"  Licitações processadas: {stats['processadas']}")
    print(f"  Docs baixados: {stats['docs_baixados']}")
    print(f"  Erros: {stats['erros']}")
    print("=" * 70)

if __name__ == "__main__":
    main()
