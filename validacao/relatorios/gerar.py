"""Geração automática dos relatórios (metodologia e resultados, Partes A e B) em MD e HTML.

Nenhum número é escrito nos templates: todo número vem do manifesto, do pré-registro e dos
arquivos de resultado da execução. Tabelas e figuras são numeradas na ordem de chamada.

Uso: python -m validacao.relatorios.gerar --run-id RUN [--partes A,B]
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import re
from pathlib import Path

import pandas as pd
import yaml
from jinja2 import ChainableUndefined, Environment, FileSystemLoader

from validacao.comum import RAIZ_VALIDACAO, carimbo, carregar_config, dir_execucao, ler_json, sha256_arquivo

TEMPLATES = RAIZ_VALIDACAO / "relatorios" / "templates"
PREREG = RAIZ_VALIDACAO / "preregistro"
CORES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]   # ordem categórica fixa
TINTA, TINTA2, GRADE = "#1f1f1e", "#5f5e5a", "#e4e3dd"
FONTE = "Fonte: elaborado pelo autor (2026)."


# ─── formatação pt-BR ────────────────────────────────────────────────────────
def _vazio(v) -> bool:
    return v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))


def n(v, casas: int = 0) -> str:
    if _vazio(v):
        return "n/d"
    s = f"{float(v):,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(v, casas: int = 1) -> str:
    return "n/d" if _vazio(v) else f"{n(100 * float(v), casas)}%"


def pv(p) -> str:
    if _vazio(p):
        return "n/d"
    return "p < 0,001" if p < 0.001 else f"p = {n(p, 3)}"


def ic(d: dict | None, casas: int = 1) -> str:
    if not d or _vazio(d.get("p")):
        return "n/d"
    return f"{pct(d['p'], casas)} (IC 95%: {pct(d['li'], casas)} a {pct(d['ls'], casas)}; {d['k']}/{d['n']})"


def rot(v) -> str:
    return str(v).replace("_", " ").lower() if v is not None else "n/d"


class Numeracao:
    def __init__(self):
        self.tab, self.fig = {}, {}

    def t(self, chave: str) -> int:
        return self.tab.setdefault(chave, len(self.tab) + 1)

    def f(self, chave: str) -> int:
        return self.fig.setdefault(chave, len(self.fig) + 1)


def tabela_md(linhas: list[list], cab: list[str]) -> str:
    if not linhas:
        return "_Sem dados nesta execução._"
    fmt = lambda x: str(x).replace("|", "/").replace("\n", " ")  # noqa: E731
    out = ["| " + " | ".join(cab) + " |", "|" + "|".join("---" for _ in cab) + "|"]
    out += ["| " + " | ".join(fmt(c) for c in l) + " |" for l in linhas]
    return "\n".join(out)


def linhas_snapshot(snap: dict) -> list[list]:
    return [[t, n(v.get("linhas")), (v.get("sha256_conteudo") or "")[:16]] for t, v in sorted((snap.get("tabelas") or {}).items())]


def linhas_modelos(modelos: dict) -> list[list]:
    return [[k, rot(m["tipo"]), m["enunciado"], rot(m["pontuacao"]["tipo"])] for k, m in sorted(modelos.items())]


def linhas_censo(c: dict) -> list[list]:
    out = []
    for a in sorted(c.get("por_ano", {}), key=int):
        m = c["por_ano"][a]
        out.append([a, n(m["P"]), n(m["P_inter_B"]), n(m["faltantes_na_base"]), n(m["ausentes_no_portal"]),
                    n(m["nao_verificaveis_fonte_desativada"]), pct(m["completude"]), pct(m["precisao_existencia"])])
    g = c["global"]
    out.append(["Total", n(g["P"]), n(g["P_inter_B"]), n(g["faltantes_na_base"]), n(g["ausentes_no_portal"]),
                n(g["nao_verificaveis_fonte_desativada"]), pct(g["completude"]), pct(g["precisao_existencia"])])
    return out


def linhas_campos(pc: dict) -> list[list]:
    out = []
    for campo, v in pc.items():
        po = v.get("por_origem", {})
        out.append([campo, ic(v), ic(po.get("TRANSPARENCIA")), ic(po.get("JSF_ENRIQUECIDO")), ic(po.get("JSF_LEGADO")),
                    n(v.get("divergencia_extracao")),
                    n(v.get("f1_medio"), 3), n(v.get("lev_medio"), 3)])
    return out


def linhas_agregados(a: dict) -> list[list]:
    return [[l["ano"], n(l["processos_base"]), n(l["processos_portal"]), pct(l["dif_processos_rel"]),
             n(l["itens_base"]), n(l["empenhado_base"], 2), n(l["valor_global_listagem_portal"], 2)]
            for l in a.get("por_ano", [])]


def linhas_tarefas(run_id: str, piloto: bool) -> list[list]:
    p = dir_execucao(run_id) / "a2" / ("tarefas_piloto.csv" if piloto else "tarefas.csv")
    if not p.exists():
        return []
    df = pd.read_csv(p)
    return [[r.instancia, rot(r.tipo), r.condicao, f"{r.sucessos}/{r.n}", n(r.n_acoes_med, 1), n(r.klm_med, 1),
             n(r.tempo_med, 1), n(r.paginas_med, 1), str(r.desfechos).strip("[]").replace("'", "")]
            for r in df.sort_values(["instancia", "condicao"]).itertuples()]


def linhas_h4(h4: dict) -> list[list]:
    return [[rot(t), "sim" if v.get("AGROIA") else "não", "sim" if v.get("PORTAL") else "não"]
            for t, v in sorted((h4 or {}).get("por_tipo", {}).items())]


def linhas_desfechos(d: dict) -> list[list]:
    return [[c, k, n(v)] for c, dd in sorted((d or {}).items()) for k, v in sorted(dd.items())]


def linhas_divergencias(campos: pd.DataFrame, limite: int = 300) -> list[list]:
    div = campos[campos["status"].isin(["DIVERGE", "DIVERGENCIA_EXTRACAO"])]
    return [[r.chave, rot(r.origem), r.campo, r.status, str(r.valor_fonte)[:80], str(r.valor_base)[:80]]
            for r in div.head(limite).itertuples()]


def linhas_falhas(ex: pd.DataFrame) -> list[list]:
    f = ex[ex["desfecho"].isin(["ERRO_INFRA", "ERRO_INFRA_CHROME", "BLOQUEADO", "TIMEOUT"])]
    return [[r.chave, r.desfecho, n(r.tentativas), str(r.motivo)[:120]] for r in f.itertuples()]


def linhas_instancias(inst: dict) -> list[list]:
    return [[i["id"], i["enunciado"], json.dumps(i["gabarito"], ensure_ascii=False, default=str)[:200]]
            for i in (inst or {}).get("instancias", [])]


def linhas_precos(cfg: dict, precos: dict) -> list[list]:
    return [[m, cfg["b"].get("rotulos", {}).get(m, m), n(precos.get(m, {}).get("entrada_por_1m"), 2),
             n(precos.get(m, {}).get("saida_por_1m"), 2), precos.get(m, {}).get("moeda", "n/d"),
             precos.get(m, {}).get("fonte", "n/d")] for m in cfg["b"]["motores"]]


def linhas_perguntas(perguntas: list[dict], gab: dict) -> list[list]:
    out = []
    for q in perguntas:
        g = gab.get(q["id"], {})
        desc = {"numero": "valores: " + ", ".join(n(v, 2) for v in g.get("valores", [])[:4]),
                "entidades": "entidades: " + ", ".join(g.get("nomes", [])[:5]),
                "abstencao": "abstenção", "sem_gabarito": "sem gabarito factual (AF@3)"}.get(g.get("tipo"), "n/d")
        out.append([q["id"], q["categoria"], q["conjunto"], q["pergunta"], desc])
    return out


def _r(b: dict, m: str) -> str:
    return b.get("rotulos", {}).get(m, m)


def linhas_acuracia(b: dict) -> list[list]:
    ap, asens = b["acuracia_principal"]["por_motor"], b["acuracia_sensibilidade"]["por_motor"]
    return [[_r(b, m), ic(ap.get(m)), ic(asens.get(m)), pct(b.get("af", {}).get(m, {}).get("af@1")),
             pct(b.get("af", {}).get(m, {}).get("af@3")), ic(b.get("uso_correto_ferramenta", {}).get(m))]
            for m in b["motores"]]


def linhas_fidelidade(b: dict) -> list[list]:
    return [[_r(b, m), pct(b["fidelidade_ferramentas"].get(m)), ic(b["abstencao"].get(m)),
             ic(b["falsa_abstencao"].get(m)), pct(b["consistencia"].get(m, {}).get("prop_mesmo_desfecho")),
             n(b["consistencia"].get(m, {}).get("fleiss_kappa"), 3)] for m in b["motores"]]


def linhas_latencia(b: dict) -> list[list]:
    lat, tt, cu = b["latencia"]["por_motor"], b["ttft"]["por_motor"], b["custo"]["por_motor"]
    return [[_r(b, m), n(lat[m]["p50"], 2), n(lat[m]["p90"], 2), n(lat[m]["p95"], 2), n(tt[m]["p50"], 2),
             n(cu[m]["media"], 6), n(b["custo_total_usd"].get(m), 4)] for m in b["motores"]]


def linhas_erros(b: dict) -> list[list]:
    return [[_r(b, m), rot(c), n(v)] for m in b["motores"] for c, v in sorted(b["erros"].get(m, {}).items())]


# ─── figuras ─────────────────────────────────────────────────────────────────
def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": GRADE,
                         "axes.labelcolor": TINTA2, "xtick.color": TINTA2, "ytick.color": TINTA2,
                         "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                         "grid.color": GRADE, "grid.linewidth": 0.6, "axes.axisbelow": True,
                         "figure.facecolor": "white", "axes.facecolor": "white", "savefig.dpi": 160})
    return plt


def fig_barras(caminho: Path, categorias: list[str], series: dict[str, list[float]], rotulo_y: str,
               erros: dict[str, list[tuple]] | None = None, percentual: bool = True) -> str | None:
    if not categorias or not series:
        return None
    plt = _plt()
    import numpy as np
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    k = len(series)
    larg = 0.8 / k
    x = np.arange(len(categorias))
    for i, (nome, vals) in enumerate(series.items()):
        pos = x - 0.4 + larg * (i + 0.5)
        vals = [0 if _vazio(v) else v for v in vals]
        ax.bar(pos, vals, width=larg * 0.92, color=CORES[i % len(CORES)], label=nome, edgecolor="white", linewidth=1)
        if erros and nome in erros:
            lo = [max(0, v - e[0]) if e[0] is not None else 0 for v, e in zip(vals, erros[nome])]
            hi = [max(0, e[1] - v) if e[1] is not None else 0 for v, e in zip(vals, erros[nome])]
            ax.errorbar(pos, vals, yerr=[lo, hi], fmt="none", ecolor=TINTA2, elinewidth=1, capsize=2)
    ax.set_xticks(x, categorias, rotation=30 if max(len(c) for c in categorias) > 8 else 0, ha="right" if max(len(c) for c in categorias) > 8 else "center")
    ax.set_ylabel(rotulo_y)
    if percentual:
        ax.set_ylim(0, 1.05)
        ax.yaxis.set_major_formatter(lambda v, _: f"{int(round(v * 100))}%")
    ax.grid(axis="x", visible=False)
    if k >= 2:
        ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(1, 1))
    fig.tight_layout()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(caminho)
    plt.close(fig)
    return caminho.name


def fig_caixas(caminho: Path, grupos: dict[str, list[float]], rotulo_y: str) -> str | None:
    grupos = {k: [x for x in v if not _vazio(x)] for k, v in grupos.items()}
    cor_de = {k: CORES[i % len(CORES)] for i, k in enumerate(grupos)}   # cor segue a entidade
    grupos = {k: v for k, v in grupos.items() if v}
    if not grupos:
        return None
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    bp = ax.boxplot(list(grupos.values()), patch_artist=True, widths=0.5,
                    medianprops={"color": TINTA, "linewidth": 1.5}, whiskerprops={"color": TINTA2},
                    capprops={"color": TINTA2}, flierprops={"marker": "o", "markersize": 3, "markerfacecolor": TINTA2,
                                                          "markeredgecolor": "white"})
    for nome, caixa in zip(grupos, bp["boxes"]):
        caixa.set_facecolor(cor_de[nome])
        caixa.set_alpha(0.85)
        caixa.set_edgecolor("white")
    ax.set_xticks(range(1, len(grupos) + 1), list(grupos.keys()))
    ax.set_ylabel(rotulo_y)
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(caminho)
    plt.close(fig)
    return caminho.name


def fig_matriz(caminho: Path, linhas: list[str], colunas: list[str], valores: list[list[float]]) -> str | None:
    if not linhas or not colunas:
        return None
    plt = _plt()
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("azul", ["#f4f8fd", "#86b6ef", "#2a78d6", "#0d366b"])
    fig, ax = plt.subplots(figsize=(7.2, 0.5 + 0.45 * len(linhas)))
    im = ax.imshow(valores, cmap=cmap, aspect="auto")
    ax.set_xticks(range(len(colunas)), colunas, rotation=30, ha="right")
    ax.set_yticks(range(len(linhas)), linhas)
    ax.grid(False)
    vmax = max((max(r) for r in valores if r), default=0) or 1
    for i, r in enumerate(valores):
        for j, v in enumerate(r):
            ax.text(j, i, n(v), ha="center", va="center", fontsize=8, color="white" if v > vmax * 0.55 else TINTA)
    fig.colorbar(im, ax=ax, fraction=0.03)
    fig.tight_layout()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(caminho)
    plt.close(fig)
    return caminho.name


# ─── contexto ────────────────────────────────────────────────────────────────
def contexto_comum(run_id: str, cfg: dict) -> dict:
    d = dir_execucao(run_id)
    man = ler_json(d / "manifesto.json", {}) or {}
    prereg = sorted(PREREG.glob("hipoteses_v*.md"))
    pre = prereg[-1] if prereg else None
    sha_reg = (pre.with_suffix(".sha256").read_text(encoding="utf-8").split()[0]
               if pre and pre.with_suffix(".sha256").exists() else None)
    sha_atual = sha256_arquivo(pre) if pre else None
    snap = ler_json(d / "snapshot" / "snapshot.json", {}) or {}
    return {"run_id": run_id, "manifesto": man, "cfg": cfg, "snapshot": snap, "gerado_em": carimbo(),
            "prereg_arquivo": pre.name if pre else None, "prereg_sha": sha_reg, "prereg_sha_atual": sha_atual,
            "prereg_alterado": bool(sha_reg and sha_atual and sha_reg != sha_atual),
            "prereg_texto": pre.read_text(encoding="utf-8") if pre else "",
            "etapas_concluidas": man.get("etapas_concluidas", []), "etapas_pedidas": man.get("etapas", []),
            "FONTE": FONTE}


def contexto_a(run_id: str, cfg: dict, fig_dir: Path) -> dict:
    d = dir_execucao(run_id)
    a1 = ler_json(d / "a1" / "resumo.json")
    a2 = ler_json(d / "a2" / "testes.json") or ler_json(d / "a2" / "testes_piloto.json")
    a2_piloto = a2 is not None and not (d / "a2" / "testes.json").exists()
    inst = ler_json(d / "a2" / "instancias.json", {}) or {}
    ex = None
    for nome in ("execucoes.csv", "execucoes_piloto.csv"):
        if (d / "a2" / nome).exists():
            ex = pd.read_csv(d / "a2" / nome)
            break
    campos = pd.read_csv(d / "a1" / "campos.csv") if (d / "a1" / "campos.csv").exists() else None
    docs = pd.read_csv(d / "a1" / "documentos.csv") if (d / "a1" / "documentos.csv").exists() else None
    figs = {}
    if a1:
        anos = sorted(a1["censo"]["por_ano"], key=int)
        figs["completude"] = fig_barras(fig_dir / "a1_completude.png", [str(a) for a in anos],
                                        {"Completude": [a1["censo"]["por_ano"][a]["completude"] for a in anos],
                                         "Precisão de existência": [a1["censo"]["por_ano"][a]["precisao_existencia"] for a in anos]},
                                        "Proporção")
        pc = a1.get("por_campo", {})
        cs = [c for c in pc if pc[c].get("n")]
        figs["campos"] = fig_barras(fig_dir / "a1_campos.png", cs, {"Correspondência": [pc[c]["p"] for c in cs]},
                                    "Correspondência", {"Correspondência": [(pc[c]["li"], pc[c]["ls"]) for c in cs]})
    if ex is not None and len(ex):
        tipos = sorted(ex["tipo"].unique())
        figs["sucesso_tipo"] = fig_barras(
            fig_dir / "a2_sucesso_tipo.png", [rot(t) for t in tipos],
            {c: [float(ex[(ex.tipo == t) & (ex.condicao == c)]["sucesso"].mean()) if len(ex[(ex.tipo == t) & (ex.condicao == c)]) else 0
                 for t in tipos] for c in ("AGROIA", "PORTAL")}, "Taxa de sucesso")
        figs["acoes"] = fig_caixas(fig_dir / "a2_acoes.png", {c: list(ex[ex.condicao == c]["n_acoes"]) for c in ("AGROIA", "PORTAL")},
                                   "Ações de navegação por execução")
        figs["klm"] = fig_caixas(fig_dir / "a2_klm.png", {c: list(ex[ex.condicao == c]["tempo_humano_klm_s"]) for c in ("AGROIA", "PORTAL")},
                                 "Tempo humano estimado (KLM, s)")
    modelos = yaml.safe_load((RAIZ_VALIDACAO / "a2_facilitacao" / "tarefas" / "modelos.yaml").read_text(encoding="utf-8"))
    return {"a1": a1, "a2": a2, "a2_piloto": a2_piloto, "instancias": inst, "execucoes": ex, "campos": campos,
            "docs": docs, "figs": figs, "modelos": modelos,
            "prompt_portal": (RAIZ_VALIDACAO / "a2_facilitacao" / "prompts" / "condicao_portal.md").read_text(encoding="utf-8"),
            "prompt_agroia": (RAIZ_VALIDACAO / "a2_facilitacao" / "prompts" / "condicao_agroia.md").read_text(encoding="utf-8")}


def contexto_b(run_id: str, cfg: dict, fig_dir: Path) -> dict:
    d = dir_execucao(run_id) / "b"
    t = ler_json(d / "testes.json") or ler_json(d / "testes_piloto.json")
    piloto = t is not None and not (d / "testes.json").exists()
    res = None
    for nome in ("resultados.csv", "resultados_piloto.csv"):
        if (d / nome).exists():
            res = pd.read_csv(d / nome)
            break
    gab = ler_json(d / "gabarito.json", {}) or {}
    figs = {}
    if t and res is not None and len(res):
        mot = t["motores"]
        rotulos = [t["rotulos"].get(m, m) for m in mot]
        ap = t["acuracia_principal"]["por_motor"]
        figs["acuracia"] = fig_barras(fig_dir / "b_acuracia.png", rotulos,
                                      {"Acurácia": [ap.get(m, {}).get("p") for m in mot]}, "Acurácia (conjunto A)",
                                      {"Acurácia": [(ap.get(m, {}).get("li"), ap.get(m, {}).get("ls")) for m in mot]})
        figs["latencia"] = fig_caixas(fig_dir / "b_latencia.png",
                                      {t["rotulos"].get(m, m): list(res[(res.motor == m) & res.erro_infra.isna()]["latencia_s"]) for m in mot},
                                      "Latência total (s)")
        cats = sorted(res["categoria_erro"].dropna().unique())
        figs["erros"] = fig_matriz(fig_dir / "b_erros.png", rotulos, [rot(c) for c in cats],
                                   [[int(((res.motor == m) & (res.categoria_erro == c)).sum()) for c in cats] for m in mot]) if cats else None
        cat_q = sorted(res["categoria"].unique())
        figs["categoria"] = fig_barras(fig_dir / "b_categoria.png", cat_q,
                                       {t["rotulos"].get(m, m): [float(res[(res.motor == m) & (res.categoria == c)]["acerto"].mean())
                                                                 if len(res[(res.motor == m) & (res.categoria == c)]) else 0 for c in cat_q]
                                        for m in mot}, "Acerto")
    from benchmark.precos_modelos import PRECOS
    from benchmark.dataset import carregar_dataset
    return {"b": t, "b_piloto": piloto, "res": res, "gab": gab, "figs": figs, "precos": PRECOS,
            "perguntas": carregar_dataset()["perguntas"], "contexto_b": (t or {}).get("contexto", {})}


# ─── renderização ────────────────────────────────────────────────────────────
CSS = """body{font-family:Nunito,Segoe UI,Arial,sans-serif;max-width:920px;margin:32px auto;padding:0 16px;
color:#1f1f1e;line-height:1.55;background:#fff}h1,h2,h3{color:#1e5631}table{border-collapse:collapse;
width:100%;font-size:13px;margin:8px 0}th,td{border:1px solid #d9d8d2;padding:4px 6px;text-align:left;
vertical-align:top}th{background:#eef5ee}img{max-width:100%}code,pre{background:#f5f5f2;font-size:12px}
pre{padding:8px;overflow-x:auto;white-space:pre-wrap}p.fonte{font-size:12px;color:#5f5e5a;margin-top:2px}"""


def md_para_html(md: str, titulo: str, fig_dir: Path) -> str:
    import markdown
    corpo = markdown.markdown(md, extensions=["tables", "fenced_code"])

    def embutir(m):
        arq = fig_dir / Path(m.group(1)).name
        if arq.exists():
            return f'src="data:image/png;base64,{base64.b64encode(arq.read_bytes()).decode()}"'
        return m.group(0)
    corpo = re.sub(r'src="(figuras/[^"]+)"', embutir, corpo)
    corpo = corpo.replace("<p>Fonte: elaborado", '<p class="fonte">Fonte: elaborado')
    return (f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><meta name='viewport' "
            f"content='width=device-width, initial-scale=1'><title>{titulo}</title><style>{CSS}</style></head>"
            f"<body>{corpo}</body></html>")


def gerar(run_id: str, partes: list[str] | None = None, cfg: dict | None = None) -> list[str]:
    cfg = cfg or carregar_config()
    partes = partes or ["A", "B"]
    d = dir_execucao(run_id)
    out_dir = d / "relatorios"
    fig_dir = out_dir / "figuras"
    fig_dir.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), undefined=ChainableUndefined, trim_blocks=True,
                      lstrip_blocks=True, keep_trailing_newline=True)
    env.filters["rotulo_motor"] = lambda m, R: R.get(m, m)
    env.filters.update({"n": n, "pct": pct, "pv": pv, "ic": ic, "rot": rot, "json": lambda v: json.dumps(v, ensure_ascii=False, default=str)})
    env.globals.update({k: v for k, v in globals().items() if k.startswith("linhas_")})
    env.globals.update({"tabela": tabela_md, "vazio": _vazio})
    base = contexto_comum(run_id, cfg)
    gerados = []
    for parte in partes:
        ctx = dict(base)
        ctx.update(contexto_a(run_id, cfg, fig_dir) if parte == "A" else contexto_b(run_id, cfg, fig_dir))
        for tipo in ("metodologia", "resultados"):
            num = Numeracao()
            env.globals.update({"tab": num.t, "fig": num.f})
            md = env.get_template(f"{tipo}_{parte}.md.j2").render(**ctx)
            md = re.sub(r"\n{3,}", "\n\n", md)
            nome = f"{tipo}_{parte}"
            (out_dir / f"{nome}.md").write_text(md, encoding="utf-8")
            titulo = {"metodologia": "Metodologia", "resultados": "Resultados"}[tipo] + f" parte {parte}"
            (out_dir / f"{nome}.html").write_text(md_para_html(md, titulo, fig_dir), encoding="utf-8")
            gerados += [f"{nome}.md", f"{nome}.html"]
    return gerados


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--partes", default="A,B")
    a = ap.parse_args()
    print(gerar(a.run_id, a.partes.split(",")))


if __name__ == "__main__":
    main()
