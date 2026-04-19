"""
AgroIA-RMC — Diagnóstico do Select de Órgão
===========================================
Lista TODAS as opções do select para encontrar SMSAN/FAAC.

Execute: python debug_select.py
"""
import asyncio
from playwright.async_api import async_playwright

FORM_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"

async def main():
    print("=" * 70)
    print("LISTANDO TODAS AS OPÇÕES DO SELECT DE ÓRGÃO")
    print("=" * 70)
    
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto(FORM_URL, timeout=30000)
        await page.wait_for_selector("select[name='form:j_id9']", timeout=15000)
        
        # Listar TODAS as opções
        options = await page.locator("select[name='form:j_id9'] option").all()
        
        print(f"\nTotal de opções: {len(options)}\n")
        print(f"{'VALUE':<30} | LABEL (texto visível)")
        print("-" * 70)
        
        smsan_encontrado = None
        for opt in options:
            text = (await opt.text_content() or "").strip()
            value = (await opt.get_attribute("value") or "").strip()
            
            # Destacar se contém SMSAN, FAAC, SEGURANÇA ALIMENTAR, etc.
            if any(x in value.upper() or x in text.upper() for x in ["SMSAN", "FAAC", "SEGURANÇA ALIMENTAR", "ABASTECIMENTO"]):
                print(f">>> {value:<27} | {text[:50]}")
                smsan_encontrado = {"value": value, "label": text}
            else:
                print(f"    {value:<27} | {text[:50]}")
        
        print("\n" + "=" * 70)
        if smsan_encontrado:
            print(f"ENCONTRADO!")
            print(f"  VALUE: {smsan_encontrado['value']}")
            print(f"  LABEL: {smsan_encontrado['label']}")
            print(f"\nUse no código:")
            print(f"  await page.select_option(\"select[name='form:j_id9']\", value=\"{smsan_encontrado['value']}\")")
        else:
            print("NÃO ENCONTRADO - verifique manualmente a lista acima")
        print("=" * 70)
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
