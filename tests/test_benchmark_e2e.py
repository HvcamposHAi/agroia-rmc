"""Teste E2E do benchmark — exercita o loop real contra a API do motor.

Roda UMA pergunta (L02) ponta-a-ponta pelo ClaudeProvider (baseline fiel): chama
a API real da Anthropic e o Supabase real via executar_tool. É pulado
automaticamente se ANTHROPIC_API_KEY/SUPABASE não estiverem configurados, para
não quebrar a suíte offline.

Como rodar:
    pytest tests/test_benchmark_e2e.py -v   # com .env contendo as chaves

Cada motor adicional pode ser ligado via env (GROQ_API_KEY etc.); cada um pula
individualmente se a sua chave faltar.
"""

import os

import pytest
from dotenv import load_dotenv

load_dotenv()

_TEM_ANTHROPIC = bool(os.getenv("ANTHROPIC_API_KEY"))
_TEM_SUPABASE = bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY"))


@pytest.mark.skipif(not (_TEM_ANTHROPIC and _TEM_SUPABASE),
                    reason="Requer ANTHROPIC_API_KEY + SUPABASE_URL/KEY no .env")
def test_e2e_claude_l02():
    from benchmark.providers.factory import get_provider
    from benchmark.agentic_loop import rodar_loop
    from benchmark.dataset import selecionar_perguntas

    q = selecionar_perguntas("L02")[0]
    provider = get_provider("claude")
    res = rodar_loop(provider, q["pergunta"])

    assert res.erro is None, f"erro inesperado: {res.erro}"
    assert res.resposta.strip(), "resposta vazia"
    assert res.latencia_total_ms > 0
    assert res.tokens_entrada > 0
    # L02 deve acionar query_itens_agro (volume de cenoura)
    assert "query_itens_agro" in res.tools_usadas


@pytest.mark.skipif(not os.getenv("GROQ_API_KEY"), reason="Requer GROQ_API_KEY")
def test_e2e_groq_smoke():
    from benchmark.providers.factory import get_provider
    from benchmark.agentic_loop import rodar_loop
    res = rodar_loop(get_provider("groq_llama"), "bom dia")
    assert res.erro is None
    assert res.latencia_total_ms > 0


@pytest.mark.skipif(not os.getenv("GOOGLE_API_KEY"), reason="Requer GOOGLE_API_KEY")
def test_e2e_gemini_smoke():
    from benchmark.providers.factory import get_provider
    from benchmark.agentic_loop import rodar_loop
    res = rodar_loop(get_provider("gemini"), "bom dia")
    assert res.erro is None
    assert res.latencia_total_ms > 0


@pytest.mark.skipif(not os.getenv("MARITACA_API_KEY"), reason="Requer MARITACA_API_KEY")
def test_e2e_maritaca_smoke():
    from benchmark.providers.factory import get_provider
    from benchmark.agentic_loop import rodar_loop
    res = rodar_loop(get_provider("maritaca"), "bom dia", max_tool_result_chars=4000)
    assert res.erro is None
    assert res.latencia_total_ms > 0
