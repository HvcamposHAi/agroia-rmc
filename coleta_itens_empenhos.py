"""
AgroIA-RMC — Coleta Completa: Itens + Empenhos
==============================================
Coleta itens de licitação e seus empenhos vinculados.

Execute: python coleta_itens_empenhos.py
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

# Controle de interrupção
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

# ── Extração de dados ─────────────────────────────────────────────────────────

def extrair_itens_do_texto(texto):
    """Extrai itens do texto da página."""
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
    """Extrai empenhos do texto (seção após clicar em Empenhos)."""
    empenhos = []
    
    # Padrão: número(digits) ano(4 digits) data(DD/MM/YYYY)
    matches = re.findall(r'(\d{1,8})\s+(\d{4})\s+(\d{2}/\d{2}/\d{4})', texto)
    
    for nr, ano, data in matches:
        dt = None
        try:
            dt = datetime.strptime(data, "%d/%m/%Y").strftime("%Y-%m-%d")
        except:
            pass
        
        empenhos.append({
            "nr_empenho": nr,
            "ano": int(ano),
            "dt_empenho": dt,
        })
    
    return empenhos

def extrair_empenhos_tabela(page):
    """Extrai empenhos da tabela visível na página."""
    empenhos = []
    
    # Buscar tabela de empenhos pelo ID
    tabela = page.query_selector("#form\\:tabelaEmpenhosProcCompra, table[id*='Empenho']")
    
    if tabela:
        rows = tabela.query_selector_all("tr")
        for row in rows:
            cells = row.query_selector_all("td")
            if len(cells) >= 3:
                nr = cells[0].inner_text().strip()
                ano = cells[1].inner_text().strip()
                data = cells[2].inner_text().strip()
                
                if nr.isdigit():
                    dt = None
                    try:
                        dt = datetime.strptime(data, "%d/%m/%Y").strftime("%Y-%m-%d")
                    except:
                        pass
                    
                    empenhos.append({
                        "nr_empenho": nr,
                        "ano": int(ano) if ano.isdigit() else None,
                        "dt_empenho": dt,
                    })
    
    # Se não encontrou pela tabela, tenta pelo texto
    if not empenhos:
        texto = page.inner_text("body")
        empenhos = extrair_empenhos_do_texto(texto)
    
    return empenhos

# ── Gravação Supabase ─────────────────────────────────────────────────────────

def gravar_item(sb, lic_id, item):
    """Grava um item e retorna o ID."""
    item["licitacao_id"] = lic_id
    try:
        r = sb.table("itens_licitacao").upsert(item, on_conflict="licitacao_id,seq").execute()
        if r.data:
            return r.data[0].get("id")
        # Buscar ID se não retornou
        r2 = sb.table("itens_licitacao").select("id").eq("licitacao_id", lic_id).eq("seq", item["seq"]).execute()
        if r2.data:
            return r2.data[0]["id"]
    except Exception as e:
        print(f"      Erro gravando item: {e}")
    return None

def gravar_empenhos(sb, item_id, empenhos):
    """Grava empenhos vinculados a um item."""
    n = 0
    for emp in empenhos:
        emp["item_id"] = item_id
        emp["coletado_em"] = datetime.now().isoformat()
        try:
            sb.table("empenhos").upsert(emp, on_conflict="item_id,nr_empenho,ano").execute()
            n += 1
        except:
            # Tenta insert se upsert falhar
            try:
                sb.table("empenhos").insert(emp).execute()
                n += 1
            except:
                pass
    return n

# ── Fluxo principal ───────────────────────────────────────────────────────────

def processar_licitacao(page, sb, lic_id, proc_text):
    """Processa uma licitação: extrai itens e empenhos."""
    
    # Extrair itens do texto da página
    texto = page.inner_text("body")
    itens = extrair_itens_do_texto(texto)
    
    if not itens:
        return 0, 0
    
    total_itens = 0
    total_empenhos = 0
    
    # Gravar cada item
    for item in itens:
        item_id = gravar_item(sb, lic_id, item)
        if item_id:
            total_itens += 1
    
    # Tentar extrair empenhos da página principal (seção Empenhos)
    empenhos_geral = extrair_empenhos_tabela(page)
    
    if empenhos_geral and total_itens > 0:
        # Vincular empenhos ao primeiro item (simplificação)
        # Buscar ID do primeiro item
        r = sb.table("itens_licitacao").select("id").eq("licitacao_id", lic_id).order("seq").limit(1).execute()
        if r.data:
            primeiro_item_id = r.data[0]["id"]
            total_empenhos = gravar_empenhos(sb, primeiro_item_id, empenhos_geral)
    
    # Tentar clicar nos links de empenhos individuais dos itens
    try:
        links_empenhos = page.query_selector_all("a:has-text('Empenhos')")
        
        for i, link in enumerate(links_empenhos[:len(itens)]):  # Um link por item
            try:
                link.click()
                page.wait_for_timeout(1500)
                
                # Extrair empenhos do modal/seção
                empenhos_item = extrair_empenhos_tabela(page)
                
                if empenhos_item:
                    # Buscar ID do item correspondente
                    r = sb.table("itens_licitacao").select("id").eq("licitacao_id", lic_id).eq("seq", itens[i]["seq"]).execute()
                    if r.data:
                        item_id = r.data[0]["id"]
                        n = gravar_empenhos(sb, item_id, empenhos_item)
                        total_empenhos += n
                
                # Fechar modal se houver
                btn_fechar = page.query_selector("input[value='Fechar'], button:has-text('Fechar'), .rich-mpnl-close")
                if btn_fechar:
                    btn_fechar.click()
                    page.wait_for_timeout(500)
                    
            except:
                pass
    except:
        pass
    
    return total_itens, total_empenhos

def main():
    global interrompido
    
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    print("=" * 60)
    print("AgroIA-RMC — COLETA: ITENS + EMPENHOS")
    print("=" * 60)
    
    # Carregar licitações
    print("\n[1] Carregando licitações do Supabase...")
    dados = sb.table("licitacoes").select("id,processo").eq("orgao", ORGAO).execute().data
    mapa = {d["processo"]: d["id"] for d in dados}
    print(f"    {len(mapa)} licitações no banco")
    
    # Verificar quais já têm itens válidos
    print("\n[2] Verificando itens existentes...")
    r = sb.table("itens_licitacao").select("licitacao_id,codigo").execute()
    coletados = set()
    for item in r.data:
        if item.get("codigo") and item["codigo"].isdigit():
            coletados.add(item["licitacao_id"])
    
    pendentes = [p for p, lid in mapa.items() if lid not in coletados]
    print(f"    {len(coletados)} já coletadas")
    print(f"    {len(pendentes)} pendentes")
    
    if not pendentes:
        print("\n✓ Todas as licitações já foram coletadas!")
        return
    
    # Iniciar coleta
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=150)
        context = browser.new_context()
        context.set_default_timeout(60000)
        page = context.new_page()
        
        print("\n[3] Acessando portal...")
        page.goto(FORM_URL, timeout=60000)
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        print("\n" + "=" * 60)
        print("PREENCHA OS FILTROS:")
        print("  1. Órgão: SMSAN/FAAC")
        print("  2. Datas: 01/01/2019 a 31/12/2025")
        print("  3. Clique em PESQUISAR")
        print("=" * 60)
        input("\n>>> Pressione ENTER após pesquisar...")
        
        # Estatísticas
        total_itens = 0
        total_empenhos = 0
        processados = 0
        sem_itens = 0
        erros = 0
        pagina = 1
        
        print("\n[4] Iniciando coleta (Ctrl+C para parar)...\n")
        
        while not interrompido:
            print(f"\n--- Página {pagina} ---")
            
            links = page.query_selector_all("a[id*='tabela'][id*='j_id26']")
            
            if not links:
                print("    Nenhuma licitação encontrada.")
                break
            
            processos_pagina = []
            for link in links:
                try:
                    texto = link.inner_text().strip()
                    if texto in pendentes:
                        processos_pagina.append(texto)
                except:
                    pass
            
            print(f"    {len(links)} licitações | {len(processos_pagina)} pendentes")
            
            for proc_text in processos_pagina:
                if interrompido:
                    break
                
                lic_id = mapa.get(proc_text)
                if not lic_id:
                    continue
                
                try:
                    # Buscar link
                    links = page.query_selector_all("a[id*='tabela'][id*='j_id26']")
                    link_alvo = None
                    for link in links:
                        if link.inner_text().strip() == proc_text:
                            link_alvo = link
                            break
                    
                    if not link_alvo:
                        continue
                    
                    # Clicar
                    link_alvo.click()
                    page.wait_for_timeout(2500)
                    
                    # Processar
                    n_itens, n_emp = processar_licitacao(page, sb, lic_id, proc_text)
                    
                    if n_itens > 0:
                        total_itens += n_itens
                        total_empenhos += n_emp
                        processados += 1
                        pendentes.remove(proc_text)
                        print(f"  [{processados:4}] {proc_text} | itens:{n_itens:3} | emp:{n_emp}")
                    else:
                        sem_itens += 1
                        print(f"  [----] {proc_text} | sem itens")
                    
                    # Voltar
                    btn = page.query_selector("input[value='Página Inicial']")
                    if btn:
                        btn.click()
                        page.wait_for_timeout(1500)
                    else:
                        aba = page.query_selector("td:has-text('Lista Licitações')")
                        if aba:
                            aba.click()
                            page.wait_for_timeout(1500)
                
                except Exception as e:
                    erros += 1
                    print(f"  [ERRO] {proc_text}: {str(e)[:40]}")
            
            if interrompido:
                break
            
            # Próxima página
            try:
                next_btns = page.query_selector_all("td.rich-datascr-button")
                next_btn = None
                for btn in next_btns:
                    if btn.inner_text().strip() == ">":
                        next_btn = btn
                        break
                
                if next_btn:
                    next_btn.click()
                    page.wait_for_timeout(2000)
                    pagina += 1
                else:
                    print("\n    Fim das páginas.")
                    break
            except:
                break
        
        browser.close()
    
    # Resumo
    print(f"\n{'='*60}")
    print(f"RESUMO")
    print(f"{'='*60}")
    print(f"  Licitações processadas: {processados}")
    print(f"  Total de itens:         {total_itens}")
    print(f"  Total de empenhos:      {total_empenhos}")
    print(f"  Sem itens:              {sem_itens}")
    print(f"  Erros:                  {erros}")
    print(f"  Pendentes:              {len(pendentes)}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
