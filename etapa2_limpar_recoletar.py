"""
AgroIA-RMC — Etapa 2: Recoletar Itens (COM LIMPEZA)
===================================================
Limpa a tabela de itens corrompidos e recoleta tudo.

Execute: python etapa2_limpar_recoletar.py
"""
import os
import re
import time
import signal
import sys
from datetime import datetime
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

FORM_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
ORGAO = "SMSAN/FAAC"

# Controle de interrupção
interrompido = False

def handler_interrupcao(sig, frame):
    global interrompido
    print("\n\n⚠️  Interrupção solicitada. Finalizando após esta licitação...")
    interrompido = True

signal.signal(signal.SIGINT, handler_interrupcao)

# ── Funções auxiliares ────────────────────────────────────────────────────────

def parse_val(t):
    try:
        return float((t or "0").strip().replace(".", "").replace(",", "."))
    except:
        return 0.0

def norm_cultura(desc):
    mapa = {
        "leite": "leite", "banana": "banana", "laranja": "laranja", 
        "maçã": "maca", "maça": "maca", "mamão": "mamao", "mamao": "mamao",
        "melancia": "melancia", "uva": "uva", "morango": "morango", 
        "tomate": "tomate", "cebola": "cebola", "cenoura": "cenoura", 
        "batata": "batata", "aipim": "aipim", "mandioca": "aipim",
        "alface": "alface", "couve": "couve", "repolho": "repolho",
        "brócolis": "brocolis", "brocolis": "brocolis", "alho": "alho", 
        "beterraba": "beterraba", "pimentão": "pimentao", "pimentao": "pimentao",
        "abobrinha": "abobrinha", "chuchu": "chuchu", "pepino": "pepino",
        "arroz": "arroz", "feijão": "feijao", "feijao": "feijao", 
        "milho": "milho", "queijo": "queijo", "ovos": "ovos", "ovo": "ovos",
        "frango": "frango", "carne": "carne", "pão": "pao", "pao": "pao",
        "mel": "mel", "abacaxi": "abacaxi", "goiaba": "goiaba",
        "limão": "limao", "limao": "limao", "kiwi": "kiwi", "manga": "manga",
        "pêra": "pera", "pera": "pera", "ameixa": "ameixa", "figo": "figo",
        "caqui": "caqui", "maracujá": "maracuja", "maracuja": "maracuja",
        "abóbora": "abobora", "abobora": "abobora", "inhame": "inhame",
        "farinha": "farinha", "açúcar": "acucar", "acucar": "acucar",
        "óleo": "oleo", "oleo": "oleo", "vinagre": "vinagre",
        "café": "cafe", "cafe": "cafe", "biscoito": "biscoito",
        "macarrão": "macarrao", "macarrao": "macarrao",
    }
    desc_lower = (desc or "").lower().strip()
    for k, v in mapa.items():
        if k in desc_lower:
            return v
    palavras = re.findall(r'[a-záéíóúâêîôûãõç]+', desc_lower)
    return palavras[0] if palavras else "outro"

def categ(cultura):
    frutas = {"abacaxi", "banana", "goiaba", "laranja", "limao", "maca", 
              "mamao", "melancia", "uva", "morango", "kiwi", "manga", 
              "pera", "ameixa", "figo", "caqui", "maracuja"}
    legumes = {"tomate", "cebola", "cenoura", "batata", "aipim", "alho", 
               "beterraba", "pimentao", "abobrinha", "chuchu", "pepino",
               "milho", "inhame", "abobora"}
    folhosas = {"alface", "couve", "repolho", "brocolis"}
    laticinios = {"queijo", "leite"}
    proteinas = {"frango", "carne", "ovos"}
    graos = {"arroz", "feijao", "farinha", "cafe", "acucar", "biscoito", "macarrao"}
    
    if cultura in frutas: return "FRUTA"
    if cultura in legumes: return "LEGUME"
    if cultura in folhosas: return "FOLHOSA"
    if cultura in laticinios: return "LATICINIOS"
    if cultura in proteinas: return "PROTEINA"
    if cultura in graos: return "GRAOS"
    return "OUTRO"

# ── Extração de dados ─────────────────────────────────────────────────────────

def extrair_itens_do_texto(texto):
    """Extrai itens do texto da página."""
    itens = []
    linhas = texto.split("\n")
    
    # Encontrar a linha "páginas" - os dados começam depois dela
    inicio_dados = -1
    for i, linha in enumerate(linhas):
        if linha.strip() == "páginas":
            inicio_dados = i + 1
            break
    
    if inicio_dados == -1:
        return itens
    
    # Processar linhas após "páginas"
    for i in range(inicio_dados, len(linhas)):
        linha = linhas[i].strip()
        
        if not linha:
            continue
        
        # Parar se encontrar outra seção
        if linha.startswith("Fornecedores") or linha.startswith("Documentos"):
            break
        
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
            cultura = norm_cultura(descricao)
            
            itens.append({
                "seq": seq,
                "codigo": codigo,
                "descricao": descricao,
                "qt_solicitada": qt,
                "unidade_medida": un,
                "valor_unitario": valor,
                "valor_total": qt * valor,
                "cultura": cultura,
                "categoria": categ(cultura),
            })
    
    return itens

def extrair_fornecedores_do_texto(texto):
    """Extrai fornecedores participantes."""
    fornecedores = []
    
    matches = re.findall(
        r'(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\s+([A-Za-záéíóúâêîôûãõçÁÉÍÓÚÂÊÎÔÛÃÕÇ\s\.\-&]+?)(?=\d{2}\.\d{3}\.\d{3}|\n|$)',
        texto
    )
    
    for cnpj, razao in matches:
        razao = razao.strip()
        if len(razao) > 5 and "Razão Social" not in razao:
            fornecedores.append({
                "cpf_cnpj": cnpj,
                "razao_social": razao[:100],
            })
    
    return fornecedores

# ── Gravação Supabase ─────────────────────────────────────────────────────────

def tipo_forn(razao):
    r = (razao or "").upper()
    if "COOPERATIV" in r: return "COOPERATIVA"
    if "ASSOCIA" in r: return "ASSOCIACAO"
    return "EMPRESA"

def gravar_itens(sb, lic_id, itens):
    """Grava itens no Supabase."""
    n = 0
    for item in itens:
        item["licitacao_id"] = lic_id
        try:
            sb.table("itens_licitacao").upsert(item, on_conflict="licitacao_id,seq").execute()
            n += 1
        except:
            pass
    return n

def gravar_fornecedores(sb, lic_id, fornecedores):
    """Grava fornecedores e participações."""
    n = 0
    for forn in fornecedores:
        try:
            r = sb.table("fornecedores").upsert(
                {
                    "cpf_cnpj": forn["cpf_cnpj"],
                    "razao_social": forn["razao_social"],
                    "tipo": tipo_forn(forn["razao_social"]),
                },
                on_conflict="cpf_cnpj"
            ).execute()
            
            fid = r.data[0]["id"] if r.data else None
            if not fid:
                r2 = sb.table("fornecedores").select("id").eq("cpf_cnpj", forn["cpf_cnpj"]).execute()
                fid = r2.data[0]["id"] if r2.data else None
            
            if fid:
                sb.table("participacoes").upsert(
                    {"licitacao_id": lic_id, "fornecedor_id": fid, "participou": True},
                    on_conflict="licitacao_id,fornecedor_id"
                ).execute()
                n += 1
        except:
            pass
    return n

# ── Limpeza da tabela ─────────────────────────────────────────────────────────

def limpar_tabela_itens(sb):
    """Limpa TODA a tabela itens_licitacao."""
    print("\n" + "=" * 60)
    print("⚠️  LIMPEZA DA TABELA itens_licitacao")
    print("=" * 60)
    
    # Contar registros atuais
    try:
        r = sb.table("itens_licitacao").select("id", count="exact").execute()
        total = r.count if r.count else len(r.data)
        print(f"\n    Registros atuais: {total}")
    except Exception as e:
        print(f"    Erro ao contar: {e}")
        total = "?"
    
    print(f"\n    Esta ação vai DELETAR TODOS os {total} registros da tabela.")
    print("    Os dados atuais estão corrompidos e serão recoletados.\n")
    
    confirmacao = input("    Digite 'LIMPAR' para confirmar: ")
    
    if confirmacao.strip().upper() != "LIMPAR":
        print("\n    ❌ Limpeza cancelada.")
        return False
    
    print("\n    Limpando tabela...")
    
    try:
        # Deletar em lotes para evitar timeout
        while True:
            # Buscar IDs para deletar
            r = sb.table("itens_licitacao").select("id").limit(1000).execute()
            
            if not r.data:
                break
            
            ids = [item["id"] for item in r.data]
            
            # Deletar lote
            for item_id in ids:
                sb.table("itens_licitacao").delete().eq("id", item_id).execute()
            
            print(f"      Deletados {len(ids)} registros...")
        
        print("\n    ✓ Tabela limpa com sucesso!")
        return True
        
    except Exception as e:
        print(f"\n    ❌ Erro ao limpar: {e}")
        
        # Tentar método alternativo
        print("    Tentando método alternativo...")
        try:
            # Deletar onde id > 0 (pega tudo)
            sb.table("itens_licitacao").delete().gt("id", 0).execute()
            print("    ✓ Tabela limpa com método alternativo!")
            return True
        except Exception as e2:
            print(f"    ❌ Erro: {e2}")
            return False

# ── Fluxo principal ───────────────────────────────────────────────────────────

def main():
    global interrompido
    
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    print("=" * 60)
    print("AgroIA-RMC — RECOLETA DE ITENS (COM LIMPEZA)")
    print("=" * 60)
    
    # 1. Limpar tabela de itens
    if not limpar_tabela_itens(sb):
        print("\n    Abortando execução.")
        return
    
    # 2. Carregar mapa do banco
    print("\n[1] Carregando licitações do Supabase...")
    dados = sb.table("licitacoes").select("id,processo").eq("orgao", ORGAO).execute().data
    mapa = {d["processo"]: d["id"] for d in dados}
    pendentes = list(mapa.keys())
    print(f"    {len(mapa)} licitações para coletar")
    
    # 3. Iniciar coleta
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=150)
        context = browser.new_context()
        context.set_default_timeout(60000)
        page = context.new_page()
        
        print("\n[2] Acessando portal...")
        page.goto(FORM_URL, timeout=60000)
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        print("\n" + "=" * 60)
        print("PREENCHA OS FILTROS MANUALMENTE:")
        print("  1. Órgão: SMSAN/FAAC")
        print("  2. Datas: 01/01/2019 a 31/12/2025")
        print("  3. Clique em PESQUISAR")
        print("=" * 60)
        input("\n>>> Pressione ENTER após pesquisar...")
        
        # Estatísticas
        total_itens = 0
        total_forns = 0
        processados = 0
        sem_itens = 0
        erros = 0
        pagina = 1
        
        print("\n[3] Iniciando coleta...")
        print("    (Ctrl+C para interromper com segurança)\n")
        
        while not interrompido:
            print(f"\n--- Página {pagina} ---")
            
            links = page.query_selector_all("a[id*='tabela'][id*='j_id26']")
            
            if not links:
                print("    Nenhuma licitação encontrada.")
                break
            
            processos_pagina = []
            for link in links:
                try:
                    texto = link.inner_text().strip()
                    processos_pagina.append(texto)
                except:
                    pass
            
            print(f"    {len(processos_pagina)} licitações na página")
            
            for proc_text in processos_pagina:
                if interrompido:
                    break
                
                lic_id = mapa.get(proc_text)
                if not lic_id:
                    continue
                
                try:
                    links = page.query_selector_all("a[id*='tabela'][id*='j_id26']")
                    link_alvo = None
                    for link in links:
                        if link.inner_text().strip() == proc_text:
                            link_alvo = link
                            break
                    
                    if not link_alvo:
                        continue
                    
                    link_alvo.click()
                    page.wait_for_timeout(2500)
                    
                    texto = page.inner_text("body")
                    itens = extrair_itens_do_texto(texto)
                    forns = extrair_fornecedores_do_texto(texto)
                    
                    if itens:
                        n_i = gravar_itens(sb, lic_id, itens)
                        n_f = gravar_fornecedores(sb, lic_id, forns)
                        
                        total_itens += n_i
                        total_forns += n_f
                        processados += 1
                        
                        print(f"  [{processados:4}] {proc_text} | itens:{n_i:3} | forn:{n_f}")
                    else:
                        sem_itens += 1
                        print(f"  [----] {proc_text} | sem itens")
                    
                    btn_voltar = page.query_selector("input[value='Página Inicial']")
                    if btn_voltar:
                        btn_voltar.click()
                        page.wait_for_timeout(1500)
                    else:
                        aba = page.query_selector("td:has-text('Lista Licitações')")
                        if aba:
                            aba.click()
                            page.wait_for_timeout(1500)
                
                except Exception as e:
                    erros += 1
                    print(f"  [ERRO] {proc_text}: {str(e)[:40]}")
                    
                    try:
                        page.goto(FORM_URL, timeout=30000)
                        page.wait_for_timeout(2000)
                    except:
                        pass
            
            if interrompido:
                break
            
            # Próxima página
            try:
                next_btns = page.query_selector_all("td.rich-datascr-button")
                next_btn = None
                for btn in next_btns:
                    txt = btn.inner_text().strip()
                    if txt == ">":
                        next_btn = btn
                        break
                
                if next_btn:
                    next_btn.click()
                    page.wait_for_timeout(2000)
                    pagina += 1
                else:
                    print("\n    Fim das páginas.")
                    break
            except:
                break
        
        browser.close()
    
    # Resumo
    print(f"\n{'='*60}")
    print(f"RESUMO DA COLETA")
    print(f"{'='*60}")
    print(f"  Processados:     {processados}")
    print(f"  Total de itens:  {total_itens}")
    print(f"  Fornecedores:    {total_forns}")
    print(f"  Sem itens:       {sem_itens}")
    print(f"  Erros:           {erros}")
    print(f"{'='*60}")
    
    if interrompido:
        print("\n⚠️  Coleta interrompida.")
        print("    Execute 'python etapa2_final.py' para continuar (sem limpar).")

if __name__ == "__main__":
    main()
