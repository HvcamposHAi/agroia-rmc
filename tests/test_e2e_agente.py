"""Teste E2E do pipeline de chat — requer servidor rodando.

Usa o contrato REAL do endpoint: POST /chat com {pergunta, historico} e header
X-API-Key; resposta {resposta, tools_usadas, session_id}.

Como rodar (servidor local em :8001):
    $env:BACKEND_URL="http://localhost:8001"; $env:API_SECRET_KEY="<chave>"
    pytest tests/test_e2e_agente.py -v

Os testes são pulados automaticamente se o backend não estiver acessível,
para não quebrar a suíte unitária offline.
"""

import os
import time

import httpx
import pytest

BASE = os.getenv("BACKEND_URL", "http://localhost:8001")
HEAD = {"X-API-Key": os.getenv("API_SECRET_KEY", "")}


def _backend_disponivel() -> bool:
    try:
        r = httpx.get(f"{BASE}/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _backend_disponivel(),
    reason=f"Backend não acessível em {BASE} (defina BACKEND_URL).",
)


CASOS = [
    "quanto de alface a merenda comprou em 2025",
    "qual o preço da cenoura na ceasa de curitiba",
    "me mostre os editais do armazém da família",
    "bom dia",
]


@pytest.mark.parametrize("pergunta", CASOS)
def test_e2e_chat(pergunta):
    t = time.time()
    r = httpx.post(
        f"{BASE}/chat",
        json={"pergunta": pergunta, "historico": []},
        headers=HEAD,
        timeout=40,
    )
    assert r.status_code == 200, f"status {r.status_code}: {r.text[:200]}"
    body = r.json()
    assert "resposta" in body and len(body["resposta"]) > 5
    assert "session_id" in body
    assert (time.time() - t) < 40


def test_e2e_input_malicioso_nao_gera_500():
    for p in ["'; DROP TABLE licitacoes; --", "alface' OR '1'='1"]:
        r = httpx.post(
            f"{BASE}/chat",
            json={"pergunta": p, "historico": []},
            headers=HEAD,
            timeout=30,
        )
        assert r.status_code != 500, f"input malicioso causou 500: {p}"
