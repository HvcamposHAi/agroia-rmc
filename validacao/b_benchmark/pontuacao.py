"""Pontuação determinística das respostas do benchmark (seção 5.4). Sem LLM como juiz."""

from __future__ import annotations

import json
import re
from types import SimpleNamespace

from validacao.a2_facilitacao.pontuacao import numeros
from validacao.comum import norm_texto

RECUSA_RE = re.compile(
    r"n[aã]o (tenho|possuo|h[aá]|encontrei|existe|consta|disp[oõ]e|est[aá] dispon)|sem dados|fora do (meu )?escopo|"
    r"n[aã]o foi poss[ií]vel (encontrar|localizar)|nenhum (registro|dado|resultado)|n[aã]o (trabalho|atuo) com|"
    r"n[aã]o fa[cç]o parte|n[aã]o posso (ajudar|responder)|n[aã]o cobre|base de dados n[aã]o", re.I)
MENSAGENS_ERRO = ("erro ao processar", "ocorreu um erro", "tente novamente", "muito complexa")


def _tools_schema() -> dict:
    try:
        from chat.tools import TOOLS_SCHEMA
        return {t["name"]: t.get("input_schema", {}) for t in TOOLS_SCHEMA}
    except Exception:
        return {}


_SCHEMAS = None


def argumentos_validos(nome: str, inputs) -> bool:
    global _SCHEMAS
    if _SCHEMAS is None:
        _SCHEMAS = _tools_schema()
    sch = _SCHEMAS.get(nome)
    if sch is None:
        return False
    try:
        import jsonschema
        jsonschema.validate(inputs or {}, sch)
        return True
    except Exception:
        return False


def numeros_relevantes(texto: str) -> list[float]:
    """Números da resposta que carregam dado (exclui anos isolados e inteiros < 10)."""
    out = []
    for v in numeros(texto):
        if 1990 <= v <= 2035 and float(v).is_integer():
            continue
        if abs(v) < 10 and float(v).is_integer():
            continue
        out.append(v)
    return out


def _aparece(v: float, payload: str) -> bool:
    for n in numeros(payload):
        if abs(n - v) <= max(0.01, 0.005 * abs(v)):
            return True
        if abs(round(n, 2) - v) <= 0.01:
            return True
    return False


def recusou(texto: str) -> bool:
    return bool(RECUSA_RE.search(texto or ""))


def pontuar(ch: dict, q: dict, gab: dict, tol_rel: float) -> dict:
    """ch: registro de chamadas.jsonl; q: pergunta do dataset; gab: gabarito da pergunta."""
    from benchmark.metricas import nivel_af
    texto = ch.get("texto") or ""
    tools = ch.get("tools") or []
    nomes = [t["nome"] for t in tools] or list((ch.get("fim") or {}).get("tools_usadas") or [])
    exe = SimpleNamespace(tools_usadas=nomes, tool_calls_detalhe=[{"nome": t["nome"], "inputs": t.get("inputs") or {}}
                                                                   for t in tools], resposta=texto)
    af = nivel_af(exe, q)
    aceitaveis = set(q.get("tools_aceitaveis") or ([q["tool_esperada"]] if q.get("tool_esperada") else []))
    uso_correto = any(t["nome"] in aceitaveis and argumentos_validos(t["nome"], t.get("inputs")) for t in tools) \
        if aceitaveis else len(nomes) == 0
    payload = " ".join(str(t.get("resultado") or "") for t in tools)
    nums = numeros_relevantes(texto)
    sem_origem = [v for v in nums if not _aparece(v, payload)]
    fidelidade = (1 - len(sem_origem) / len(nums)) if nums else None
    infra = ch.get("erro")
    msg_erro = any(m in norm_texto(texto) for m in MENSAGENS_ERRO)

    factual = None
    if gab["tipo"] == "numero":
        factual = any(abs(n - v) <= tol_rel * max(abs(v), 1e-9) for v in gab["valores"] for n in numeros(texto))
    elif gab["tipo"] == "entidades":
        t = norm_texto(texto)
        cit = sum(1 for nome in gab["nomes"] if norm_texto(nome) and norm_texto(nome) in t)
        factual = (cit / len(gab["nomes"])) >= gab.get("limiar", 0.67) if gab["nomes"] else None
    abst = None
    if q["conjunto"] == "B":
        # Definição do pacote benchmark/ (metricas.abstencao_correta): sem ferramenta esperada,
        # basta não chamar ferramenta; nas perguntas de dado inexistente (PAA/PNAE), não
        # apresentar número inventado. Recusa explícita sem número também conta como correta.
        from benchmark.metricas import abstencao_correta
        abst = bool(abstencao_correta(exe, q)) or (recusou(texto) and not numeros_relevantes(texto))
    falsa_abst = (q["conjunto"] == "A" and recusou(texto) and not nums and not infra)

    # Desfecho principal por chamada
    if infra:
        acerto, categoria = False, infra
    elif q["conjunto"] == "B":
        acerto = bool(abst)
        categoria = None if acerto else ("NUMERO_SEM_ORIGEM" if sem_origem else "RESPOSTA_INCORRETA")
    elif factual is not None:
        acerto = bool(factual)
        categoria = None if acerto else _categoria_falha(nomes, aceitaveis, tools, sem_origem, msg_erro)
    else:
        acerto = af > 0
        categoria = None if acerto else _categoria_falha(nomes, aceitaveis, tools, sem_origem, msg_erro)
    return {"af_nivel": af, "uso_correto_ferramenta": bool(uso_correto), "fidelidade_ferramentas": fidelidade,
            "numeros_sem_origem": len(sem_origem), "factual": factual, "abstencao_correta": abst,
            "falsa_abstencao": bool(falsa_abst), "acerto": bool(acerto), "categoria_erro": categoria,
            "desfecho": "CORRETO" if acerto else (categoria or "RESPOSTA_INCORRETA"), "n_tools": len(nomes),
            "tools": nomes}


def _categoria_falha(nomes, aceitaveis, tools, sem_origem, msg_erro) -> str:
    if msg_erro and not nomes:
        return "FORMATO"
    if not nomes:
        return "SEM_FERRAMENTA"
    if aceitaveis and not any(n in aceitaveis for n in nomes):
        return "FERRAMENTA_ERRADA"
    if any(t["nome"] in aceitaveis and not argumentos_validos(t["nome"], t.get("inputs")) for t in tools):
        return "ARGUMENTO_INVALIDO"
    if sem_origem:
        return "NUMERO_SEM_ORIGEM"
    return "RESPOSTA_INCORRETA"


def carregar_chamadas(caminho) -> list[dict]:
    out = {}
    if not caminho.exists():
        return []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if linha.strip():
            r = json.loads(linha)
            out[r["chave"]] = r      # última tentativa por chave prevalece
    return list(out.values())
