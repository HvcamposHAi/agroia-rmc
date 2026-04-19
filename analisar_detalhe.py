import warnings
from bs4 import XMLParsedAsHTMLWarning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

html = open('debug_detalhe_v2.html', 'r', encoding='utf-8', errors='ignore').read()

print("=== PRIMEIROS 800 CHARS BRUTOS ===")
print(repr(html[:800]))

print("\n=== BUSCA POR 'PINTURA' ===")
idx = html.find('PINTURA')
if idx >= 0:
    print(f"Encontrado na posição {idx}:")
    print(repr(html[max(0,idx-200):idx+300]))
else:
    print("NÃO ENCONTRADO")

print("\n=== BUSCA POR '<table' ===")
idx = html.lower().find('<table')
if idx >= 0:
    print(f"Primeira <table na posição {idx}:")
    print(repr(html[idx:idx+400]))
else:
    print("NÃO ENCONTRADO")

print("\n=== BUSCA POR 'CDATA' ===")
idx = html.find('CDATA')
if idx >= 0:
    print(repr(html[max(0,idx-50):idx+400]))
else:
    print("NÃO ENCONTRADO")

print("\n=== BUSCA POR 'Seq' ou 'seq' ===")
for kw in ['Seq','seq','CNPJ','cnpj','Empenho']:
    idx = html.find(kw)
    if idx >= 0:
        print(f"'{kw}' pos={idx}: {repr(html[max(0,idx-30):idx+100])}")
