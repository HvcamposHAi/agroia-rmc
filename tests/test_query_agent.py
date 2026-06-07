"""Testes pontuais (unit) do Query Agent — síncronos, offline (sem DB)."""

from datetime import datetime

from chat.query_agent import (
    _detectar_intencao,
    _extrair_filtros,
    _montar_hint,
)


class TestDeteccaoIntencao:
    def test_intencao_preco(self):
        assert _detectar_intencao("qual o preço da alface hoje") == "preco"

    def test_intencao_licitacao(self):
        assert _detectar_intencao("quanto de cenoura curitiba comprou") == "licitacao"

    def test_intencao_edital(self):
        assert _detectar_intencao("qual edital de chamamento foi publicado") == "edital"

    def test_intencao_geral_fallback(self):
        assert _detectar_intencao("olá bom dia tudo bem") == "geral"


class TestFiltrosImplicitos:
    def test_filtro_ano_atual(self):
        filtros = _extrair_filtros("compras deste ano", [])
        assert filtros.get("ano") == datetime.now().year

    def test_filtro_ano_explicito(self):
        filtros = _extrair_filtros("compras de alface em 2024", [])
        assert filtros.get("ano") == 2024

    def test_filtro_ano_passado(self):
        filtros = _extrair_filtros("o que compraram no ano passado", [])
        assert filtros.get("ano") == datetime.now().year - 1

    def test_filtro_canal_pnae(self):
        termos = [{"original": "merenda escolar", "canonico": "PNAE", "coluna": "canal"}]
        filtros = _extrair_filtros("merenda escolar comprou couve", termos)
        assert filtros.get("canal") == "PNAE"

    def test_filtro_canal_armazem(self):
        termos = [{"original": "armazém da família", "canonico": "ARMAZEM_FAMILIA", "coluna": "canal"}]
        filtros = _extrair_filtros("armazém da família comprou banana", termos)
        assert filtros.get("canal") == "ARMAZEM_FAMILIA"

    def test_sem_filtro_quando_ausente(self):
        assert _extrair_filtros("me fale sobre alface", []) == {}


class TestMontarHint:
    def test_hint_com_cultura(self):
        termos = [{"original": "alface", "canonico": "ALFACE", "coluna": "cultura"}]
        h = _montar_hint(termos, {}, "licitacao")
        assert "ALFACE" in h
        assert "intenção=licitacao" in h

    def test_hint_com_canal_e_ano(self):
        termos = [{"original": "merenda", "canonico": "PNAE", "coluna": "canal"}]
        h = _montar_hint(termos, {"canal": "PNAE", "ano": 2025}, "licitacao")
        assert "canal=PNAE" in h
        assert "ano=2025" in h

    def test_hint_vazio_sem_termos(self):
        assert _montar_hint([], {}, "geral") == ""
