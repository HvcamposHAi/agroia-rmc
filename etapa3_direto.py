"""
ETAPA 3 - DIRETO: Coleta de PDFs por acesso direto aos processos

Estratégia: Em vez de fazer busca + paginação (que falha),
acessar diretamente cada processo pelos 326 que estão em vw_itens_agro.

Vantagens:
- Sem problema de paginação
- Mais rápido
- Mais confiável
- Processa apenas o que é necessário
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

DEBUG = True
HEADLESS = True
DELAY = 0.5

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

def setup_google_drive():
    """Setup Google Drive usando token.pickle"""
    if not os.path.exists("token.pickle"):
        print("[!] token.pickle não encontrado")
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
    """Upload para Google Drive"""
    try:
        file_metadata = {'name': nome_arquivo, 'parents': [folder_id]}
        media = MediaIoBaseUpload(BytesIO(arquivo_bytes), mimetype='application/pdf', resumable=True)
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webContentLink').execute()

        # Dar permissão pública
        drive_service.permissions().create(
            fileId=file['id'],
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()

        return file.get('webContentLink')
    except Exception as e:
        print(f"[gdrive-err] {e}")
        return None

def sanitizar_nome(texto):
    """Sanitizar nome de arquivo"""
    nfd = unicodedata.normalize('NFD', texto)
    sem_acentos = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
    safe = re.sub(r'[^\w\-]', '_', sem_acentos)
    return safe[:100]

def abrir_modal(page):
    """Abrir modal de documentos"""
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
    except Exception as e:
        if DEBUG:
            print(f"[modal-err] {e}")
        return False

def extrair_documentos(page):
    """Extrair documentos da modal"""
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
    """Baixar documento via GET+POST"""
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

def main():
    print("\n" + "=" * 70)
    print("ETAPA 3 - ACESSO DIRETO: Coleta de PDFs dos 326 processos")
    print("=" * 70)
    print()

    # Carregar processos de vw_itens_agro - APENAS PE (Pregão Eletrônico)
    # Nota: Só PE tem botão "Documentos da licitação"
    print("[init] Carregando processos PE de vw_itens_agro...")
    try:
        # Buscar processos e depois filtrar por PE
        result = sb.table("vw_itens_agro").select("licitacao_id, processo").execute()

        processos_map = {}
        for row in result.data:
            lic_id = row['licitacao_id']
            processo = row['processo']
            # Filtrar apenas PE (Pregão Eletrônico)
            if processo.startswith("PE "):
                if lic_id not in processos_map:
                    processos_map[lic_id] = processo

        print(f"[init] {len(processos_map)} licitações PE para processar")
    except Exception as e:
        print(f"[!] Erro ao carregar processos: {e}")
        return

    drive_service = setup_google_drive()
    folder_id = GOOGLE_DRIVE_FOLDER_ID

    stats = {"docs_baixados": 0, "erros": 0, "processadas": 0, "sem_docs": 0}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        try:
            page.goto(DETALHE_URL, wait_until='domcontentloaded')
            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except PlaywrightTimeout:
                pass
            time.sleep(1)

            # Processar cada licitação
            for idx, (lic_id, processo) in enumerate(processos_map.items(), 1):
                print(f"\n[{idx}/{len(processos_map)}] {processo} (ID: {lic_id})")

                try:
                    # Abrir modal
                    if not abrir_modal(page):
                        print(f"  [!] Modal não abriu")
                        stats["erros"] += 1
                        continue

                    # Extrair documentos
                    docs = extrair_documentos(page)
                    if not docs:
                        print(f"  [sem_docs]")
                        stats["sem_docs"] += 1
                        try:
                            page.evaluate('Richfaces.hideModalPanel("form:documentos")')
                        except:
                            pass
                        continue

                    print(f"  Docs: {len(docs)}")

                    # Baixar cada documento
                    for doc in docs:
                        resultado = baixar_documento(page, doc, lic_id, drive_service, folder_id)
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
                            except Exception as db_err:
                                if "23505" not in str(db_err):
                                    print(f"      [db-err] {db_err}")

                    # Fechar modal
                    try:
                        page.evaluate('Richfaces.hideModalPanel("form:documentos")')
                    except:
                        pass

                    stats["processadas"] += 1
                    time.sleep(DELAY)

                    # Refresh página a cada 10 licitações para evitar degradação de estado
                    if idx % 10 == 0:
                        print(f"[refresh] Atualizando página...")
                        page.goto(DETALHE_URL, wait_until='domcontentloaded')
                        try:
                            page.wait_for_load_state("networkidle", timeout=20000)
                        except PlaywrightTimeout:
                            pass
                        time.sleep(1)

                except Exception as e:
                    print(f"  [!] Erro: {e}")
                    stats["erros"] += 1
                    try:
                        page.goto(DETALHE_URL)
                    except:
                        pass

        finally:
            try:
                browser.close()
            except:
                pass

    print("\n" + "=" * 70)
    print("RESUMO:")
    print(f"  Licitações processadas: {stats['processadas']}")
    print(f"  Docs baixados: {stats['docs_baixados']}")
    print(f"  Sem documentos: {stats['sem_docs']}")
    print(f"  Erros: {stats['erros']}")
    print("=" * 70)

if __name__ == "__main__":
    main()
