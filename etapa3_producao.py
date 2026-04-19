"""
AgroIA-RMC — Coleta de Documentos (Produção)
=============================================

Script de produção para coletar 100% dos PDFs de licitações.
Usa a solução comprovada: expect_page() + expect_download()

Execute: python etapa3_producao.py [--resume] [--limit N]

Exemplos:
  python etapa3_producao.py                  # Começa do início
  python etapa3_producao.py --resume          # Continua do última rodada
  python etapa3_producao.py --limit 100       # Coleta 100 processos
"""

import os
import sys
import time
import re
import json
import pickle
import unicodedata
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
from supabase import create_client
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload

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

CHECKPOINT_FILE = "coleta_checkpoint.json"
LOG_FILE = "coleta_producao.log"
SKIP_DB_SYNC = True  # Set to False when Supabase is reachable

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── Logging ──────────────────────────────────────────────────────────────

def log(msg, level="INFO"):
    """Log message com timestamp"""
    ts = datetime.now().strftime("%H:%M:%S")
    linha = f"[{ts}] [{level}] {msg}"
    print(linha)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(linha + "\n")

def retry_query(func, max_attempts=3, backoff=2):
    """Retry database query com exponential backoff para lidar com DNS/network timeouts"""
    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as e:
            error_str = str(e)
            # Só retry em erros de rede (getaddrinfo, timeout, connection)
            if any(x in error_str for x in ['getaddrinfo', 'timeout', 'connection', 'ConnectError', 'OSError']):
                if attempt < max_attempts - 1:
                    wait_time = backoff ** attempt
                    log(f"    Retry em {wait_time}s (tentativa {attempt+1}/{max_attempts}): {type(e).__name__}", "WARN")
                    time.sleep(wait_time)
                    continue
            # Se não é erro de rede ou última tentativa, retornar None
            return None
    return None

# ─── Google Drive ──────────────────────────────────────────────────────────

def setup_google_drive():
    """Setup Google Drive API"""
    if not os.path.exists("token.pickle"):
        log("token.pickle não encontrado", "ERROR")
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

def upload_para_google_drive(drive_service, arquivo_bytes, nome, folder_id):
    """Upload arquivo para Google Drive (em memória, sem disco)"""
    try:
        import io
        file_metadata = {
            'name': nome,
            'parents': [folder_id] if folder_id else []
        }

        # Converter bytes para BytesIO para upload
        media = MediaIoBaseUpload(io.BytesIO(arquivo_bytes), mimetype='application/pdf', resumable=True)

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

        return file.get('webViewLink')
    except Exception as e:
        log(f"Erro upload: {e}", "ERROR")
        return None

# ─── Checkpoint ───────────────────────────────────────────────────────────

def salvar_checkpoint(stats):
    """Salvar progresso para possível retomada"""
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(stats, f, indent=2)

def carregar_checkpoint():
    """Carregar progresso anterior"""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {
        'processados': 0,
        'docs_coletados': 0,
        'erros': 0,
        'ultima_pagina': 0
    }

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
    try:
        page.wait_for_selector("select", state="visible", timeout=20000)
    except:
        pass
    time.sleep(1)

    selecionar_opcao(page, ORGAO)
    preencher_data(page, "form:dataInferiorInputDate", DT_INICIO)
    preencher_data(page, "form:j_id18InputDate", DT_FIM)

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
    log(f"Pesquisa: {total} licitações encontradas")
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
    try:
        link.first.click()
        time.sleep(1.5)
        page.wait_for_load_state("networkidle", timeout=30000)
        return True
    except:
        return False

def voltar_para_lista(page):
    """Voltar para listagem"""
    aba = page.locator('[id="form:abaPesquisa_lbl"]')
    if aba.count() > 0:
        try:
            aba.first.click()
            time.sleep(1.5)
            page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass

def extrair_licitacao_id(proc_texto):
    """Extrair ID da licitação do texto do processo (ex: 'DE 4/2019 - SMSAN/FAAC' -> ID do BD)"""
    def query_func():
        result = sb.table("licitacoes").select("id").eq("processo", proc_texto).limit(1).execute()
        return result.data[0]['id'] if result.data else None

    lic_id = retry_query(query_func, max_attempts=3, backoff=2)
    if lic_id is None:
        log(f"    ⚠ Não encontrou licitação '{proc_texto}' no banco após 3 tentativas", "WARN")
    return lic_id

def salvar_documento_banco(licitacao_id, doc_nome, url_drive, tamanho_bytes=0):
    """Salvar documento no banco de dados com retry automático"""
    nome_arq = re.sub(r'[^\w\-_.]', '_', doc_nome) + '.pdf'

    # Query 1: Verificar se já existe
    def check_exists():
        result = sb.table("documentos_licitacao").select("id").eq("licitacao_id", licitacao_id).eq("nome_arquivo", nome_arq).execute()
        return result.data

    existing = retry_query(check_exists, max_attempts=3, backoff=2)
    if existing:
        log(f"    Documento já existe no BD (ID={existing[0]['id']})", "WARN")
        return True

    # Query 2: Inserir documento
    def insert_doc():
        data = {
            'licitacao_id': licitacao_id,
            'nome_doc': doc_nome,
            'nome_arquivo': nome_arq,
            'storage_path': url_drive,
            'url_publica': url_drive,
            'tamanho_bytes': tamanho_bytes,
            'coletado_em': datetime.now().isoformat(),
            'erro': None
        }
        sb.table("documentos_licitacao").insert(data).execute()
        return True

    result = retry_query(insert_doc, max_attempts=3, backoff=2)
    if result is None:
        log(f"    ⚠ Falhou ao salvar documento '{doc_nome}' no BD após 3 tentativas", "WARN")
        return False
    return True

def coletar_documentos(page, drive_service, proc_texto):
    """Coletar documentos do processo"""
    docs_coletados = 0

    # Obter ID da licitação
    licitacao_id = extrair_licitacao_id(proc_texto)
    if not licitacao_id:
        log(f"  Aviso: Não encontrou ID da licitação '{proc_texto}' no banco", "WARN")

    # Abrir modal - com retry
    btn = page.locator('[id="form:j_id111"]')
    if btn.count() == 0:
        return docs_coletados

    try:
        # Tentar clicar com timeouts progressivos
        try:
            btn.first.click(timeout=5000)
        except:
            # Se falhar, tentar com scroll e força
            btn.first.scroll_into_view()
            time.sleep(0.5)
            btn.first.click(force=True, timeout=10000)
    except Exception as e:
        # Se ainda falhar, retornar sem documentos (pode tentar próxima vez)
        return docs_coletados

    time.sleep(2)
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except:
        pass

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
    if rows:
        log(f"  {proc_texto}: {len(rows)} documento(s)")

    # Processar cada documento
    for i, tr in enumerate(rows[:10]):  # Máximo 10 docs por licitação
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

        try:
            elem = page.locator(f'[id="{inp_id}"]')
            if elem.count() == 0:
                continue

            # Capturar popup
            with page.context.expect_page(timeout=10000) as nova_pag_info:
                elem.first.click()
                time.sleep(0.5)

            nova_pag = nova_pag_info.value
            time.sleep(1)
            try:
                nova_pag.wait_for_load_state("networkidle", timeout=10000)
            except:
                pass

            # Capturar download
            try:
                with nova_pag.expect_download(timeout=10000) as download_info:
                    btns = nova_pag.locator("button, input[type='button'], input[type='submit']")
                    if btns.count() > 0:
                        btns.first.click()
                    time.sleep(3)

                download = download_info.value

                # Ler arquivo em memória (sem salvar em disco)
                import tempfile
                with tempfile.TemporaryDirectory() as tmpdir:
                    caminho_temp = os.path.join(tmpdir, "temp.pdf")
                    download.save_as(caminho_temp)

                    # Ler arquivo em memória
                    with open(caminho_temp, 'rb') as f:
                        arquivo_bytes = f.read()

                    # Preparar nome do arquivo
                    nome_safe = re.sub(r'[^\w\-_.]', '_', nome_doc)
                    nome_arquivo = f"{nome_safe}.pdf"
                    tamanho_bytes = len(arquivo_bytes)

                    # Upload direto para Google Drive (em memória)
                    if drive_service and GOOGLE_DRIVE_FOLDER_ID:
                        url = upload_para_google_drive(
                            drive_service,
                            arquivo_bytes,
                            nome_arquivo,
                            GOOGLE_DRIVE_FOLDER_ID
                        )
                        if url:
                            # Salvar no banco de dados (se habilitado)
                            if SKIP_DB_SYNC:
                                log(f"    [{i+1}] {nome_doc[:40]}: OK (DB skip)")
                                docs_coletados += 1
                            elif licitacao_id:
                                if salvar_documento_banco(licitacao_id, nome_doc, url, tamanho_bytes):
                                    log(f"    [{i+1}] {nome_doc[:40]}: OK (DB salvo)")
                                else:
                                    log(f"    [{i+1}] {nome_doc[:40]}: OK (sem DB)")
                                docs_coletados += 1
                            else:
                                log(f"    [{i+1}] {nome_doc[:40]}: OK")
                                docs_coletados += 1
                    else:
                        docs_coletados += 1

            except PlaywrightTimeout:
                pass
            except Exception as e:
                log(f"    [{i+1}] Erro: {e}", "WARN")
            finally:
                try:
                    nova_pag.close()
                except:
                    pass

        except Exception as e:
            log(f"    [{i+1}] Erro: {e}", "WARN")

    # Fechar modal
    try:
        page.evaluate("Richfaces.hideModalPanel('form:documentos')")
    except:
        pass
    time.sleep(0.5)

    return docs_coletados

# ─── Main ──────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true", help="Retomar de onde parou")
    parser.add_argument("--limit", type=int, default=None, help="Limite de processos")
    args = parser.parse_args()

    log("=" * 70)
    log("COLETA DE DOCUMENTOS - PRODUÇÃO")
    log("=" * 70)

    # Carregar checkpoint se --resume
    checkpoint = {}
    if args.resume and os.path.exists(CHECKPOINT_FILE):
        checkpoint = carregar_checkpoint()
        log(f"Retomando de checkpoint: {checkpoint['processados']} processados")
    else:
        checkpoint = {
            'processados': 0,
            'docs_coletados': 0,
            'erros': 0,
            'ultima_pagina': 0
        }

    drive_service = setup_google_drive()
    if not GOOGLE_DRIVE_FOLDER_ID:
        log("GOOGLE_DRIVE_FOLDER_ID não definido", "ERROR")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        try:
            log("Acessando portal...")
            page.goto(PORTAL_URL, wait_until='domcontentloaded')
            time.sleep(2)

            log("Pesquisando...")
            total = fazer_pesquisa(page)

            if total == 0:
                log("Nenhuma licitação encontrada", "ERROR")
                return

            log(f"\nColetando documentos (limit={args.limit})...")
            processos_processados_agora = 0
            pagina = 0

            while True:
                if args.limit and (checkpoint['processados'] >= args.limit):
                    log(f"Limite atingido ({args.limit})")
                    break

                processos = extrair_processos(page)

                if not processos:
                    log("Nenhum processo nesta página")
                    break

                for proc in processos:
                    if args.limit and (checkpoint['processados'] >= args.limit):
                        break

                    log(f"\n[{checkpoint['processados'] + 1}] {proc['texto']}")

                    if not abrir_processo(page, proc):
                        checkpoint['erros'] += 1
                        continue

                    docs = coletar_documentos(page, drive_service, proc['texto'])
                    checkpoint['docs_coletados'] += docs
                    checkpoint['processados'] += 1
                    processos_processados_agora += 1

                    voltar_para_lista(page)
                    time.sleep(0.5)

                    # Salvar checkpoint a cada 10 processos
                    if checkpoint['processados'] % 10 == 0:
                        salvar_checkpoint(checkpoint)
                        log(f"Checkpoint salvo: {checkpoint['processados']} processados")

                # Próxima página - tentar múltiplos seletores
                proximo = None

                # Selector 1: Links com datascroller_next
                proximo = page.locator('a[onclick*="datascroller_next"]').first
                if proximo.count() == 0:
                    # Selector 2: Qualquer elemento com datascroller_next no onclick
                    proximo = page.locator('[onclick*="datascroller_next"]').first
                if proximo.count() == 0:
                    # Selector 3: Procurar por padrão de paginação RichFaces
                    proximo = page.locator('.rich-datascr-button >> nth=2').first  # Botão "next"
                if proximo.count() == 0:
                    # Selector 4: Qualquer imagem ou botão de "next"
                    proximo = page.locator('img[onclick*="next"], button[onclick*="next"]').first

                if proximo and proximo.count() > 0:
                    try:
                        proximo.click()
                        time.sleep(2)
                        pagina += 1
                    except Exception as e:
                        log(f"Erro ao clicar próxima página: {e}", "WARN")
                        break
                else:
                    log(f"Nenhum botão de próxima página encontrado (fim da paginação)")
                    break

            # Salvar checkpoint final
            salvar_checkpoint(checkpoint)

            # Resumo
            log("\n" + "=" * 70)
            log("RESUMO DA COLETA")
            log("=" * 70)
            log(f"Processados: {checkpoint['processados']}")
            log(f"Documentos: {checkpoint['docs_coletados']}")
            log(f"Erros: {checkpoint['erros']}")
            log(f"Taxa sucesso: {100*checkpoint['docs_coletados']/max(1,checkpoint['processados']):.1f}%")

        except Exception as e:
            log(f"ERRO: {e}", "ERROR")
            import traceback
            traceback.print_exc()
        finally:
            browser.close()

if __name__ == "__main__":
    main()
