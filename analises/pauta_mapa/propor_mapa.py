"""Proposta de mapeamento espécie da pauta → descrição da CEASA-PR (plano v3, E3) — para validação.

Para cada espécie (e variedade) da Portaria SMSAN 175/2026, lista as descrições cotadas na
CEASA Curitiba nos últimos 30 dias (tabela ceasa_pr_cotacoes) e sugere uma de referência:
a mais cotada entre as vendidas a granel com peso (R$/kg comparável ao teto por quilograma),
evitando itens especiais (bandeja, pacote, cereja, importado, hidropônico, colorido), que só
entram se não houver outra. Mostra até 3 alternativas.
A sugestão NÃO vale até a SMSAN validar (premissa P7; integridade I22).

Só lê o banco; grava proposta_mapa_<data>.md e .csv nesta pasta.
    python analises/pauta_mapa/propor_mapa.py
"""

from __future__ import annotations

import csv
import os
import re
import sys
import unicodedata
from datetime import date, timedelta
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
sys.path.insert(0, str(RAIZ))

from chat.pauta_dados import PAUTA_175  # noqa: E402

HOJE = date.today()
RECENTE = (HOJE - timedelta(days=30)).isoformat()
TETO_REVOGADO = 3.99   # Resolução SMSAN 2/2024, revogada em 24/09/2026 — só referência

# nomes alternativos usados pela CEASA-PR
SINONIMOS = {      # nomes usados pela CEASA-PR (conferidos nas descrições de Curitiba)
    "aipim": ["aipim mandioca", "mandioca", "aipim"],
    "mandioquinha-salsa": ["mandioquinha batata salsa", "mandioquinha", "batata salsa"],
    "brócolis": ["couve brocolo", "couve brocolis", "brocolis", "brocolo"],
    "feijão-vagem": ["feijao vagem", "vagem"],
    "pitaya": ["pitaya", "pitaia"],
    "cheiro-verde": ["cheiro verde"],
    "escarola": ["escarola chicoria", "escarola"],
    "maxixe": ["maxixi", "maxixe"],
    "inhame": ["inhame taia", "inhame"],
}
ESPECIAIS = re.compile(r"\b(bj|pc)\b|bandeja|cereja|importad|hidroponic|colorido|organic", re.I)
VARIEDADE = {"murcote": ["murcote", "murcot", "murkote", "morcote"],
             "tahiti": ["tahiti", "taiti"]}


def norm(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[-/]", " ", s.lower())).strip()


def cliente():
    from dotenv import load_dotenv
    from supabase import create_client
    load_dotenv(RAIZ / ".env")
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def carregar_recentes(sb) -> list[dict]:
    """Cotações de Curitiba dos últimos 30 dias, agregadas por descrição (paginação por id)."""
    linhas, ultimo = [], 0
    while True:
        lote = (sb.table("ceasa_pr_cotacoes")
                .select("id,data_coleta,descricao,embalagem,peso_kg,preco,preco_kg")
                .eq("unidade", "CURITIBA").gte("data_coleta", RECENTE).gt("id", ultimo)
                .order("id").limit(1000).execute().data or [])
        linhas += lote
        if len(lote) < 1000:
            break
        ultimo = lote[-1]["id"]
    por_desc: dict[str, dict] = {}
    for l in linhas:
        d = por_desc.setdefault(l["descricao"], {"descricao": l["descricao"], "embalagem": l["embalagem"],
                                                 "peso_kg": l["peso_kg"], "precos": [], "precos_kg": [],
                                                 "ultima_data": l["data_coleta"]})
        d["precos"].append(l["preco"])
        if l["preco_kg"] is not None:
            d["precos_kg"].append(l["preco_kg"])
        d["ultima_data"] = max(d["ultima_data"], l["data_coleta"])
    for d in por_desc.values():
        d["cotacoes_30d"] = len(d["precos"])
        d["media_30d"] = round(sum(d["precos"]) / len(d["precos"]), 2)
        d["media_kg_30d"] = round(sum(d["precos_kg"]) / len(d["precos_kg"]), 2) if d["precos_kg"] else None
        d["especial"] = bool(ESPECIAIS.search(d["descricao"] + " " + (d["embalagem"] or "")))
    return list(por_desc.values())


def candidatos(recentes: list[dict], especie: str, variedade: str | None, todas: list[str]) -> list[dict]:
    nomes = [norm(n) for n in SINONIMOS.get(especie, [especie])]
    # nomes de OUTRAS espécies mais longos que casam com a mesma descrição ("batata doce" ⊃ "batata")
    outros = [norm(n) for o in todas if o != especie for n in SINONIMOS.get(o, [o])]
    saida = []
    for c in recentes:
        d = norm(c["descricao"])
        casados = [n for n in nomes if d == n or d.startswith(n + " ")]
        if not casados:
            continue
        if any((d == o or d.startswith(o + " ")) and len(o) > max(len(n) for n in casados) for o in outros):
            continue
        if variedade and not any(v in d for v in VARIEDADE.get(variedade, [norm(variedade)])):
            continue
        saida.append(c)
    return sorted(saida, key=lambda c: (c["peso_kg"] is not None, not c["especial"], c["cotacoes_30d"]),
                  reverse=True)


def main():
    recentes_todas = carregar_recentes(cliente())
    unicas, estacoes = {}, {}
    for l in PAUTA_175:
        k = (l["especie"], l["variedade"])
        unicas.setdefault(k, l)
        estacoes.setdefault(k, set()).add("OI" if l["estacao"] == "outono_inverno" else "PV")
    todas_especies = sorted({e for e, _ in unicas})
    linhas_md, linhas_csv, resumo = [], [], {"com_fonte": 0, "sem_peso": 0, "sem_fonte": 0}
    for (esp, var), l in sorted(unicas.items(), key=lambda x: (x[1]["ordem_subgrupo"], x[0][0], x[0][1] or "")):
        cand = candidatos(recentes_todas, esp, var, todas_especies)
        sug = cand[0] if cand else None
        outras = "; ".join((f"{c['descricao']} ({c['media_kg_30d']:.2f}/kg)" if c["media_kg_30d"]
                            else c["descricao"]).replace(".", ",") for c in cand[1:4]) or "—"
        if not sug:
            situacao = "sem_fonte"
        elif sug["peso_kg"] is None:
            situacao = "sem_peso"
        else:
            situacao = "com_fonte"
        resumo[situacao] += 1
        nome = esp + (f" {var}" if var else "")
        rkg = f"{sug['media_kg_30d']:.2f}".replace(".", ",") if sug and sug["media_kg_30d"] else "—"
        acima = "sim" if sug and sug["media_kg_30d"] and sug["media_kg_30d"] > TETO_REVOGADO else ""
        linhas_md.append(
            f"| {l['subgrupo']} | {nome} | {'/'.join(sorted(estacoes[(esp, var)]))} | "
            f"{sug['descricao'] if sug else '—'} | {rkg} | {acima} | {outras} | {situacao} | "
            f"{'sim' if l['validar_smsan'] else ''} |")
        for c in cand:
            linhas_csv.append({"especie": esp, "variedade": var or "", "sugerida": c is sug,
                               **{k: c[k] for k in ("descricao", "embalagem", "peso_kg", "ultima_data",
                                                    "cotacoes_30d", "media_kg_30d", "media_30d", "especial")}})
    cab = [f"# Proposta de mapeamento pauta → CEASA-PR (Curitiba) — {HOJE.isoformat()}", "",
           "Para validação da SMSAN (premissa P7). Sugestão = descrição cotada nos últimos 30 dias, com "
           "peso (R$/kg), vendida a granel e com mais cotações; itens especiais (bandeja, pacote, cereja, "
           "importado, hidropônico, colorido) só quando não há outro. Todas as alternativas no CSV ao "
           "lado. \"Acima de R$ 3,99\" compara "
           "a média de 30 dias com o teto da Resolução SMSAN 2/2024, **revogada em 24/09/2026** — só "
           "referência enquanto não houver nova resolução.", "",
           f"Resumo: {resumo['com_fonte']} espécies com fonte por kg, {resumo['sem_peso']} só por "
           f"embalagem sem peso, {resumo['sem_fonte']} sem cotação recente na CEASA Curitiba.", "",
           "| Subgrupo | Espécie | Estação | Descrição sugerida (CEASA-PR) | R$/kg (média 30 d) | "
           "Acima de R$ 3,99? | Outras opções (até 3) | Situação | Interpretação a validar |",
           "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    (AQUI / f"proposta_mapa_{HOJE.isoformat()}.md").write_text("\n".join(cab + linhas_md) + "\n",
                                                               encoding="utf-8")
    with open(AQUI / f"proposta_mapa_{HOJE.isoformat()}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas_csv[0]) if linhas_csv else ["especie"])
        w.writeheader()
        w.writerows(linhas_csv)
    print(resumo, AQUI / f"proposta_mapa_{HOJE.isoformat()}.md")


if __name__ == "__main__":
    main()
