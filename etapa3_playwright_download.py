"""
AgroIA-RMC — Coleta de Documentos com Playwright Download Handler
===================================================================

ESTRATÉGIA CORRIGIDA:
1. Usar Playwright's download event para capturar PDFs nativamente
2. Não usar requests.get() (sessão JSF não funciona fora do browser)
3. Clicar no documento → Playwright captura o arquivo → Upload Google Drive

Execute: python etapa3_playwright_download.py
"""

import os
import re
import time
import signal
import json
import pickle
import unicodedata
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
from supabase import create_client

# Google Drive
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

load_dotenv()

# ─── Configuração ─────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

PORTAL_URL = (
    "http://consultalicitacao.curitiba.pr.gov.br:9090/"
    "ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
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

PASTA_DOWNLOADS = "pdfs_downloads"
DELAY_POS_AJAX  = 2.0
TIMEOUT_DOWNLOAD = 30000  # 30 segundos

INTERROMPIDO = False

def handler_sigint(sig, frame):
    global INTERROMPIDO
    INTERROMPIDO = True
    print("\n[!] Interrupcao solicitada...")

signal.signal(signal.SIGINT, handler_sigint)

# Criar pasta de downloads
Path(PASTA_DOWNLOADS).mkdir(exist_ok=True)

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
        print("[OK] Google Drive conectado")
        return drive_service
    except Exception as e:
        print(f"[!] Erro ao conectar Google Drive: {e}")
        return None

def upload_para_google_drive(drive_service, caminho_arquivo, nome_arquivo, folder_id):
    """Upload de arquivo para Google Drive"""
    try:
        file_metadata = {
            'name': nome_arquivo,
            'parents': [folder_id] if folder_id else []
        }

        media = MediaFileUpload(caminho_arquivo, mimetype='application/pdf')
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()

        file_id = file.get('id')

        # Compartilhar publicamente
        drive_service.permissions().create(
            fileId=file_id,
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()

        web_link = file.get('webViewLink')
        print(f"    [OK] Upload concluído: {web_link}")
        return web_link
    except Exception as e:
        print(f"    [!] Erro no upload: {e}")
        return None

# ─── Portal Automation ─────────────────────────────────────────────────────────

def preencher_data(page, campo_id, valor):
    """Preencher campo de data - seguir padrão do etapa3_google_drive.py"""
    campo = page.locator(f'[id="{campo_id}"]')

    try:
        if campo.count() == 0:
            return False
    except Exception:
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
    except Exception:
        return False

def selecionar_opcao(page, texto_opcao, debug_label):
    """Selecionar opção em SELECT HTML"""
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
    """Executar pesquisa no portal - usar padrão do etapa3_google_drive.py"""
    print("[Pesquisa] Aguardando elementos...")
    try:
        page.wait_for_selector("select", state="visible", timeout=20000)
    except PlaywrightTimeout:
        pass
    time.sleep(1)

    print("[Pesquisa] Preenchendo filtros...")
    selecionar_opcao(page, ORGAO, "Orgao")
    preencher_data(page, "form:dataInferiorInputDate", DT_INICIO)
    preencher_data(page, "form:j_id18InputDate", DT_FIM)

    # Clicar botão pesquisar
    print("[Pesquisa] Enviando pesquisa...")
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

    # Extrair total
    html = page.content()
    m = re.search(r"quantidade registros.*?(\d+)</label>", html, re.I | re.DOTALL)
    total = int(m.group(1)) if m else 0

    if total == 0:
        print(f"[!] Padrão não encontrado")
        m2 = re.search(r"(\d+)\s*registros", html, re.I)
        if m2:
            total = int(m2.group(1))

    print(f"[Pesquisa] Total encontrado: {total}")
    return total

def extrair_processos_pagina(page):
    """Extrair processos da página atual"""
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
    """Abrir página de detalhe do processo"""
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
    """Voltar para página de pesquisa"""
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
    """Extrair informações dos documentos da modal"""
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
    """Fechar modal de documentos"""
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

def baixar_documento_playwright(page, doc, drive_service, folder_id):
    """Baixar documento usando Playwright's native download handler"""
    locator_str = doc["locator_str"]
    nome_doc = doc["nome"]

    elem = page.locator(locator_str)
    if elem.count() == 0:
        return None

    print(f"      [click] {nome_doc[:30]}...")

    try:
        # Esperar pelo download usando o mecanismo nativo do Playwright
        with page.expect_download(timeout=TIMEOUT_DOWNLOAD) as download_info:
            elem.first.click()
            time.sleep(0.5)

        download = download_info.value

        # Salvar arquivo localmente
        nome_sanitizado = unicodedata.normalize('NFD', nome_doc)
        nome_sanitizado = ''.join(c for c in nome_sanitizado if unicodedata.category(c) != 'Mn')
        nome_sanitizado = re.sub(r'[^\w\-_.]', '_', nome_sanitizado)

        nome_arquivo = f"{nome_sanitizado}_{download.suggested_filename}"
        caminho_local = os.path.join(PASTA_DOWNLOADS, nome_arquivo)

        download.save_as(caminho_local)
        print(f"      [OK] Salvo: {caminho_local}")

        # Upload para Google Drive
        if drive_service and folder_id:
            url_drive = upload_para_google_drive(drive_service, caminho_local, nome_arquivo, folder_id)
            if url_drive:
                return url_drive

        return "local"

    except PlaywrightTimeout:
        print(f"      [!] Timeout no download")
        return None
    except Exception as e:
        print(f"      [!] Erro: {e}")
        return None

def coletar_documentos(page, drive_service):
    """Coletar documentos do modal"""
    docs_coletados = 0

    if not abrir_modal_documentos(page):
        print("      [!] Falha ao abrir modal")
        return docs_coletados

    documentos = extrair_documentos_da_modal(page)

    if not documentos:
        print("      [!] Nenhum documento encontrado")
        fechar_modal(page)
        return docs_coletados

    # Processar cada documento até MAX_DOCS_POR_LIC
    for i, doc in enumerate(documentos[:MAX_DOCS_POR_LIC]):
        if INTERROMPIDO:
            break

        try:
            result = baixar_documento_playwright(page, doc, drive_service, GOOGLE_DRIVE_FOLDER_ID)
            if result:
                docs_coletados += 1
        except Exception as e:
            print(f"      [!] Erro ao processar doc {i}: {e}")

    fechar_modal(page)
    return docs_coletados

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    global INTERROMPIDO

    # Setup Google Drive
    drive_service = setup_google_drive()
    if not GOOGLE_DRIVE_FOLDER_ID:
        print("[!] GOOGLE_DRIVE_FOLDER_ID não definido no .env")
        return

    # Estatísticas
    stats = {
        'total_pesquisados': 0,
        'total_abertos': 0,
        'total_docs_coletados': 0,
        'erros': []
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, slow_mo=SLOW_MO)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        try:
            print("\n" + "=" * 70)
            print("COLETA DE DOCUMENTOS COM PLAYWRIGHT DOWNLOAD HANDLER")
            print("=" * 70)

            # Acessar portal
            print(f"\n[1] Acessando portal...")
            page.goto(PORTAL_URL, wait_until='domcontentloaded')
            time.sleep(2)

            # Fazer pesquisa
            print(f"\n[2] Fazendo pesquisa ({ORGAO}, {DT_INICIO} a {DT_FIM})...")
            total = fazer_pesquisa(page)
            stats['total_pesquisados'] = total

            if total == 0:
                print("[!] Nenhuma licitação encontrada")
                return

            # Processar primeiros 5 processos como teste
            print(f"\n[3] Processando processos...")
            processos_processados = 0

            while processos_processados < 5 and not INTERROMPIDO:
                processos = extrair_processos_pagina(page)

                if not processos:
                    print("[!] Nenhum processo encontrado na página")
                    break

                for processo in processos:
                    if processos_processados >= 5 or INTERROMPIDO:
                        break

                    print(f"\n  [{processos_processados + 1}] Abrindo: {processo['texto']}")

                    if abrir_detalhe(page, processo):
                        stats['total_abertos'] += 1

                        # Coletar documentos
                        docs = coletar_documentos(page, drive_service)
                        stats['total_docs_coletados'] += docs

                        print(f"      [OK] {docs} documento(s) coletado(s)")

                        # Voltar para lista
                        voltar_para_lista(page)
                        time.sleep(1)
                    else:
                        print(f"      [!] Falha ao abrir detalhe")
                        stats['erros'].append(processo['texto'])

                    processos_processados += 1

                # Próxima página
                if processos_processados < 5:
                    proximo_btn = page.locator('a[onclick*="datascroller_next"]').first
                    if proximo_btn.count() > 0:
                        proximo_btn.click()
                        time.sleep(2)
                    else:
                        break

            # Resumo
            print("\n" + "=" * 70)
            print("RESUMO DA COLETA")
            print("=" * 70)
            print(f"Total pesquisados: {stats['total_pesquisados']}")
            print(f"Total abertos: {stats['total_abertos']}")
            print(f"Total documentos coletados: {stats['total_docs_coletados']}")
            print(f"Erros: {len(stats['erros'])}")

            if stats['erros']:
                print("\nProcessos com erro:")
                for erro in stats['erros'][:5]:
                    print(f"  - {erro}")

        except Exception as e:
            print(f"\n[ERRO] {e}")
            import traceback
            traceback.print_exc()
        finally:
            browser.close()

if __name__ == "__main__":
    main()
