"""Teste E2E (backend + banco) do pacote pauta do Sacolão / safra / projeção — plano v3.

Casos T-E1 a T-E10. Mesma convenção de tests/test_e2e_comparador.py: pula sozinho
se o backend ou o banco não estiverem acessíveis, para não quebrar a suíte offline.
Etapa ainda não aplicada (rota 404, tabela ausente) também PULA — exceto com
PAUTA_E2E_EXIGIR=1, usado no aceite de cada etapa, quando vira FALHA.

Como rodar (backend local em :8001):
    $env:BACKEND_URL="http://localhost:8001"; $env:API_SECRET_KEY="<chave>"
    pytest tests/test_e2e_pauta.py -v
Aceite de etapa:
    $env:PAUTA_E2E_EXIGIR="1"; pytest tests/test_e2e_pauta.py -v -k "te2 or te3"
"""

import io
import os
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest

BASE = os.getenv("BACKEND_URL", "http://localhost:8001")
HEAD = {"X-API-Key": os.getenv("API_SECRET_KEY", "")}
EXIGIR = os.getenv("PAUTA_E2E_EXIGIR") == "1"

# Rotas da API em 15/10/2026 (32). Nenhuma pode sumir; rota nova só sob /pauta.
ROTAS_EXISTENTES = {
    "/", "/health", "/chat", "/chat/stream", "/conversas/{session_id}",
    "/alertas", "/alertas/stream", "/auditoria/executar", "/auditoria/executar/stream",
    "/auditoria/chat", "/auditoria/consistencia", "/coleta/iniciar", "/coleta/cancelar",
    "/coleta/status", "/coleta/ultima-execucao", "/coleta/proxima-execucao",
    "/coleta/stream", "/coleta/stats", "/coleta/config", "/prohort/coletar",
    "/prohort/status", "/prohort/chat/stream", "/produtor/chat/stream",
    "/produtor/ofertas/upload", "/config/motor", "/benchmark/motores",
    "/benchmark/comparar/stream", "/voz/status", "/voz/tts",
}
GET_SEM_CHAVE = ["/health", "/coleta/status", "/prohort/status", "/config/motor",
                 "/voz/status", "/benchmark/motores"]


def _backend_disponivel() -> bool:
    try:
        return httpx.get(f"{BASE}/health", timeout=3).status_code == 200
    except Exception:
        return False


BACKEND = _backend_disponivel()
precisa_backend = pytest.mark.skipif(not BACKEND, reason=f"Backend não acessível em {BASE}.")


def _pendente(motivo: str):
    """Etapa ainda não aplicada: pula no dia a dia, falha no aceite."""
    if EXIGIR:
        pytest.fail(f"Exigido e ausente: {motivo}")
    pytest.skip(f"Etapa pendente: {motivo}")


def _get(caminho: str, **params) -> httpx.Response:
    r = httpx.get(f"{BASE}{caminho}", params=params, headers=HEAD, timeout=30)
    if r.status_code == 404 and r.headers.get("content-type", "").startswith("application/json") \
            and r.json().get("detail") == "Not Found":
        _pendente(f"rota {caminho} não existe")
    return r


def _supabase():
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
        from supabase import create_client
        url, chave = os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"]
    except Exception:
        pytest.skip("Sem SUPABASE_URL/SUPABASE_KEY.")
    return create_client(url, chave)


def _tabela(sb, nome, colunas="*"):
    try:
        return sb.table(nome).select(colunas)
    except Exception:
        _pendente(f"tabela {nome}")


def _executar(q, nome):
    try:
        return q.execute()
    except Exception as e:
        if "404" in str(e) or "does not exist" in str(e) or "PGRST205" in str(e):
            _pendente(f"tabela {nome}")
        raise


def _ultimo_dia_util(hoje: date) -> date:
    d = hoje - timedelta(days=1)
    while d.weekday() == 6:          # CEASA-PR cota de segunda a sábado
        d -= timedelta(days=1)
    return d


# ── T-E1 · coleta CEASA-PR em produção ───────────────────────────────────────

def test_te1_coleta_ceasa_pr_ok_fresca_e_com_historico():
    sb = _supabase()
    st = _executar(_tabela(sb, "ceasa_pr_status").eq("id", 1), "ceasa_pr_status").data
    assert st and st[0]["status"] == "ok", st
    assert st[0]["data_max"] >= _ultimo_dia_util(date.today()).isoformat()
    mais_antiga = _executar(_tabela(sb, "ceasa_pr_cotacoes", "data_coleta")
                            .eq("unidade", "CURITIBA").order("data_coleta").limit(1),
                            "ceasa_pr_cotacoes").data
    dias = (date.today() - date.fromisoformat(mais_antiga[0]["data_coleta"])).days
    assert dias >= 730, f"histórico de Curitiba com só {dias} dias"


# ── T-E2 · GET /pauta ────────────────────────────────────────────────────────

@precisa_backend
def test_te2_pauta_estrutura_e_rastreabilidade():
    r = _get("/pauta", unidade="CURITIBA")
    assert r.status_code == 200
    p = r.json()
    assert p["ato"] == "Portaria 175"
    assert datetime.fromisoformat(p["consultado_em"])          # IN SEGES 65/2021, art. 5º
    assert len(p["subgrupos"]) == 5
    assert sum(len(s["especies"]) for s in p["subgrupos"]) == 43
    assert sum(s["minimo"] for s in p["subgrupos"]) == 26
    classes = {"normal", "moderadamente_alto", "anormalmente_alto", "baixo", "indisponivel"}
    for s in p["subgrupos"]:
        assert s["atende"] == (s["com_preco"] >= s["minimo"])
        for e in s["especies"]:
            if e["preco"] is None:
                assert e["motivo"], f"{e['especie']}: sem preço e sem motivo"
                continue
            assert e["fonte"] and e["descricao"] and e["data"], e
            assert e["preco"] > 0
            assert e["anomalia"]["classe"] in classes


@precisa_backend
@pytest.mark.parametrize("params", [{"unidade": "XXX"}, {"estacao": "verao'; drop table x"}])
def test_te2_pauta_entrada_invalida(params):
    r = _get("/pauta", **params)
    assert r.status_code in (400, 422)


# ── T-E3 · GET /pauta/fundamentacao ──────────────────────────────────────────

@precisa_backend
def test_te3_fundamentacao_art3():
    fim = date.today()
    r = _get("/pauta/fundamentacao", especie="TOMATE", unidade="CURITIBA",
             inicio=(fim - timedelta(days=180)).isoformat(), fim=fim.isoformat())
    assert r.status_code == 200
    f = r.json()
    datas = [x["data"] for x in f["serie"]]
    assert datas == sorted(datas) and datas, "série ordenada e não vazia"
    assert all((fim - timedelta(days=180)).isoformat() <= d <= fim.isoformat() for d in datas)
    assert "variacao_mensal" in f and "variacao_anual" in f
    assert "CEASA" in f["fonte"].upper() and f["consultado_em"]


# ── T-E4 · GET /pauta/exportar ───────────────────────────────────────────────

@precisa_backend
def test_te4_exportar_xlsx_igual_ao_json():
    openpyxl = pytest.importorskip("openpyxl")
    j = _get("/pauta", unidade="CURITIBA").json()
    r = _get("/pauta/exportar", unidade="CURITIBA")
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]
    ws = openpyxl.load_workbook(io.BytesIO(r.content)).active
    cab = [c.value for c in ws[1]]
    i_esp, i_preco = cab.index("Espécie"), cab.index("Preço (R$)")
    xlsx = {(row[i_esp], row[i_preco]) for row in ws.iter_rows(min_row=2, values_only=True)
            if row[i_esp]}
    json_ = {(e["especie"], e["preco"]) for s in j["subgrupos"] for e in s["especies"]}
    assert xlsx == json_


# ── T-E5 · agente com a chave ligada ─────────────────────────────────────────

@precisa_backend
@pytest.mark.skipif(os.getenv("AGENTE_PAUTA_ATIVO", "").lower() != "true",
                    reason="AGENTE_PAUTA_ATIVO desligado (padrão).")
def test_te5_agente_usa_ferramenta_de_variedades():
    with httpx.stream("POST", f"{BASE}/chat/stream", headers=HEAD, timeout=120,
                      json={"pergunta": "Qual o preço da tangerina ponkan na CEASA de Curitiba?",
                            "idioma": "pt"}) as r:
        assert r.status_code == 200
        texto = "".join(r.iter_text())
    # evento "fim" traz tools_usadas
    assert "consultar_variedades_ceasa_pr" in texto
    assert "ponkan" in texto.lower() and "ceasa" in texto.lower()


# ── T-E7 · não impacto ───────────────────────────────────────────────────────

@precisa_backend
def test_te7_rotas_existentes_intactas():
    caminhos = set(httpx.get(f"{BASE}/openapi.json", timeout=10).json()["paths"])
    assert ROTAS_EXISTENTES <= caminhos, f"sumiram: {ROTAS_EXISTENTES - caminhos}"
    novas = caminhos - ROTAS_EXISTENTES
    assert all(c.startswith("/pauta") for c in novas), f"rota fora de /pauta: {novas}"


@precisa_backend
@pytest.mark.parametrize("caminho", GET_SEM_CHAVE)
def test_te7_get_existentes_respondem(caminho):
    r = httpx.get(f"{BASE}{caminho}", timeout=30)
    assert r.status_code == 200, f"{caminho}: {r.status_code}"


# ── T-E8 · GET /pauta/projecao ───────────────────────────────────────────────

@precisa_backend
def test_te8_projecao_publicada_ou_motivo():
    r = _get("/pauta/projecao", produto="tomate", unidade="CURITIBA")
    assert r.status_code == 200
    p = r.json()
    if not p["publicada"]:
        assert p["motivo"], "sem projeção e sem motivo"
        return
    assert p["mase"] < 1
    # regra de 16/10/2026: vencer os dois ingênuos, não só o sazonal
    assert p["p_vs_sazonal"] < 0.05 and p["p_vs_ingenuo"] < 0.05
    assert {h["h"] for h in p["horizontes"]} <= {1, 2, 4, 8} and p["horizontes"]
    for h in p["horizontes"]:
        assert h["q10"] <= h["q50"] <= h["q90"]
    assert p["modelo_versao"] and p["dados_ate"]


# ── T-E9 · safra: calendário sazonal e comparação entre CEASAs ───────────────

@precisa_backend
def test_te9_catalogo_lista_fechada():
    r = _get("/pauta/safra/catalogo")
    assert r.status_code == 200
    c = r.json()
    assert "couve-flor" in c["produtos"] and "CURITIBA" in c["ceasas"]


@precisa_backend
def test_te9_sazonal_12_meses():
    r = _get("/pauta/safra/sazonal", produto="couve-flor", ceasa="CURITIBA")
    assert r.status_code == 200
    meses = r.json()["meses"]
    assert [m["mes"] for m in meses] == list(range(1, 13))
    for m in meses:
        assert m["confiavel"] == (m["anos"] >= 3)


@precisa_backend
def test_te9_comparar_ranking_unidade_e_frete():
    r = _get("/pauta/safra/comparar", produto="repolho", unidade="KG")
    assert r.status_code == 200
    c = r.json()
    medianas = [x["mediana"] for x in c["ranking"]]
    assert medianas == sorted(medianas, reverse=True)
    assert c["unidade"] == "KG"
    assert "frete" in c["aviso_frete"].lower()


# ── T-E10 · clima histórico ──────────────────────────────────────────────────

def test_te10_clima_regioes_e_atraso():
    sb = _supabase()
    regioes = _executar(_tabela(sb, "clima_regiao", "id,lat,lon"), "clima_regiao").data
    assert regioes and all(r["lat"] is not None and r["lon"] is not None for r in regioes)
    ult = _executar(_tabela(sb, "clima_diario", "data").order("data", desc=True).limit(1),
                    "clima_diario").data
    atraso = (datetime.now(timezone.utc).date() - date.fromisoformat(ult[0]["data"])).days
    assert atraso <= 10, f"clima com {atraso} dias de atraso"
