"""
AgroIA-RMC — Coleta de Documentos (PDFs) de Licitações (Etapa 3)
=================================================================
Mecanismo confirmado (util.js + diagnóstico):
  - Botão: <input type="image"> com onclick A4J.AJAX.Submit({'id': doc_id})
  - AJAX envia doc_id ao servidor (salvo na sessão HTTP)
  - oncomplete chama open_download() → window.open('download.jsf')
  - O popup carrega download.jsf, o servidor serve o arquivo consumindo o token

PROBLEMA com requests: o popup consome o token antes de conseguirmos usar.

Estratégia correta:
  - context.expect_page() captura o popup dentro do contexto Playwright
  - nova_pag.on('response') intercepta a resposta BINÁRIA de download.jsf
  - Os bytes são salvos em disco antes da página fechar
  - NÃO usamos requests — tudo dentro do browser

Execute: python etapa3_documentos.py

Pré-requisitos no Supabase (rodar SQL antes):
  - Tabela `documentos_licitacao` (ver criar_tabela_documentos.sql)
  - Bucket `documentos-licitacoes` com acesso público
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
import requests as req_lib

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
DT_INICIO  = "01/01/2019"
DT_FIM     = "31/12/2026"

# Filtro de Modalidade (opcional).
# None  = sem filtro (busca todas as modalidades)
# "PE"  = só Pregão Eletrônico  (têm PROCESSO LICITATÓRIO)
# "DS"  = só Dispensa           (raramente têm docs)
# "AD"  = Adesão; "CP" = Concorrência; etc.
MODALIDADE = "PE"

REGS_POR_PAG    = 5
DELAY           = 2.0
DEBUG           = True
HEADLESS        = False   # JSF requer browser visível
SLOW_MO         = 80

BUCKET          = "documentos-licitacoes"
PASTA_LOCAL     = "pdfs"          # pasta local temporária para downloads

# False = pula licitações que já têm documentos no banco
# True  = baixa mesmo se já existe (sobreescreve no Storage via upsert)
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

# ─── Funções de navegação (padrão etapa2) ─────────────────────────────────────

def preencher_data(page, campo_id, valor):
    """
    Preenche campo de data JSF via triple-click + keyboard.type + Tab.
    IMPORTANTE: usar [id="..."] — IDs JSF com ':' quebram seletores CSS.
    """
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


def _extrair_total_de_html(html):
    m = re.search(r"quantidade registros.*?(\d+)</label>", html, re.I | re.DOTALL)
    if m:
        return int(m.group(1))
    texto = BeautifulSoup(html, "lxml").get_text()
    m2 = re.search(r"quantidade\s+registros[\s:]*?(\d+)", texto, re.I)
    return int(m2.group(1)) if m2 else 0


def _selecionar_opcao(page, texto_opcao, debug_label):
    """
    Encontra o select que contém texto_opcao e seleciona essa opção.
    Aguarda AJAX pós-seleção estabilizar.
    Retorna True se selecionou, False caso contrário.
    """
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
    """Executa pesquisa no portal. Retorna total de registros (ou TOTAL_DESCONHECIDO)."""
    # Aguarda select ficar visível antes de interagir (evita TimeoutError no select_option)
    try:
        page.wait_for_selector("select", state="visible", timeout=20000)
    except PlaywrightTimeout:
        if DEBUG:
            print("    [~] Timeout aguardando select ficar visível")
    time.sleep(1)

    # Órgão licitante
    _selecionar_opcao(page, ORGAO, "Órgão")

    preencher_data(page, "form:dataInferiorInputDate", DT_INICIO)
    preencher_data(page, "form:j_id18InputDate",       DT_FIM)
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
    page.wait_for_load_state("networkidle", timeout=30000)
    time.sleep(1)

    html  = page.content()
    total = _extrair_total_de_html(html)
    if total > 0:
        if DEBUG:
            print(f"    ✓ Total de registros: {total}")
        return total

    if extrair_processos_pagina(page):
        print("    [~] Contador não lido, mas há processos → total desconhecido")
        return TOTAL_DESCONHECIDO

    return 0


def extrair_processos_pagina(page):
    """Extrai processos da página atual da listagem."""
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


def ir_para_proxima_pagina(page, pag_atual):
    """Navega para a próxima página da listagem. Retorna True se navegou."""
    prox = pag_atual + 1
    pags = page.locator("td.rich-datascr-inact")
    for i in range(pags.count()):
        elem = pags.nth(i)
        if elem.text_content().strip() == str(prox):
            try:
                elem.click()
                time.sleep(2)
                page.wait_for_load_state("networkidle", timeout=15000)
                return True
            except Exception as e:
                if DEBUG:
                    print(f"      [!] Erro ao clicar página {prox}: {e}")
                return False

    btn_prox = page.locator("td.rich-datascr-button").filter(has_text=">")
    if btn_prox.count() > 0:
        try:
            btn_prox.first.click()
            time.sleep(2)
            page.wait_for_load_state("networkidle", timeout=15000)
            return True
        except Exception as e:
            if DEBUG:
                print(f"      [!] Erro ao clicar botão '>': {e}")

    return False


def ir_para_pagina_lista(page, num_pagina):
    try:
        pags = page.locator("td.rich-datascr-inact")
        for i in range(pags.count()):
            elem = pags.nth(i)
            if elem.text_content().strip() == str(num_pagina):
                elem.click()
                time.sleep(2)
                page.wait_for_load_state("networkidle", timeout=15000)
                return True
        return False
    except Exception as e:
        if DEBUG:
            print(f"      [!] Erro ao ir para página {num_pagina}: {e}")
        return False


def fechar_modal_bloqueante(page):
    """
    Remove modais RichFaces residuais que bloqueiam cliques na listagem.
    Observado no log: rich-mpnl-mask-div interceptando pointer events.
    """
    try:
        # Fecha qualquer modal aberto via JS
        page.evaluate("""
            () => {
                const masks = document.querySelectorAll('.rich-mpnl-mask-div-opaque, .rich-mpnl-mask-div');
                masks.forEach(el => el.style.display = 'none');
            }
        """)
    except Exception:
        pass


def abrir_detalhe(page, processo):
    """Abre a página de detalhe clicando no link da listagem."""
    link_id = processo.get("link_id", "")
    if not link_id:
        return False

    # Garante que não há modal bloqueando (pode sobrar da licitação anterior)
    fechar_modal_bloqueante(page)

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
    """Volta para a aba de listagem via aba JSF (id=form:abaPesquisa_lbl)."""
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


def refazer_pesquisa_e_navegar(page, pagina_alvo):
    """Recarrega o portal, refaz pesquisa e navega até página alvo."""
    page.goto(PORTAL_URL, timeout=60000)
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except PlaywrightTimeout:
        pass
    time.sleep(2)
    total = fazer_pesquisa(page)
    if total == 0:
        return False
    for p in range(2, pagina_alvo + 1):
        if not ir_para_pagina_lista(page, p):
            if not ir_para_proxima_pagina(page, p - 1):
                return False
    return True

# ─── Interação com o modal de documentos ──────────────────────────────────────

def abrir_modal_documentos(page):
    """
    Clica no botão 'Documentos da licitação' e aguarda o modal abrir.
    Retorna True se o modal foi aberto com sucesso.
    """
    # Seletor confirmado pelo diagnostico_documentos.py
    btn = page.locator('[id="form:j_id111"]')
    if btn.count() == 0:
        # Fallback por valor do input
        btn = page.locator('input[value="Documentos da licitação"]')
    if btn.count() == 0:
        if DEBUG:
            print("        [!] Botão 'Documentos da licitação' não encontrado")
        return False

    try:
        btn.first.click()
        time.sleep(2)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightTimeout:
            pass  # normal em modais RichFaces
        time.sleep(0.5)
        return True
    except Exception as e:
        if DEBUG:
            print(f"        [!] Erro ao abrir modal: {e}")
        return False


def extrair_documentos_da_modal(page):
    """
    Parseia form:tabelaDocumentos e retorna lista de documentos.

    Estrutura confirmada pelo diagnóstico:
      - Coluna 1: nome do documento (ex: "D.E 4")
      - Coluna 2: <input type="image" id="form:tabelaDocumentos:N:j_id283"
                   onclick="A4J.AJAX.Submit(...,'parameters':{'id': 17466,...})">

    Cada item retornado: {
        'nome':        str,         # label do portal
        'locator_str': str,         # seletor Playwright do input
        'doc_id':      int|None,    # parâmetro 'id' extraído do onclick
        'row_index':   int,         # índice 0-based na tabela
    }
    """
    html   = page.content()
    soup   = BeautifulSoup(html, "lxml")
    tabela = soup.find("table", id="form:tabelaDocumentos")

    if not tabela:
        if DEBUG:
            print("        [!] form:tabelaDocumentos não encontrada no HTML")
        return []

    documentos = []
    rows = tabela.find_all("tr")[1:]  # pula cabeçalho
    if DEBUG:
        print(f"        ✓ Documentos encontrados: {len(rows)}")

    for i, tr in enumerate(rows):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue

        nome_doc = tds[0].get_text(strip=True)
        col_arq  = tds[1]

        # Padrão confirmado: <input type="image" id="form:tabelaDocumentos:N:j_id283">
        inp = col_arq.find("input")
        if not inp:
            if DEBUG:
                print(f"        [~] Doc {i+1} '{nome_doc}': nenhum <input> encontrado")
            continue

        inp_id  = inp.get("id", "")
        onclick = inp.get("onclick", "")

        # Extrai o 'id' do documento do parâmetro onclick do A4J
        # Padrão: 'parameters':{'id':17466,'form:tabelaDocumentos:0:j_id283':...}
        m_id = re.search(r"'id'\s*:\s*(\d+)", onclick)
        doc_id = int(m_id.group(1)) if m_id else None

        # Seletor: usa id JSF se disponível, senão posição na tabela
        if inp_id:
            locator_str = f'[id="{inp_id}"]'
        else:
            locator_str = f'[id="form:tabelaDocumentos"] tr:nth-child({i+2}) input'

        documentos.append({
            "nome":        nome_doc,
            "locator_str": locator_str,
            "doc_id":      doc_id,
            "row_index":   i,
        })
        if DEBUG:
            print(f"        • Doc {i+1}: '{nome_doc}' | id={doc_id} | input={inp_id}")

    return documentos


def fechar_modal(page):
    """Fecha o modal de documentos via botão X ou JS RichFaces."""
    try:
        fechar = page.locator('img[onclick*="hideModalPanel(\'form:documentos\')"]')
        if fechar.count() > 0:
            fechar.first.click()
            time.sleep(0.5)
            return
        page.evaluate("Richfaces.hideModalPanel('form:documentos')")
        time.sleep(0.5)
    except Exception:
        pass


def _nome_cd(cd_header):
    """Extrai nome do arquivo do header Content-Disposition."""
    m = re.search(r'filename[^;=\n]*=[\"\']?([^\"\';\n]+)', cd_header or "", re.I)
    return m.group(1).strip() if m else None


def baixar_documento(page, doc, licitacao_id):
    """
    Estratégia abort + requests:
      1. Clique → A4J.AJAX registra doc_id na sessão do servidor
      2. oncomplete → window.open('download.jsf') → popup tenta abrir
      3. context.route() ABORTA a requisição do popup antes de chegar ao servidor
         → token NÃO é consumido (servidor nunca recebeu a requisição)
      4. requests.get(download.jsf) com os cookies do browser
         → servidor recebe, serve o PDF e consome o token agora
    Vantagem: sem race conditions; download.jsf só é chamado 1x com sucesso.
    """
    locator_str = doc["locator_str"]
    nome_doc    = doc["nome"]
    doc_id      = doc.get("doc_id")
    row_index   = doc.get("row_index", 0)

    elem = page.locator(locator_str)
    if elem.count() == 0:
        if DEBUG:
            print(f"          [!] Elemento não encontrado: {locator_str}")
        return None, None

    pasta_lic = os.path.join(PASTA_LOCAL, str(licitacao_id))
    os.makedirs(pasta_lic, exist_ok=True)

    rota_disparou = {"ok": False}

    def abortar_popup(route):
        rota_disparou["ok"] = True
        if DEBUG:
            print(f"          [route] Abortando popup ({route.request.url[-40:]})")
        try:
            route.abort()
        except Exception:
            pass

    page.context.route("**/download/download.jsf**", abortar_popup)

    try:
        with page.context.expect_page(timeout=60000) as nova_pag_info:
            elem.first.click()

        nova_pag = nova_pag_info.value
        time.sleep(1.5)  # aguarda rota disparar e abortar antes de fechar
        try:
            nova_pag.close()
        except Exception:
            pass

    except PlaywrightTimeout:
        if DEBUG:
            print(f"          [!] Popup não abriu em 60s para '{nome_doc}'")
        return None, None
    except Exception as e:
        if DEBUG:
            print(f"          [!] Erro ao abrir popup: {e}")
        return None, None
    finally:
        try:
            page.context.unroute("**/download/download.jsf**", abortar_popup)
        except Exception:
            pass

    if not rota_disparou["ok"]:
        if DEBUG:
            print(f"          [!] Popup abriu mas não tentou download.jsf")
        return None, None

    # Pega cookies de sessão do contexto Playwright
    cookies = {c["name"]: c["value"] for c in page.context.cookies()}

    # Faz o download com requests — servidor ainda tem o token (popup foi abortado)
    try:
        r = req_lib.get(DOWNLOAD_JSF_URL, cookies=cookies, timeout=30, allow_redirects=True)
        ct   = r.headers.get("content-type", "")
        size = len(r.content)
        if DEBUG:
            print(f"          [requests] status={r.status_code} CT={ct[:50]} size={size}")
        if r.status_code == 200 and size > 200 and "text/html" not in ct:
            nome_arquivo = (
                _nome_cd(r.headers.get("content-disposition", ""))
                or f"{re.sub(r'[^\w]', '_', nome_doc)}_{doc_id or row_index + 1}.pdf"
            )
            nome_safe = re.sub(r'[<>:"/\\|?*]', '_', nome_arquivo).strip()
            caminho   = os.path.join(pasta_lic, nome_safe)
            with open(caminho, "wb") as f:
                f.write(r.content)
            if DEBUG:
                print(f"          ✓ Salvo: {nome_safe} ({size} bytes)")
            return caminho, nome_safe
        else:
            if DEBUG:
                print(f"          [!] Resposta inválida — provável HTML de erro/sessão expirada")
            return None, None
    except Exception as e:
        if DEBUG:
            print(f"          [!] Erro no requests: {e}")
        return None, None

# ─── Upload para Supabase Storage ─────────────────────────────────────────────

def upload_supabase(licitacao_id, nome_arquivo, caminho_local):
    """
    Faz upload do arquivo para o bucket e retorna (storage_path, url_publica).
    """
    storage_path = f"{licitacao_id}/{nome_arquivo}"
    try:
        with open(caminho_local, "rb") as f:
            conteudo = f.read()

        sb.storage.from_(BUCKET).upload(
            storage_path,
            conteudo,
            {"content-type": "application/pdf", "upsert": "true"},
        )
        url = sb.storage.from_(BUCKET).get_public_url(storage_path)
        if DEBUG:
            print(f"          ✓ Upload: {storage_path}")
        return storage_path, url

    except Exception as e:
        if DEBUG:
            print(f"          [!] Erro no upload '{nome_arquivo}': {e}")
        return storage_path, None  # retorna path mesmo sem URL pública

# ─── Gravação de metadados ────────────────────────────────────────────────────

def gravar_documento(licitacao_id, nome_arquivo, nome_doc, storage_path, url_publica, tamanho_bytes, erro=None):
    """Upsert do metadado do documento em documentos_licitacao."""
    try:
        sb.table("documentos_licitacao").upsert(
            {
                "licitacao_id":  licitacao_id,
                "nome_arquivo":  nome_arquivo or nome_doc,
                "nome_doc":      nome_doc,
                "storage_path":  storage_path,
                "url_publica":   url_publica,
                "tamanho_bytes": tamanho_bytes,
                "erro":          erro,
            },
            on_conflict="licitacao_id,nome_arquivo",
        ).execute()
    except Exception as e:
        if DEBUG:
            print(f"          [!] Erro ao gravar metadado '{nome_arquivo}': {e}")

# ─── Carregar licitações do banco ─────────────────────────────────────────────

def carregar_licitacoes_com_itens():
    """
    Retorna:
      - todas: {id → {id, processo}}
      - ids_com_itens: set de licitacao_id que têm itens
      - ids_com_docs: set de licitacao_id que já têm documentos
      - indice: {processo_texto → licitacao_id}
    """
    # Licitações
    lics = []
    offset = 0
    while True:
        r = sb.table("licitacoes").select("id, processo").range(offset, offset + 999).execute()
        lics.extend(r.data)
        if len(r.data) < 1000:
            break
        offset += 1000
    todas = {x["id"]: x for x in lics}

    # IDs com itens
    itens = []
    offset = 0
    while True:
        r = sb.table("itens_licitacao").select("licitacao_id").range(offset, offset + 999).execute()
        itens.extend(r.data)
        if len(r.data) < 1000:
            break
        offset += 1000
    ids_com_itens = set(x["licitacao_id"] for x in itens if x.get("licitacao_id"))

    # IDs com documentos já coletados
    docs = []
    offset = 0
    while True:
        r = sb.table("documentos_licitacao").select("licitacao_id").range(offset, offset + 999).execute()
        docs.extend(r.data)
        if len(r.data) < 1000:
            break
        offset += 1000
    ids_com_docs = set(x["licitacao_id"] for x in docs if x.get("licitacao_id"))

    # Índice processo → id
    indice = {}
    for lic in todas.values():
        proc = lic.get("processo", "")
        if proc:
            indice[proc] = lic["id"]
            m = re.match(r'^([A-Z]{2}\s+\d+/\d{4})', proc)
            if m:
                indice[m.group(1)] = lic["id"]

    return todas, ids_com_itens, ids_com_docs, indice

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    global INTERROMPIDO

    print("=" * 65)
    print("AgroIA-RMC — Coleta de Documentos (Etapa 3)")
    print(f"Início: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"FORCAR_REDOWNLOAD: {FORCAR_REDOWNLOAD}")
    print(f"MODALIDADE: {MODALIDADE or '(todas)'}")
    print("=" * 65)

    print("\n[0] Carregando licitações do Supabase...")
    todas, ids_com_itens, ids_com_docs, indice = carregar_licitacoes_com_itens()
    ids_alvo = ids_com_itens  # apenas licitações com itens coletados
    pendentes = len(ids_alvo - ids_com_docs) if not FORCAR_REDOWNLOAD else len(ids_alvo)
    print(f"    {len(todas)} licitações no banco")
    print(f"    {len(ids_alvo)} com itens coletados")
    print(f"    {len(ids_com_docs)} já têm documentos")
    print(f"    {pendentes} pendentes de coleta")

    if pendentes == 0 and not FORCAR_REDOWNLOAD:
        print("\n    Nada a fazer. Use FORCAR_REDOWNLOAD=True para reprocessar.")
        return

    stats = {
        "processados": 0,
        "documentos":  0,
        "pulados":     0,
        "erros":       0,
        "sem_docs":    0,
        "nao_encontrados": 0,
    }

    os.makedirs(PASTA_LOCAL, exist_ok=True)

    with sync_playwright() as p:
        print("\n[1] Abrindo navegador...")
        browser = p.chromium.launch(headless=HEADLESS, slow_mo=SLOW_MO)
        context = browser.new_context(accept_downloads=True)
        page    = context.new_page()

        print("[2] Acessando portal e fazendo pesquisa...")
        page.goto(PORTAL_URL, timeout=60000)
        try:
            page.wait_for_load_state("networkidle", timeout=20000)
        except PlaywrightTimeout:
            pass  # RichFaces faz polling contínuo — prossegue mesmo sem networkidle
        time.sleep(2)

        total = fazer_pesquisa(page)
        if total == 0:
            print("\n[!] PROBLEMA: Nenhum registro retornado. Verifique portal/órgão/datas.")
            browser.close()
            return

        if total == TOTAL_DESCONHECIDO:
            total_pags = None
            print("\n[3] Total desconhecido. Paginando até esgotar...")
        else:
            total_pags = math.ceil(total / REGS_POR_PAG)
            print(f"\n[3] {total} registros em {total_pags} páginas. Iniciando coleta...")

        pag_atual = 1
        paginas_sem_processo = 0

        while not INTERROMPIDO:
            if total_pags is not None and pag_atual > total_pags:
                break

            print(f"\n--- Página {pag_atual}" +
                  (f"/{total_pags}" if total_pags else "") + " ---")

            processos = extrair_processos_pagina(page)
            if not processos:
                print("    [!] Nenhum processo — possivelmente perdeu estado. Refazendo...")
                if not refazer_pesquisa_e_navegar(page, pag_atual):
                    print("    [!] Falha ao recuperar. Encerrando.")
                    break
                processos = extrair_processos_pagina(page)

            if not processos:
                paginas_sem_processo += 1
                if paginas_sem_processo >= 3:
                    print("    [!] 3 páginas consecutivas sem processos. Encerrando.")
                    break
                pag_atual += 1
                continue
            else:
                paginas_sem_processo = 0

            print(f"    {len(processos)} processos encontrados")

            for proc in processos:
                if INTERROMPIDO:
                    break

                texto = proc.get("texto", "")

                # Filtro client-side de modalidade (ex: "PE", "DS")
                # Evita abrir detalhe de licitações fora do escopo atual
                if MODALIDADE and not texto.startswith(MODALIDADE + " "):
                    stats["pulados"] += 1
                    continue

                # Resolve ID no banco
                lic_id = None
                for chave in [texto, texto.split(" - ")[0] if " - " in texto else texto]:
                    if chave in indice:
                        lic_id = indice[chave]
                        break

                if not lic_id:
                    if DEBUG:
                        print(f"    [?] Não encontrado no banco: '{texto}'")
                    stats["nao_encontrados"] += 1
                    continue

                # Pula licitações sem itens (fora do escopo desta etapa)
                if lic_id not in ids_alvo:
                    stats["pulados"] += 1
                    continue

                # Pula se já tem documentos e não está forçando
                if lic_id in ids_com_docs and not FORCAR_REDOWNLOAD:
                    if DEBUG:
                        print(f"    [=] Docs já coletados: {texto}")
                    stats["pulados"] += 1
                    continue

                print(f"    [>] Processando: {texto} (ID={lic_id})")

                # Abre detalhe
                if not abrir_detalhe(page, proc):
                    print(f"        [!] Falha ao abrir detalhe")
                    stats["erros"] += 1
                    refazer_pesquisa_e_navegar(page, pag_atual)
                    continue

                # Abre modal de documentos
                if not abrir_modal_documentos(page):
                    gravar_documento(lic_id, "_modal_nao_abriu", texto, None, None, 0, erro="modal_nao_abriu")
                    stats["erros"] += 1
                    voltar_para_lista(page)
                    continue

                # Extrai lista de documentos
                documentos = extrair_documentos_da_modal(page)

                if not documentos:
                    print(f"        [~] Nenhum documento nesta licitação")
                    stats["sem_docs"] += 1
                    gravar_documento(lic_id, "_sem_docs", texto, None, None, 0, erro="sem_docs")
                    ids_com_docs.add(lic_id)  # evita re-visitar nas próximas execuções
                    fechar_modal(page)
                    if not voltar_para_lista(page):
                        refazer_pesquisa_e_navegar(page, pag_atual)
                    time.sleep(DELAY)
                    continue

                print(f"        {len(documentos)} documento(s) a baixar")

                n_doc = 0
                for doc in documentos:
                    nome_doc = doc["nome"]
                    if DEBUG:
                        print(f"          → {nome_doc}")

                    # Download
                    caminho_local, nome_arquivo = baixar_documento(page, doc, lic_id)

                    if caminho_local and nome_arquivo:
                        tamanho = os.path.getsize(caminho_local)
                        # Upload para Supabase Storage
                        storage_path, url = upload_supabase(lic_id, nome_arquivo, caminho_local)
                        gravar_documento(lic_id, nome_arquivo, nome_doc, storage_path, url, tamanho)
                        n_doc += 1
                    else:
                        gravar_documento(
                            lic_id, f"_erro_{doc['row_index']}", nome_doc,
                            None, None, 0, erro="download_falhou"
                        )
                        stats["erros"] += 1

                stats["documentos"]  += n_doc
                stats["processados"] += 1
                ids_com_docs.add(lic_id)
                print(f"        ✓ {n_doc} documento(s) coletados")

                fechar_modal(page)
                if not voltar_para_lista(page):
                    print("        [~] Falha ao voltar. Refazendo pesquisa...")
                    if not refazer_pesquisa_e_navegar(page, pag_atual):
                        print("    [!] Falha na recuperação. Encerrando.")
                        INTERROMPIDO = True
                        break

                time.sleep(DELAY)

            if INTERROMPIDO:
                break

            if total_pags is not None and pag_atual >= total_pags:
                print(f"\n    Página {pag_atual}/{total_pags} — última. Coleta concluída.")
                break

            print(f"\n    Navegando para página {pag_atual + 1}...")
            navegou = ir_para_proxima_pagina(page, pag_atual)
            if not navegou:
                if total_pags is None:
                    print("    → Sem mais páginas. Coleta concluída.")
                    break
                else:
                    print(f"    [!] Não conseguiu ir para página {pag_atual + 1}. Refazendo...")
                    if not refazer_pesquisa_e_navegar(page, pag_atual + 1):
                        print("    [!] Falha na navegação. Encerrando.")
                        break
            pag_atual += 1

        browser.close()

    # ─── Relatório final ──────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("CONCLUÍDO!")
    print("=" * 65)
    print(f"  Processados:      {stats['processados']}")
    print(f"  Documentos:       {stats['documentos']}")
    print(f"  Sem documentos:   {stats['sem_docs']}")
    print(f"  Pulados:          {stats['pulados']}")
    print(f"  Não encontrados:  {stats['nao_encontrados']}")
    print(f"  Erros:            {stats['erros']}")
    if INTERROMPIDO:
        print("  (Interrompido — rode novamente para continuar)")
    print("=" * 65)


if __name__ == "__main__":
    main()
