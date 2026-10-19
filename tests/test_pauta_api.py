"""Testes offline das rotas /pauta (plano v3, E7) — achados B1, B12 e M2 da auditoria.

Monta um app só com o roteador e substitui o catálogo; nenhuma chamada ao banco.
    pytest tests/test_pauta_api.py -v
"""

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api import pauta_api  # noqa: E402

CATALOGO = {"produtos": ["alface", "couve-flor"], "ceasas": ["CASCAVEL", "CURITIBA"],
            "ultima": {("alface", "CURITIBA"): "2026-10-15"}}


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setattr(pauta_api, "_catalogo", lambda: CATALOGO)
    pauta_api._cache.clear()
    app = FastAPI()
    app.include_router(pauta_api.router)
    return TestClient(app)


@pytest.mark.parametrize("params", [
    {"produto": "alface", "ceasa": ""},            # B1: antes virava None → 404 "em None"
    {"produto": "alface", "ceasa": "MARTE"},
    {"produto": "xyz"},
    {"produto": "alface'; drop table x;--"},
    {"produto": "a" * 41},
])
def test_sazonal_entrada_invalida_e_422(cliente, params):
    r = cliente.get("/pauta/safra/sazonal", params=params)
    assert r.status_code == 422, r.text


def test_comparar_unidade_invalida_e_422(cliente):
    assert cliente.get("/pauta/safra/comparar", params={"produto": "alface", "unidade": "KG1"}).status_code == 422


def test_cache_devolve_hora_da_leitura_do_banco(monkeypatch):
    """B12: consultado_em é a hora em que o dado foi lido, não a do pedido."""
    pauta_api._cache.clear()
    horas = iter(["2026-10-19T10:00:00+00:00", "2026-10-19T10:30:00+00:00"])
    monkeypatch.setattr(pauta_api, "_agora", lambda: next(horas))
    v1, h1 = pauta_api._em_cache(("k",), lambda: 1)
    v2, h2 = pauta_api._em_cache(("k",), lambda: 2)        # dentro da validade: não regera
    assert (v1, v2) == (1, 1) and h1 == h2 == "2026-10-19T10:00:00+00:00"


def test_cache_expurga_vencidas_e_respeita_teto(monkeypatch):
    """M2: entradas vencidas saem e o total nunca passa de CACHE_MAX."""
    pauta_api._cache.clear()
    relogio = [0.0]
    monkeypatch.setattr(pauta_api.time, "monotonic", lambda: relogio[0])
    monkeypatch.setattr(pauta_api, "CACHE_MAX", 5)
    for i in range(3):
        pauta_api._em_cache(("velha", i), lambda: i)
    relogio[0] = pauta_api.CACHE_SEG + 1                     # as 3 venceram
    pauta_api._em_cache(("nova", 0), lambda: 0)
    assert all(k[0] == "nova" for k in pauta_api._cache)
    for i in range(1, 10):
        relogio[0] += 1
        pauta_api._em_cache(("nova", i), lambda: i)
    assert len(pauta_api._cache) <= 5
    assert ("nova", 9) in pauta_api._cache and ("nova", 0) not in pauta_api._cache


def test_cache_aguenta_varias_threads(monkeypatch):
    """N1: o expurgo sem trava dava RuntimeError/KeyError (resposta 500) com várias threads."""
    import threading
    pauta_api._cache.clear()
    monkeypatch.setattr(pauta_api, "CACHE_MAX", 8)
    erros = []

    def trabalhar(t):
        try:
            for i in range(300):
                pauta_api._em_cache((t, i % 20), lambda: i)
        except Exception as e:          # noqa: BLE001
            erros.append(repr(e))

    ths = [threading.Thread(target=trabalhar, args=(t,)) for t in range(8)]
    for th in ths:
        th.start()
    for th in ths:
        th.join()
    assert erros == [] and len(pauta_api._cache) <= 8
