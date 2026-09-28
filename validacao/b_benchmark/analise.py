"""Análise da Parte B (seção 5.5) e auditoria humana da pontuação (5.6).

- Acurácia entre motores: Q de Cochran sobre as perguntas do conjunto A (desfecho por maioria
  das repetições); se significativo, McNemar exato par a par com Holm.
- Latência e custo: Friedman; se significativo, Wilcoxon par a par com Holm; δ de Cliff.
- Abstenção: Wilson (baixo poder declarado).
- Principal (intenção de tratar: falha de infraestrutura = erro) e sensibilidade (por protocolo).
- Poder: menor efeito detectável do McNemar com n perguntas.

Uso: python -m validacao.b_benchmark.analise --run-id RUN [--auditoria]
"""

from __future__ import annotations

import argparse
import itertools
import random

import numpy as np
import pandas as pd

from validacao.b_benchmark.pontuacao import carregar_chamadas, pontuar
from validacao.comum import carregar_config, dir_execucao, ler_json, salvar_json
from validacao.estatistica.multiplos import cochran_q, cohen_kappa, fleiss_kappa, friedman, holm
from validacao.estatistica.pareados import (cliff_delta, magnitude_cliff, mcnemar_exato, menor_efeito_detectavel,
                                            minimo_discordantes, tabela_2x2, wilcoxon_pareado)
from validacao.estatistica.proporcoes import wilson


def _pct(v, q):
    v = sorted(x for x in v if x is not None and not pd.isna(x))
    if not v:
        return None
    return float(np.percentile(v, q))


def resultados(run_id: str, cfg: dict, piloto: bool = False) -> pd.DataFrame:
    from benchmark.dataset import carregar_dataset
    from benchmark.precos_modelos import custo_usd
    d = dir_execucao(run_id) / "b"
    suf = "_piloto" if piloto else ""
    gab = ler_json(d / "gabarito.json", {})
    qs = {q["id"]: q for q in carregar_dataset()["perguntas"]}
    linhas = []
    for ch in carregar_chamadas(d / f"chamadas{suf}.jsonl"):
        q = qs[ch["pergunta_id"]]
        p = pontuar(ch, q, gab.get(q["id"], {"tipo": "sem_gabarito"}), cfg["b"]["tolerancia_relativa"])
        fim = ch.get("fim") or {}
        te, ts = fim.get("tokens_entrada"), fim.get("tokens_saida")
        linhas.append({"chave": ch["chave"], "pergunta_id": q["id"], "categoria": q["categoria"],
                       "conjunto": q["conjunto"], "motor": ch["motor"], "rep": ch["rep"],
                       "latencia_s": ch["latencia_s"], "ttft_s": ch.get("ttft_s"),
                       "tokens_entrada": te, "tokens_saida": ts,
                       "custo_usd": custo_usd(ch["motor"], te or 0, ts or 0) if te is not None else None,
                       "erro_infra": ch.get("erro"), "gabarito_tipo": gab.get(q["id"], {}).get("tipo"),
                       **{k: v for k, v in p.items() if k != "tools"}, "tools": ",".join(p["tools"]),
                       "resposta": (ch.get("texto") or "")[:2000]})
    df = pd.DataFrame(linhas)
    if not df.empty:
        df.to_csv(d / f"resultados{suf}.csv", index=False, encoding="utf-8")
        df[df["categoria_erro"].notna()].to_csv(d / f"erros{suf}.csv", index=False, encoding="utf-8")
    return df


def _maioria(df: pd.DataFrame, col: str) -> pd.DataFrame:
    return df.groupby(["pergunta_id", "motor"])[col].apply(lambda s: int(s.astype(bool).sum() > len(s) / 2)).unstack()


def comparar_acuracia(df: pd.DataFrame, motores: list[str], alfa: float, conf: float) -> dict:
    a = df[df["conjunto"] == "A"]
    piv = _maioria(a, "acerto").reindex(columns=motores).dropna()
    out = {"n_perguntas": int(len(piv)),
           "por_motor": {m: wilson(int(piv[m].sum()), len(piv), conf) for m in piv.columns}}
    if len(piv) and piv.shape[1] >= 2:
        out["cochran"] = cochran_q(piv.values.tolist())
        pares = {}
        for m1, m2 in itertools.combinations(piv.columns, 2):
            t = tabela_2x2(list(piv[m1]), list(piv[m2]))
            pares[f"{m1}|{m2}"] = {"tabela": t, **mcnemar_exato(t["n10"], t["n01"], conf)}
        aj = holm({k: v["p_valor"] for k, v in pares.items()}, alfa)
        for k in pares:
            pares[k]["p_holm"] = aj[k]["p_holm"]
        out["pares"] = pares
        out["post_hoc_aplicavel"] = bool(out["cochran"]["p_valor"] is not None and out["cochran"]["p_valor"] < alfa)
    return out


def comparar_continua(df: pd.DataFrame, col: str, motores: list[str], alfa: float) -> dict:
    med = df.groupby(["pergunta_id", "motor"])[col].median().unstack().reindex(columns=motores).dropna()
    out = {"n_perguntas": int(len(med)),
           "por_motor": {m: {"p50": _pct(df.loc[df.motor == m, col], 50), "p90": _pct(df.loc[df.motor == m, col], 90),
                             "p95": _pct(df.loc[df.motor == m, col], 95),
                             "media": float(df.loc[df.motor == m, col].dropna().mean()) if df.loc[df.motor == m, col].notna().any() else None}
                         for m in motores}}
    if med.shape[1] >= 3 and len(med) >= 2:
        out["friedman"] = friedman(*[med[m] for m in med.columns])
        pares = {}
        for m1, m2 in itertools.combinations(med.columns, 2):
            w = wilcoxon_pareado(list(med[m1]), list(med[m2]))
            cd = cliff_delta(list(med[m1]), list(med[m2]))
            pares[f"{m1}|{m2}"] = {**w, "cliff": cd, "cliff_magnitude": magnitude_cliff(cd)}
        aj = holm({k: v["p_valor"] for k, v in pares.items()}, alfa)
        for k in pares:
            pares[k]["p_holm"] = aj[k]["p_holm"]
        out["pares"] = pares
        out["post_hoc_aplicavel"] = bool(out["friedman"]["p_valor"] is not None and out["friedman"]["p_valor"] < alfa)
    return out


def analisar(run_id: str, cfg: dict | None = None, piloto: bool = False, auditoria: bool = False) -> dict:
    cfg = cfg or carregar_config()
    d = dir_execucao(run_id) / "b"
    suf = "_piloto" if piloto else ""
    alfa = cfg["estatistica"]["alfa"]
    conf = 1 - alfa
    motores = list(cfg["b"]["motores"])
    df = resultados(run_id, cfg, piloto)
    res: dict = {"n_chamadas": int(len(df)), "motores": motores, "rotulos": cfg["b"].get("rotulos", {})}
    if df.empty:
        salvar_json(d / f"testes{suf}.json", res)
        return res
    motores = [m for m in motores if m in set(df["motor"])]
    res["motores"] = motores
    res["acuracia_principal"] = comparar_acuracia(df, motores, alfa, conf)
    sens = df[df["erro_infra"].isna()]
    res["acuracia_sensibilidade"] = comparar_acuracia(sens, motores, alfa, conf)
    res["latencia"] = comparar_continua(sens, "latencia_s", motores, alfa)
    res["ttft"] = comparar_continua(sens, "ttft_s", motores, alfa)
    res["custo"] = comparar_continua(sens, "custo_usd", motores, alfa)
    res["custo_total_usd"] = {m: float(df.loc[df.motor == m, "custo_usd"].fillna(0).sum()) for m in motores}
    res["af"] = {m: {f"af@{k}": float(((g["af_nivel"] > 0) & (g["af_nivel"] <= k)).mean())
                     for k in (1, 2, 3)} for m, g in df[df.conjunto == "A"].groupby("motor")}
    res["uso_correto_ferramenta"] = {m: wilson(int(g["uso_correto_ferramenta"].sum()), len(g), conf)
                                     for m, g in df[df.conjunto == "A"].groupby("motor")}
    res["fidelidade_ferramentas"] = {m: float(g["fidelidade_ferramentas"].dropna().mean())
                                     if g["fidelidade_ferramentas"].notna().any() else None for m, g in df.groupby("motor")}
    b = df[df.conjunto == "B"]
    res["abstencao"] = {m: wilson(int(g["abstencao_correta"].fillna(False).astype(bool).sum()), len(g), conf)
                        for m, g in b.groupby("motor")}
    res["falsa_abstencao"] = {m: wilson(int(g["falsa_abstencao"].sum()), len(g), conf)
                              for m, g in df[df.conjunto == "A"].groupby("motor")}
    # Consistência: mesmo desfecho em todas as repetições; κ de Fleiss sobre o desfecho
    cons = {}
    for m, g in df.groupby("motor"):
        rot = [list(gg.sort_values("rep")["desfecho"]) for _, gg in g.groupby("pergunta_id")]
        cons[m] = {"prop_mesmo_desfecho": float(np.mean([len(set(r)) == 1 for r in rot])) if rot else None,
                   "fleiss_kappa": fleiss_kappa(rot)}
    res["consistencia"] = cons
    res["erros"] = {m: g["categoria_erro"].value_counts().to_dict() for m, g in df.groupby("motor")}
    res["erros_infra"] = {m: g["erro_infra"].value_counts().to_dict() for m, g in df.groupby("motor")}
    res["acuracia_por_categoria"] = {c: {m: float(gg["acerto"].mean()) for m, gg in g.groupby("motor")}
                                     for c, g in df.groupby("categoria")}
    n = res["acuracia_principal"]["n_perguntas"]
    res["poder"] = {"n": n, "minimo_discordantes_sig": minimo_discordantes(alfa),
                    "mde_psi_0_3": menor_efeito_detectavel(n, 0.3, alfa, cfg["estatistica"]["poder"]) if n else None,
                    "mde_psi_0_5": menor_efeito_detectavel(n, 0.5, alfa, cfg["estatistica"]["poder"]) if n else None}
    res["contexto"] = ler_json(d / f"contexto{suf}.json", {})

    # Auditoria (5.6): amostra estratificada de 20% gravada uma vez; kappa quando preenchida.
    arq_aud = d / f"auditoria{suf}.csv"
    if not arq_aud.exists():
        rng = random.Random(int(cfg["execucao"]["seed"]) + 3)
        partes = []
        for _, g in df.groupby(["motor", "desfecho"]):
            k = max(1, round(len(g) * cfg["b"]["auditoria_fracao"]))
            partes.append(g.loc[rng.sample(list(g.index), min(k, len(g)))])
        aud = pd.concat(partes)[["chave", "pergunta_id", "motor", "rep", "desfecho", "acerto", "resposta"]]
        aud = aud.rename(columns={"acerto": "acerto_automatico"})
        aud["acerto_humano"] = ""
        aud["observacao_humana"] = ""
        aud.sort_values("chave").to_csv(arq_aud, index=False, encoding="utf-8")
    if auditoria or arq_aud.exists():
        aud = pd.read_csv(arq_aud, dtype={"acerto_humano": str})
        pre = aud[aud["acerto_humano"].fillna("").str.strip() != ""]
        if len(pre):
            hum = pre["acerto_humano"].str.strip().str.lower().isin(["1", "true", "sim", "s", "verdadeiro"])
            res["auditoria"] = {"n_rotuladas": int(len(pre)), "n_total": int(len(aud)),
                                "kappa": cohen_kappa(list(pre["acerto_automatico"].astype(bool)), list(hum)),
                                "concordancia": float((pre["acerto_automatico"].astype(bool) == hum).mean())}
    salvar_json(d / f"testes{suf}.json", res)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--auditoria", action="store_true")
    ap.add_argument("--piloto", action="store_true")
    a = ap.parse_args()
    r = analisar(a.run_id, piloto=a.piloto, auditoria=a.auditoria)
    print(r.get("auditoria") or {k: r.get(k) for k in ("n_chamadas",)})
    if a.auditoria:
        from validacao.relatorios.gerar import gerar
        gerar(a.run_id, partes=["B"])


if __name__ == "__main__":
    main()
