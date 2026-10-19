"""Ablação do clima na projeção (plano v3, E6, validação item 4) — prévia.

Mesmo modelo de árvores global de rodar.py, com e sem atributos de clima, nas folhosas e
brássicas (alface, couve, couve-flor, repolho, brócolis). Escolha AGRONÔMICA: são os
produtos que a CEASA Curitiba recebe sobretudo do cinturão verde da RMC, onde está o clima
medido — não decorre da análise clima × preço (que, refeita com teste exato, não achou
associação). Clima = anomalia semanal das células distintas do NASA POWER que cobrem os 5
pontos da RMC (PROVISÓRIO), só com semanas ≤ origem (sem vazamento).

Pergunta: o clima faz o modelo vencer o ingênuo simples, que a regra de publicação exige?
    python analises/projecao_viabilidade/ablacao_clima.py
"""

from __future__ import annotations

import math
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
HOJE = date.today().isoformat()   # uma única data por execução (achado B14)
RAIZ = AQUI.parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "analises" / "clima_preco"))
sys.path.insert(0, str(AQUI))

import rodar as viab  # noqa: E402  (analises/projecao_viabilidade/rodar.py)
from ml.atributos import montar_atributos  # noqa: E402
from ml.avaliacao import decidir_publicacao  # noqa: E402

ALVO = ["alface", "couve-flor", "repolho", "brocolo", "couve"]
HORIZONTES = (4, 8)
SEMANAS = 52


def _clima():
    import importlib.util
    spec = importlib.util.spec_from_file_location("clima_rodar", RAIZ / "analises/clima_preco/rodar.py")
    cp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cp)
    return cp.semanal_clima(cp.clima_diario())


def atributos_clima(anom: pd.DataFrame, origem) -> dict:
    """Somas e médias móveis das anomalias até a origem (inclusive)."""
    passado = anom[anom.index <= origem]
    out = {}
    for j in (4, 8, 12):
        janela = passado.tail(j)
        out[f"chuva_{j}"] = float(janela["chuva_mm"].sum())
        out[f"tmin_{j}"] = float(janela["tmin"].mean())
    out["solo_4"] = float(passado.tail(4)["umidade_solo"].mean())
    out["geada_8"] = float(passado.tail(8)["dias_geada"].sum())
    return out


def tabela(series: dict, h: int, anom: pd.DataFrame | None) -> pd.DataFrame:
    linhas = []
    for prod, s in series.items():
        idx = s.index
        for k in range(60, len(idx) - h):
            o, alvo = idx[k], idx[k] + pd.Timedelta(weeks=h)
            if alvo not in s.index:
                continue
            at = montar_atributos(s, o, h)
            if at["lag_0"] is None or at["lag_52"] is None:
                continue
            linha = {"produto": prod, "origem": o, "alvo_data": alvo, "preco_origem": at["lag_0"],
                     "y": math.log(s[alvo] / at["lag_0"]), **at}
            if anom is not None:
                linha.update(atributos_clima(anom, o))
            linhas.append(linha)
    tab = pd.DataFrame(linhas)
    base = tab["preco_origem"]
    for c in [c for c in tab.columns if c.startswith(("lag_", "media_", "desvio_"))]:
        tab[c] = np.log(tab[c] / base) if c.startswith(("lag_", "media_")) else tab[c] / base
    tab["produto_cod"] = tab["produto"].astype("category").cat.codes
    return tab


def prever(tab: pd.DataFrame, origens) -> pd.DataFrame:
    from sklearn.ensemble import HistGradientBoostingRegressor
    cols = [c for c in tab.columns if c not in ("produto", "origem", "alvo_data", "y", "preco_origem")]
    saida = []
    for o in origens:
        treino, teste = tab[tab["alvo_data"] <= o], tab[(tab["origem"] == o) & tab["produto"].isin(ALVO)]
        if len(treino) < 500 or teste.empty:
            continue
        gbm = HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, max_leaf_nodes=15,
                                            min_samples_leaf=40, random_state=0)
        gbm.fit(treino[cols], treino["y"])
        p = np.exp(gbm.predict(teste[cols])) * teste["preco_origem"]
        saida += [{"produto": a, "origem": o, "previsto": v} for a, v in zip(teste["produto"], p)]
    return pd.DataFrame(saida)


def main():
    series = viab.series_semanais(viab.carregar("CURITIBA"))
    anom = _clima()
    datas = sorted(set().union(*(s.index for s in series.values())))
    l = ["# Ablação do clima na projeção — prévia", "",
         f"Gerado em {HOJE}. Origem móvel nas últimas {SEMANAS} semanas; árvores "
         "com gradiente global, com e sem clima do cinturão verde da RMC (provisório). Regra de "
         "publicação: MASE < 1 e p < 0,05 contra os dois ingênuos.", ""]
    for h in HORIZONTES:
        origens = datas[-(SEMANAS + h):-h]
        sem = prever(tabela(series, h, None), origens).rename(columns={"previsto": "sem_clima"})
        com = prever(tabela(series, h, anom), origens).rename(columns={"previsto": "com_clima"})
        r = sem.merge(com, on=["produto", "origem"])
        l += [f"## Horizonte de {h} semanas", "",
              "| Produto | MASE ingênuo | MASE sem clima | MASE com clima | Publica com clima? | Motivo |",
              "| --- | --- | --- | --- | --- | --- |"]
        for prod, g in r.groupby("produto"):
            s = series[prod]
            alvo = g["origem"] + pd.Timedelta(weeks=h)
            real = s.reindex(alvo).to_numpy()
            ing = s.reindex(g["origem"]).to_numpy()
            saz = s.reindex(alvo - pd.Timedelta(weeks=52)).to_numpy()
            ok = ~np.isnan(real) & ~np.isnan(saz)
            hist = s[s.index <= g["origem"].min()].to_numpy()
            escala = np.mean(np.abs(hist[52:] - hist[:-52]))
            mase = lambda prev: float(np.mean(np.abs(real[ok] - prev[ok])) / escala)
            d = decidir_publicacao(real[ok], g["com_clima"].to_numpy()[ok], ing[ok], saz[ok], hist, h=h)
            l.append(f"| {prod} | {mase(ing):.2f} | {mase(g['sem_clima'].to_numpy()):.2f} | "
                     f"{mase(g['com_clima'].to_numpy()):.2f} | {'sim' if d['publicar'] else 'não'} | "
                     f"{d['motivo'] or '—'} |")
        l.append("")
    arq = AQUI / f"ablacao_clima_{HOJE}.md"
    arq.write_text("\n".join(l), encoding="utf-8")
    print(arq)


if __name__ == "__main__":
    main()
