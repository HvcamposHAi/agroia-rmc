"""Sorteio de parâmetros e cálculo do gabarito das tarefas da A2 (seção 4.2.2).

Parâmetros são sorteados SOMENTE entre registros verificados na A1 (a1/verificados.json):
processos cujos campos de que a tarefa depende foram confirmados na fonte, e anos cujo
censo atingiu a completude mínima. Instâncias sem gabarito válido são descartadas e
sorteadas de novo; cada descarte é registrado com o motivo.
"""

from __future__ import annotations

import random
import re
from pathlib import Path

import pandas as pd
import yaml

from validacao.comum import dir_execucao, ler_json, norm_texto, salvar_json, sha256_arquivo

MODELOS = Path(__file__).with_name("modelos.yaml")
TENTATIVAS_POR_INSTANCIA = 40


def carregar_modelos() -> dict:
    return yaml.safe_load(MODELOS.read_text(encoding="utf-8"))


class Contexto:
    def __init__(self, run_id: str, snap, cfg: dict):
        self.run_id, self.snap, self.cfg = run_id, snap, cfg
        d = dir_execucao(run_id)
        v = ler_json(d / "a1" / "verificados.json", {}) or {}
        self.verificados: dict = v.get("processos", {})
        self.anos_aptos: list[int] = v.get("anos_aptos", [])
        self.censo = ler_json(d / "a1" / "censo.json", {}) or {}
        self.docs = pd.read_csv(d / "a1" / "documentos.csv") if (d / "a1" / "documentos.csv").exists() else pd.DataFrame()
        self.dir_docs = d / "a1" / "cache" / "docs"
        lic = snap.licitacoes.copy()
        lic["dt_abertura"] = pd.to_datetime(lic["dt_abertura"], errors="coerce").dt.date
        lic["ano"] = lic["ano"].astype("float").astype("Int64")
        snap.sql("SELECT 1")                       # inicializa DuckDB
        snap._duck.register("lic", lic)

    def q(self, consulta: str, params: dict) -> pd.DataFrame:
        usados = {k: v for k, v in params.items() if f"${k}" in consulta}
        return self.snap._duck.execute(consulta, usados).df()

    # ─── conjuntos de parâmetros ─────────────────────────────────────────────
    def processos_ok(self, campos: list[str]) -> list[str]:
        return sorted(c for c, v in self.verificados.items() if all(x in v["campos_ok"] for x in campos
                                                                   if x not in ("censo", "arquivos")))

    def anos_exatos(self) -> list[int]:
        """Anos cujo censo casou 1:1 (completude e precisão iguais a 1)."""
        out = []
        for a, m in (self.censo.get("por_ano") or {}).items():
            if m.get("completude") == 1 and m.get("precisao_existencia") == 1 and m.get("nao_verificaveis_fonte_desativada", 0) == 0:
                out.append(int(a))
        return sorted(out)

    def produtos_do_processo(self, chave: str) -> list[str]:
        df = self.q("SELECT DISTINCT upper(i.cultura) AS c FROM itens_licitacao i JOIN lic ON lic.id = i.licitacao_id "
                    "WHERE lic.chave = $processo AND i.relevante_agro AND i.cultura IS NOT NULL", {"processo": chave})
        return sorted(df["c"].dropna())

    def urls_documentos(self, chave: str) -> list[str]:
        if self.docs.empty:
            return []
        d = self.docs[(self.docs["chave"] == chave) & (self.docs["disponivel"] == True)]  # noqa: E712
        return sorted(set(d["url"].dropna()) | set(d["par_portal"].dropna()))


# ─── sorteio por tipo de parâmetro ───────────────────────────────────────────
def sortear_parametros(tipo_lista: list[str], ctx: Contexto, rng: random.Random, depende: list[str]) -> dict | None:
    p: dict = {}
    for t in tipo_lista:
        if t == "processo":
            cands = ctx.processos_ok(depende)
            if "arquivos" in depende:
                cands = [c for c in cands if ctx.urls_documentos(c)]
            if not cands:
                return None
            p["processo"] = rng.choice(cands)
        elif t == "produto":
            prods = ctx.produtos_do_processo(p["processo"])
            if not prods:
                return None
            p["produto"] = rng.choice(prods)
        elif t in ("ano", "ano_exato"):
            anos = ctx.anos_exatos() if t == "ano_exato" else ctx.anos_aptos
            if not anos:
                return None
            p["ano"] = rng.choice(anos)
        elif t == "ano_produto":
            cands = [(c, v["ano"]) for c, v in ctx.verificados.items() if "itens" in v["campos_ok"]
                     and v["ano"] in ctx.anos_aptos]
            if not cands:
                return None
            chave, ano = rng.choice(sorted(cands))
            prods = ctx.produtos_do_processo(chave)
            if not prods:
                return None
            p.update({"ano": int(ano), "produto": rng.choice(prods)})
        elif t in ("fornecedor_empenho", "fornecedor_participacao"):
            campo = "empenhos" if t == "fornecedor_empenho" else "participantes"
            cands = [(c, v) for c, v in ctx.verificados.items() if campo in v["campos_ok"] and v["ano"] in ctx.anos_aptos]
            if not cands:
                return None
            chave, v = rng.choice(sorted(cands, key=lambda x: x[0]))
            if campo == "empenhos":
                df = ctx.q("SELECT DISTINCT regexp_replace(f.cpf_cnpj, '[^0-9]', '', 'g') AS doc, f.razao_social AS nome "
                           "FROM empenhos e JOIN itens_licitacao i ON i.id = e.item_id JOIN lic ON lic.id = i.licitacao_id "
                           "JOIN fornecedores f ON f.id = e.fornecedor_id WHERE lic.chave = $processo ORDER BY doc, nome",
                           {"processo": chave})
            else:
                df = ctx.q("SELECT DISTINCT regexp_replace(f.cpf_cnpj, '[^0-9]', '', 'g') AS doc, f.razao_social AS nome "
                           "FROM participacoes pa JOIN lic ON lic.id = pa.licitacao_id JOIN fornecedores f "
                           "ON f.id = pa.fornecedor_id WHERE lic.chave = $processo ORDER BY doc, nome", {"processo": chave})
            # ORDER BY + reset_index: sem ordem fixa o DuckDB pode devolver as linhas em outra
            # sequência e o sorteio (mesma semente) escolheria outro fornecedor.
            df = df[df["doc"].str.len() >= 11].reset_index(drop=True)
            if df.empty:
                return None
            r = df.sample(1, random_state=rng.randrange(2 ** 31)).iloc[0]
            p.update({"ano": int(v["ano"]), "doc": r["doc"], "fornecedor": f"{r['nome']} (CNPJ {r['doc']})"})
        elif t == "processo_edital":
            cands = [c for c in ctx.processos_ok([]) if ctx.urls_documentos(c)]
            if not cands:
                return None
            p["processo"] = rng.choice(cands)
    return p


# ─── gabarito ────────────────────────────────────────────────────────────────
PADRAO_PRAZO = re.compile(
    r"prazo\s+(?:m[aá]ximo\s+)?(?:de|para)\s+(?:a\s+)?entrega[^.;]{0,120}?(\d{1,3})\s*(?:\([^)]{0,30}\)\s*)?(?:dias|horas)",
    re.I | re.S)


def prazos_texto(texto: str) -> set:
    return {int(m.group(1)) for m in PADRAO_PRAZO.finditer(texto or "")}


def gabarito_t11(ctx: Contexto, chave: str) -> tuple[dict | None, str]:
    """Prazo de entrega extraído do PDF por duas bibliotecas (PyMuPDF e pypdf); só vale se
    ambas encontrarem exatamente o mesmo valor único."""
    if ctx.docs.empty:
        return None, "sem documentos na A1"
    d = ctx.docs[(ctx.docs["chave"] == chave) & (ctx.docs["disponivel"] == True)]  # noqa: E712
    from validacao.comum import sha256_bytes
    for url in d["url"].dropna():
        pdf = ctx.dir_docs / f"{sha256_bytes(url.encode())[:20]}.pdf"
        if not pdf.exists():
            continue
        try:
            # 1ª leitura (PyMuPDF): reaproveita o texto que a A1 extraiu com a mesma biblioteca.
            txt_cache = pdf.with_suffix(".txt")
            if txt_cache.exists():
                t1 = txt_cache.read_text(encoding="utf-8")
            else:
                import fitz
                with fitz.open(pdf) as doc:
                    t1 = "\n".join(p.get_text() for p in doc)
            a = prazos_texto(t1)
            # A regra só aceita prazo único nas duas leituras: sem prazo único na 1ª, a 2ª
            # (pypdf, lenta em PDFs digitalizados grandes) não muda o resultado.
            if len(a) != 1:
                continue
            from pypdf import PdfReader
            t2 = "\n".join((pg.extract_text() or "") for pg in PdfReader(str(pdf)).pages)
        except Exception:
            continue
        b = prazos_texto(t2)
        if len(a) == 1 and a == b:
            return {"valor": next(iter(a)), "documento": url, "sha256_pdf": sha256_arquivo(pdf)}, ""
    return None, "prazo não encontrado de forma única e concordante nas duas leituras"


def calcular_gabarito(mid: str, modelo: dict, params: dict, ctx: Contexto) -> tuple[dict | None, str]:
    pont = modelo["pontuacao"]
    if mid == "T11":
        return gabarito_t11(ctx, params["processo"])
    if mid == "T12":
        return {"abstencao": True}, ""
    df = ctx.q(modelo["consulta"], params)
    if df.empty:
        return None, "consulta vazia"
    t = pont["tipo"]
    if t == "objeto_data":
        r = df.iloc[0]
        if not r["objeto"] or not r["data"]:
            return None, "objeto ou data ausente"
        return {"objeto": r["objeto"], "data": str(r["data"])[:10]}, ""
    if t == "documento_data":
        urls = ctx.urls_documentos(params["processo"])
        if not urls or not df.iloc[0]["data"]:
            return None, "sem documento disponível ou sem data"
        return {"documentos": urls, "data": str(df.iloc[0]["data"])[:10]}, ""
    if t == "numero":
        vals = sorted(set(float(x) for x in df["valor"].dropna()))
        if not vals:
            return None, "valor nulo"
        if pont.get("exige_unico") and len(vals) != 1:
            return None, f"{len(vals)} valores distintos (ambíguo)"
        if vals[0] == 0 and "tolerancia_rel" in pont:
            return None, "valor zero"
        return {"valor": vals[0]}, ""
    if t == "conjunto_fornecedores":
        return {"fornecedores": df.to_dict("records")}, ""
    if t == "topk":
        if len(df) < pont.get("k", 5):
            return None, "menos de k itens"
        return {"itens": list(df["nome"]), "valores": [round(float(v), 2) for v in df["valor"]]}, ""
    if t == "conjunto_meses":
        return {"meses": sorted(int(m) for m in df["mes"].dropna())}, ""
    if t == "categorica":
        if len(df) != 1 or not df.iloc[0]["n_cotacoes"]:
            return None, "sem cotação CEASA-PR compatível (unidade kg) no mês"
        r = df.iloc[0]
        preco, ceasa = float(r["preco"]), float(r["ceasa"])
        tol = pont.get("tolerancia_igual_rel", 0.01)
        cat = "igual" if abs(preco - ceasa) <= tol * ceasa else ("acima" if preco > ceasa else "abaixo")
        return {"categoria": cat, "preco": preco, "ceasa": round(ceasa, 4), "n_cotacoes": int(r["n_cotacoes"])}, ""
    return None, f"tipo de pontuação desconhecido: {t}"


def instanciar(run_id: str, snap, cfg: dict) -> dict:
    arq = dir_execucao(run_id) / "a2" / "instancias.json"
    existente = ler_json(arq)
    if existente:
        return existente
    modelos = carregar_modelos()
    ctx = Contexto(run_id, snap, cfg)
    rng = random.Random(int(cfg["execucao"]["seed"]))
    n_inst = int(cfg["a2"]["instancias_por_modelo"])
    instancias, descartes, sem_instancia = [], [], []
    for mid in cfg["a2"]["modelos_ativos"]:
        m = modelos[mid]
        vistos = set()
        for i in range(1, n_inst + 1):
            ok = False
            for _ in range(TENTATIVAS_POR_INSTANCIA):
                params = sortear_parametros(m["parametros"], ctx, rng, m.get("depende", []))
                if params is None:
                    descartes.append({"modelo": mid, "motivo": "sorteio sem registro verificado compatível"})
                    continue
                assinatura = tuple(sorted((k, str(v)) for k, v in params.items()))
                if assinatura in vistos:
                    continue
                vistos.add(assinatura)
                gab, motivo = calcular_gabarito(mid, m, params, ctx)
                if gab is None:
                    descartes.append({"modelo": mid, "parametros": params, "motivo": motivo})
                    continue
                enun = m["enunciado"].format(**{k: v for k, v in params.items()})
                instancias.append({"id": f"{mid}-{i}", "modelo": mid, "tipo": m["tipo"], "enunciado": enun,
                                   "parametros": params, "gabarito": gab, "pontuacao": m["pontuacao"]})
                ok = True
                break
            if not ok:
                sem_instancia.append(f"{mid}-{i}")
    res = {"instancias": instancias, "descartes": descartes, "sem_instancia": sem_instancia,
           "sha256_modelos": sha256_arquivo(MODELOS), "seed": cfg["execucao"]["seed"]}
    salvar_json(arq, res)
    return res
