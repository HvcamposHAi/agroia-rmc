"""
AgroIA-RMC — Teste de Extração V3 (CORRIGIDO)
=============================================
O formato real dos dados é:
- Headers em linhas separadas: Seq, Código, Descrição, etc.
- Depois de "páginas" vêm os dados
- Cada linha de dados: "2  890606027107  LEITE,  520.000,00  LITRO  2,2800  Empenhos"

Execute: python teste_extracao_v3.py
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
    """
    Extrai itens do texto da página.
    
    Formato real:
    ...
    Empenhos
    páginas
    2       890606027107    LEITE,  520.000,00      LITRO   2,2800  Empenhos
    1       890606035180    LEITE,  12.000,00       LITRO   2,2800  Empenhos
    ...
    """
    itens = []
    linhas = texto.split("\n")
    
    # Encontrar a linha que contém "páginas" - os dados começam depois dela
    inicio_dados = -1
    for i, linha in enumerate(linhas):
        if linha.strip() == "páginas":
            inicio_dados = i + 1
            break
    
    if inicio_dados == -1:
        print("    [DEBUG] Não encontrou 'páginas' como marcador")
        return itens
    
    print(f"    [DEBUG] Dados começam na linha {inicio_dados}")
    
    # Processar linhas após "páginas"
    for i in range(inicio_dados, len(linhas)):
        linha = linhas[i].strip()
        
        if not linha:
            continue
        
        # Parar se encontrar outra seção
        if linha.startswith("Fornecedores") or linha.startswith("Documentos"):
            break
        
        # Formato da linha: "2  890606027107  LEITE,  520.000,00  LITRO  2,2800  Empenhos"
        # Usar regex para extrair os campos
        
        # Padrão: seq(número) código(números) descrição quantidade unidade valor "Empenhos"
        match = re.match(
            r'^(\d+)\s+(\d+)\s+(.+?)\s+([\d.]+,\d{2})\s+(\S+)\s+([\d.]+,\d{4})\s+Empenhos',
            linha
        )
        
        if match:
            seq = int(match.group(1))
            codigo = match.group(2)
            descricao = match.group(3).strip().rstrip(",")
            qt = parse_val(match.group(4))
            un = match.group(5)
            valor = parse_val(match.group(6))
            
            itens.append({
                "seq": seq,
                "codigo": codigo,
                "descricao": descricao,
                "qt_solicitada": qt,
                "unidade_medida": un,
                "valor_unitario": valor,
            })
            continue
        
        # Tentar padrão alternativo (split por tabs/espaços múltiplos)
        partes = re.split(r'\s{2,}|\t', linha)
        
        if len(partes) >= 6 and partes[0].isdigit():
            try:
                seq = int(partes[0])
                codigo = partes[1] if partes[1].isdigit() else ""
                
                # Encontrar descrição e quantidade
                idx = 2 if codigo else 1
                descricao = partes[idx].strip().rstrip(",") if idx < len(partes) else ""
                
                # Procurar quantidade (formato XXX.XXX,XX ou XXX,XX)
                qt = 0
                un = ""
                valor = 0
                
                for j in range(idx + 1, len(partes)):
                    p = partes[j].strip()
                    if re.match(r'^[\d.]+,\d{2}$', p) and qt == 0:
                        qt = parse_val(p)
                    elif p.isupper() and len(p) <= 15 and not un:
                        un = p
                    elif re.match(r'^[\d.]+,\d{4}$', p):
                        valor = parse_val(p)
                
                if descricao and qt > 0:
                    itens.append({
                        "seq": seq,
                        "codigo": codigo,
                        "descricao": descricao,
                        "qt_solicitada": qt,
                        "unidade_medida": un,
                        "valor_unitario": valor,
                    })
            except:
                pass
    
    return itens

def main():
    print("=" * 70)
    print("TESTE DE EXTRAÇÃO V3 (CORRIGIDO)")
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
        
        # Mostrar trecho relevante
        print("\n[3] Trecho do texto capturado:")
        print("-" * 40)
        if "páginas" in texto:
            idx = texto.find("páginas")
            print(texto[idx:idx+500])
        print("-" * 40)
        
        # Extrair itens
        print("\n[4] Extraindo itens...")
        itens = extrair_itens_do_texto(texto)
        
        print(f"\n{'='*70}")
        print(f"ITENS EXTRAÍDOS: {len(itens)}")
        print(f"{'='*70}")
        
        for item in itens:
            print(f"  Seq {item['seq']:3} | {item['codigo']:15} | {item['descricao'][:25]:25} | {item['qt_solicitada']:>12,.2f} {item['unidade_medida']:8} | R$ {item['valor_unitario']:.4f}")
        
        if itens:
            print("\n✓ EXTRAÇÃO FUNCIONANDO!")
        else:
            print("\n✗ NENHUM ITEM EXTRAÍDO")
            print("\n    Verifique o formato das linhas de dados.")
        
        print("\n[5] Pressione ENTER para fechar...")
        input()
        
        browser.close()

if __name__ == "__main__":
    main()
