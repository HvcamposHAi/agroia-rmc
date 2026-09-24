"""
AgroIA-RMC — Coleta de licitações via Portal da Transparência de Curitiba
=========================================================================
Fonte: https://www.transparencia.curitiba.pr.gov.br/sgp/licitacoes.aspx
       (órgão FAAC = Fundo de Abastecimento Alimentar de Curitiba, "Setor Edital SMSAN/FAAC")

POR QUE ESTA FONTE: o portal antigo (consultalicitacao.curitiba.pr.gov.br:9090, JSF)
foi DESATIVADO pela Prefeitura — o registro DNS não existe mais (NXDOMAIN nos
servidores autoritativos da Akamai, verificado em 23/09/2026). O Portal da
Transparência consulta o MESMO sistema de compras (SGP): mesma numeração de
processos (ex.: "PE 1/2026"), mesmos objetos, mesma "Data Abertura Edital".

Vantagens: HTTP puro (ASP.NET WebForms + UpdatePanel) — sem Playwright/navegador;
empenhos vêm COM valor (empenhado/liquidado/pago) e itens com fornecedor vencedor.

Fluxo por ano (padrão: ano anterior + ano corrente):
  pesquisa (órgão FAAC, ano) → pagina a grade → para cada processo decide se precisa
  do detalhe → postback "Ver detalhes" (devolve o id) → GET LicitacoesDetalhes.aspx?id=N
  → grava licitação / itens / fornecedores / participações / empenhos.

Uso:
  python coleta_transparencia.py                      # incremental (ano anterior + corrente)
  python coleta_transparencia.py --anos 2019-2026     # varredura completa
  python coleta_transparencia.py --dry-run --limite 5 # só mostra o que faria (não grava)
"""

import os
import re
import sys
import json
import time
import signal
import argparse
from datetime import datetime, date, timezone

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from classificacao_licitacao import classificar_tipo, classificar_canal, is_af
from enriquecer_classificacao import classificar_item, is_relevante_agro

load_dotenv()

BASE = "https://www.transparencia.curitiba.pr.gov.br"
URL_BUSCA = f"{BASE}/sgp/licitacoes.aspx"
URL_DETALHE = f"{BASE}/Sgp/LicitacoesDetalhes.aspx?id={{id}}"
ORGAO_FILTRO = "FAAC"            # value do ddlOrgao
ORGAO_DB = "SMSAN/FAAC"          # valor de licitacoes.orgao (sufixo do processo no corpus)
EMPRESA = "Fundo de Abastecimento Alimentar de Curitiba"
DELAY = float(os.getenv("COLETA_DELAY", "0.7"))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AgroIA-RMC/1.0 (pesquisa academica PPGCA/UEPG)"

P = "ctl00$cphMasterPrincipal$"
PAINEL_GRADE = P + "uplGrid"

# Situações do portal da Transparência que não mudam mais. Processos fora deste
# conjunto são reconsultados a cada execução (empenhos/vencedores ainda evoluem).
SITUACOES_TERMINAIS = {
    "Empenhado", "Processo Concluído", "Processo Anulado", "Número Descartado",
    "Pedido ou Empenho Anulado", "Exportado para o SisMAB",
}

INTERROMPIDO = False


def _sigint(sig, frame):
    global INTERROMPIDO
    INTERROMPIDO = True
    print("\n[!] Interrupção solicitada — terminando o processo atual...")


signal.signal(signal.SIGINT, _sigint)
if hasattr(signal, "SIGTERM"):
    signal.signal(signal.SIGTERM, _sigint)


class PortalIndisponivel(RuntimeError):
    """Portal fora do ar ou com estrutura irreconhecível — a execução deve FALHAR
    (status error), nunca ser registrada como 'concluída sem novidades'."""


# ─── Utilidades ──────────────────────────────────────────────────────────────
def agora_iso():
    return datetime.now(timezone.utc).isoformat()


def parse_brl(txt):
    """'R$ 1.234,56' / '1.234,56' / '20.000' → float."""
    t = re.sub(r"[^\d,.-]", "", txt or "")
    if not t:
        return 0.0
    try:
        return float(t.replace(".", "").replace(",", "."))
    except ValueError:
        return 0.0


def parse_data_br(txt):
    try:
        return datetime.strptime((txt or "").strip()[:10], "%d/%m/%Y").strftime("%Y-%m-%d")
    except Exception:
        return None


def normalizar_processo(txt):
    """'PE 83 /2026' / 'PE 83/2026' → 'PE 83/2026'."""
    t = re.sub(r"\s+", " ", (txt or "").strip())
    return re.sub(r"\s*/\s*", "/", t)


def chave_db(proc):
    return f"{normalizar_processo(proc)} - {ORGAO_DB}"


def so_digitos(doc):
    return re.sub(r"\D", "", doc or "")


def formatar_doc(d):
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return d


def tipo_forn(razao):
    r = (razao or "").upper()
    if "COOPERATIV" in r or "COOP." in r:
        return "COOPERATIVA"
    if "ASSOCIA" in r:
        return "ASSOCIACAO"
    return "EMPRESA"


# ─── Cliente do portal ───────────────────────────────────────────────────────
class PortalTransparencia:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = UA
        self.campos = {}

    def _req(self, metodo, url, tentativas=4, **kw):
        ultimo = None
        for n in range(1, tentativas + 1):
            try:
                r = self.s.request(metodo, url, timeout=120, **kw)
                if r.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {r.status_code}")
                r.encoding = "utf-8"
                return r
            except Exception as e:
                ultimo = e
                print(f"    [!] {metodo} falhou ({n}/{tentativas}): {str(e)[:150]}")
                time.sleep(5 * n)
        raise PortalIndisponivel(f"Portal da Transparência inacessível: {ultimo}")

    @staticmethod
    def _campos_form(soup):
        d = {}
        for i in soup.select("form input"):
            n = i.get("name")
            if n and i.get("type") not in ("submit", "image", "button", "checkbox"):
                d[n] = i.get("value", "")
        for s in soup.select("form select"):
            o = s.find("option", selected=True) or s.find("option")
            d[s["name"]] = o.get("value", "") if o else ""
        return d

    @staticmethod
    def _parse_delta(texto):
        """Resposta MS AJAX: 'len|tipo|id|conteúdo|' repetido."""
        out, i = [], 0
        while i < len(texto):
            j = texto.index("|", i); n = int(texto[i:j]); i = j + 1
            j = texto.index("|", i); tipo = texto[i:j]; i = j + 1
            j = texto.index("|", i); ident = texto[i:j]; i = j + 1
            out.append((tipo, ident, texto[i:i + n])); i += n + 1
        return out

    def _postback(self, alvo):
        f = dict(self.campos)
        f.update({"ctl00$smaMasterPrincipal": f"{PAINEL_GRADE}|{alvo}",
                  "__EVENTTARGET": alvo, "__EVENTARGUMENT": "", "__ASYNCPOST": "true"})
        r = self._req("POST", URL_BUSCA, data=f,
                      headers={"X-MicrosoftAjax": "Delta=true", "X-Requested-With": "XMLHttpRequest"})
        try:
            partes = self._parse_delta(r.text)
        except Exception:
            raise PortalIndisponivel(f"Resposta inesperada do portal: {r.text[:200]!r}")
        paineis, redirect = {}, None
        for tipo, ident, conteudo in partes:
            if tipo == "updatePanel":
                paineis[ident] = conteudo
            elif tipo == "hiddenField":
                self.campos[ident] = conteudo
            elif tipo == "pageRedirect":
                redirect = requests.utils.unquote(conteudo)
            elif tipo == "error":
                raise PortalIndisponivel(f"Erro do portal: {conteudo[:200]}")
        return paineis, redirect

    def pesquisar(self, ano):
        """Pesquisa FAAC no ano. Retorna o HTML da 1ª página da grade."""
        r = self._req("GET", URL_BUSCA)
        soup = BeautifulSoup(r.text, "lxml")
        ddl = soup.find(id="cphMasterPrincipal_ddlOrgao")
        if not ddl or not ddl.find("option", value=ORGAO_FILTRO):
            raise PortalIndisponivel("Formulário mudou: órgão FAAC não encontrado no filtro")
        self.campos = self._campos_form(soup)
        self.campos[P + "ddlOrgao"] = ORGAO_FILTRO
        self.campos[P + "txtAnoProcesso"] = str(ano)
        paineis, _ = self._postback(P + "lnbPesquisar")
        grade = paineis.get("cphMasterPrincipal_uplGrid")
        if grade is None:
            raise PortalIndisponivel("Pesquisa não devolveu a grade de resultados")
        return grade

    @staticmethod
    def linhas_grade(html):
        soup = BeautifulSoup(html, "lxml")
        tabela = soup.find(id="cphMasterPrincipal_gdvLicitacao")
        linhas = []
        if tabela:
            for tr in tabela.find_all("tr")[1:]:
                tds = tr.find_all("td")
                if len(tds) < 9:
                    continue
                a = tds[0].find("a")
                m = re.search(r"__doPostBack\('([^']+)'", (a.get("href") if a else "") or "")
                linhas.append({
                    "processo":   normalizar_processo(tds[0].get_text(" ", strip=True)),
                    "modalidade": tds[1].get_text(" ", strip=True),
                    "objeto":     tds[3].get_text(" ", strip=True),
                    "valor":      parse_brl(tds[4].get_text(strip=True)),
                    "dt_publicacao": tds[6].get_text(strip=True),
                    "protocolo":  tds[7].get_text(strip=True),
                    "situacao":   tds[8].get_text(" ", strip=True),
                    "alvo":       m.group(1) if m else None,
                })
        return linhas, soup

    def proxima_pagina(self, soup, pagina_atual):
        """Postback para a página seguinte. Retorna o HTML da grade ou None se não houver.
        O paginador mostra ~10 números + '...' nas pontas; o alvo tem a forma
        'ucPaginadorBaixo$<índice do link>_pg<nº da página>' (ou '_pg...' no '...').
        Atenção: o prefixo é o ÍNDICE do link, não a página (ex.: '10_pg12')."""
        links = []
        for a in soup.select("a[href*=ucPaginadorBaixo]"):
            m = re.search(r"'(ctl00\$cphMasterPrincipal\$ucPaginadorBaixo\$\d+_pg([^']*))'", a.get("href", ""))
            if m:
                links.append((m.group(1), m.group(2)))
        alvo = next((t for t, pg in links if pg == str(pagina_atual + 1)), None)
        if alvo is None and len(links) > 1 and links[-1][1] == "...":
            alvo = links[-1][0]   # '...' à direita → próximo bloco
        if alvo is None:
            return None
        paineis, _ = self._postback(alvo)
        return paineis.get("cphMasterPrincipal_uplGrid")

    def id_detalhe(self, alvo):
        """Postback 'Ver detalhes' → redirect .../LicitacoesDetalhes.aspx?id=N."""
        _, redirect = self._postback(alvo)
        m = re.search(r"id=(\d+)", redirect or "")
        return int(m.group(1)) if m else None

    def detalhe(self, id_det):
        r = self._req("GET", URL_DETALHE.format(id=id_det))
        return parse_detalhe(r.text)


def _tabela(soup, ident):
    """Linhas (lista de listas de <td>) de uma grade; [] se 'Nenhuma informação'."""
    t = soup.find(id=ident)
    if not t:
        return []
    out = []
    for tr in t.find_all("tr")[1:]:
        tds = tr.find_all("td")
        if len(tds) <= 1:
            continue
        out.append(tds)
    return out


def parse_detalhe(html):
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style"]):
        t.decompose()
    linhas = [l for l in soup.get_text("\n", strip=True).split("\n") if l]

    def campo(rotulo):
        for i, l in enumerate(linhas):
            if l.rstrip(":").strip().lower() == rotulo.lower() and i + 1 < len(linhas):
                prox = linhas[i + 1]
                # rótulo seguido de outro rótulo = campo vazio
                return "" if prox.endswith(":") else prox
        return ""

    titulo = next((l for l in linhas if l.startswith("Detalhes Licitacao -")), "")
    det = {
        "processo":   normalizar_processo(titulo.replace("Detalhes Licitacao -", "")),
        "objeto":     campo("Licitação/Contratação"),
        "empresa":    campo("Empresa"),
        "setor":      campo("Setor/Órgão"),
        "modalidade": campo("Modalidade da Contratação"),
        "situacao":   campo("Situação do Processo"),
        "nr_edital":  campo("Nº Edital"),
        "dt_abertura": parse_data_br(campo("Data Abertura Edital")),
        "setor_edital": campo("Setor Edital"),
        "total_forn_retiraram_edital": int(parse_brl(campo("Total de Forn. que Retiraram o Edital")) or 0),
        "total_forn_participantes": int(parse_brl(campo("Total de Fornecedores Participantes")) or 0),
        "participantes": [], "itens": [], "empenhos": [], "arquivos": [],
    }
    if not det["processo"]:
        raise PortalIndisponivel("Página de detalhe sem o cabeçalho esperado")

    for tds in _tabela(soup, "cphMasterPrincipal_gdvFornecedoresParticipantes"):
        doc = so_digitos(tds[0].get_text(strip=True))
        if len(doc) >= 11:
            det["participantes"].append({"doc": doc, "razao": tds[1].get_text(" ", strip=True)})

    for seq, tds in enumerate(_tabela(soup, "cphMasterPrincipal_gdvItensProcesso"), start=1):
        if len(tds) < 7:
            continue
        det["itens"].append({
            "seq": seq,
            "descricao": tds[0].get_text(" ", strip=True),
            "qt": parse_brl(tds[1].get_text(strip=True)),
            "unidade": tds[2].get_text(" ", strip=True),
            "vencedor": tds[3].get_text(" ", strip=True),
            "vencedor_doc": so_digitos(tds[4].get_text(strip=True)),
            "v_unit": parse_brl(tds[5].get_text(strip=True)),
            "v_total": parse_brl(tds[6].get_text(strip=True)),
        })

    for tds in _tabela(soup, "cphMasterPrincipal_gdvEmpenhoItens"):
        if len(tds) < 5:
            continue
        link = tds[-1].find("a")
        m = re.search(r"exercicio=(\d{4})", (link.get("href") if link else "") or "")
        det["empenhos"].append({
            "razao": tds[1].get_text(" ", strip=True),
            "doc": so_digitos(tds[2].get_text(strip=True)),
            "valor": parse_brl(tds[3].get_text(strip=True)),
            "nr": tds[4].get_text(strip=True),
            "ano": int(m.group(1)) if m else None,
        })

    for tds in _tabela(soup, "cphMasterPrincipal_gdvArquivos"):
        a = tds[-1].find("a")
        if a and a.get("href"):
            det["arquivos"].append({"nome": tds[0].get_text(" ", strip=True), "url": a["href"]})
    return det


# ─── Banco (Supabase) ────────────────────────────────────────────────────────
class Banco:
    def __init__(self, dry_run=False):
        from supabase import create_client
        url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError("Missing required env vars: SUPABASE_URL, SUPABASE_KEY")
        self.sb = create_client(url, key)
        self.dry = dry_run
        self._forn_cache = {}
        self.novas = set()   # processos inseridos nesta execução

    def _todas(self, tabela, colunas):
        out, off = [], 0
        while True:
            d = self.sb.table(tabela).select(colunas).range(off, off + 999).execute().data
            out += d
            if len(d) < 1000:
                return out
            off += 1000

    def carregar_indice(self):
        lics = self._todas("licitacoes", "id,processo,situacao,url_detalhe")
        itens = self._todas("itens_licitacao", "licitacao_id,codigo")
        self.lics = {l["processo"]: l for l in lics}
        self.com_itens = {i["licitacao_id"] for i in itens}
        # Itens gravados pelo portal antigo têm 'codigo'; os da Transparência não.
        # Itens legados nunca são regravados (seq/código de esquema diferente).
        self.itens_legado = {i["licitacao_id"] for i in itens if (i.get("codigo") or "").strip()}
        print(f"    {len(self.lics)} licitações | {len(self.com_itens)} com itens")

    def fornecedor_id(self, doc, razao):
        """Id do fornecedor pelo documento. A base tem ~1,4 mil CNPJs gravados nas duas
        grafias (com e sem pontuação); as participações/empenhos da coleta usam a
        grafia SÓ DÍGITOS — preferi-la evita participações duplicadas."""
        doc = so_digitos(doc)
        if len(doc) < 11:
            return None
        if doc in self._forn_cache:
            return self._forn_cache[doc]
        r = (self.sb.table("fornecedores").select("id,cpf_cnpj")
             .in_("cpf_cnpj", [doc, formatar_doc(doc)]).order("id").execute())
        if r.data:
            so_dig = [f for f in r.data if f["cpf_cnpj"] == doc]
            fid = (so_dig or r.data)[0]["id"]
        elif self.dry:
            fid = -1
        else:
            ins = self.sb.table("fornecedores").insert({
                "cpf_cnpj": doc, "razao_social": razao, "tipo": tipo_forn(razao),
                "fonte": "PORTAL_TRANSPARENCIA",
            }).execute()
            fid = ins.data[0]["id"]
        self._forn_cache[doc] = fid
        return fid

    def gravar(self, det, linha, lic_existente):
        """Grava licitação + itens + participações + empenhos. Retorna contadores."""
        c = {"itens": 0, "fornecedores": 0, "empenhos": 0}
        processo = chave_db(det["processo"] or linha["processo"])
        objeto = det["objeto"] or linha["objeto"]
        url_det = URL_DETALHE.format(id=det["_id"])
        campos = {
            "total_forn_retiraram_edital": det["total_forn_retiraram_edital"],
            "total_forn_participantes": det["total_forn_participantes"],
            "url_detalhe": url_det,
        }
        if lic_existente is None:
            campos.update({
                "processo": processo, "tipo_processo": classificar_tipo(processo),
                "orgao": ORGAO_DB, "objeto": objeto, "empresa": det["empresa"] or EMPRESA,
                "setor": det["setor"] or None, "modalidade": det["modalidade"] or None,
                "nr_edital": det["nr_edital"] or None,
                "dt_abertura": det["dt_abertura"] or parse_data_br(linha["dt_publicacao"]),
                "situacao": det["situacao"] or linha["situacao"],
                "canal": classificar_canal(objeto), "relevante_af": is_af(objeto),
                "coletado_em": agora_iso(),
            })
        elif lic_existente["id"] not in self.itens_legado:
            # Registro desta fonte: situação no mesmo vocabulário → pode atualizar.
            campos["situacao"] = det["situacao"] or linha["situacao"]
        # (Licitações do portal antigo mantêm a 'situacao' original — vocabulário
        #  diferente, ex. "Concluído" × "Processo Concluído"; não misturar.)

        if self.dry:
            print(f"        [dry] {'INSERT' if lic_existente is None else 'UPDATE'} {processo}: "
                  f"{len(det['itens'])} itens, {len(det['participantes'])} part., {len(det['empenhos'])} emp.")
            return None, c

        if lic_existente is None:
            r = self.sb.table("licitacoes").upsert(campos, on_conflict="processo,orgao").execute()
            lic_id = r.data[0]["id"]
            # Registrado já aqui: se itens/empenhos falharem depois, a licitação nova
            # continua contada e indexada (e é retentada como "sem itens").
            self.lics[processo] = {"id": lic_id, "processo": processo,
                                   "situacao": campos["situacao"], "url_detalhe": url_det}
            self.novas.add(processo)
        else:
            lic_id = lic_existente["id"]
            self.sb.table("licitacoes").update(campos).eq("id", lic_id).execute()

        # Itens (só quando não há itens legados do portal antigo)
        if lic_id not in self.itens_legado and det["itens"]:
            registros = []
            for it in det["itens"]:
                cultura, cat = classificar_item(it["descricao"])
                registros.append({
                    "licitacao_id": lic_id, "seq": it["seq"], "codigo": None,
                    "descricao": it["descricao"], "descricao_completa": it["descricao"],
                    "qt_solicitada": it["qt"], "unidade_medida": it["unidade"],
                    "valor_unitario": it["v_unit"],
                    "valor_total": it["v_total"] or it["qt"] * it["v_unit"],
                    # "categoria" é legado (domínio restrito por CHECK; = "OUTRO" em 99,9% do corpus):
                    # a classificação vigente é categoria_v2.
                    "cultura": cultura, "categoria": "OUTRO", "categoria_v2": cat,
                    "relevante_agro": is_relevante_agro(cat),
                })
            self.sb.table("itens_licitacao").upsert(registros, on_conflict="licitacao_id,seq").execute()
            c["itens"] = len(registros)
            self.com_itens.add(lic_id)

        # Participantes + vencedores
        vencedores = {it["vencedor_doc"] for it in det["itens"] if it["vencedor_doc"]}
        docs = {p["doc"]: p["razao"] for p in det["participantes"]}
        for it in det["itens"]:
            if it["vencedor_doc"] and it["vencedor_doc"] not in docs:
                docs[it["vencedor_doc"]] = it["vencedor"]
        for doc, razao in docs.items():
            fid = self.fornecedor_id(doc, razao)
            if not fid:
                continue
            self.sb.table("participacoes").upsert({
                "licitacao_id": lic_id, "fornecedor_id": fid, "participou": True,
                "vencedor": doc in vencedores,
            }, on_conflict="licitacao_id,fornecedor_id").execute()
            c["fornecedores"] += 1

        # Empenhos — convenção do corpus: vinculados ao 1º item da licitação.
        # Mescla por número (atualiza valor/fornecedor, insere os novos, nunca apaga:
        # preserva dt_empenho coletada pelo portal antigo).
        if det["empenhos"]:
            item_ids = [r["id"] for r in self.sb.table("itens_licitacao").select("id")
                        .eq("licitacao_id", lic_id).order("id").execute().data]
            if item_ids:
                item_id = item_ids[0]
                # Procura em TODOS os itens: a base legada nem sempre usou o mesmo "1º item".
                existentes = {e["nr_empenho"]: e["id"] for e in self.sb.table("empenhos")
                              .select("id,nr_empenho").in_("item_id", item_ids).execute().data}
                for e in det["empenhos"]:
                    reg = {"valor_empenhado": e["valor"],
                           "fornecedor_id": self.fornecedor_id(e["doc"], e["razao"])}
                    if e["ano"]:
                        reg["ano"] = e["ano"]
                    if e["nr"] in existentes:
                        self.sb.table("empenhos").update(reg).eq("id", existentes[e["nr"]]).execute()
                    else:
                        reg.update({"item_id": item_id, "nr_empenho": e["nr"]})
                        self.sb.table("empenhos").insert(reg).execute()
                    c["empenhos"] += 1
        return lic_id, c


# ─── Status compartilhado (coleta_status / coleta_execucoes) ─────────────────
class Status:
    def __init__(self, banco, arquivo, origem, anos):
        self.banco, self.arquivo, self.origem = banco, arquivo, origem
        self.anos = anos
        self.stats = {"processados": 0, "itens": 0, "fornecedores": 0, "empenhos": 0,
                      "pulados": 0, "erros": 0, "licitacoes_novas": 0,
                      "licitacoes_atualizadas": 0, "total_portal": 0,
                      "iniciado_em": agora_iso(), "erros_detalhe": []}

    def _janela(self):
        return f"01/01/{min(self.anos)}", f"31/12/{max(self.anos)}"

    def escrever(self, etapa="coletando", status="running", extra=None):
        s = self.stats
        dt_ini, dt_fim = self._janela()
        dados = {
            "status": status, "etapa": etapa,
            "processados": s["processados"], "novos": s["licitacoes_novas"],
            "atualizadas": s["licitacoes_atualizadas"], "pulados": s["pulados"],
            "erros": s["erros"], "itens_coletados": s["itens"],
            "fornecedores": s["fornecedores"], "empenhos": s["empenhos"],
            "total_portal": s["total_portal"],
            "iniciado_em": s["iniciado_em"], "atualizado_em": agora_iso(),
            "pid": os.getpid(), "run_id": os.getenv("GITHUB_RUN_ID"),
            "fonte": "transparencia",
            "consulta_portal": {"url": URL_BUSCA, "orgao": ORGAO_DB,
                                "dt_inicio": dt_ini, "dt_fim": dt_fim, "registros_por_pagina": 15},
        }
        if extra:
            dados.update(extra)
        try:
            with open(self.arquivo, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        if self.banco and not self.banco.dry:
            try:
                self.banco.sb.table("coleta_status").upsert(
                    {"id": 1, "dados": dados, "atualizado_em": dados["atualizado_em"]},
                    on_conflict="id").execute()
            except Exception as e:
                print(f"[!] Falha ao espelhar status (ignorada): {e}")

    def erro(self, processo, msg):
        self.stats["erros"] += 1
        if len(self.stats["erros_detalhe"]) < 50:
            self.stats["erros_detalhe"].append({"processo": processo, "mensagem": str(msg)[:300]})

    def finalizar(self, status, erro_resumo=None):
        self.escrever(etapa="finalizado", status=status, extra={"msg": erro_resumo} if erro_resumo else None)
        if not self.banco or self.banco.dry:
            return
        s = self.stats
        ini = datetime.fromisoformat(s["iniciado_em"])
        dt_ini, dt_fim = self._janela()
        try:
            self.banco.sb.table("coleta_execucoes").insert({
                "iniciado_em": s["iniciado_em"], "finalizado_em": agora_iso(),
                "duracao_seg": int((datetime.now(timezone.utc) - ini).total_seconds()),
                "status": status, "etapa": "finalizado", "origem": self.origem,
                "dt_inicio": dt_ini, "dt_fim": dt_fim,
                "processados": s["processados"], "novos": s["licitacoes_novas"],
                "pulados": s["pulados"], "erros": s["erros"],
                "itens_coletados": s["itens"], "fornecedores": s["fornecedores"],
                "empenhos": s["empenhos"],
                "erro_resumo": (erro_resumo or None) and erro_resumo[:2000],
                "erro_detalhes": s["erros_detalhe"],
            }).execute()
            print(f"[OK] Execução registrada em coleta_execucoes (status={status})")
        except Exception as e:
            print(f"[!] Falha ao registrar execução (ignorada): {e}")


# ─── Orquestração ────────────────────────────────────────────────────────────
def precisa_detalhe(linha, lic, banco):
    """Decide se o processo precisa do detalhe (1 POST + 1 GET)."""
    if lic is None:
        return "nova"
    if not (lic.get("url_detalhe") or "").strip():
        return "enriquecer (1ª vez nesta fonte)"
    if lic["id"] not in banco.com_itens:
        return "sem itens"
    if linha["situacao"] not in SITUACOES_TERMINAIS:
        return f"em andamento ({linha['situacao']})"
    # Registros do portal antigo usam outro vocabulário de situação — não comparar.
    if lic["id"] not in banco.itens_legado and (lic.get("situacao") or "") != linha["situacao"]:
        return f"situação {lic.get('situacao')!r} → {linha['situacao']!r}"
    return None


def coletar(anos, arquivo_status, origem, dry_run=False, limite=None):
    banco = Banco(dry_run=dry_run)
    st = Status(banco, arquivo_status, origem, anos)
    st.escrever(etapa="iniciando")
    print("[0] Carregando índice do banco...")
    banco.carregar_indice()
    portal = PortalTransparencia()
    detalhes_feitos = 0

    for ano in anos:
        if INTERROMPIDO:
            break
        print(f"\n[{ano}] Pesquisando FAAC no Portal da Transparência...")
        grade = portal.pesquisar(ano)
        pagina = 1
        vistos = set()
        while grade is not None and not INTERROMPIDO:
            linhas, soup = portal.linhas_grade(grade)
            chaves = {ln["processo"] for ln in linhas}
            if not chaves or chaves <= vistos:
                break   # página vazia/repetida: fim (proteção contra laço no paginador)
            vistos |= chaves
            st.stats["total_portal"] += len(linhas)
            print(f"  pág. {pagina}: {len(linhas)} processos")
            for ln in linhas:
                if INTERROMPIDO or (limite and detalhes_feitos >= limite):
                    break
                chave = chave_db(ln["processo"])
                lic = banco.lics.get(chave)
                motivo = precisa_detalhe(ln, lic, banco)
                if not motivo:
                    st.stats["pulados"] += 1
                    continue
                try:
                    id_det = portal.id_detalhe(ln["alvo"])
                    if not id_det:
                        raise RuntimeError("postback de detalhe sem redirect")
                    time.sleep(DELAY)
                    det = portal.detalhe(id_det)
                    det["_id"] = id_det
                    if normalizar_processo(det["processo"]) != ln["processo"]:
                        raise RuntimeError(f"detalhe de outro processo ({det['processo']})")
                    print(f"    [{'+' if lic is None else '>'}] {chave} — {motivo}")
                    lic_id, c = banco.gravar(det, ln, lic)
                    detalhes_feitos += 1
                    st.stats["processados"] += 1
                    for k in ("itens", "fornecedores", "empenhos"):
                        st.stats[k] += c[k]
                    if lic is not None:
                        st.stats["licitacoes_atualizadas"] += 1
                except PortalIndisponivel:
                    raise
                except Exception as e:
                    print(f"    [!] {chave}: {e}")
                    st.erro(chave, e)
                st.stats["licitacoes_novas"] = len(banco.novas)
                st.escrever()
                time.sleep(DELAY)
            if limite and detalhes_feitos >= limite:
                break
            st.escrever()
            grade = portal.proxima_pagina(soup, pagina)
            pagina += 1
            time.sleep(DELAY)

    s = st.stats
    print("\n" + "=" * 60)
    for rot, k in [("Processos no portal", "total_portal"), ("Licitações novas", "licitacoes_novas"),
                   ("Atualizadas", "licitacoes_atualizadas"), ("Itens", "itens"),
                   ("Fornecedores", "fornecedores"), ("Empenhos", "empenhos"),
                   ("Pulados (sem mudança)", "pulados"), ("Erros", "erros")]:
        print(f"  {rot + ':':24s}{s[k]}")
    print("=" * 60)

    if INTERROMPIDO:
        final = "cancelled"
    elif s["erros"] and s["erros"] >= max(3, s["processados"] // 2):
        final = "error"   # falha sistemática, não pontual
    else:
        final = "completed"
    st.finalizar(final, erro_resumo=(f"{s['erros']} processos com erro" if final == "error" else None))
    return final, st


def parse_anos(txt):
    if not txt:
        hoje = date.today()
        return [hoje.year - 1, hoje.year]
    anos = set()
    for parte in txt.split(","):
        if "-" in parte:
            a, b = parte.split("-")
            anos.update(range(int(a), int(b) + 1))
        else:
            anos.add(int(parte))
    return sorted(anos)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--anos", help="Ex.: 2026 | 2025,2026 | 2019-2026 (padrão: ano anterior + corrente)")
    ap.add_argument("--progress-file", default="coleta_status.json")
    ap.add_argument("--origem", default=os.getenv("COLETA_ORIGEM") or "manual")
    ap.add_argument("--dry-run", action="store_true", help="Não grava nada no banco")
    ap.add_argument("--limite", type=int, help="Máx. de detalhes consultados (teste)")
    a = ap.parse_args()
    anos = parse_anos(a.anos)
    print(f"[>] Coleta Transparência — anos {anos} — origem {a.origem}{' — DRY-RUN' if a.dry_run else ''}")
    st = None
    try:
        final, st = coletar(anos, a.progress_file, a.origem, dry_run=a.dry_run, limite=a.limite)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[!] Coleta falhou:\n{tb}")
        try:
            st = st or Status(Banco(dry_run=a.dry_run), a.progress_file, a.origem, anos)
            st.finalizar("error", erro_resumo=f"{type(e).__name__}: {e}")
        except Exception:
            pass
        sys.exit(1)
    sys.exit(1 if final == "error" else 0)


if __name__ == "__main__":
    main()
