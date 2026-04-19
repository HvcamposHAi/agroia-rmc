"""
AgroIA-RMC — Análise detalhada do HTML
======================================
Analisa o arquivo debug_html_post.html para entender a estrutura.

Execute: python analisar_html.py
"""
import re
from bs4 import BeautifulSoup

print("=" * 70)
print("ANÁLISE DETALHADA DO HTML")
print("=" * 70)

# Ler o arquivo
try:
    with open("debug_html_post.html", "r", encoding="utf-8") as f:
        html = f.read()
except FileNotFoundError:
    print("Arquivo debug_html_post.html não encontrado!")
    print("Execute primeiro: python debug_html.py")
    exit(1)

soup = BeautifulSoup(html, "lxml")

# 1. Procurar "quantidade registros" no contexto
print("\n[1] Contexto de 'quantidade registros':")
m = re.search(r"quantidade registros.{0,200}", html, re.I | re.DOTALL)
if m:
    print(f"    {m.group(0)[:200]}")

# 2. Procurar todos os números que aparecem perto de "registros" ou "páginas"
print("\n[2] Números próximos a 'registros' ou 'páginas':")
matches = re.findall(r".{0,30}(\d+).{0,10}(registros?|p[aá]ginas?).{0,30}", html, re.I)
for m in matches[:10]:
    print(f"    ...{m}...")

# 3. Procurar labels com números
print("\n[3] Labels e campos com números:")
for label in soup.find_all("label"):
    text = label.get_text(strip=True)
    if "registros" in text.lower() or "páginas" in text.lower() or "quantidade" in text.lower():
        # Pegar o próximo elemento
        next_elem = label.find_next_sibling()
        next_text = next_elem.get_text(strip=True) if next_elem else ""
        print(f"    Label: '{text}' | Next: '{next_text[:50]}'")

# 4. Procurar datascroller (paginação)
print("\n[4] Datascroller (paginação):")
scroller = soup.find("table", {"class": re.compile("rich-datascr", re.I)})
if scroller:
    cells = scroller.find_all("td")
    print(f"    Encontrado com {len(cells)} células")
    for cell in cells[:10]:
        text = cell.get_text(strip=True)
        if text:
            print(f"      '{text}'")
else:
    print("    Não encontrado")

# 5. Contar tabelas e suas estruturas
print("\n[5] Tabelas encontradas:")
tables = soup.find_all("table")
for i, t in enumerate(tables):
    ths = [th.get_text(strip=True)[:20] for th in t.find_all("th")]
    rows = len(t.find_all("tr"))
    if ths and rows > 1:
        print(f"    Tabela[{i}]: {rows} linhas | headers: {ths[:4]}")

# 6. Procurar o total de registros em inputs hidden
print("\n[6] Inputs hidden relevantes:")
for inp in soup.find_all("input", {"type": "hidden"}):
    name = inp.get("name", "")
    value = inp.get("value", "")
    if "total" in name.lower() or "count" in name.lower() or "size" in name.lower():
        print(f"    {name} = {value[:50]}")

# 7. Procurar spans ou divs com números grandes
print("\n[7] Elementos com números grandes (possível total):")
for elem in soup.find_all(["span", "div", "td"]):
    text = elem.get_text(strip=True)
    if re.match(r"^\d{3,4}$", text):  # 3-4 dígitos
        parent = elem.parent.get_text(strip=True)[:50] if elem.parent else ""
        print(f"    '{text}' (contexto: {parent})")

# 8. Verificar se há mensagem indicando filtro
print("\n[8] Possíveis mensagens de filtro/restrição:")
for text in ["filtro", "período", "data", "máximo", "limite"]:
    matches = re.findall(rf".{{0,50}}{text}.{{0,50}}", html, re.I)
    for m in matches[:2]:
        clean = re.sub(r"\s+", " ", m)
        print(f"    ...{clean}...")

print("\n" + "=" * 70)
