"""Testes offline do coletor do Portal da Transparência (coleta_transparencia.py).
Fixtures = páginas reais salvas em 23/09/2026 (tests/fixtures/transparencia_*.html)."""
from pathlib import Path

import pytest

import coleta_transparencia as C
from classificacao_licitacao import classificar_canal, is_af

FIX = Path(__file__).parent / "fixtures"


def _ler(nome):
    return (FIX / nome).read_text(encoding="utf-8", errors="replace")


class TestUtilidades:
    @pytest.mark.parametrize("entrada,esperado", [
        ("PE 83 /2026", "PE 83/2026"), ("PE 1/2026", "PE 1/2026"), ("  IN  5 / 2025 ", "IN 5/2025"),
    ])
    def test_normalizar_processo(self, entrada, esperado):
        assert C.normalizar_processo(entrada) == esperado

    def test_chave_db_casa_com_o_corpus(self):
        assert C.chave_db("PE 83 /2026") == "PE 83/2026 - SMSAN/FAAC"

    @pytest.mark.parametrize("txt,val", [("R$ 104.250,00", 104250.0), ("20.000", 20000.0),
                                         ("R$ 0,00", 0.0), ("", 0.0), ("41.400,00", 41400.0)])
    def test_parse_brl(self, txt, val):
        assert C.parse_brl(txt) == val

    def test_formatar_doc(self):
        assert C.formatar_doc("76125244000162") == "76.125.244/0001-62"


class TestGrade:
    def test_linhas_grade(self):
        linhas, _ = C.PortalTransparencia.linhas_grade(_ler("transparencia_grade_faac_2026_p1.html"))
        assert len(linhas) == 15
        pe1 = linhas[0]
        assert pe1["processo"] == "PE 1/2026"
        assert pe1["situacao"] == "Empenhado"
        assert pe1["alvo"].endswith("lnbVerDetalhes")
        assert pe1["objeto"].startswith("AQUISIÇÃO DE MAIONESE")

    def _soup_pager(self, links):
        from bs4 import BeautifulSoup
        html = "".join(f"<a href=\"javascript:__doPostBack('ctl00$cphMasterPrincipal$ucPaginadorBaixo${i}_pg{pg}','')\">{pg}</a>"
                       for i, pg in links)
        return BeautifulSoup(html, "lxml")

    def _alvo(self, links, pagina_atual, monkeypatch):
        p = C.PortalTransparencia()
        chamado = {}
        monkeypatch.setattr(p, "_postback", lambda alvo: (chamado.setdefault("alvo", alvo), ({}, None))[1])
        p.proxima_pagina(self._soup_pager(links), pagina_atual)
        return chamado.get("alvo")

    def test_pager_usa_numero_da_pagina_e_nao_o_indice(self, monkeypatch):
        # Na pág. 11 o paginador é "... 4..10 [11] 12 13": o link da 12 tem índice 10.
        links = [(1, "..."), (2, "4"), (3, "5"), (8, "10"), (10, "12"), (11, "13")]
        assert self._alvo(links, 11, monkeypatch).endswith("$10_pg12")

    def test_pager_segue_reticencias_da_direita(self, monkeypatch):
        links = [(2, "2"), (3, "3"), (10, "10"), (11, "...")]  # pág. 11 está atrás do '...'
        assert self._alvo(links, 10, monkeypatch).endswith("$11_pg...")

    def test_pager_fim(self, monkeypatch):
        links = [(1, "..."), (2, "11"), (3, "12")]
        assert self._alvo(links, 12, monkeypatch) is None  # '...' à esquerda não avança


class TestDetalhe:
    def test_detalhe_concluido(self):
        d = C.parse_detalhe(_ler("transparencia_detalhe_pe1_2026.html"))
        assert d["processo"] == "PE 1/2026"
        assert d["setor"] == "FAAC"
        assert d["setor_edital"] == "SMSAN/FAAC"
        assert d["situacao"] == "Empenhado"
        assert d["objeto"].startswith("AQUISIÇÃO DE MAIONESE")
        assert d["total_forn_participantes"] == len(d["participantes"]) == 18
        assert len(d["itens"]) == 7
        it = d["itens"][0]
        assert it["seq"] == 1 and it["descricao"].startswith("MAIONESE")
        assert it["qt"] == 25000 and it["v_unit"] == 4.17 and it["v_total"] == 104250.0
        assert it["vencedor_doc"] == "56954281000176"
        assert len(d["empenhos"]) == 18
        e = d["empenhos"][0]
        assert e["nr"] == "664" and e["valor"] == 41400.0 and e["ano"] == 2026
        assert e["doc"] == "48429239000108"
        assert all(a["url"].startswith("https://") for a in d["arquivos"])

    def test_detalhe_em_montagem_sem_participantes(self):
        d = C.parse_detalhe(_ler("transparencia_detalhe_pe83_2026.html"))
        assert d["processo"] == "PE 83/2026"
        assert d["dt_abertura"] == "2026-09-29"
        assert d["situacao"] == "Processo de Compra Montado"
        assert d["participantes"] == [] and d["empenhos"] == []
        assert [i["seq"] for i in d["itens"]] == [1, 2, 3]
        assert d["itens"][0]["vencedor_doc"] == ""

    def test_detalhe_invalido_levanta(self):
        with pytest.raises(C.PortalIndisponivel):
            C.parse_detalhe("<html><body>Erro</body></html>")


class TestDecisao:
    class _Banco:
        def __init__(self, com_itens=(), legado=()):
            self.com_itens, self.itens_legado = set(com_itens), set(legado)

    def _linha(self, sit="Empenhado"):
        return {"situacao": sit}

    def test_nova(self):
        assert C.precisa_detalhe(self._linha(), None, self._Banco()) == "nova"

    def test_enriquecer_legado_uma_vez(self):
        lic = {"id": 1, "situacao": "Concluído", "url_detalhe": None}
        assert "enriquecer" in C.precisa_detalhe(self._linha(), lic, self._Banco({1}, {1}))

    def test_legado_ja_enriquecido_nao_repete_por_vocabulario(self):
        # "Concluído" (portal antigo) × "Empenhado" (Transparência) NÃO é mudança.
        lic = {"id": 1, "situacao": "Concluído", "url_detalhe": "https://x"}
        assert C.precisa_detalhe(self._linha(), lic, self._Banco({1}, {1})) is None

    def test_em_andamento_sempre_reconsulta(self):
        lic = {"id": 2, "situacao": "Parcialmente Empenhado", "url_detalhe": "https://x"}
        assert C.precisa_detalhe(self._linha("Parcialmente Empenhado"), lic, self._Banco({2})).startswith("em andamento")

    def test_mudanca_de_situacao_nesta_fonte(self):
        lic = {"id": 3, "situacao": "Confirmado Vencedor", "url_detalhe": "https://x"}
        assert "situação" in C.precisa_detalhe(self._linha("Empenhado"), lic, self._Banco({3}))

    def test_sem_mudanca_pula(self):
        lic = {"id": 3, "situacao": "Empenhado", "url_detalhe": "https://x"}
        assert C.precisa_detalhe(self._linha("Empenhado"), lic, self._Banco({3})) is None


class TestAnos:
    def test_padrao_ano_anterior_e_corrente(self):
        from datetime import date
        a = date.today().year
        assert C.parse_anos(None) == [a - 1, a]

    def test_intervalos(self):
        assert C.parse_anos("2019-2021,2026") == [2019, 2020, 2021, 2026]


def test_classificacao_licitacao_regras_da_etapa1():
    obj = "AQUISIÇÃO DE PANETONES, PARA O PROGRAMA ARMAZÉM DA FAMÍLIA"
    assert classificar_canal(obj.lower().upper()) == "ARMAZEM_FAMILIA"
    assert is_af(obj) is True
    assert classificar_canal("Prestação de serviços de cartão alimentação") == "OUTRO"
