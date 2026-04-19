"""
Captura o HTML da página 2 via Playwright para comparar com página 1.
Execute: python capturar_pagina2.py
"""
import asyncio
from playwright.async_api import async_playwright

FORM_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"

async def capturar():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=600)
        page = await browser.new_page()

        # Interceptar requisições XHR
        requests_log = []
        async def on_request(req):
            if "consultaProcesso" in req.url and req.method == "POST":
                try:
                    body = req.post_data or ""
                    requests_log.append({"url": req.url, "body": body})
                    print(f"\n[XHR] POST capturado ({len(body)} chars)")
                    # Mostrar só os parâmetros relevantes
                    for part in body.split("&"):
                        if any(k in part for k in ["tabela", "j_id52", "AJAX", "scroll", "btSearch", "ajaxSource"]):
                            print(f"  {part}")
                except: pass
        page.on("request", on_request)

        print("[1] Abrindo formulário...")
        await page.goto(FORM_URL, timeout=30000)
        await page.wait_for_selector("select[name='form:j_id9']", timeout=15000)
        await asyncio.sleep(1.5)

        print("[2] Selecionando SMSAN/FAAC e pesquisando...")
        await page.select_option("select[name='form:j_id9']", label="SMSAN/FAAC")
        await asyncio.sleep(1.0)
        await page.fill("#form\\:dataInferiorInputDate", "01/01/2019")
        await page.fill("#form\\:j_id18InputDate", "31/12/2025")
        await asyncio.sleep(0.5)
        await page.click("#form\\:btSearch")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(3)

        # Salvar página 1
        html1 = await page.content()
        with open("pagina1.html", "w", encoding="utf-8") as f:
            f.write(html1)
        print("[3] Página 1 salva em pagina1.html")

        print("\n[4] Clicando na página 2...")
        try:
            await page.click("td.rich-datascr-inact:has-text('2')")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(3)
            html2 = await page.content()
            with open("pagina2.html", "w", encoding="utf-8") as f:
                f.write(html2)
            print("[5] Página 2 salva em pagina2.html")
        except Exception as e:
            print(f"[!] Erro ao clicar página 2: {e}")
            # Tentar via onclick
            try:
                await page.evaluate("document.querySelector('td.rich-datascr-inact').click()")
                await asyncio.sleep(3)
                html2 = await page.content()
                with open("pagina2.html", "w", encoding="utf-8") as f:
                    f.write(html2)
                print("[5] Página 2 salva via evaluate")
            except Exception as e2:
                print(f"[!] Também falhou: {e2}")

        print("\n[6] Requisições XHR capturadas:")
        for i, req in enumerate(requests_log):
            print(f"\n  Requisição {i+1}:")
            for part in req["body"].split("&"):
                if any(k in part for k in ["tabela","j_id52","AJAX","scroll","btSearch","ajaxSource","j_id253"]):
                    import urllib.parse
                    print(f"    {urllib.parse.unquote(part)}")

        print("\n[7] Browser aberto 20s para inspeção...")
        await asyncio.sleep(20)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(capturar())
