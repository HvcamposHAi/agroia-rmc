"""
TESTE: Processar apenas 1 licitação
"""
import os
import re
import time
from datetime import datetime
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

FORM_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"

def parse_val(t):
    try:
        return float((t or "0").strip().replace(".", "").replace(",", "."))
    except:
        return 0.0

def extrair_itens(texto):
    itens = []
    linhas = texto.split("\n")
    
    inicio = -1
    for i, linha in enumerate(linhas):
        if linha.strip() == "páginas":
            inicio = i + 1
            break
    
    if inicio == -1:
        return itens
    
    for i in range(inicio, len(linhas)):
        linha = linhas[i].strip()
        if not linha:
            continue
        if linha.startswith("Fornecedores") or linha.startswith("Documentos") or linha.startswith("Empenhos"):
            break
        
        match = re.match(
            r'^(\d+)\s+(\d+)\s+(.+?)\s+([\d.]+,\d{2})\s+(\S+)\s+([\d.]+,\d{4})\s+Empenhos',
            linha
        )
        
        if match:
            itens.append({
                "seq": int(match.group(1)),
                "codigo": match.group(2),
                "descricao": match.group(3).strip().rstrip(","),
                "qt_solicitada": parse_val(match.group(4)),
                "unidade_medida": match.group(5),
                "valor_unitario": parse_val(match.group(6)),
            })
    
    return itens

def main():
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    print("=" * 50)
    print("TESTE: PROCESSAR 1 LICITAÇÃO")
    print("=" * 50)
    
    # Carregar mapa
    dados = sb.table("licitacoes").select("id,processo").eq("orgao", "SMSAN/FAAC").execute().data
    mapa = {d["processo"]: d["id"] for d in dados}
    print(f"\n{len(mapa)} licitações no banco")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        page = browser.new_page()
        
        print("\nAcessando portal...")
        page.goto(FORM_URL, timeout=60000)
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        # Filtros
        print("Preenchendo filtros...")
        page.evaluate("""() => {
            var selects = document.querySelectorAll('select');
            for (var s of selects) {
                for (var opt of s.options) {
                    if (opt.text.includes('SMSAN/FAAC')) {
                        s.value = opt.value;
                        s.dispatchEvent(new Event('change', { bubbles: true }));
                        break;
                    }
                }
            }
            var inputs = document.querySelectorAll('input[type="text"]');
            for (var inp of inputs) {
                if (inp.id && inp.id.includes('dataInferior') && inp.id.includes('Input')) {
                    inp.value = '01/01/2019';
                }
                if (inp.id && inp.id.includes('j_id18') && inp.id.includes('Input')) {
                    inp.value = '31/12/2026';
                }
            }
        }""")
        time.sleep(1)
        
        page.click("input[value='Pesquisar']")
        page.wait_for_timeout(4000)
        
        # Mostrar processos da página 1
        print("\nProcessos na página 1:")
        links = page.query_selector_all("a[id*='tabela'][id*='j_id26']")
        
        processos_portal = []
        for link in links:
            proc = link.inner_text().strip()
            processos_portal.append(proc)
            no_banco = proc in mapa
            print(f"  '{proc}' -> no banco: {no_banco}")
        
        # Encontrar primeiro que está no banco
        alvo = None
        for proc in processos_portal:
            if proc in mapa:
                alvo = proc
                break
        
        if not alvo:
            print("\nNenhum processo da página 1 está no banco!")
            print("Pressione ENTER para fechar...")
            input()
            browser.close()
            return
        
        print(f"\n>>> Processando: {alvo}")
        lic_id = mapa[alvo]
        print(f"    ID no banco: {lic_id}")
        
        # Clicar no link
        print("    Clicando no link...")
        links = page.query_selector_all("a[id*='tabela'][id*='j_id26']")
        for link in links:
            if link.inner_text().strip() == alvo:
                link.click()
                break
        
        page.wait_for_timeout(3000)
        
        # Extrair itens
        print("    Extraindo itens...")
        texto = page.inner_text("body")
        itens = extrair_itens(texto)
        
        print(f"    Encontrados: {len(itens)} itens")
        
        if itens:
            for item in itens[:3]:
                print(f"      - {item['codigo']} | {item['descricao'][:30]}")
            
            # Gravar
            print("    Gravando no banco...")
            for item in itens:
                item["licitacao_id"] = lic_id
                item["cultura"] = "outro"
                item["categoria"] = "OUTRO"
                item["valor_total"] = item["qt_solicitada"] * item["valor_unitario"]
                try:
                    sb.table("itens_licitacao").upsert(item, on_conflict="licitacao_id,seq").execute()
                    print(f"      ✓ seq={item['seq']}")
                except Exception as e:
                    print(f"      ✗ seq={item['seq']}: {e}")
            
            print("\n✓ SUCESSO!")
        else:
            print("    Nenhum item encontrado")
        
        print("\nPressione ENTER para fechar...")
        input()
        browser.close()

if __name__ == "__main__":
    main()
