"""Testes pontuais (offline) do pacote benchmark/.

Cobrem, SEM rede e SEM chaves de API:
- conversão de schema Anthropic → OpenAI / Gemini;
- parsing de respostas cruas (fakes) → LLMResponse, p/ cada provider;
- semântica do loop agêntico (tool_use → end_turn, max-iter, erro);
- métricas AF@k / abstenção / percentis e Bonferroni.

Rodar: pytest tests/test_benchmark_providers.py
"""

import json
import types

import pytest

from chat.tools import TOOLS_SCHEMA
from benchmark import schema_adapter as sa
from benchmark.providers.base import LLMResponse, ToolCall
from benchmark.agentic_loop import rodar_loop, ExecucaoResultado
from benchmark import metricas, stats
from benchmark.dataset import carregar_dataset, selecionar_perguntas


# ---------------------------------------------------------------------------
# 1. Conversão de schemas
# ---------------------------------------------------------------------------
class TestSchemaAdapter:
    def test_anthropic_para_openai_preserva_parameters_e_enum(self):
        oai = sa.anthropic_tools_para_openai(TOOLS_SCHEMA)
        assert len(oai) == len(TOOLS_SCHEMA)
        assert all(t["type"] == "function" for t in oai)
        itens = next(t for t in oai if t["function"]["name"] == "query_itens_agro")
        params = itens["function"]["parameters"]
        # parameters == input_schema original (mapeamento 1:1)
        assert params["properties"]["agregacao"]["enum"] == [
            "detalhado", "por_cultura", "por_canal", "por_ano", "por_categoria"
        ]

    def test_anthropic_para_gemini_uppercase_e_sem_chaves_invalidas(self):
        decls = sa.anthropic_tools_para_gemini_dict(TOOLS_SCHEMA)
        itens = next(d for d in decls if d["name"] == "query_itens_agro")
        p = itens["parameters"]
        assert p["type"] == "OBJECT"
        assert p["properties"]["ano"]["type"] == "INTEGER"
        assert p["properties"]["agregacao"]["type"] == "STRING"
        assert "additionalProperties" not in json.dumps(p)
        assert isinstance(p["required"], list)

    def test_canonico_para_openai_tool_result_vira_role_tool(self):
        messages = [
            {"role": "user", "content": "oi"},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t1", "name": "query_itens_agro", "input": {"agregacao": "detalhado"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": '{"x":1}'},
            ]},
        ]
        oai = sa.canonico_para_openai_messages("SYS", messages)
        assert oai[0] == {"role": "system", "content": "SYS"}
        assistant = next(m for m in oai if m["role"] == "assistant")
        assert assistant["tool_calls"][0]["function"]["name"] == "query_itens_agro"
        # arguments é STRING JSON
        assert json.loads(assistant["tool_calls"][0]["function"]["arguments"]) == {"agregacao": "detalhado"}
        tool_msg = next(m for m in oai if m["role"] == "tool")
        assert tool_msg["tool_call_id"] == "t1"

    def test_canonico_para_gemini_roles_e_function_response(self):
        messages = [
            {"role": "user", "content": "oi"},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t1", "name": "q", "input": {"a": 1}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": '{"x":1}'},
            ]},
        ]
        hist = sa.canonico_para_gemini_history(messages)
        assert hist[0]["role"] == "user"
        assert hist[1]["role"] == "model"
        assert hist[1]["parts"][0]["function_call"]["name"] == "q"
        # nome do function_response é recuperado do tool_use (id t1 → "q")
        assert hist[2]["parts"][0]["function_response"]["name"] == "q"


# ---------------------------------------------------------------------------
# 2. Parsing de respostas cruas (fakes) → LLMResponse
# ---------------------------------------------------------------------------
class TestParsingProviders:
    def test_openai_compat_parse_tool_call(self, monkeypatch):
        from benchmark.providers.openai_base import OpenAICompatProvider

        fake_tc = types.SimpleNamespace(
            id="call_1",
            function=types.SimpleNamespace(name="query_itens_agro",
                                           arguments='{"agregacao": "por_cultura"}'),
        )
        fake_msg = types.SimpleNamespace(content=None, tool_calls=[fake_tc])
        fake_choice = types.SimpleNamespace(message=fake_msg, finish_reason="tool_calls")
        fake_resp = types.SimpleNamespace(
            choices=[fake_choice],
            usage=types.SimpleNamespace(prompt_tokens=11, completion_tokens=7),
        )

        prov = OpenAICompatProvider.__new__(OpenAICompatProvider)
        prov.nome = "groq_llama"
        prov.modelo = "llama-3.1-8b-instant"
        prov._client = types.SimpleNamespace(
            chat=types.SimpleNamespace(
                completions=types.SimpleNamespace(create=lambda **kw: fake_resp)
            )
        )
        out = prov.gerar("SYS", TOOLS_SCHEMA, [{"role": "user", "content": "x"}])
        assert out.stop_reason == "tool_use"
        assert out.tool_calls[0].nome == "query_itens_agro"
        assert out.tool_calls[0].inputs == {"agregacao": "por_cultura"}  # string → dict
        assert out.tokens_entrada == 11 and out.tokens_saida == 7

    def test_openai_compat_parse_end_turn(self):
        from benchmark.providers.openai_base import OpenAICompatProvider
        fake_msg = types.SimpleNamespace(content="resposta final", tool_calls=None)
        fake_choice = types.SimpleNamespace(message=fake_msg, finish_reason="stop")
        fake_resp = types.SimpleNamespace(
            choices=[fake_choice],
            usage=types.SimpleNamespace(prompt_tokens=5, completion_tokens=3),
        )
        prov = OpenAICompatProvider.__new__(OpenAICompatProvider)
        prov.nome = "maritaca"; prov.modelo = "sabia-3"
        prov._client = types.SimpleNamespace(
            chat=types.SimpleNamespace(
                completions=types.SimpleNamespace(create=lambda **kw: fake_resp)
            )
        )
        out = prov.gerar("SYS", TOOLS_SCHEMA, [{"role": "user", "content": "x"}])
        assert out.stop_reason == "end_turn"
        assert out.texto == "resposta final"
        assert not out.tool_calls

    def test_openai_compat_erro_nao_levanta(self):
        from benchmark.providers.openai_base import OpenAICompatProvider

        def boom(**kw):
            raise RuntimeError("429 rate limit")

        prov = OpenAICompatProvider.__new__(OpenAICompatProvider)
        prov.nome = "groq_llama"; prov.modelo = "m"
        prov._client = types.SimpleNamespace(
            chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=boom))
        )
        out = prov.gerar("SYS", TOOLS_SCHEMA, [{"role": "user", "content": "x"}])
        assert out.stop_reason == "erro"
        assert "429" in out.texto

    def test_gemini_proto_para_python(self):
        from benchmark.providers.gemini import _proto_para_python

        class FakeMap(dict):
            pass

        args = FakeMap({"cultura": "tomate", "anos": [2022, 2023]})
        assert _proto_para_python(args) == {"cultura": "tomate", "anos": [2022, 2023]}


# ---------------------------------------------------------------------------
# 3. Semântica do loop agêntico (com FakeProvider)
# ---------------------------------------------------------------------------
class FakeProvider:
    """Provider roteirizado: devolve respostas pré-definidas em sequência."""
    nome = "fake"
    modelo = "fake-1"

    def __init__(self, respostas):
        self._respostas = list(respostas)
        self.chamadas = 0
        self.ultimas_messages = None

    def gerar(self, system_prompt, tools_schema, messages, max_tokens=2048, timeout=30):
        self.ultimas_messages = messages
        r = self._respostas[self.chamadas]
        self.chamadas += 1
        return r


class TestLoopAgentico:
    def test_tool_use_depois_end_turn(self, monkeypatch):
        monkeypatch.setattr("benchmark.agentic_loop.executar_tool",
                            lambda nome, inputs: [{"cultura": "TOMATE", "total": 10}])
        provider = FakeProvider([
            LLMResponse(texto="", stop_reason="tool_use",
                        tool_calls=[ToolCall(id="t1", nome="query_itens_agro", inputs={"agregacao": "detalhado"})],
                        tokens_entrada=10, tokens_saida=5),
            LLMResponse(texto="Resposta final.", stop_reason="end_turn",
                        tokens_entrada=8, tokens_saida=4),
        ])
        res = rodar_loop(provider, "volume de tomate")
        assert isinstance(res, ExecucaoResultado)
        assert res.iteracoes == 2
        assert res.tools_usadas == ["query_itens_agro"]
        assert res.tool_calls_detalhe[0]["inputs"] == {"agregacao": "detalhado"}
        assert res.tokens_entrada == 18 and res.tokens_saida == 9
        assert res.resposta == "Resposta final."
        assert res.erro is None
        # Regressão: o bloco tool_result canônico NÃO pode ter chaves extras
        # (a API Anthropic rejeita campos como _nome_tool com erro 400).
        tool_result = provider.ultimas_messages[-1]["content"][0]
        assert set(tool_result.keys()) == {"type", "tool_use_id", "content"}

    def test_erro_de_provider_retorna_sem_crash(self):
        provider = FakeProvider([LLMResponse(texto="boom", stop_reason="erro")])
        res = rodar_loop(provider, "x")
        assert res.erro == "boom"
        assert res.stop_reason_final == "erro"

    def test_pergunta_vazia(self):
        provider = FakeProvider([])
        res = rodar_loop(provider, "   ")
        assert "válida" in res.resposta
        assert provider.chamadas == 0

    def test_truncamento_tool_result(self, monkeypatch):
        grande = [{"k": "v" * 5000}]
        monkeypatch.setattr("benchmark.agentic_loop.executar_tool", lambda n, i: grande)
        provider = FakeProvider([
            LLMResponse(texto="", stop_reason="tool_use",
                        tool_calls=[ToolCall(id="t1", nome="query_itens_agro", inputs={})]),
            LLMResponse(texto="ok", stop_reason="end_turn"),
        ])
        res = rodar_loop(provider, "x", max_tool_result_chars=100)
        assert res.tool_result_truncado is True


# ---------------------------------------------------------------------------
# 4. Métricas e estatística
# ---------------------------------------------------------------------------
class _ExecFake:
    def __init__(self, tools_usadas, detalhe=None, resposta=""):
        self.tools_usadas = tools_usadas
        self.tool_calls_detalhe = detalhe or []
        self.resposta = resposta


class TestMetricas:
    def test_af1_tool_e_param_corretos(self):
        gab = {"tool_esperada": "query_itens_agro", "tools_aceitaveis": ["query_itens_agro"],
               "parametros_esperados": {"cultura": "cenoura"}, "parametros_criticos": ["cultura"],
               "conjunto": "A"}
        ex = _ExecFake(["query_itens_agro"],
                       [{"nome": "query_itens_agro", "inputs": {"cultura": "cenoura"}}])
        assert metricas.nivel_af(ex, gab) == 1

    def test_af_acento_insensivel(self):
        gab = {"tool_esperada": "consultar_preco_produto",
               "tools_aceitaveis": ["consultar_preco_produto"],
               "parametros_esperados": {"produto": "pimentão"},
               "parametros_criticos": ["produto"], "conjunto": "A"}
        ex = _ExecFake(["consultar_preco_produto"],
                       [{"nome": "consultar_preco_produto", "inputs": {"produto": "pimentao"}}])
        assert metricas.nivel_af(ex, gab) == 1  # "pimentao" casa com "pimentão"

    def test_af2_quando_tool_certa_na_segunda_chamada(self):
        gab = {"tool_esperada": "query_itens_agro", "tools_aceitaveis": ["query_itens_agro"],
               "parametros_esperados": {}, "parametros_criticos": [], "conjunto": "A"}
        ex = _ExecFake(["buscar_chunks_rag", "query_itens_agro"],
                       [{"nome": "buscar_chunks_rag", "inputs": {}},
                        {"nome": "query_itens_agro", "inputs": {}}])
        assert metricas.nivel_af(ex, gab) == 2

    def test_abstencao_tool_none(self):
        gab = {"tool_esperada": None, "tools_aceitaveis": [], "parametros_esperados": {},
               "parametros_criticos": [], "conjunto": "B"}
        assert metricas.nivel_af(_ExecFake([]), gab) == 1
        assert metricas.nivel_af(_ExecFake(["query_itens_agro"]), gab) == 0

    def test_param_strict(self):
        gab = {"tool_esperada": "query_itens_agro", "tools_aceitaveis": ["query_itens_agro"],
               "parametros_esperados": {"cultura": "cenoura"}, "parametros_criticos": ["cultura"],
               "conjunto": "A"}
        ex = _ExecFake(["query_itens_agro"],
                       [{"nome": "query_itens_agro", "inputs": {"cultura": "alface"}}])
        assert metricas.nivel_af(ex, gab) == 0
        assert metricas.af_param_strict(ex, gab) is True

    def test_percentis_formula(self):
        lat = list(range(1, 101))  # 1..100
        p = metricas.percentis(lat)
        assert p["p50_ms"] == 51  # vals[int(100*0.5)] = vals[50] = 51
        assert p["n"] == 100


class TestStats:
    def test_bonferroni_corrige_e_marca(self):
        out = stats.bonferroni({"a": 0.001, "b": 0.5}, n_testes=24)
        assert out["a"]["p_corrigido"] == round(0.001 * 24, 6)
        assert out["a"]["significativo"] is True
        assert out["b"]["significativo"] is False

    def test_comparar_pareado_tamanhos_diferentes(self):
        with pytest.raises(ValueError):
            stats.comparar_pareado([1, 2, 3], [1, 2])


# ---------------------------------------------------------------------------
# 5. Dataset / gabarito
# ---------------------------------------------------------------------------
class TestDataset:
    def test_dataset_carrega_e_valida(self):
        dados = carregar_dataset()
        assert len(dados["perguntas"]) == 30
        ids = [q["id"] for q in dados["perguntas"]]
        assert len(set(ids)) == 30

    def test_paa_e_conjunto_B(self):
        l06 = next(q for q in carregar_dataset()["perguntas"] if q["id"] == "L06")
        assert l06["conjunto"] == "B"
        assert l06["resultado_esperado"] == "vazio"

    def test_selecionar_por_categoria_e_ids(self):
        assert all(q["categoria"] == "preco" for q in selecionar_perguntas("preco"))
        sel = selecionar_perguntas("L02,P01")
        assert {q["id"] for q in sel} == {"L02", "P01"}
