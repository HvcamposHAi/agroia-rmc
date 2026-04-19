import re

content = open('debug_pesquisa.html', 'r', encoding='utf-8', errors='ignore').read()

print("=== LINKS DE PAGINAÇÃO ===")
# Padrão Ajax4jsf para links numéricos
links = re.findall(r"'(form:[^']*?)':\s*'(form:[^']*?)'[^>]*>\s*(\d+)\s*</a", content)
for l in links[:20]:
    print(l)

print("\n=== TODOS OS LINKS COM NÚMEROS ===")
# Mais amplo
links2 = re.findall(r"id=\"(form:[^\"]+)\"[^>]*>[^<]*(\d+)[^<]*</a", content)
for l in links2[:20]:
    print(l)

print("\n=== TRECHO DO PAGINADOR ===")
idx = content.find('páginas')
if idx > 0:
    print(content[idx:idx+800])
