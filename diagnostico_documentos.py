"""
AgroIA-RMC — Diagnóstico: Modal de Documentos da Licitação
===========================================================
Abre 3 licitações no portal, clica em "Documentos da licitação",
captura o HTML do modal e imprime a estrutura dos links encontrados.

Objetivo: descobrir o formato real dos links de download antes de
implementar o script completo de coleta (etapa3_documentos.py).

Execute: python diagnostico_documentos.py
"""

import os
import re
import time
import json
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup

# ─── Configuração ─────────────────────────────────────────────────────────────
PORTAL_URL = (
    "http://consultalicitacao.curitiba.pr.gov.br:9090/"
    "ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
)
ORGAO     = "SMSAN/FAAC"
DT_INICIO = "01/01/2019"
DT_FIM    = "31/12/2026"
MAX_LICITACOES = 3  # quantas licitações testar


# ─── Funções reutilizadas do etapa2_itens_v9.py ──────────────────────────────

def preencher_data(page, campo_id, valor):
    campo = page.locator(f'[id="{campo_id}"]')
    if campo.count() == 0:
        print(f"  [ERR] Campo {campo_id} nao encontrado")
        return False
    try:
        campo.wait_for(state="visible", timeout=15000)
    except PlaywrightTimeout:
        print(f"  [ERR] Campo {campo_id} nao ficou visivel")
        return False
    campo.click(click_count=3)
    time.sleep(0.2)
    page.keyboard.type(valor, delay=50)
    time.sleep(0.3)
    page.keyboard.press("Tab")
    time.sleep(0.5)
    return True


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
                print(f"  [OK] {debug_label}: {texto_opcao}")
                return True
        except PlaywrightTimeout:
            continue
    print(f"  [ERR] Nao encontrou opcao '{texto_opcao}' para {debug_label}")
    return False


def fazer_pesquisa(page):
    try:
        page.wait_for_selector("select", state="visible", timeout=20000)
    except PlaywrightTimeout:
        print("  [WAIT] Timeout aguardando select ficar visivel")
    time.sleep(1)

    _selecionar_opcao(page, ORGAO, "Orgao")
    preencher_data(page, "form:dataInferiorInputDate", DT_INICIO)
    preencher_data(page, "form:j_id18InputDate", DT_FIM)
    print(f"  [OK] Datas: {DT_INICIO} -> {DT_FIM}")

    btn = page.locator('[id="form:btSearch"], input[value="Pesquisar"]')
    if btn.count() == 0:
        print("  [ERR] Botao Pesquisar nao encontrado")
        return 0
    try:
        btn.first.wait_for(state="visible", timeout=15000)
    except PlaywrightTimeout:
        print("  [ERR] Botao Pesquisar nao ficou visivel")
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
    print(f"  [OK] Total de registros: {total}")
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
            processos.append({
                "texto":   proc_texto,
                "link_id": link_id,
            })
        break
    return processos


def fechar_modal_bloqueante(page):
    try:
        page.evaluate("""
            () => {
                const masks = document.querySelectorAll('.rich-mpnl-mask-div-opaque, .rich-mpnl-mask-div');
                masks.forEach(el => el.style.display = 'none');
            }
        """)
    except Exception:
        pass


def abrir_detalhe(page, processo):
    link_id = processo.get("link_id", "")
    if not link_id:
        return False

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
        print(f"    [ERR] Erro ao abrir detalhe: {e}")
        return False


def voltar_para_lista(page):
    try:
        aba = page.locator('[id="form:abaPesquisa_lbl"]')
        if aba.count() > 0:
            aba.first.click()
            time.sleep(1.5)
            page.wait_for_load_state("networkidle", timeout=15000)
            return True
        return False
    except:
        return False


# ─── Diagnóstico do modal de documentos ──────────────────────────────────────

def diagnosticar_documentos(page, processo_texto):
    """
    Clica em "Documentos da licitação", captura o modal, requisições e analisa.
    """
    print(f"    [DOC] Clicando em 'Documentos da licitação'...")

    # Registrar requisições para diagnóstico
    requisicoes = []
    def handle_response(response):
        try:
            requisicoes.append({
                "url": response.url,
                "status": response.status,
                "content_type": response.headers.get("content-type", ""),
                "timestamp": datetime.now().isoformat()
            })
        except:
            pass

    page.on("response", handle_response)

    btn_doc = page.locator('[id="form:j_id111"]')
    if btn_doc.count() == 0:
        # Fallback: procura por valor do botão
        btn_doc = page.locator('input[value="Documentos da licitação"]')
    if btn_doc.count() == 0:
        print(f"    [ERR] Botão 'Documentos da licitação' não encontrado!")
        page.remove_listener("response", handle_response)
        return

    btn_doc.first.click()
    time.sleep(2)
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except PlaywrightTimeout:
        print(f"    [WAIT] Timeout no networkidle (pode ser normal)")
    time.sleep(1)

    # Aguarda tabela ter ao menos 1 linha (ou timeout)
    try:
        page.wait_for_selector(
            '[id="form:tabelaDocumentos:tb"] tr',
            timeout=8000,
        )
        print(f"    [DOC] [OK] Tabela de documentos carregou com dados")
    except PlaywrightTimeout:
        print(f"    [DOC] Tabela vazia ou sem dados (timeout)")

    # Captura HTML completo
    html = page.content()
    nome_safe = re.sub(r'[^\w]', '_', processo_texto)[:50]
    arquivo_html = f"debug_documentos_{nome_safe}.html"
    with open(arquivo_html, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"    [DOC] HTML salvo em: {arquivo_html}")

    # Analisa a tabela
    soup = BeautifulSoup(html, "lxml")
    tabela = soup.find("table", id="form:tabelaDocumentos")

    docs_parseados = []
    if not tabela:
        print(f"    [DOC] [ERR] Tabela form:tabelaDocumentos não encontrada no HTML")
    else:
        rows = tabela.find_all("tr")[1:]  # pula cabeçalho
        print(f"    [DOC] Linhas na tabela: {len(rows)}")

        if not rows:
            print(f"    [DOC] -> Nenhum documento para esta licitação")
        else:
            for i, tr in enumerate(rows):
                tds = tr.find_all("td")
                if len(tds) < 2:
                    continue

                col_doc = tds[0]
                col_arq = tds[1]

                nome_doc = col_doc.get_text(strip=True)
                print(f"\n    [DOC] --- Documento {i+1} ---")
                print(f"    [DOC] Nome: {nome_doc}")

                doc_info = {
                    "indice": i + 1,
                    "nome": nome_doc,
                    "html_arquivo": str(col_arq),
                    "elementos": []
                }

                # Procura links <a>
                links = col_arq.find_all("a")
                if links:
                    for link in links:
                        href = link.get("href", "")
                        onclick = link.get("onclick", "")
                        texto = link.get_text(strip=True)
                        elem_info = {
                            "tipo": "a",
                            "texto": texto,
                            "href": href,
                            "onclick": onclick
                        }
                        doc_info["elementos"].append(elem_info)
                        print(f"    [DOC]   <a> texto='{texto}' href='{href}'")
                        if onclick:
                            print(f"    [DOC]      onclick='{onclick[:120]}...'")
                else:
                    print(f"    [DOC]   Sem <a> — texto: '{col_arq.get_text(strip=True)}'")

                # Procura inputs/buttons
                inputs = col_arq.find_all("input")
                for inp in inputs:
                    elem_info = {
                        "tipo": "input",
                        "input_type": inp.get("type", ""),
                        "value": inp.get("value", ""),
                        "onclick": inp.get("onclick", ""),
                        "id": inp.get("id", "")
                    }
                    doc_info["elementos"].append(elem_info)
                    print(f"    [DOC]   <input type='{inp.get('type','')}' value='{inp.get('value','')}'")
                    if inp.get("onclick"):
                        print(f"    [DOC]      onclick='{inp.get('onclick','')[:120]}...'")

                docs_parseados.append(doc_info)

    # Salvar diagnóstico em JSON
    arquivo_json = f"debug_documentos_{nome_safe}.json"
    diagnostico = {
        "timestamp": datetime.now().isoformat(),
        "processo": processo_texto,
        "documentos": docs_parseados,
        "requisicoes_capturadas": requisicoes,
        "quantidade_docs": len(docs_parseados)
    }
    with open(arquivo_json, "w", encoding="utf-8") as f:
        json.dump(diagnostico, f, indent=2, ensure_ascii=False)
    print(f"    [DOC] JSON salvo em: {arquivo_json}")

    # Imprimir resumo de requisições
    print(f"    [DOC] Requisições capturadas: {len(requisicoes)}")
    for req in requisicoes:
        if "download" in req["url"].lower() or "documento" in req["url"].lower():
            print(f"    [DOC]   • {req['status']} {req['url']}")

    page.remove_listener("response", handle_response)
    fechar_modal(page)


def fechar_modal(page):
    """Fecha o modal de documentos."""
    try:
        # Botão X do modal
        fechar = page.locator('img[onclick*="hideModalPanel(\'form:documentos\')"]')
        if fechar.count() > 0:
            fechar.first.click()
            time.sleep(0.5)
            return
        # Fallback: executa JS direto
        page.evaluate("Richfaces.hideModalPanel('form:documentos')")
        time.sleep(0.5)
    except Exception:
        pass


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 65)
    print("AgroIA-RMC — Diagnóstico: Modal de Documentos")
    print("=" * 65)

    with sync_playwright() as p:
        print("\n[1] Abrindo navegador...")
        browser = p.chromium.launch(headless=False, slow_mo=100)
        context = browser.new_context()
        page = context.new_page()

        print("[2] Acessando portal...")
        page.goto(PORTAL_URL, timeout=60000)
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        print("[3] Fazendo pesquisa...")
        total = fazer_pesquisa(page)
        if total == 0:
            print("[ERR] Nenhum registro. Verifique portal/órgão/datas.")
            browser.close()
            return

        print(f"\n[4] Testando {MAX_LICITACOES} licitações...\n")

        processos = extrair_processos_pagina(page)
        if not processos:
            print("[ERR] Nenhum processo extraído da página.")
            browser.close()
            return

        testados = 0
        for proc in processos:
            if testados >= MAX_LICITACOES:
                break

            texto = proc["texto"]
            print(f"\n  === Licitação {testados+1}/{MAX_LICITACOES}: {texto} ===")

            if not abrir_detalhe(page, proc):
                print(f"    [ERR] Falha ao abrir detalhe. Pulando.")
                continue

            diagnosticar_documentos(page, texto)

            if not voltar_para_lista(page):
                print(f"    [ERR] Falha ao voltar para lista. Refazendo pesquisa...")
                page.goto(PORTAL_URL, timeout=60000)
                page.wait_for_load_state("networkidle")
                time.sleep(2)
                fazer_pesquisa(page)

            testados += 1
            time.sleep(1)

        browser.close()

    print("\n" + "=" * 65)
    print(f"Diagnóstico concluído. {testados} licitações testadas.")
    print("Analise os arquivos debug_documentos_*.html gerados.")
    print("=" * 65)


if __name__ == "__main__":
    main()
