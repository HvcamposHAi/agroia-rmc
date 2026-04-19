"""
AgroIA-RMC — Diagnóstico da Pesquisa no Portal
==============================================
Verifica se a pesquisa está funcionando corretamente.

Execute: python debug_pesquisa.py
"""
import asyncio
import re
from playwright.async_api import async_playwright

FORM_URL  = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
ORGAO     = "SMSAN/FAAC"
DT_INICIO = "01/01/2019"
DT_FIM    = "31/12/2025"

async def main():
    print("=" * 60)
    print("DIAGNÓSTICO DA PESQUISA NO PORTAL")
    print("=" * 60)
    
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False, slow_mo=500)
        page = await browser.new_page()
        
        # 1. Abrir página
        print("\n[1] Abrindo portal...")
        await page.goto(FORM_URL, timeout=30000)
        await page.wait_for_selector("select[name='form:j_id9']", timeout=15000)
        await asyncio.sleep(2)
        
        # 2. Verificar opções do select de órgão
        print("\n[2] Opções disponíveis no select de órgão:")
        options = await page.locator("select[name='form:j_id9'] option").all()
        orgao_encontrado = False
        for opt in options[:20]:  # Mostrar primeiras 20
            text = await opt.text_content()
            value = await opt.get_attribute("value")
            if ORGAO in text:
                print(f"    >>> {text} (value={value}) <<<")
                orgao_encontrado = True
            else:
                print(f"    {text[:50]}")
        
        if not orgao_encontrado:
            print(f"\n    [!] ATENÇÃO: '{ORGAO}' não encontrado nas opções!")
            print("    Verifique o nome correto do órgão.")
        
        # 3. Verificar valores atuais dos campos de data
        print("\n[3] Valores atuais dos campos:")
        dt_ini_val = await page.locator("#form\\:dataInferiorInputDate").input_value()
        dt_fim_val = await page.locator("#form\\:j_id18InputDate").input_value()
        print(f"    Data início: '{dt_ini_val}'")
        print(f"    Data fim: '{dt_fim_val}'")
        
        # 4. Selecionar órgão
        print(f"\n[4] Selecionando órgão '{ORGAO}'...")
        try:
            await page.select_option("select[name='form:j_id9']", label=ORGAO)
            await asyncio.sleep(1)
            selected = await page.locator("select[name='form:j_id9']").input_value()
            print(f"    Valor selecionado: {selected}")
        except Exception as e:
            print(f"    [!] ERRO ao selecionar: {e}")
            # Tentar com value em vez de label
            print("    Tentando selecionar por texto parcial...")
            opts = await page.locator("select[name='form:j_id9'] option").all()
            for opt in opts:
                txt = await opt.text_content()
                if "SMSAN" in txt or "FAAC" in txt:
                    val = await opt.get_attribute("value")
                    print(f"    Encontrado: '{txt}' (value={val})")
                    await page.select_option("select[name='form:j_id9']", value=val)
                    break
        
        # 5. Limpar e preencher datas
        print(f"\n[5] Preenchendo datas ({DT_INICIO} a {DT_FIM})...")
        
        # Data início - limpar completamente
        await page.locator("#form\\:dataInferiorInputDate").click()
        await page.keyboard.press("Control+a")
        await page.keyboard.press("Delete")
        await page.keyboard.type(DT_INICIO)
        await asyncio.sleep(0.5)
        
        # Data fim - limpar completamente
        await page.locator("#form\\:j_id18InputDate").click()
        await page.keyboard.press("Control+a")
        await page.keyboard.press("Delete")
        await page.keyboard.type(DT_FIM)
        await asyncio.sleep(0.5)
        
        # Verificar valores após preenchimento
        dt_ini_new = await page.locator("#form\\:dataInferiorInputDate").input_value()
        dt_fim_new = await page.locator("#form\\:j_id18InputDate").input_value()
        print(f"    Data início agora: '{dt_ini_new}'")
        print(f"    Data fim agora: '{dt_fim_new}'")
        
        # 6. Clicar em Pesquisar
        print("\n[6] Clicando em Pesquisar...")
        await page.click("#form\\:btSearch")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(3)
        
        # 7. Verificar resultado
        print("\n[7] Resultado da pesquisa:")
        html = await page.content()
        
        # Extrair total de registros
        m = re.search(r"quantidade registros.*?(\d+)", html, re.I | re.DOTALL)
        if m:
            print(f"    Total de registros: {m.group(1)}")
        else:
            print("    [!] Não encontrou 'quantidade registros' no HTML")
            # Procurar outras indicações
            m2 = re.search(r"(\d+)\s*registros", html, re.I)
            if m2:
                print(f"    Encontrou '{m2.group(0)}'")
        
        # Extrair páginas
        m3 = re.search(r"(\d+)\s*p[aá]ginas?", html, re.I)
        if m3:
            print(f"    Total de páginas: {m3.group(1)}")
        
        # Contar linhas na tabela
        rows = await page.locator("table tr").count()
        print(f"    Linhas na tabela: {rows}")
        
        # Mostrar primeiros processos
        print("\n[8] Primeiros processos encontrados:")
        links = await page.locator("a").all()
        count = 0
        for link in links:
            text = await link.text_content()
            if text and re.match(r"^[A-Z]{2}\s+\d+/\d{4}", text.strip()):
                print(f"    {text.strip()}")
                count += 1
                if count >= 5:
                    break
        
        if count == 0:
            print("    [!] Nenhum processo encontrado na página!")
        
        # 9. Aguardar para inspeção visual
        print("\n" + "=" * 60)
        print("AGUARDANDO 30 SEGUNDOS PARA INSPEÇÃO VISUAL...")
        print("Verifique na tela se a pesquisa retornou resultados.")
        print("=" * 60)
        await asyncio.sleep(30)
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
