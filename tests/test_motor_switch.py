"""Testes pontuais (offline) do switch global de motor + providers REST + endpoints.

Sem rede e sem chaves reais. Cobre:
- parsing dos providers REST (requests monkeypatchado);
- motor_router (cliente Supabase fake): get/default/resolver;
- chat.agent honra o switch sem tocar o caminho Claude;
- endpoints /config/motor e /benchmark/comparar/stream via TestClient.

Rodar: pytest tests/test_motor_switch.py
"""

import os
import types

import pytest

# Env mínimo p/ importar api.main (valida no import). Cliente Supabase é lazy.
API_KEY = "test-secret-key"
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-anon-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ["API_SECRET_KEY"] = API_KEY

from benchmark.providers.base import LLMResponse, ToolCall  # noqa: E402
from benchmark.providers import rest_providers as rp  # noqa: E402


# ---------------------------------------------------------------------------
# 1. Providers REST — parsing com requests monkeypatchado
# ---------------------------------------------------------------------------
class _FakeHTTP:
    def __init__(self, payload):
        self._payload = payload
    def raise_for_status(self):
        return None
    def json(self):
        return self._payload


class TestRestProviders:
    def test_openai_compat_tool_call(self, monkeypatch):
        payload = {
            "choices": [{
                "message": {"content": None, "tool_calls": [
                    {"id": "c1", "function": {"name": "query_itens_agro",
                                              "arguments": '{"agregacao":"por_cultura"}'}}]},
                "finish_reason": "tool_calls",
            }],
            "usage": {"prompt_tokens": 12, "completion_tokens": 8},
        }
        monkeypatch.setattr(rp.requests, "post", lambda *a, **k: _FakeHTTP(payload))
        prov = rp.OpenAICompatRestProvider("k", "https://x/v1", "llama-3.1-8b-instant", "groq_llama")
        out = prov.gerar("SYS", [], [{"role": "user", "content": "x"}])
        assert out.stop_reason == "tool_use"
        assert out.tool_calls[0].nome == "query_itens_agro"
        assert out.tool_calls[0].inputs == {"agregacao": "por_cultura"}
        assert out.tokens_entrada == 12 and out.tokens_saida == 8

    def test_openai_compat_end_turn(self, monkeypatch):
        payload = {"choices": [{"message": {"content": "ok final"}, "finish_reason": "stop"}],
                   "usage": {"prompt_tokens": 3, "completion_tokens": 2}}
        monkeypatch.setattr(rp.requests, "post", lambda *a, **k: _FakeHTTP(payload))
        prov = rp.OpenAICompatRestProvider("k", "https://x/v1", "sabia-4", "maritaca")
        out = prov.gerar("SYS", [], [{"role": "user", "content": "x"}])
        assert out.stop_reason == "end_turn" and out.texto == "ok final"

    def test_rest_erro_nao_levanta(self, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("429 rate limit")
        monkeypatch.setattr(rp.requests, "post", boom)
        prov = rp.OpenAICompatRestProvider("k", "https://x/v1", "m", "groq_llama")
        out = prov.gerar("SYS", [], [{"role": "user", "content": "x"}])
        assert out.stop_reason == "erro" and "429" in out.texto

    def test_gemini_rest_function_call(self, monkeypatch):
        payload = {
            "candidates": [{"content": {"parts": [
                {"functionCall": {"name": "query_itens_agro", "args": {"cultura": "tomate"}}}]}}],
            "usageMetadata": {"promptTokenCount": 20, "candidatesTokenCount": 5},
        }
        captura = {}
        def fake_post(url, json=None, **k):
            captura["url"] = url; captura["body"] = json
            return _FakeHTTP(payload)
        monkeypatch.setattr(rp.requests, "post", fake_post)
        prov = rp.GeminiRestProvider("k")
        # tools não-vazias p/ verificar function_declarations no body
        from chat.tools import TOOLS_SCHEMA
        out = prov.gerar("SYS", TOOLS_SCHEMA, [{"role": "user", "content": "x"}])
        assert out.stop_reason == "tool_use"
        assert out.tool_calls[0].nome == "query_itens_agro"
        assert out.tool_calls[0].inputs == {"cultura": "tomate"}
        assert "function_declarations" in captura["body"]["tools"][0]

    def test_get_live_provider_sem_chave(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        with pytest.raises(RuntimeError):
            rp.get_live_provider("groq_llama")


# ---------------------------------------------------------------------------
# 2. motor_router — cliente Supabase fake
# ---------------------------------------------------------------------------
class _FakeQuery:
    def __init__(self, data): self._data = data
    def select(self, *a, **k): return self
    def eq(self, *a, **k): return self
    def limit(self, *a, **k): return self
    def execute(self): return types.SimpleNamespace(data=self._data)


class _FakeSB:
    def __init__(self, data): self._data = data
    def table(self, *a, **k): return _FakeQuery(self._data)


class TestMotorRouter:
    def _reset(self):
        import chat.motor_router as mr
        mr._cache_motor = None
        mr._cache_ts = 0.0

    def test_get_motor_default_claude_em_erro(self, monkeypatch):
        import chat.motor_router as mr
        self._reset()
        monkeypatch.setattr("chat.db.get_supabase_client", lambda: (_ for _ in ()).throw(RuntimeError("db off")))
        assert mr.get_motor_ativo() == "claude"

    def test_get_motor_le_valor(self, monkeypatch):
        import chat.motor_router as mr
        self._reset()
        monkeypatch.setattr("chat.db.get_supabase_client", lambda: _FakeSB([{"motor_ativo": "gemini"}]))
        assert mr.get_motor_ativo() == "gemini"

    def test_resolver_provider_claude_none(self, monkeypatch):
        import chat.motor_router as mr
        self._reset()
        monkeypatch.setattr("chat.db.get_supabase_client", lambda: _FakeSB([{"motor_ativo": "claude"}]))
        assert mr.resolver_provider() is None


# ---------------------------------------------------------------------------
# 3. chat.agent honra o switch sem tocar o caminho Claude
# ---------------------------------------------------------------------------
class _FakeProvider:
    nome = "groq_llama"; modelo = "llama-3.1-8b-instant"
    def __init__(self, respostas): self._r = list(respostas); self.i = 0
    def gerar(self, *a, **k):
        r = self._r[self.i]; self.i += 1; return r


class TestAgentSwitch:
    def test_chat_usa_provider_e_nao_claude(self, monkeypatch):
        import chat.agent as agent
        import chat.motor_router as mr
        # motor ativo = groq_llama
        monkeypatch.setattr(mr, "get_motor_ativo", lambda: "groq_llama")
        fake = _FakeProvider([
            LLMResponse(texto="", stop_reason="tool_use",
                        tool_calls=[ToolCall(id="t1", nome="query_itens_agro", inputs={"agregacao": "detalhado"})],
                        tokens_entrada=10, tokens_saida=5),
            LLMResponse(texto="Resposta via Llama.", stop_reason="end_turn", tokens_entrada=8, tokens_saida=4),
        ])
        monkeypatch.setattr(mr, "resolver_provider", lambda *a, **k: fake)
        monkeypatch.setattr("benchmark.agentic_loop.executar_tool", lambda nome, inputs: [{"x": 1}])
        # se o caminho Claude for tocado, falha:
        monkeypatch.setattr(agent, "get_client", lambda: (_ for _ in ()).throw(AssertionError("não deveria usar Claude")))

        out = agent.chat("volume de tomate")
        assert out["resposta"] == "Resposta via Llama."
        assert out["tools_usadas"] == ["query_itens_agro"]


# ---------------------------------------------------------------------------
# 4. Endpoints via TestClient
# ---------------------------------------------------------------------------
from fastapi.testclient import TestClient  # noqa: E402
from api.main import app  # noqa: E402

client = TestClient(app)


class TestEndpoints:
    def test_get_config_motor_publico(self, monkeypatch):
        import chat.motor_router as mr
        monkeypatch.setattr(mr, "get_motor_ativo", lambda: "claude")
        r = client.get("/config/motor")
        assert r.status_code == 200
        body = r.json()
        assert body["motor_ativo"] == "claude"
        assert any(m["motor"] == "claude" and m["baseline"] for m in body["motores"])

    def test_post_config_motor_sem_chave_403(self):
        r = client.post("/config/motor", json={"motor": "gemini"})
        assert r.status_code == 403

    def test_post_config_motor_invalido_400(self):
        r = client.post("/config/motor", json={"motor": "xpto"}, headers={"X-API-Key": API_KEY})
        assert r.status_code == 400

    def test_comparar_stream_sem_chave_403(self):
        r = client.post("/benchmark/comparar/stream", json={"pergunta": "oi", "motores": ["claude"]})
        assert r.status_code == 403

    def test_comparar_stream_ok(self, monkeypatch):
        import api.benchmark_api as bapi
        fake = _FakeProvider([LLMResponse(texto="Olá!", stop_reason="end_turn",
                                          tokens_entrada=5, tokens_saida=2)])
        monkeypatch.setattr(bapi, "get_live_provider", lambda nome: fake)
        monkeypatch.setattr("benchmark.agentic_loop.executar_tool", lambda n, i: {"ok": 1})
        r = client.post("/benchmark/comparar/stream",
                        json={"pergunta": "bom dia", "motores": ["claude"]},
                        headers={"X-API-Key": API_KEY})
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]
        corpo = r.text
        assert '"tipo": "motor"' in corpo and '"resposta": "Olá!"' in corpo
        assert "[DONE]" in corpo

    def test_comparar_stream_falha_de_motor_isolada(self, monkeypatch):
        import api.benchmark_api as bapi
        def boom(nome):
            raise RuntimeError("chave ausente")
        monkeypatch.setattr(bapi, "get_live_provider", boom)
        r = client.post("/benchmark/comparar/stream",
                        json={"pergunta": "x", "motores": ["gemini"]},
                        headers={"X-API-Key": API_KEY})
        assert r.status_code == 200  # nunca 500
        assert '"erro"' in r.text and "chave ausente" in r.text
