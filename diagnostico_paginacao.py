"""
Diagnóstico: Entender a estrutura real da paginação RichFaces
Inspeciona o HTML para encontrar o seletor correto do botão "próxima"
"""

import os
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

load_dotenv()

PORTAL_URL = (
    "http://consultalicitacao.curitiba.pr.gov.br:9090/"
    "ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
)

print("=" * 80)
print("DIAGNÓSTICO: Paginação RichFaces")
print("=" * 80)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=80)
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()

    print("\n[1] Acessando portal...")
    page.goto(PORTAL_URL, wait_until='domcontentloaded')
    time.sleep(2)

    print("[2] Fazendo pesquisa...")
    try:
        page.wait_for_selector("select", state="visible", timeout=20000)
    except:
        pass
    time.sleep(1)

    # Selecionar órgão
    selects = page.locator("select")
    for i in range(selects.count()):
        sel = selects.nth(i)
        try:
            if sel.locator('option:has-text("SMSAN/FAAC")').count() > 0:
                sel.select_option(label='SMSAN/FAAC')
                time.sleep(1)
                break
        except:
            continue

    # Pesquisar
    btn = page.locator('[id="form:btSearch"], input[value="Pesquisar"]')
    if btn.count() > 0:
        btn.first.click()
        time.sleep(3)
        try:
            page.wait_for_load_state("networkidle", timeout=30000)
        except:
            pass

    print("[3] Página de resultados carregada")
    print("\n[4] Analisando estrutura de paginação...")

    # Capturar e salvar HTML
    html = page.content()

    # Buscar diferentes padrões de paginação
    soup = BeautifulSoup(html, 'lxml')

    print("\n" + "=" * 80)
    print("ANÁLISE DE ESTRUTURA")
    print("=" * 80)

    # 1. Procurar por datascroller
    datascroller = soup.find('div', class_='rich-datascroller')
    if datascroller:
        print("\n[OK] Encontrado: <div class='rich-datascroller'>")
        print("  Conteudo:")
        print(datascroller.prettify()[:1000])
    else:
        print("\n[NOT] Nao encontrado: <div class='rich-datascroller'>")

    # 2. Procurar por botões com classe rich-datascr
    buttons = soup.find_all('td', class_='rich-datascr-button')
    if buttons:
        print(f"\n[OK] Encontrados {len(buttons)} botoes com 'rich-datascr-button':")
        for i, btn in enumerate(buttons):
            print(f"  [{i}] {btn}")
    else:
        print("\n[NOT] Nao encontrados botoes com 'rich-datascr-button'")

    # 3. Procurar por links de paginação
    links = soup.find_all('a', onclick=True)
    pag_links = [l for l in links if 'scrollerState' in str(l.get('onclick', ''))]
    if pag_links:
        print(f"\n[OK] Encontrados {len(pag_links)} links com 'scrollerState':")
        for i, link in enumerate(pag_links[:5]):
            print(f"  [{i}] {link}")
    else:
        print("\n[NOT] Nao encontrados links com 'scrollerState'")

    # 4. Procurar por qualquer elemento que contenha "próxima" ou ">"
    all_text = soup.get_text()
    if "prxima" in all_text.lower() or "próxima" in all_text.lower():
        print("\n[OK] Encontrado texto 'proxima' na pagina")
    if ">" in all_text:
        print("[OK] Encontrado simbolo '>' na pagina")

    # 5. Procurar por form hidden fields
    hidden_fields = soup.find_all('input', type='hidden')
    print(f"\n[OK] Encontrados {len(hidden_fields)} campos hidden")
    print("  Campos importantes:")
    for field in hidden_fields[:10]:
        name = field.get('name', '')
        if 'scroller' in name.lower() or 'page' in name.lower():
            print(f"    - {name}")

    # 6. Salvar HTML para inspeção manual
    with open("pagina_pesquisa.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("\n[5] HTML salvo em: pagina_pesquisa.html")

    print("\n" + "=" * 80)
    print("SELETORES TESTADOS:")
    print("=" * 80)

    # Testar diferentes seletores
    seletores = [
        ('td.rich-datascr-button:has-text(">")', "RichFaces botão >"),
        ('a:has-text(">")', "Link com >"),
        ('a:has-text("Próxima")', "Link com texto Próxima"),
        ('td.rich-datascr-button', "Todos os botões datascr"),
        ('[onclick*="scrollerState"]', "Elementos com scrollerState"),
    ]

    for seletor, descricao in seletores:
        locator = page.locator(seletor)
        count = locator.count()
        print(f"\n[TEST] {descricao}")
        print(f"  Seletor: {seletor}")
        print(f"  Encontrados: {count}")
        if count > 0:
            try:
                attr_class = locator.first.get_attribute("class")
                attr_onclick = locator.first.get_attribute("onclick")
                print(f"  Class: {attr_class}")
                if attr_onclick:
                    print(f"  OnClick: {attr_onclick[:100]}...")
            except:
                pass

    print("\n" + "=" * 80)
    browser.close()

print("\n[PRÓXIMO] Verifique o arquivo 'pagina_pesquisa.html' para mais detalhes")
