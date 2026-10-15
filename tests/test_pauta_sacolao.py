"""Teste PONTUAL (offline) do pacote pauta do Sacolão / safra / projeção — plano v3.

Especificação de aceite: cada caso T-Pn do plano vira um teste aqui. Os módulos
ainda não existem; cada teste fica IGNORADO (importorskip) até a etapa que cria
o módulo, e passa a valer sozinho quando o módulo aparece. T-P0 é a exceção:
roda já e reproduz o defeito atual do coletor CEASA-PR (xfail estrito).

Contratos esperados (criados nas etapas do plano):
    chat/pauta_dados.py   PAUTA_175 (E2)
    chat/pauta.py         variacao_mensal, variacao_anual, indicador_anomalia_fao,
                          indice_sazonal, cobertura_subgrupo, acima_do_teto,
                          comparar_ceasas, PESO_TRIMESTRAL, PESO_ANUAL,
                          LIMIAR_MODERADO, LIMIAR_ANORMAL (E5)
    ml/avaliacao.py       mase, cobertura_intervalo (E6)
    ml/atributos.py       montar_atributos (E6)

Sem rede e sem credenciais:
    pytest tests/test_pauta_sacolao.py -v
"""

import math
from collections import Counter, defaultdict
from datetime import date, timedelta

import pytest


# ── Séries sintéticas (determinísticas) ──────────────────────────────────────

def _ruido(i: int) -> float:
    """Pseudo-ruído fixo em [-0,02; 0,02] (LCG), para o desvio-padrão não ser zero."""
    x = (1103515245 * (i + 7) + 12345) % 2**31
    return (x / 2**31 - 0.5) * 0.04


def _serie_mensal(anos: int, inflacao_anual: float = 0.0, ano0: int = 2019) -> dict:
    """{'AAAA-MM': preço} com sazonalidade fixa (pico em abril) e inflação opcional."""
    serie = {}
    for k in range(anos * 12):
        ano, mes = ano0 + k // 12, k % 12 + 1
        sazonal = 1 + 0.3 * math.cos(2 * math.pi * (mes - 4) / 12)
        serie[f"{ano:04d}-{mes:02d}"] = round(
            10 * sazonal * (1 + inflacao_anual) ** (k / 12) * (1 + _ruido(k)), 4)
    return serie


# ── T-P0 · coletor CEASA-PR com banco sem a tabela ───────────────────────────

_HTML_CEASA = (
    "<table><tr><td>Data</td><td>Unidade</td><td>Curitiba</td><td>Maringá</td>"
    "<td>Londrina</td><td>Foz do Iguaçu</td><td>Cascavel</td></tr>"
    "<tr><td>{data}</td><td>TOMATE LONGA VIDA cx 20 kg</td><td>80,00</td><td>-</td>"
    "<td>-</td><td>-</td><td>75,00</td></tr></table>"
)


class _RespostaFalsa:
    def __init__(self, html: str):
        self.content = html.encode("cp1252")

    def raise_for_status(self):
        return None


class _ClienteHttpFalso:
    """Substitui httpx.Client: o portal responde 200 com uma linha de cotação."""

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, *a, **k):
        return _RespostaFalsa("")

    def post(self, *a, **k):
        return _RespostaFalsa(_HTML_CEASA.format(data=date.today().strftime("%d/%m/%Y")))


class _SupabaseSemTabela:
    """Upsert em ceasa_pr_cotacoes falha como no PostgREST com tabela ausente (404)."""

    falhar = True

    def __init__(self):
        self.status = []

    def table(self, nome):
        banco = self

        class _Q:
            def upsert(self, dados, **k):
                self.dados = dados
                return self

            def execute(self):
                if nome == "ceasa_pr_cotacoes":
                    if banco.falhar:
                        raise RuntimeError("relation ceasa_pr_cotacoes does not exist (404)")
                    return None
                banco.status.append(self.dados)
                return None
        return _Q()


class _ClienteHttpVazio(_ClienteHttpFalso):
    """Portal responde 200, mas sem nenhuma linha de cotação (HTML mudou)."""

    def post(self, *a, **k):
        return _RespostaFalsa("<table><tr><td>Nenhum registro</td></tr></table>")


def _coletor(monkeypatch, sb, cliente=_ClienteHttpFalso):
    import sys
    import types

    import chat.ceasa_pr_collector as col

    falso_db = types.ModuleType("chat.db")
    falso_db.get_supabase_client = lambda: sb
    monkeypatch.setitem(sys.modules, "chat.db", falso_db)
    monkeypatch.setattr(col.httpx, "Client", cliente)
    monkeypatch.setattr(col.time, "sleep", lambda s: None)
    return col


def test_tp0_coletor_ceasa_pr_gravacao_falha_e_erro(monkeypatch):
    sb = _SupabaseSemTabela()
    r = _coletor(monkeypatch, sb).coletar_ceasa_pr(1)
    assert r["linhas_inseridas"] == 0
    assert r["status"] == "erro", f"coleta 'verde' sem gravar nada: {r}"
    assert r["data_max"] is None                      # nada gravado → sem data máxima
    assert sb.status and sb.status[-1]["status"] == "erro"


def test_tp0_coletor_ceasa_pr_gravou_e_ok(monkeypatch):
    sb = _SupabaseSemTabela()
    sb.falhar = False
    r = _coletor(monkeypatch, sb).coletar_ceasa_pr(1)
    assert r["status"] == "ok" and r["linhas_inseridas"] == 2   # Curitiba e Cascavel
    assert r["data_max"] == date.today().isoformat()
    assert sb.status[-1]["status"] == "ok"


def test_tp0_coletor_ceasa_pr_portal_sem_cotacoes_e_erro(monkeypatch):
    sb = _SupabaseSemTabela()
    sb.falhar = False
    r = _coletor(monkeypatch, sb, _ClienteHttpVazio).coletar_ceasa_pr(7)
    assert r["status"] == "erro"
    assert any("HTML" in f for f in r["falhas"])


class _ClienteHttpDiaRuim(_ClienteHttpFalso):
    """Janela que contém o dia ruim dá HTTP 500 (como 10/10/2016 no portal real)."""

    ruim = date.today() - timedelta(days=1)
    pedidos: list = []

    def post(self, url, data=None, **k):
        from datetime import datetime as dt
        ini = dt.strptime(data["dataIni"], "%d/%m/%Y").date()
        fim = dt.strptime(data["dataFim"], "%d/%m/%Y").date()
        self.pedidos.append((ini, fim))
        if ini <= self.ruim <= fim:
            import httpx
            raise httpx.HTTPStatusError("500 Internal Server Error", request=None, response=None)
        return _RespostaFalsa(_HTML_CEASA.format(data=ini.strftime("%d/%m/%Y")))


def test_tp0_coletor_ceasa_pr_isola_dia_com_erro_500(monkeypatch):
    sb = _SupabaseSemTabela()
    sb.falhar = False
    _ClienteHttpDiaRuim.pedidos = []
    r = _coletor(monkeypatch, sb, _ClienteHttpDiaRuim).coletar_ceasa_pr(3)   # 1 janela de 3 dias
    assert len(_ClienteHttpDiaRuim.pedidos) == 4          # janela + 3 dias isolados
    assert r["linhas_inseridas"] == 4                     # 2 dias bons × 2 unidades
    assert r["status"] == "ok"
    assert [f[:10] for f in r["falhas"]] == [_ClienteHttpDiaRuim.ruim.isoformat()]


def test_tp0_coletor_ceasa_pr_argumentos():
    from chat.ceasa_pr_collector import _args
    a = _args([])
    assert (a.dias, a.inicio, a.fim) == (7, None, None)     # sem argumentos: últimos 7 dias
    assert _args(["90"]).dias == 90
    a = _args(["--inicio", "2021-01-01", "--fim", "2021-03-31"])
    assert (a.inicio, a.fim) == (date(2021, 1, 1), date(2021, 3, 31))


# ── T-P1 · cadastro fiel ao Anexo I da Portaria nº 175 ───────────────────────

def test_tp1_cadastro_pauta_175():
    dados = pytest.importorskip("chat.pauta_dados", reason="E2 pendente")
    linhas = dados.PAUTA_175
    assert {l["ato"] for l in linhas} == {"Portaria 175"}

    por_estacao = defaultdict(list)
    for l in linhas:
        por_estacao[l["estacao"]].append(l)
    assert len(por_estacao) == 2, "duas estações no Anexo I"
    assert sum(len(v) for v in por_estacao.values()) == 86

    minimos_esperados = [[5, 2, 10, 6, 3], [3, 6, 3, 12, 2]]
    for estacao, esperado in zip(sorted(por_estacao), minimos_esperados):
        ls = por_estacao[estacao]
        assert len(ls) == 43, f"{estacao}: 43 espécies"
        subgrupos = {}
        for l in ls:
            subgrupos.setdefault((l["ordem_subgrupo"], l["subgrupo"]), l["minimo"])
        assert len(subgrupos) == 5, f"{estacao}: 5 subgrupos"
        minimos = [m for _, m in sorted(subgrupos.items())]
        assert minimos == esperado
        assert sum(minimos) == 26
        # cada subgrupo tem ao menos tantas espécies quanto o seu mínimo
        n = Counter((l["ordem_subgrupo"], l["subgrupo"]) for l in ls)
        for chave, minimo in subgrupos.items():
            assert n[chave] >= minimo, chave
        # espécie não se repete dentro da estação (cítricas distintas por variedade)
        nomes = [(l["especie"], l.get("variedade")) for l in ls]
        assert len(nomes) == len(set(nomes)), f"{estacao}: espécie repetida"


# ── T-P2 · variação mensal e anual ───────────────────────────────────────────

def test_tp2_variacao_mensal_e_anual():
    pauta = pytest.importorskip("chat.pauta", reason="E5 pendente")
    serie = {"2025-10": 4.0, "2026-09": 4.0, "2026-10": 5.0, "2026-11": 3.75}
    assert pauta.variacao_mensal(serie, "2026-10") == pytest.approx(25.0)
    assert pauta.variacao_mensal(serie, "2026-11") == pytest.approx(-25.0)
    assert pauta.variacao_anual(serie, "2026-10") == pytest.approx(25.0)
    assert pauta.variacao_mensal(serie, "2025-10") is None   # sem mês anterior
    assert pauta.variacao_anual(serie, "2026-09") is None    # sem mesmo mês do ano anterior


# ── T-P3 · alerta de anomalia (método FAO, ODS 2.c.1) ────────────────────────

def test_tp3_anomalia_fao_parametros():
    pauta = pytest.importorskip("chat.pauta", reason="E5 pendente")
    assert pauta.PESO_TRIMESTRAL == pytest.approx(0.4)
    assert pauta.PESO_ANUAL == pytest.approx(0.6)
    assert pauta.LIMIAR_MODERADO == pytest.approx(0.5)
    assert pauta.LIMIAR_ANORMAL == pytest.approx(1.0)


def test_tp3_alta_de_40pct_no_semestre_e_anormal():
    pauta = pytest.importorskip("chat.pauta", reason="E5 pendente")
    serie = _serie_mensal(anos=7)                     # 2019-01 .. 2025-12
    meses = sorted(serie)
    for i, mes in enumerate(meses[-6:], start=1):     # rampa até +40% no último semestre
        serie[mes] = round(serie[mes] * (1 + 0.4 * i / 6), 4)
    r = pauta.indicador_anomalia_fao(serie, meses[-1])
    assert r["disponivel"] is True
    assert r["indice"] >= 1.0
    assert r["classe"] == "anormalmente_alto"


def test_tp3_menos_de_5_anos_nao_calcula():
    pauta = pytest.importorskip("chat.pauta", reason="E5 pendente")
    serie = _serie_mensal(anos=4)
    r = pauta.indicador_anomalia_fao(serie, max(serie))
    assert r["disponivel"] is False
    assert r["indice"] is None
    assert r["motivo"]


# ── T-P4 · cobertura dos mínimos do subgrupo ─────────────────────────────────

def test_tp4_cobertura_minimos():
    pauta = pytest.importorskip("chat.pauta", reason="E5 pendente")
    folhosas = [2.5, 3.0, None, 1.8, None, 2.2]       # 4 de 6 com preço
    r = pauta.cobertura_subgrupo(folhosas, minimo=5)
    assert r == {"com_preco": 4, "minimo": 5, "atende": False}
    assert pauta.cobertura_subgrupo(folhosas, minimo=4)["atende"] is True


# ── T-P5 · acima do teto (Art. 7º) ───────────────────────────────────────────

def test_tp5_acima_do_teto():
    pauta = pytest.importorskip("chat.pauta", reason="E5 pendente")
    itens = [
        {"especie": "TOMATE", "subgrupo": "Frutos", "preco": 4.50},
        {"especie": "ABOBRINHA", "subgrupo": "Frutos", "preco": 3.99},   # igual ao teto: não excede
        {"especie": "LIMÃO TAHITI", "subgrupo": "Frutas", "preco": 4.20},
        {"especie": "BANANA", "subgrupo": "Frutas", "preco": 2.10},
        {"especie": "ALFACE", "subgrupo": "Folhosas", "preco": None},     # sem preço: não entra
    ]
    r = pauta.acima_do_teto(itens, teto=3.99)
    assert [(x["especie"], x["subgrupo"]) for x in r] == [
        ("TOMATE", "Frutos"), ("LIMÃO TAHITI", "Frutas")]


# ── T-P6 · índice sazonal ────────────────────────────────────────────────────

def test_tp6_indice_sazonal_ignora_inflacao():
    pauta = pytest.importorskip("chat.pauta", reason="E5 pendente")
    sem = pauta.indice_sazonal(_serie_mensal(anos=5))
    com = pauta.indice_sazonal(_serie_mensal(anos=5, inflacao_anual=0.10))
    assert sorted(sem) == list(range(1, 13))
    for mes in range(1, 13):
        assert com[mes]["indice"] == pytest.approx(sem[mes]["indice"], abs=0.05), mes
    assert sem[4]["indice"] > 1 > sem[10]["indice"]   # pico em abril, vale em outubro


def test_tp6_mes_com_menos_de_3_anos_pouco_confiavel():
    pauta = pytest.importorskip("chat.pauta", reason="E5 pendente")
    serie = _serie_mensal(anos=4)
    for ano in (2019, 2020):                           # março só em 2021 e 2022
        del serie[f"{ano}-03"]
    r = pauta.indice_sazonal(serie)
    assert r[3]["anos"] == 2 and r[3]["confiavel"] is False
    assert r[4]["anos"] == 4 and r[4]["confiavel"] is True


# ── T-P7 · comparação entre CEASAs ───────────────────────────────────────────

def test_tp7_comparar_ceasas():
    pauta = pytest.importorskip("chat.pauta", reason="E5 pendente")
    hoje = date(2026, 10, 15)
    cot = []
    for d in range(0, 30, 2):
        dia = (hoje - timedelta(days=d)).isoformat()
        cot.append({"ceasa": "CURITIBA", "unidade": "UN", "data": dia, "preco": 3.33})
        cot.append({"ceasa": "CASCAVEL", "unidade": "UN", "data": dia, "preco": 10.0})
        cot.append({"ceasa": "SAO PAULO", "unidade": "KG", "data": dia, "preco": 7.0})
    cot.append({"ceasa": "MARINGA", "unidade": "UN", "data": "2025-07-29", "preco": 4.0})
    r = pauta.comparar_ceasas(cot, hoje=hoje, unidade="UN")
    assert [x["ceasa"] for x in r["ranking"]] == ["CASCAVEL", "CURITIBA"]   # decrescente
    assert r["ranking"][0]["mediana"] == pytest.approx(10.0)
    motivos = {x["ceasa"]: x["motivo"] for x in r["excluidas"]}
    assert set(motivos) == {"MARINGA", "SAO PAULO"}
    assert "frete" in r["aviso_frete"].lower()


# ── T-P8 · métricas da projeção ──────────────────────────────────────────────

def test_tp8_mase_e_cobertura():
    av = pytest.importorskip("ml.avaliacao", reason="E6 pendente")
    m = 4
    hist = [10 + 2 * (t // m) + (t % m) for t in range(5 * m)]   # ingênuo sazonal erra 2 sempre
    real = [20.0, 21.0, 22.0, 23.0]
    assert av.mase(real, real, hist, m=m) == pytest.approx(0.0)
    assert av.mase(real, [r + 2 for r in real], hist, m=m) == pytest.approx(1.0)
    assert av.mase(real, [r - 1 for r in real], hist, m=m) == pytest.approx(0.5)

    y = list(range(10))
    lo = [v - 1 for v in y]
    hi = [v + 1 for v in y]
    hi[0] = y[0] - 0.5                                  # 2 fora da faixa
    lo[9] = y[9] + 0.5
    assert av.cobertura_intervalo(y, lo, hi) == pytest.approx(0.8)


def test_tp8_perda_quantil_e_diebold_mariano():
    av = pytest.importorskip("ml.avaliacao", reason="E6 pendente")
    assert av.perda_quantil([10], [8], 0.9) == pytest.approx(1.8)    # subestimou: 0,9 × 2
    assert av.perda_quantil([10], [12], 0.9) == pytest.approx(0.2)   # superestimou: 0,1 × 2
    ref = [3.0 + _ruido(i) * 10 for i in range(40)]                  # erros da referência
    melhor = [e / 3 for e in ref]
    r = av.diebold_mariano(melhor, ref)
    assert r["p_valor"] < 0.05 and r["estatistica"] < 0
    assert av.diebold_mariano(ref, melhor)["p_valor"] > 0.95         # pior não passa


# ── T-P9 · sem vazamento temporal ────────────────────────────────────────────

def test_tp9_atributos_nao_veem_o_futuro():
    pd = pytest.importorskip("pandas")
    at = pytest.importorskip("ml.atributos", reason="E6 pendente")
    idx = pd.date_range("2022-06-06", periods=230, freq="W-MON")
    serie = pd.Series([10 + (i % 52) / 10 for i in range(230)], index=idx)
    origem = idx[180]
    base = at.montar_atributos(serie, origem)
    alterada = serie.copy()
    alterada[alterada.index > origem] *= 5               # muda só o futuro
    assert at.montar_atributos(alterada, origem) == base
    mexida = serie.copy()
    mexida[mexida.index == origem] *= 5                  # controle: o passado muda o atributo
    assert at.montar_atributos(mexida, origem) != base
