"""
AgroIA-RMC — Teste de Extração de Itens (DS 73/2019)
====================================================
Testa a extração de itens em uma licitação específica
para validar se está capturando LEITE, MANDIOCA, etc.

Execute: python teste_extracao_itens.py
"""
import re
import time
from playwright.sync_api import sync_playwright

FORM_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
ORGAO = "SMSAN/FAAC"

def parse_val(t):
    try:
        return float((t or "0").strip().replace(".", "").replace(",", "."))
    except:
        return 0.0

def main():
    print("=" * 70)
    print("TESTE DE EXTRAÇÃO - DS 73/2019 (LEITE, MANDIOCA)")
    print("=" * 70)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        page = browser.new_page()
        
        # 1. Acessar e pesquisar
        print("\n[1] Acessando portal...")
        page.goto(FORM_URL, timeout=60000)
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        print("[2] Navegue até a licitação DS 73/2019 manualmente:")
        print("    1. Selecione SMSAN/FAAC")
        print("    2. Datas: 01/01/2019 a 31/12/2025")
        print("    3. Pesquise")
        print("    4. Clique na DS 73/2019 (Aquisição de produtos alimentícios)")
        input("\n    >>> Pressione ENTER quando estiver na página de DETALHE da DS 73/2019...")
        
        # 2. Extrair tabela de itens
        print("\n[3] Analisando tabela de itens...")
        
        tabelas = page.query_selector_all("table")
        print(f"    Total de tabelas: {len(tabelas)}")
        
        itens_encontrados = []
        
        for idx, tabela in enumerate(tabelas):
            headers = tabela.query_selector_all("th")
            if not headers:
                continue
            
            header_texts = [h.inner_text().strip() for h in headers]
            header_lower = [h.lower() for h in header_texts]
            
            # Identificar tabela de itens
            if "seq" in header_lower:
                print(f"\n    ★ TABELA {idx} - Headers: {header_texts}")
                
                # Mapear colunas
                col_map = {}
                for i, h in enumerate(header_lower):
                    if h == "seq":
                        col_map["seq"] = i
                    elif "código" in h or "codigo" in h:
                        col_map["codigo"] = i
                    elif "descrição" in h or "descricao" in h:
                        col_map["descricao"] = i
                    elif "qt" in h or "solicitada" in h:
                        col_map["qt"] = i
                    elif h == "un":
                        col_map["un"] = i
                    elif "valor" in h:
                        col_map["valor"] = i
                
                print(f"    Mapeamento: {col_map}")
                
                # Extrair linhas
                rows = tabela.query_selector_all("tr")
                print(f"    Linhas: {len(rows)}")
                
                for row in rows[1:]:  # Pular header
                    cells = row.query_selector_all("td")
                    if len(cells) < 3:
                        continue
                    
                    # Extrair valores
                    seq = cells[col_map.get("seq", 0)].inner_text().strip() if "seq" in col_map else ""
                    
                    if not seq.isdigit():
                        continue
                    
                    codigo = cells[col_map.get("codigo", 1)].inner_text().strip() if "codigo" in col_map else ""
                    descricao = cells[col_map.get("descricao", 2)].inner_text().strip() if "descricao" in col_map else ""
                    qt = cells[col_map.get("qt", 3)].inner_text().strip() if "qt" in col_map else ""
                    un = cells[col_map.get("un", 4)].inner_text().strip() if "un" in col_map else ""
                    valor = cells[col_map.get("valor", 5)].inner_text().strip() if "valor" in col_map else ""
                    
                    item = {
                        "seq": int(seq),
                        "codigo": codigo,
                        "descricao": descricao,
                        "qt_solicitada": parse_val(qt),
                        "unidade": un,
                        "valor": parse_val(valor),
                    }
                    itens_encontrados.append(item)
                    
                    print(f"      Item {seq}: {codigo} | {descricao[:30]} | {qt} {un} | R$ {valor}")
        
        # 3. Resumo
        print(f"\n{'='*70}")
        print(f"RESULTADO DA EXTRAÇÃO")
        print(f"{'='*70}")
        print(f"Total de itens encontrados: {len(itens_encontrados)}")
        
        if itens_encontrados:
            print("\nItens extraídos:")
            for item in itens_encontrados:
                print(f"  Seq {item['seq']:2} | {item['codigo']:18} | {item['descricao'][:25]:25} | {item['qt_solicitada']:>12,.2f} {item['unidade']:8} | R$ {item['valor']:>8,.4f}")
            
            # Verificar se tem LEITE e MANDIOCA
            descricoes = [i["descricao"].upper() for i in itens_encontrados]
            if any("LEITE" in d for d in descricoes):
                print("\n✓ LEITE encontrado!")
            else:
                print("\n✗ LEITE NÃO encontrado")
            
            if any("MANDIOCA" in d or "AIPIM" in d for d in descricoes):
                print("✓ MANDIOCA/AIPIM encontrado!")
            else:
                print("✗ MANDIOCA/AIPIM NÃO encontrado")
        else:
            print("\n✗ NENHUM ITEM ENCONTRADO - Verifique a estrutura HTML")
        
        print("\n[4] Pressione ENTER para fechar...")
        input()
        
        browser.close()

if __name__ == "__main__":
    main()
