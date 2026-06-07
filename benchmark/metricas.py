"""Métricas do benchmark: AF@k, abstenção, percentis de latência e consistência.

AF@k (Acurácia de Ferramenta Top-K): a tool esperada aparece nas PRIMEIRAS k
chamadas E os parâmetros críticos batem na primeira ocorrência dessa tool.
Para perguntas de conjunto B com tool_esperada=null, vale a ABSTENÇÃO correta.
"""

from __future__ import annotations

import unicodedata


# ---------------------------------------------------------------------------
# Normalização (acento-insensível) p/ comparar valores de texto livre
# ---------------------------------------------------------------------------
def _norm(texto) -> str:
    s = str(texto or "").strip().lower()
    nfd = unicodedata.normalize("NFD", s)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def _params_batem(tool_calls_detalhe: list[dict], gabarito: dict, k: int) -> bool:
    """Verifica se os parametros_criticos batem na 1ª chamada da tool esperada (top-k)."""
    criticos = gabarito.get("parametros_criticos", [])
    if not criticos:
        return True  # sem param crítico → basta acertar a tool
    aceitaveis = set(gabarito.get("tools_aceitaveis") or [gabarito.get("tool_esperada")])
    esperados = gabarito.get("parametros_esperados", {})

    for tc in tool_calls_detalhe[:k]:
        if tc.get("nome") in aceitaveis:
            inputs = tc.get("inputs", {}) or {}
            ok = True
            for chave in criticos:
                esperado = esperados.get(chave)
                fornecido = inputs.get(chave)
                if isinstance(esperado, int):
                    ok = ok and (_to_int(fornecido) == esperado)
                else:
                    # match acento/caixa-insensível por substring (testa intenção)
                    e, f = _norm(esperado), _norm(fornecido)
                    ok = ok and bool(e) and (e in f or f in e)
            return ok
    return False


def _to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def nivel_af(execucao, gabarito: dict) -> int:
    """Retorna o nível AF atingido: 1, 2, 3 ou 0 (falha).

    `execucao` é um ExecucaoResultado (usa .tools_usadas e .tool_calls_detalhe).
    Para tool_esperada=None (abstenção), 1 se nenhuma tool foi chamada, senão 0.
    """
    tool_esperada = gabarito.get("tool_esperada")
    tools_usadas = list(getattr(execucao, "tools_usadas", []) or [])

    if tool_esperada is None:
        return 1 if len(tools_usadas) == 0 else 0

    aceitaveis = set(gabarito.get("tools_aceitaveis") or [tool_esperada])
    detalhe = getattr(execucao, "tool_calls_detalhe", []) or []
    for k in (1, 2, 3):
        primeiras = tools_usadas[:k]
        if any(t in aceitaveis for t in primeiras) and _params_batem(detalhe, gabarito, k):
            return k
    return 0


def af_param_strict(execucao, gabarito: dict) -> bool:
    """True quando a tool certa foi chamada mas os params críticos NÃO bateram."""
    tool_esperada = gabarito.get("tool_esperada")
    if tool_esperada is None:
        return False
    aceitaveis = set(gabarito.get("tools_aceitaveis") or [tool_esperada])
    tools_usadas = list(getattr(execucao, "tools_usadas", []) or [])
    chamou_certo = any(t in aceitaveis for t in tools_usadas)
    return chamou_certo and nivel_af(execucao, gabarito) == 0


def abstencao_correta(execucao, gabarito: dict) -> bool:
    """Para conjunto B: motor não chamou tool (ou só recusou)."""
    if gabarito.get("conjunto") != "B":
        return False
    if gabarito.get("tool_esperada") is None:
        return len(getattr(execucao, "tools_usadas", []) or []) == 0
    # caso PAA/vazio: correto se NÃO alucinou número (heurística: sem dígitos longos)
    resp = getattr(execucao, "resposta", "") or ""
    return not _tem_numero_grande(resp)


def _tem_numero_grande(texto: str) -> bool:
    """Heurística: presença de número com 3+ dígitos sugere dado 'inventado'."""
    import re
    return bool(re.search(r"\d[\d.,]{2,}", texto))


# ---------------------------------------------------------------------------
# Percentis de latência — MESMA fórmula de scripts/coletar_baseline.py
# ---------------------------------------------------------------------------
def percentis(latencias_ms: list[float]) -> dict:
    vals = sorted(float(x) for x in latencias_ms if x is not None)
    n = len(vals)
    if n == 0:
        return {"p50_ms": 0, "p95_ms": 0, "media_ms": 0, "dp_ms": 0, "n": 0}
    p50 = vals[int(n * 0.5)]
    p95 = vals[min(int(n * 0.95), n - 1)]
    media = sum(vals) / n
    dp = (sum((x - media) ** 2 for x in vals) / n) ** 0.5
    return {
        "p50_ms": round(p50, 1), "p95_ms": round(p95, 1),
        "media_ms": round(media, 1), "dp_ms": round(dp, 1), "n": n,
    }


# ---------------------------------------------------------------------------
# Consistência: similaridade cosseno média par-a-par das N respostas
# ---------------------------------------------------------------------------
_MODELO_EMBED = None
_MODELO_NOME = "paraphrase-multilingual-MiniLM-L12-v2"  # melhor p/ PT que all-MiniLM-L6-v2


def _get_modelo_embed():
    global _MODELO_EMBED
    if _MODELO_EMBED is None:
        from sentence_transformers import SentenceTransformer
        _MODELO_EMBED = SentenceTransformer(_MODELO_NOME)
    return _MODELO_EMBED


def consistencia(respostas: list[str]) -> float:
    """Similaridade cosseno média par-a-par ∈ [0,1] (1.0 = alta consistência).

    Requer >= 2 respostas. Retorna 1.0 para 0/1 resposta (nada a comparar).
    """
    from itertools import combinations
    textos = [r for r in respostas if r and r.strip()]
    if len(textos) < 2:
        return 1.0
    modelo = _get_modelo_embed()
    emb = modelo.encode(textos, normalize_embeddings=True)
    sims = [float((emb[i] * emb[j]).sum()) for i, j in combinations(range(len(emb)), 2)]
    return round(sum(sims) / len(sims), 4) if sims else 1.0
