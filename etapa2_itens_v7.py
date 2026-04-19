"""
AgroIA-RMC — Coleta de Itens de Licitações (v7)
================================================
Correções vs v6:
  1. [CRÍTICO] preencher_data: [id="..."] em vez de #id (bug JSF)
  2. [CRÍTICO] extrair_dados_detalhe: usa IDs reais das tabelas
       - form:tabelaItens           → itens
       - form:tabelaFornecedoresParticipantes / Edital → fornecedores
       - form:tabelaEmpenhosProcCompra → empenhos
  3. valor_total calculado como qt_solicitada × valor_unitario
  4. Aguarda carregamento dos itens antes de capturar HTML
  5. Paginação interna da tabela de itens (datascroller próprio)
  6. FORCAR_REPROCESSAR: deleta itens existentes antes de reprocessar

Execute: python etapa2_itens_v7.py
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
ORGAO = "SMSAN/FAAC"
DT_INICIO = "01/01/2019"
DT_FIM = "31/12/2026"
REGS_POR_PAG = 5
DELAY = 2.0
DEBUG = True

# Se True: apaga itens existentes antes de reprocessar (corrige dados corrompidos)
FORCAR_REPROCESSAR = True

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
            # normaliza nome canônico
            canon = {
                "FEIJAO": "Feijão", "MACA": "Maçã", "AIPIM": "Mandioca",
                "ABOBORA": "Abóbora", "PIMENTAO": "Pimentão",
            }
            return canon.get(c, c.capitalize())
    return ""

def categ(cultura):
    if not cultura:
        return "OUTRO"
    hort = ["Alface", "Tomate", "Batata", "Cenoura", "Cebola", "Repolho",
            "Alho", "Beterraba", "Inhame", "Couve", "Espinafre", "Abóbora",
            "Pepino", "Pimentão"]
    grao = ["Feijão", "Arroz", "Milho"]
    frut = ["Banana", "Laranja", "Maçã"]
    prot = ["Leite", "Ovo", "Frango", "Carne", "Peixe"]
    raiz = ["Mandioca"]
    if cultura in hort: return "HORTALIÇA"
    if cultura in grao: return "GRÃO"
    if cultura in frut: return "FRUTA"
    if cultura in prot: return "PROTEÍNA"
    if cultura in raiz: return "RAIZ"
    return "OUTRO"

def tipo_forn(razao):
    razao = (razao or "").upper()
    if "COOPERATIVA" in razao or "COOP" in razao:
        return "cooperativa"
    if "ASSOCIA" in razao:
        return "associacao"
    return "empresa"

# ─── Extração de dados da página de detalhe ───────────────────────────────────
def extrair_itens_de_html(html):
    """
    Extrai itens, fornecedores e empenhos do HTML da página de detalhe.

    Usa os IDs reais das tabelas JSF (confirmados via debug_detalhe_playwright.html):
      - form:tabelaItens
      - form:tabelaFornecedoresParticipantes  (preferencial)
      - form:tabelaFornecedoresEdital         (fallback)
      - form:tabelaEmpenhosProcCompra
    """
    soup = BeautifulSoup(html, "lxml")
    itens, forns, emps = [], [], []

    # ── Itens ─────────────────────────────────────────────────────────────────
    t_itens = soup.find(id="form:tabelaItens")
    if t_itens:
        tbody = t_itens.find("tbody")
        linhas = tbody.find_all("tr") if tbody else t_itens.find_all("tr")[1:]
        for i, tr in enumerate(linhas):
            cols = tr.find_all("td")
            if len(cols) < 3:
                continue
            seq_txt = cols[0].get_text(strip=True)
            seq = int(seq_txt) if seq_txt.isdigit() else i + 1
            codigo  = cols[1].get_text(strip=True) if len(cols) > 1 else ""
            desc    = cols[2].get_text(strip=True) if len(cols) > 2 else ""
            qt      = parse_val(cols[3].get_text(strip=True)) if len(cols) > 3 else 0.0
            un      = cols[4].get_text(strip=True) if len(cols) > 4 else ""
            v_unit  = parse_val(cols[5].get_text(strip=True)) if len(cols) > 5 else 0.0
            # col[6] é o link "Empenhos" — não é valor monetário
            v_total = round(qt * v_unit, 2)
            cultura = norm_cultura(desc)
            itens.append({
                "seq": seq,
                "codigo": codigo,
                "descricao": desc,
                "qt_solicitada": qt,
                "unidade_medida": un,
                "valor_unitario": v_unit,
                "valor_total": v_total,
                "cultura": cultura,
                "categoria": categ(cultura),
            })

    # ── Fornecedores ──────────────────────────────────────────────────────────
    cpfs_vistos = set()
    for forn_id in ["form:tabelaFornecedoresParticipantes", "form:tabelaFornecedoresEdital"]:
        t_forn = soup.find(id=forn_id)
        if not t_forn:
            continue
        tbody = t_forn.find("tbody")
        linhas = tbody.find_all("tr") if tbody else t_forn.find_all("tr")[1:]
        for tr in linhas:
            cols = tr.find_all("td")
            if len(cols) < 2:
                continue
            cpf   = cols[0].get_text(strip=True)
            razao = cols[1].get_text(strip=True)
            digits = re.sub(r"[^\d]", "", cpf)
            if len(digits) >= 11 and razao and cpf not in cpfs_vistos:
                cpfs_vistos.add(cpf)
                forns.append({"cpf_cnpj": cpf.strip(), "razao_social": razao.strip()})

    # ── Empenhos ──────────────────────────────────────────────────────────────
    t_emp = soup.find(id="form:tabelaEmpenhosProcCompra")
    if t_emp:
        tbody = t_emp.find("tbody")
        linhas = tbody.find_all("tr") if tbody else t_emp.find_all("tr")[1:]
        for tr in linhas:
            cols = tr.find_all("td")
            if len(cols) < 1:
                continue
            nr = cols[0].get_text(strip=True)
            if not nr or nr == "null":
                continue
            ano  = cols[1].get_text(strip=True) if len(cols) > 1 else ""
            data = cols[2].get_text(strip=True) if len(cols) > 2 else ""
            try:
                dt = datetime.strptime(data, "%d/%m/%Y").strftime("%Y-%m-%d")
            except:
                dt = None
            emps.append({
                "nr_empenho": nr,
                "ano": int(ano) if ano.isdigit() else None,
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
                    "cpf_cnpj": forn["cpf_cnpj"],
                    "razao_social": forn["razao_social"],
                    "tipo": tipo_forn(forn["razao_social"]),
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
                    try:
                        sb.table("empenhos").insert(emp).execute()
                    except Exception as e:
                        if DEBUG:
                            print(f"      [!] Erro empenho: {e}")
        except Exception as e:
            if DEBUG:
                print(f"      [!] Erro ao buscar item para empenho: {e}")

    return n_i, n_f

def deletar_itens_licitacao(lic_id):
    """Remove todos os itens de uma licitação (para reprocessamento limpo)."""
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

def fazer_pesquisa(page):
    """Executa pesquisa no portal com órgão e datas configurados."""
    # Selecionar órgão
    selects = page.locator("select")
    for i in range(selects.count()):
        sel = selects.nth(i)
        if sel.locator(f'option:has-text("{ORGAO}")').count() > 0:
            sel.select_option(label=ORGAO)
            time.sleep(1)
            if DEBUG:
                print(f"    ✓ Órgão: {ORGAO}")
            break
    else:
        print(f"    [!] Órgão {ORGAO} não encontrado")

    # Preencher datas
    ok_ini = preencher_data(page, "form:dataInferiorInputDate", DT_INICIO)
    ok_fim = preencher_data(page, "form:j_id18InputDate", DT_FIM)
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

    # Extrair total de registros
    html = page.content()
    for pat in [
        r'\b(\d+)\s+quantidade\s+registros\b',
        r'quantidade\s+registros[:\s]*(\d+)',
        r'(\d+)\s+registros',
    ]:
        m = re.search(pat, html, re.I)
        if m:
            return int(m.group(1))
    return 0

def extrair_processos_pagina(page):
    """Extrai lista de processos da página atual de resultados."""
    soup = BeautifulSoup(page.content(), "lxml")
    processos = []
    for a in soup.find_all("a", onclick=True):
        onclick = a.get("onclick", "")
        m = re.search(r"id=(\d+).*?situacao=([^&'\"]+)", onclick)
        if m:
            processos.append({
                "portal_id": m.group(1),
                "situacao": m.group(2),
                "texto": a.get_text(strip=True),
                "onclick": onclick,
            })
    return processos

def ir_para_pagina_lista(page, num_pagina):
    """
    Navega para página num_pagina na tabela de resultados.
    Usa o datascroller da lista principal (não o de itens do detalhe).
    """
    try:
        # Tenta clicar no número de página dentro do datascroller da lista
        # O datascroller da lista está fora de qualquer painel de detalhe
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
    """
    Aguarda a tabela form:tabelaItens aparecer e ter pelo menos uma linha.
    Retorna True se carregou, False se timeout.
    """
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
    Retorna lista consolidada de (itens, forns, emps) de todas as páginas.
    """
    todos_itens, todos_forns, todos_emps = [], [], []
    seqs_vistos = set()

    pagina = 1
    while True:
        html = page.content()
        itens, forns, emps = extrair_itens_de_html(html)

        # Acumula apenas itens novos (evita duplicatas de re-renderização)
        for item in itens:
            if item["seq"] not in seqs_vistos:
                seqs_vistos.add(item["seq"])
                todos_itens.append(item)

        # Fornecedores e empenhos: coleta apenas na primeira passagem
        if pagina == 1:
            todos_forns = forns
            todos_emps = emps

        # Verifica se há próxima página de itens
        proximas = page.locator("td.rich-datascr-inact")
        prox_pagina = None
        for i in range(proximas.count()):
            elem = proximas.nth(i)
            txt = elem.text_content().strip()
            if txt == str(pagina + 1):
                prox_pagina = elem
                break

        if prox_pagina is None:
            break  # sem mais páginas de itens

        if DEBUG:
            print(f"        → Página de itens {pagina + 1}...")
        prox_pagina.click()
        time.sleep(1.5)
        page.wait_for_load_state("networkidle", timeout=10000)
        pagina += 1

    return todos_itens, todos_forns, todos_emps

def abrir_detalhe(page, processo):
    """Abre a página de detalhe de um processo e aguarda os itens carregarem."""
    try:
        links = page.locator(f"a[onclick*=\"id={processo['portal_id']}\"]")
        if links.count() == 0:
            return False
        links.first.click()
        time.sleep(1.5)
        page.wait_for_load_state("networkidle", timeout=30000)

        # Aguarda os itens aparecerem na tabela
        if not aguardar_tabela_itens(page, timeout_ms=15000):
            if DEBUG:
                print("        [~] Tabela de itens não carregou (pode estar vazia)")
        return True
    except Exception as e:
        if DEBUG:
            print(f"      [!] Erro ao abrir detalhe: {e}")
        return False

def voltar_para_lista(page):
    """Volta para a aba de listagem de licitações."""
    try:
        link = page.locator("a:has-text('Lista Licitações')")
        if link.count() > 0:
            link.first.click()
            time.sleep(1.5)
            page.wait_for_load_state("networkidle", timeout=15000)
            return True
        return False
    except:
        return False

def refazer_pesquisa_e_navegar(page, pagina_alvo):
    """Recarrega portal, refaz pesquisa e navega até a página alvo."""
    page.goto(PORTAL_URL, timeout=60000)
    page.wait_for_load_state("networkidle")
    time.sleep(2)
    total = fazer_pesquisa(page)
    if total == 0:
        return False
    for p in range(2, pagina_alvo + 1):
        if not ir_para_pagina_lista(page, p):
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
    print("AgroIA-RMC — Coleta de Itens de Licitações (v7)")
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
        "processados": 0,
        "itens": 0,
        "fornecedores": 0,
        "pulados": 0,
        "erros": 0,
        "nao_encontrados": 0,
    }

    with sync_playwright() as p:
        print("\n[1] Abrindo navegador...")
        browser = p.chromium.launch(headless=False, slow_mo=80)
        context = browser.new_context()
        page = context.new_page()

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

        total_pags = math.ceil(total / REGS_POR_PAG)
        print(f"\n[3] {total} registros em {total_pags} páginas. Iniciando coleta...")

        pag_atual = 1
        while pag_atual <= total_pags and not INTERROMPIDO:
            print(f"\n--- Página {pag_atual}/{total_pags} ---")

            processos = extrair_processos_pagina(page)
            if not processos:
                print("    [!] Nenhum processo encontrado — possivelmente perdeu estado. Refazendo...")
                if not refazer_pesquisa_e_navegar(page, pag_atual):
                    print("    [!] Falha ao recuperar. Encerrando.")
                    break
                processos = extrair_processos_pagina(page)

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

                # Se forçando reprocessamento, deleta itens antigos
                if FORCAR_REPROCESSAR and lic_id in ids_com_itens:
                    deletar_itens_licitacao(lic_id)
                    ids_com_itens.discard(lic_id)

                # Abre detalhe
                if not abrir_detalhe(page, proc):
                    print(f"        [!] Falha ao abrir detalhe")
                    stats["erros"] += 1
                    # Tenta recuperar estado
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

            # Navega para próxima página da lista
            if pag_atual < total_pags and not INTERROMPIDO:
                print(f"\n    Navegando para página {pag_atual + 1}...")
                if not ir_para_pagina_lista(page, pag_atual + 1):
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
