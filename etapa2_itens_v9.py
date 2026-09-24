"""
AgroIA-RMC — Coleta de Itens de Licitações (v9)
================================================
Correções vs v8.1:
  1. [CRÍTICO] voltar_para_lista: "Lista Licitações" é um <td> de aba RichFaces
     (id="form:abaPesquisa_lbl"), não um <a>. Corrigido seletor.
  2. [CRÍTICO] empenhos: colunas reais são Número|Ano|Data Empenho (3 cols),
     não Número|Data|Valor|Ano (4 cols). Mapeamento corrigido.
  3. coletar_todas_paginas_itens: datascroller escopado para
     form:tabelaItens:j_id140, evitando conflito com outros datascrollers.

Correções anteriores (mantidas):
  4. _extrair_total_de_html: regex com DOTALL cruzando tags HTML.
  5. extrair_processos_pagina: extrai id do <a> (ex: "form:tabela:0:j_id26").
  6. abrir_detalhe: clica via [id="form:tabela:N:j_id26"] (atributo).
  7. fazer_pesquisa: fallback se contador=0 mas há processos visíveis.
  8. Loop principal: funciona com total desconhecido.

Execute: python etapa2_itens_v9.py
"""

import os
import re
import math
import time
import json
import signal
import argparse
from datetime import datetime, date, timedelta, timezone
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
from supabase import create_client
from enriquecer_classificacao import classificar_item, is_relevante_agro
from classificacao_licitacao import classificar_tipo, classificar_canal, is_af

load_dotenv()

# ─── Configuração ─────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing required env vars: SUPABASE_URL, SUPABASE_KEY")

PORTAL_URL = "http://consultalicitacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
ORGAO      = "SMSAN/FAAC"
REGS_POR_PAG = 5
DELAY        = 2.0
DEBUG        = True

# Headless configurável: padrão visível (local Windows). Em servidor sem display
# (ex.: container Linux), setar PLAYWRIGHT_HEADLESS=true.
HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() in ("1", "true", "yes")
SLOW_MO  = int(os.getenv("PLAYWRIGHT_SLOW_MO", "0" if HEADLESS else "80"))
LAUNCH_ARGS = ["--no-sandbox", "--disable-dev-shm-usage"] if HEADLESS else []

# Se True: apaga itens existentes antes de reprocessar (corrige dados corrompidos)
FORCAR_REPROCESSAR = False

# Se True: re-entra apenas nas licitações que têm itens mas NÃO têm empenhos,
# regrava só os empenhos (sem tocar em itens/fornecedores). Modo de manutenção —
# NÃO insere licitações novas. Ligado via CLI (--somente-empenhos), nunca por padrão:
# ficou True por engano após jun/2026 e a coleta passou a descartar processos novos.
FORCAR_EMPENHOS = False

# Janela padrão da coleta incremental (quando --dt-inicio/--dt-fim não são dados):
#  - início: última data conhecida (menor entre MAX(dt_abertura) e MAX(coletado_em))
#    menos JANELA_SOBREPOSICAO_DIAS — dt_abertura pode estar no futuro no momento da
#    coleta, então partir dela pularia processos publicados nesse intervalo;
#  - fim: hoje + JANELA_FUTURO_DIAS — o portal lista processos com abertura futura.
JANELA_SOBREPOSICAO_DIAS = 120
JANELA_FUTURO_DIAS = 180

# Valor sentinela: pesquisa OK mas total de registros desconhecido
TOTAL_DESCONHECIDO = -1

# Origem gravada em coleta_execucoes (sobrescrita por --origem no CLI).
ORIGEM = "manual"

# ─── Controle de interrupção ──────────────────────────────────────────────────
INTERROMPIDO = False

def handler_sigint(sig, frame):
    global INTERROMPIDO
    INTERROMPIDO = True
    print("\n[!] Interrupção solicitada. Aguardando processo atual terminar...")

signal.signal(signal.SIGINT, handler_sigint)

# ─── Conexão Supabase ─────────────────────────────────────────────────────────
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── Argumentos CLI ──────────────────────────────────────────────────────────
def parse_args():
    parser = argparse.ArgumentParser(
        description="Coleta de itens de licitações agrícolas"
    )
    parser.add_argument(
        "--dt-inicio",
        type=str,
        default=None,
        help="Data inicial (DD/MM/YYYY). Se omitida, usa MAX(dt_abertura) do banco."
    )
    parser.add_argument(
        "--dt-fim",
        type=str,
        default=None,
        help="Data final (DD/MM/YYYY). Se omitida, usa data de hoje."
    )
    parser.add_argument(
        "--progress-file",
        type=str,
        default="coleta_status.json",
        help="Arquivo para salvar progresso JSON."
    )
    parser.add_argument(
        "--somente-empenhos",
        action="store_true",
        help="Modo manutenção: só regrava empenhos de licitações 'Concluído' sem empenhos."
    )
    parser.add_argument(
        "--origem",
        type=str,
        default=os.getenv("COLETA_ORIGEM") or "manual",
        help="Origem registrada em coleta_execucoes (manual | agendada)."
    )
    return parser.parse_args()

def _max_data(coluna: str):
    resp = (sb.table("licitacoes").select(coluna).not_.is_(coluna, "null")
            .order(coluna, desc=True).limit(1).execute())
    if resp.data and resp.data[0].get(coluna):
        return date.fromisoformat(resp.data[0][coluna][:10])
    return None

def get_data_inicio_padrao() -> str:
    """Início da janela incremental (DD/MM/YYYY): última data conhecida menos a
    sobreposição. Reprocessar processos já gravados é barato (são pulados ou só têm
    a situação atualizada); perder processos novos não é."""
    try:
        datas = [d for d in (_max_data("dt_abertura"), _max_data("coletado_em")) if d]
        if not datas:
            return "01/01/2019"
        inicio = min(datas) - timedelta(days=JANELA_SOBREPOSICAO_DIAS)
        return max(inicio, date(2019, 1, 1)).strftime("%d/%m/%Y")
    except Exception as e:
        print(f"[!] Erro ao calcular data inicial: {e}. Usando fallback 01/01/2019.")
        return "01/01/2019"

def get_data_fim_padrao() -> str:
    return (date.today() + timedelta(days=JANELA_FUTURO_DIAS)).strftime("%d/%m/%Y")

def escrever_progresso(progress_file: str, stats: dict, etapa: str = "coletando", status: str = "running",
                      dt_inicio: str = None, dt_fim: str = None, portal_url: str = None, orgao: str = None, regs_por_pag: int = None):
    """Escreve progresso em JSON com timestamp e parâmetros de consulta ao portal."""
    dados = {
        "status": status,
        "etapa": etapa,
        "processados": stats.get("processados", 0),
        # "novos" = licitações NOVAS inseridas (antes era espelho de itens).
        "novos": stats.get("licitacoes_novas", 0),
        "atualizadas": stats.get("licitacoes_atualizadas", 0),
        "total_portal": stats.get("total_portal"),
        "pagina": stats.get("pagina"),
        "total_paginas": stats.get("total_paginas"),
        "pulados": stats.get("pulados", 0),
        "erros": stats.get("erros", 0),
        "itens_coletados": stats.get("itens", 0),
        "fornecedores": stats.get("fornecedores", 0),
        "empenhos": stats.get("empenhos", 0),
        "iniciado_em": stats.get("iniciado_em", datetime.now(timezone.utc).isoformat()),
        "atualizado_em": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
        # ID do run do GitHub Actions (quando a coleta roda como workflow) — usado
        # para o backend conseguir cancelar o run. None quando roda localmente.
        "run_id": os.getenv("GITHUB_RUN_ID"),
    }

    # Adicionar informações de consulta ao portal se disponíveis
    if dt_inicio or dt_fim or portal_url or orgao:
        dados["consulta_portal"] = {
            "url": portal_url or PORTAL_URL,
            "orgao": orgao or ORGAO,
            "dt_inicio": dt_inicio,
            "dt_fim": dt_fim,
            "registros_por_pagina": regs_por_pag or REGS_POR_PAG
        }

    try:
        with open(progress_file, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception as e:
        if DEBUG:
            print(f"[!] Erro ao escrever {progress_file}: {e}")

    # Espelha o status no Supabase (tabela coleta_status, linha única id=1) — é a
    # FONTE COMPARTILHADA que o backend (Render) lê para mostrar progresso ao vivo,
    # independentemente de onde a coleta roda (GitHub Actions, local, etc.).
    # Blindado: falha aqui nunca interrompe a coleta.
    try:
        sb.table("coleta_status").upsert(
            {"id": 1, "dados": dados, "atualizado_em": dados["atualizado_em"]},
            on_conflict="id",
        ).execute()
    except Exception as e:
        if DEBUG:
            print(f"[!] Erro ao espelhar status no Supabase (ignorado): {e}")


def registrar_erro(stats: dict, processo: str, mensagem: str, limite: int = 50):
    """Incrementa o contador de erros e acumula o detalhe (processo + mensagem),
    limitado a `limite` itens para não inflar o payload gravado/transmitido."""
    stats["erros"] = stats.get("erros", 0) + 1
    detalhe = stats.setdefault("erros_detalhe", [])
    if len(detalhe) < limite:
        detalhe.append({"processo": processo or "?", "mensagem": (mensagem or "")[:300]})


def registrar_execucao(stats: dict, final_status: str, dt_inicio: str = None,
                       dt_fim: str = None, erro_resumo: str = None, origem: str = None):
    """Grava um resumo da execução em coleta_execucoes (Supabase) para o histórico
    exibido na página de Coleta. Blindado: qualquer falha apenas loga — NUNCA
    interrompe a coleta nem propaga exceção."""
    try:
        iniciado = stats.get("iniciado_em")
        finalizado = datetime.now(timezone.utc)
        duracao = None
        if iniciado:
            try:
                duracao = int((finalizado - datetime.fromisoformat(iniciado)).total_seconds())
            except Exception:
                duracao = None
        registro = {
            "iniciado_em":     iniciado,
            "finalizado_em":   finalizado.isoformat(),
            "duracao_seg":     duracao,
            "status":          final_status,
            "etapa":           "finalizado",
            "origem":          origem or ORIGEM,
            "dt_inicio":       dt_inicio,
            "dt_fim":          dt_fim,
            "processados":     stats.get("processados", 0),
            "novos":           stats.get("licitacoes_novas", 0),
            "pulados":         stats.get("pulados", 0),
            "erros":           stats.get("erros", 0),
            "itens_coletados": stats.get("itens", 0),
            "fornecedores":    stats.get("fornecedores", 0),
            "empenhos":        stats.get("empenhos", 0),
            "erro_resumo":     ((erro_resumo or "")[:2000] or None),
            "erro_detalhes":   stats.get("erros_detalhe", []),
        }
        sb.table("coleta_execucoes").insert(registro).execute()
        print(f"[OK] Execução registrada em coleta_execucoes (status={final_status})")
    except Exception as e:
        print(f"[!] Falha ao registrar execução em coleta_execucoes (ignorada): {e}")

# ─── Funções auxiliares ───────────────────────────────────────────────────────
def parse_val(t):
    """Converte string de valor brasileiro (1.234,56) para float."""
    try:
        return float((t or "0").strip().replace(".", "").replace(",", "."))
    except:
        return 0.0

def norm_cultura(desc):
    """Extrai cultura canônica do item usando o dicionário expandido."""
    cultura, _ = classificar_item(desc)
    return cultura

def tipo_forn(razao):
    razao = (razao or "").upper()
    if any(x in razao for x in ["COOPERATIVA", "COOP."]):
        return "COOPERATIVA"
    if any(x in razao for x in ["ASSOCIAÇÃO", "ASSOCIACAO", "ASSOC."]):
        return "ASSOCIACAO"
    return "EMPRESA"

# ─── Extração de dados do detalhe ─────────────────────────────────────────────
def extrair_itens_de_html(html):
    """
    Extrai itens, fornecedores e empenhos do HTML de detalhe de licitação.
    Usa as tabelas reais do portal:
      - form:tabelaItens                          → itens
      - form:tabelaFornecedoresParticipantes /
        form:tabelaFornecedoresEdital             → fornecedores
      - form:tabelaEmpenhosProcCompra             → empenhos
    """
    soup = BeautifulSoup(html, "lxml")
    itens, forns, emps = [], [], []

    # ── Itens ────────────────────────────────────────────────────────────────
    # Estratégia 1: ID fixo confirmado no portal
    tabela_itens = soup.find("table", id="form:tabelaItens")
    # Estratégia 2 (fallback): tabela com TH "seq"/"código" (abordagem da Etapa 1)
    if not tabela_itens:
        for t in soup.find_all("table"):
            ths = [th.get_text(strip=True).lower() for th in t.find_all("th")]
            if any(h in ths for h in ["seq", "código", "codigo"]):
                tabela_itens = t
                break
    if tabela_itens:
        for tr in tabela_itens.find_all("tr")[1:]:  # pula cabeçalho
            tds = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(tds) < 4:
                continue
            try:
                seq   = int(tds[0]) if tds[0].isdigit() else None
                cod   = tds[1]
                desc  = tds[2]
                qt    = parse_val(tds[3])
                und   = tds[4]  if len(tds) > 4 else ""
                v_un  = parse_val(tds[5]) if len(tds) > 5 else 0.0
                v_tot = qt * v_un
                # Tenta ler valor total da coluna se existir
                if len(tds) > 6:
                    v_col = parse_val(tds[6])
                    if v_col > 0:
                        v_tot = v_col

                if seq is None:
                    continue

                _cultura, _cat = classificar_item(desc)
                itens.append({
                    "seq":              seq,
                    "codigo":           cod,
                    "descricao":        desc,
                    "descricao_completa": desc,
                    "qt_solicitada":    qt,
                    "unidade_medida":   und,
                    "valor_unitario":   v_un,
                    "valor_total":      v_tot,
                    "cultura":          _cultura,
                    "categoria":        _cat,
                    "categoria_v2":     _cat,
                    "relevante_agro":   is_relevante_agro(_cat),
                })
            except Exception:
                continue

    # ── Fornecedores ─────────────────────────────────────────────────────────
    for tab_id in ["form:tabelaFornecedoresParticipantes", "form:tabelaFornecedoresEdital"]:
        tab = soup.find("table", id=tab_id)
        if not tab:
            continue
        for tr in tab.find_all("tr")[1:]:
            tds = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(tds) < 2:
                continue
            cnpj = re.sub(r'\D', '', tds[0])
            nome = tds[1] if len(tds) > 1 else ""
            if cnpj and len(cnpj) >= 11:
                forns.append({"cpf_cnpj": cnpj, "razao_social": nome})
        if forns:
            break

    # ── Empenhos ─────────────────────────────────────────────────────────────
    # Colunas no HTML:    Número | Ano | Data Empenho
    # Colunas no Supabase: nr_empenho | ano | dt_empenho | valor_empenhado | fornecedor_id
    tab_emp = soup.find("table", id="form:tabelaEmpenhosProcCompra")
    if tab_emp:
        for tr in tab_emp.find_all("tr")[1:]:
            tds = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(tds) < 2:
                continue
            nr  = tds[0]
            ano = tds[1] if len(tds) > 1 else ""
            dt  = tds[2] if len(tds) > 2 else ""
            # Converte data DD/MM/YYYY → YYYY-MM-DD para Supabase
            dt_iso = None
            if dt and "/" in dt:
                parts = dt.split("/")
                if len(parts) == 3:
                    dt_iso = f"{parts[2]}-{parts[1]}-{parts[0]}"
            emps.append({
                "nr_empenho": nr if nr else None,
                "ano":        int(ano) if ano.isdigit() else None,
                "dt_empenho": dt_iso,
            })

    return itens, forns, emps

# ─── Gravação no Supabase ─────────────────────────────────────────────────────
def gravar(lic_id, itens, forns, emps):
    n_i = n_f = 0

    for item in itens:
        item["licitacao_id"] = lic_id
        try:
            sb.table("itens_licitacao").upsert(
                item, on_conflict="licitacao_id,seq"
            ).execute()
            n_i += 1
        except Exception as e:
            if DEBUG:
                print(f"      [!] Erro item seq={item.get('seq')}: {e}")

    for forn in forns:
        try:
            r = sb.table("fornecedores").upsert(
                {
                    "cpf_cnpj":    forn["cpf_cnpj"],
                    "razao_social": forn["razao_social"],
                    "tipo":        tipo_forn(forn["razao_social"]),
                },
                on_conflict="cpf_cnpj",
            ).execute()
            fid = r.data[0]["id"] if r.data else None
            if not fid:
                r2 = sb.table("fornecedores").select("id").eq(
                    "cpf_cnpj", forn["cpf_cnpj"]
                ).execute()
                fid = r2.data[0]["id"] if r2.data else None
            if fid:
                sb.table("participacoes").upsert(
                    {"licitacao_id": lic_id, "fornecedor_id": fid, "participou": True},
                    on_conflict="licitacao_id,fornecedor_id",
                ).execute()
                n_f += 1
        except Exception as e:
            if DEBUG:
                print(f"      [!] Erro fornecedor: {e}")

    # Empenhos: associa ao primeiro item da licitação
    n_e = 0
    if emps and itens:
        try:
            r = sb.table("itens_licitacao").select("id").eq(
                "licitacao_id", lic_id
            ).limit(1).execute()
            if r.data:
                item_id = r.data[0]["id"]
                # Limpa empenhos anteriores do item para evitar duplicatas
                sb.table("empenhos").delete().eq("item_id", item_id).execute()
                for emp in emps:
                    emp["item_id"] = item_id
                    try:
                        sb.table("empenhos").insert(emp).execute()
                        n_e += 1
                    except Exception as e2:
                        if DEBUG:
                            print(f"      [!] Erro empenho: {e2}")
        except Exception as e:
            if DEBUG:
                print(f"      [!] Erro empenhos: {e}")

    return n_i, n_f, n_e

def gravar_apenas_empenhos(lic_id, emps):
    """
    Regrava somente os empenhos de uma licitação (delete + insert).
    Não toca em itens nem fornecedores.
    Retorna o número de empenhos gravados.
    """
    n_e = 0
    if not emps:
        return 0
    try:
        r = sb.table("itens_licitacao").select("id").eq(
            "licitacao_id", lic_id
        ).limit(1).execute()
        if not r.data:
            if DEBUG:
                print(f"      [!] Nenhum item encontrado para licitacao_id={lic_id}")
            return 0
        item_id = r.data[0]["id"]
        sb.table("empenhos").delete().eq("item_id", item_id).execute()
        for emp in emps:
            emp["item_id"] = item_id
            try:
                sb.table("empenhos").insert(emp).execute()
                n_e += 1
            except Exception as e2:
                if DEBUG:
                    print(f"      [!] Erro empenho: {e2}")
    except Exception as e:
        if DEBUG:
            print(f"      [!] Erro ao gravar empenhos: {e}")
    return n_e


def parse_data_br(texto):
    """DD/MM/YYYY → YYYY-MM-DD (None se inválida)."""
    try:
        return datetime.strptime((texto or "").strip()[:10], "%d/%m/%Y").strftime("%Y-%m-%d")
    except Exception:
        return None

def inserir_licitacao(proc):
    """Insere (upsert em processo,orgao) uma licitação vista na listagem do portal e
    ainda ausente no banco. Classificação idêntica à da Etapa 1. Retorna o id ou None."""
    objeto = proc.get("objeto", "")
    registro = {
        "processo":      proc["texto"],
        "tipo_processo": classificar_tipo(proc["texto"]),
        "orgao":         ORGAO,
        "objeto":        objeto,
        "empresa":       "Fundo de Abastecimento Alimentar de Curitiba",
        "dt_abertura":   parse_data_br(proc.get("dt_abertura")),
        "situacao":      proc.get("situacao", ""),
        "canal":         classificar_canal(objeto),
        "relevante_af":  is_af(objeto),
        "coletado_em":   datetime.now(timezone.utc).isoformat(),
    }
    r = sb.table("licitacoes").upsert(registro, on_conflict="processo,orgao").execute()
    if r.data:
        return r.data[0]["id"]
    r2 = (sb.table("licitacoes").select("id").eq("processo", proc["texto"])
          .eq("orgao", ORGAO).limit(1).execute())
    return r2.data[0]["id"] if r2.data else None

def atualizar_licitacao(lic_id, campos):
    """Atualiza campos de uma licitação existente. Blindado."""
    try:
        sb.table("licitacoes").update(campos).eq("id", lic_id).execute()
    except Exception as e:
        print(f"      [!] Erro ao atualizar licitacao_id={lic_id}: {e}")

def extrair_totais_fornecedores(html):
    """Contadores do cabeçalho do detalhe (retiraram edital / participantes)."""
    texto = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    totais = {}
    for campo, pat in [("total_forn_retiraram_edital", r"Retiraram o Edital[:\s]+(\d+)"),
                       ("total_forn_participantes", r"Fornecedores Participantes[:\s]+(\d+)")]:
        m = re.search(pat, texto, re.I)
        if m:
            totais[campo] = int(m.group(1))
    return totais

def deletar_itens_licitacao(lic_id):
    try:
        sb.table("itens_licitacao").delete().eq("licitacao_id", lic_id).execute()
    except Exception as e:
        if DEBUG:
            print(f"      [!] Erro ao deletar itens de licitacao_id={lic_id}: {e}")

# ─── Funções de navegação no portal ───────────────────────────────────────────
def preencher_data(page, campo_id, valor):
    """
    Preenche campo de data JSF via triple-click + keyboard.type + Tab.
    IMPORTANTE: usar [id="..."] em vez de #id — IDs JSF com ':' quebram CSS.
    """
    campo = page.locator(f'[id="{campo_id}"]')
    if campo.count() == 0:
        if DEBUG:
            print(f"      [!] Campo {campo_id} não encontrado")
        return False
    campo.click(click_count=3)
    time.sleep(0.2)
    page.keyboard.type(valor, delay=50)
    time.sleep(0.3)
    page.keyboard.press("Tab")  # dispara onchange JSF
    time.sleep(0.5)
    return True

def _extrair_total_de_html(html):
    """
    Extrai o total de registros do HTML da página de resultados.

    Estrutura real do portal (confirmada no ingestao_supabase.py / Etapa 1):
        quantidade registros:</label></td><td><label>1238</label>
    O número fica dentro de um <label> em um <td> DIFERENTE do texto.
    Regex com re.DOTALL atravessa as tags intermediárias.
    """
    # Método 1: regex com DOTALL — confirmado no ingestao_supabase.py
    m = re.search(r"quantidade registros.*?(\d+)</label>", html, re.I | re.DOTALL)
    if m:
        return int(m.group(1))

    # Método 2: texto plano (fallback)
    texto = BeautifulSoup(html, "lxml").get_text()
    m2 = re.search(r"quantidade\s+registros[\s:]*?(\d+)", texto, re.I)
    return int(m2.group(1)) if m2 else 0

def fazer_pesquisa(page):
    """
    Executa pesquisa no portal com órgão e datas configurados.
    Retorna:
        N > 0              → N registros encontrados
        TOTAL_DESCONHECIDO → pesquisa OK mas não foi possível ler o contador
        0                  → nenhum resultado (ou falha na pesquisa)
    """
    # Selecionar órgão — aguarda elemento visível antes de interagir
    try:
        page.wait_for_selector("select", state="visible", timeout=20000)
    except PlaywrightTimeout:
        if DEBUG:
            print("    [~] Timeout aguardando select ficar visível")
    time.sleep(1)

    selects = page.locator("select")
    orgao_ok = False
    for i in range(selects.count()):
        sel = selects.nth(i)
        try:
            if sel.locator(f'option:has-text("{ORGAO}")').count() > 0:
                sel.wait_for(state="visible", timeout=10000)
                sel.select_option(label=ORGAO)
                time.sleep(1)
                orgao_ok = True
                if DEBUG:
                    print(f"    ✓ Órgão: {ORGAO}")
                break
        except PlaywrightTimeout:
            continue
    if not orgao_ok:
        # Sem o filtro de órgão a pesquisa traria a prefeitura inteira (ou nada):
        # é portal fora do ar/mudado, não "nenhuma licitação nova".
        raise PortalIndisponivel(f"Órgão {ORGAO} não encontrado no formulário do portal")

    # Preencher datas
    ok_ini = preencher_data(page, "form:dataInferiorInputDate", DT_INICIO)
    ok_fim = preencher_data(page, "form:j_id18InputDate",       DT_FIM)
    if DEBUG:
        print(f"    {'✓' if ok_ini else '✗'} Data inicial: {DT_INICIO}")
        print(f"    {'✓' if ok_fim else '✗'} Data final:   {DT_FIM}")

    # Clicar em Pesquisar
    btn = page.locator('[id="form:btSearch"], input[value="Pesquisar"]')
    if btn.count() == 0:
        print("    [!] Botão Pesquisar não encontrado")
        return 0
    btn.first.click()
    time.sleep(3)
    page.wait_for_load_state("networkidle", timeout=30000)
    time.sleep(1)

    # Tentar extrair total de registros via BeautifulSoup
    html  = page.content()
    total = _extrair_total_de_html(html)
    if total > 0:
        if DEBUG:
            print(f"    ✓ Total de registros: {total}")
        procs_pg1 = extrair_processos_pagina(page)
        if DEBUG:
            print(f"    ✓ Processos visíveis na pág. 1: {len(procs_pg1)}")
            for p in procs_pg1[:3]:
                print(f"      • {p['texto']} (link_id={p['link_id']})")
        return total

    # Fallback: se contador não foi lido mas há processos na página, continua
    if extrair_processos_pagina(page):
        print("    [~] Contador não lido, mas há processos visíveis → total desconhecido")
        return TOTAL_DESCONHECIDO

    return 0

def extrair_processos_pagina(page):
    """
    Extrai lista de processos da página atual de resultados.

    Estratégia (confirmada na Etapa 1 / ingestao_supabase.py):
    - Encontra a tabela que tem TH "processo" e "objeto"
    - Cada linha tem col[0] = número do processo (ex: "DS 70/2019 - SMSAN/FAAC")
    - O <a> da col[0] tem atributo id="form:tabela:N:j_id26" → usado para clicar
    """
    soup = BeautifulSoup(page.content(), "lxml")
    processos = []
    for tabela in soup.find_all("table"):
        ths = [th.get_text(strip=True).lower() for th in tabela.find_all("th")]
        if "processo" not in ths or "objeto" not in ths:
            continue
        for tr in tabela.find_all("tr")[1:]:
            cols = tr.find_all("td")
            if len(cols) < 3:
                continue
            proc_texto = cols[0].get_text(strip=True)
            if not re.match(r"^[A-Z]{2}\s+\d+/\d{4}", proc_texto):
                continue
            link = cols[0].find("a")
            link_id = link.get("id", "") if link else ""
            processos.append({
                "texto":   proc_texto,
                "link_id": link_id,
                "objeto":  cols[1].get_text(strip=True) if len(cols) > 1 else "",
                "dt_abertura": cols[2].get_text(strip=True) if len(cols) > 2 else "",
                "situacao": cols[3].get_text(strip=True) if len(cols) > 3 else "",
            })
        break  # tabela correta encontrada
    return processos

def ir_para_proxima_pagina(page, pag_atual):
    """
    Tenta navegar para a próxima página na tabela de resultados.
    Estratégia 1: clica no número (pag_atual+1) em td.rich-datascr-inact.
    Estratégia 2: clica no botão ">" (próxima página) do datascroller.
    Retorna True se navegou, False se não há próxima página.
    """
    prox = pag_atual + 1

    # Estratégia 1: clica no número da próxima página
    pags = page.locator("td.rich-datascr-inact")
    for i in range(pags.count()):
        elem = pags.nth(i)
        if elem.text_content().strip() == str(prox):
            try:
                elem.click()
                time.sleep(2)
                page.wait_for_load_state("networkidle", timeout=15000)
                return True
            except Exception as e:
                if DEBUG:
                    print(f"      [!] Erro ao clicar página {prox}: {e}")
                return False

    # Estratégia 2: botão ">" do datascroller (página seguinte)
    btn_prox = page.locator("td.rich-datascr-button").filter(has_text=">")
    if btn_prox.count() > 0:
        try:
            btn_prox.first.click()
            time.sleep(2)
            page.wait_for_load_state("networkidle", timeout=15000)
            return True
        except Exception as e:
            if DEBUG:
                print(f"      [!] Erro ao clicar botão '>': {e}")

    return False

def ir_para_pagina_lista(page, num_pagina):
    """
    Navega para a página num_pagina na tabela de resultados.
    Mantido para compatibilidade com refazer_pesquisa_e_navegar.
    """
    try:
        pags = page.locator("td.rich-datascr-inact")
        for i in range(pags.count()):
            elem = pags.nth(i)
            if elem.text_content().strip() == str(num_pagina):
                elem.click()
                time.sleep(2)
                page.wait_for_load_state("networkidle", timeout=15000)
                return True
        return False
    except Exception as e:
        if DEBUG:
            print(f"      [!] Erro ao ir para página {num_pagina}: {e}")
        return False

def aguardar_tabela_itens(page, timeout_ms=15000):
    """Aguarda a tabela form:tabelaItens aparecer e ter pelo menos uma linha."""
    try:
        page.wait_for_selector(
            '[id="form:tabelaItens"] tbody tr',
            timeout=timeout_ms,
        )
        return True
    except PlaywrightTimeout:
        return False

def coletar_todas_paginas_itens(page):
    """
    Coleta itens de todas as páginas da tabela form:tabelaItens no detalhe.
    Retorna (itens, forns, emps) consolidados de todas as páginas.
    """
    todos_itens, todos_forns, todos_emps = [], [], []
    seqs_vistos = set()

    pagina = 1
    while True:
        html = page.content()
        itens, forns, emps = extrair_itens_de_html(html)

        for item in itens:
            if item["seq"] not in seqs_vistos:
                seqs_vistos.add(item["seq"])
                todos_itens.append(item)

        if pagina == 1:
            todos_forns = forns
            todos_emps  = emps

        # Verifica se há próxima página de itens
        # Escopado para o datascroller da tabelaItens (j_id140),
        # evitando conflito com datascrollers de outras tabelas na página
        proximas = page.locator(
            '[id="form:tabelaItens:j_id140"] td.rich-datascr-inact'
        )
        prox_pagina = None
        for i in range(proximas.count()):
            elem = proximas.nth(i)
            txt  = elem.text_content().strip()
            if txt == str(pagina + 1):
                prox_pagina = elem
                break

        if prox_pagina is None:
            break

        if DEBUG:
            print(f"        → Página de itens {pagina + 1}...")
        # O datascroller interno pode estar fora da viewport ou dentro de
        # um painel JSF oculto. Estratégias em cascata:
        #   1. scroll_into_view_if_needed + click normal
        #   2. click(force=True) — bypassa checagem de visibilidade
        #   3. JavaScript .click() direto — ignora tudo de visibilidade
        clicou = False
        try:
            prox_pagina.scroll_into_view_if_needed(timeout=2000)
            prox_pagina.click(timeout=3000)
            clicou = True
        except Exception:
            pass
        if not clicou:
            try:
                prox_pagina.click(force=True, timeout=5000)
                clicou = True
            except Exception:
                pass
        if not clicou:
            # Fallback JS: invoca o onclick no datascroller escopado
            page_num_str = str(pagina + 1)
            page.evaluate(f"""() => {{
                const container = document.getElementById('form:tabelaItens:j_id140');
                if (!container) return;
                const tds = container.querySelectorAll('td.rich-datascr-inact');
                for (const td of tds) {{
                    if (td.textContent.trim() === '{page_num_str}') {{
                        td.click();
                        break;
                    }}
                }}
            }}""")
        time.sleep(1.5)
        page.wait_for_load_state("networkidle", timeout=10000)
        pagina += 1

    return todos_itens, todos_forns, todos_emps

def abrir_detalhe(page, processo):
    """
    Abre a página de detalhe de um processo clicando no link da listagem.

    O link tem id="form:tabela:N:j_id31" — usa seletor de atributo [id="..."]
    pois IDs com ':' quebram seletores CSS padrão no Playwright.
    """
    link_id = processo.get("link_id", "")
    if not link_id:
        if DEBUG:
            print(f"        [!] link_id ausente para: {processo.get('texto','?')}")
        return False
    try:
        elem = page.locator(f'[id="{link_id}"]')
        if elem.count() == 0:
            if DEBUG:
                print(f"        [!] Link não encontrado na página: id={link_id}")
            return False
        elem.first.click()
        time.sleep(1.5)
        page.wait_for_load_state("networkidle", timeout=30000)
        if not aguardar_tabela_itens(page, timeout_ms=15000):
            if DEBUG:
                print("        [~] Tabela de itens não carregou (pode estar vazia)")
        return True
    except Exception as e:
        if DEBUG:
            print(f"      [!] Erro ao abrir detalhe: {e}")
        return False

def voltar_para_lista(page):
    """
    Volta para a aba de listagem de licitações.
    No portal JSF/RichFaces, "Lista Licitações" é um <td> de aba,
    não um <a>. ID confirmado: form:abaPesquisa_lbl
    """
    try:
        aba = page.locator('[id="form:abaPesquisa_lbl"]')
        if aba.count() > 0:
            aba.first.click()
            time.sleep(1.5)
            page.wait_for_load_state("networkidle", timeout=15000)
            return True
        return False
    except:
        return False

class PortalIndisponivel(RuntimeError):
    """Portal não carregou / formulário irreconhecível — a execução deve falhar
    (status error), nunca ser registrada como 'concluída sem novidades'."""


def abrir_portal(page, tentativas=3):
    """page.goto com retentativas e backoff — o portal JSF é instável."""
    ultimo_erro = None
    for n in range(1, tentativas + 1):
        try:
            page.goto(PORTAL_URL, timeout=60000)
            page.wait_for_load_state("networkidle", timeout=60000)
            page.wait_for_selector("select", state="visible", timeout=20000)
            time.sleep(2)
            return
        except Exception as e:
            ultimo_erro = e
            print(f"    [!] Portal não carregou (tentativa {n}/{tentativas}): {str(e)[:150]}")
            time.sleep(15 * n)
    raise PortalIndisponivel(f"Portal inacessível após {tentativas} tentativas: {ultimo_erro}")


def refazer_pesquisa_e_navegar(page, pagina_alvo):
    """
    Recarrega o portal, refaz a pesquisa e navega até a página alvo.
    Retorna True se chegou na página alvo (ou se a pesquisa tem resultados).
    """
    try:
        abrir_portal(page)
        total = fazer_pesquisa(page)
    except Exception as e:
        print(f"    [!] Falha ao refazer pesquisa: {str(e)[:200]}")
        return False
    if total == 0:
        return False  # portal não retornou nada

    # Se total desconhecido ou positivo, tenta navegar
    for p in range(2, pagina_alvo + 1):
        if not ir_para_pagina_lista(page, p):
            # Tenta botão "próxima"
            if not ir_para_proxima_pagina(page, p - 1):
                return False
    return True

# ─── Carregar licitações do banco ─────────────────────────────────────────────
def carregar_licitacoes():
    """Carrega licitações do Supabase e identifica pendentes e sem empenhos."""
    # Paginar licitações
    lics = []
    offset = 0
    while True:
        r = sb.table("licitacoes").select(
            "id, processo, situacao, tipo_processo"
        ).range(offset, offset + 999).execute()
        lics.extend(r.data)
        if len(r.data) < 1000:
            break
        offset += 1000
    todas = {x["id"]: x for x in lics}

    # Paginar itens_licitacao
    itens = []
    offset = 0
    while True:
        r_itens = sb.table("itens_licitacao").select("id, licitacao_id").range(offset, offset + 999).execute()
        itens.extend(r_itens.data)
        if len(r_itens.data) < 1000:
            break
        offset += 1000
    ids_com_itens = set(x["licitacao_id"] for x in itens if x.get("licitacao_id"))
    item_id_to_lic = {x["id"]: x["licitacao_id"] for x in itens}

    # IDs de licitações que já têm empenhos (via item_id)
    emps = []
    offset = 0
    while True:
        r_emps = sb.table("empenhos").select("item_id").range(offset, offset + 999).execute()
        emps.extend(r_emps.data)
        if len(r_emps.data) < 1000:
            break
        offset += 1000
    lics_com_emp = set(
        item_id_to_lic[x["item_id"]]
        for x in emps
        if x.get("item_id") and x["item_id"] in item_id_to_lic
    )

    # Licitações "Concluído" com itens mas sem empenhos
    ids_sem_empenhos = set(
        lid for lid in ids_com_itens
        if lid not in lics_com_emp
        and todas.get(lid, {}).get("situacao", "") == "Concluído"
    )

    # Índice processo → id
    indice = {}
    for lic in todas.values():
        proc = lic.get("processo", "")
        if proc:
            indice[proc] = lic["id"]
            m = re.match(r'^([A-Z]{2}\s+\d+/\d{4})', proc)
            if m:
                indice[m.group(1)] = lic["id"]

    return todas, ids_com_itens, indice, ids_sem_empenhos

# ─── Main ─────────────────────────────────────────────────────────────────────
def _registrar_final(stats, final_status, dt_inicio, dt_fim, erro_resumo=None):
    escrever_progresso(PROGRESS_FILE, stats, etapa="finalizado", status=final_status,
                       dt_inicio=dt_inicio, dt_fim=dt_fim, portal_url=PORTAL_URL,
                       orgao=ORGAO, regs_por_pag=REGS_POR_PAG)
    registrar_execucao(stats, final_status, dt_inicio=dt_inicio, dt_fim=dt_fim,
                       erro_resumo=erro_resumo)


def main(dt_inicio: str = None, dt_fim: str = None) -> str:
    """Coleta incremental. Para cada processo listado no portal na janela:
      - ausente no banco      → INSERE a licitação e coleta itens/fornecedores/empenhos;
      - presente, sem itens   → coleta o detalhe;
      - situação mudou        → atualiza a situação e recoleta o detalhe
                                (participantes/empenhos surgem ao longo do processo);
      - sem mudança           → pulado.
    Retorna o status final ('completed' | 'cancelled' | 'error')."""
    global INTERROMPIDO

    print("=" * 65)
    print("AgroIA-RMC — Coleta de Licitações, Itens e Empenhos (v10)")
    print(f"Início: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"Janela: {dt_inicio} → {dt_fim}")
    print(f"FORCAR_REPROCESSAR: {FORCAR_REPROCESSAR}")
    print(f"FORCAR_EMPENHOS:    {FORCAR_EMPENHOS}")
    print("=" * 65)

    kw = dict(dt_inicio=dt_inicio, dt_fim=dt_fim, portal_url=PORTAL_URL,
              orgao=ORGAO, regs_por_pag=REGS_POR_PAG)
    stats = {
        "processados":    0,
        "itens":          0,
        "fornecedores":   0,
        "empenhos":       0,
        "pulados":        0,
        "erros":          0,
        "nao_encontrados": 0,
        "licitacoes_novas": 0,
        "licitacoes_atualizadas": 0,
        "sem_itens":      0,
        # UTC tz-aware: duracao_seg e staleness no backend dependem disso.
        "iniciado_em":    datetime.now(timezone.utc).isoformat(),
    }
    escrever_progresso(PROGRESS_FILE, stats, etapa="iniciando", status="running", **kw)

    print("\n[0] Carregando licitações do Supabase...")
    todas, ids_com_itens, indice, ids_sem_empenhos = carregar_licitacoes()
    print(f"    {len(todas)} licitações no banco | {len(ids_com_itens)} com itens | "
          f"{len(ids_sem_empenhos)} 'Concluído' sem empenhos")

    if FORCAR_EMPENHOS and not ids_sem_empenhos:
        print("\n    Nenhuma licitação pendente de empenhos. Encerrando.")
        _registrar_final(stats, "completed", dt_inicio, dt_fim)
        return "completed"

    falha = None  # motivo de encerramento prematuro (coleta incompleta)

    with sync_playwright() as p:
        print("\n[1] Abrindo navegador...")
        browser = p.chromium.launch(headless=HEADLESS, slow_mo=SLOW_MO, args=LAUNCH_ARGS)
        try:
            page = browser.new_context().new_page()

            print("[2] Acessando portal e fazendo pesquisa...")
            abrir_portal(page)
            total = fazer_pesquisa(page)

            if total == 0:
                print("\n[=] O portal não retornou processos na janela consultada.")
                total_pags = 0
            elif total == TOTAL_DESCONHECIDO:
                total_pags = None
                print("\n[3] Total de registros desconhecido. Paginando até esgotar...")
            else:
                total_pags = math.ceil(total / REGS_POR_PAG)
                stats["total_portal"] = total
                print(f"\n[3] {total} registros em {total_pags} páginas. Iniciando coleta...")
            stats["total_paginas"] = total_pags

            pag_atual = 1
            paginas_sem_processo = 0

            while not INTERROMPIDO and total_pags != 0:
                if total_pags is not None and pag_atual > total_pags:
                    break

                print(f"\n--- Página {pag_atual}" + (f"/{total_pags}" if total_pags else "") + " ---")
                stats["pagina"] = pag_atual
                # Heartbeat por página: mesmo quando tudo é pulado o backend vê progresso
                # (evita a auto-cura marcar como travada uma coleta que está andando).
                escrever_progresso(PROGRESS_FILE, stats, etapa="coletando", status="running", **kw)

                processos = extrair_processos_pagina(page)
                if not processos:
                    print("    [!] Nenhum processo encontrado — possivelmente perdeu estado. Refazendo...")
                    if not refazer_pesquisa_e_navegar(page, pag_atual):
                        falha = f"Falha ao recuperar a listagem na página {pag_atual}"
                        break
                    processos = extrair_processos_pagina(page)

                if not processos:
                    paginas_sem_processo += 1
                    if paginas_sem_processo >= 3:
                        falha = "3 páginas consecutivas sem processos"
                        break
                    pag_atual += 1
                    continue
                paginas_sem_processo = 0

                print(f"    {len(processos)} processos encontrados")

                for proc in processos:
                    if INTERROMPIDO:
                        break

                    texto = proc.get("texto", "")
                    situacao_portal = proc.get("situacao", "")

                    lic_id = None
                    for chave in [texto, texto.split(" - ")[0] if " - " in texto else texto]:
                        if chave in indice:
                            lic_id = indice[chave]
                            break

                    if not lic_id:
                        if FORCAR_EMPENHOS:
                            stats["nao_encontrados"] += 1
                            continue
                        try:
                            lic_id = inserir_licitacao(proc)
                        except Exception as e:
                            lic_id = None
                            print(f"    [!] Erro ao inserir '{texto}': {e}")
                        if not lic_id:
                            registrar_erro(stats, texto, "Falha ao inserir licitação nova no banco")
                            continue
                        stats["licitacoes_novas"] += 1
                        indice[texto] = lic_id
                        todas[lic_id] = {"id": lic_id, "processo": texto, "situacao": situacao_portal}
                        print(f"    [+] NOVA: {texto} (ID={lic_id}) — {proc.get('objeto', '')[:70]}")
                    elif FORCAR_EMPENHOS:
                        if lic_id not in ids_sem_empenhos:
                            stats["pulados"] += 1
                            continue
                        print(f"    [emp] Coletando empenhos: {texto} (ID={lic_id})")
                    else:
                        sit_banco = (todas.get(lic_id) or {}).get("situacao") or ""
                        mudou = bool(situacao_portal) and situacao_portal != sit_banco
                        if mudou:
                            atualizar_licitacao(lic_id, {"situacao": situacao_portal})
                            todas.setdefault(lic_id, {})["situacao"] = situacao_portal
                            stats["licitacoes_atualizadas"] += 1
                        if FORCAR_REPROCESSAR:
                            motivo = "reprocessar"
                        elif lic_id not in ids_com_itens:
                            motivo = "sem itens"
                        elif mudou:
                            motivo = f"situação {sit_banco!r} → {situacao_portal!r}"
                        else:
                            stats["pulados"] += 1
                            continue
                        print(f"    [>] {texto} (ID={lic_id}) — {motivo}")
                        if FORCAR_REPROCESSAR and lic_id in ids_com_itens:
                            deletar_itens_licitacao(lic_id)
                            ids_com_itens.discard(lic_id)

                    # Abre detalhe
                    if not abrir_detalhe(page, proc):
                        print("        [!] Falha ao abrir detalhe")
                        registrar_erro(stats, texto, "Falha ao abrir detalhe da licitação")
                        if not refazer_pesquisa_e_navegar(page, pag_atual):
                            falha = f"Falha ao recuperar a listagem na página {pag_atual}"
                            break
                        continue

                    itens, forns, emps = coletar_todas_paginas_itens(page)

                    if FORCAR_EMPENHOS:
                        n_e = gravar_apenas_empenhos(lic_id, emps)
                        stats["processados"] += 1
                        if n_e > 0:
                            ids_sem_empenhos.discard(lic_id)
                            stats["empenhos"] += n_e
                            print(f"        ✓ {n_e} empenhos gravados")
                        else:
                            print("        [~] Nenhum empenho no portal")
                    else:
                        totais = extrair_totais_fornecedores(page.content())
                        if totais:
                            atualizar_licitacao(lic_id, totais)
                        stats["processados"] += 1
                        if itens:
                            n_i, n_f, n_e = gravar(lic_id, itens, forns, emps)
                            stats["itens"]        += n_i
                            stats["fornecedores"] += n_f
                            stats["empenhos"]     += n_e
                            ids_com_itens.add(lic_id)
                            print(f"        ✓ {n_i} itens, {n_f} fornecedores, {n_e} empenhos")
                        else:
                            # Processo recém-publicado pode ainda não ter itens: fica
                            # "sem itens" e é retentado nas próximas execuções.
                            stats["sem_itens"] += 1
                            print("        [~] Sem itens no portal (será retentado)")

                    escrever_progresso(PROGRESS_FILE, stats, etapa="coletando", status="running", **kw)

                    if not voltar_para_lista(page):
                        print("        [~] Aba 'Lista Licitações' não encontrada. Refazendo pesquisa...")
                        if not refazer_pesquisa_e_navegar(page, pag_atual):
                            falha = f"Falha ao voltar à listagem na página {pag_atual}"
                            break

                    time.sleep(DELAY)

                if INTERROMPIDO or falha:
                    break

                if total_pags is not None and pag_atual >= total_pags:
                    print(f"\n    Página {pag_atual}/{total_pags} — última página. Coleta concluída.")
                    break

                print(f"\n    Navegando para página {pag_atual + 1}...")
                if not ir_para_proxima_pagina(page, pag_atual):
                    if total_pags is None:
                        print("    → Sem mais páginas. Coleta concluída.")
                        break
                    print(f"    [!] Não conseguiu ir para página {pag_atual + 1}. Refazendo...")
                    if not refazer_pesquisa_e_navegar(page, pag_atual + 1):
                        falha = f"Falha ao navegar para a página {pag_atual + 1}/{total_pags}"
                        break
                pag_atual += 1
        finally:
            browser.close()

    print("\n" + "=" * 65)
    print("CONCLUÍDO!" if not falha else f"INCOMPLETO: {falha}")
    print("=" * 65)
    for rotulo, chave in [("Licitações novas", "licitacoes_novas"),
                          ("Situação atualizada", "licitacoes_atualizadas"),
                          ("Detalhes coletados", "processados"), ("Itens gravados", "itens"),
                          ("Fornecedores", "fornecedores"), ("Empenhos", "empenhos"),
                          ("Sem itens (retentar)", "sem_itens"), ("Pulados", "pulados"),
                          ("Não encontrados", "nao_encontrados"), ("Erros", "erros")]:
        print(f"  {rotulo + ':':22s}{stats.get(chave, 0)}")
    if INTERROMPIDO:
        print("  (Interrompido — rode novamente para continuar)")
    print("=" * 65)

    if INTERROMPIDO:
        final_status = "cancelled"
    elif falha:
        final_status = "error"
    else:
        final_status = "completed"
    _registrar_final(stats, final_status, dt_inicio, dt_fim,
                     erro_resumo=(f"Coleta incompleta: {falha}" if falha else None))
    return final_status


if __name__ == "__main__":
    args = parse_args()

    DT_INICIO = args.dt_inicio if args.dt_inicio else get_data_inicio_padrao()
    DT_FIM = args.dt_fim if args.dt_fim else get_data_fim_padrao()
    PROGRESS_FILE = args.progress_file
    ORIGEM = args.origem
    if args.somente_empenhos:
        FORCAR_EMPENHOS = True

    print(f"[>] Coleta iniciada ({ORIGEM})")
    print(f"    Data inicial: {DT_INICIO}")
    print(f"    Data final:   {DT_FIM}")
    print(f"    Arquivo de progresso: {PROGRESS_FILE}")

    try:
        resultado = main(dt_inicio=DT_INICIO, dt_fim=DT_FIM)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[!] Coleta falhou com erro fatal:\n{tb}")
        stats_erro = {"iniciado_em": datetime.now(timezone.utc).isoformat()}
        escrever_progresso(PROGRESS_FILE, stats_erro, etapa="falha", status="error",
                          dt_inicio=DT_INICIO, dt_fim=DT_FIM, portal_url=PORTAL_URL,
                          orgao=ORGAO, regs_por_pag=REGS_POR_PAG)
        registrar_execucao(stats_erro, "error", dt_inicio=DT_INICIO, dt_fim=DT_FIM,
                          erro_resumo=tb)
        raise
    # Exit code != 0 em coleta incompleta: o run do GitHub Actions fica vermelho.
    raise SystemExit(1 if resultado == "error" else 0)
