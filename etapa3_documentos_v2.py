"""
AgroIA-RMC — Coleta de Documentos (PDFs) - ESTRATÉGIA FINAL (v2)
================================================================

MUDANÇA CRÍTICA: Não usar requests library. Tudo no Playwright browser.

Estratégia:
1. Clicar documento → AJAX request é enviado (doc ID vai para sessão)
2. Deixar browser navegar para download.jsf via page.goto()
3. Interceptar resposta com context.route + route.continue_() para ler bytes
4. Fazer upload para Supabase Storage
5. Registrar no banco de dados

Execute: python etapa3_documentos_v2.py
"""

import os
import re
import math
import time
import signal
from datetime import datetime
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
from supabase import create_client

load_dotenv()

# ─── Configuração ─────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://rsphlvcekuomvpvjqxqm.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

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
MODALIDADE = "PE"  # Filtro de modalidade

REGS_POR_PAG    = 5
DELAY           = 2.0
DEBUG           = True
HEADLESS        = False
SLOW_MO         = 80

BUCKET          = "documentos-licitacoes"
PASTA_LOCAL     = "pdfs"

FORCAR_REDOWNLOAD = False
TOTAL_DESCONHECIDO = -1

# ─── Controle de interrupção ──────────────────────────────────────────────────
INTERROMPIDO = False

def handler_sigint(sig, frame):
    global INTERROMPIDO
    INTERROMPIDO = True
    print("\n[!] Interrupção solicitada. Aguardando processo atual terminar...")

signal.signal(signal.SIGINT, handler_sigint)

# ─── Conexão Supabase ─────────────────────────────────────────────────────────
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── Funções de navegação ─────────────────────────────────────────────────────

def preencher_data(page, campo_id, valor):
    """Preenche campo de data JSF."""
    campo = page.locator(f'[id="{campo_id}"]')
    if campo.count() == 0:
        if DEBUG:
            print(f"      [!] Campo {campo_id} não encontrado")
        return False
    try:
        campo.wait_for(state="visible", timeout=15000)
    except PlaywrightTimeout:
        if DEBUG:
            print(f"      [!] Campo {campo_id} não ficou visível")
        return False
    campo.click(click_count=3)
    time.sleep(0.2)
    page.keyboard.type(valor, delay=50)
    time.sleep(0.3)
    page.keyboard.press("Tab")
    time.sleep(0.5)
    return True


def _selecionar_opcao(page, texto_opcao, debug_label):
    """Seleciona opção em select."""
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
                    print(f"    ✓ {debug_label}: {texto_opcao}")
                return True
        except PlaywrightTimeout:
            continue
    if DEBUG:
        print(f"    [!] Não encontrou opção '{texto_opcao}' para {debug_label}")
    return False


def fazer_pesquisa(page):
    """Executa pesquisa."""
    try:
        page.wait_for_selector("select", state="visible", timeout=20000)
    except PlaywrightTimeout:
        if DEBUG:
            print("    [~] Timeout aguardando select")
    time.sleep(1)

    _selecionar_opcao(page, ORGAO, "Órgão")
    preencher_data(page, "form:dataInferiorInputDate", DT_INICIO)
    preencher_data(page, "form:j_id18InputDate", DT_FIM)
    if DEBUG:
        print(f"    ✓ Datas: {DT_INICIO} → {DT_FIM}")

    btn = page.locator('[id="form:btSearch"], input[value="Pesquisar"]')
    if btn.count() == 0:
        print("    [!] Botão Pesquisar não encontrado")
        return 0
    try:
        btn.first.wait_for(state="visible", timeout=15000)
    except PlaywrightTimeout:
        print("    [!] Botão Pesquisar não ficou visível")
        return 0
    btn.first.click()
    time.sleep(3)
    try:
        page.wait_for_load_state("networkidle", timeout=30000)
    except PlaywrightTimeout:
        pass
    time.sleep(1)

    html  = page.content()
    m = re.search(r"quantidade registros.*?(\d+)</label>", html, re.I | re.DOTALL)
    total = int(m.group(1)) if m else 0
    if total > 0:
        if DEBUG:
            print(f"    ✓ Total de registros: {total}")
        return total

    if extrair_processos_pagina(page):
        print("    [~] Contador não lido, mas há processos → total desconhecido")
        return TOTAL_DESCONHECIDO

    return 0


def extrair_processos_pagina(page):
    """Extrai processos da página."""
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
    """Abre detalhe da licitação."""
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
    except Exception as e:
        if DEBUG:
            print(f"      [!] Erro ao abrir detalhe: {e}")
        return False


def voltar_para_lista(page):
    """Volta para lista."""
    try:
        aba = page.locator('[id="form:abaPesquisa_lbl"]')
        if aba.count() > 0:
            aba.first.click()
            time.sleep(1.5)
            page.wait_for_load_state("networkidle", timeout=15000)
            return True
        return False
    except Exception:
        return False


def baixar_documento_v2(page, lic_id, doc_nome):
    """
    ESTRATÉGIA FINAL: Browser navigation

    1. Clicar botão de download (AJAX)
    2. Deixar browser navegar para download.jsf via page.goto()
    3. Capturar response com context.route
    4. Salvar bytes
    """

    print(f"      [download] Iniciando download: {doc_nome[:40]}")

    # Estado para capturar response
    arquivo_capturado = {"bytes": None, "content_type": ""}

    def handle_download_response(route):
        """Intercepta response de download.jsf e captura bytes."""
        try:
            response = route.fetch()
            ct = response.headers.get("content-type", "")
            body = response.body()

            arquivo_capturado["content_type"] = ct
            arquivo_capturado["bytes"] = body

            # Verificar se é PDF válido
            eh_pdf = ct.lower().startswith("application/pdf") or body[:4] == b"%PDF"
            tamanho = len(body)

            print(f"      [capture] {tamanho} bytes, PDF={eh_pdf}, CT={ct[:30]}")

            # Deixar response passar (importante!)
            route.continue_(response=response)

        except Exception as e:
            print(f"      [capture-err] {e}")
            try:
                route.continue_()
            except:
                pass

    # Registrar interceptor
    page.context.route("**/download/download.jsf**", handle_download_response)

    try:
        # Passo 1: Encontrar botão de download no modal
        btn_download = page.locator('[id="form:tabelaDocumentos:0:j_id283"]')
        if btn_download.count() == 0:
            print(f"      [!] Botão de download não encontrado no modal")
            return None

        # Passo 2: Clicar botão (dispara AJAX)
        print(f"      [click] Clicando botão...")
        btn_download.first.click()
        time.sleep(1)

        # Passo 3: Aguardar página estabilizar (AJAX completar)
        print(f"      [wait] Aguardando AJAX completar...")
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightTimeout:
            print(f"      [wait] Timeout networkidle, continuando...")
            time.sleep(2)

        # Passo 4: Navegar para download.jsf (simula window.location)
        print(f"      [nav] Navegando para download.jsf...")
        page.goto(DOWNLOAD_JSF_URL, wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)

        # Passo 5: Verificar se bytes foram capturados
        if arquivo_capturado["bytes"]:
            tamanho = len(arquivo_capturado["bytes"])
            ct = arquivo_capturado["content_type"]
            eh_pdf = ct.lower().startswith("application/pdf") or arquivo_capturado["bytes"][:4] == b"%PDF"

            print(f"      [result] ✓ Capturado: {tamanho} bytes, PDF={eh_pdf}")

            return {
                "lic_id": lic_id,
                "doc_nome": doc_nome,
                "bytes": arquivo_capturado["bytes"],
                "content_type": ct,
                "tamanho": tamanho,
                "eh_pdf": eh_pdf,
                "timestamp": datetime.now().isoformat()
            }
        else:
            print(f"      [result] ✗ Nenhum arquivo capturado")
            return None

    except Exception as e:
        print(f"      [erro] {e}")
        return None

    finally:
        try:
            page.context.unroute("**/download/download.jsf**")
        except:
            pass


def gravar_documento(sb, resultado):
    """Salva documento no Supabase Storage e registra no banco."""
    if not resultado:
        return False

    lic_id = resultado["lic_id"]
    tamanho = resultado["tamanho"]
    eh_pdf = resultado["eh_pdf"]
    ct = resultado["content_type"]

    try:
        # Upload para Storage
        caminho_storage = f"licitacao_{lic_id}/documento.pdf"
        sb.storage.from_(BUCKET).upload(
            caminho_storage,
            resultado["bytes"],
            file_options={"content-type": ct}
        )
        print(f"      [storage] ✓ Uploaded: {caminho_storage} ({tamanho} bytes)")

        # Registrar no banco
        sb.table("documentos_licitacao").upsert({
            "lic_id": lic_id,
            "erro": "ok" if eh_pdf else "formato_invalido",
            "tamanho_bytes": tamanho,
            "storage_path": caminho_storage,
            "content_type": ct,
            "data_coleta": datetime.now().isoformat()
        }).execute()

        print(f"      [db] ✓ Registrado no banco")
        return True

    except Exception as e:
        print(f"      [erro] Falha ao gravar: {e}")
        sb.table("documentos_licitacao").upsert({
            "lic_id": lic_id,
            "erro": "upload_falhou"
        }).execute()
        return False


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 70)
    print("ETAPA 3: Coleta de Documentos (PDFs) - v2")
    print("=" * 70)
    print(f"Modalidade: {MODALIDADE if MODALIDADE else 'todas'}")
    print(f"Período: {DT_INICIO} → {DT_FIM}")
    print(f"Headless: {HEADLESS}")
    print()

    stats = {
        "paginas_visitadas": 0,
        "licitacoes_processadas": 0,
        "documentos_encontrados": 0,
        "documentos_baixados": 0,
        "erros": 0,
        "pulados": 0
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, slow_mo=SLOW_MO)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        print("[init] Acessando portal...")
        page.goto(PORTAL_URL, wait_until="domcontentloaded")
        time.sleep(2)

        print("[init] Fazendo pesquisa inicial...")
        total = fazer_pesquisa(page)
        print(f"[init] Total de registros: {total}")

        # Processar páginas
        pag_atual = 1
        lic_processadas = set()

        while True:
            if INTERROMPIDO:
                print("\n[!] Interrupção detectada. Encerrando...")
                break

            print(f"\n[página {pag_atual}] Extraindo processos...")
            processos = extrair_processos_pagina(page)
            print(f"  {len(processos)} processos encontrados")

            stats["paginas_visitadas"] += 1

            # Processar cada processo
            for i, proc in enumerate(processos):
                if INTERROMPIDO:
                    break

                texto = proc["texto"]

                # Filtro de modalidade
                if MODALIDADE and not texto.startswith(MODALIDADE + " "):
                    stats["pulados"] += 1
                    continue

                stats["licitacoes_processadas"] += 1
                lic_id = int(re.search(r"ID=(\d+)", page.content()).group(1)) if "ID=" in page.content() else None

                print(f"\n  [{i+1}/{len(processos)}] {texto}")

                # Abrir detalhe
                if not abrir_detalhe(page, proc):
                    print(f"    [!] Falha ao abrir detalhe")
                    stats["erros"] += 1
                    continue

                # Clicar documentos
                btn_doc = page.locator('[id="form:j_id111"]')
                if btn_doc.count() == 0:
                    print(f"    [!] Botão documentos não encontrado")
                    stats["erros"] += 1
                    voltar_para_lista(page)
                    continue

                print(f"    [docs] Abrindo modal...")
                btn_doc.first.click()
                time.sleep(2)

                # Procurar documentos na tabela
                docs = page.locator('[id="form:tabelaDocumentos"] tbody tr')
                num_docs = docs.count()
                print(f"    [docs] Encontrados {num_docs} documento(s)")

                if num_docs == 0:
                    # Registrar como sem_docs
                    sb.table("documentos_licitacao").upsert({
                        "lic_id": lic_id if lic_id else 0,
                        "processo": texto,
                        "erro": "sem_docs"
                    }).execute()
                    stats["documentos_encontrados"] += 0
                else:
                    stats["documentos_encontrados"] += num_docs

                    # Tentar baixar primeiro documento
                    resultado = baixar_documento_v2(page, lic_id, "Documento 1")
                    if resultado and resultado.get("eh_pdf"):
                        if gravar_documento(sb, resultado):
                            stats["documentos_baixados"] += 1
                        else:
                            stats["erros"] += 1
                    else:
                        stats["erros"] += 1

                # Voltar
                voltar_para_lista(page)
                time.sleep(DELAY)

            # Próxima página
            print(f"\n[página {pag_atual}] Tentando ir para próxima página...")
            pag_atual += 1
            # TODO: Implementar navegação para próxima página
            break  # Por enquanto, apenas 1 página

        browser.close()

    # Resumo
    print("\n" + "=" * 70)
    print("RESUMO")
    print("=" * 70)
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print()

if __name__ == "__main__":
    main()
