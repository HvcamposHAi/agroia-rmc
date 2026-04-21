"""
Coleta Direcionada: PDFs dos 24 Processos Críticos com Empenhos
===============================================================

Coleta APENAS licitações que têm empenhos mas SEM documentação.

Execute:
  python coleta_criticos.py

Processos críticos:
  545, 1321, 1256, 1184, 1180, 1261, 1304, 1268, 626, 1359,
  1191, 1294, 1353, 1195, 1198, 1285, 1202, 402, 1146, 1189,
  1201, 1204, 1345, 1349
"""

import os
import sys
import time
import json
import pickle
import io
from datetime import datetime
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
from supabase import create_client
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload

# Force UTF-8 on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

PORTAL_URL = "https://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/"
ORGAO = "SMSAN/FAAC"
DT_INICIO = "01/01/2019"
DT_FIM = "30/04/2026"

LOG_FILE = "coleta_criticos.log"
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# IDs dos 24 processos críticos com empenhos mas SEM documentação
LICITACAO_IDS_CRITICOS = [
    545, 1321, 1256, 1184, 1180, 1261, 1304, 1268, 626, 1359,
    1191, 1294, 1353, 1195, 1198, 1285, 1202, 402, 1146, 1189,
    1201, 1204, 1345, 1349
]

def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    linha = f"[{ts}] [{level}] {msg}"
    print(linha)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(linha + "\n")

def setup_google_drive():
    if not os.path.exists("token.pickle"):
        log("token.pickle nao encontrado", "ERROR")
        return None
    try:
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
        drive_service = build('drive', 'v3', credentials=creds)
        log("Google Drive conectado")
        return drive_service
    except Exception as e:
        log(f"Erro Google Drive: {e}", "ERROR")
        return None

def upload_google_drive(drive_service, arquivo_bytes, nome, folder_id):
    if not drive_service:
        return None
    try:
        file_metadata = {
            'name': nome,
            'parents': [folder_id],
            'mimeType': 'application/pdf'
        }
        media = MediaIoBaseUpload(io.BytesIO(arquivo_bytes), mimetype='application/pdf', resumable=True)
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return file.get('id')
    except Exception as e:
        log(f"Erro upload Google Drive: {e}", "WARN")
        return None

def fazer_pesquisa(page):
    """Preenche formulário de pesquisa e faz busca."""
    try:
        # Data inicio
        page.locator('[id="form:dataInferiorInputDate"]').click(click_count=3)
        page.keyboard.type(DT_INICIO)
        page.keyboard.press("Tab")
        time.sleep(0.5)

        # Data fim
        page.locator('[id="form:dataFimInputDate"]').click(click_count=3)
        page.keyboard.type(DT_FIM)
        page.keyboard.press("Tab")
        time.sleep(0.5)

        # Órgão
        orgao_field = page.locator('[id="form:orgaoInputText"]')
        orgao_field.click(click_count=3)
        orgao_field.fill(ORGAO)
        page.keyboard.press("Tab")
        time.sleep(0.5)

        # Pesquisar
        page.locator('[id="form:botaoPesquisar"]').click()
        page.wait_for_load_state('networkidle')
        time.sleep(1)

        log("Pesquisa realizada com sucesso")
        return True
    except Exception as e:
        log(f"Erro ao pesquisar: {e}", "ERROR")
        return False

def extrair_processos(page):
    """Extrai lista de processos da página atual."""
    try:
        html = page.content()
        soup = BeautifulSoup(html, 'html.parser')
        tabela = soup.find('table', {'id': 'form:tabela'})

        if not tabela:
            return []

        processos = []
        rows = tabela.find_all('tr')[1:]  # Skip header

        for i, row in enumerate(rows):
            try:
                cols = row.find_all('td')
                if len(cols) >= 2:
                    processo_text = cols[1].get_text(strip=True)
                    processos.append({
                        'texto': processo_text,
                        'indice': i
                    })
            except:
                continue

        return processos
    except Exception as e:
        log(f"Erro ao extrair processos: {e}", "ERROR")
        return []

def abrir_processo(page, proc):
    """Abre um processo específico."""
    try:
        selector = f'[id="form:tabela:{proc["indice"]}:j_id26"]'
        page.locator(selector).click()
        page.wait_for_load_state('networkidle')
        time.sleep(1)
        return True
    except Exception as e:
        log(f"Erro ao abrir processo: {e}", "WARN")
        return False

def coletar_documentos(page, drive_service, processo_texto):
    """Coleta documentos de um processo aberto."""
    docs_coletados = 0
    try:
        # Obter dados do processo atual (formulário oculto)
        pagina_html = page.content()
        soup = BeautifulSoup(pagina_html, 'html.parser')

        # Buscar botões de download na tabela de documentos
        try:
            docs_table = soup.find('table', {'id': 'form:tabelaDocs'})
            if not docs_table:
                return 0

            rows = docs_table.find_all('tr')[1:]

            for row in rows:
                try:
                    cols = row.find_all('td')
                    if len(cols) < 2:
                        continue

                    doc_name = cols[0].get_text(strip=True)

                    # Procurar link/botão de download
                    download_link = row.find('a', href=True)
                    if not download_link:
                        continue

                    log(f"  Baixando: {doc_name[:50]}...")

                    # Fazer download
                    with page.expect_download() as download_info:
                        download_link.click()

                    download = download_info.value
                    arquivo_bytes = download.read_buffer()

                    # Salvar em Supabase + Google Drive
                    nome_arquivo = f"{processo_texto.replace(' ', '_')}_{doc_name[:20]}.pdf"

                    # Supabase Storage
                    try:
                        sb.storage.from_("licitacoes_pdfs").upload(
                            f"pdfs/{nome_arquivo}",
                            arquivo_bytes,
                            {"content-type": "application/pdf"}
                        )
                        log(f"    [Supabase] Salvo", "INFO")
                    except Exception as e:
                        if "already exists" not in str(e):
                            log(f"    [Supabase] Erro: {e}", "WARN")

                    # Google Drive
                    gd_id = upload_google_drive(drive_service, arquivo_bytes, nome_arquivo, GOOGLE_DRIVE_FOLDER_ID)
                    if gd_id:
                        log(f"    [GoogleDrive] Salvo (ID={gd_id})", "INFO")

                    docs_coletados += 1

                except Exception as e:
                    log(f"    Erro ao processar doc: {e}", "WARN")
                    continue

        except Exception as e:
            log(f"  Erro ao processar tabela de docs: {e}", "WARN")

    except Exception as e:
        log(f"Erro ao coletar documentos: {e}", "ERROR")

    return docs_coletados

def voltar_para_lista(page):
    """Volta para a lista de licitações."""
    try:
        page.locator('[id="form:abaPesquisa_lbl"]').click()
        page.wait_for_load_state('networkidle')
        time.sleep(0.5)
    except Exception as e:
        log(f"Erro ao voltar: {e}", "WARN")

def main():
    log("=" * 70)
    log("COLETA DIRECIONADA: 24 PROCESSOS CRÍTICOS COM EMPENHOS")
    log("=" * 70)

    # Buscar info dos processos críticos no BD
    log(f"\nCarregando info dos {len(LICITACAO_IDS_CRITICOS)} processos críticos...")
    processos_criticos = []

    for lic_id in LICITACAO_IDS_CRITICOS:
        try:
            result = sb.from_("licitacoes").select("id, processo, dt_abertura").eq("id", lic_id).execute()
            if result.data:
                lic = result.data[0]
                processos_criticos.append({
                    'id': lic_id,
                    'processo': lic['processo'],
                    'dt_abertura': lic['dt_abertura']
                })
        except Exception as e:
            log(f"Erro ao buscar ID {lic_id}: {e}", "WARN")

    log(f"Encontrados {len(processos_criticos)} processos críticos")

    drive_service = setup_google_drive()
    if not GOOGLE_DRIVE_FOLDER_ID:
        log("GOOGLE_DRIVE_FOLDER_ID nao definido", "ERROR")
        return

    total_docs = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        try:
            page.goto(PORTAL_URL, wait_until='domcontentloaded')
            time.sleep(2)

            # Fazer pesquisa geral
            if not fazer_pesquisa(page):
                return

            # Iterar pelos processos críticos encontrados
            log(f"\nColetando documentos dos processos críticos...")

            for i, proc_critico in enumerate(processos_criticos, 1):
                log(f"\n[{i}/{len(processos_criticos)}] {proc_critico['processo']}")

                # Buscar processo na lista
                processos_na_pagina = extrair_processos(page)
                encontrado = False

                for proc_pg in processos_na_pagina:
                    if proc_critico['processo'] in proc_pg['texto']:
                        if abrir_processo(page, proc_pg):
                            docs = coletar_documentos(page, drive_service, proc_critico['processo'])
                            total_docs += docs
                            log(f"  Documentos coletados: {docs}")
                            voltar_para_lista(page)
                            encontrado = True
                            time.sleep(1)
                        break

                if not encontrado:
                    log(f"  Processo nao encontrado na lista", "WARN")

        except Exception as e:
            log(f"Erro fatal: {e}", "ERROR")

        finally:
            browser.close()

    log(f"\n{'=' * 70}")
    log(f"COLETA CONCLUÍDA")
    log(f"Total de documentos coletados: {total_docs}")
    log(f"{'=' * 70}")

if __name__ == "__main__":
    main()
