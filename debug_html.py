"""
AgroIA-RMC — Análise do HTML do Portal
======================================
Salva o HTML retornado para análise detalhada.

Execute: python debug_html.py
"""
import re
import requests

FORM_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
ORGAO = "SMSAN/FAAC"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Referer": FORM_URL,
}

def get_vs(html):
    m = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', html)
    return m.group(1) if m else ""

print("=" * 60)
print("ANÁLISE DO HTML DO PORTAL")
print("=" * 60)

session = requests.Session()
session.headers.update(HEADERS)

# 1. GET inicial
print("\n[1] GET inicial...")
r1 = session.get(FORM_URL, timeout=30)
vs = get_vs(r1.text)
print(f"    Status: {r1.status_code}")
print(f"    Tamanho: {len(r1.text)} chars")
print(f"    ViewState: {len(vs)} chars")

# Salvar
with open("debug_html_get.html", "w", encoding="utf-8") as f:
    f.write(r1.text)
print("    Salvo em: debug_html_get.html")

# 2. POST de pesquisa
print("\n[2] POST de pesquisa...")
payload = {
    "AJAXREQUEST": "_viewRoot",
    "form:tabs": "abaPesquisa",
    "form:j_id6": "-1",
    "form:j_id9": ORGAO,
    "form:j_id12": "-1",
    "form:j_id15": "",
    "form:dataInferiorInputDate": "01/01/2019",
    "form:dataInferiorInputCurrentDate": "03/2026",
    "form:j_id18InputDate": "31/12/2025",
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

r2 = session.post(FORM_URL, data=payload, timeout=30)
print(f"    Status: {r2.status_code}")
print(f"    Tamanho: {len(r2.text)} chars")

# Salvar
with open("debug_html_post.html", "w", encoding="utf-8") as f:
    f.write(r2.text)
print("    Salvo em: debug_html_post.html")

# 3. Analisar conteúdo
print("\n[3] Análise do conteúdo:")

# Procurar padrões de quantidade
patterns = [
    (r"quantidade registros.*?(\d+)", "quantidade registros"),
    (r"(\d+)\s*registros", "N registros"),
    (r"(\d+)\s*p[aá]ginas?", "N páginas"),
    (r"form:tabela", "tabela"),
    (r"rich-datascr", "datascroller"),
]

for pat, desc in patterns:
    m = re.search(pat, r2.text, re.I | re.DOTALL)
    if m:
        print(f"    '{desc}': encontrado - '{m.group(0)[:50]}...'")
    else:
        print(f"    '{desc}': NÃO encontrado")

# Procurar processos
procs = re.findall(r"([A-Z]{2}\s+\d+/\d{4}\s*-\s*SMSAN)", r2.text)
print(f"\n    Processos encontrados no HTML: {len(procs)}")
if procs:
    for p in procs[:5]:
        print(f"      {p}")

# 4. Verificar se há mensagem de erro
print("\n[4] Verificando erros/mensagens:")
if "erro" in r2.text.lower():
    m = re.search(r"(erro[^<]{0,100})", r2.text, re.I)
    if m:
        print(f"    ERRO encontrado: {m.group(1)}")
if "nenhum registro" in r2.text.lower():
    print("    Mensagem: 'nenhum registro encontrado'")
if "session" in r2.text.lower() and "expired" in r2.text.lower():
    print("    Mensagem: sessão expirada")

print("\n" + "=" * 60)
print("ARQUIVOS SALVOS:")
print("  - debug_html_get.html (página inicial)")
print("  - debug_html_post.html (resultado da pesquisa)")
print("\nAbra esses arquivos no navegador para inspecionar.")
print("=" * 60)
