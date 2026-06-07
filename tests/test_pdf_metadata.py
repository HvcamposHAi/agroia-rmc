"""Testes pontuais dos helpers de metadados de PDF — puros, offline (sem DB)."""

from ingestion.pdf_metadata import (
    identificar_culturas_no_chunk,
    inferir_ano,
    inferir_canal,
    inferir_tipo_documento,
)

TEXTO_EDITAL = """
PREFEITURA MUNICIPAL DE CURITIBA
CHAMAMENTO PÚBLICO Nº 001/2025 - PROGRAMA NACIONAL DE ALIMENTAÇÃO ESCOLAR (PNAE)
Data de abertura: 15/03/2025

ITEM 1 - ALFACE AMERICANA - 1.800 kg
ITEM 2 - COUVE MANTEIGA - 1.500 kg
ITEM 3 - CENOURA - 2.000 kg
"""


class TestCulturas:
    def test_identifica_alface(self):
        culturas = identificar_culturas_no_chunk("ALFACE AMERICANA 1800 kg")
        assert "ALFACE" in culturas

    def test_identifica_multiplas(self):
        culturas = identificar_culturas_no_chunk("CENOURA e BETERRABA para entrega")
        assert "CENOURA" in culturas and "BETERRABA" in culturas

    def test_sem_cultura(self):
        assert identificar_culturas_no_chunk("documento administrativo geral") == []

    def test_chunk_vazio(self):
        assert identificar_culturas_no_chunk("") == []


class TestAno:
    def test_ano_via_data(self):
        assert inferir_ano(TEXTO_EDITAL) == 2025

    def test_ano_via_token(self):
        assert inferir_ano("Edital referente ao exercício de 2023.") == 2023

    def test_sem_ano(self):
        assert inferir_ano("documento sem datas") is None


class TestCanal:
    def test_canal_armazem(self):
        assert inferir_canal("Aquisição para o Armazém da Família") == "ARMAZEM_FAMILIA"

    def test_canal_banco_alimentos(self):
        assert inferir_canal("destinado ao Banco de Alimentos municipal") == "BANCO_ALIMENTOS"

    def test_canal_mesa_solidaria(self):
        assert inferir_canal("programa Mesa Solidária") == "MESA_SOLIDARIA"

    def test_pnae_fora_do_escopo_retorna_none(self):
        # PNAE/PAA não são canais deste dataset (SMSAN/FAAC) → não inferidos
        assert inferir_canal(TEXTO_EDITAL) is None

    def test_sem_canal(self):
        assert inferir_canal("texto genérico") is None


class TestTipoDocumento:
    def test_edital(self):
        assert inferir_tipo_documento("chamamento_001.pdf", TEXTO_EDITAL) == "edital"

    def test_documento_geral(self):
        assert inferir_tipo_documento("nota.pdf", "conteúdo qualquer") == "documento_geral"
