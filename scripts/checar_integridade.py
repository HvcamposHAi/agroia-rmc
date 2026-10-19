"""Checagens de integridade e consistência (plano v3, "Plano de integridade").

Implementadas (as que já têm dado em produção):
  I1  unicidade das cotações              bloqueante
  I2  domínio (preço, unidade, data)       bloqueante
  I2b cotações em domingo                  aviso (a CEASA abre em datas especiais)
  I3  coerência do R$/kg                   bloqueante
  I4  frescor de Curitiba                  bloqueante (relatório e projeção)
  I5  continuidade (lacuna > 3 meses)      bloqueante para o alerta FAO — só com --completo
  I6  valores atípicos                     aviso
  I14 cobertura e validade do clima        bloqueante (treino)
  I17 IPCA sem meses faltantes             bloqueante (treino)
  I21 status × tabela                      bloqueante
Nenhuma checagem apaga ou corrige dado: só mede e informa.

Uso:
  python scripts/checar_integridade.py                # cotações dos últimos 30 dias
  python scripts/checar_integridade.py --completo     # base inteira (auditoria)
Grava validacao/relatorios/integridade_<data>.json; sai 1 se algum bloqueante reprovar.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import median

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

UNIDADES = {"CURITIBA", "MARINGA", "LONDRINA", "FOZ DO IGUACU", "CASCAVEL"}
PAGINA = 1000


def cliente():
    from dotenv import load_dotenv
    from supabase import create_client
    load_dotenv(RAIZ / ".env")
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def paginar(consulta) -> list[dict]:
    linhas, i = [], 0
    while True:
        lote = consulta.range(i, i + PAGINA - 1).execute().data or []
        linhas += lote
        if len(lote) < PAGINA:
            return linhas
        i += PAGINA


def paginar_por_id(montar) -> list[dict]:
    """Paginação por id (keyset): custo constante por página, mesmo com centenas de milhares
    de linhas — o deslocamento (offset) estoura o tempo limite do PostgREST.
    `montar(ultimo_id)` devolve a consulta já filtrada por id > ultimo_id."""
    linhas, ultimo = [], 0
    while True:
        lote = montar(ultimo).order("id").limit(PAGINA).execute().data or []
        linhas += lote
        if len(lote) < PAGINA:
            return linhas
        ultimo = lote[-1]["id"]


def ultimo_dia_util(d: date) -> date:
    d -= timedelta(days=1)
    while d.weekday() == 6:
        d -= timedelta(days=1)
    return d


def resultado(regra, nome, tipo, ok, afetadas=0, detalhe=None):
    return {"regra": regra, "nome": nome, "tipo": tipo, "aprovada": bool(ok),
            "linhas_afetadas": afetadas, "detalhe": detalhe,
            "hora": datetime.now(timezone.utc).isoformat(timespec="seconds")}


# ── Cotações CEASA/PR ────────────────────────────────────────────────────────

def checar_cotacoes(sb, desde: str | None, hoje: date) -> list[dict]:
    def montar(ultimo):
        q = sb.table("ceasa_pr_cotacoes").select("id,data_coleta,unidade,descricao,preco,peso_kg,preco_kg")             .gt("id", ultimo)
        return q.gte("data_coleta", desde) if desde else q
    linhas = paginar_por_id(montar)
    out = []

    vistos, dup = set(), 0
    for r in linhas:
        k = (r["data_coleta"], r["unidade"], r["descricao"])
        dup += k in vistos
        vistos.add(k)
    out.append(resultado("I1", "unicidade (data, unidade, descrição)", "bloqueante", dup == 0, dup))

    fora = [r["id"] for r in linhas
            if r["preco"] is None or r["preco"] <= 0 or r["unidade"] not in UNIDADES
            or r["data_coleta"] > hoje.isoformat()]
    out.append(resultado("I2", "domínio: preço > 0, unidade válida, data ≤ hoje",
                         "bloqueante", not fora, len(fora), fora[:20] or None))
    # A CEASA abre em alguns domingos (ex.: 22 e 29/12/2024, antes das festas): dado real,
    # publicado pela fonte — só aviso.
    domingos = sorted({r["data_coleta"] for r in linhas if date.fromisoformat(r["data_coleta"]).weekday() == 6})
    out.append(resultado("I2b", "cotações em domingo (a CEASA abre em datas especiais)", "aviso", True,
                         sum(1 for r in linhas if r["data_coleta"] in domingos), domingos or None))

    incoer = [r["id"] for r in linhas
              if (r["peso_kg"] and (r["preco_kg"] is None or abs(r["preco_kg"] - r["preco"] / r["peso_kg"]) > 0.01))
              or (not r["peso_kg"] and r["preco_kg"] is not None)]
    out.append(resultado("I3", "preco_kg = preco ÷ peso_kg (±R$ 0,01)", "bloqueante",
                         not incoer, len(incoer), incoer[:20] or None))

    # I6: variação diária > 3× a mediana das variações dos 30 dias anteriores (por série)
    series = defaultdict(list)
    for r in linhas:
        series[(r["unidade"], r["descricao"])].append((r["data_coleta"], r["preco"], r["id"]))
    atipicas = []
    for pts in series.values():
        pts.sort()
        for i in range(1, len(pts)):
            d0 = date.fromisoformat(pts[i][0])
            janela = [abs(pts[j][1] - pts[j - 1][1]) for j in range(1, i)
                      if (d0 - date.fromisoformat(pts[j][0])).days <= 30]
            if len(janela) >= 5:
                ref = median(janela)
                var = abs(pts[i][1] - pts[i - 1][1])
                if ref > 0 and var > 3 * ref:
                    atipicas.append(pts[i][2])
    out.append(resultado("I6", "variação diária > 3× a mediana dos 30 dias anteriores", "aviso",
                         True, len(atipicas), atipicas[:20] or None))
    return out


def checar_frescor_e_status(sb, hoje: date) -> list[dict]:
    ult = sb.table("ceasa_pr_cotacoes").select("data_coleta").eq("unidade", "CURITIBA") \
        .order("data_coleta", desc=True).limit(1).execute().data
    ult = ult[0]["data_coleta"] if ult else None
    limite = ultimo_dia_util(ultimo_dia_util(hoje)).isoformat()
    out = [resultado("I4", f"última cotação de Curitiba ≥ {limite} (último dia útil − 1)",
                     "bloqueante", ult is not None and ult >= limite, detalhe={"ultima": ult})]
    st = (sb.table("ceasa_pr_status").select("*").eq("id", 1).execute().data or [{}])[0]
    maior = sb.table("ceasa_pr_cotacoes").select("data_coleta").order("data_coleta", desc=True) \
        .limit(1).execute().data
    maior = maior[0]["data_coleta"] if maior else None
    ok = st.get("status") != "ok" or ((st.get("linhas_inseridas") or 0) > 0 and st.get("data_max") == maior)
    out.append(resultado("I21", "status ok ⇒ linhas gravadas e data_max = maior data da tabela",
                         "bloqueante", ok, detalhe={"status": st.get("status"),
                                                    "data_max_status": st.get("data_max"),
                                                    "maior_data_tabela": maior}))
    return out


def checar_continuidade(sb) -> list[dict]:
    """I5 (base inteira, Curitiba): séries com lacuna > 3 meses ficam fora do alerta FAO."""
    linhas = paginar_por_id(lambda u: sb.table("ceasa_pr_cotacoes").select("id,data_coleta,descricao")
                            .eq("unidade", "CURITIBA").gt("id", u))
    meses = defaultdict(set)
    for r in linhas:
        a, m = map(int, r["data_coleta"][:7].split("-"))
        meses[r["descricao"]].add(a * 12 + m - 1)
    com_lacuna = {}
    for desc, ms in meses.items():
        ms = sorted(ms)
        maior = max((b - a - 1 for a, b in zip(ms, ms[1:])), default=0)
        if maior > 3:
            com_lacuna[desc] = maior
    return [resultado("I5", "séries de Curitiba com lacuna > 3 meses (fora do alerta FAO)",
                      "bloqueante para o alerta", True, len(com_lacuna),
                      {"series_total": len(meses), "exemplos": dict(list(com_lacuna.items())[:15])})]


# ── Clima e deflator ─────────────────────────────────────────────────────────

def checar_clima(sb, hoje: date) -> list[dict]:
    regioes = sb.table("clima_regiao").select("id,lat,lon").execute().data or []
    out, detalhes, ok = [], {}, bool(regioes)
    for r in regioes:
        dias = paginar(sb.table("clima_diario").select("data,chuva_mm,tmax_c,tmin_c")
                       .eq("regiao_id", r["id"]).order("data"))
        if not dias:
            detalhes[r["id"]] = "sem dados"
            ok = False
            continue
        ini, fim = date.fromisoformat(dias[0]["data"]), date.fromisoformat(dias[-1]["data"])
        cobertura = len(dias) / ((fim - ini).days + 1)
        impossiveis = sum(1 for d in dias if (d["chuva_mm"] is not None and d["chuva_mm"] < 0) or
                          (d["tmin_c"] is not None and d["tmax_c"] is not None and d["tmin_c"] > d["tmax_c"]))
        atraso = (hoje - fim).days
        detalhes[r["id"]] = {"de": str(ini), "ate": str(fim), "cobertura": round(cobertura, 4),
                             "impossiveis": impossiveis, "atraso_dias": atraso}
        ok &= cobertura >= 0.98 and impossiveis == 0 and atraso <= 10
    out.append(resultado("I14", "clima: ≥ 98% dos dias, nada impossível, atraso ≤ 10 dias",
                         "bloqueante", ok, detalhe=detalhes))
    return out


def checar_ipca(sb, desde: str = "2017-01-01") -> list[dict]:
    meses = [r["mes"][:7] for r in paginar(sb.table("ipca_mensal").select("mes").gte("mes", desde).order("mes"))]
    idx = sorted({int(m[:4]) * 12 + int(m[5:7]) - 1 for m in meses})
    faltam = [f"{k // 12:04d}-{k % 12 + 1:02d}" for a, b in zip(idx, idx[1:]) for k in range(a + 1, b)]
    # o IBGE divulga o IPCA de um mês por volta do dia 10 do mês seguinte: mais de 2 meses
    # sem novo índice = série parada (achado B10)
    hoje = date.today()
    atraso = (hoje.year * 12 + hoje.month - 1) - idx[-1] if idx else None
    parado = atraso is None or atraso > 2
    return [resultado("I17", f"IPCA sem meses faltantes desde {desde[:7]} e com até 2 meses de atraso",
                      "bloqueante", bool(idx) and not faltam and not parado, len(faltam),
                      {"ultimo": meses[-1] if meses else None, "atraso_meses": atraso,
                       "faltam": faltam or None})]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--completo", action="store_true", help="base inteira (inclui I5)")
    ap.add_argument("--dias", type=int, default=30, help="janela das cotações sem --completo")
    a = ap.parse_args()

    sb, hoje = cliente(), date.today()
    desde = None if a.completo else (hoje - timedelta(days=a.dias)).isoformat()
    checagens = []
    for nome, f in (("cotações", lambda: checar_cotacoes(sb, desde, hoje)),
                    ("frescor/status", lambda: checar_frescor_e_status(sb, hoje)),
                    ("continuidade", lambda: checar_continuidade(sb) if a.completo else []),
                    ("clima", lambda: checar_clima(sb, hoje)),
                    ("ipca", lambda: checar_ipca(sb))):
        try:
            checagens += f()
        except Exception as e:      # tabela ausente etc.: registra como reprovação, não aborta
            checagens.append(resultado(nome, f"falha ao executar: {type(e).__name__}", "bloqueante",
                                       False, detalhe=str(e)[:200]))

    bloqueadas = [c for c in checagens if not c["aprovada"] and c["tipo"].startswith("bloqueante")]
    rel = {"executado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "escopo": "completo" if a.completo else f"cotações dos últimos {a.dias} dias",
           "aprovado": not bloqueadas, "checagens": checagens}
    # um arquivo por escopo: a checagem de 30 dias não sobrescreve a completa do dia (B10)
    sufixo = "completo" if a.completo else f"{a.dias}d"
    destino = RAIZ / "validacao" / "relatorios" / f"integridade_{hoje.isoformat()}_{sufixo}.json"
    destino.write_text(json.dumps(rel, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    for c in checagens:
        marca = "OK " if c["aprovada"] else "REPROVADA"
        print(f"{marca:9} {c['regra']:4} {c['nome']} — afetadas: {c['linhas_afetadas']}")
    print(destino)
    sys.exit(0 if not bloqueadas else 1)


if __name__ == "__main__":
    main()
