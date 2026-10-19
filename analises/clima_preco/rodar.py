"""Clima × preço — análise preliminar (plano v3, E5), PROHORT Curitiba.

Escopo PROVISÓRIO: folhosas e brássicas, que a CEASA Curitiba recebe sobretudo do cinturão
verde da RMC; clima = média simples das 5 regiões provisórias de sql/clima.sql (Curitiba,
Colombo, São José dos Pinhais, Mandirituba, Araucária). A ponderação por procedência (E3,
P8/P9) ainda não existe — os resultados são indício, não conclusão.

Procedimento (seção "Clima × preço" do plano):
  1. preço semanal = mediana da semana, deflacionada pelo IPCA, em log;
  2. STL (período 52) → resíduo = variação que o calendário não explica;
  3. anomalias semanais de clima contra a climatologia 1991–2020 da mesma semana do ano;
  4. correlação cruzada resíduo × anomalia, defasagens 0–16 semanas:
     IC 95% por bootstrap em blocos móveis (bloco de 8 semanas);
     valor-p EXATO por todos os deslocamentos circulares do clima (preserva a autocorrelação);
  5. Granger (clima → preço) com 4 e 8 defasagens, depois de ADF e KPSS;
  6. Benjamini-Hochberg sobre todos os testes (produto × variável × defasagem).

Só lê fontes públicas e o banco; grava relatório e CSV nesta pasta (cache em _cache/).
    python analises/clima_preco/rodar.py
"""

from __future__ import annotations

import json
import os
import sys
import warnings
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
SAIDA = Path(__file__).resolve().parent
CACHE = SAIDA / "_cache"

from chat.clima_collector import (ONI_URL, SIDRA_URL, buscar_power, parse_power,  # noqa: E402
                                  parse_sidra)

REGIOES = {   # mesmas coordenadas de sql/clima.sql (provisórias)
    "pr_curitiba": (-25.4284, -49.2733), "pr_colombo": (-25.2925, -49.2262),
    "pr_sjp": (-25.5302, -49.2061), "pr_mandirituba": (-25.7769, -49.3256),
    "pr_araucaria": (-25.5859, -49.4047),
}
PRODUTOS = ["alface", "couve", "couve-flor", "repolho", "brocolo"]
DEFASAGENS = range(0, 17)
CELULAS_DISTINTAS = None
HOJE = date.today().isoformat()   # uma única data por execução
N_BOOT = 999
BLOCO = 8
SEMENTE = 20261016


# ── Dados ────────────────────────────────────────────────────────────────────

def clima_diario() -> pd.DataFrame:
    import httpx
    CACHE.mkdir(exist_ok=True)
    quadros = []
    with httpx.Client(timeout=300) as c:
        for rid, (lat, lon) in REGIOES.items():
            arq = CACHE / f"power_{rid}.json"
            if not arq.exists():
                arq.write_text(json.dumps(buscar_power(c, lat, lon, date(1991, 1, 1), date.today())))
            quadros.append(pd.DataFrame(parse_power(json.loads(arq.read_text()), rid)))
    # Pontos que caem na MESMA célula de 0,5° do POWER têm séries idênticas (achado M3):
    # 4 dos 5 pontos são a mesma célula. Média só sobre as células distintas.
    unicos, vistos = [], set()
    for q in quadros:
        assinatura = tuple(q["chuva_mm"].round(3)) + tuple(q["tmax_c"].round(3))
        if assinatura not in vistos:
            vistos.add(assinatura)
            unicos.append(q)
    global CELULAS_DISTINTAS
    CELULAS_DISTINTAS = len(unicos)
    d = pd.concat(unicos)
    d["data"] = pd.to_datetime(d["data"])
    return d.groupby("data").mean(numeric_only=True)       # média simples das células distintas


def ipca() -> pd.Series:
    import httpx
    arq = CACHE / "ipca.json"
    if not arq.exists():
        arq.write_text(json.dumps(httpx.get(SIDRA_URL, timeout=120).json()))
    s = pd.DataFrame(parse_sidra(json.loads(arq.read_text())))
    return s.set_index(pd.to_datetime(s["mes"]))["numero_indice"]


def precos() -> pd.DataFrame:
    from dotenv import load_dotenv
    from supabase import create_client
    load_dotenv(RAIZ / ".env")
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    linhas = []
    for p in PRODUTOS:
        i = 0
        while True:
            lote = (sb.table("prohort_precos").select("produto_norm,unidade,data_coleta,preco_medio")
                    .eq("ceasa", "CURITIBA").eq("produto_norm", p).order("id")
                    .range(i, i + 999).execute().data)
            linhas += lote
            if len(lote) < 1000:
                break
            i += 1000
    d = pd.DataFrame(linhas)
    d = d[d["preco_medio"] > 0]
    d["data"] = pd.to_datetime(d["data_coleta"])
    return d


# ── Séries semanais ──────────────────────────────────────────────────────────

def semanal_clima(d: pd.DataFrame) -> pd.DataFrame:
    w = pd.DataFrame({
        "chuva_mm": d["chuva_mm"].resample("W-MON", label="left", closed="left").sum(min_count=5),
        "dias_chuva": (d["chuva_mm"] >= 1).resample("W-MON", label="left", closed="left").sum(),
        "tmax": d["tmax_c"].resample("W-MON", label="left", closed="left").mean(),
        "tmin": d["tmin_c"].resample("W-MON", label="left", closed="left").mean(),
        "dias_geada": (d["tmin_c"] <= 2).resample("W-MON", label="left", closed="left").sum(),
        "dias_calor": (d["tmax_c"] >= 32).resample("W-MON", label="left", closed="left").sum(),
        "umidade_solo": d["umidade_solo"].resample("W-MON", label="left", closed="left").mean(),
    })
    semana = w.index.isocalendar().week.clip(upper=52).astype(int)
    base = w[(w.index.year >= 1991) & (w.index.year <= 2020)]
    clim = base.groupby(base.index.isocalendar().week.clip(upper=52).astype(int)).mean()
    anom = w - clim.loc[semana].set_index(w.index)
    return anom.dropna()


def semanal_preco(d: pd.DataFrame, indice: pd.Series) -> dict[str, pd.Series]:
    from statsmodels.tsa.seasonal import STL
    deflator = indice / indice.iloc[-1]                     # preços em R$ do último mês
    out = {}
    for p, g in d.groupby("produto_norm"):
        un = g["unidade"].mode().iat[0]
        s = g[g["unidade"] == un].set_index("data")["preco_medio"].sort_index()
        mes = s.index.to_period("M").to_timestamp()
        # meses ainda sem IPCA publicado usam o último índice disponível (ordem cronológica)
        meses = pd.DatetimeIndex(sorted(set(deflator.index) | set(mes)))
        s = s / deflator.reindex(meses).ffill().reindex(mes).values
        w = np.log(s.resample("W-MON", label="left", closed="left").median()).interpolate(limit=2)
        w = w.dropna()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = STL(w, period=52, robust=True).fit().resid
        out[p] = res
    return out


# ── Estatística ──────────────────────────────────────────────────────────────

def _corr(x: np.ndarray, y: np.ndarray) -> float:
    return float(np.corrcoef(x, y)[0, 1])


def correlacao_defasada(y: pd.Series, x: pd.Series, lag: int, rng) -> dict:
    """corr(y_t, x_{t-lag}); IC por blocos móveis; p por deslocamento circular de x."""
    xs = x.shift(lag)
    j = pd.concat([y.rename("y"), xs.rename("x")], axis=1).dropna()
    yv, xv = j["y"].to_numpy(), j["x"].to_numpy()
    n = len(yv)
    r = _corr(xv, yv)
    nb = int(np.ceil(n / BLOCO))
    inicios = rng.integers(0, n - BLOCO + 1, size=(N_BOOT, nb))
    idx = (inicios[:, :, None] + np.arange(BLOCO)).reshape(N_BOOT, -1)[:, :n]
    boot = np.array([_corr(xv[i], yv[i]) for i in idx])
    # Nulo exato: TODOS os deslocamentos circulares de pelo menos meio ano. Sortear com
    # reposição (versão anterior) repetia os ~176 deslocamentos distintos e criava um piso
    # artificial de p = 0,001 (achado A1 da auditoria de 17/10/2026).
    nulo = np.array([_corr(np.roll(xv, k), yv) for k in range(26, n - 26)])
    p = (1 + np.sum(np.abs(nulo) >= abs(r))) / (1 + len(nulo))
    return {"r": r, "ic_inf": float(np.percentile(boot, 2.5)),
            "ic_sup": float(np.percentile(boot, 97.5)), "p": float(p), "n": n}


def estacionaria(s: pd.Series) -> dict:
    from statsmodels.tsa.stattools import adfuller, kpss
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p_adf = adfuller(s.dropna(), autolag="AIC")[1]
        p_kpss = kpss(s.dropna(), regression="c", nlags="auto")[1]
    return {"p_adf": float(p_adf), "p_kpss": float(p_kpss),
            "estacionaria": bool(p_adf < 0.05 and p_kpss > 0.05)}


def granger(y: pd.Series, x: pd.Series, lag: int) -> float:
    from statsmodels.tsa.stattools import grangercausalitytests
    j = pd.concat([y.rename("y"), x.rename("x")], axis=1).dropna()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = grangercausalitytests(j[["y", "x"]], maxlag=[lag], verbose=False)
    return float(res[lag][0]["ssr_ftest"][1])


def benjamini_hochberg(p: np.ndarray) -> np.ndarray:
    n = len(p)
    ordem = np.argsort(p)
    ajust = p[ordem] * n / np.arange(1, n + 1)
    ajust = np.minimum.accumulate(ajust[::-1])[::-1]
    out = np.empty(n)
    out[ordem] = np.minimum(ajust, 1)
    return out


# ── Relatório ────────────────────────────────────────────────────────────────

ROTULO = {"chuva_mm": "chuva da semana (mm)", "dias_chuva": "dias com chuva ≥ 1 mm",
          "tmax": "temperatura máxima média", "tmin": "temperatura mínima média",
          "dias_geada": "dias de geada (mín ≤ 2 °C)", "dias_calor": "dias de calor (máx ≥ 32 °C)",
          "umidade_solo": "umidade do solo"}


def relatorio(cc: pd.DataFrame, gr: pd.DataFrame, est: dict, periodo: tuple) -> str:
    l = ["# Clima × preço — análise preliminar (PROHORT Curitiba)", "",
         f"Gerado em {HOJE}. Preços de {periodo[0]} a {periodo[1]}, "
         "deflacionados pelo IPCA, em log, sem tendência e sazonalidade (STL). Clima: 5 pontos do "
         f"cinturão verde da RMC que caem em {CELULAS_DISTINTAS} células distintas do NASA POWER "
         "(média das células), em anomalia contra 1991–2020. **Escopo provisório:** sem "
         "ponderação por procedência (P8/P9). Valor-p exato por todos os deslocamentos "
         "circulares (substitui a versão de 16/10, que tinha piso artificial — auditoria, A1).", "",
         f"Testes: {len(cc)} correlações (produto × variável × defasagem 0–16 semanas) e "
         f"{len(gr)} testes de Granger, todos corrigidos juntos por Benjamini-Hochberg. "
         "Correlação é associação, não causa. Com o p mínimo de 1/(deslocamentos + 1) e "
         "a correção sobre todos os testes, o poder é baixo: resultado nulo significa efeito "
         "NÃO DETECTÁVEL com este desenho e estes ~4 anos, não ausência de efeito.", ""]
    sig = cc[cc["p_bh"] < 0.05]
    l += [f"## Resultado: {len(sig)} associações sobrevivem à correção para múltiplos testes", ""]
    l += ["| Produto | Variável | Defasagem (semanas) | r | IC 95% | p ajustado |",
          "| --- | --- | --- | --- | --- | --- |"]
    for _, x in sig.sort_values("p_bh").head(25).iterrows():
        l.append(f"| {x['produto']} | {ROTULO[x['variavel']]} | {x['lag']} | {x['r']:+.2f} | "
                 f"[{x['ic_inf']:+.2f}; {x['ic_sup']:+.2f}] | {x['p_bh']:.3f} |")
    if sig.empty:
        l.append("| — | nenhuma | — | — | — | — |")
    l += ["", "## Maior associação por produto (antes da correção)", "",
          "| Produto | Variável | Defasagem | r | IC 95% | p bruto | p ajustado |",
          "| --- | --- | --- | --- | --- | --- | --- |"]
    for p, g in cc.groupby("produto"):
        x = g.loc[g["r"].abs().idxmax()]
        l.append(f"| {p} | {ROTULO[x['variavel']]} | {x['lag']} | {x['r']:+.2f} | "
                 f"[{x['ic_inf']:+.2f}; {x['ic_sup']:+.2f}] | {x['p']:.3f} | {x['p_bh']:.3f} |")
    gsig = gr[gr["p_bh"] < 0.05]
    l += ["", f"## Granger (clima → preço): {len(gsig)} de {len(gr)} significativos após correção", "",
          "| Produto | Variável | Defasagens | p bruto | p ajustado |", "| --- | --- | --- | --- | --- |"]
    for _, x in gr.sort_values("p").head(12).iterrows():
        l.append(f"| {x['produto']} | {ROTULO[x['variavel']]} | {x['lag']} | {x['p']:.4f} | {x['p_bh']:.3f} |")
    l += ["", "## Estacionariedade do resíduo de preço (ADF e KPSS)", "",
          "| Produto | p ADF | p KPSS | Estacionário |", "| --- | --- | --- | --- |"]
    for p, e in est.items():
        l.append(f"| {p} | {e['p_adf']:.3f} | {e['p_kpss']:.3f} | {'sim' if e['estacionaria'] else 'não'} |")
    l += ["", "Correlação, IC e p de todas as combinações: CSV ao lado deste relatório.", ""]
    return "\n".join(l)


def main():
    rng = np.random.default_rng(SEMENTE)
    anom = semanal_clima(clima_diario())
    pdf = precos()
    residuos = semanal_preco(pdf, ipca())
    linhas, glinhas, est = [], [], {}
    for p, y in residuos.items():
        est[p] = estacionaria(y)
        for v in anom.columns:
            x = anom[v]
            for lag in DEFASAGENS:
                linhas.append({"produto": p, "variavel": v, "lag": lag,
                               **correlacao_defasada(y, x, lag, rng)})
            for lag in (4, 8):
                glinhas.append({"produto": p, "variavel": v, "lag": lag, "p": granger(y, x, lag)})
    cc, gr = pd.DataFrame(linhas), pd.DataFrame(glinhas)
    todos = benjamini_hochberg(np.concatenate([cc["p"].to_numpy(), gr["p"].to_numpy()]))
    cc["p_bh"], gr["p_bh"] = todos[:len(cc)], todos[len(cc):]
    periodo = (pdf["data_coleta"].min(), pdf["data_coleta"].max())
    stem = f"resultado_{HOJE}"
    cc.to_csv(SAIDA / f"{stem}_correlacoes.csv", index=False)
    gr.to_csv(SAIDA / f"{stem}_granger.csv", index=False)
    (SAIDA / f"{stem}.md").write_text(relatorio(cc, gr, est, periodo), encoding="utf-8")
    print(SAIDA / f"{stem}.md")


if __name__ == "__main__":
    main()
