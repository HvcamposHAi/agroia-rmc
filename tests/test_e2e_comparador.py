"""Teste E2E do switch de motor + comparador — requer backend rodando.

Pula automaticamente se o backend não estiver acessível (mesma convenção de
tests/test_e2e_agente.py), para não quebrar a suíte offline.

Como rodar (backend local em :8001):
    $env:BACKEND_URL="http://localhost:8001"; $env:API_SECRET_KEY="<chave>"
    pytest tests/test_e2e_comparador.py -v
"""

import os

import httpx
import pytest

BASE = os.getenv("BACKEND_URL", "http://localhost:8001")
HEAD = {"X-API-Key": os.getenv("API_SECRET_KEY", "")}


def _backend_disponivel() -> bool:
    try:
        return httpx.get(f"{BASE}/health", timeout=3).status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _backend_disponivel(),
    reason=f"Backend não acessível em {BASE} (defina BACKEND_URL).",
)


def test_config_motor_get():
    r = httpx.get(f"{BASE}/config/motor", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert "motor_ativo" in body and isinstance(body["motores"], list)


def test_config_motor_set_claude():
    # Garante o sistema no baseline (não deixa um motor experimental fixado).
    r = httpx.post(f"{BASE}/config/motor", json={"motor": "claude"}, headers=HEAD, timeout=10)
    assert r.status_code == 200
    assert r.json()["motor_ativo"] == "claude"


def test_comparar_stream_claude():
    pergunta = "quanto de alface a merenda comprou em 2025"
    with httpx.stream("POST", f"{BASE}/benchmark/comparar/stream",
                      json={"pergunta": pergunta, "motores": ["claude"]},
                      headers=HEAD, timeout=90) as r:
        assert r.status_code == 200
        eventos = "".join(chunk for chunk in r.iter_text())
    assert '"tipo": "motor"' in eventos
    assert '"motor": "claude"' in eventos
    assert "[DONE]" in eventos
