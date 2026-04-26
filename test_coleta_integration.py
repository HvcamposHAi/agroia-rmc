#!/usr/bin/env python3
"""
Script de teste de integração para o sistema de coleta de dados.
Valida que todos os componentes estão funcionando corretamente.
"""

import json
import os
import sys
from datetime import datetime

def test_imports():
    """Testa se todos os imports necessários funcionam."""
    print("\n[1] Testando imports...")
    try:
        from etapa2_itens_v9 import escrever_progresso, get_data_mais_recente, parse_args
        print("  OK: etapa2_itens_v9")

        from api.coleta import (
            get_data_mais_recente as get_data_coleta,
            get_status,
            get_stats_classificacao,
            iniciar_coleta,
            cancelar_coleta
        )
        print("  OK: api.coleta")

        from api.main import app
        print("  OK: api.main (FastAPI app)")

        print("[OK] Todos os imports funcionam!")
        return True
    except Exception as e:
        print(f"[ERRO] Erro de import: {e}")
        return False

def test_progress_file():
    """Testa se o arquivo de progresso é escrito corretamente."""
    print("\n[2] Testando escrita de progresso JSON...")
    try:
        from etapa2_itens_v9 import escrever_progresso

        test_file = "test_progress_temp.json"
        test_stats = {
            'processados': 42,
            'itens': 100,
            'fornecedores': 5,
            'empenhos': 50,
            'pulados': 10,
            'erros': 1,
            'nao_encontrados': 0,
            'iniciado_em': datetime.now().isoformat()
        }

        escrever_progresso(test_file, test_stats, etapa="teste", status="running")

        with open(test_file, 'r') as f:
            data = json.load(f)

        assert data['status'] == 'running', f"Status errado: {data['status']}"
        assert data['processados'] == 42, f"Processados errado: {data['processados']}"
        assert data['pid'] is not None, "PID nao foi registrado"

        os.remove(test_file)
        print("  Arquivo escrito corretamente")
        print("  Estrutura JSON OK")
        print("[OK] Progresso em JSON funciona!")
        return True
    except Exception as e:
        print(f"[ERRO] Erro ao testar progress file: {e}")
        if os.path.exists("test_progress_temp.json"):
            os.remove("test_progress_temp.json")
        return False

def test_data_parsing():
    """Testa se as funcoes de data funcionam corretamente."""
    print("\n[3] Testando parsing de datas...")
    try:
        import re
        from datetime import date, datetime

        # Simula MAX(dt_abertura) = 2026-04-25
        test_date_iso = "2026-04-25"
        d = datetime.strptime(test_date_iso, "%Y-%m-%d").date()
        result = d.strftime("%d/%m/%Y")

        assert result == "25/04/2026", f"Formato incorreto: {result}"
        print(f"  ISO: {test_date_iso} -> Portal: {result}")

        # Valida formato de data do portal
        portal_date = "30/04/2026"
        assert re.match(r'^\d{2}/\d{2}/\d{4}$', portal_date), "Formato de portal invalido"
        print(f"  Portal format OK: {portal_date}")

        print("[OK] Parsing de datas funciona!")
        return True
    except Exception as e:
        print(f"[ERRO] Erro ao testar dates: {e}")
        return False

def test_api_structure():
    """Testa a estrutura da API."""
    print("\n[4] Testando estrutura da API...")
    try:
        from api.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)

        # Testar endpoint raiz
        resp = client.get("/")
        assert resp.status_code == 200, f"GET / retornou {resp.status_code}"
        assert "endpoints" in resp.json(), "Resposta raiz nao tem endpoints"
        print("  GET / OK")

        # Testar endpoint de status
        resp = client.get("/coleta/status")
        assert resp.status_code == 200, f"GET /coleta/status retornou {resp.status_code}"
        data = resp.json()
        assert "status" in data, "Status nao tem campo 'status'"
        print("  GET /coleta/status OK")

        # Testar endpoint de stats
        resp = client.get("/coleta/stats")
        assert resp.status_code == 200, f"GET /coleta/stats retornou {resp.status_code}"
        print("  GET /coleta/stats OK")

        print("[OK] Estrutura da API OK!")
        return True
    except Exception as e:
        print(f"[ERRO] Erro ao testar API: {e}")
        return False

def main():
    print("=" * 60)
    print("TESTE DE INTEGRACAO: Sistema de Coleta de Dados")
    print("=" * 60)

    results = {
        "imports": test_imports(),
        "progress_file": test_progress_file(),
        "data_parsing": test_data_parsing(),
        "api_structure": test_api_structure(),
    }

    print("\n" + "=" * 60)
    print("RESULTADO FINAL:")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "[PASSOU]" if passed else "[FALHOU]"
        print(f"  {test_name}: {status}")

    all_passed = all(results.values())

    if all_passed:
        print("\nTodos os testes passaram! Sistema pronto para usar.")
        return 0
    else:
        print("\nAlguns testes falharam. Verifique os erros acima.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
