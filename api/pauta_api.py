"""Rotas da pauta do Sacolão e do planejamento de safra (plano v3, E7). Só leitura.

Incluído em api/main.py dentro de try/except: erro aqui nunca derruba a API.
Implementadas nesta etapa (dados do PROHORT, já em produção):
  GET /pauta/safra/catalogo  produtos e CEASAs aceitos
  GET /pauta/safra/sazonal   calendário sazonal de um produto numa CEASA
  GET /pauta/safra/comparar  ranking das CEASAs pela mediana dos últimos 30 dias
Pendentes: /pauta, /pauta/fundamentacao, /pauta/exportar (E2/E3) e /pauta/projecao (E6).

Sem pandas/numpy (requirements-api.txt): os cálculos estão em chat/pauta.py.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from statistics import median

from fastapi import APIRouter, HTTPException, Query

from chat import pauta

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pauta", tags=["pauta"])

FONTE_PROHORT = "PROHORT/CONAB"
CACHE_SEG = 3600
CACHE_MAX = 300          # teto de entradas: o processo da API tem 512 MB (achado M2)
PAGINA = 1000
_cache: dict[tuple, tuple[float, object, str]] = {}   # chave → (instante, valor, consultado_em)
_trava = threading.Lock()   # rotas síncronas rodam em várias threads (achado N1)


def _sb():
    from chat.db import get_supabase_client
    return get_supabase_client()


def _em_cache(chave: tuple, gerar) -> tuple[object, str]:
    """Devolve (valor, consultado_em). consultado_em = hora em que o dado foi lido do banco,
    não a do pedido (achado B12). Entradas vencidas saem a cada gravação e o total é
    limitado a CACHE_MAX, descartando as mais antigas (achado M2)."""
    agora = time.monotonic()
    with _trava:
        hit = _cache.get(chave)
    if hit and agora - hit[0] < CACHE_SEG:
        return hit[1], hit[2]
    valor = gerar()                      # fora da trava: consultas ao banco em paralelo
    consultado_em = _agora()
    with _trava:
        for k in [k for k, v in _cache.items() if agora - v[0] >= CACHE_SEG]:
            del _cache[k]
        while len(_cache) >= CACHE_MAX:
            del _cache[min(_cache, key=lambda k: _cache[k][0])]
        _cache[chave] = (agora, valor, consultado_em)
    return valor, consultado_em


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _catalogo() -> dict:
    """Produtos e CEASAs válidos (lista fechada) e a última cotação de cada par."""
    def gerar():
        linhas = _paginar(_sb().table("v_prohort_baseline_24m")
                          .select("produto_norm,ceasa,ultima_cotacao")
                          .order("produto_norm").order("ceasa"))       # achado B7
        return {
            "produtos": sorted({l["produto_norm"] for l in linhas}),
            "ceasas": sorted({l["ceasa"] for l in linhas}),
            "ultima": {(l["produto_norm"], l["ceasa"]): l["ultima_cotacao"] for l in linhas},
        }
    return _em_cache(("catalogo",), gerar)[0]


def _validar(produto: str, ceasa: str | None = None) -> tuple[str, str | None]:
    cat = _catalogo()
    p = produto.strip().lower()
    if p not in cat["produtos"]:
        raise HTTPException(422, f"produto desconhecido: use um de {', '.join(cat['produtos'])}")
    c = ceasa.strip().upper() if ceasa is not None else None
    if c is not None and c not in cat["ceasas"]:      # inclui ceasa="" (achado B1)
        raise HTTPException(422, f"CEASA desconhecida: use uma de {', '.join(cat['ceasas'])}")
    return p, c


def _paginar(consulta) -> list[dict]:
    linhas, inicio = [], 0
    while True:
        lote = consulta.range(inicio, inicio + PAGINA - 1).execute().data or []
        linhas += lote
        if len(lote) < PAGINA:
            return linhas
        inicio += PAGINA


@router.get("/safra/catalogo")
def safra_catalogo():
    """Produtos e CEASAs aceitos pelas rotas de safra (lista fechada)."""
    cat = _catalogo()
    return {"produtos": cat["produtos"], "ceasas": cat["ceasas"], "fonte": FONTE_PROHORT}


@router.get("/safra/sazonal")
def safra_sazonal(produto: str = Query(..., max_length=40),
                  ceasa: str = Query("CURITIBA", max_length=40)):
    """Índice sazonal mensal (preço do mês ÷ média do ano, mediana entre anos)."""
    p, c = _validar(produto, ceasa)

    def gerar():
        linhas = _paginar(_sb().table("prohort_precos")
                          .select("data_coleta,unidade,preco_medio")
                          .eq("produto_norm", p).eq("ceasa", c).order("data_coleta").order("id"))
        linhas = [l for l in linhas if l["preco_medio"] is not None and l["preco_medio"] > 0]
        if not linhas:
            return None
        unidade = Counter(l["unidade"] for l in linhas).most_common(1)[0][0]
        por_mes: dict[str, list[float]] = {}
        for l in linhas:
            if l["unidade"] == unidade:
                por_mes.setdefault(l["data_coleta"][:7], []).append(l["preco_medio"])
        serie = {m: median(v) for m, v in por_mes.items()}
        indice = pauta.indice_sazonal(serie)
        return {
            "produto": p, "ceasa": c, "unidade": unidade, "fonte": FONTE_PROHORT,
            "periodo": {"inicio": linhas[0]["data_coleta"], "fim": linhas[-1]["data_coleta"]},
            "meses": [{"mes": m, **indice[m]} for m in range(1, 13)],
            "mediana_mensal": [{"mes": k, "preco": round(v, 2)} for k, v in sorted(serie.items())],
            "observacao": f"Meses com menos de {pauta.MIN_ANOS_CONFIAVEL} anos de dados são pouco confiáveis.",
        }

    corpo, consultado_em = _em_cache(("sazonal", p, c), gerar)
    if corpo is None:
        raise HTTPException(404, f"sem cotações de {p} em {c}")
    return {**corpo, "consultado_em": consultado_em}


@router.get("/safra/comparar")
def safra_comparar(produto: str = Query(..., max_length=40),
                   unidade: str | None = Query(None, pattern=r"^[A-Za-z]{1,4}$")):
    """Ranking das CEASAs pela mediana dos últimos 30 dias, com exclusões e aviso de frete."""
    p, _ = _validar(produto)
    hoje = date.today()

    def gerar():
        desde = (hoje - timedelta(days=pauta.JANELA_COMPARACAO_DIAS - 1)).isoformat()
        linhas = _paginar(_sb().table("prohort_precos")
                          .select("ceasa,unidade,data_coleta,preco_medio")
                          .eq("produto_norm", p).gte("data_coleta", desde).order("id"))
        return [{"ceasa": l["ceasa"], "unidade": l["unidade"], "data": l["data_coleta"],
                 "preco": l["preco_medio"]} for l in linhas]

    cotacoes, consultado_em = _em_cache(("comparar", p, hoje.isoformat()), gerar)
    un = (unidade or "").upper() or (
        Counter(c["unidade"] for c in cotacoes if c["ceasa"] == "CURITIBA").most_common(1) or
        Counter(c["unidade"] for c in cotacoes).most_common(1) or [("KG", 0)])[0][0]
    # CEASA sem nenhuma cotação na janela: entra pela última data conhecida (vira "excluída")
    presentes = {c["ceasa"] for c in cotacoes}
    paradas = [{"ceasa": c, "unidade": un, "data": ultima, "preco": 0.01}   # preço não é usado
               for (prod, c), ultima in _catalogo()["ultima"].items()
               if prod == p and c not in presentes and ultima
               and (hoje - date.fromisoformat(ultima[:10])).days > pauta.FRESCOR_DIAS]
    resultado = pauta.comparar_ceasas(cotacoes + paradas, hoje=hoje, unidade=un)
    return {**resultado, "produto": p, "fonte": FONTE_PROHORT, "consultado_em": consultado_em}
