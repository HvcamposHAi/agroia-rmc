"""
Testes unitários do coletor CEASA/PR por variedade (offline — sem rede nem Supabase).
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from chat.ceasa_pr_collector import parse_descricao, parse_html, _preco


@pytest.mark.parametrize("descricao,produto,variedade,embalagem,peso", [
    ("TANGERINA PONKAN MEDIA cx 20 kg", "tangerina", "ponkan media", "cx 20 kg", 20.0),
    ("TANGERINA MURKOTE GRAUDA  cx 20 kg", "tangerina", "murkote grauda", "cx 20 kg", 20.0),
    ("ABACAXI PEROLA GRAUDO un 1,8 kg", "abacaxi", "perola graudo", "un 1,8 kg", 1.8),
    ("TOMATE CEREJA BANDEJA bj 200 g", "tomate", "cereja bandeja", "bj 200 g", 0.2),
    ("MAMAO FORMOSA kg", "mamao", "formosa", "kg", 1.0),
    ("BANANA MAÇA PRIMEIRA cx 20 kg", "banana", "maca primeira", "cx 20 kg", 20.0),
    ("OVO BRANCO EXTRA cx c/ 30 dz", "ovo", "branco extra", "cx c/ 30 dz", None),
    ("JACA kg", "jaca", None, "kg", 1.0),
])
def test_parse_descricao(descricao, produto, variedade, embalagem, peso):
    p = parse_descricao(descricao)
    assert (p["produto"], p["variedade"], p["embalagem"], p["peso_kg"]) == (produto, variedade, embalagem, peso)


def test_preco():
    assert _preco("40,00") == 40.0
    assert _preco("1.250,50") == 1250.5
    assert _preco("-") is None
    assert _preco("") is None


HTML = """
<table>
<tr><td>Data</td><td>Unidade</td><td>Preço mais comum ( R$)</td></tr>
<tr><td></td><td></td><td>Curitiba</td><td>Maring&aacute;</td><td>Londrina</td>
    <td>Foz do Iguaçu</td><td>Cascavel</td></tr>
<tr><td><font>22/09/2026</font></td><td>TANGERINA PONKAN MEDIA  cx 20 kg</td>
    <td>40,00</td><td>-</td><td>-</td><td>-</td><td>62,00</td></tr>
<tr><td>22/09/2026</td><td>TANGERINA MONTEN/BERGAM cx 20 kg</td>
    <td>80,00</td><td>-</td><td>-</td><td>-</td><td>-</td></tr>
</table>
"""


def test_parse_html_uma_linha_por_unidade_com_preco():
    regs = parse_html(HTML.replace("Maring&aacute;", "Maringá"))
    assert [(r["unidade"], r["variedade"], r["preco"], r["preco_kg"]) for r in regs] == [
        ("CURITIBA", "ponkan media", 40.0, 2.0),
        ("CASCAVEL", "ponkan media", 62.0, 3.1),
        ("CURITIBA", "monten/bergam", 80.0, 4.0),
    ]
    assert regs[0]["data_coleta"] == "2026-09-22"
    assert regs[0]["descricao"] == "TANGERINA PONKAN MEDIA cx 20 kg"


def test_parse_html_sem_cabecalho_ignora_linhas():
    assert parse_html("<tr><td>22/09/2026</td><td>X cx 1 kg</td><td>1,00</td></tr>") == []
