"""
AgroIA-RMC — Teste da Listagem (com regex correta)
==================================================
Verifica se a pesquisa está retornando os 1240 registros.

Execute: python teste_listagem.py
"""
import re, math, time
import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings
from datetime import datetime

warnings.filterwarnings('ignore', category=XMLParsedAsHTMLWarning)

FORM_URL  = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
ORGAO     = "SMSAN/FAAC"
DT_INICIO = "01/01/2019"
DT_FIM    = "31/12/2025"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Referer": FORM_URL,
}

def get_data_atual():
    now = datetime.now()
    return f"{now.month:02d}/{now.year}"

def obter_viewstate(html):
    soup = BeautifulSoup(html, "lxml")
    tag = soup.find("input", {"name": "javax.faces.ViewState"})
    return tag["value"] if tag else ""

def extrair_total(html):
    """Regex CORRETA da Etapa 1."""
    m = re.search(r"quantidade registros.*?(\d+)</label>", html, re.I | re.DOTALL)
    if m:
        return int(m.group(1))
    return 0

def extrair_processos(html):
    soup = BeautifulSoup(html, "lxml")
    procs = []
    for t in soup.find_all("table"):
        ths = [th.get_text(strip=True).lower() for th in t.find_all("th")]
        if "processo" in ths and "objeto" in ths:
            for tr in t.find_all("tr")[1:]:
                cols = tr.find_all("td")
                if not cols: continue
                proc = cols[0].get_text(strip=True)
                if re.match(r"^[A-Z]{2}\s+\d+/\d{4}", proc):
                    procs.append(proc)
            break
    return procs

print("=" * 60)
print("TESTE DA LISTAGEM")
print("=" * 60)

session = requests.Session()
session.headers.update(HEADERS)

# GET inicial
print("\n[1] Obtendo ViewState...")
resp = session.get(FORM_URL, timeout=30)
viewstate = obter_viewstate(resp.text)
print(f"    ViewState: {len(viewstate)} chars")

# Pesquisa
print(f"\n[2] Pesquisando: {ORGAO} | {DT_INICIO} → {DT_FIM}")
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

r = session.post(FORM_URL, data=payload, timeout=30)
viewstate = obter_viewstate(r.text) or viewstate

total = extrair_total(r.text)
total_pags = math.ceil(total / 5)
procs_p1 = extrair_processos(r.text)

print(f"    Total de registros: {total}")
print(f"    Total de páginas: {total_pags}")
print(f"    Processos na página 1: {len(procs_p1)}")
for p in procs_p1:
    print(f"      {p}")

# Testar paginação - página 2
print("\n[3] Testando paginação (página 2)...")
payload2 = {
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
    "ajaxSingle": "form:tabela:j_id52",
    "form:tabela:j_id52": "2",
    "AJAX:EVENTS_COUNT": "1",
}

time.sleep(1)
r2 = session.post(FORM_URL, data=payload2, timeout=30)
procs_p2 = extrair_processos(r2.text)

print(f"    Processos na página 2: {len(procs_p2)}")
for p in procs_p2:
    print(f"      {p}")

# Testar página 50 (no meio)
print("\n[4] Testando página 50...")
payload3 = payload2.copy()
payload3["form:tabela:j_id52"] = "50"
payload3["javax.faces.ViewState"] = obter_viewstate(r2.text) or viewstate

time.sleep(1)
r3 = session.post(FORM_URL, data=payload3, timeout=30)
procs_p50 = extrair_processos(r3.text)

print(f"    Processos na página 50: {len(procs_p50)}")
for p in procs_p50:
    print(f"      {p}")

print("\n" + "=" * 60)
if total >= 1000:
    print(f"✓ SUCESSO! Portal retornou {total} registros.")
    print("  Execute: python etapa2_v2.py")
else:
    print(f"✗ Problema: apenas {total} registros encontrados.")
print("=" * 60)
