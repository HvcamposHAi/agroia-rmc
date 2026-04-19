"""
AgroIA-RMC — Teste de Extração (uma licitação)
==============================================
Testa a extração de itens em uma licitação específica
para validar o algoritmo.

Execute: python teste_extracao_v2.py
"""
import re
from playwright.sync_api import sync_playwright

FORM_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"

def parse_val(t):
    try:
        return float((t or "0").strip().replace(".", "").replace(",", "."))
    except:
        return 0.0

def extrair_itens_do_texto(texto):
    """Extrai itens do texto da página."""
    itens = []
    linhas = texto.split("\n")
    
    em_itens = False
    
    for linha in linhas:
        linha = linha.strip()
        
        # Detectar início da tabela de itens
        if "Seq" in linha and "Código" in linha:
            em_itens = True
            continue
        
        # Parar quando encontrar "páginas" ou "Fornecedores"
        if em_itens and ("páginas" in linha.lower() or linha.startswith("Fornecedores")):
            break
        
        if not em_itens:
            continue
        
        # Parsear linha de item
        partes = linha.split()
        
        if len(partes) < 4:
            continue
        
        # Primeira parte deve ser número (seq)
        if not partes[0].isdigit():
            continue
        
        seq = int(partes[0])
        
        # Segunda parte é o código
        codigo = ""
        idx = 1
        
        if len(partes) > 1 and (partes[1].isdigit() or re.match(r'^\d{6,}', partes[1])):
            codigo = partes[1]
            idx = 2
        
        # Coletar descrição até encontrar número decimal (qt_solicitada)
        desc_parts = []
        while idx < len(partes):
            if re.match(r'^[\d.]+,\d{2}$', partes[idx]):
                break
            desc_parts.append(partes[idx])
            idx += 1
        
        descricao = " ".join(desc_parts).strip().rstrip(",")
        
        if not descricao:
            continue
        
        # Quantidade solicitada
        qt = 0
        if idx < len(partes):
            qt = parse_val(partes[idx])
            idx += 1
        
        # Unidade
        un = ""
        if idx < len(partes):
            un = partes[idx]
            idx += 1
        
        # Valor
        valor = 0
        if idx < len(partes):
            valor = parse_val(partes[idx])
        
        itens.append({
            "seq": seq,
            "codigo": codigo,
            "descricao": descricao,
            "qt_solicitada": qt,
            "unidade_medida": un,
            "valor_unitario": valor,
        })
    
    return itens

def main():
    print("=" * 70)
    print("TESTE DE EXTRAÇÃO V2")
    print("=" * 70)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=200)
        page = browser.new_page()
        
        print("\n[1] Abrindo portal...")
        page.goto(FORM_URL, timeout=60000)
        page.wait_for_load_state("networkidle")
        
        print("\n[2] Navegue até a DS 73/2019 (com LEITE, MANDIOCA)")
        print("    Pressione ENTER quando estiver na página de DETALHE...")
        input("\n>>> ")
        
        # Extrair texto
        texto = page.inner_text("body")
        
        # Extrair itens
        print("\n[3] Extraindo itens...")
        itens = extrair_itens_do_texto(texto)
        
        print(f"\n{'='*70}")
        print(f"ITENS EXTRAÍDOS: {len(itens)}")
        print(f"{'='*70}")
        
        for item in itens:
            print(f"  Seq {item['seq']:3} | {item['codigo']:15} | {item['descricao'][:25]:25} | {item['qt_solicitada']:>12,.2f} {item['unidade_medida']:8} | R$ {item['valor_unitario']:.4f}")
        
        if itens:
            print("\n✓ EXTRAÇÃO FUNCIONANDO!")
            
            # Verificar culturas específicas
            descricoes = [i["descricao"].upper() for i in itens]
            if any("LEITE" in d for d in descricoes):
                print("✓ LEITE encontrado!")
            if any("MANDIOCA" in d or "AIPIM" in d for d in descricoes):
                print("✓ MANDIOCA/AIPIM encontrado!")
        else:
            print("\n✗ NENHUM ITEM EXTRAÍDO")
            print("\nTexto capturado (primeiros 1500 chars):")
            print("-" * 40)
            print(texto[:1500])
            print("-" * 40)
        
        print("\n[4] Pressione ENTER para fechar...")
        input()
        
        browser.close()

if __name__ == "__main__":
    main()
