"""
AgroIA-RMC — Coleta FINAL (filtro até 2026)
===========================================
Execute: python coleta_final.py
"""
import os
import re
import time
import signal
from datetime import datetime
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

FORM_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
ORGAO = "SMSAN/FAAC"
DT_INICIO = "01/01/2019"
DT_FIM = "31/12/2026"  # CORRIGIDO: incluir 2026

interrompido = False

def handler_interrupcao(sig, frame):
    global interrompido
    print("\n\n⚠️  Interrupção solicitada. Finalizando...")
    interrompido = True

signal.signal(signal.SIGINT, handler_interrupcao)

# ── Funções auxiliares ────────────────────────────────────────────────────────

def parse_val(t):
    try:
        return float((t or "0").strip().replace(".", "").replace(",", "."))
    except:
        return 0.0

def norm_cultura(desc):
    mapa = {
        "leite": "leite", "banana": "banana", "laranja": "laranja", 
        "maçã": "maca", "mamão": "mamao", "melancia": "melancia", 
        "uva": "uva", "morango": "morango", "tomate": "tomate", 
        "cebola": "cebola", "cenoura": "cenoura", "batata": "batata", 
        "aipim": "aipim", "mandioca": "aipim", "alface": "alface", 
        "couve": "couve", "repolho": "repolho", "brócolis": "brocolis",
        "alho": "alho", "beterraba": "beterraba", "pimentão": "pimentao",
        "abobrinha": "abobrinha", "chuchu": "chuchu", "pepino": "pepino",
        "arroz": "arroz", "feijão": "feijao", "feijao": "feijao",
        "milho": "milho", "queijo": "queijo", "ovos": "ovos", "ovo": "ovos",
        "frango": "frango", "carne": "carne", "pão": "pao", "mel": "mel",
        "abacaxi": "abacaxi", "goiaba": "goiaba", "limão": "limao",
        "manga": "manga", "maracujá": "maracuja", "abóbora": "abobora",
        "farinha": "farinha", "açúcar": "acucar", "café": "cafe",
    }
    desc_lower = (desc or "").lower().strip()
    for k, v in mapa.items():
        if k in desc_lower:
            return v
    palavras = re.findall(r'[a-záéíóúâêîôûãõç]+', desc_lower)
    return palavras[0] if palavras else "outro"

def categ(cultura):
    frutas = {"abacaxi", "banana", "goiaba", "laranja", "limao", "maca", 
              "mamao", "melancia", "uva", "morango", "manga", "maracuja"}
    legumes = {"tomate", "cebola", "cenoura", "batata", "aipim", "alho", 
               "beterraba", "pimentao", "abobrinha", "chuchu", "pepino",
               "milho", "abobora"}
    folhosas = {"alface", "couve", "repolho", "brocolis"}
    laticinios = {"queijo", "leite"}
    proteinas = {"frango", "carne", "ovos"}
    graos = {"arroz", "feijao", "farinha", "cafe", "acucar"}
    
    if cultura in frutas: return "FRUTA"
    if cultura in legumes: return "LEGUME"
    if cultura in folhosas: return "FOLHOSA"
    if cultura in laticinios: return "LATICINIOS"
    if cultura in proteinas: return "PROTEINA"
    if cultura in graos: return "GRAOS"
    return "OUTRO"

# ── Extração ──────────────────────────────────────────────────────────────────

def extrair_itens_do_texto(texto):
    itens = []
    linhas = texto.split("\n")
    
    inicio_dados = -1
    for i, linha in enumerate(linhas):
        if linha.strip() == "páginas":
            inicio_dados = i + 1
            break
    
    if inicio_dados == -1:
        return itens
    
    for i in range(inicio_dados, len(linhas)):
        linha = linhas[i].strip()
        if not linha:
            continue
        if linha.startswith("Fornecedores") or linha.startswith("Documentos") or linha.startswith("Empenhos"):
            break
        
        match = re.match(
            r'^(\d+)\s+(\d+)\s+(.+?)\s+([\d.]+,\d{2})\s+(\S+)\s+([\d.]+,\d{4})\s+Empenhos',
            linha
        )
        
        if match:
            seq = int(match.group(1))
            codigo = match.group(2)
            descricao = match.group(3).strip().rstrip(",")
            qt = parse_val(match.group(4))
            un = match.group(5)
            valor = parse_val(match.group(6))
            cultura = norm_cultura(descricao)
            
            itens.append({
                "seq": seq,
                "codigo": codigo,
                "descricao": descricao,
                "qt_solicitada": qt,
                "unidade_medida": un,
                "valor_unitario": valor,
                "valor_total": qt * valor,
                "cultura": cultura,
                "categoria": categ(cultura),
            })
    
    return itens

def extrair_empenhos_do_texto(texto):
    empenhos = []
    matches = re.findall(r'(\d{1,8})\s+(\d{4})\s+(\d{2}/\d{2}/\d{4})', texto)
    
    for nr, ano, data in matches:
        dt = None
        try:
            dt = datetime.strptime(data, "%d/%m/%Y").strftime("%Y-%m-%d")
        except:
            pass
        empenhos.append({"nr_empenho": nr, "ano": int(ano), "dt_empenho": dt})
    
    return empenhos

# ── Gravação ──────────────────────────────────────────────────────────────────

def gravar_item(sb, lic_id, item):
    item["licitacao_id"] = lic_id
    try:
        r = sb.table("itens_licitacao").upsert(item, on_conflict="licitacao_id,seq").execute()
        if r.data:
            return r.data[0].get("id")
        r2 = sb.table("itens_licitacao").select("id").eq("licitacao_id", lic_id).eq("seq", item["seq"]).execute()
        if r2.data:
            return r2.data[0]["id"]
    except:
        pass
    return None

def gravar_empenhos(sb, item_id, empenhos):
    n = 0
    for emp in empenhos:
        emp["item_id"] = item_id
        emp["coletado_em"] = datetime.now().isoformat()
        try:
            sb.table("empenhos").upsert(emp, on_conflict="item_id,nr_empenho,ano").execute()
            n += 1
        except:
            try:
                sb.table("empenhos").insert(emp).execute()
                n += 1
            except:
                pass
    return n

# ── Navegação ─────────────────────────────────────────────────────────────────

def preencher_filtros(page):
    page.evaluate(f"""() => {{
        var selects = document.querySelectorAll('select');
        for (var s of selects) {{
            for (var opt of s.options) {{
                if (opt.text.includes('{ORGAO}')) {{
                    s.value = opt.value;
                    s.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    break;
                }}
            }}
        }}
        var inputs = document.querySelectorAll('input[type="text"]');
        for (var inp of inputs) {{
            if (inp.id && inp.id.includes('dataInferior') && inp.id.includes('Input')) {{
                inp.value = '{DT_INICIO}';
            }}
            if (inp.id && inp.id.includes('j_id18') && inp.id.includes('Input')) {{
                inp.value = '{DT_FIM}';
            }}
        }}
    }}""")
    time.sleep(1)
    
    btn = page.query_selector("input[value='Pesquisar']")
    if btn:
        btn.click()
        page.wait_for_timeout(4000)
        return True
    return False

def get_pagina_atual(page):
    """Retorna o número da página atual."""
    try:
        atual = page.query_selector("td.rich-datascr-act")
        if atual:
            return int(atual.inner_text().strip())
    except:
        pass
    return 1

def ir_para_proxima_pagina(page):
    """Vai para a próxima página. Retorna True se conseguiu."""
    try:
        pag_atual = get_pagina_atual(page)
        prox = pag_atual + 1
        
        # Tentar clicar no número da próxima página
        tds = page.query_selector_all("td.rich-datascr-inact")
        for td in tds:
            try:
                num = td.inner_text().strip()
                if num.isdigit() and int(num) == prox:
                    td.click()
                    page.wait_for_timeout(2500)
                    return get_pagina_atual(page) == prox
            except:
                continue
        
        # Tentar botão >
        btns = page.query_selector_all("td.rich-datascr-button")
        for btn in btns:
            try:
                onclick = btn.get_attribute("onclick") or ""
                if "onscroll" in onclick:
                    btn.click()
                    page.wait_for_timeout(2500)
                    return get_pagina_atual(page) > pag_atual
            except:
                continue
    except:
        pass
    
    return False

def processar_licitacao(page, sb, lic_id, proc):
    """Processa uma licitação e retorna (n_itens, n_empenhos)."""
    texto = page.inner_text("body")
    itens = extrair_itens_do_texto(texto)
    
    if not itens:
        return 0, 0
    
    total_itens = 0
    total_empenhos = 0
    
    for item in itens:
        item_id = gravar_item(sb, lic_id, item)
        if item_id:
            total_itens += 1
    
    empenhos = extrair_empenhos_do_texto(texto)
    if empenhos and total_itens > 0:
        r = sb.table("itens_licitacao").select("id").eq("licitacao_id", lic_id).order("seq").limit(1).execute()
        if r.data:
            total_empenhos = gravar_empenhos(sb, r.data[0]["id"], empenhos)
    
    return total_itens, total_empenhos

def voltar_para_lista(page):
    """Volta para a lista de licitações."""
    try:
        btn = page.query_selector("input[value='Página Inicial']")
        if btn:
            btn.click()
            page.wait_for_timeout(2000)
            return True
    except:
        pass
    
    try:
        page.evaluate("""() => {
            var tabs = document.querySelectorAll('td[class*="tab"]');
            for (var tab of tabs) {
                if (tab.textContent.includes('Lista')) {
                    tab.click();
                    return;
                }
            }
        }""")
        page.wait_for_timeout(2000)
        return True
    except:
        pass
    
    return False

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    global interrompido
    
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    print("=" * 60)
    print("AgroIA-RMC — COLETA FINAL")
    print(f"Filtro: {ORGAO} | {DT_INICIO} a {DT_FIM}")
    print("=" * 60)
    
    # Carregar licitações do banco
    print("\n[1] Carregando licitações do banco...")
    dados = sb.table("licitacoes").select("id,processo").eq("orgao", ORGAO).execute().data
    mapa = {d["processo"]: d["id"] for d in dados}
    print(f"    {len(mapa)} licitações")
    
    # Verificar já coletadas
    r = sb.table("itens_licitacao").select("licitacao_id,codigo").execute()
    coletados = set()
    for item in r.data:
        if item.get("codigo") and item["codigo"].isdigit():
            coletados.add(item["licitacao_id"])
    
    pendentes_ids = set(lid for lid in mapa.values() if lid not in coletados)
    pendentes_procs = set(p for p, lid in mapa.items() if lid in pendentes_ids)
    
    print(f"    {len(coletados)} já coletadas | {len(pendentes_procs)} pendentes")
    
    if not pendentes_procs:
        print("\n✓ Todas as licitações já foram coletadas!")
        return
    
    # Iniciar navegação
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=150)
        page = browser.new_page()
        page.set_default_timeout(60000)
        
        print("\n[2] Acessando portal...")
        page.goto(FORM_URL, timeout=60000)
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        print(f"[3] Preenchendo filtros ({DT_INICIO} a {DT_FIM})...")
        preencher_filtros(page)
        
        texto = page.inner_text("body")
        match = re.search(r'quantidade registros[:\s]*(\d+)', texto, re.I)
        total_registros = int(match.group(1)) if match else 0
        max_paginas = (total_registros // 5) + 1
        print(f"    ✓ {total_registros} registros ({max_paginas} páginas)")
        
        if total_registros == 0:
            print("    Nenhum registro encontrado. Abortando.")
            browser.close()
            return
        
        # Estatísticas
        stats = {"processadas": 0, "itens": 0, "empenhos": 0, "sem_itens": 0, "erros": 0}
        
        print(f"\n[4] Coletando (Ctrl+C para parar)...\n")
        
        pagina = 1
        tentativas_pagina = 0
        
        while not interrompido:
            pag_atual = get_pagina_atual(page)
            
            # Obter links da página
            links = page.query_selector_all("a[id*='tabela'][id*='j_id26']")
            if not links:
                if tentativas_pagina < 3:
                    tentativas_pagina += 1
                    page.wait_for_timeout(2000)
                    continue
                break
            
            tentativas_pagina = 0
            
            # Processos da página
            processos_pagina = []
            for link in links:
                try:
                    proc = link.inner_text().strip()
                    if proc in pendentes_procs:
                        processos_pagina.append(proc)
                except:
                    pass
            
            if processos_pagina:
                print(f"--- Página {pag_atual} | {len(processos_pagina)} pendentes ---")
            
            # Processar cada licitação pendente
            for proc in processos_pagina:
                if interrompido:
                    break
                
                lic_id = mapa.get(proc)
                if not lic_id:
                    continue
                
                try:
                    # Encontrar e clicar no link
                    links = page.query_selector_all("a[id*='tabela'][id*='j_id26']")
                    link_alvo = None
                    for lk in links:
                        try:
                            if lk.inner_text().strip() == proc:
                                link_alvo = lk
                                break
                        except:
                            pass
                    
                    if not link_alvo:
                        continue
                    
                    link_alvo.click()
                    page.wait_for_timeout(2500)
                    
                    # Processar
                    n_i, n_e = processar_licitacao(page, sb, lic_id, proc)
                    
                    if n_i > 0:
                        stats["itens"] += n_i
                        stats["empenhos"] += n_e
                        stats["processadas"] += 1
                        pendentes_procs.discard(proc)
                        print(f"  [{stats['processadas']:4}] {proc} | itens:{n_i} emp:{n_e}")
                    else:
                        stats["sem_itens"] += 1
                    
                    # Voltar para lista
                    voltar_para_lista(page)
                    
                    # Re-navegar para a página correta se necessário
                    if get_pagina_atual(page) != pag_atual:
                        for _ in range(pag_atual - 1):
                            ir_para_proxima_pagina(page)
                
                except Exception as e:
                    stats["erros"] += 1
                    print(f"  [ERRO] {proc}: {str(e)[:40]}")
                    voltar_para_lista(page)
            
            if interrompido:
                break
            
            # Próxima página
            if not ir_para_proxima_pagina(page):
                # Verificar se é realmente o fim
                if get_pagina_atual(page) >= max_paginas:
                    print("\n    Última página alcançada.")
                    break
                
                # Tentar re-pesquisar
                print(f"\n    Erro na paginação. Tentando re-pesquisar...")
                page.goto(FORM_URL, timeout=60000)
                page.wait_for_load_state("networkidle")
                time.sleep(2)
                preencher_filtros(page)
                
                # Navegar até a página onde parou
                for _ in range(pag_atual):
                    ir_para_proxima_pagina(page)
        
        browser.close()
    
    # Resumo
    print(f"\n{'='*60}")
    print(f"RESUMO")
    print(f"{'='*60}")
    print(f"  Processadas: {stats['processadas']}")
    print(f"  Itens:       {stats['itens']}")
    print(f"  Empenhos:    {stats['empenhos']}")
    print(f"  Sem itens:   {stats['sem_itens']}")
    print(f"  Erros:       {stats['erros']}")
    print(f"  Pendentes:   {len(pendentes_procs)}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
