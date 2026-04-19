"""
AgroIA-RMC — Diagnóstico do Portal (v2)
=======================================
Testa diferentes configurações de pesquisa para descobrir
por que o portal retorna apenas 5 registros.

Execute: python diagnostico_portal.py
"""

import time
import re
from playwright.sync_api import sync_playwright

PORTAL_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
ORGAO = "SMSAN/FAAC"

def preencher_data(page, campo_id, valor):
    """Preenche campo de data via triple-click + type."""
    try:
        campo = page.locator(f"#{campo_id}")
        if campo.count() == 0:
            print(f"    [!] Campo {campo_id} não encontrado")
            return False
        campo.click(click_count=3)
        time.sleep(0.2)
        page.keyboard.type(valor, delay=50)
        time.sleep(0.3)
        page.keyboard.press("Tab")
        time.sleep(0.5)
        return True
    except Exception as e:
        print(f"    [!] Erro ao preencher {campo_id}: {e}")
        return False

def contar_registros(page):
    """Extrai total de registros do HTML."""
    html = page.content()
    # Tenta diferentes padrões
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
        val = page.locator("#form\\:dataInferiorInputDate").input_value()
        print(f"      Data inicial: {val}")
    except:
        print("      Data inicial: [não encontrado]")
    
    # Data final
    try:
        val = page.locator("#form\\:j_id18InputDate").input_value()
        print(f"      Data final: {val}")
    except:
        print("      Data final: [não encontrado]")
    
    # Órgão
    try:
        val = page.locator("select[id*='j_id9']").input_value()
        print(f"      Órgão: {val}")
    except:
        print("      Órgão: [não encontrado]")

def fazer_pesquisa(page, descricao, orgao=None, dt_ini=None, dt_fim=None):
    """Executa uma pesquisa e retorna o total."""
    print(f"\n[TEST] {descricao}")
    
    # Recarrega página
    page.goto(PORTAL_URL, timeout=60000)
    page.wait_for_load_state("networkidle")
    time.sleep(2)
    
    # Selecionar órgão
    if orgao:
        try:
            orgao_select = page.locator("select[id*='j_id9'], select[id*='orgao']")
            if orgao_select.count() > 0:
                orgao_select.first.select_option(label=orgao)
                time.sleep(1)
                print(f"    Órgão: {orgao}")
        except Exception as e:
            print(f"    [!] Erro ao selecionar órgão: {e}")
    else:
        print("    Órgão: [não selecionado]")
    
    # Preencher datas
    if dt_ini:
        preencher_data(page, "form:dataInferiorInputDate", dt_ini)
        print(f"    Data inicial: {dt_ini}")
    else:
        print("    Data inicial: [não preenchida]")
    
    if dt_fim:
        preencher_data(page, "form:j_id18InputDate", dt_fim)
        print(f"    Data final: {dt_fim}")
    else:
        print("    Data final: [não preenchida]")
    
    # Verificar valores reais
    verificar_valores_formulario(page)
    
    # Pesquisar
    btn = page.locator("#form\\:btSearch, input[value='Pesquisar']")
    if btn.count() > 0:
        btn.click()
        time.sleep(3)
        page.wait_for_load_state("networkidle", timeout=30000)
    else:
        print("    [!] Botão Pesquisar não encontrado")
        return 0
    
    # Contar resultados
    total = contar_registros(page)
    print(f"    → Resultado: {total} registros")
    
    return total

def main():
    print("=" * 70)
    print("DIAGNÓSTICO DO PORTAL — AgroIA-RMC")
    print("=" * 70)
    print("\nObjetivo: Descobrir por que a pesquisa retorna apenas 5 registros")
    print("quando deveria retornar ~1240 (licitações SMSAN/FAAC 2019-2026)")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)
        page = browser.new_page()
        
        # Teste 1: Sem filtros (total geral do portal)
        t1 = fazer_pesquisa(page, "Sem nenhum filtro",
                           orgao=None, dt_ini=None, dt_fim=None)
        
        # Teste 2: Só órgão
        t2 = fazer_pesquisa(page, "Apenas órgão SMSAN/FAAC",
                           orgao=ORGAO, dt_ini=None, dt_fim=None)
        
        # Teste 3: Órgão + período 2019-2025
        t3 = fazer_pesquisa(page, "SMSAN/FAAC + 2019-2025",
                           orgao=ORGAO, dt_ini="01/01/2019", dt_fim="31/12/2025")
        
        # Teste 4: Órgão + período 2019-2026
        t4 = fazer_pesquisa(page, "SMSAN/FAAC + 2019-2026",
                           orgao=ORGAO, dt_ini="01/01/2019", dt_fim="31/12/2026")
        
        # Teste 5: Período mais curto (último ano)
        t5 = fazer_pesquisa(page, "SMSAN/FAAC + 2025-2026",
                           orgao=ORGAO, dt_ini="01/01/2025", dt_fim="31/12/2026")
        
        # Teste 6: Período médio (2023-2026)
        t6 = fazer_pesquisa(page, "SMSAN/FAAC + 2023-2026",
                           orgao=ORGAO, dt_ini="01/01/2023", dt_fim="31/12/2026")
        
        browser.close()
    
    # Resumo
    print("\n" + "=" * 70)
    print("RESUMO DOS TESTES")
    print("=" * 70)
    print(f"  Sem filtros:           {t1:>6} registros")
    print(f"  Só SMSAN/FAAC:         {t2:>6} registros")
    print(f"  SMSAN + 2019-2025:     {t3:>6} registros")
    print(f"  SMSAN + 2019-2026:     {t4:>6} registros")
    print(f"  SMSAN + 2025-2026:     {t5:>6} registros")
    print(f"  SMSAN + 2023-2026:     {t6:>6} registros")
    print("=" * 70)
    
    # Análise
    print("\nANÁLISE:")
    if t2 > 100:
        print("  ✓ O órgão SMSAN/FAAC retorna muitos registros sem filtro de data")
        if t3 < 100 or t4 < 100:
            print("  ✗ O filtro de data está restringindo demais os resultados")
            print("    → Problema: Os campos de data podem não estar sendo preenchidos corretamente")
            print("    → Solução: Verificar se o JSF aceita as datas ou se há outro campo de data")
    elif t2 < 10:
        print("  ? SMSAN/FAAC retorna poucos registros mesmo sem data")
        print("    → Pode ser que o portal tenha mudado ou o órgão não esteja correto")
    
    if t1 > 1000:
        print(f"  ✓ Portal tem {t1} registros no total (funcionando)")
    
    print("\nPróximo passo: Execute etapa2_itens_v6.py com os ajustes")

if __name__ == "__main__":
    main()
