"""
Testes pontuais das correções da página "Atualização de Dados" (/coleta).

Cobrem o núcleo do bug e das mudanças, sem depender do Supabase nem do navegador:
- /coleta/stream agora é POST (era GET → causava o "Stream error" 405).
- Endpoints de escrita validam a API key (verify_api_key).
- Gate B3 (COLETA_ENABLED): no ambiente de nuvem, iniciar coleta é bloqueado.
- Detecção de PID vivo é segura no Windows.

Rodar: pytest tests/test_coleta_fixes.py
"""

import os

import pytest

# Env mínimo para importar api.main (que valida variáveis no import).
# O cliente Supabase é criado lazy dentro das funções, então valores fictícios bastam.
API_KEY = "test-secret-key"
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-anon-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ["API_SECRET_KEY"] = API_KEY
os.environ["COLETA_ENABLED"] = "false"  # simula nuvem (Render) por padrão

from fastapi.testclient import TestClient  # noqa: E402

from api import coleta as coleta_mod  # noqa: E402
from api.main import app, _pid_vivo  # noqa: E402

client = TestClient(app)


class TestMetodoStream:
    def test_stream_get_retorna_405(self):
        # A causa-raiz do "Stream error": o frontend faz POST; GET deve ser 405.
        resp = client.get("/coleta/stream")
        assert resp.status_code == 405

    def test_stream_post_sem_chave_retorna_403(self):
        # Agora protegido por verify_api_key — sem chave, 403 (não 405/200).
        resp = client.post("/coleta/stream")
        assert resp.status_code == 403


class TestAuthEndpointsEscrita:
    def test_iniciar_sem_chave_403(self):
        resp = client.post("/coleta/iniciar")
        assert resp.status_code == 403

    def test_cancelar_sem_chave_403(self):
        resp = client.post("/coleta/cancelar")
        assert resp.status_code == 403

    def test_config_sem_chave_403(self):
        resp = client.post("/coleta/config", json={"dia_semana": 0, "hora": 6, "minuto": 0})
        assert resp.status_code == 403

    def test_iniciar_com_chave_errada_403(self):
        resp = client.post("/coleta/iniciar", headers={"X-API-Key": "errada"})
        assert resp.status_code == 403


class TestGateColetaB3:
    def test_coleta_habilitada_le_env(self, monkeypatch):
        monkeypatch.setenv("COLETA_ENABLED", "true")
        assert coleta_mod.coleta_habilitada() is True
        monkeypatch.setenv("COLETA_ENABLED", "false")
        assert coleta_mod.coleta_habilitada() is False

    def test_iniciar_bloqueado_na_nuvem(self):
        # Com chave válida porém COLETA_ENABLED=false → 400 com mensagem de execução local.
        # (não dispara subprocess/navegador)
        resp = client.post("/coleta/iniciar", headers={"X-API-Key": API_KEY})
        assert resp.status_code == 400
        assert "local" in resp.json()["detail"].lower()


class TestPidVivo:
    def test_pid_none_morto(self):
        assert _pid_vivo(None) is False

    def test_pid_proprio_vivo(self):
        # O processo do próprio teste está vivo (no Windows a função retorna True por design).
        assert _pid_vivo(os.getpid()) is True
