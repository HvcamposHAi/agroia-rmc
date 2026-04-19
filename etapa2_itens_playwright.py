"""
AgroIA-RMC — Etapa 2: Coleta de Itens (Playwright - CORRIGIDO)
==============================================================
Versão corrigida que usa Playwright para renderizar JavaScript
e capturar a tabela de itens corretamente.

A tabela de itens tem estrutura:
Seq | Código | Descrição | Qt. Solicitada | UN | Valor | Empenhos

Execute: python etapa2_itens_playwright.py
"""
import os
import re
import time
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

# ── Funções auxiliares ────────────────────────────────────────────────────────

def parse_val(t):
    """Converte texto numérico BR para float."""
    try:
        return float((t or "0").strip().replace(".", "").replace(",", "."))
    except:
        return 0.0

def norm_cultura(desc):
    """Normaliza nome da cultura a partir da descrição."""
    mapa = {
        "leite": "leite", "banana": "banana", "laranja": "laranja", 
        "maçã": "maca", "maça": "maca", "mamão": "mamao", "mamao": "mamao",
        "melancia": "melancia", "uva": "uva", "morango": "morango", 
        "tomate": "tomate", "cebola": "cebola", "cenoura": "cenoura", 
        "batata": "batata", "aipim": "aipim", "mandioca": "aipim",
        "alface": "alface", "couve": "couve", "repolho": "repolho",
        "brócolis": "brocolis", "brocolis": "brocolis", "alho": "alho", 
        "beterraba": "beterraba", "pimentão": "pimentao", "pimentao": "pimentao",
        "abobrinha": "abobrinha", "chuchu": "chuchu", "pepino": "pepino",
        "arroz": "arroz", "feijão": "feijao", "feijao": "feijao", 
        "milho": "milho", "queijo": "queijo", "ovos": "ovos", "ovo": "ovos",
        "frango": "frango", "carne": "carne", "pão": "pao", "pao": "pao",
        "mel": "mel", "abacaxi": "abacaxi", "goiaba": "goiaba",
        "limão": "limao", "limao": "limao", "kiwi": "kiwi", "manga": "manga",
        "pêra": "pera", "pera": "pera", "ameixa": "ameixa", "figo": "figo",
        "caqui": "caqui", "maracujá": "maracuja", "maracuja": "maracuja",
        "abóbora": "abobora", "abobora": "abobora", "inhame": "inhame",
        "farinha": "farinha", "açúcar": "acucar", "acucar": "acucar",
        "óleo": "oleo", "oleo": "oleo", "vinagre": "vinagre",
        "café": "cafe", "cafe": "cafe", "biscoito": "biscoito",
        "macarrão": "macarrao", "macarrao": "macarrao",
    }
    desc_lower = (desc or "").lower().strip()
    for k, v in mapa.items():
        if k in desc_lower:
            return v
    # Retorna primeira palavra significativa se não encontrar no mapa
    palavras = re.findall(r'[a-záéíóúâêîôûãõç]+', desc_lower)
    return palavras[0] if palavras else "outro"

def categ(cultura):
    """Categoriza a cultura."""
    frutas = {"abacaxi", "banana", "goiaba", "laranja", "limao", "maca", 
              "mamao", "melancia", "uva", "morango", "kiwi", "manga", 
              "pera", "ameixa", "figo", "caqui", "maracuja"}
    legumes = {"tomate", "cebola", "cenoura", "batata", "aipim", "alho", 
               "beterraba", "pimentao", "abobrinha", "chuchu", "pepino",
               "milho", "inhame", "abobora"}
    folhosas = {"alface", "couve", "repolho", "brocolis"}
    laticinios = {"queijo", "leite"}
    proteinas = {"frango", "carne", "ovos"}
    graos = {"arroz", "feijao", "farinha", "cafe", "acucar", "biscoito", "macarrao"}
    
    if cultura in frutas: return "FRUTA"
    if cultura in legumes: return "LEGUME"
    if cultura in folhosas: return "FOLHOSA"
    if cultura in laticinios: return "LATICINIOS"
    if cultura in proteinas: return "PROTEINA"
    if cultura in graos: return "GRAOS"
    return "OUTRO"

def tipo_forn(razao):
    """Classifica tipo de fornecedor."""
    r = (razao or "").upper()
    if "COOPERATIV" in r: return "COOPERATIVA"
    if "ASSOCIA" in r: return "ASSOCIACAO"
    return "EMPRESA"

# ── Extração de dados ─────────────────────────────────────────────────────────

def extrair_itens(page):
    """Extrai itens da tabela na página de detalhe."""
    itens = []
    
    # Buscar todas as tabelas
    tabelas = page.query_selector_all("table")
    
    for tabela in tabelas:
        # Verificar headers
        headers = tabela.query_selector_all("th")
        if not headers:
            continue
        
        header_texts = [h.inner_text().strip().lower() for h in headers]
        
        # Identificar tabela de itens: tem "seq" e "código" ou "descrição"
        if "seq" in header_texts and ("código" in header_texts or "codigo" in header_texts or "descrição" in header_texts):
            
            # Mapear índices das colunas
            idx_seq = header_texts.index("seq") if "seq" in header_texts else None
            idx_codigo = None
            idx_descricao = None
            idx_qt = None
            idx_un = None
            idx_valor = None
            
            for i, h in enumerate(header_texts):
                if "código" in h or "codigo" in h:
                    idx_codigo = i
                elif "descrição" in h or "descricao" in h:
                    idx_descricao = i
                elif "qt" in h or "solicitada" in h:
                    idx_qt = i
                elif h == "un" or "unidade" in h:
                    idx_un = i
                elif "valor" in h and "total" not in h:
                    idx_valor = i
            
            # Extrair linhas de dados
            rows = tabela.query_selector_all("tr")
            
            for row in rows[1:]:  # Pular header
                cells = row.query_selector_all("td")
                if len(cells) < 3:
                    continue
                
                # Extrair valores
                seq_text = cells[idx_seq].inner_text().strip() if idx_seq is not None and idx_seq < len(cells) else ""
                
                # Validar que é um item real (seq deve ser número)
                if not seq_text.isdigit():
                    continue
                
                codigo = cells[idx_codigo].inner_text().strip() if idx_codigo is not None and idx_codigo < len(cells) else ""
                descricao = cells[idx_descricao].inner_text().strip() if idx_descricao is not None and idx_descricao < len(cells) else ""
                qt_text = cells[idx_qt].inner_text().strip() if idx_qt is not None and idx_qt < len(cells) else "0"
                un = cells[idx_un].inner_text().strip() if idx_un is not None and idx_un < len(cells) else ""
                valor_text = cells[idx_valor].inner_text().strip() if idx_valor is not None and idx_valor < len(cells) else "0"
                
                # Normalizar cultura
                cultura = norm_cultura(descricao)
                
                itens.append({
                    "seq": int(seq_text),
                    "codigo": codigo,
                    "descricao": descricao,
                    "qt_solicitada": parse_val(qt_text),
                    "unidade_medida": un,
                    "valor_unitario": parse_val(valor_text),
                    "valor_total": 0,  # Calcular depois se necessário
                    "cultura": cultura,
                    "categoria": categ(cultura),
                })
            
            break  # Encontrou a tabela de itens
    
    return itens

def extrair_fornecedores(page):
    """Extrai fornecedores participantes."""
    fornecedores = []
    
    tabelas = page.query_selector_all("table")
    
    for tabela in tabelas:
        headers = tabela.query_selector_all("th")
        if not headers:
            continue
        
        header_texts = [h.inner_text().strip().lower() for h in headers]
        
        # Tabela de fornecedores: tem "cpf/cnpj" e "razão social"
        if "cpf/cnpj" in header_texts and "razão social" in header_texts:
            idx_cpf = header_texts.index("cpf/cnpj")
            idx_razao = header_texts.index("razão social")
            
            rows = tabela.query_selector_all("tr")
            
            for row in rows[1:]:
                cells = row.query_selector_all("td")
                if len(cells) < 2:
                    continue
                
                cpf = cells[idx_cpf].inner_text().strip() if idx_cpf < len(cells) else ""
                razao = cells[idx_razao].inner_text().strip() if idx_razao < len(cells) else ""
                
                # Validar CPF/CNPJ (deve ter pelo menos 11 dígitos)
                cpf_limpo = re.sub(r"[^\d]", "", cpf)
                if len(cpf_limpo) >= 11 and razao and razao != "Razão Social":
                    fornecedores.append({
                        "cpf_cnpj": cpf,
                        "razao_social": razao,
                    })
    
    return fornecedores

def extrair_empenhos(page):
    """Extrai empenhos."""
    empenhos = []
    
    tabelas = page.query_selector_all("table")
    
    for tabela in tabelas:
        headers = tabela.query_selector_all("th")
        if not headers:
            continue
        
        header_texts = [h.inner_text().strip().lower() for h in headers]
        
        # Tabela de empenhos: tem "número" e "ano" e "data empenho"
        if "número" in header_texts and "ano" in header_texts:
            idx_num = header_texts.index("número")
            idx_ano = header_texts.index("ano")
            idx_data = None
            for i, h in enumerate(header_texts):
                if "data" in h and "empenho" in h:
                    idx_data = i
                    break
            
            rows = tabela.query_selector_all("tr")
            
            for row in rows[1:]:
                cells = row.query_selector_all("td")
                if len(cells) < 2:
                    continue
                
                nr = cells[idx_num].inner_text().strip() if idx_num < len(cells) else ""
                ano = cells[idx_ano].inner_text().strip() if idx_ano < len(cells) else ""
                data = cells[idx_data].inner_text().strip() if idx_data and idx_data < len(cells) else ""
                
                if nr and nr.isdigit():
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
    
    return empenhos

# ── Gravação Supabase ─────────────────────────────────────────────────────────

def gravar_itens(sb, lic_id, itens):
    """Grava itens no Supabase."""
    n = 0
    for item in itens:
        item["licitacao_id"] = lic_id
        try:
            sb.table("itens_licitacao").upsert(item, on_conflict="licitacao_id,seq").execute()
            n += 1
        except Exception as e:
            print(f"      Erro item seq={item.get('seq')}: {e}")
    return n

def gravar_fornecedores(sb, lic_id, fornecedores):
    """Grava fornecedores e participações."""
    n = 0
    for forn in fornecedores:
        try:
            # Upsert fornecedor
            r = sb.table("fornecedores").upsert(
                {
                    "cpf_cnpj": forn["cpf_cnpj"],
                    "razao_social": forn["razao_social"],
                    "tipo": tipo_forn(forn["razao_social"]),
                },
                on_conflict="cpf_cnpj"
            ).execute()
            
            fid = r.data[0]["id"] if r.data else None
            if not fid:
                r2 = sb.table("fornecedores").select("id").eq("cpf_cnpj", forn["cpf_cnpj"]).execute()
                fid = r2.data[0]["id"] if r2.data else None
            
            if fid:
                # Upsert participação
                sb.table("participacoes").upsert(
                    {"licitacao_id": lic_id, "fornecedor_id": fid, "participou": True},
                    on_conflict="licitacao_id,fornecedor_id"
                ).execute()
                n += 1
        except Exception as e:
            print(f"      Erro fornecedor: {e}")
    return n

def gravar_empenhos(sb, lic_id, empenhos):
    """Grava empenhos."""
    if not empenhos:
        return 0
    
    try:
        # Pegar primeiro item da licitação para associar
        r = sb.table("itens_licitacao").select("id").eq("licitacao_id", lic_id).limit(1).execute()
        if not r.data:
            return 0
        
        item_id = r.data[0]["id"]
        n = 0
        for emp in empenhos:
            emp["item_id"] = item_id
            try:
                sb.table("empenhos").insert(emp).execute()
                n += 1
            except:
                pass
        return n
    except:
        return 0

# ── Fluxo principal ───────────────────────────────────────────────────────────

def main():
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Carregar mapa do banco
    print("[0] Carregando licitações do Supabase...")
    dados = sb.table("licitacoes").select("id,processo").eq("orgao", ORGAO).execute().data
    mapa = {d["processo"]: d["id"] for d in dados}
    
    # IDs que já têm itens VÁLIDOS (com código no formato XX.XX.XX)
    # Precisamos recoletar TODOS porque os dados antigos estão corrompidos
    print("    ATENÇÃO: Recoletando TODOS os itens (dados anteriores corrompidos)")
    
    # Limpar tabela de itens corrompidos
    print("    Limpando itens antigos...")
    try:
        sb.table("itens_licitacao").delete().neq("id", 0).execute()
        print("    Itens limpos!")
    except Exception as e:
        print(f"    Aviso ao limpar: {e}")
    
    pendentes = list(mapa.keys())
    print(f"    {len(mapa)} licitações para coletar\n")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        page = browser.new_page()
        
        # Acessar portal
        print("[1] Acessando portal...")
        page.goto(FORM_URL, timeout=60000)
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        # Preencher filtros
        print("[2] Preenchendo filtros...")
        
        # Encontrar e preencher o select de órgão
        selects = page.query_selector_all("select")
        for sel in selects:
            options = sel.query_selector_all("option")
            for opt in options:
                if ORGAO in opt.inner_text():
                    sel.select_option(value=opt.get_attribute("value"))
                    break
        
        # Preencher datas
        inputs = page.query_selector_all("input[type='text']")
        for inp in inputs:
            inp_id = inp.get_attribute("id") or ""
            if "dataInferior" in inp_id and "Input" in inp_id:
                inp.fill(DT_INICIO)
            elif "j_id18" in inp_id and "Input" in inp_id:
                inp.fill(DT_FIM)
        
        # Pesquisar
        print("[3] Pesquisando...")
        btn = page.query_selector("input[value='Pesquisar']")
        if btn:
            btn.click()
        page.wait_for_timeout(3000)
        
        # Processar licitações
        print("[4] Coletando detalhes...\n")
        
        total_itens = 0
        total_forns = 0
        total_emps = 0
        processados = 0
        erros = 0
        
        pagina_atual = 1
        
        while True:
            # Extrair links da página atual
            links = page.query_selector_all("a[id^='form:tabela:'][id$=':j_id26']")
            
            if not links:
                print("    Nenhum link encontrado na página")
                break
            
            for i, link in enumerate(links):
                try:
                    # Obter texto do processo
                    proc_text = link.inner_text().strip()
                    lic_id = mapa.get(proc_text)
                    
                    if not lic_id:
                        continue
                    
                    # Clicar no link
                    link.click()
                    page.wait_for_timeout(2000)
                    
                    # Extrair dados
                    itens = extrair_itens(page)
                    forns = extrair_fornecedores(page)
                    emps = extrair_empenhos(page)
                    
                    # Gravar no banco
                    if itens:
                        n_i = gravar_itens(sb, lic_id, itens)
                        n_f = gravar_fornecedores(sb, lic_id, forns)
                        n_e = gravar_empenhos(sb, lic_id, emps)
                        
                        total_itens += n_i
                        total_forns += n_f
                        total_emps += n_e
                        processados += 1
                        
                        print(f"  [{processados}] {proc_text} | itens:{n_i} | forn:{n_f} | emp:{n_e}")
                    else:
                        print(f"  [!] {proc_text} | sem itens")
                    
                    # Voltar para lista
                    btn_voltar = page.query_selector("input[value='Página Inicial']")
                    if btn_voltar:
                        btn_voltar.click()
                        page.wait_for_timeout(2000)
                    else:
                        # Clicar na aba Lista Licitações
                        aba = page.query_selector("text='Lista Licitações'")
                        if aba:
                            aba.click()
                            page.wait_for_timeout(2000)
                    
                except Exception as e:
                    erros += 1
                    print(f"  ERRO: {str(e)[:50]}")
                    # Tentar voltar
                    try:
                        page.goto(FORM_URL, timeout=30000)
                        page.wait_for_timeout(2000)
                    except:
                        pass
            
            # Próxima página
            try:
                # Buscar botão de próxima página
                next_btn = page.query_selector("a[onclick*='j_id52'][onclick*='next'], td.rich-datascr-button:has-text('>')")
                if next_btn:
                    next_btn.click()
                    page.wait_for_timeout(2000)
                    pagina_atual += 1
                    print(f"\n  --- Página {pagina_atual} ---\n")
                else:
                    break
            except:
                break
        
        browser.close()
    
    print(f"\n{'='*55}")
    print(f"Concluído!")
    print(f"  Processados:  {processados}")
    print(f"  Itens:        {total_itens}")
    print(f"  Fornecedores: {total_forns}")
    print(f"  Empenhos:     {total_emps}")
    print(f"  Erros:        {erros}")
    print(f"{'='*55}")

if __name__ == "__main__":
    main()
