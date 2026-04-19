"""
AgroIA-RMC — Coleta de Itens de Licitações (v6 - CORRIGIDA)
===========================================================
Correções:
  1. Preenchimento de data via triple-click + type (confirmado na Etapa 1)
  2. Não filtra por data inicialmente para diagnosticar total real
  3. Debug detalhado do matching portal → banco
  4. Processa TODOS os registros do portal (não apenas os pendentes)

Execute: python etapa2_itens_v6.py
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
DT_FIM = "31/12/2026"  # Expandido para incluir 2026
REGS_POR_PAG = 5
DELAY = 2.0
DEBUG = True  # Ativa debug detalhado

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
    """Converte string de valor para float."""
    try:
        return float((t or "0").strip().replace(".", "").replace(",", "."))
    except:
        return 0.0

def norm_cultura(desc):
    """Extrai cultura do item."""
    desc = (desc or "").upper()
    culturas = [
        "ALFACE", "TOMATE", "BATATA", "CENOURA", "CEBOLA", "REPOLHO",
        "FEIJÃO", "ARROZ", "MILHO", "MANDIOCA", "BANANA", "LARANJA",
        "MAÇÃ", "LEITE", "OVO", "FRANGO", "CARNE", "PEIXE"
    ]
    for c in culturas:
        if c in desc:
            return c.capitalize()
    return ""

def categ(cultura):
    """Categoriza a cultura."""
    if not cultura:
        return "OUTRO"
    hort = ["Alface", "Tomate", "Batata", "Cenoura", "Cebola", "Repolho"]
    grao = ["Feijão", "Arroz", "Milho"]
    frut = ["Banana", "Laranja", "Maçã"]
    prot = ["Leite", "Ovo", "Frango", "Carne", "Peixe"]
    if cultura in hort: return "HORTALIÇA"
    if cultura in grao: return "GRÃO"
    if cultura in frut: return "FRUTA"
    if cultura in prot: return "PROTEÍNA"
    return "OUTRO"

def tipo_forn(razao):
    """Classifica tipo de fornecedor."""
    razao = (razao or "").upper()
    if "COOPERATIVA" in razao or "COOP" in razao:
        return "cooperativa"
    if "ASSOCIA" in razao:
        return "associacao"
    return "empresa"

# ─── Extração de dados da página de detalhe ───────────────────────────────────
def extrair_dados_detalhe(html):
    """Extrai itens, fornecedores e empenhos do HTML de detalhe."""
    soup = BeautifulSoup(html, "lxml")
    itens, forns, emps = [], [], []
    
    for t in soup.find_all("table"):
        ths = [th.get_text(strip=True).lower() for th in t.find_all("th")]
        
        # Tabela de itens (detecta por cabeçalhos)
        if any(h in ths for h in ["seq", "código", "codigo"]):
            for i, tr in enumerate(t.find_all("tr")[1:]):
                cols = tr.find_all("td")
                if len(cols) < 3:
                    continue
                seq_txt = cols[0].get_text(strip=True)
                desc = cols[2].get_text(strip=True) if len(cols) > 2 else ""
                cultura = norm_cultura(desc)
                itens.append({
                    "seq": int(seq_txt) if seq_txt.isdigit() else i + 1,
                    "codigo": cols[1].get_text(strip=True) if len(cols) > 1 else "",
                    "descricao": desc,
                    "qt_solicitada": parse_val(cols[3].get_text(strip=True)) if len(cols) > 3 else 0,
                    "unidade_medida": cols[4].get_text(strip=True) if len(cols) > 4 else "",
                    "valor_unitario": parse_val(cols[5].get_text(strip=True)) if len(cols) > 5 else 0,
                    "valor_total": parse_val(cols[6].get_text(strip=True)) if len(cols) > 6 else 0,
                    "cultura": cultura,
                    "categoria": categ(cultura),
                })
        
        # Tabela de fornecedores
        elif any(h in ths for h in ["cpf/cnpj", "cnpj", "razão social", "razao social"]):
            for tr in t.find_all("tr")[1:]:
                cols = tr.find_all("td")
                if len(cols) < 2:
                    continue
                cpf = cols[0].get_text(strip=True)
                razao = cols[1].get_text(strip=True)
                if len(re.sub(r"[^\d]", "", cpf)) >= 11 and razao:
                    forns.append({"cpf_cnpj": cpf.strip(), "razao_social": razao.strip()})
        
        # Tabela de empenhos
        elif "empenho" in " ".join(ths):
            for tr in t.find_all("tr")[1:]:
                cols = tr.find_all("td")
                if len(cols) < 2:
                    continue
                nr = cols[0].get_text(strip=True)
                if nr and nr != "null":
                    ano = cols[1].get_text(strip=True) if len(cols) > 1 else ""
                    data = cols[2].get_text(strip=True) if len(cols) > 2 else ""
                    try:
                        dt = datetime.strptime(data, "%d/%m/%Y").strftime("%Y-%m-%d")
                    except:
                        dt = None
                    emps.append({
                        "nr_empenho": nr,
                        "ano": int(ano) if ano.isdigit() else None,
                        "dt_empenho": dt
                    })
    
    return itens, forns, emps

# ─── Gravação no Supabase ─────────────────────────────────────────────────────
def gravar(lic_id, itens, forns, emps):
    """Grava itens, fornecedores e empenhos no Supabase."""
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
                    "tipo": tipo_forn(forn["razao_social"])
                },
                on_conflict="cpf_cnpj"
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
                    on_conflict="licitacao_id,fornecedor_id"
                ).execute()
                n_f += 1
        except Exception as e:
            if DEBUG:
                print(f"      [!] Erro fornecedor: {e}")
    
    # Empenhos (associa ao primeiro item)
    if emps and itens:
        try:
            r = sb.table("itens_licitacao").select("id").eq(
                "licitacao_id", lic_id
            ).limit(1).execute()
            if r.data:
                for emp in emps:
                    emp["item_id"] = r.data[0]["id"]
                    sb.table("empenhos").insert(emp).execute()
        except:
            pass
    
    return n_i, n_f

# ─── Funções de navegação no portal ───────────────────────────────────────────
def preencher_data(page, campo_id, valor):
    """Preenche campo de data usando triple-click + type (método confirmado)."""
    campo = page.locator(f"#{campo_id}")
    campo.click(click_count=3)  # Seleciona todo o texto
    time.sleep(0.2)
    page.keyboard.type(valor, delay=50)
    time.sleep(0.3)
    # Tab para disparar evento onchange do JSF
    page.keyboard.press("Tab")
    time.sleep(0.5)

def fazer_pesquisa(page, usar_datas=True):
    """Executa pesquisa no portal."""
    # Selecionar órgão
    print("    Selecionando órgão SMSAN/FAAC...")
    orgao_select = page.locator("select[id*='j_id9'], select[id*='orgao']")
    if orgao_select.count() > 0:
        orgao_select.first.select_option(label=ORGAO)
        time.sleep(1)
    
    if usar_datas:
        print(f"    Preenchendo datas: {DT_INICIO} → {DT_FIM}")
        preencher_data(page, "form:dataInferiorInputDate", DT_INICIO)
        preencher_data(page, "form:j_id18InputDate", DT_FIM)
    else:
        print("    Pesquisando SEM filtro de datas (diagnóstico)...")
    
    # Clicar em Pesquisar
    print("    Clicando em Pesquisar...")
    btn = page.locator("#form\\:btSearch, input[value='Pesquisar']")
    btn.click()
    time.sleep(3)
    
    # Aguardar carregamento
    page.wait_for_load_state("networkidle", timeout=30000)
    time.sleep(1)
    
    # Extrair total de registros
    html = page.content()
    m = re.search(r'\b(\d+)\s+quantidade\s+registros\b', html, re.I)
    if not m:
        m = re.search(r'quantidade\s+registros[:\s]*(\d+)', html, re.I)
    if not m:
        m = re.search(r'(\d+)\s+registros', html, re.I)
    
    total = int(m.group(1)) if m else 0
    print(f"    Total de registros: {total}")
    return total

def extrair_processos_pagina(page):
    """Extrai lista de processos da página atual."""
    html = page.content()
    soup = BeautifulSoup(html, "lxml")
    processos = []
    
    # Procura tabela com processos
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            # Procura link com onclick contendo id e situacao
            for a in tr.find_all("a", onclick=True):
                onclick = a.get("onclick", "")
                m = re.search(r"id=(\d+).*?situacao=([^&'\"]+)", onclick)
                if m:
                    proc_id = m.group(1)
                    situacao = m.group(2)
                    texto = a.get_text(strip=True)
                    processos.append({
                        "portal_id": proc_id,
                        "situacao": situacao,
                        "texto": texto,
                        "onclick": onclick
                    })
    
    return processos

def ir_para_pagina(page, num_pagina):
    """Navega para uma página específica via datascroller."""
    try:
        # RichFaces datascroller usa td com classe rich-datascr-inact
        paginas = page.locator("td.rich-datascr-inact")
        
        for i in range(paginas.count()):
            elem = paginas.nth(i)
            if elem.text_content().strip() == str(num_pagina):
                elem.click()
                time.sleep(2)
                page.wait_for_load_state("networkidle", timeout=15000)
                return True
        
        return False
    except Exception as e:
        if DEBUG:
            print(f"      [!] Erro navegação: {e}")
        return False

def abrir_detalhe(page, processo):
    """Abre a página de detalhe de um processo."""
    try:
        # Usa o onclick original
        onclick = processo.get("onclick", "")
        if onclick:
            # Procura o link e clica
            links = page.locator(f"a[onclick*=\"id={processo['portal_id']}\"]")
            if links.count() > 0:
                links.first.click()
                time.sleep(2)
                page.wait_for_load_state("networkidle", timeout=30000)
                return True
        return False
    except Exception as e:
        if DEBUG:
            print(f"      [!] Erro ao abrir detalhe: {e}")
        return False

def voltar_para_lista(page):
    """Volta para a lista de licitações."""
    try:
        link = page.locator("a:has-text('Lista Licitações')")
        if link.count() > 0:
            link.first.click()
            time.sleep(2)
            page.wait_for_load_state("networkidle", timeout=15000)
            return True
        return False
    except:
        return False

# ─── Carregar licitações do banco ─────────────────────────────────────────────
def carregar_licitacoes():
    """Carrega licitações do Supabase e identifica pendentes."""
    # Todas as licitações
    r = sb.table("licitacoes").select("id, processo, situacao, tipo_processo").limit(2000).execute()
    todas = {x["id"]: x for x in r.data}
    
    # IDs que já têm itens
    r_itens = sb.table("itens_licitacao").select("licitacao_id").execute()
    ids_com_itens = set(x["licitacao_id"] for x in r_itens.data if x.get("licitacao_id"))
    
    # Criar índice por processo (ex: "DS 70/2019 - SMSAN/FAAC" → id)
    indice = {}
    for lic in todas.values():
        proc = lic.get("processo", "")
        if proc:
            indice[proc] = lic["id"]
            # Também indexa versão simplificada (ex: "DS 70/2019")
            m = re.match(r'^([A-Z]{2}\s+\d+/\d{4})', proc)
            if m:
                indice[m.group(1)] = lic["id"]
    
    return todas, ids_com_itens, indice

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    global INTERROMPIDO
    
    print("=" * 60)
    print("AgroIA-RMC — Coleta de Itens de Licitações (v6)")
    print(f"Início: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 60)
    
    # Carregar dados do banco
    print("[0] Carregando licitações do Supabase...")
    todas, ids_com_itens, indice = carregar_licitacoes()
    pendentes = len(todas) - len(ids_com_itens)
    print(f"    {len(todas)} licitações no banco")
    print(f"    {len(ids_com_itens)} já têm itens coletados")
    print(f"    {pendentes} pendentes de coleta")
    
    # Estatísticas
    stats = {
        "processados": 0,
        "itens": 0,
        "fornecedores": 0,
        "pulados": 0,
        "erros": 0,
        "nao_encontrados": 0
    }
    
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
        # Primeiro: pesquisa SEM data para ver total real
        total_sem_data = fazer_pesquisa(page, usar_datas=False)
        
        # Recarrega página e faz pesquisa COM datas
        page.goto(PORTAL_URL, timeout=60000)
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        total_com_data = fazer_pesquisa(page, usar_datas=True)
        
        if total_com_data == 0:
            print("\n[!] PROBLEMA: Nenhum registro retornado com filtro de datas!")
            print("    Verifique se os campos de data estão sendo preenchidos corretamente.")
            print(f"    Total SEM data: {total_sem_data}")
            print(f"    Total COM data: {total_com_data}")
            browser.close()
            return
        
        total_pags = math.ceil(total_com_data / REGS_POR_PAG)
        
        print(f"\n[4] Iniciando coleta ({total_com_data} registros em {total_pags} páginas)...")
        
        pag_atual = 1
        while pag_atual <= total_pags and not INTERROMPIDO:
            print(f"\n--- Página {pag_atual}/{total_pags} ---")
            
            # Extrair processos da página
            processos = extrair_processos_pagina(page)
            print(f"    {len(processos)} processos encontrados na página")
            
            for proc in processos:
                if INTERROMPIDO:
                    break
                
                texto = proc.get("texto", "")
                portal_id = proc.get("portal_id", "")
                
                # Tentar encontrar no banco
                lic_id = None
                for chave in [texto, texto.split(" - ")[0] if " - " in texto else texto]:
                    if chave in indice:
                        lic_id = indice[chave]
                        break
                
                if not lic_id:
                    if DEBUG:
                        print(f"    [?] Não encontrado no banco: {texto}")
                    stats["nao_encontrados"] += 1
                    continue
                
                # Verificar se já tem itens
                if lic_id in ids_com_itens:
                    print(f"    [=] Já coletado: {texto}")
                    stats["pulados"] += 1
                    continue
                
                print(f"    [>] Processando: {texto} (ID={lic_id})")
                
                # Abrir detalhe
                if not abrir_detalhe(page, proc):
                    print(f"        [!] Falha ao abrir detalhe")
                    stats["erros"] += 1
                    continue
                
                # Extrair dados
                html = page.content()
                itens, forns, emps = extrair_dados_detalhe(html)
                
                if itens:
                    n_i, n_f = gravar(lic_id, itens, forns, emps)
                    stats["itens"] += n_i
                    stats["fornecedores"] += n_f
                    stats["processados"] += 1
                    ids_com_itens.add(lic_id)  # Marca como coletado
                    print(f"        ✓ {n_i} itens, {n_f} fornecedores")
                else:
                    print(f"        [!] Nenhum item encontrado")
                    stats["erros"] += 1
                
                # Voltar para lista
                if not voltar_para_lista(page):
                    # Refaz pesquisa se não conseguir voltar
                    page.goto(PORTAL_URL, timeout=60000)
                    page.wait_for_load_state("networkidle")
                    fazer_pesquisa(page, usar_datas=True)
                    # Navegar para página atual
                    for p_nav in range(2, pag_atual + 1):
                        ir_para_pagina(page, p_nav)
                
                time.sleep(DELAY)
            
            # Próxima página
            if pag_atual < total_pags and not INTERROMPIDO:
                if not ir_para_pagina(page, pag_atual + 1):
                    print(f"    [!] Não conseguiu navegar para página {pag_atual + 1}")
                    # Tenta refazer pesquisa e navegar
                    page.goto(PORTAL_URL, timeout=60000)
                    page.wait_for_load_state("networkidle")
                    fazer_pesquisa(page, usar_datas=True)
                    for p_nav in range(2, pag_atual + 2):
                        if not ir_para_pagina(page, p_nav):
                            break
            
            pag_atual += 1
        
        browser.close()
    
    # Relatório final
    inicio = datetime.now()
    print("\n" + "=" * 60)
    print("CONCLUÍDO!")
    print("=" * 60)
    print(f"  Processados:     {stats['processados']}")
    print(f"  Itens:           {stats['itens']}")
    print(f"  Fornecedores:    {stats['fornecedores']}")
    print(f"  Pulados:         {stats['pulados']}")
    print(f"  Não encontrados: {stats['nao_encontrados']}")
    print(f"  Erros:           {stats['erros']}")
    print(f"  Pendentes:       {pendentes - stats['processados']}")
    if INTERROMPIDO:
        print("  (Interrompido pelo usuário - rode novamente para continuar)")
    print("=" * 60)

if __name__ == "__main__":
    main()
