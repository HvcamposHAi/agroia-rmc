"""Carga e seleção do dataset de perguntas do benchmark (com gabarito)."""

from __future__ import annotations

import json
from pathlib import Path

_ARQUIVO = Path(__file__).with_name("perguntas_benchmark.json")

_CHAVES_OBRIGATORIAS = {
    "id", "categoria", "conjunto", "pergunta",
    "tool_esperada", "tools_aceitaveis", "parametros_esperados",
    "parametros_criticos", "resultado_esperado",
}


def carregar_dataset(caminho: str | Path | None = None) -> dict:
    """Carrega o JSON do dataset e valida o schema mínimo de cada pergunta."""
    p = Path(caminho) if caminho else _ARQUIVO
    dados = json.loads(p.read_text(encoding="utf-8"))
    perguntas = dados.get("perguntas", [])
    if not perguntas:
        raise ValueError("Dataset sem perguntas.")
    ids = set()
    for q in perguntas:
        faltando = _CHAVES_OBRIGATORIAS - set(q)
        if faltando:
            raise ValueError(f"Pergunta {q.get('id', '?')} sem chaves: {sorted(faltando)}")
        if q["id"] in ids:
            raise ValueError(f"ID duplicado no dataset: {q['id']}")
        ids.add(q["id"])
        if q["conjunto"] not in ("A", "B"):
            raise ValueError(f"Conjunto inválido em {q['id']}: {q['conjunto']}")
    return dados


def selecionar_perguntas(seletor: str = "all", caminho: str | Path | None = None) -> list[dict]:
    """Seleciona perguntas por `seletor`.

    seletor:
      - "all"                  → todas
      - "A" | "B"              → por conjunto
      - "preco|licitacao|edital|geral" → por categoria
      - "P01,L02,..."          → lista de ids
    """
    perguntas = carregar_dataset(caminho)["perguntas"]
    s = (seletor or "all").strip()
    if s.lower() == "all":
        return perguntas
    if s in ("A", "B"):
        return [q for q in perguntas if q["conjunto"] == s]
    if s.lower() in ("preco", "licitacao", "edital", "geral"):
        return [q for q in perguntas if q["categoria"] == s.lower()]
    ids = {x.strip().upper() for x in s.split(",") if x.strip()}
    selecionadas = [q for q in perguntas if q["id"].upper() in ids]
    if not selecionadas:
        raise ValueError(f"Nenhuma pergunta casou com o seletor: {seletor!r}")
    return selecionadas
