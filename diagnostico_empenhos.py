"""
AgroIA-RMC — Diagnóstico de Empenhos
====================================
Captura o texto da página para identificar o formato dos empenhos.

Execute: python diagnostico_empenhos.py
"""
import re
from playwright.sync_api import sync_playwright

FORM_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"

def main():
    print("=" * 70)
    print("DIAGNÓSTICO DE EMPENHOS")
    print("=" * 70)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=200)
        page = browser.new_page()
        
        print("\n[1] Abrindo portal...")
        page.goto(FORM_URL, timeout=60000)
        page.wait_for_load_state("networkidle")
        
        print("\n[2] Navegue até uma licitação COM EMPENHOS")
        print("    (Ex: DS 73/2019 - clique no link 'Empenhos' de um item)")
        print("    Pressione ENTER quando estiver vendo os empenhos...")
        input("\n>>> ")
        
        # Capturar texto completo
        texto = page.inner_text("body")
        
        # Salvar texto completo
        with open("debug_empenhos.txt", "w", encoding="utf-8") as f:
            f.write(texto)
        print("\n    Texto salvo em: debug_empenhos.txt")
        
        # Buscar seção de empenhos
        print("\n[3] Buscando padrões de empenhos...")
        
        # Procurar por "Número" e "Ano" e "Data Empenho"
        if "Número" in texto and "Data Empenho" in texto:
            print("    ✓ Encontrado headers de empenhos")
            
            # Mostrar contexto
            idx = texto.find("Data Empenho")
            if idx > 0:
                print("\n    Contexto (500 chars após 'Data Empenho'):")
                print("-" * 50)
                print(texto[idx:idx+500])
                print("-" * 50)
        
        # Procurar padrões de data (DD/MM/YYYY)
        datas = re.findall(r'\d{2}/\d{2}/\d{4}', texto)
        print(f"\n    Datas encontradas: {len(datas)}")
        if datas:
            print(f"    Exemplos: {datas[:5]}")
        
        # Procurar números de empenho (geralmente 4-8 dígitos)
        # Padrão: número ano data
        empenhos_pattern = re.findall(r'(\d{1,8})\s+(\d{4})\s+(\d{2}/\d{2}/\d{4})', texto)
        print(f"\n    Padrão 'número ano data': {len(empenhos_pattern)} encontrados")
        if empenhos_pattern:
            print("    Exemplos:")
            for emp in empenhos_pattern[:5]:
                print(f"      Nr: {emp[0]} | Ano: {emp[1]} | Data: {emp[2]}")
        
        print("\n[4] Texto completo (primeiros 3000 chars):")
        print("=" * 50)
        print(texto[:3000])
        print("=" * 50)
        
        print("\n[5] Pressione ENTER para fechar...")
        input()
        
        browser.close()

if __name__ == "__main__":
    main()
