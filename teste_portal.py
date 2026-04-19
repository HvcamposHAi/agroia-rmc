"""
AgroIA-RMC — Teste de Pesquisa no Portal
========================================
Verifica quantos registros o portal retorna com período 2019-2025.

Execute: python teste_portal.py
"""

import re
import requests
from bs4 import BeautifulSoup

FORM_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Referer": FORM_URL,
}

def get_viewstate(html):
    """Extrai o ViewState do JSF."""
    m = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', html)
    return m.group(1) if m else ""

def contar_registros(html):
    """Extrai o total de registros do HTML."""
    # Procura por "quantidade registros: X" ou "X registros"
    m = re.search(r'quantidade\s+registros[:\s]*(\d+)', html, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r'(\d+)\s+registros', html, re.I)
    if m:
        return int(m.group(1))
    return 0

def contar_paginas(html):
    """Extrai o total de páginas."""
    m = re.search(r'(\d+)\s+p[aá]ginas?', html, re.I)
    return int(m.group(1)) if m else 1

print("=" * 60)
print("TESTE DE PESQUISA NO PORTAL")
print("=" * 60)

session = requests.Session()
session.headers.update(HEADERS)

# 1. GET inicial para ViewState
print("\n[1] Obtendo ViewState...")
r1 = session.get(FORM_URL, timeout=30)
vs = get_viewstate(r1.text)
print(f"    ViewState: {len(vs)} chars")

# 2. Testar com diferentes períodos
periodos = [
    ("01/01/2019", "31/12/2025", "2019-2025 (completo)"),
    ("01/01/2024", "31/12/2025", "2024-2025"),
    ("01/01/2025", "31/12/2025", "2025"),
    ("01/01/2019", "31/12/2019", "2019"),
]

print("\n[2] Testando diferentes períodos:")
print("-" * 60)

for dt_ini, dt_fim, desc in periodos:
    payload = {
        "AJAXREQUEST": "_viewRoot",
        "form:tabs": "abaPesquisa",
        "form:j_id6": "-1",           # Modalidade: todas
        "form:j_id9": "SMSAN/FAAC",   # Órgão
        "form:j_id12": "-1",          # Situação: todas
        "form:j_id15": "",            # Palavra-chave
        "form:dataInferiorInputDate": dt_ini,
        "form:dataInferiorInputCurrentDate": "03/2026",
        "form:j_id18InputDate": dt_fim,
        "form:j_id18InputCurrentDate": "03/2026",
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
        "javax.faces.ViewState": vs,
        "form:btSearch": "Pesquisar",
        "ajaxSource": "form:btSearch",
    }
    
    r = session.post(FORM_URL, data=payload, timeout=30)
    vs = get_viewstate(r.text) or vs  # Atualiza ViewState
    
    total = contar_registros(r.text)
    pags = contar_paginas(r.text)
    
    print(f"    {desc:25} → {total:4} registros | {pags:3} páginas")

print("\n" + "=" * 60)
print("CONCLUSÃO")
print("=" * 60)
print("""
Se o período 2019-2025 retorna ~1200+ registros, o scraper
deve usar esse período para encontrar todos os pendentes.

Se retorna poucos registros, há um problema no payload.
""")
