"""Persistência dos resultados do benchmark.

Fonte AUTORITATIVA = arquivos CSV/JSON em metrics/. O espelho no Supabase é
OPCIONAL (BENCHMARK_DB_SYNC=true) e NUNCA bloqueia/derruba a execução (try/except
que só registra, espelhando a filosofia de chat/agent.py:_registrar_log).
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

CAMPOS_CSV = [
    "run_id", "motor", "modelo", "questao_id", "categoria", "conjunto", "repeticao",
    "dt_execucao", "latencia_ms", "iteracoes", "tokens_entrada", "tokens_saida",
    "tokens_estimados", "custo_usd", "tool_esperada", "tools_usadas",
    "tool_calls_detalhe", "af_nivel", "af_param_strict", "abstencao_correta",
    "resultado_vazio", "tool_result_truncado", "status", "erro", "resposta",
]


def garantir_dir(caminho: str | Path) -> Path:
    p = Path(caminho)
    p.mkdir(parents=True, exist_ok=True)
    return p


def caminho_csv(metrics_dir: str | Path, run_id: str) -> Path:
    return Path(metrics_dir) / f"benchmark_runs_{run_id}.csv"


def append_row(csv_path: str | Path, row: dict) -> None:
    """Acrescenta uma linha ao CSV, escrevendo o header só na primeira vez."""
    p = Path(csv_path)
    novo = not p.exists()
    linha = {c: _serial(row.get(c, "")) for c in CAMPOS_CSV}
    with p.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_CSV)
        if novo:
            w.writeheader()
        w.writerow(linha)


def _serial(v):
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False, default=str)
    return v


def escrever_json(caminho: str | Path, dados: dict) -> Path:
    p = Path(caminho)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Espelho Supabase (OPCIONAL, não-bloqueante)
# ---------------------------------------------------------------------------
def sync_habilitado() -> bool:
    return os.getenv("BENCHMARK_DB_SYNC", "false").lower() == "true"


def sync_execucao(execucao: dict) -> None:
    if not sync_habilitado():
        return
    try:
        from chat.db import get_supabase_client
        get_supabase_client().table("benchmark_execucoes").upsert(execucao).execute()
    except Exception as e:  # noqa: BLE001
        print(f"[aviso] sync benchmark_execucoes falhou (ignorado): {e}")


def sync_resultado(linha: dict) -> None:
    if not sync_habilitado():
        return
    try:
        from chat.db import get_supabase_client
        payload = {k: _json_compat(v) for k, v in linha.items() if k in _COLUNAS_DB}
        get_supabase_client().table("benchmark_resultados").upsert(
            payload, on_conflict="run_id,motor,questao_id,repeticao"
        ).execute()
    except Exception as e:  # noqa: BLE001
        print(f"[aviso] sync benchmark_resultados falhou (ignorado): {e}")


_COLUNAS_DB = {
    "run_id", "motor", "modelo", "questao_id", "categoria", "conjunto", "repeticao",
    "dt_execucao", "latencia_ms", "iteracoes", "tokens_entrada", "tokens_saida",
    "custo_usd", "tool_esperada", "tools_usadas", "tool_calls_detalhe", "af_nivel",
    "abstencao_correta", "tool_result_truncado", "status", "erro", "resposta",
}


def _json_compat(v):
    # tools_usadas / tool_calls_detalhe vão como jsonb (objeto), não string.
    return v


# ---------------------------------------------------------------------------
# Export p/ o front-end (JSON estático servido pelo Vite/Cloudflare Pages)
# ---------------------------------------------------------------------------
def export_frontend(resumo_consolidado: dict,
                    dest: str | Path | None = None) -> Path:
    """Grava o JSON consolidado em agroia-frontend/public/benchmark/resultados.json."""
    if dest is None:
        raiz = Path(__file__).resolve().parents[1]
        dest = raiz / "agroia-frontend" / "public" / "benchmark" / "resultados.json"
    return escrever_json(dest, resumo_consolidado)
