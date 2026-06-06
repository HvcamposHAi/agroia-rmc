"""
Teste pontual da carga em lote de ofertas (planilha do produtor).

Foco: a orquestração de `processar_planilha_ofertas` e os utilitários de parsing,
SEM tocar o banco — `registrar_oferta_produtor` é substituído por um stub que apenas
captura as chamadas e simula sucesso/erro por linha.

Rodar:  pytest api/test_upload_ofertas.py -v
"""
import chat.tools as tools
from chat.tools import (
    _to_float, _norm_cabecalho, processar_planilha_ofertas,
    PLANILHA_MAX_LINHAS,
)


# ─── Utilitários de parsing ────────────────────────────────────────────────

def test_to_float_formatos_br():
    assert _to_float("4,00") == 4.0
    assert _to_float("R$ 4,50") == 4.5
    assert _to_float("1.234,56") == 1234.56   # milhar + decimal BR
    assert _to_float("200") == 200.0
    assert _to_float("") is None
    assert _to_float(None) is None
    assert _to_float("nan") is None
    assert _to_float("-") is None


def test_norm_cabecalho_remove_acento_e_caixa():
    assert _norm_cabecalho("CPF/CNPJ".replace("/", "_")) == "cpf_cnpj"
    assert _norm_cabecalho("Descrição") == "descricao"
    assert _norm_cabecalho("Preço Pretendido") == "preco_pretendido"
    assert _norm_cabecalho("  Município ") == "municipio"


# ─── Orquestração em lote (registrar_oferta_produtor mockado) ──────────────

def _stub_ok(monkeypatch):
    chamadas = []

    def fake(**kwargs):
        chamadas.append(kwargs)
        return {"ok": True, "oferta_id": len(chamadas), "produtor_id": 1, "resumo": "x"}

    monkeypatch.setattr(tools, "registrar_oferta_produtor", fake)
    return chamadas


def test_planilha_valida_grava_todas_com_origem_planilha(monkeypatch):
    chamadas = _stub_ok(monkeypatch)
    linhas = [
        {"nome": "João", "cpf_cnpj": "111.444.777-35", "descricao": "Alface", "quantidade": "200", "unidade": "kg"},
        {"nome": "Maria", "cpf_cnpj": "12345678000195", "descricao": "Tomate", "quantidade": "500", "preco_pretendido": "3,50"},
    ]
    res = processar_planilha_ofertas(linhas)
    assert res["total"] == 2
    assert res["inseridas"] == 2
    assert res["erros"] == []
    # origem PLANILHA propagada e valores convertidos
    assert all(c["origem"] == "PLANILHA" for c in chamadas)
    assert chamadas[0]["quantidade"] == 200.0
    assert chamadas[1]["preco_pretendido"] == 3.5


def test_cabecalho_com_acento_e_caixa_e_normalizado(monkeypatch):
    chamadas = _stub_ok(monkeypatch)
    linhas = [{"Nome": "João", "CPF_CNPJ": "111.444.777-35", "Descrição": "Cenoura", "Quantidade": "100"}]
    res = processar_planilha_ofertas(linhas)
    assert res["inseridas"] == 1
    assert chamadas[0]["nome"] == "João"
    assert chamadas[0]["descricao"] == "Cenoura"
    assert chamadas[0]["quantidade"] == 100.0


def test_linha_invalida_nao_interrompe_as_demais(monkeypatch):
    # Stub: rejeita quando o CPF é o inválido conhecido, aceita o resto
    def fake(**kwargs):
        if kwargs.get("cpf_cnpj", "").replace(".", "").replace("-", "") == "00000000000":
            return {"ok": False, "erro": "CPF/CNPJ inválido."}
        return {"ok": True}

    monkeypatch.setattr(tools, "registrar_oferta_produtor", fake)
    linhas = [
        {"nome": "Bom", "cpf_cnpj": "111.444.777-35", "descricao": "Alface", "quantidade": "10"},
        {"nome": "Ruim", "cpf_cnpj": "000.000.000-00", "descricao": "Tomate", "quantidade": "10"},
        {"nome": "Bom2", "cpf_cnpj": "12345678000195", "descricao": "Cenoura", "quantidade": "10"},
    ]
    res = processar_planilha_ofertas(linhas)
    assert res["total"] == 3
    assert res["inseridas"] == 2
    assert len(res["erros"]) == 1
    assert res["erros"][0]["linha"] == 2
    assert "CPF" in res["erros"][0]["motivo"]


def test_excede_limite_de_linhas(monkeypatch):
    _stub_ok(monkeypatch)
    linhas = [{"nome": "x", "cpf_cnpj": "1", "descricao": "y", "quantidade": "1"}] * (PLANILHA_MAX_LINHAS + 1)
    res = processar_planilha_ofertas(linhas)
    assert res["inseridas"] == 0
    assert res["erros"] and "limite" in res["erros"][0]["motivo"].lower()


def test_planilha_vazia(monkeypatch):
    _stub_ok(monkeypatch)
    res = processar_planilha_ofertas([])
    assert res == {"total": 0, "inseridas": 0, "erros": []}
