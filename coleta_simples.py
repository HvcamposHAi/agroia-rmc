"""
AgroIA-RMC — Coleta SIMPLES
===========================
Versão simplificada: processa todas as licitações de cada página antes de avançar.

Execute: python coleta_simples.py
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
DT_FIM = "31/12/2026"

interrompido = False

def handler_interrupcao(sig, frame):
    global interrompido
    print("\n\n⚠️  Interrupção solicitada...")
    interrompido = True

signal.signal(signal.SIGINT, handler_interrupcao)

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

def extrair_itens(texto):
    itens = []
    linhas = texto.split("\n")
    
    inicio = -1
    for i, linha in enumerate(linhas):
        if linha.strip() == "páginas":
            inicio = i + 1
            break
    
    if inicio == -1:
        return itens
    
    for i in range(inicio, len(linhas)):
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
            desc = match.group(3).strip().rstrip(",")
            qt = parse_val(match.group(4))
            un = match.group(5)
            valor = parse_val(match.group(6))
            cultura = norm_cultura(desc)
            
            itens.append({
                "seq": seq,
                "codigo": codigo,
                "descricao": desc,
                "qt_solicitada": qt,
                "unidade_medida": un,
                "valor_unitario": valor,
                "valor_total": qt * valor,
                "cultura": cultura,
                "categoria": categ(cultura),
            })
    
    return itens

def extrair_empenhos(texto):
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

def gravar_itens(sb, lic_id, itens):
    n = 0
    for item in itens:
        item["licitacao_id"] = lic_id
        try:
            sb.table("itens_licitacao").upsert(item, on_conflict="licitacao_id,seq").execute()
            n += 1
        except:
            pass
    return n

def gravar_empenhos(sb, lic_id, empenhos):
    if not empenhos:
        return 0
    
    # Buscar primeiro item
    r = sb.table("itens_licitacao").select("id").eq("licitacao_id", lic_id).order("seq").limit(1).execute()
    if not r.data:
        return 0
    
    item_id = r.data[0]["id"]
    n = 0
    
    for emp in empenhos:
        emp["item_id"] = item_id
        emp["coletado_em"] = datetime.now().isoformat()
        try:
            sb.table("empenhos").upsert(emp, on_conflict="item_id,nr_empenho,ano").execute()
            n += 1
        except:
            pass
    
    return n

def main():
    global interrompido
    
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    print("=" * 60)
    print("AgroIA-RMC — COLETA SIMPLES")
    print("=" * 60)
    
    # Carregar mapa de licitações
    print("\n[1] Carregando licitações...")
    dados = sb.table("licitacoes").select("id,processo").eq("orgao", ORGAO).execute().data
    mapa = {d["processo"]: d["id"] for d in dados}
    print(f"    {len(mapa)} no banco")
    
    # Verificar já coletadas
    r = sb.table("itens_licitacao").select("licitacao_id,codigo").execute()
    coletados = set()
    for item in r.data:
        if item.get("codigo") and item["codigo"].isdigit():
            coletados.add(item["licitacao_id"])
    
    pendentes = set(p for p, lid in mapa.items() if lid not in coletados)
    print(f"    {len(coletados)} coletadas | {len(pendentes)} pendentes")
    
    if not pendentes:
        print("\n✓ Tudo coletado!")
        return
    
    # Estatísticas
    stats = {"proc": 0, "itens": 0, "emp": 0, "sem": 0, "err": 0}
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=200)
        page = browser.new_page()
        page.set_default_timeout(60000)
        
        print("\n[2] Acessando portal...")
        page.goto(FORM_URL, timeout=60000)
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        # Preencher filtros
        print(f"[3] Filtros: {ORGAO} | {DT_INICIO} a {DT_FIM}")
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
        
        page.click("input[value='Pesquisar']")
        page.wait_for_timeout(4000)
        
        texto = page.inner_text("body")
        match = re.search(r'quantidade registros[:\s]*(\d+)', texto, re.I)
        total = int(match.group(1)) if match else 0
        print(f"    ✓ {total} registros")
        
        print(f"\n[4] Coletando (Ctrl+C para parar)...\n")
        
        pagina = 1
        
        while not interrompido:
            # Obter processos da página atual
            links = page.query_selector_all("a[id*='tabela'][id*='j_id26']")
            if not links:
                print("    Sem links na página")
                break
            
            processos_pagina = [l.inner_text().strip() for l in links]
            pendentes_pagina = [p for p in processos_pagina if p in pendentes]
            
            print(f"--- Pág {pagina} | {len(pendentes_pagina)}/{len(processos_pagina)} pendentes ---")
            
            # Processar cada licitação pendente DESTA página
            for idx, proc in enumerate(pendentes_pagina):
                if interrompido:
                    break
                
                lic_id = mapa.get(proc)
                if not lic_id:
                    continue
                
                try:
                    # Encontrar link (re-buscar porque pode ter mudado)
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
                        print(f"    Link não encontrado: {proc}")
                        continue
                    
                    # Clicar no link
                    link_alvo.click()
                    page.wait_for_timeout(3000)
                    
                    # Extrair dados
                    texto = page.inner_text("body")
                    itens = extrair_itens(texto)
                    
                    if itens:
                        n_i = gravar_itens(sb, lic_id, itens)
                        n_e = gravar_empenhos(sb, lic_id, extrair_empenhos(texto))
                        
                        stats["proc"] += 1
                        stats["itens"] += n_i
                        stats["emp"] += n_e
                        pendentes.discard(proc)
                        
                        print(f"  [{stats['proc']:4}] {proc} | {n_i} itens, {n_e} emp")
                    else:
                        stats["sem"] += 1
                    
                    # Voltar para lista
                    btn = page.query_selector("input[value='Página Inicial']")
                    if btn:
                        btn.click()
                        page.wait_for_timeout(2000)
                    else:
                        page.go_back()
                        page.wait_for_timeout(2000)
                
                except Exception as e:
                    stats["err"] += 1
                    print(f"  [ERRO] {proc}: {str(e)[:30]}")
                    # Tentar voltar
                    try:
                        page.query_selector("input[value='Página Inicial']").click()
                        page.wait_for_timeout(2000)
                    except:
                        page.go_back()
                        page.wait_for_timeout(2000)
            
            if interrompido:
                break
            
            # Avançar para próxima página
            pag_atual = 1
            try:
                atual = page.query_selector("td.rich-datascr-act")
                if atual:
                    pag_atual = int(atual.inner_text().strip())
            except:
                pass
            
            # Clicar na próxima página
            avancou = False
            tds = page.query_selector_all("td.rich-datascr-inact")
            for td in tds:
                try:
                    num = td.inner_text().strip()
                    if num.isdigit() and int(num) == pag_atual + 1:
                        td.click()
                        page.wait_for_timeout(2500)
                        avancou = True
                        break
                except:
                    pass
            
            if not avancou:
                # Tentar botão >
                btns = page.query_selector_all("td.rich-datascr-button")
                for btn in btns:
                    try:
                        onclick = btn.get_attribute("onclick") or ""
                        if "onscroll" in onclick:
                            btn.click()
                            page.wait_for_timeout(2500)
                            avancou = True
                            break
                    except:
                        pass
            
            if not avancou:
                print("\n    Fim das páginas.")
                break
            
            pagina += 1
        
        browser.close()
    
    print(f"\n{'='*60}")
    print("RESUMO")
    print(f"{'='*60}")
    print(f"  Processadas: {stats['proc']}")
    print(f"  Itens:       {stats['itens']}")
    print(f"  Empenhos:    {stats['emp']}")
    print(f"  Sem itens:   {stats['sem']}")
    print(f"  Erros:       {stats['err']}")
    print(f"  Pendentes:   {len(pendentes)}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
