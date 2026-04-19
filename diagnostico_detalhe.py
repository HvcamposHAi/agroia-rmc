"""
AgroIA-RMC — Diagnóstico da Página de Detalhe
=============================================
Captura o HTML de uma página de detalhe para analisar
a estrutura correta da tabela de itens.

Execute: python diagnostico_detalhe.py
"""
import os, re, time
from datetime import datetime
from dotenv import load_dotenv
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings
import requests

warnings.filterwarnings('ignore', category=XMLParsedAsHTMLWarning)
load_dotenv()

FORM_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
ORGAO = "SMSAN/FAAC"
DT_INICIO = "01/01/2019"
DT_FIM = "31/12/2025"

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

print("=" * 70)
print("DIAGNÓSTICO DA PÁGINA DE DETALHE")
print("=" * 70)

session = requests.Session()
session.headers.update(HEADERS)

# 1. GET inicial
print("\n[1] Obtendo ViewState...")
resp = session.get(FORM_URL, timeout=60)
viewstate = obter_viewstate(resp.text)
print(f"    ViewState: {len(viewstate)} chars")

# 2. Pesquisa
print(f"\n[2] Pesquisando: {ORGAO}")
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

r = session.post(FORM_URL, data=payload, timeout=60)
viewstate = obter_viewstate(r.text) or viewstate

# Extrair primeiro processo da lista
soup = BeautifulSoup(r.text, "lxml")
link = None
for t in soup.find_all("table"):
    ths = [th.get_text(strip=True).lower() for th in t.find_all("th")]
    if "processo" in ths and "objeto" in ths:
        for tr in t.find_all("tr")[1:]:
            a = tr.find("a")
            if a and a.get("id"):
                link = a
                break
        break

if not link:
    print("    Nenhum processo encontrado!")
    exit()

link_id = link.get("id")
proc_text = link.get_text(strip=True)
print(f"    Processo encontrado: {proc_text}")
print(f"    Link ID: {link_id}")

# 3. Clicar no processo para abrir detalhe
print(f"\n[3] Abrindo detalhe do processo...")
time.sleep(1)

payload_click = {
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
    link_id: link_id,
}

r_det = session.post(FORM_URL, data=payload_click, timeout=60)

# Salvar HTML para análise
with open("debug_detalhe.html", "w", encoding="utf-8") as f:
    f.write(r_det.text)
print(f"    HTML salvo em: debug_detalhe.html ({len(r_det.text)} chars)")

# 4. Analisar estrutura das tabelas
print(f"\n[4] Analisando tabelas encontradas...")
soup_det = BeautifulSoup(r_det.text, "lxml")

tabelas = soup_det.find_all("table")
print(f"    Total de tabelas: {len(tabelas)}")

for i, t in enumerate(tabelas):
    ths = [th.get_text(strip=True) for th in t.find_all("th")]
    trs = t.find_all("tr")
    
    # Pular tabelas sem headers ou muito pequenas
    if not ths or len(trs) < 2:
        continue
    
    print(f"\n    --- Tabela {i} ---")
    print(f"    Headers: {ths[:7]}")  # Primeiros 7 headers
    print(f"    Linhas: {len(trs)}")
    
    # Mostrar primeira linha de dados
    if len(trs) > 1:
        cols = trs[1].find_all("td")
        dados = [c.get_text(strip=True)[:30] for c in cols[:7]]
        print(f"    Exemplo: {dados}")

# 5. Buscar tabela de itens especificamente
print(f"\n[5] Buscando tabela de ITENS (com Seq, Código, Descrição)...")

for i, t in enumerate(tabelas):
    ths = [th.get_text(strip=True).lower() for th in t.find_all("th")]
    
    # Critério: tem "seq" E "código" E "descrição"
    if "seq" in ths and ("código" in ths or "codigo" in ths):
        print(f"\n    ✓ TABELA DE ITENS ENCONTRADA (índice {i})")
        print(f"    Headers completos: {[th.get_text(strip=True) for th in t.find_all('th')]}")
        
        # Mostrar todas as linhas de dados
        trs = t.find_all("tr")[1:]  # Pular header
        print(f"    Total de itens: {len(trs)}")
        
        for j, tr in enumerate(trs[:5]):  # Primeiros 5 itens
            cols = tr.find_all("td")
            if cols:
                dados = [c.get_text(strip=True)[:40] for c in cols]
                print(f"    Item {j+1}: {dados}")
        
        # Identificar índice de cada coluna
        print(f"\n    Mapeamento de colunas:")
        for idx, th in enumerate(t.find_all("th")):
            print(f"      [{idx}] {th.get_text(strip=True)}")

# 6. Buscar tabela de fornecedores
print(f"\n[6] Buscando tabela de FORNECEDORES (com CPF/CNPJ)...")

for i, t in enumerate(tabelas):
    ths = [th.get_text(strip=True).lower() for th in t.find_all("th")]
    
    if "cpf/cnpj" in ths or "cnpj" in ths or "razão social" in ths:
        print(f"\n    ✓ TABELA DE FORNECEDORES ENCONTRADA (índice {i})")
        print(f"    Headers: {[th.get_text(strip=True) for th in t.find_all('th')]}")
        
        trs = t.find_all("tr")[1:]
        print(f"    Total: {len(trs)}")
        
        for j, tr in enumerate(trs[:3]):
            cols = tr.find_all("td")
            if cols:
                dados = [c.get_text(strip=True)[:40] for c in cols]
                print(f"    Forn {j+1}: {dados}")

print("\n" + "=" * 70)
print("Análise concluída! Verifique debug_detalhe.html para detalhes.")
print("=" * 70)
