"""
AgroIA-RMC — Etapa 2: Coleta de Detalhes (v2 - CORRIGIDO)
=========================================================
Usa a mesma lógica de paginação da Etapa 1 (ingestao_supabase.py)
que conseguiu coletar 1237 registros.

Fluxo:
1. Pesquisa via requests (lista processos)
2. Para cada processo PENDENTE, clica e extrai detalhes
3. Grava itens, fornecedores e empenhos no Supabase

Execute: python etapa2_v2.py
"""
import os, re, math, time
from datetime import datetime
from dotenv import load_dotenv
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings
import requests
from supabase import create_client

warnings.filterwarnings('ignore', category=XMLParsedAsHTMLWarning)
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

FORM_URL  = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
ORGAO     = "SMSAN/FAAC"
DT_INICIO = "01/01/2019"
DT_FIM    = "31/12/2025"
REGS_POR_PAGINA = 5
DELAY     = 1.2

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Referer": FORM_URL,
}

# ── Funções auxiliares ────────────────────────────────────────────────────────

def parse_val(t):
    try: return float((t or "0").strip().replace(".","").replace(",","."))
    except: return 0.0

def norm_cultura(d):
    mapa = {"banana":"banana","laranja":"laranja","maçã":"maca","mamão":"mamao",
            "melancia":"melancia","uva":"uva","morango":"morango","tomate":"tomate",
            "cebola":"cebola","cenoura":"cenoura","batata":"batata","aipim":"aipim",
            "mandioca":"aipim","alface":"alface","couve":"couve","repolho":"repolho",
            "brócolis":"brocolis","alho":"alho","beterraba":"beterraba",
            "pimentão":"pimentao","abobrinha":"abobrinha","chuchu":"chuchu",
            "arroz":"arroz","feijão":"feijao","milho":"milho","queijo":"queijo",
            "leite":"leite","ovos":"ovos","frango":"frango","carne":"carne",
            "pão":"pao","mel":"mel","inhame":"inhame","abacaxi":"abacaxi",
            "goiaba":"goiaba","limão":"limao","kiwi":"kiwi"}
    d = (d or "").lower().strip()
    for k, v in mapa.items():
        if k in d: return v
    return d

def categ(c):
    if c in {"abacaxi","banana","goiaba","laranja","limao","maca","mamao",
             "melancia","uva","morango","kiwi"}: return "FRUTA"
    if c in {"tomate","cebola","cenoura","batata","aipim","alho","beterraba",
             "pimentao","abobrinha","chuchu","milho","inhame"}: return "LEGUME"
    if c in {"alface","couve","repolho","brocolis"}: return "FOLHOSA"
    if c in {"queijo","leite"}: return "LATICINIOS"
    if c in {"frango","carne","ovos"}: return "PROTEINA"
    if c in {"arroz","feijao","mel","pao"}: return "GRAOS"
    return "OUTRO"

def tipo_forn(r):
    r = (r or "").upper()
    if "COOPERATIV" in r: return "COOPERATIVA"
    if "ASSOCIA" in r:    return "ASSOCIACAO"
    return "EMPRESA"

def get_data_atual():
    now = datetime.now()
    return f"{now.month:02d}/{now.year}"

def obter_viewstate(html):
    soup = BeautifulSoup(html, "lxml")
    tag = soup.find("input", {"name": "javax.faces.ViewState"})
    return tag["value"] if tag else ""

def extrair_total(html):
    """Regex CORRETA da Etapa 1 que funcionou."""
    m = re.search(r"quantidade registros.*?(\d+)</label>", html, re.I | re.DOTALL)
    if m:
        return int(m.group(1))
    texto = BeautifulSoup(html, "lxml").get_text()
    m2 = re.search(r"quantidade registros[\s:]*?(\d+)", texto, re.I)
    return int(m2.group(1)) if m2 else 0

# ── Requisições HTTP ──────────────────────────────────────────────────────────

def post_pesquisa(session, viewstate, pagina=1):
    """POST de pesquisa - igual à Etapa 1."""
    data_atual = get_data_atual()
    payload = {
        "AJAXREQUEST": "_viewRoot",
        "form:tabs": "abaPesquisa",
        "form:j_id6": "-1",
        "form:j_id9": ORGAO,
        "form:j_id12": "-1",
        "form:j_id15": "",
        "form:dataInferiorInputDate": DT_INICIO,
        "form:dataInferiorInputCurrentDate": data_atual,
        "form:j_id18InputDate": DT_FIM,
        "form:j_id18InputCurrentDate": data_atual,
        "form:fornecedoresEditalOpenedState": "",
        "form:fornecedoresParticipantesOpenedState": "",
        "form:observacoesItemOpenedState": "",
        "form:j_id253": "",
        "form:messagesOpenedState": "",
        "form:waitOpenedState": "",
        "form:empenhosProcCompraOpenedState": "",
        "form:documentosOpenedState": "",
        "form": "form",
        "autoScroll": "",
        "javax.faces.ViewState": viewstate,
        "form:btSearch": "Pesquisar",
        "ajaxSource": "form:btSearch",
    }
    # Paginação via RichFaces DataScroller
    if pagina > 1:
        del payload["form:btSearch"]
        del payload["ajaxSource"]
        payload["ajaxSingle"] = "form:tabela:j_id52"
        payload["form:tabela:j_id52"] = str(pagina)
        payload["AJAX:EVENTS_COUNT"] = "1"
    
    resp = session.post(FORM_URL, data=payload, timeout=30)
    return resp.text

def clicar_processo(session, viewstate, link_id, id_interno=None, situacao=None):
    """
    Abre o detalhe de um processo.
    O link_id é o id do <a> JSF (ex: "form:tabela:0:j_id26").
    id_interno e situacao são extraídos do onclick.
    """
    payload = {
        "AJAXREQUEST": "_viewRoot",
        "form:tabs": "abaPesquisa",
        "form:j_id6": "-1",
        "form:j_id9": ORGAO,
        "form:j_id12": "-1",
        "form:j_id15": "",
        "form:dataInferiorInputDate": DT_INICIO,
        "form:dataInferiorInputCurrentDate": get_data_atual(),
        "form:j_id18InputDate": DT_FIM,
        "form:j_id18InputCurrentDate": get_data_atual(),
        "form:fornecedoresEditalOpenedState": "",
        "form:fornecedoresParticipantesOpenedState": "",
        "form:observacoesItemOpenedState": "",
        "form:j_id253": "",
        "form:messagesOpenedState": "",
        "form:waitOpenedState": "",
        "form:empenhosProcCompraOpenedState": "",
        "form:documentosOpenedState": "",
        "form": "form",
        "autoScroll": "",
        "javax.faces.ViewState": viewstate,
        link_id: link_id,
    }
    # Adicionar parâmetros do onclick se disponíveis
    if id_interno:
        payload["id"] = str(id_interno)
    if situacao:
        payload["situacao"] = situacao
    
    resp = session.post(FORM_URL, data=payload, timeout=30)
    return resp.text

# ── Extração HTML ─────────────────────────────────────────────────────────────

def extrair_lista(html):
    """Extrai processos da página atual."""
    soup = BeautifulSoup(html, "lxml")
    regs = []
    for t in soup.find_all("table"):
        ths = [th.get_text(strip=True).lower() for th in t.find_all("th")]
        if "processo" in ths and "objeto" in ths:
            for tr in t.find_all("tr")[1:]:
                cols = tr.find_all("td")
                if len(cols) < 3: continue
                proc = cols[0].get_text(strip=True)
                if not re.match(r"^[A-Z]{2}\s+\d+/\d{4}", proc): continue
                link = cols[0].find("a")
                link_id = ""
                id_interno = 0
                situacao = ""
                if link:
                    link_id = link.get("id", "")
                    onclick = link.get("onclick", "")
                    m_id = re.search(r"'id'\s*:\s*(\d+)", onclick)
                    m_sit = re.search(r"'situacao'\s*:\s*'([^']+)'", onclick)
                    if m_id: id_interno = int(m_id.group(1))
                    if m_sit: situacao = m_sit.group(1)
                regs.append({
                    "processo": proc,
                    "link_id": link_id,
                    "id_interno": id_interno,
                    "situacao": situacao,
                })
            break
    return regs

def extrair_detalhes(html):
    """Extrai itens, fornecedores e empenhos do detalhe."""
    soup = BeautifulSoup(html, "lxml")
    itens, forns, emps = [], [], []
    
    for t in soup.find_all("table"):
        ths = [th.get_text(strip=True).lower() for th in t.find_all("th")]
        
        # Tabela de itens
        if any(h in ths for h in ["seq", "código", "codigo"]):
            for i, tr in enumerate(t.find_all("tr")[1:]):
                cols = tr.find_all("td")
                if len(cols) < 3: continue
                desc = cols[2].get_text(strip=True) if len(cols) > 2 else ""
                seq = cols[0].get_text(strip=True)
                cultura = norm_cultura(desc)
                itens.append({
                    "seq": int(seq) if seq.isdigit() else i+1,
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
                if len(cols) < 2: continue
                cpf = cols[0].get_text(strip=True)
                razao = cols[1].get_text(strip=True)
                if len(re.sub(r"[^\d]", "", cpf)) >= 11 and razao:
                    forns.append({"cpf_cnpj": cpf.strip(), "razao_social": razao.strip()})
        
        # Tabela de empenhos
        elif "data empenho" in " ".join(ths) or "dt. empenho" in " ".join(ths):
            for tr in t.find_all("tr")[1:]:
                cols = tr.find_all("td")
                if len(cols) < 2: continue
                nr = cols[0].get_text(strip=True)
                if nr and nr != "null":
                    ano = cols[1].get_text(strip=True) if len(cols) > 1 else ""
                    data = cols[2].get_text(strip=True) if len(cols) > 2 else ""
                    try: dt = datetime.strptime(data, "%d/%m/%Y").strftime("%Y-%m-%d")
                    except: dt = None
                    emps.append({
                        "nr_empenho": nr,
                        "ano": int(ano) if ano.isdigit() else None,
                        "dt_empenho": dt
                    })
    
    return itens, forns, emps

# ── Gravação Supabase ─────────────────────────────────────────────────────────

def gravar(sb, lic_id, itens, forns, emps):
    n_i = n_f = 0
    for item in itens:
        item["licitacao_id"] = lic_id
        try:
            sb.table("itens_licitacao").upsert(item, on_conflict="licitacao_id,seq").execute()
            n_i += 1
        except: pass
    
    for forn in forns:
        try:
            r = sb.table("fornecedores").upsert(
                {"cpf_cnpj": forn["cpf_cnpj"], "razao_social": forn["razao_social"],
                 "tipo": tipo_forn(forn["razao_social"])},
                on_conflict="cpf_cnpj").execute()
            fid = r.data[0]["id"] if r.data else None
            if not fid:
                r2 = sb.table("fornecedores").select("id").eq("cpf_cnpj", forn["cpf_cnpj"]).execute()
                fid = r2.data[0]["id"] if r2.data else None
            if fid:
                sb.table("participacoes").upsert(
                    {"licitacao_id": lic_id, "fornecedor_id": fid, "participou": True},
                    on_conflict="licitacao_id,fornecedor_id").execute()
                n_f += 1
        except: pass
    
    if emps and itens:
        try:
            r = sb.table("itens_licitacao").select("id").eq("licitacao_id", lic_id).limit(1).execute()
            if r.data:
                for emp in emps:
                    emp["item_id"] = r.data[0]["id"]
                    sb.table("empenhos").insert(emp).execute()
        except: pass
    
    return n_i, n_f

# ── Fluxo principal ───────────────────────────────────────────────────────────

def main():
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    session = requests.Session()
    session.headers.update(HEADERS)
    
    # Carregar mapa do banco
    print("[0] Carregando licitações do Supabase...")
    dados = sb.table("licitacoes").select("id,processo").eq("orgao", ORGAO).execute().data
    mapa = {d["processo"]: d["id"] for d in dados}
    
    # IDs que já têm itens
    r = sb.table("itens_licitacao").select("licitacao_id").execute()
    coletados = {row["licitacao_id"] for row in r.data}
    pendentes_ids = {lid for lid in mapa.values() if lid not in coletados}
    print(f"    {len(mapa)} no banco | {len(coletados)} coletados | {len(pendentes_ids)} pendentes\n")
    
    if not pendentes_ids:
        print("Tudo coletado!")
        return
    
    # GET inicial
    print("[1] Obtendo ViewState...")
    resp = session.get(FORM_URL, timeout=30)
    viewstate = obter_viewstate(resp.text)
    print(f"    ViewState: {len(viewstate)} chars")
    
    # Pesquisa
    print(f"[2] Pesquisando: {ORGAO} | {DT_INICIO} → {DT_FIM}")
    html = post_pesquisa(session, viewstate, pagina=1)
    viewstate = obter_viewstate(html) or viewstate
    
    total_reg = extrair_total(html)
    total_pag = math.ceil(total_reg / REGS_POR_PAGINA)
    print(f"    {total_reg} registros | {total_pag} páginas\n")
    
    if total_reg == 0:
        print("[!] 0 registros encontrados")
        return
    
    # Coletar detalhes
    print("[3] Coletando detalhes...\n")
    total_itens = total_forns = total_erros = processados = 0
    
    for pagina in range(1, total_pag + 1):
        if pagina > 1:
            time.sleep(DELAY)
            html = post_pesquisa(session, viewstate, pagina=pagina)
            viewstate = obter_viewstate(html) or viewstate
        
        regs = extrair_lista(html)
        
        for reg in regs:
            proc = reg["processo"]
            lic_id = mapa.get(proc)
            
            # Pular se não está no banco ou já coletado
            if not lic_id or lic_id not in pendentes_ids:
                continue
            
            try:
                time.sleep(DELAY)
                html_det = clicar_processo(
                    session, viewstate, 
                    reg["link_id"], 
                    reg["id_interno"], 
                    reg["situacao"]
                )
                viewstate = obter_viewstate(html_det) or viewstate
                
                itens, forns, emps = extrair_detalhes(html_det)
                n_i, n_f = gravar(sb, lic_id, itens, forns, emps)
                
                pendentes_ids.discard(lic_id)
                total_itens += n_i
                total_forns += n_f
                processados += 1
                
                print(f"  [{processados}] {proc} | itens:{n_i} | forn:{n_f} | emp:{len(emps)}")
                
                # Voltar para lista - nova pesquisa na mesma página
                time.sleep(DELAY)
                html = post_pesquisa(session, viewstate, pagina=pagina)
                viewstate = obter_viewstate(html) or viewstate
                
            except Exception as e:
                total_erros += 1
                print(f"  ERRO {proc}: {str(e)[:60]}")
        
        # Progresso
        if pagina % 10 == 0:
            print(f"\n  --- Página {pagina}/{total_pag} | Processados: {processados} | Pendentes: {len(pendentes_ids)} ---\n")
    
    print(f"\n{'='*55}")
    print(f"Concluído!")
    print(f"  Processados:  {processados}")
    print(f"  Itens:        {total_itens}")
    print(f"  Fornecedores: {total_forns}")
    print(f"  Erros:        {total_erros}")
    print(f"  Pendentes:    {len(pendentes_ids)}")
    print(f"{'='*55}")

if __name__ == "__main__":
    main()
