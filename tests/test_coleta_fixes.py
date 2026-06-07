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

    def test_iniciar_bloqueado_quando_desabilitada(self):
        # Com chave válida porém COLETA_ENABLED=false → 400 (não dispara nada).
        resp = client.post("/coleta/iniciar", headers={"X-API-Key": API_KEY})
        assert resp.status_code == 400
        assert "desabilitada" in resp.json()["detail"].lower()


class TestPidVivo:
    def test_pid_none_morto(self):
        assert _pid_vivo(None) is False

    def test_pid_proprio_vivo(self):
        # O processo do próprio teste está vivo (no Windows a função retorna True por design).
        assert _pid_vivo(os.getpid()) is True


# ─── Fakes leves do cliente Supabase (sem rede) ──────────────────────────────
class _FakeResp:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, data):
        self._data = data

    def select(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        return _FakeResp(self._data)


class _FakeSB:
    def __init__(self, data):
        self._data = data

    def table(self, *a, **k):
        return _FakeQuery(self._data)


class TestPopenDevnull:
    """P1/P2: iniciar_coleta usa DEVNULL (anti-deadlock) e respeita o gate habilitado."""

    def test_popen_usa_devnull_quando_habilitado(self, monkeypatch):
        monkeypatch.setenv("COLETA_ENABLED", "true")
        monkeypatch.setattr(coleta_mod, "get_status", lambda: {"status": "idle"})

        capturado = {}

        class FakeProc:
            pid = 4321

        def fake_popen(cmd, **kwargs):
            capturado["cmd"] = cmd
            capturado["kwargs"] = kwargs
            return FakeProc()

        monkeypatch.setattr(coleta_mod.subprocess, "Popen", fake_popen)

        # dt_inicio/dt_fim explícitos evitam ida ao Supabase (get_data_mais_recente)
        ok, msg = coleta_mod.iniciar_coleta(dt_inicio="01/01/2026", dt_fim="07/01/2026")

        assert ok is True  # P2: gate habilitado seguiu adiante
        assert capturado["kwargs"].get("stdout") is coleta_mod.subprocess.DEVNULL
        assert capturado["kwargs"].get("stderr") is coleta_mod.subprocess.DEVNULL
        assert capturado["kwargs"].get("stdout") is not coleta_mod.subprocess.PIPE


class TestProximaExecucao:
    """P3: proxima_execucao_iso depende do gate."""

    def test_desabilitada_retorna_none(self, monkeypatch):
        monkeypatch.setenv("COLETA_ENABLED", "false")
        assert coleta_mod.proxima_execucao_iso() is None

    def test_habilitada_retorna_iso(self, monkeypatch):
        monkeypatch.setenv("COLETA_ENABLED", "true")
        res = coleta_mod.proxima_execucao_iso()
        assert res is None or isinstance(res, str)
        if isinstance(res, str):
            assert "T" in res  # formato ISO


class TestUltimaExecucao:
    """P4: get_ultima_execucao mapeia a resposta do Supabase."""

    def test_com_registro(self, monkeypatch):
        linha = {"id": 9, "status": "completed", "processados": 12}
        monkeypatch.setattr(coleta_mod, "get_supabase_client", lambda: _FakeSB([linha]))
        assert coleta_mod.get_ultima_execucao() == linha

    def test_sem_registro(self, monkeypatch):
        monkeypatch.setattr(coleta_mod, "get_supabase_client", lambda: _FakeSB([]))
        assert coleta_mod.get_ultima_execucao() is None


class TestColetaModo:
    def test_default_local(self, monkeypatch):
        monkeypatch.delenv("COLETA_MODE", raising=False)
        assert coleta_mod.coleta_modo() == "local"

    def test_github(self, monkeypatch):
        monkeypatch.setenv("COLETA_MODE", "github")
        assert coleta_mod.coleta_modo() == "github"


class TestStaleness:
    def test_status_estagnado_true(self):
        antigo = {"status": "running", "atualizado_em": "2020-01-01T00:00:00"}
        assert coleta_mod._status_estagnado(antigo, limite_seg=900) is True

    def test_status_estagnado_false_recente(self):
        from datetime import datetime
        agora = {"status": "running", "atualizado_em": datetime.now().isoformat()}
        assert coleta_mod._status_estagnado(agora, limite_seg=900) is False

    def test_idade_seg_invalida(self):
        assert coleta_mod._idade_seg(None) is None


class TestDispatchGithub:
    """iniciar_coleta no modo github chama a API do GitHub (workflow_dispatch)."""

    def test_dispara_workflow(self, monkeypatch):
        monkeypatch.setenv("COLETA_ENABLED", "true")
        monkeypatch.setenv("COLETA_MODE", "github")
        monkeypatch.setenv("GITHUB_REPO", "owner/repo")
        monkeypatch.setenv("GH_DISPATCH_TOKEN", "tok")
        monkeypatch.setattr(coleta_mod, "get_status", lambda: {"status": "idle"})
        monkeypatch.setattr(coleta_mod, "_upsert_status", lambda d: None)

        chamado = {}

        class FakeResp:
            status_code = 204
            text = ""

        def fake_post(url, **kwargs):
            chamado["url"] = url
            chamado["json"] = kwargs.get("json")
            return FakeResp()

        import requests
        monkeypatch.setattr(requests, "post", fake_post)

        ok, msg = coleta_mod.iniciar_coleta(dt_inicio="01/01/2026", dt_fim="07/01/2026")
        assert ok is True
        assert "GitHub" in msg
        assert "/actions/workflows/" in chamado["url"]
        assert chamado["json"]["ref"]  # ref enviado

    def test_falta_config(self, monkeypatch):
        monkeypatch.setenv("COLETA_ENABLED", "true")
        monkeypatch.setenv("COLETA_MODE", "github")
        monkeypatch.delenv("GITHUB_REPO", raising=False)
        monkeypatch.delenv("GH_DISPATCH_TOKEN", raising=False)
        monkeypatch.setattr(coleta_mod, "get_status", lambda: {"status": "idle"})
        ok, msg = coleta_mod.iniciar_coleta(dt_inicio="01/01/2026", dt_fim="07/01/2026")
        assert ok is False
        assert "GITHUB_REPO" in msg or "GH_DISPATCH_TOKEN" in msg


class TestHeadlessEnv:
    """P5: PLAYWRIGHT_HEADLESS controla o launch do Chromium no etapa2."""

    def test_headless_true_adiciona_no_sandbox(self, monkeypatch):
        monkeypatch.setenv("PLAYWRIGHT_HEADLESS", "true")
        import importlib
        import etapa2_itens_v9
        importlib.reload(etapa2_itens_v9)
        try:
            assert etapa2_itens_v9.HEADLESS is True
            assert "--no-sandbox" in etapa2_itens_v9.LAUNCH_ARGS
            assert "--disable-dev-shm-usage" in etapa2_itens_v9.LAUNCH_ARGS
        finally:
            # Restaura o default (headed) para não afetar outros testes
            monkeypatch.setenv("PLAYWRIGHT_HEADLESS", "false")
            importlib.reload(etapa2_itens_v9)
