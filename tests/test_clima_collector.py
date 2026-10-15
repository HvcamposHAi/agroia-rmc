"""Testes offline do coletor de clima (plano v3, E4): parsers e semântica de status.

    pytest tests/test_clima_collector.py -v
"""

import sys
import types

import pytest

from chat import clima_collector as cc

POWER = {
    "header": {"fill_value": -999.0},
    "properties": {"parameter": {
        "PRECTOTCORR": {"20261001": 12.5, "20261002": 0.0, "20261003": -999.0},
        "T2M_MAX": {"20261001": 24.1, "20261002": 27.3, "20261003": -999.0},
        "T2M_MIN": {"20261001": 13.0, "20261002": -999.0, "20261003": -999.0},
        "T2M": {"20261001": 18.2, "20261002": 20.0, "20261003": -999.0},
        "RH2M": {"20261001": 81.0, "20261002": 70.5, "20261003": -999.0},
        "GWETROOT": {"20261001": 0.71, "20261002": 0.69, "20261003": -999.0},
    }},
}

ONI = """ 1950         2026
 2025  -0.60  -0.40  -0.20   0.00   0.10   0.10   0.00  -0.10  -0.30  -0.50  -0.60  -0.70
 2026  -0.50  -0.30  -0.10   0.10   0.30   0.50   0.70 -99.90 -99.90 -99.90 -99.90 -99.90
  -99.9
 ONI from CPC
"""

SIDRA = [
    {"D3C": "Mês (Código)", "V": "Valor"},
    {"D3C": "202607", "V": "7657.7300000000000"},
    {"D3C": "202608", "V": "7661.5600000000000"},
    {"D3C": "202609", "V": "..."},
]


def test_parse_power_preenchimento_e_cauda():
    linhas = cc.parse_power(POWER, "pr_colombo")
    assert [l["data"] for l in linhas] == ["2026-10-01", "2026-10-02"]   # 03/10 só -999: fora
    assert linhas[0] == {"regiao_id": "pr_colombo", "data": "2026-10-01", "chuva_mm": 12.5,
                         "tmax_c": 24.1, "tmin_c": 13.0, "tmed_c": 18.2, "umidade_rel": 81.0,
                         "umidade_solo": 0.71}
    assert linhas[1]["tmin_c"] is None and linhas[1]["chuva_mm"] == 0.0   # zero é dado


def test_parse_oni_ignora_ausentes_e_rodape():
    linhas = cc.parse_oni(ONI)
    assert len(linhas) == 12 + 7
    assert linhas[0] == {"mes": "2025-01-01", "oni": -0.6}
    assert linhas[-1] == {"mes": "2026-07-01", "oni": 0.7}


def test_parse_sidra_pula_cabecalho_e_sem_dado():
    assert cc.parse_sidra(SIDRA) == [
        {"mes": "2026-07-01", "numero_indice": 7657.73},
        {"mes": "2026-08-01", "numero_indice": 7661.56},
    ]


# ── Semântica de status ──────────────────────────────────────────────────────

class _Resp:
    def __init__(self, json_=None, text=""):
        self._json, self.text = json_, text

    def raise_for_status(self):
        return None

    def json(self):
        return self._json


class _Http:
    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url, params=None):
        if url == cc.POWER_URL:
            return _Resp(POWER)
        if url == cc.ONI_URL:
            return _Resp(text=ONI)
        return _Resp(SIDRA)


class _Banco:
    def __init__(self, falhar_em=()):
        self.falhar_em, self.gravado, self.status = set(falhar_em), {}, []

    def table(self, nome):
        banco = self

        class _Q:
            def select(self, *a):
                return self

            def eq(self, *a):
                return self

            def upsert(self, dados, **k):
                self.dados = dados
                return self

            def execute(self):
                if nome in banco.falhar_em:
                    raise RuntimeError(f"relation {nome} does not exist (404)")
                if nome == "clima_regiao":
                    return types.SimpleNamespace(data=[{"id": "pr_colombo", "lat": -25.29, "lon": -49.23}])
                if nome == "clima_status":
                    banco.status.append(self.dados)
                else:
                    banco.gravado.setdefault(nome, []).extend(self.dados)
                return types.SimpleNamespace(data=None)
        return _Q()


@pytest.fixture
def coletor(monkeypatch):
    def _montar(banco):
        db = types.ModuleType("chat.db")
        db.get_supabase_client = lambda: banco
        monkeypatch.setitem(sys.modules, "chat.db", db)
        monkeypatch.setattr(cc.httpx, "Client", _Http)
        monkeypatch.setattr(cc.time, "sleep", lambda s: None)
        return cc.coletar_clima
    return _montar


def test_coleta_ok_grava_tres_tabelas(coletor):
    banco = _Banco()
    r = coletor(banco)()
    assert r["status"] == "ok" and r["data_max"] == "2026-10-02"
    assert len(banco.gravado["clima_diario"]) == 2
    assert len(banco.gravado["indice_enso"]) == 19 and len(banco.gravado["ipca_mensal"]) == 2
    assert banco.status[-1]["status"] == "ok"


def test_coleta_tabela_ausente_e_erro(coletor):
    banco = _Banco(falhar_em={"clima_diario"})
    r = coletor(banco)()
    assert r["status"] == "erro"                       # ONI e IPCA gravaram, clima não: erro
    assert any("clima_diario" in f for f in r["falhas"])


def test_coleta_sem_regioes_cadastradas_e_erro(coletor):
    banco = _Banco(falhar_em={"clima_regiao"})
    r = coletor(banco)(so_clima=True)
    assert r["status"] == "erro" and r["linhas_inseridas"] == 0


def test_argumentos():
    a = cc._args([])
    assert (a.inicio, a.fim, a.regiao, a.so_clima) == (None, None, None, False)
    a = cc._args(["--inicio", "2017-01-01", "--regiao", "pr_sjp", "--so-clima"])
    assert str(a.inicio) == "2017-01-01" and a.regiao == "pr_sjp" and a.so_clima
