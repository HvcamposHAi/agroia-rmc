"""
AgroIA-RMC — Coleta de Itens de Licitações (v9)
================================================
Correções vs v8.1:
  1. [CRÍTICO] voltar_para_lista: "Lista Licitações" é um <td> de aba RichFaces
     (id="form:abaPesquisa_lbl"), não um <a>. Corrigido seletor.
  2. [CRÍTICO] empenhos: colunas reais são Número|Ano|Data Empenho (3 cols),
     não Número|Data|Valor|Ano (4 cols). Mapeamento corrigido.
  3. coletar_todas_paginas_itens: datascroller escopado para
     form:tabelaItens:j_id140, evitando conflito com outros datascrollers.

Correções anteriores (mantidas):
  4. _extrair_total_de_html: regex com DOTALL cruzando tags HTML.
  5. extrair_processos_pagina: extrai id do <a> (ex: "form:tabela:0:j_id26").
  6. abrir_detalhe: clica via [id="form:tabela:N:j_id26"] (atributo).
  7. fazer_pesquisa: fallback se contador=0 mas há processos visíveis.
  8. Loop principal: funciona com total desconhecido.

Execute: python etapa2_itens_v9.py
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

PORTAL_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
ORGAO      = "SMSAN/FAAC"
DT_INICIO  = "01/01/2019"
DT_FIM     = "31/12/2026"
REGS_POR_PAG = 5
DELAY        = 2.0
DEBUG        = True

# Se True: apaga itens existentes antes de reprocessar (corrige dados corrompidos)
FORCAR_REPROCESSAR = True

# Valor sentinela: pesquisa OK mas total de registros desconhecido
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

# ─── Funções auxiliares ───────────────────────────────────────────────────────
def parse_val(t):
    """Converte string de valor brasileiro (1.234,56) para float."""
    try:
        return float((t or "0").strip().replace(".", "").replace(",", "."))
    except:
        return 0.0

def norm_cultura(desc):
    """Extrai cultura do item."""
    desc = (desc or "").upper()
    culturas = [
        "ALFACE", "TOMATE", "BATATA", "CENOURA", "CEBOLA", "REPOLHO",
        "FEIJÃO", "FEIJAO", "ARROZ", "MILHO", "MANDIOCA", "AIPIM",
        "BANANA", "LARANJA", "MAÇÃ", "MACA", "LEITE", "OVO", "FRANGO",
        "CARNE", "PEIXE", "ALHO", "BETERRABA", "INHAME", "COUVE",
        "ESPINAFRE", "ABÓBORA", "ABOBORA", "PEPINO", "PIMENTÃO", "PIMENTAO",
    ]
    for c in culturas:
        if c in desc:
            canon = {
                "FEIJAO": "FEIJÃO", "MACA": "MAÇÃ", "ABOBORA": "ABÓBORA",
                "PIMENTAO": "PIMENTÃO", "AIPIM": "MANDIOCA",
            }
            return canon.get(c, c)
    return "OUTRO"

def tipo_forn(razao):
    razao = (razao or "").upper()
    if any(x in razao for x in ["COOPERATIVA", "COOP."]):
        return "cooperativa"
    if any(x in razao for x in ["ASSOCIAÇÃO", "ASSOCIACAO", "ASSOC."]):
        return "associacao"
    return "individual"

# ─── Extração de dados do detalhe ─────────────────────────────────────────────
def extrair_itens_de_html(html):
    """
    Extrai itens, fornecedores e empenhos do HTML de detalhe de licitação.
    Usa as tabelas reais do portal:
      - form:tabelaItens                          → itens
      - form:tabelaFornecedoresParticipantes /
        form:tabelaFornecedoresEdital             → fornecedores
      - form:tabelaEmpenhosProcCompra             → empenhos
    """
    soup = BeautifulSoup(html, "lxml")
    itens, forns, emps = [], [], []

    # ── Itens ────────────────────────────────────────────────────────────────
    # Estratégia 1: ID fixo confirmado no portal
    tabela_itens = soup.find("table", id="form:tabelaItens")
    # Estratégia 2 (fallback): tabela com TH "seq"/"código" (abordagem da Etapa 1)
    if not tabela_itens:
        for t in soup.find_all("table"):
            ths = [th.get_text(strip=True).lower() for th in t.find_all("th")]
            if any(h in ths for h in ["seq", "código", "codigo"]):
                tabela_itens = t
                break
    if tabela_itens:
        for tr in tabela_itens.find_all("tr")[1:]:  # pula cabeçalho
            tds = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(tds) < 4:
                continue
            try:
                seq   = int(tds[0]) if tds[0].isdigit() else None
                cod   = tds[1]
                desc  = tds[2]
                qt    = parse_val(tds[3])
                und   = tds[4]  if len(tds) > 4 else ""
                v_un  = parse_val(tds[5]) if len(tds) > 5 else 0.0
                v_tot = qt * v_un
                # Tenta ler valor total da coluna se existir
                if len(tds) > 6:
                    v_col = parse_val(tds[6])
                    if v_col > 0:
                        v_tot = v_col

                if seq is None:
                    continue

                itens.append({
                    "seq":              seq,
                    "codigo":           cod,
                    "descricao":        desc,
                    "descricao_completa": desc,
                    "qt_solicitada":    qt,
                    "unidade_medida":   und,
                    "valor_unitario":   v_un,
                    "valor_total":      v_tot,
                    "cultura":          norm_cultura(desc),
                    "categoria":        "OUTRO",
                })
            except Exception:
                continue

    # ── Fornecedores ─────────────────────────────────────────────────────────
    for tab_id in ["form:tabelaFornecedoresParticipantes", "form:tabelaFornecedoresEdital"]:
        tab = soup.find("table", id=tab_id)
        if not tab:
            continue
        for tr in tab.find_all("tr")[1:]:
            tds = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(tds) < 2:
                continue
            cnpj = re.sub(r'\D', '', tds[0])
            nome = tds[1] if len(tds) > 1 else ""
            if cnpj and len(cnpj) >= 11:
                forns.append({"cpf_cnpj": cnpj, "razao_social": nome})
        if forns:
            break

    # ── Empenhos ─────────────────────────────────────────────────────────────
    # Colunas reais (confirmadas no HTML): Número | Ano | Data Empenho
    tab_emp = soup.find("table", id="form:tabelaEmpenhosProcCompra")
    if tab_emp:
        for tr in tab_emp.find_all("tr")[1:]:
            tds = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(tds) < 2:
                continue
            num = tds[0]
            ano = tds[1] if len(tds) > 1 else ""
            dt  = tds[2] if len(tds) > 2 else ""
            emps.append({
                "numero":     num,
                "valor":      0.0,
                "ano":        int(ano) if ano.isdigit() else None,
                "dt_empenho": dt,
            })

    return itens, forns, emps

# ─── Gravação no Supabase ─────────────────────────────────────────────────────
def gravar(lic_id, itens, forns, emps):
    n_i = n_f = 0

    for item in itens:
        item["licitacao_id"] = lic_id
        try:
            sb.table("itens_licitacao").upsert(
                item, on_conflict="licitacao_id,seq"
            ).execute()
            n_i += 1
        except Exception as e:
            if DEBUG:
                print(f"      [!] Erro item seq={item.get('seq')}: {e}")

    for forn in forns:
        try:
            r = sb.table("fornecedores").upsert(
                {
                    "cpf_cnpj":    forn["cpf_cnpj"],
                    "razao_social": forn["razao_social"],
                    "tipo":        tipo_forn(forn["razao_social"]),
                },
                on_conflict="cpf_cnpj",
            ).execute()
            fid = r.data[0]["id"] if r.data else None
            if not fid:
                r2 = sb.table("fornecedores").select("id").eq(
                    "cpf_cnpj", forn["cpf_cnpj"]
                ).execute()
                fid = r2.data[0]["id"] if r2.data else None
            if fid:
                sb.table("participacoes").upsert(
                    {"licitacao_id": lic_id, "fornecedor_id": fid, "participou": True},
                    on_conflict="licitacao_id,fornecedor_id",
                ).execute()
                n_f += 1
        except Exception as e:
            if DEBUG:
                print(f"      [!] Erro fornecedor: {e}")

    # Empenhos: associa ao primeiro item da licitação
    if emps and itens:
        try:
            r = sb.table("itens_licitacao").select("id").eq(
                "licitacao_id", lic_id
            ).limit(1).execute()
            if r.data:
                item_id = r.data[0]["id"]
                for emp in emps:
                    emp["item_id"] = item_id
                    sb.table("empenhos").upsert(
                        emp, on_conflict="item_id,numero"
                    ).execute()
        except Exception as e:
            if DEBUG:
                print(f"      [!] Erro empenhos: {e}")

    return n_i, n_f

def deletar_itens_licitacao(lic_id):
    try:
        sb.table("itens_licitacao").delete().eq("licitacao_id", lic_id).execute()
    except Exception as e:
        if DEBUG:
            print(f"      [!] Erro ao deletar itens de licitacao_id={lic_id}: {e}")

# ─── Funções de navegação no portal ───────────────────────────────────────────
def preencher_data(page, campo_id, valor):
    """
    Preenche campo de data JSF via triple-click + keyboard.type + Tab.
    IMPORTANTE: usar [id="..."] em vez de #id — IDs JSF com ':' quebram CSS.
    """
    campo = page.locator(f'[id="{campo_id}"]')
    if campo.count() == 0:
        if DEBUG:
            print(f"      [!] Campo {campo_id} não encontrado")
        return False
    campo.click(click_count=3)
    time.sleep(0.2)
    page.keyboard.type(valor, delay=50)
    time.sleep(0.3)
    page.keyboard.press("Tab")  # dispara onchange JSF
    time.sleep(0.5)
    return True

def _extrair_total_de_html(html):
    """
    Extrai o total de registros do HTML da página de resultados.

    Estrutura real do portal (confirmada no ingestao_supabase.py / Etapa 1):
        quantidade registros:</label></td><td><label>1238</label>
    O número fica dentro de um <label> em um <td> DIFERENTE do texto.
    Regex com re.DOTALL atravessa as tags intermediárias.
    """
    # Método 1: regex com DOTALL — confirmado no ingestao_supabase.py
    m = re.search(r"quantidade registros.*?(\d+)</label>", html, re.I | re.DOTALL)
    if m:
        return int(m.group(1))

    # Método 2: texto plano (fallback)
    texto = BeautifulSoup(html, "lxml").get_text()
    m2 = re.search(r"quantidade\s+registros[\s:]*?(\d+)", texto, re.I)
    return int(m2.group(1)) if m2 else 0

def fazer_pesquisa(page):
    """
    Executa pesquisa no portal com órgão e datas configurados.
    Retorna:
        N > 0              → N registros encontrados
        TOTAL_DESCONHECIDO → pesquisa OK mas não foi possível ler o contador
        0                  → nenhum resultado (ou falha na pesquisa)
    """
    # Selecionar órgão
    selects = page.locator("select")
    orgao_ok = False
    for i in range(selects.count()):
        sel = selects.nth(i)
        if sel.locator(f'option:has-text("{ORGAO}")').count() > 0:
            sel.select_option(label=ORGAO)
            time.sleep(1)
            orgao_ok = True
            if DEBUG:
                print(f"    ✓ Órgão: {ORGAO}")
            break
    if not orgao_ok:
        print(f"    [!] Órgão {ORGAO} não encontrado nos selects")

    # Preencher datas
    ok_ini = preencher_data(page, "form:dataInferiorInputDate", DT_INICIO)
    ok_fim = preencher_data(page, "form:j_id18InputDate",       DT_FIM)
    if DEBUG:
        print(f"    {'✓' if ok_ini else '✗'} Data inicial: {DT_INICIO}")
        print(f"    {'✓' if ok_fim else '✗'} Data final:   {DT_FIM}")

    # Clicar em Pesquisar
    btn = page.locator('[id="form:btSearch"], input[value="Pesquisar"]')
    if btn.count() == 0:
        print("    [!] Botão Pesquisar não encontrado")
        return 0
    btn.first.click()
    time.sleep(3)
    page.wait_for_load_state("networkidle", timeout=30000)
    time.sleep(1)

    # Tentar extrair total de registros via BeautifulSoup
    html  = page.content()
    total = _extrair_total_de_html(html)
    if total > 0:
        if DEBUG:
            print(f"    ✓ Total de registros: {total}")
        procs_pg1 = extrair_processos_pagina(page)
        if DEBUG:
            print(f"    ✓ Processos visíveis na pág. 1: {len(procs_pg1)}")
            for p in procs_pg1[:3]:
                print(f"      • {p['texto']} (link_id={p['link_id']})")
        return total

    # Fallback: se contador não foi lido mas há processos na página, continua
    if extrair_processos_pagina(page):
        print("    [~] Contador não lido, mas há processos visíveis → total desconhecido")
        return TOTAL_DESCONHECIDO

    return 0

def extrair_processos_pagina(page):
    """
    Extrai lista de processos da página atual de resultados.

    Estratégia (confirmada na Etapa 1 / ingestao_supabase.py):
    - Encontra a tabela que tem TH "processo" e "objeto"
    - Cada linha tem col[0] = número do processo (ex: "DS 70/2019 - SMSAN/FAAC")
    - O <a> da col[0] tem atributo id="form:tabela:N:j_id26" → usado para clicar
    """
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
                "objeto":  cols[1].get_text(strip=True) if len(cols) > 1 else "",
                "situacao": cols[3].get_text(strip=True) if len(cols) > 3 else "",
            })
        break  # tabela correta encontrada
    return processos

def ir_para_proxima_pagina(page, pag_atual):
    """
    Tenta navegar para a próxima página na tabela de resultados.
    Estratégia 1: clica no número (pag_atual+1) em td.rich-datascr-inact.
    Estratégia 2: clica no botão ">" (próxima página) do datascroller.
    Retorna True se navegou, False se não há próxima página.
    """
    prox = pag_atual + 1

    # Estratégia 1: clica no número da próxima página
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

    # Estratégia 2: botão ">" do datascroller (página seguinte)
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
    """
    Navega para a página num_pagina na tabela de resultados.
    Mantido para compatibilidade com refazer_pesquisa_e_navegar.
    """
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

def aguardar_tabela_itens(page, timeout_ms=15000):
    """Aguarda a tabela form:tabelaItens aparecer e ter pelo menos uma linha."""
    try:
        page.wait_for_selector(
            '[id="form:tabelaItens"] tbody tr',
            timeout=timeout_ms,
        )
        return True
    except PlaywrightTimeout:
        return False

def coletar_todas_paginas_itens(page):
    """
    Coleta itens de todas as páginas da tabela form:tabelaItens no detalhe.
    Retorna (itens, forns, emps) consolidados de todas as páginas.
    """
    todos_itens, todos_forns, todos_emps = [], [], []
    seqs_vistos = set()

    pagina = 1
    while True:
        html = page.content()
        itens, forns, emps = extrair_itens_de_html(html)

        for item in itens:
            if item["seq"] not in seqs_vistos:
                seqs_vistos.add(item["seq"])
                todos_itens.append(item)

        if pagina == 1:
            todos_forns = forns
            todos_emps  = emps

        # Verifica se há próxima página de itens
        # Escopado para o datascroller da tabelaItens (j_id140),
        # evitando conflito com datascrollers de outras tabelas na página
        proximas = page.locator(
            '[id="form:tabelaItens:j_id140"] td.rich-datascr-inact'
        )
        prox_pagina = None
        for i in range(proximas.count()):
            elem = proximas.nth(i)
            txt  = elem.text_content().strip()
            if txt == str(pagina + 1):
                prox_pagina = elem
                break

        if prox_pagina is None:
            break

        if DEBUG:
            print(f"        → Página de itens {pagina + 1}...")
        # O datascroller interno pode estar fora da viewport ou dentro de
        # um painel JSF oculto. Estratégias em cascata:
        #   1. scroll_into_view_if_needed + click normal
        #   2. click(force=True) — bypassa checagem de visibilidade
        #   3. JavaScript .click() direto — ignora tudo de visibilidade
        clicou = False
        try:
            prox_pagina.scroll_into_view_if_needed(timeout=2000)
            prox_pagina.click(timeout=3000)
            clicou = True
        except Exception:
            pass
        if not clicou:
            try:
                prox_pagina.click(force=True, timeout=5000)
                clicou = True
            except Exception:
                pass
        if not clicou:
            # Fallback JS: invoca o onclick no datascroller escopado
            page_num_str = str(pagina + 1)
            page.evaluate(f"""() => {{
                const container = document.getElementById('form:tabelaItens:j_id140');
                if (!container) return;
                const tds = container.querySelectorAll('td.rich-datascr-inact');
                for (const td of tds) {{
                    if (td.textContent.trim() === '{page_num_str}') {{
                        td.click();
                        break;
                    }}
                }}
            }}""")
        time.sleep(1.5)
        page.wait_for_load_state("networkidle", timeout=10000)
        pagina += 1

    return todos_itens, todos_forns, todos_emps

def abrir_detalhe(page, processo):
    """
    Abre a página de detalhe de um processo clicando no link da listagem.

    O link tem id="form:tabela:N:j_id31" — usa seletor de atributo [id="..."]
    pois IDs com ':' quebram seletores CSS padrão no Playwright.
    """
    link_id = processo.get("link_id", "")
    if not link_id:
        if DEBUG:
            print(f"        [!] link_id ausente para: {processo.get('texto','?')}")
        return False
    try:
        elem = page.locator(f'[id="{link_id}"]')
        if elem.count() == 0:
            if DEBUG:
                print(f"        [!] Link não encontrado na página: id={link_id}")
            return False
        elem.first.click()
        time.sleep(1.5)
        page.wait_for_load_state("networkidle", timeout=30000)
        if not aguardar_tabela_itens(page, timeout_ms=15000):
            if DEBUG:
                print("        [~] Tabela de itens não carregou (pode estar vazia)")
        return True
    except Exception as e:
        if DEBUG:
            print(f"      [!] Erro ao abrir detalhe: {e}")
        return False

def voltar_para_lista(page):
    """
    Volta para a aba de listagem de licitações.
    No portal JSF/RichFaces, "Lista Licitações" é um <td> de aba,
    não um <a>. ID confirmado: form:abaPesquisa_lbl
    """
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

def refazer_pesquisa_e_navegar(page, pagina_alvo):
    """
    Recarrega o portal, refaz a pesquisa e navega até a página alvo.
    Retorna True se chegou na página alvo (ou se a pesquisa tem resultados).
    """
    page.goto(PORTAL_URL, timeout=60000)
    page.wait_for_load_state("networkidle")
    time.sleep(2)

    total = fazer_pesquisa(page)
    if total == 0:
        return False  # portal não retornou nada

    # Se total desconhecido ou positivo, tenta navegar
    for p in range(2, pagina_alvo + 1):
        if not ir_para_pagina_lista(page, p):
            # Tenta botão "próxima"
            if not ir_para_proxima_pagina(page, p - 1):
                return False
    return True

# ─── Carregar licitações do banco ─────────────────────────────────────────────
def carregar_licitacoes():
    """Carrega licitações do Supabase e identifica pendentes."""
    r = sb.table("licitacoes").select(
        "id, processo, situacao, tipo_processo"
    ).limit(2000).execute()
    todas = {x["id"]: x for x in r.data}

    r_itens = sb.table("itens_licitacao").select("licitacao_id").execute()
    ids_com_itens = set(
        x["licitacao_id"] for x in r_itens.data if x.get("licitacao_id")
    )

    # Índice processo → id
    indice = {}
    for lic in todas.values():
        proc = lic.get("processo", "")
        if proc:
            indice[proc] = lic["id"]
            # ex: "DS 70/2019 - SMSAN/FAAC" → também indexa "DS 70/2019"
            m = re.match(r'^([A-Z]{2}\s+\d+/\d{4})', proc)
            if m:
                indice[m.group(1)] = lic["id"]

    return todas, ids_com_itens, indice

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    global INTERROMPIDO

    print("=" * 65)
    print("AgroIA-RMC — Coleta de Itens de Licitações (v9)")
    print(f"Início: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"FORCAR_REPROCESSAR: {FORCAR_REPROCESSAR}")
    print("=" * 65)

    print("\n[0] Carregando licitações do Supabase...")
    todas, ids_com_itens, indice = carregar_licitacoes()
    pendentes = len(todas) - len(ids_com_itens)
    print(f"    {len(todas)} licitações no banco")
    print(f"    {len(ids_com_itens)} já têm itens")
    print(f"    {pendentes} pendentes de coleta")
    if FORCAR_REPROCESSAR and ids_com_itens:
        print(f"    FORCAR_REPROCESSAR=True → {len(ids_com_itens)} serão reprocessadas")

    stats = {
        "processados":    0,
        "itens":          0,
        "fornecedores":   0,
        "pulados":        0,
        "erros":          0,
        "nao_encontrados": 0,
    }

    with sync_playwright() as p:
        print("\n[1] Abrindo navegador...")
        browser = p.chromium.launch(headless=False, slow_mo=80)
        context = browser.new_context()
        page    = context.new_page()

        print("[2] Acessando portal e fazendo pesquisa...")
        page.goto(PORTAL_URL, timeout=60000)
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        total = fazer_pesquisa(page)

        if total == 0:
            print("\n[!] PROBLEMA: Nenhum registro retornado.")
            print("    Verifique portal, órgão e datas.")
            browser.close()
            return

        if total == TOTAL_DESCONHECIDO:
            total_pags = None
            print("\n[3] Total de registros desconhecido. Paginando até esgotar...")
        else:
            total_pags = math.ceil(total / REGS_POR_PAG)
            print(f"\n[3] {total} registros em {total_pags} páginas. Iniciando coleta...")

        pag_atual   = 1
        paginas_sem_processo = 0  # segurança para evitar loop infinito

        while not INTERROMPIDO:
            # Condição de parada quando total é conhecido
            if total_pags is not None and pag_atual > total_pags:
                break

            print(f"\n--- Página {pag_atual}" +
                  (f"/{total_pags}" if total_pags else "") + " ---")

            processos = extrair_processos_pagina(page)
            if not processos:
                print("    [!] Nenhum processo encontrado — possivelmente perdeu estado. Refazendo...")
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

                texto     = proc.get("texto", "")
                portal_id = proc.get("portal_id", "")

                # Encontra ID no banco
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

                # Pular se já tem itens e não está forçando reprocessamento
                if lic_id in ids_com_itens and not FORCAR_REPROCESSAR:
                    print(f"    [=] Já coletado: {texto}")
                    stats["pulados"] += 1
                    continue

                print(f"    [>] Processando: {texto} (ID={lic_id})")

                if FORCAR_REPROCESSAR and lic_id in ids_com_itens:
                    deletar_itens_licitacao(lic_id)
                    ids_com_itens.discard(lic_id)

                # Abre detalhe
                if not abrir_detalhe(page, proc):
                    print(f"        [!] Falha ao abrir detalhe")
                    stats["erros"] += 1
                    refazer_pesquisa_e_navegar(page, pag_atual)
                    continue

                # Coleta itens de todas as páginas do detalhe
                itens, forns, emps = coletar_todas_paginas_itens(page)

                if itens:
                    n_i, n_f = gravar(lic_id, itens, forns, emps)
                    stats["itens"]        += n_i
                    stats["fornecedores"] += n_f
                    stats["processados"]  += 1
                    ids_com_itens.add(lic_id)
                    print(f"        ✓ {n_i} itens, {n_f} fornecedores, {len(emps)} empenhos")
                else:
                    print(f"        [!] Nenhum item encontrado no detalhe")
                    stats["erros"] += 1

                # Volta para lista
                if not voltar_para_lista(page):
                    print("        [~] Link 'Lista Licitações' não encontrado. Refazendo pesquisa...")
                    if not refazer_pesquisa_e_navegar(page, pag_atual):
                        print("    [!] Falha ao recuperar. Encerrando.")
                        INTERROMPIDO = True
                        break

                time.sleep(DELAY)

            if INTERROMPIDO:
                break

            # Navega para a próxima página da lista
            print(f"\n    Navegando para página {pag_atual + 1}...")
            navegou = ir_para_proxima_pagina(page, pag_atual)
            if not navegou:
                if total_pags is None:
                    print("    → Sem mais páginas. Coleta concluída.")
                else:
                    print(f"    [!] Não conseguiu ir para página {pag_atual + 1}. Refazendo...")
                    if not refazer_pesquisa_e_navegar(page, pag_atual + 1):
                        print("    [!] Falha na navegação. Encerrando.")
                        break
            pag_atual += 1

        browser.close()

    # Relatório final
    print("\n" + "=" * 65)
    print("CONCLUÍDO!")
    print("=" * 65)
    print(f"  Processados:     {stats['processados']}")
    print(f"  Itens gravados:  {stats['itens']}")
    print(f"  Fornecedores:    {stats['fornecedores']}")
    print(f"  Pulados:         {stats['pulados']}")
    print(f"  Não encontrados: {stats['nao_encontrados']}")
    print(f"  Erros:           {stats['erros']}")
    if INTERROMPIDO:
        print("  (Interrompido — rode novamente para continuar)")
    print("=" * 65)


if __name__ == "__main__":
    main()
