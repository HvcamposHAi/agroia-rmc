"""
Captura as requisições XHR ao clicar em um processo para ver o detalhe.
Execute: python capturar_detalhe.py
"""
import asyncio
from playwright.async_api import async_playwright
import urllib.parse

FORM_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"

async def capturar():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=600)
        page    = await browser.new_page()

        requests_log = []

        async def on_request(req):
            if "consultaProcesso" in req.url and req.method == "POST":
                try:
                    body = req.post_data or ""
                    requests_log.append({"url": req.url, "body": body, "n": len(requests_log)+1})
                    print(f"\n[XHR #{len(requests_log)}] POST ({len(body)} chars)")
                    # Mostrar params relevantes
                    params = {}
                    for part in body.split("&"):
                        if "=" in part:
                            k, v = part.split("=", 1)
                            params[urllib.parse.unquote(k)] = urllib.parse.unquote(v)[:80]
                    # Mostrar só os não-padrão
                    ignorar = {"AJAXREQUEST","form:tabs","form:j_id6","form:j_id9",
                               "form:j_id12","form:j_id15","form:dataInferiorInputDate",
                               "form:dataInferiorInputCurrentDate","form:j_id18InputDate",
                               "form:j_id18InputCurrentDate","form:fornecedoresEditalOpenedState",
                               "form:fornecedoresParticipantesOpenedState",
                               "form:observacoesItemOpenedState","form:j_id253",
                               "form:messagesOpenedState","form:waitOpenedState",
                               "form:empenhosProcCompraOpenedState","form:documentosOpenedState",
                               "form","autoScroll","javax.faces.ViewState"}
                    for k, v in params.items():
                        if k not in ignorar:
                            print(f"  EXTRA: {k} = {v}")
                except Exception as e:
                    print(f"  Erro ao ler request: {e}")

        page.on("request", on_request)

        print("[1] Abrindo formulário...")
        await page.goto(FORM_URL, timeout=30000)
        await page.wait_for_selector("select[name='form:j_id9']", timeout=15000)
        await asyncio.sleep(1.5)

        print("[2] Pesquisando SMSAN/FAAC...")
        await page.select_option("select[name='form:j_id9']", label="SMSAN/FAAC")
        await asyncio.sleep(1.0)
        await page.fill("#form\\:dataInferiorInputDate", "01/01/2019")
        await page.fill("#form\\:j_id18InputDate", "31/12/2025")
        await asyncio.sleep(0.5)
        await page.click("#form\\:btSearch")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(3)
        print(f"    Pesquisa feita. {len(requests_log)} requisições até agora.\n")

        print("[3] Clicando no primeiro processo (AD 3/2019)...")
        requests_log.clear()

        try:
            await page.click("a:has-text('AD 3/2019')")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(3)
        except Exception as e:
            print(f"  Erro: {e}")
            await page.click("td.rich-table-cell >> a >> nth=0")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(3)

        print(f"\n[4] Requisições capturadas após clicar no processo: {len(requests_log)}")
        for req in requests_log:
            print(f"\n  === Requisição #{req['n']} ({len(req['body'])} chars) ===")
            params = {}
            for part in req['body'].split("&"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    params[urllib.parse.unquote(k)] = urllib.parse.unquote(v)[:100]
            for k, v in params.items():
                print(f"    {k} = {v}")

        # Salvar HTML do detalhe
        html = await page.content()
        with open("debug_detalhe_playwright.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\n[5] HTML do detalhe salvo ({len(html)} chars)")
        print("    Tem 'PINTURA':", 'PINTURA' in html)
        print("    Tem '<table':", '<table' in html.lower())

        print("\n[6] Browser aberto 20s para inspeção...")
        await asyncio.sleep(20)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(capturar())
