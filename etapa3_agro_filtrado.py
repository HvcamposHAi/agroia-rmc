"""
ETAPA 3 FILTRADA: Usa fluxo do etapa3_google_drive mas processa apenas licitações de vw_itens_agro
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
from bs4 import BeautifulSoup
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
DELAY = 0.5
DT_INICIO = "01/01/2019"
DT_FIM = "30/04/2026"
ORGAO = "SMSAN/FAAC"

# Inicializar Supabase
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# Carregar mapping de processo -> licitacao_id
import json
with open("processo_lic_mapping.json", "r") as f:
    PROCESSO_LIC_MAPPING = json.load(f)

print(f"[init] Carregados {len(PROCESSO_LIC_MAPPING)} processos para processar")

# ─── Google Drive Setup ────────────────────────────────────────────────────────

def setup_google_drive():
    """Configurar Google Drive API"""
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
        file_metadata = {'name': nome_arquivo, 'parents': [folder_id]}
        media = MediaIoBaseUpload(BytesIO(arquivo_bytes), mimetype='application/pdf', resumable=True)
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webContentLink').execute()
        drive_service.permissions().create(fileId=file['id'], body={'role': 'reader', 'type': 'anyone'}).execute()
        return file.get('webContentLink')
    except Exception as e:
        print(f"[gdrive-err] {e}")
        return None

# ─── Funções do Portal ────────────────────────────────────────────────────────

def sanitizar_nome_arquivo(texto):
    """Sanitizar nome de arquivo"""
    sem_acentos = unicodedata.normalize('NFD', texto)
    sem_acentos = ''.join(c for c in sem_acentos if unicodedata.category(c) != 'Mn')
    safe = re.sub(r'[^\w\-]', '_', sem_acentos)
    return safe[:100]

def preencher_data(page, campo_id, valor):
    """Preencher campo de data"""
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
        print(f"[!] Erro ao preencher {campo_id}: {e}")
        return False

def selecionar_opcao(page, texto_opcao, debug_label):
    """Selecionar opção em dropdown HTML"""
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
    """Fazer pesquisa no portal"""
    try:
        page.wait_for_selector("select", state="visible", timeout=20000)
    except PlaywrightTimeout:
        pass
    time.sleep(1)

    print(f"[debug] Selecionando órgão...")
    result = selecionar_opcao(page, ORGAO, "Orgao")
    print(f"[debug] Órgão seleção resultado: {result}")

    print(f"[debug] Preenchendo datas...")
    preencher_data(page, "form:dataInferiorInputDate", DT_INICIO)
    preencher_data(page, "form:j_id18InputDate", DT_FIM)

    btn = page.locator('[id="form:btSearch"], input[value="Pesquisar"]')
    if btn.count() == 0:
        print(f"[debug] Botão de pesquisa não encontrado")
        # Salvar HTML para diagnóstico
        html = page.content()
        with open("debug_pesquisa.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[debug] HTML salvo em debug_pesquisa.html para análise")
        return 0

    print(f"[debug] Clicando botão pesquisar...")
    btn.first.click()
    time.sleep(3)
    try:
        page.wait_for_load_state("networkidle", timeout=30000)
    except PlaywrightTimeout:
        pass

    html = page.content()
    # Tentar padrão alternativo se não encontrar
    m = re.search(r"quantidade registros.*?(\d+)</label>", html, re.I | re.DOTALL)
    if not m:
        print(f"[debug] Padrão não encontrado, tentando alternativo...")
        m = re.search(r"(\d+)\s*registros", html, re.I)

    total = int(m.group(1)) if m else 0
    print(f"[debug] Total encontrado: {total}")
    return total

def extrair_processos_pagina(page):
    """Extrair processos da página"""
    soup = BeautifulSoup(page.content(), "lxml")
    processos = []

    for tabela in soup.find_all("table"):
        ths = [th.get_text(strip=True).lower() for th in tabela.find_all("th")]
        if "processo" not in ths or "objeto" not in ths:
            continue

        for idx, tr in enumerate(tabela.find_all("tr")[1:]):
            cols = tr.find_all("td")
            if len(cols) < 2:
                continue

            texto = cols[0].get_text(strip=True)
            processos.append({"texto": texto, "index": idx, "tabela_index": len(processos)})

    return processos

def abrir_detalhe(page, proc):
    """Abrir página de detalhe"""
    try:
        link_id = f"form:tabela:{proc['index']}:j_id26"
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
    """Abrir modal"""
    btn = page.locator('[id="form:j_id111"]')
    if btn.count() == 0:
        btn = page.locator('input[value="Documentos da licitacao"]')

    try:
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
    """Extrair documentos"""
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

def baixar_documento(page, doc, processo_nome, drive_service, folder_id):
    """Baixar documento"""
    try:
        btn = page.locator(f'[id="{doc["input_id"]}"]')
        if btn.count() == 0:
            return None

        btn.first.click()
        time.sleep(1)

        try:
            page.goto(f"{PORTAL_URL.split('searchLicitacao')[0]}download.jsf", wait_until="domcontentloaded", timeout=30000)
        except:
            return None

        html = page.content()
        m = re.search(r'javax\.faces\.ViewState"\s+value="([^"]+)"', html)
        if not m:
            return None

        viewstate = m.group(1)
        cookies = {c['name']: c['value'] for c in page.context.cookies()}

        try:
            resp = requests.post(
                f"{PORTAL_URL.split('searchLicitacao')[0]}download.jsf",
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
                print(f"      [pdf] {size:.1f}MB [gdrive] OK")

                nome_safe = sanitizar_nome_arquivo(doc["nome"])
                url = upload_para_google_drive(drive_service, resp.content, nome_safe, folder_id)

                if url:
                    return {"url": url, "tamanho": len(resp.content), "nome": nome_safe}

        except Exception as e:
            print(f"      [!] Erro POST: {e}")
            return None

    except Exception as e:
        print(f"      [!] Erro: {e}")
        return None

def voltar_para_lista(page):
    """Voltar para lista"""
    try:
        btn = page.locator('[id="form:abaPesquisa_lbl"]')
        if btn.count() > 0:
            btn.first.click()
            time.sleep(2)
            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except:
                pass
    except:
        pass

def fechar_modal(page):
    """Fechar modal"""
    try:
        page.evaluate('if (window.Richfaces) Richfaces.hideModalPanel("form:documentos")')
    except:
        pass

# ─── Main ────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 70)
    print("ETAPA 3: Coleta de PDFs - Filtrado para vw_itens_agro (326 licitações)")
    print("=" * 70)
    print()

    drive_service = setup_google_drive()
    folder_id = GOOGLE_DRIVE_FOLDER_ID

    stats = {"docs_baixados": 0, "erros": 0, "processadas": 0}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, slow_mo=SLOW_MO)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        try:
            page.goto(PORTAL_URL, wait_until='domcontentloaded')
            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except:
                pass
            time.sleep(2)

            print("[init] Fazendo pesquisa no portal...")
            total = fazer_pesquisa(page)
            print(f"[init] Total encontrado: {total}")
            print(f"[init] Processando apenas {len(PROCESSO_LIC_MAPPING)} licitações de vw_itens_agro...")
            print()

            # Navegar por páginas
            page_num = 1
            while True:
                print(f"\n[page {page_num}] Extraindo processos...")

                processos = extrair_processos_pagina(page)
                print(f"  {len(processos)} processos encontrados")

                for proc in processos:
                    # Verificar se o processo está no mapping
                    if proc["texto"] not in PROCESSO_LIC_MAPPING:
                        continue

                    lic_id = PROCESSO_LIC_MAPPING[proc["texto"]]

                    print(f"\n  [✓] {proc['texto']} (ID: {lic_id})")

                    try:
                        if not abrir_detalhe(page, proc):
                            print(f"    [!] Falha ao abrir")
                            stats["erros"] += 1
                            continue

                        if not abrir_modal_documentos(page):
                            print(f"    [!] Modal não abriu")
                            stats["erros"] += 1
                            voltar_para_lista(page)
                            continue

                        docs = extrair_documentos(page)
                        if not docs:
                            voltar_para_lista(page)
                            continue

                        for doc in docs:
                            resultado = baixar_documento(page, doc, proc["texto"], drive_service, folder_id)
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
                                except:
                                    pass

                        fechar_modal(page)
                        voltar_para_lista(page)
                        stats["processadas"] += 1

                    except Exception as e:
                        print(f"    [!] Erro: {e}")
                        stats["erros"] += 1
                        try:
                            voltar_para_lista(page)
                        except:
                            pass

                time.sleep(DELAY)
                page_num += 1
                # Continuar até acabar os processos

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
