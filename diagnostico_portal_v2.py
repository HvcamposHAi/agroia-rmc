"""
AgroIA-RMC — Diagnóstico do Portal (v2 - CORRIGIDO)
===================================================
Correção: Seletores CSS com ':' precisam usar [id="..."] em vez de #id

Execute: python diagnostico_portal_v2.py
"""

import time
import re
from playwright.sync_api import sync_playwright

PORTAL_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
ORGAO = "SMSAN/FAAC"

def preencher_data(page, campo_id, valor):
    """Preenche campo de data via triple-click + type.
    
    IMPORTANTE: Usar [id="..."] em vez de #id quando o ID contém ':'
    """
    try:
        # Seletor correto para IDs com ':' (JSF gera IDs como form:campo)
        campo = page.locator(f'[id="{campo_id}"]')
        if campo.count() == 0:
            print(f"    [!] Campo {campo_id} não encontrado")
            return False
        
        campo.click(click_count=3)  # Seleciona todo o texto
        time.sleep(0.2)
        page.keyboard.type(valor, delay=50)
        time.sleep(0.3)
        page.keyboard.press("Tab")  # Dispara evento onchange do JSF
        time.sleep(0.5)
        return True
    except Exception as e:
        print(f"    [!] Erro ao preencher {campo_id}: {e}")
        return False

def contar_registros(page):
    """Extrai total de registros do HTML."""
    html = page.content()
    patterns = [
        r'\b(\d+)\s+quantidade\s+registros\b',
        r'quantidade\s+registros[:\s]*(\d+)',
        r'(\d+)\s+registros',
        r'registros[:\s]*(\d+)'
    ]
    for p in patterns:
        m = re.search(p, html, re.I)
        if m:
            return int(m.group(1))
    return 0

def verificar_valores_formulario(page):
    """Verifica os valores atuais dos campos do formulário."""
    print("\n    Valores do formulário após preenchimento:")
    
    # Data inicial
    try:
        campo = page.locator('[id="form:dataInferiorInputDate"]')
        if campo.count() > 0:
            val = campo.input_value()
            print(f"      Data inicial: {val}")
        else:
            print("      Data inicial: [campo não encontrado]")
    except Exception as e:
        print(f"      Data inicial: [erro: {e}]")
    
    # Data final
    try:
        campo = page.locator('[id="form:j_id18InputDate"]')
        if campo.count() > 0:
            val = campo.input_value()
            print(f"      Data final: {val}")
        else:
            print("      Data final: [campo não encontrado]")
    except Exception as e:
        print(f"      Data final: [erro: {e}]")
    
    # Órgão (select)
    try:
        # Tenta diferentes seletores para o órgão
        selects = page.locator("select")
        for i in range(selects.count()):
            sel = selects.nth(i)
            sel_id = sel.get_attribute("id") or ""
            if "j_id9" in sel_id or "orgao" in sel_id.lower():
                val = sel.input_value()
                texto = sel.locator(f'option[value="{val}"]').text_content() if val else "[vazio]"
                print(f"      Órgão ({sel_id}): {texto}")
                break
        else:
            print("      Órgão: [select não encontrado]")
    except Exception as e:
        print(f"      Órgão: [erro: {e}]")

def listar_campos_formulario(page):
    """Lista todos os campos do formulário para diagnóstico."""
    print("\n    Campos encontrados no formulário:")
    
    # Inputs
    inputs = page.locator("input[type='text']")
    for i in range(min(inputs.count(), 10)):
        inp = inputs.nth(i)
        inp_id = inp.get_attribute("id") or "[sem id]"
        inp_name = inp.get_attribute("name") or "[sem name]"
        inp_val = inp.input_value() or "[vazio]"
        print(f"      INPUT: id={inp_id} | name={inp_name} | valor={inp_val}")
    
    # Selects
    selects = page.locator("select")
    for i in range(min(selects.count(), 5)):
        sel = selects.nth(i)
        sel_id = sel.get_attribute("id") or "[sem id]"
        sel_name = sel.get_attribute("name") or "[sem name]"
        print(f"      SELECT: id={sel_id} | name={sel_name}")
        # Listar algumas opções
        options = sel.locator("option")
        for j in range(min(options.count(), 5)):
            opt = options.nth(j)
            opt_val = opt.get_attribute("value") or ""
            opt_txt = opt.text_content() or ""
            if "SMSAN" in opt_txt or "FAAC" in opt_txt:
                print(f"        → OPÇÃO SMSAN: value={opt_val} | text={opt_txt}")

def fazer_pesquisa(page, descricao, orgao=None, dt_ini=None, dt_fim=None, listar_campos=False):
    """Executa uma pesquisa e retorna o total."""
    print(f"\n{'='*70}")
    print(f"[TEST] {descricao}")
    print("="*70)
    
    # Recarrega página
    page.goto(PORTAL_URL, timeout=60000)
    page.wait_for_load_state("networkidle")
    time.sleep(2)
    
    # Listar campos (primeira vez apenas)
    if listar_campos:
        listar_campos_formulario(page)
    
    # Selecionar órgão
    if orgao:
        try:
            # Encontrar o select de órgão
            selects = page.locator("select")
            orgao_encontrado = False
            for i in range(selects.count()):
                sel = selects.nth(i)
                # Verifica se tem a opção SMSAN/FAAC
                if sel.locator(f'option:has-text("{orgao}")').count() > 0:
                    sel.select_option(label=orgao)
                    time.sleep(1)
                    print(f"    ✓ Órgão selecionado: {orgao}")
                    orgao_encontrado = True
                    break
            
            if not orgao_encontrado:
                print(f"    [!] Órgão {orgao} não encontrado nos selects")
        except Exception as e:
            print(f"    [!] Erro ao selecionar órgão: {e}")
    else:
        print("    Órgão: [não selecionado]")
    
    # Preencher datas
    if dt_ini:
        ok = preencher_data(page, "form:dataInferiorInputDate", dt_ini)
        print(f"    {'✓' if ok else '✗'} Data inicial: {dt_ini}")
    else:
        print("    Data inicial: [não preenchida]")
    
    if dt_fim:
        ok = preencher_data(page, "form:j_id18InputDate", dt_fim)
        print(f"    {'✓' if ok else '✗'} Data final: {dt_fim}")
    else:
        print("    Data final: [não preenchida]")
    
    # Verificar valores reais
    verificar_valores_formulario(page)
    
    # Pesquisar
    btn = page.locator('[id="form:btSearch"], input[value="Pesquisar"]')
    if btn.count() > 0:
        btn.first.click()
        print("\n    Clicando em Pesquisar...")
        time.sleep(3)
        page.wait_for_load_state("networkidle", timeout=30000)
    else:
        print("    [!] Botão Pesquisar não encontrado")
        return 0
    
    # Contar resultados
    total = contar_registros(page)
    print(f"\n    → RESULTADO: {total} registros")
    
    return total

def main():
    print("=" * 70)
    print("DIAGNÓSTICO DO PORTAL — AgroIA-RMC (v2 - Seletores Corrigidos)")
    print("=" * 70)
    print("\nObjetivo: Verificar se os campos estão sendo preenchidos corretamente")
    print("Correção: Usando [id=\"...\"] em vez de #id para IDs com ':'")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)
        page = browser.new_page()
        
        # Teste 1: Sem filtros + listar campos
        t1 = fazer_pesquisa(page, "Sem nenhum filtro (listar campos)",
                           orgao=None, dt_ini=None, dt_fim=None,
                           listar_campos=True)
        
        # Teste 2: Só órgão
        t2 = fazer_pesquisa(page, "Apenas órgão SMSAN/FAAC",
                           orgao=ORGAO, dt_ini=None, dt_fim=None)
        
        # Teste 3: Órgão + período completo
        t3 = fazer_pesquisa(page, "SMSAN/FAAC + 01/01/2019 → 31/12/2026",
                           orgao=ORGAO, dt_ini="01/01/2019", dt_fim="31/12/2026")
        
        # Teste 4: Período mais curto para testar
        t4 = fazer_pesquisa(page, "SMSAN/FAAC + 01/01/2025 → 31/03/2026",
                           orgao=ORGAO, dt_ini="01/01/2025", dt_fim="31/03/2026")
        
        browser.close()
    
    # Resumo
    print("\n" + "=" * 70)
    print("RESUMO DOS TESTES")
    print("=" * 70)
    print(f"  Sem filtros:             {t1:>6} registros")
    print(f"  Só SMSAN/FAAC:           {t2:>6} registros")
    print(f"  SMSAN + 2019-2026:       {t3:>6} registros")
    print(f"  SMSAN + 2025-mar/2026:   {t4:>6} registros")
    print("=" * 70)
    
    # Análise
    print("\nANÁLISE:")
    if t2 > 100:
        print(f"  ✓ SMSAN/FAAC retorna {t2} registros - órgão está funcionando!")
    elif t2 > 0:
        print(f"  ? SMSAN/FAAC retorna {t2} registros - verificar se é o esperado")
    else:
        print("  ✗ SMSAN/FAAC retorna 0 - problema com seleção de órgão")
    
    if t3 > t2:
        print(f"  ✓ Filtro de data está expandindo resultados ({t2} → {t3})")
    elif t3 < t2 and t3 > 0:
        print(f"  ⚠ Filtro de data está restringindo resultados ({t2} → {t3})")
    elif t3 == 0 and t2 > 0:
        print("  ✗ Filtro de data está zerando resultados - verificar formato")

if __name__ == "__main__":
    main()
