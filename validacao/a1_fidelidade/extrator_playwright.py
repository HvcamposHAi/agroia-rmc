"""Extrator determinístico do Portal da Transparência de Curitiba (Playwright).

Implementação independente do coletor de produção (regra 0.3.3): lê o DOM
renderizado pelo navegador, sem reutilizar código de `coleta_transparencia.py`.

Fluxo:
  listar_ano(ano)      → linhas da grade de pesquisa (órgão FAAC, ano do processo)
  resolver_urls(ano)   → processo → URL do detalhe (POST do próprio formulário da página
                         com __EVENTTARGET do link "Ver detalhes"; o servidor responde 302)
  detalhe(url)         → campos rotulados + grades (participantes, itens, empenhos, arquivos)

Toda página lida é guardada (HTML + PNG) no cache da execução, com data e hora da captura.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from urllib.parse import urljoin

from validacao.comum import (LimiteTaxa, agora_utc, carimbo, norm_processo, norm_texto,
                             salvar_json, ler_json, sha256_bytes)

SEL_ORGAO = "#cphMasterPrincipal_ddlOrgao"
SEL_ANO = "#cphMasterPrincipal_txtAnoProcesso"
SEL_NUMERO = "#cphMasterPrincipal_txtProcessoCompra"
SEL_PESQUISAR = "#cphMasterPrincipal_lnbPesquisar"
SEL_GRADE = "#cphMasterPrincipal_gdvLicitacao"
SEL_PAGINADOR = "a[href*=ucPaginadorBaixo]"

# Rótulos do quadro "Dados da Licitação/Contratação" → nome do campo
ROTULOS = {
    "licitacao/contratacao": "objeto",
    "empresa": "empresa",
    "setor/orgao": "setor",
    "modalidade da contratacao": "modalidade",
    "prazo contratual": "prazo_contratual",
    "protocolo": "protocolo",
    "situacao do processo": "situacao",
    "no edital": "nr_edital",
    "n edital": "nr_edital",
    "data abertura edital": "dt_abertura",
    "setor edital": "setor_edital",
    "total de forn. que retiraram o edital": "total_forn_retiraram_edital",
    "total de fornecedores participantes": "total_forn_participantes",
}
GRADES = {
    "participantes": "cphMasterPrincipal_gdvFornecedoresParticipantes",
    "arquivos": "cphMasterPrincipal_gdvArquivos",
    "itens": "cphMasterPrincipal_gdvItensProcesso",
    "empenhos": "cphMasterPrincipal_gdvEmpenhoItens",
    "atas": "cphMasterPrincipal_gdvAtasProcesso",
}

_JS_DETALHE = r"""
(grades) => {
  const txt = (el) => (el ? el.innerText : '').replace(/ /g, ' ').trim();
  const out = {titulo: '', pares: [], grades: {}};
  const h = Array.from(document.querySelectorAll('h1,h2,h3,h4,span,div'))
      .find(e => /^Detalhes Licita/.test(txt(e)) && e.children.length === 0);
  out.titulo = h ? txt(h) : '';
  const quadro = Array.from(document.querySelectorAll('fieldset'))
      .find(f => /Dados da Licita/.test(txt(f.querySelector('legend'))));
  if (quadro) {
    for (const tr of quadro.querySelectorAll('tr')) {
      const tds = Array.from(tr.querySelectorAll('td'));
      for (let i = 0; i + 1 < tds.length; i += 2) out.pares.push([txt(tds[i]), txt(tds[i + 1])]);
    }
  }
  for (const [nome, id] of Object.entries(grades)) {
    const t = document.getElementById(id);
    if (!t) { out.grades[nome] = null; continue; }
    const cab = Array.from(t.querySelectorAll('tr th')).map(txt);
    const linhas = [];
    for (const tr of t.querySelectorAll('tr')) {
      const tds = Array.from(tr.querySelectorAll('td'));
      if (tds.length <= 1) continue;
      linhas.push(tds.map(td => {
        const a = td.querySelector('a[href]');
        return {texto: txt(td), href: a ? a.href : null};
      }));
    }
    out.grades[nome] = {cabecalho: cab, linhas: linhas};
  }
  return out;
}
"""


def _rotulo(s: str) -> str:
    return norm_texto(s).rstrip(":").replace("º", "o").replace("°", "o").strip()


class ExtratorPortal:
    def __init__(self, cfg: dict, dir_cache: Path, headless: bool | None = None):
        self.cfg = cfg
        self.url_busca = cfg["fontes"]["portal_url"]
        self.orgao = cfg["fontes"]["portal_orgao"]
        self.cache = Path(dir_cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.limite = LimiteTaxa(cfg["acesso"]["intervalo_min_s"])
        self.headless = cfg["acesso"].get("playwright_headless", True) if headless is None else headless
        self._pw = self._browser = self._ctx = self.page = None
        self.requisicoes = 0

    # ─── ciclo de vida ───────────────────────────────────────────────────────
    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self.headless)
        # O portal não entrega os scripts do ASP.NET a UAs que não parecem navegador:
        # mantém o UA do Chromium e acrescenta a identificação acadêmica ao final.
        tmp = self._browser.new_page()
        ua_base = tmp.evaluate("navigator.userAgent")
        tmp.close()
        self.user_agent = f"{ua_base} {self.cfg['acesso']['user_agent']}"
        self._ctx = self._browser.new_context(user_agent=self.user_agent,
                                              locale="pt-BR", viewport={"width": 1366, "height": 900})
        self._ctx.set_default_timeout(self.cfg["acesso"]["timeout_http_s"] * 1000)
        self.page = self._ctx.new_page()
        return self

    def __exit__(self, *exc):
        for obj in (self._ctx, self._browser):
            try:
                obj and obj.close()
            except Exception:
                pass
        try:
            self._pw and self._pw.stop()
        except Exception:
            pass

    # ─── pesquisa e listagem ─────────────────────────────────────────────────
    def _pesquisar(self, ano: int, numero: str | None = None):
        pg = self.page
        self.limite.esperar()
        pg.goto(self.url_busca, wait_until="load")
        try:
            pg.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass
        self.requisicoes += 1
        if not pg.locator(f"{SEL_ORGAO} option[value='{self.orgao}']").count():
            raise RuntimeError("Formulário do portal mudou: órgão não encontrado no filtro")
        pg.wait_for_function("() => typeof window.__doPostBack === 'function'")
        pg.select_option(SEL_ORGAO, self.orgao)
        pg.fill(SEL_ANO, str(ano))
        if numero:
            pg.fill(SEL_NUMERO, str(numero))
        self._postback_grade(lambda: pg.click(SEL_PESQUISAR))
        # Confirma que o filtro foi aplicado (a grade padrão lista todos os órgãos).
        linhas = self._linhas_pagina()
        orgaos = {norm_texto(l["orgao"]) for l in linhas}
        if linhas and (len(orgaos) > 1 or not all(l["processo"].endswith(f"/{ano}") for l in linhas)):
            raise RuntimeError(f"Pesquisa não aplicou o filtro (órgãos={sorted(orgaos)[:3]})")

    def _postback_grade(self, acao):
        """Executa uma ação que dispara o postback assíncrono e espera a grade atualizar."""
        pg = self.page
        self.limite.esperar()
        with pg.expect_response(lambda r: "licitacoes.aspx" in r.url.lower()
                                and r.request.method == "POST"):
            acao()
        self.requisicoes += 1
        pg.wait_for_function(
            "() => !(window.Sys && Sys.WebForms && Sys.WebForms.PageRequestManager"
            " && Sys.WebForms.PageRequestManager.getInstance().get_isInAsyncPostBack())")
        pg.wait_for_timeout(300)

    def _linhas_pagina(self) -> list[dict]:
        dados = self.page.eval_on_selector_all(
            f"{SEL_GRADE} tr",
            """trs => trs.map(tr => {
                 const c = Array.from(tr.cells);
                 const a = c.length ? c[0].querySelector('a[href]') : null;
                 return {celulas: c.map(x => x.innerText.replace(/\\u00a0/g,' ').trim()),
                         th: tr.querySelectorAll('th').length, href: a ? a.getAttribute('href') : null};
               })""")
        cab = next((d["celulas"] for d in dados if d["th"]), [])
        out = []
        for d in dados:
            if d["th"] or len(d["celulas"]) < len(cab) or len(cab) == 0:
                continue
            reg = {norm_texto(h): v for h, v in zip(cab, d["celulas"])}
            m = re.search(r"__doPostBack\('([^']+)'", d["href"] or "")
            out.append({"processo": norm_processo(reg.get("num processo", "")),
                        "processo_bruto": reg.get("num processo", ""),
                        "modalidade": reg.get("modalidade", ""),
                        "orgao": reg.get("orgao", ""),
                        "objeto": reg.get("objeto", ""),
                        "valor_global": reg.get("valor global", ""),
                        "local": reg.get("local execucao/entrega", ""),
                        "celebracao": reg.get("celebracao", ""),
                        "protocolo": reg.get("protocolo", ""),
                        "situacao": reg.get("situacao", ""),
                        "_alvo": m.group(1) if m else None,
                        "_cabecalho": cab})
        return out

    def _proxima(self, pagina_atual: int) -> bool:
        links = self.page.eval_on_selector_all(
            SEL_PAGINADOR, "as => as.map(a => [a.innerText.trim(), a.getAttribute('href')])")
        alvo = next((h for t, h in links if t == str(pagina_atual + 1)), None)
        if alvo is None and len(links) > 1 and links[-1][0] == "...":
            alvo = links[-1][1]
        if alvo is None:
            return False
        m = re.search(r"__doPostBack\('([^']+)'", alvo)
        if not m:
            return False
        link = self.page.locator(f"{SEL_PAGINADOR}[href*=\"'{m.group(1)}'\"]").first
        self._postback_grade(lambda: link.click())
        return True

    def listar_ano(self, ano: int, max_paginas: int = 500) -> list[dict]:
        """Todas as linhas da pesquisa (órgão, ano). Cache em disco por execução."""
        arq = self.cache / f"listagem_{ano}.json"
        em_cache = ler_json(arq)
        if em_cache is not None:
            return em_cache["linhas"]
        self._pesquisar(ano)
        linhas, pagina, vistos = [], 1, set()
        while pagina <= max_paginas:
            atuais = self._linhas_pagina()
            assinatura = tuple(l["processo"] for l in atuais)
            if assinatura in vistos:
                break
            vistos.add(assinatura)
            for l in atuais:
                l["pagina"] = pagina
            linhas += atuais
            if not self._proxima(pagina):
                break
            pagina += 1
        salvar_json(arq, {"ano": ano, "capturado_em": carimbo(), "paginas": pagina,
                          "requisicoes": self.requisicoes, "linhas": linhas})
        return linhas

    # ─── resolução da URL do detalhe ─────────────────────────────────────────
    def resolver_urls(self, ano: int, processos: set[str]) -> dict[str, str]:
        """Resolve a URL de detalhe de cada processo pelo clique em 'Ver detalhes'.

        A pesquisa usa o campo "Processo de compra" (número) do formulário, o que põe o
        processo na 1ª página da grade: 2 requisições por processo, sem percorrer a paginação.
        (Um postback completo sempre reassocia a linha clicada à 1ª página de resultados, e o
        botão voltar não restaura a grade; por isso não se reaproveita a pesquisa do censo.)
        A URL só é aceita se o cabeçalho do detalhe for o processo procurado."""
        arq = self.cache / f"urls_{ano}.json"
        mapa = ler_json(arq, {}) or {}
        for proc in sorted(p for p in processos if p not in mapa):
            m = re.match(r"^[A-Z]+ (\d+)/\d{4}$", proc)
            if not m:
                continue
            try:
                self._pesquisar(ano, m.group(1))
                linha = next((l for l in self._linhas_pagina() if l["processo"] == proc), None)
                if not linha or not linha["_alvo"]:
                    mapa.setdefault("_erros", {})[proc] = "processo não listado na pesquisa por número"
                    continue
                link = self.page.locator(f"{SEL_GRADE} a[href*=\"'{linha['_alvo']}'\"]").first
                self.limite.esperar()
                with self.page.expect_navigation(url=re.compile(r"LicitacoesDetalhes", re.I)):
                    link.click()
                self.requisicoes += 1
                url = self.page.url
                self.page.wait_for_selector("#cphMasterPrincipal_uppDetalhes")
                bruto = self.page.evaluate(_JS_DETALHE, GRADES)
                lido = norm_processo(re.sub(r"^Detalhes Licita\w*\s*-\s*", "", bruto.get("titulo") or ""))
                if lido == proc:
                    mapa[proc] = url
                    salvar_json(arq, mapa)
                else:
                    mapa.setdefault("_erros", {})[proc] = f"cabeçalho divergente: {lido}"
            except Exception as e:  # noqa: BLE001 — um processo não derruba o lote
                mapa.setdefault("_erros", {})[proc] = str(e)[:300]
        salvar_json(arq, mapa)
        return {p: mapa[p] for p in processos if p in mapa}

    # ─── detalhe ─────────────────────────────────────────────────────────────
    def detalhe(self, url: str, evidencia_dir: Path | None = None) -> dict:
        m = re.search(r"id=(\d+)", url)
        ident = m.group(1) if m else sha256_bytes(url.encode())[:12]
        arq = self.cache / f"detalhe_{ident}.json"
        em_cache = ler_json(arq)
        if em_cache is not None:
            return em_cache
        self.limite.esperar()
        inicio = agora_utc()
        self.page.goto(url, wait_until="domcontentloaded")
        self.requisicoes += 1
        self.page.wait_for_selector("#cphMasterPrincipal_uppDetalhes")
        bruto = self.page.evaluate(_JS_DETALHE, GRADES)
        html = self.page.content()
        (self.cache / f"detalhe_{ident}.html").write_text(html, encoding="utf-8")
        if evidencia_dir:
            evidencia_dir.mkdir(parents=True, exist_ok=True)
            try:
                self.page.screenshot(path=str(evidencia_dir / f"detalhe_{ident}.png"), full_page=True)
            except Exception:
                pass
        det = interpretar_detalhe(bruto)
        det.update({"url": url, "id_portal": ident, "capturado_em": carimbo(inicio),
                    "sha256_html": sha256_bytes(html.encode("utf-8"))})
        salvar_json(arq, det)
        return det


def _grade_dicts(grade: dict | None) -> list[dict]:
    if not grade:
        return []
    cab = [norm_texto(c) for c in grade["cabecalho"]]
    out = []
    for linha in grade["linhas"]:
        if len(linha) < len(cab):
            continue
        d = {}
        for h, cel in zip(cab, linha):
            d[h] = cel["texto"]
            if cel.get("href"):
                d[h + "__href"] = cel["href"]
        out.append(d)
    return out


def _pega(d: dict, *chaves):
    for k in chaves:
        for dk, v in d.items():
            if dk.startswith(k):
                return v
    return None


def _vazio(v):
    v = (v or "").strip()
    return None if v in ("", "-", "—") else v


def interpretar_detalhe(bruto: dict) -> dict:
    """Converte a leitura crua do DOM em campos nomeados (valores como aparecem na tela)."""
    campos = {}
    for rot, val in bruto.get("pares", []):
        nome = ROTULOS.get(_rotulo(rot))
        if nome and nome not in campos:
            campos[nome] = _vazio(val)
    titulo = bruto.get("titulo") or ""
    proc = re.sub(r"^Detalhes Licita\w*\s*-\s*", "", titulo).strip()
    g = bruto.get("grades", {})
    participantes = [{"doc": _pega(d, "cpf", "cnpj", "documento"), "razao": _pega(d, "razao", "fornecedor", "nome")}
                     for d in _grade_dicts(g.get("participantes"))]
    itens = [{"descricao": _pega(d, "item", "descricao"), "quantidade": _pega(d, "quantidade"),
              "unidade": _pega(d, "unidade"), "fornecedor": _vazio(_pega(d, "fornecedor")),
              "cnpj": _vazio(_pega(d, "cnpj", "cpf")), "valor_unitario": _pega(d, "valor unitario"),
              "valor_total": _pega(d, "valor total")}
             for d in _grade_dicts(g.get("itens"))]
    empenhos = []
    for d in _grade_dicts(g.get("empenhos")):
        href = next((v for k, v in d.items() if k.endswith("__href")), None)
        m = re.search(r"exercicio=(\d{4})", href or "")
        empenhos.append({"numero": d.get("num empenho"), "credor": d.get("nome contratado"),
                         "doc": d.get("cnpj"), "valor": d.get("empenhado"),
                         "liquidado": d.get("liquidado"), "pago": d.get("pago"),
                         "exercicio": m.group(1) if m else None, "href": href})
    arquivos = [{"nome": _pega(d, "documento"), "url": _pega(d, "arquivo__href")}
                for d in _grade_dicts(g.get("arquivos"))]
    return {"processo": norm_processo(proc), "processo_bruto": proc, **campos,
            "participantes": participantes, "itens": itens, "empenhos": empenhos,
            "arquivos": [a for a in arquivos if a["url"]],
            "cabecalhos": {k: (v or {}).get("cabecalho") for k, v in g.items()}}
