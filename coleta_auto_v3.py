"""
AgroIA-RMC — Coleta Automática V3 (Paginação Corrigida)
=======================================================
Execute: python coleta_auto_v3.py
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
DT_FIM = "31/12/2025"

interrompido = False

def handler_interrupcao(sig, frame):
    global interrompido
    print("\n\n⚠️  Interrupção solicitada...")
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
    """Preenche filtros usando JavaScript."""
    print("[2] Preenchendo filtros...")
    
    page.evaluate(f"""
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
    """)
    print(f"    Órgão: {ORGAO}")
    time.sleep(1)
    
    page.evaluate(f"""
        var inputs = document.querySelectorAll('input[type="text"]');
        for (var inp of inputs) {{
            if (inp.id && inp.id.includes('dataInferior') && inp.id.includes('Input')) {{
                inp.value = '{DT_INICIO}';
                inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}
            if (inp.id && inp.id.includes('j_id18') && inp.id.includes('Input')) {{
                inp.value = '{DT_FIM}';
                inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}
        }}
    """)
    print(f"    Período: {DT_INICIO} a {DT_FIM}")
    time.sleep(1)
    
    btn = page.query_selector("input[value='Pesquisar']")
    if btn:
        btn.click()
        print("    Pesquisando...")
        page.wait_for_timeout(5000)
        
        texto = page.inner_text("body")
        match = re.search(r'quantidade registros[:\s]*(\d+)', texto, re.I)
        if match:
            total = int(match.group(1))
            print(f"    ✓ Encontrados: {total} registros")
            return total
    
    return 0

def ir_para_proxima_pagina(page, pagina_atual):
    """Navega para a próxima página usando diferentes métodos."""
    
    # Método 1: Clicar no número da próxima página
    prox_num = str(pagina_atual + 1)
    try:
        # Buscar link com o número da próxima página
        link_pagina = page.query_selector(f"a:has-text('{prox_num}')")
        if link_pagina:
            # Verificar se é um link de paginação (não um link de licitação)
            parent_class = link_pagina.evaluate("el => el.parentElement ? el.parentElement.className : ''")
            if "datascr" in parent_class.lower() or "scroller" in parent_class.lower():
                link_pagina.click()
                page.wait_for_timeout(2500)
                return True
    except:
        pass
    
    # Método 2: Clicar no botão ">"
    try:
        # Buscar todos os elementos que podem ser botões de paginação
        elementos = page.query_selector_all("td.rich-datascr-button, a.rich-datascr-button, span.rich-datascr-button")
        for el in elementos:
            texto = el.inner_text().strip()
            if texto == ">":
                el.click()
                page.wait_for_timeout(2500)
                return True
    except:
        pass
    
    # Método 3: Usar JavaScript para clicar no botão de próxima página
    try:
        result = page.evaluate("""
            // Buscar botões de paginação
            var btns = document.querySelectorAll('td.rich-datascr-button, .rich-datascr-act');
            for (var btn of btns) {
                if (btn.textContent.trim() === '>') {
                    btn.click();
                    return true;
                }
            }
            
            // Tentar pelo onclick
            var allTds = document.querySelectorAll('td[onclick*="j_id52"]');
            for (var td of allTds) {
                if (td.textContent.trim() === '>') {
                    td.click();
                    return true;
                }
            }
            
            return false;
        """)
        if result:
            page.wait_for_timeout(2500)
            return True
    except:
        pass
    
    # Método 4: Buscar qualquer elemento clicável com ">"
    try:
        next_btn = page.locator("text='>'").first
        if next_btn:
            next_btn.click()
            page.wait_for_timeout(2500)
            return True
    except:
        pass
    
    return False

def processar_licitacao(page, sb, lic_id):
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
        aba = page.query_selector("td.rich-tab-header:has-text('Lista Licitações')")
        if aba:
            aba.click()
            page.wait_for_timeout(2000)
            return True
    except:
        pass
    
    try:
        page.evaluate("""
            var tabs = document.querySelectorAll('td.rich-tab-header');
            for (var tab of tabs) {
                if (tab.textContent.includes('Lista')) {
                    tab.click();
                    return true;
                }
            }
        """)
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
    print("AgroIA-RMC — COLETA AUTOMÁTICA V3")
    print("=" * 60)
    
    print("\n[1] Carregando licitações...")
    dados = sb.table("licitacoes").select("id,processo").eq("orgao", ORGAO).execute().data
    mapa = {d["processo"]: d["id"] for d in dados}
    print(f"    {len(mapa)} licitações no banco")
    
    r = sb.table("itens_licitacao").select("licitacao_id,codigo").execute()
    coletados = set()
    for item in r.data:
        if item.get("codigo") and item["codigo"].isdigit():
            coletados.add(item["licitacao_id"])
    
    pendentes = [p for p, lid in mapa.items() if lid not in coletados]
    print(f"    {len(coletados)} já coletadas | {len(pendentes)} pendentes")
    
    if not pendentes:
        print("\n✓ Todas já coletadas!")
        return
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)
        page = browser.new_page()
        page.set_default_timeout(60000)
        
        print("\n[2] Acessando portal...")
        page.goto(FORM_URL, timeout=60000)
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        total_registros = preencher_filtros(page)
        
        if total_registros == 0:
            print("\n    Falha ao pesquisar. Abortando.")
            browser.close()
            return
        
        # Estatísticas
        total_itens = 0
        total_empenhos = 0
        processados = 0
        sem_itens = 0
        erros = 0
        pagina = 1
        max_paginas = (total_registros // 5) + 1
        
        print(f"\n[3] Coletando ({max_paginas} páginas, Ctrl+C para parar)...\n")
        
        while not interrompido and pagina <= max_paginas:
            links = page.query_selector_all("a[id*='tabela'][id*='j_id26']")
            
            if not links:
                print(f"    Página {pagina}: sem links, tentando recarregar...")
                page.wait_for_timeout(2000)
                links = page.query_selector_all("a[id*='tabela'][id*='j_id26']")
                if not links:
                    break
            
            # Coletar textos dos processos na página atual
            processos_pagina = []
            for link in links:
                try:
                    txt = link.inner_text().strip()
                    processos_pagina.append(txt)
                except:
                    pass
            
            pendentes_pagina = [p for p in processos_pagina if p in pendentes]
            
            print(f"--- Página {pagina}/{max_paginas} | {len(pendentes_pagina)} pendentes ---")
            
            for proc in pendentes_pagina:
                if interrompido:
                    break
                
                lic_id = mapa.get(proc)
                if not lic_id:
                    continue
                
                try:
                    # Re-buscar link
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
                    
                    n_i, n_e = processar_licitacao(page, sb, lic_id)
                    
                    if n_i > 0:
                        total_itens += n_i
                        total_empenhos += n_e
                        processados += 1
                        pendentes.remove(proc)
                        print(f"  [{processados:4}] {proc} | itens:{n_i} emp:{n_e}")
                    else:
                        sem_itens += 1
                    
                    voltar_para_lista(page)
                
                except Exception as e:
                    erros += 1
                    print(f"  [ERRO] {proc}: {str(e)[:30]}")
                    voltar_para_lista(page)
            
            if interrompido:
                break
            
            # Próxima página
            if pagina < max_paginas:
                if ir_para_proxima_pagina(page, pagina):
                    pagina += 1
                else:
                    print(f"\n    Não conseguiu ir para página {pagina + 1}")
                    break
            else:
                break
        
        browser.close()
    
    print(f"\n{'='*60}")
    print(f"RESUMO")
    print(f"{'='*60}")
    print(f"  Processadas: {processados}")
    print(f"  Itens:       {total_itens}")
    print(f"  Empenhos:    {total_empenhos}")
    print(f"  Sem itens:   {sem_itens}")
    print(f"  Erros:       {erros}")
    print(f"  Pendentes:   {len(pendentes)}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
