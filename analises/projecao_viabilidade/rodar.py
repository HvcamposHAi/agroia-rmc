"""Viabilidade da projeção semanal com o PROHORT de Curitiba (plano v3, prévia de E6).

Pergunta: com ~4 anos de PROHORT, algum modelo simples supera o ingênuo sazonal?
Avaliação com origem móvel nas últimas N semanas, sem dado posterior à origem.

Modelos:
  ingenuo           último preço observado
  ingenuo_sazonal   preço da mesma semana do ano anterior (referência obrigatória)
  ets               suavização exponencial simples (statsmodels), sem sazonalidade
  gbm_global        HistGradientBoosting (scikit-learn) global, atributos de ml/atributos.py,
                    alvo = log(preço alvo / preço da origem). Substituto do LightGBM até
                    requirements_ml.txt existir — mesmo princípio (árvores com gradiente).

Só lê o banco; grava o relatório em analises/projecao_viabilidade/.
    python analises/projecao_viabilidade/rodar.py [--semanas 52] [--ceasa CURITIBA]
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import warnings
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from ml.atributos import montar_atributos  # noqa: E402
from ml.avaliacao import diebold_mariano, escala_ingenuo_sazonal  # noqa: E402

HORIZONTES = (1, 4, 8)
MIN_SEMANAS = 104 + 8
SAIDA = Path(__file__).resolve().parent


def carregar(ceasa: str) -> pd.DataFrame:
    from dotenv import load_dotenv
    from supabase import create_client
    load_dotenv(RAIZ / ".env")
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    linhas, i = [], 0
    while True:
        lote = (sb.table("prohort_precos").select("produto_norm,unidade,data_coleta,preco_medio")
                .eq("ceasa", ceasa).order("id").range(i, i + 999).execute().data)
        linhas += lote
        if len(lote) < 1000:
            break
        i += 1000
    df = pd.DataFrame(linhas)
    df = df[df["preco_medio"] > 0]
    df["data"] = pd.to_datetime(df["data_coleta"])
    return df


def series_semanais(df: pd.DataFrame) -> dict[str, pd.Series]:
    """Mediana semanal (semana iniciada na segunda) da unidade mais comum de cada produto."""
    out = {}
    for prod, g in df.groupby("produto_norm"):
        un = g["unidade"].mode().iat[0]
        s = g[g["unidade"] == un].set_index("data")["preco_medio"].resample("W-MON", label="left",
                                                                            closed="left").median()
        s = s.interpolate(limit=2).dropna()
        if len(s) >= MIN_SEMANAS:
            out[prod] = s
    return out


def prever_ets(hist: pd.Series, h: int) -> float:
    from statsmodels.tsa.holtwinters import SimpleExpSmoothing
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ajuste = SimpleExpSmoothing(np.log(hist.values), initialization_method="estimated").fit()
    return float(np.exp(ajuste.forecast(h)[-1]))


def avaliar(series: dict[str, pd.Series], semanas: int) -> pd.DataFrame:
    from sklearn.ensemble import HistGradientBoostingRegressor

    datas = sorted(set().union(*(s.index for s in series.values())))
    origens = datas[-(semanas + max(HORIZONTES)):-max(HORIZONTES)]
    registros = []
    for h in HORIZONTES:
        # tabela de atributos global (todas as séries, todas as origens possíveis)
        linhas = []
        for prod, s in series.items():
            idx = s.index
            for k in range(60, len(idx) - h):
                o = idx[k]
                alvo = idx[k] + pd.Timedelta(weeks=h)
                if alvo not in s.index:
                    continue
                at = montar_atributos(s, o, h)
                if at["lag_0"] is None or at["lag_52"] is None:
                    continue
                linhas.append({"produto": prod, "origem": o, "alvo_data": alvo,
                               "y": math.log(s[alvo] / at["lag_0"]), **at})
        tab = pd.DataFrame(linhas)
        tab["preco_origem"] = tab["lag_0"]          # guardado antes de normalizar os lags
        base = tab["preco_origem"]
        for c in [c for c in tab.columns if c.startswith(("lag_", "media_", "desvio_"))]:
            tab[c] = np.log(tab[c] / base) if c.startswith(("lag_", "media_")) else tab[c] / base
        cols = [c for c in tab.columns if c not in ("produto", "origem", "alvo_data", "y", "preco_origem")]
        tab["produto_cod"] = tab["produto"].astype("category").cat.codes
        cols.append("produto_cod")

        for o in origens:
            treino = tab[tab["alvo_data"] <= o]            # alvo conhecido até a origem
            teste = tab[tab["origem"] == o]
            if len(treino) < 500 or teste.empty:
                continue
            gbm = HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, max_leaf_nodes=15,
                                                min_samples_leaf=40, random_state=0)
            gbm.fit(treino[cols], treino["y"])
            pred_gbm = dict(zip(teste["produto"], np.exp(gbm.predict(teste[cols])) * teste["preco_origem"]))
            for prod, s in series.items():
                alvo = o + pd.Timedelta(weeks=h)
                if o not in s.index or alvo not in s.index or prod not in pred_gbm:
                    continue
                hist = s[s.index <= o]
                sazonal = s.get(alvo - pd.Timedelta(weeks=52))
                if sazonal is None or len(hist) < 60:
                    continue
                registros.append({
                    "produto": prod, "h": h, "origem": o, "real": s[alvo],
                    "ingenuo": hist.iat[-1], "ingenuo_sazonal": sazonal,
                    "ets": prever_ets(hist, h), "gbm_global": pred_gbm[prod],
                    "escala": escala_ingenuo_sazonal(hist.values, 52),
                })
    return pd.DataFrame(registros)


def resumir(r: pd.DataFrame) -> pd.DataFrame:
    modelos = ["ingenuo", "ingenuo_sazonal", "ets", "gbm_global"]
    linhas = []
    for (prod, h), g in r.groupby(["produto", "h"]):
        linha = {"produto": prod, "h": h, "n": len(g)}
        for m in modelos:
            linha[f"mase_{m}"] = float(np.mean(np.abs(g["real"] - g[m]) / g["escala"]))
        for m in ("ets", "gbm_global"):
            dm = diebold_mariano(g["real"] - g[m], g["real"] - g["ingenuo_sazonal"], h=h)
            linha[f"p_{m}"] = dm["p_valor"]
            dm = diebold_mariano(g["real"] - g[m], g["real"] - g["ingenuo"], h=h)
            linha[f"p_{m}_ing"] = dm["p_valor"]
        linhas.append(linha)
    return pd.DataFrame(linhas)


def relatorio(res: pd.DataFrame, ceasa: str, semanas: int) -> str:
    l = [f"# Viabilidade da projeção — PROHORT {ceasa}", "",
         f"Gerado em {date.today().isoformat()}. Origem móvel nas últimas {semanas} semanas; "
         "MASE < 1 = melhor que o ingênuo sazonal. Regra v3: MASE < 1 e p < 0,05 contra o "
         "ingênuo sazonal. Regra nova (16/10/2026): além disso, p < 0,05 contra o ingênuo "
         "simples (último preço). p = Diebold-Mariano unilateral.", ""]
    for h in HORIZONTES:
        g = res[res["h"] == h]
        l += [f"## Horizonte de {h} semana(s) — {len(g)} séries", "",
              "| Modelo | MASE mediano | Séries com MASE < 1 | Publicáveis, regra v3 | Publicáveis, regra nova |",
              "| --- | --- | --- | --- | --- |"]
        for m in ("ingenuo", "ingenuo_sazonal", "ets", "gbm_global"):
            col = g[f"mase_{m}"]
            pub = nova = "—"
            if m in ("ets", "gbm_global"):
                v3 = (g[f"mase_{m}"] < 1) & (g[f"p_{m}"] < 0.05)
                pub = str(int(v3.sum()))
                nova = str(int((v3 & (g[f"p_{m}_ing"] < 0.05)).sum()))
            l.append(f"| {m} | {col.median():.2f} | {int((col < 1).sum())} | {pub} | {nova} |")
        l.append("")
    fmt = lambda v: "—" if v is None or pd.isna(v) else f"{v:.3f}"
    l += ["## Por produto (horizonte de 4 semanas)", "",
          "| Produto | MASE ing. sazonal | MASE ingênuo | MASE ETS | MASE GBM | p GBM × sazonal | p GBM × ingênuo |",
          "| --- | --- | --- | --- | --- | --- | --- |"]
    for _, x in res[res["h"] == 4].sort_values("mase_gbm_global").iterrows():
        l.append(f"| {x['produto']} | {x['mase_ingenuo_sazonal']:.2f} | {x['mase_ingenuo']:.2f} | "
                 f"{x['mase_ets']:.2f} | {x['mase_gbm_global']:.2f} | {fmt(x['p_gbm_global'])} | "
                 f"{fmt(x['p_gbm_global_ing'])} |")
    return "\n".join(l) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--semanas", type=int, default=52)
    ap.add_argument("--ceasa", default="CURITIBA")
    a = ap.parse_args()
    series = series_semanais(carregar(a.ceasa))
    print(f"{len(series)} séries com >= {MIN_SEMANAS} semanas")
    r = avaliar(series, a.semanas)
    res = resumir(r)
    stem = f"resultado_{a.ceasa.lower()}_{date.today().isoformat()}"
    res.to_csv(SAIDA / f"{stem}.csv", index=False)
    (SAIDA / f"{stem}.md").write_text(relatorio(res, a.ceasa, a.semanas), encoding="utf-8")
    print(SAIDA / f"{stem}.md")


if __name__ == "__main__":
    main()
