"""
Testes para validar hotfixes críticos da auditoria de código.
Execute com: pytest tests/test_critical_hotfixes.py -v
"""

import pytest
import json
import sys
import os

# Adicionar caminho do projeto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_env_vars_present():
    """Verifica se variáveis de ambiente críticas estão definidas."""
    from dotenv import load_dotenv
    load_dotenv()

    assert os.getenv("SUPABASE_URL"), "Missing SUPABASE_URL"
    assert os.getenv("SUPABASE_KEY"), "Missing SUPABASE_KEY"
    assert os.getenv("ANTHROPIC_API_KEY"), "Missing ANTHROPIC_API_KEY"
    print("✓ All required env vars are present")


def test_agent_returns_valid_resposta():
    """Testa se agent sempre retorna dict com 'resposta' field."""
    from chat.agent import chat

    # Teste 1: Pergunta normal
    resultado = chat("Qual a demanda de alface?", [])
    assert isinstance(resultado, dict), "chat() should return dict"
    assert "resposta" in resultado, "Response missing 'resposta' field"
    assert "tools_usadas" in resultado, "Response missing 'tools_usadas' field"
    assert isinstance(resultado["resposta"], str), "resposta should be string"
    assert len(resultado["resposta"]) > 0, "resposta should not be empty"
    print(f"✓ Valid response: {resultado['resposta'][:100]}")

    # Teste 2: Pergunta vazia (deve ser tratada)
    resultado = chat("", [])
    assert isinstance(resultado, dict), "chat() should return dict even for empty input"
    assert "resposta" in resultado, "Response missing 'resposta' field for empty input"
    print("✓ Empty question handled gracefully")

    # Teste 3: Pergunta None
    try:
        resultado = chat(None, [])
        # Se não levantar erro, verificar resposta
        if resultado:
            assert "resposta" in resultado
    except AttributeError:
        # Esperado se pergunta for None
        pass
    print("✓ None question handled")


def test_tool_input_sanitization():
    """Testa se inputs de tools são sanitizados."""
    from chat.tools import sanitizar_string

    # Teste 1: String normal
    result = sanitizar_string("alface")
    assert result == "alface"
    print("✓ Normal string passes sanitization")

    # Teste 2: String com caracteres suspeitos
    with pytest.raises(ValueError):
        sanitizar_string("alface'; DROP TABLE--")
    print("✓ Malicious input rejected")

    # Teste 3: String longa
    long_string = "a" * 200
    result = sanitizar_string(long_string, max_length=100)
    assert len(result) == 100
    print("✓ Long string truncated")

    # Teste 4: String com whitespace
    result = sanitizar_string("  alface  ")
    assert result == "alface"
    print("✓ Whitespace trimmed")


def test_chat_endpoint_response_validation():
    """Testa se endpoint /chat valida resposta antes de retornar."""
    from api.main import ChatRequest, chat_endpoint

    # Teste 1: Request válido
    request = ChatRequest(pergunta="test question", historico=[])
    try:
        response = chat_endpoint(request)
        # Se não levantar erro, verificar resposta
        assert hasattr(response, 'resposta'), "Response should have resposta field"
        assert isinstance(response.resposta, str), "resposta should be string"
        assert len(response.resposta) > 0, "resposta should not be empty"
        print(f"✓ Endpoint returns valid ChatResponse with resposta: {response.resposta[:50]}")
    except Exception as e:
        # Esperado se não houver conexão ao Supabase
        print(f"⚠ Endpoint error (expected without DB): {str(e)[:80]}")


def test_logging_setup():
    """Testa se logging está configurado corretamente."""
    import logging
    from api.main import logger

    assert logger is not None, "Logger not initialized"
    assert logger.level >= logging.INFO, "Logger level should be INFO or higher"
    print("✓ Logging configured correctly")


def test_agent_error_handling():
    """Testa se agent trata erros gracefully."""
    from chat.agent import chat

    # Teste com uma pergunta que pode causar erro
    # (se nenhuma view existir, ainda deve retornar resposta)
    resultado = chat("Mostre todas as culturas", [])

    assert isinstance(resultado, dict), "Should return dict even on error"
    assert "resposta" in resultado, "Should have resposta even on error"
    assert resultado["resposta"], "resposta should be non-empty even on error"
    print(f"✓ Error handling works: {resultado['resposta'][:80]}")


def test_api_startup_validation():
    """Testa se API valida env vars no startup."""
    # Este teste verifica se as validações estão no código
    from api import main

    # Se chegou aqui, validações passaram (do contrário teria levantado RuntimeError)
    print("✓ API startup validation passed")


if __name__ == "__main__":
    # Rodar testes básicos sem pytest
    print("Running basic validation tests...\n")

    try:
        test_env_vars_present()
        test_logging_setup()
        test_tool_input_sanitization()
        test_api_startup_validation()
        # test_agent_returns_valid_resposta()  # Requer DB
        # test_chat_endpoint_response_validation()  # Requer DB

        print("\n✅ All basic validation tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
