"""
Testes unitários da integração PROHORT (offline — sem rede nem Supabase).
Cobrem normalização de produtos, parsing numérico/data e mapeamento de CEASA.
"""
import sys
import os
import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import MagicMock

import pandas as pd
import pytest

from chat.prohort_normalizer import normalizar_produto
from chat.prohort_collector import _to_float, _registrar_status, CEASA_ALIAS, CEASAS_ALVO


# ─── normalizar_produto ──────────────────────────────────────────────────────

@pytest.mark.parametrize("entrada,esperado", [
    ("TOMATE ITALIANO", "tomate"),
    ("TOMATE SALADA", "tomate"),
    ("AIPIM", "mandioca"),
    ("MANDIOCA", "mandioca"),
    ("ALFACE CRESPA", "alface"),
    ("  TOMATE  ", "tomate"),          # strip
])
def test_normalizar_produto_conhecido(entrada, esperado):
    assert normalizar_produto(entrada) == esperado


def test_normalizar_produto_fallback():
    # produto fora do dicionário cai no nome em minúsculas (não é descartado)
    assert normalizar_produto("PRODUTO DESCONHECIDO XPTO") == "produto desconhecido xpto"


def test_normalizar_produto_vazio():
    assert normalizar_produto("") == ""


# ─── _to_float ───────────────────────────────────────────────────────────────

def test_to_float_ponto():
    assert _to_float("4.5") == 4.5
    assert _to_float("4.25") == 4.25


def test_to_float_virgula_fallback():
    # robustez caso a CONAB troque o separador
    assert _to_float("3,50") == 3.5


def test_to_float_invalido():
    assert _to_float("") is None
    assert _to_float("nan") is None
    assert _to_float(None) is None
    assert _to_float("abc") is None


# ─── CEASA_ALIAS ─────────────────────────────────────────────────────────────

def test_ceasa_alias():
    assert CEASA_ALIAS["CEASA/PR - CURITIBA"] == "CURITIBA"
    assert CEASA_ALIAS["CEASA/PR - MARINGA"] == "MARINGA"
    assert CEASA_ALIAS["CEAGESP - SAO PAULO"] == "SAO PAULO"


def test_ceasas_alvo_consistente():
    # toda chave alvo precisa ter alias; Londrina não existe no PROHORT
    assert CEASAS_ALVO == set(CEASA_ALIAS.keys())
    assert not any("LONDRINA" in k for k in CEASAS_ALVO)


# ─── Parsing de uma linha no formato real do ProhortDiario.txt ───────────────

HEADER = ("municipio_ceasa;cod_ibge_municipio;uf_ceasa;dsc_ceasa;dsc_produto;"
          "sig_unidade_medida;data_preco;preco_diario")
LINHA = ("CURITIBA-PR;4106902;PR;CEASA/PR - CURITIBA;TOMATE ITALIANO;KG;"
         "2026/06/01 00:00:00.000;4.5")


def test_parse_linha_real():
    import io
    df = pd.read_csv(io.StringIO(HEADER + "\n" + LINHA), sep=";", dtype=str)
    df.columns = [c.strip() for c in df.columns]
    row = df.iloc[0]
    # mapeamento de CEASA
    ceasa_key = CEASA_ALIAS.get(row["dsc_ceasa"].strip().upper())
    assert ceasa_key == "CURITIBA"
    # data
    d = pd.to_datetime(row["data_preco"], format="%Y/%m/%d %H:%M:%S.%f")
    assert d.date() == datetime.date(2026, 6, 1)
    # preço e produto
    assert _to_float(row["preco_diario"]) == 4.5
    assert normalizar_produto(row["dsc_produto"]) == "tomate"


# ─── _registrar_status (gravação da "última atualização" em prohort_status) ──

def _mock_supabase():
    """Mock encadeável: supabase.table(...).upsert(...).execute()."""
    sb = MagicMock()
    chain = MagicMock()
    sb.table.return_value = chain
    chain.upsert.return_value = chain
    chain.execute.return_value = MagicMock(data=[{"id": 1}])
    return sb, chain


def test_registrar_status_payload():
    sb, chain = _mock_supabase()
    _registrar_status(sb, finalizado_em="2026-06-08T09:30:00+00:00",
                      data_max="2026-06-06", data_min="2026-05-08",
                      linhas=1234, modo="diario", status="ok")
    sb.table.assert_called_once_with("prohort_status")
    payload, kwargs = chain.upsert.call_args.args, chain.upsert.call_args.kwargs
    enviado = payload[0]
    assert enviado["id"] == 1
    assert enviado["finalizado_em"] == "2026-06-08T09:30:00+00:00"
    assert enviado["data_max"] == "2026-06-06"
    assert enviado["data_min"] == "2026-05-08"
    assert enviado["linhas_inseridas"] == 1234
    assert enviado["modo"] == "diario"
    assert enviado["status"] == "ok"
    assert kwargs.get("on_conflict") == "id"     # mantém singleton id=1
    chain.execute.assert_called_once()


def test_registrar_status_nao_propaga_erro():
    # Best-effort: falha ao gravar status NUNCA pode derrubar a ingestão de preços.
    sb = MagicMock()
    sb.table.side_effect = RuntimeError("supabase indisponível")
    # não deve levantar
    _registrar_status(sb, finalizado_em="2026-06-08T09:30:00+00:00",
                      data_max=None, data_min=None, linhas=0, modo="diario",
                      status="ok")


def test_registrar_status_erro_download_datas_nulas():
    # Caminho de erro de download: sem datas vistas, status="erro".
    sb, chain = _mock_supabase()
    _registrar_status(sb, finalizado_em="2026-06-08T09:30:00+00:00",
                      data_max=None, data_min=None, linhas=0, modo="diario",
                      status="erro", erro="download:timeout")
    enviado = chain.upsert.call_args.args[0]
    assert enviado["status"] == "erro"
    assert enviado["data_max"] is None
    assert enviado["erro"] == "download:timeout"
