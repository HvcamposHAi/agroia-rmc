"""
AgroIA-RMC — Etapa 2: Coleta de Itens (v4 - FINAL)
===================================================
Extrai itens da tabela de detalhes de cada licitação usando Playwright.

Colunas da tabela (conforme portal):
  Seq | Código | Descrição | Qt. Solicitada | UN | Valor | Empenhos

Melhorias desta versão:
  - Retry com backoff exponencial (3 tentativas)
  - Validação de dados antes de gravar
  - Paginação via datascroller JSF
  - Graceful shutdown (Ctrl+C)
  - Timeout configurável
  - Modo headless opcional

Requisitos:
  pip install playwright python-dotenv supabase beautifulsoup4 lxml
  playwright install chromium

Execute: python etapa2_itens_v4.py
"""

import os
import re
import asyncio
import signal
import sys
from datetime import datetime
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from supabase import create_client

load_dotenv()

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO
# ══════════════════════════════════════════════════════════════════════════════

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

FORM_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
ORGAO = "SMSAN/FAAC"
DT_INICIO = "01/01/2019"
DT_FIM = "31/12/2025"

# Configurações de execução
HEADLESS = False  # Mudar para True para rodar em background
SLOW_MO = 300     # Milissegundos entre ações (0 = mais rápido, 500 = mais estável)
TIMEOUT = 60000   # Timeout em milissegundos
DELAY_ENTRE_PROCESSOS = 2.0   # Segundos entre processos
DELAY_ENTRE_PAGINAS = 1.5     # Segundos entre páginas

# Retry
MAX_TENTATIVAS = 3
BACKOFF_BASE = 5  # Segundos (5, 10, 15)

# Flag de interrupção
interrompido = False


def signal_handler(sig, frame):
    """Handler para Ctrl+C - interrupção graciosa."""
    global interrompido
    if interrompido:
        print("\n[!] Forçando saída...")
        sys.exit(1)
    print("\n[!] Interrupção solicitada. Aguardando processo atual terminar...")
    interrompido = True


signal.signal(signal.SIGINT, signal_handler)


# ══════════════════════════════════════════════════════════════════════════════
# FUNÇÕES AUXILIARES
# ══════════════════════════════════════════════════════════════════════════════

def parse_valor(texto: str) -> float:
    """Converte string de valor brasileiro para float."""
    try:
        t = (texto or "0").strip()
        t = t.replace(".", "").replace(",", ".")
        return float(t)
    except:
        return 0.0


def normalizar_cultura(descricao: str) -> str:
    """Normaliza descrição para cultura padronizada."""
    mapa = {
        "abacaxi": "abacaxi", "banana": "banana", "goiaba": "goiaba",
        "laranja": "laranja", "limão": "limao", "limao": "limao",
        "maçã": "maca", "maca": "maca", "mamão": "mamao", "mamao": "mamao",
        "melancia": "melancia", "morango": "morango", "uva": "uva", "kiwi": "kiwi",
        "tomate": "tomate", "cebola": "cebola", "cenoura": "cenoura",
        "batata": "batata", "aipim": "aipim", "mandioca": "aipim",
        "alho": "alho", "beterraba": "beterraba", "pimentão": "pimentao",
        "pimentao": "pimentao", "abobrinha": "abobrinha", "chuchu": "chuchu",
        "milho": "milho", "inhame": "inhame",
        "alface": "alface", "couve": "couve", "repolho": "repolho",
        "brócolis": "brocolis", "brocolis": "brocolis",
        "arroz": "arroz", "feijão": "feijao", "feijao": "feijao",
        "queijo": "queijo", "leite": "leite", "ovos": "ovos",
        "frango": "frango", "carne": "carne",
        "pão": "pao", "pao": "pao", "mel": "mel",
    }
    d = (descricao or "").lower().strip()
    for k, v in mapa.items():
        if k in d:
            return v
    return ""


def categorizar(cultura: str) -> str:
    """Retorna categoria da cultura."""
    categorias = {
        "FRUTA": {"abacaxi", "banana", "goiaba", "laranja", "limao", "maca",
                  "mamao", "melancia", "morango", "uva", "kiwi"},
        "LEGUME": {"tomate", "cebola", "cenoura", "batata", "aipim", "alho",
                   "beterraba", "pimentao", "abobrinha", "chuchu", "milho", "inhame"},
        "FOLHOSA": {"alface", "couve", "repolho", "brocolis"},
        "LATICINIOS": {"queijo", "leite"},
        "PROTEINA": {"frango", "carne", "ovos"},
        "GRAOS": {"arroz", "feijao", "mel", "pao"},
    }
    for cat, itens in categorias.items():
        if cultura in itens:
            return cat
    return "OUTRO"


def validar_item(item: dict) -> bool:
    """Valida se um item extraído é válido."""
    # Seq deve ser número positivo
    if not isinstance(item.get("seq"), int) or item["seq"] < 1:
        return False
    
    # Descrição deve ter pelo menos 3 caracteres
    desc = item.get("descricao", "")
    if not desc or len(desc) < 3:
        return False
    
    # Filtrar elementos de UI capturados erroneamente
    palavras_invalidas = [
        "quantidade registros", "data abertura", "página", "pesquisar",
        "selecione", "aguardando", "julgamento", "concluído", "segterquaqui",
        "segtequi", "leia mais", "empenhos", "página inicial",
    ]
    desc_lower = desc.lower()
    if any(p in desc_lower for p in palavras_invalidas):
        return False
    
    # Código deve ter pelo menos 5 caracteres (ex: 89.09.06.04851-7)
    codigo = item.get("codigo", "")
    if not codigo or len(codigo) < 5:
        return False
    
    return True


# ══════════════════════════════════════════════════════════════════════════════
# EXTRAÇÃO DE DADOS
# ══════════════════════════════════════════════════════════════════════════════

def extrair_itens_do_html(html: str) -> list[dict]:
    """
    Extrai itens da tabela de detalhes.
    Colunas: Seq | Código | Descrição | Qt. Solicitada | UN | Valor | Empenhos
    """
    soup = BeautifulSoup(html, "lxml")
    itens = []
    
    # Procurar tabela com cabeçalhos corretos
    for tabela in soup.find_all("table"):
        headers = [th.get_text(strip=True).lower() for th in tabela.find_all("th")]
        
        # Identificar tabela de itens
        has_seq = "seq" in headers
        has_codigo = "código" in headers or "codigo" in headers
        has_descricao = "descrição" in headers or "descricao" in headers
        
        if has_seq and (has_codigo or has_descricao):
            linhas = tabela.find_all("tr")[1:]  # Pular cabeçalho
            
            for tr in linhas:
                cols = tr.find_all("td")
                if len(cols) < 5:
                    continue
                
                # Extrair textos
                seq_txt = cols[0].get_text(strip=True)
                codigo_txt = cols[1].get_text(strip=True)
                descricao_txt = cols[2].get_text(strip=True) if len(cols) > 2 else ""
                qt_txt = cols[3].get_text(strip=True) if len(cols) > 3 else "0"
                un_txt = cols[4].get_text(strip=True) if len(cols) > 4 else ""
                valor_txt = cols[5].get_text(strip=True) if len(cols) > 5 else "0"
                
                # Converter seq para int
                try:
                    seq = int(seq_txt)
                except:
                    continue
                
                cultura = normalizar_cultura(descricao_txt)
                
                item = {
                    "seq": seq,
                    "codigo": codigo_txt,
                    "descricao": descricao_txt,
                    "qt_solicitada": parse_valor(qt_txt),
                    "unidade_medida": un_txt,
                    "valor_unitario": parse_valor(valor_txt),
                    "valor_total": 0.0,
                    "cultura": cultura,
                    "categoria": categorizar(cultura),
                }
                
                # Validar antes de adicionar
                if validar_item(item):
                    itens.append(item)
            
            # Se encontrou tabela com itens válidos, retornar
            if itens:
                return itens
    
    return itens


def extrair_fornecedores_do_html(html: str) -> list[dict]:
    """Extrai fornecedores participantes da tabela de detalhes."""
    soup = BeautifulSoup(html, "lxml")
    fornecedores = []
    cnpjs_vistos = set()  # Evitar duplicatas
    
    for tabela in soup.find_all("table"):
        headers = [th.get_text(strip=True).lower() for th in tabela.find_all("th")]
        
        # Identificar tabela de fornecedores
        if any(h in headers for h in ["cpf/cnpj", "cnpj", "razão social", "razao social"]):
            linhas = tabela.find_all("tr")[1:]
            
            for tr in linhas:
                cols = tr.find_all("td")
                if len(cols) < 2:
                    continue
                
                cpf_cnpj = cols[0].get_text(strip=True)
                razao = cols[1].get_text(strip=True)
                
                # Validar CPF/CNPJ (11 ou 14 dígitos)
                digitos = re.sub(r"[^\d]", "", cpf_cnpj)
                if len(digitos) >= 11 and razao and len(razao) > 3:
                    # Evitar duplicatas
                    if digitos not in cnpjs_vistos:
                        cnpjs_vistos.add(digitos)
                        fornecedores.append({
                            "cpf_cnpj": cpf_cnpj.strip(),
                            "razao_social": razao.strip()
                        })
            
            # Se encontrou fornecedores, não procurar em outras tabelas
            if fornecedores:
                break
    
    return fornecedores


# ══════════════════════════════════════════════════════════════════════════════
# GRAVAÇÃO NO SUPABASE
# ══════════════════════════════════════════════════════════════════════════════

def gravar_itens(sb, lic_id: int, itens: list[dict]) -> int:
    """Grava itens no Supabase com upsert."""
    n = 0
    for item in itens:
        item["licitacao_id"] = lic_id
        try:
            sb.table("itens_licitacao").upsert(
                item, on_conflict="licitacao_id,seq"
            ).execute()
            n += 1
        except Exception as e:
            print(f"        [db] Erro item seq={item['seq']}: {str(e)[:40]}")
    return n


def gravar_fornecedores(sb, lic_id: int, fornecedores: list[dict]) -> int:
    """Grava fornecedores e participações no Supabase."""
    n = 0
    for forn in fornecedores:
        try:
            # Determinar tipo
            razao_upper = forn["razao_social"].upper()
            if "COOPERATIV" in razao_upper:
                tipo = "COOPERATIVA"
            elif "ASSOCIA" in razao_upper:
                tipo = "ASSOCIACAO"
            else:
                tipo = "EMPRESA"
            
            # Upsert fornecedor
            r = sb.table("fornecedores").upsert({
                "cpf_cnpj": forn["cpf_cnpj"],
                "razao_social": forn["razao_social"],
                "tipo": tipo
            }, on_conflict="cpf_cnpj").execute()
            
            # Obter ID do fornecedor
            fid = r.data[0]["id"] if r.data else None
            if not fid:
                r2 = sb.table("fornecedores").select("id").eq(
                    "cpf_cnpj", forn["cpf_cnpj"]).execute()
                fid = r2.data[0]["id"] if r2.data else None
            
            # Gravar participação
            if fid:
                sb.table("participacoes").upsert({
                    "licitacao_id": lic_id,
                    "fornecedor_id": fid,
                    "participou": True
                }, on_conflict="licitacao_id,fornecedor_id").execute()
                n += 1
        except Exception as e:
            print(f"        [db] Erro fornecedor: {str(e)[:40]}")
    return n


# ══════════════════════════════════════════════════════════════════════════════
# FUNÇÕES PLAYWRIGHT
# ══════════════════════════════════════════════════════════════════════════════

async def fazer_pesquisa(page) -> int:
    """Preenche o formulário e executa a pesquisa. Retorna total de registros."""
    print("    Selecionando órgão SMSAN/FAAC...")
    await page.select_option("select[name='form:j_id9']", label=ORGAO)
    await asyncio.sleep(0.5)
    
    print(f"    Preenchendo datas: {DT_INICIO} → {DT_FIM}")
    await page.fill("[id='form:dataInferiorInputDate']", DT_INICIO)
    await page.fill("[id='form:j_id18InputDate']", DT_FIM)
    await asyncio.sleep(0.5)
    
    print("    Clicando em Pesquisar...")
    await page.click("[id='form:btSearch']")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(2)
    
    # Extrair total de registros
    html = await page.content()
    m = re.search(r"quantidade registros.*?(\d+)", html, re.I | re.DOTALL)
    total = int(m.group(1)) if m else 0
    print(f"    Total de registros: {total}")
    
    return total


async def extrair_processos_da_pagina(page) -> list[dict]:
    """Extrai os processos listados na página atual da tabela de resultados."""
    html = await page.content()
    soup = BeautifulSoup(html, "lxml")
    processos = []
    
    # Procurar especificamente a tabela de resultados (tem classe rich-table)
    for tabela in soup.find_all("table", class_=re.compile(r"rich-table|dataTable")):
        headers = [th.get_text(strip=True).lower() for th in tabela.find_all("th")]
        
        # Verificar se é a tabela de processos
        if "processo" in headers and "objeto" in headers:
            linhas = tabela.find_all("tr")[1:]  # Pular cabeçalho
            
            for tr in linhas:
                cols = tr.find_all("td")
                if len(cols) < 3:
                    continue
                
                proc_txt = cols[0].get_text(strip=True)
                
                # Validar formato (ex: "DE 4/2019", "DS 70/2019", "CR 2/2025")
                if not re.match(r"^[A-Z]{2}\s+\d+/\d{4}", proc_txt):
                    continue
                
                link = cols[0].find("a")
                link_id = link.get("id", "") if link else ""
                
                # Só adicionar se tiver link_id válido (evita duplicatas)
                if link_id and not any(p["link_id"] == link_id for p in processos):
                    processos.append({
                        "processo": proc_txt,
                        "objeto": cols[1].get_text(strip=True),
                        "link_id": link_id,
                    })
            
            # Se encontrou processos nesta tabela, não procurar em outras
            if processos:
                break
    
    return processos


async def clicar_processo_com_retry(page, link_id: str) -> str:
    """Clica no link do processo com retry e retorna HTML do detalhe."""
    if not link_id:
        return ""
    
    # Usar seletor de atributo id (não precisa escapar :)
    selector = f"[id='{link_id}']"
    
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            await page.click(selector)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(1.5)
            
            # Aguardar tabela de itens
            try:
                await page.wait_for_selector("table th:has-text('Seq')", timeout=10000)
            except:
                pass  # Processo pode não ter itens
            
            html = await page.content()
            
            # Verificar se carregou corretamente (não é página de loading)
            if "aguarde" in html.lower() and "carregando" in html.lower():
                raise Exception("Página de loading")
            
            return html
            
        except Exception as e:
            if tentativa < MAX_TENTATIVAS:
                espera = BACKOFF_BASE * tentativa
                print(f"        [retry {tentativa}/{MAX_TENTATIVAS}] Aguardando {espera}s...")
                await asyncio.sleep(espera)
            else:
                print(f"        [!] Falhou após {MAX_TENTATIVAS} tentativas: {str(e)[:40]}")
                return ""
    
    return ""


async def voltar_para_lista(page):
    """Volta para a lista de processos clicando no link 'Lista Licitações'."""
    try:
        # Na página de detalhe, o link é "Lista Licitações" no topo
        # Tentar diferentes seletores
        try:
            await page.click("a:has-text('Lista Licitações')")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(DELAY_ENTRE_PAGINAS)
            return
        except:
            pass
        
        # Fallback: tentar pelo texto exato
        try:
            await page.click("text=Lista Licitações")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(DELAY_ENTRE_PAGINAS)
            return
        except:
            pass
        
        # Fallback 2: clicar no botão Pesquisar (se disponível)
        try:
            await page.click("[id='form:btSearch']")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(DELAY_ENTRE_PAGINAS)
            return
        except:
            pass
            
    except Exception as e:
        print(f"        [!] Erro ao voltar: {str(e)[:40]}")


async def navegar_para_proxima_pagina(page, pagina_destino: int) -> bool:
    """
    Navega para a próxima página usando o datascroller JSF.
    O portal usa RichFaces DataScroller com links numerados.
    """
    try:
        html = await page.content()
        soup = BeautifulSoup(html, "lxml")
        
        # Procurar links de paginação que contêm o número da página
        for a in soup.find_all("a"):
            txt = a.get_text(strip=True)
            if txt == str(pagina_destino):
                link_id = a.get("id", "")
                if link_id:
                    selector = f"[id='{link_id}']"
                    await page.click(selector)
                    await page.wait_for_load_state("networkidle")
                    await asyncio.sleep(DELAY_ENTRE_PAGINAS)
                    return True
        
        # Fallback: tentar clicar no seletor de texto
        try:
            await page.click(f"a:text-is('{pagina_destino}')")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(DELAY_ENTRE_PAGINAS)
            return True
        except:
            pass
        
        # Fallback 2: clicar em ">>" ou ">" para avançar
        try:
            await page.click("a:has-text('>>')")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(DELAY_ENTRE_PAGINAS)
            return True
        except:
            pass
        
        return False
        
    except Exception as e:
        print(f"    [!] Erro navegação: {str(e)[:40]}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# FLUXO PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

async def main():
    global interrompido
    
    print("=" * 60)
    print("AgroIA-RMC — Coleta de Itens de Licitações (v4)")
    print("=" * 60)
    
    # Conectar Supabase
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Carregar licitações do banco
    print("\n[0] Carregando licitações do Supabase...")
    dados = sb.table("licitacoes").select("id,processo").eq("orgao", ORGAO).execute().data
    mapa_processos = {d["processo"]: d["id"] for d in dados}
    
    # IDs que já têm itens
    r = sb.table("itens_licitacao").select("licitacao_id").execute()
    coletados = {row["licitacao_id"] for row in r.data}
    pendentes_ids = set(lid for lid in mapa_processos.values() if lid not in coletados)
    
    print(f"    {len(mapa_processos)} licitações no banco")
    print(f"    {len(coletados)} já têm itens coletados")
    print(f"    {len(pendentes_ids)} pendentes de coleta")
    
    if not pendentes_ids:
        print("\n[✓] Todos os detalhes já foram coletados!")
        return
    
    # Iniciar Playwright
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        print(f"\n[1] Abrindo navegador (headless={HEADLESS})...")
        browser = await p.chromium.launch(headless=HEADLESS, slow_mo=SLOW_MO)
        page = await browser.new_page()
        page.set_default_timeout(TIMEOUT)
        
        print(f"[2] Acessando portal...")
        await page.goto(FORM_URL, timeout=TIMEOUT)
        await page.wait_for_selector("select[name='form:j_id9']", timeout=15000)
        await asyncio.sleep(1)
        
        print("[3] Fazendo pesquisa...")
        total_registros = await fazer_pesquisa(page)
        
        if total_registros == 0:
            print("[!] Nenhum registro encontrado.")
            await browser.close()
            return
        
        # Estatísticas
        stats = {
            "processados": 0,
            "itens": 0,
            "fornecedores": 0,
            "erros": 0,
            "pulados": 0,
        }
        
        print(f"\n[4] Iniciando coleta de {len(pendentes_ids)} licitações pendentes...\n")
        
        pagina_atual = 1
        regs_por_pagina = 5
        max_paginas = (total_registros // regs_por_pagina) + 1
        
        while pagina_atual <= max_paginas and not interrompido:
            # Extrair processos da página atual
            processos = await extrair_processos_da_pagina(page)
            
            print(f"--- Página {pagina_atual}/{max_paginas} | {len(processos)} processos ---")
            
            for proc in processos:
                if interrompido:
                    break
                
                processo = proc["processo"]
                lic_id = mapa_processos.get(processo)
                
                # Pular se não está no banco ou já foi coletado
                if not lic_id:
                    continue
                if lic_id not in pendentes_ids:
                    stats["pulados"] += 1
                    continue
                
                print(f"\n  [{stats['processados']+1}] {processo}")
                
                try:
                    # Clicar no processo com retry
                    html_detalhe = await clicar_processo_com_retry(page, proc["link_id"])
                    
                    if not html_detalhe:
                        print("        [!] Não conseguiu abrir detalhe")
                        stats["erros"] += 1
                        await voltar_para_lista(page)
                        continue
                    
                    # Extrair dados
                    itens = extrair_itens_do_html(html_detalhe)
                    fornecedores = extrair_fornecedores_do_html(html_detalhe)
                    
                    # Gravar no Supabase
                    n_itens = gravar_itens(sb, lic_id, itens)
                    n_forns = gravar_fornecedores(sb, lic_id, fornecedores)
                    
                    # Atualizar contadores
                    pendentes_ids.discard(lic_id)
                    stats["processados"] += 1
                    stats["itens"] += n_itens
                    stats["fornecedores"] += n_forns
                    
                    print(f"        ✓ Itens: {n_itens} | Fornecedores: {n_forns}")
                    
                    # Voltar para lista
                    await asyncio.sleep(DELAY_ENTRE_PROCESSOS)
                    await voltar_para_lista(page)
                    
                except Exception as e:
                    stats["erros"] += 1
                    print(f"        [!] Erro: {str(e)[:50]}")
                    
                    # Tentar recuperar
                    try:
                        await voltar_para_lista(page)
                    except:
                        pass
            
            # Próxima página
            pagina_atual += 1
            if pagina_atual <= max_paginas and not interrompido:
                sucesso = await navegar_para_proxima_pagina(page, pagina_atual)
                if not sucesso:
                    print(f"[!] Não conseguiu navegar para página {pagina_atual}")
                    # Tentar refazer a pesquisa
                    try:
                        await fazer_pesquisa(page)
                        for _ in range(1, pagina_atual):
                            await navegar_para_proxima_pagina(page, _ + 1)
                    except:
                        break
            
            # Progresso a cada 10 páginas
            if pagina_atual % 10 == 0:
                print(f"\n    [progresso] Processados: {stats['processados']} | "
                      f"Itens: {stats['itens']} | Pendentes: {len(pendentes_ids)}\n")
        
        # Fechar browser com tratamento de erro
        try:
            await browser.close()
        except:
            pass  # Browser já pode estar fechado
    
    # Resumo final
    print("\n" + "=" * 60)
    print("CONCLUÍDO!")
    print("=" * 60)
    print(f"  Processados:   {stats['processados']}")
    print(f"  Itens:         {stats['itens']}")
    print(f"  Fornecedores:  {stats['fornecedores']}")
    print(f"  Pulados:       {stats['pulados']}")
    print(f"  Erros:         {stats['erros']}")
    print(f"  Pendentes:     {len(pendentes_ids)}")
    if interrompido:
        print("  (Interrompido pelo usuário - rode novamente para continuar)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
