"""stream-json do Claude Code → sequência de ações de navegador e métricas (seção 4.2.3).

Ferramentas de instrumentação (gif_creator, update_plan, tabs_context_mcp) não contam
como ação de navegação. `browser_batch` é expandido nas ações que contém.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from urllib.parse import urldefrag

from validacao.a2_facilitacao import klm
from validacao.claude_chrome import PREFIXO_CHROME, ler_eventos, resultado_final

INSTRUMENTACAO = {"gif_creator", "update_plan", "tabs_context_mcp"}
DOC_RE = re.compile(r"\.(pdf|tif|tiff|docx?|xlsx?|odt)(\?|$)|drive\.google\.com/file|drive\.usercontent", re.I)
URL_RE = re.compile(r"https?://[^\s\"'<>)\]]+")


def _classificar(nome: str, entrada: dict) -> list[dict]:
    """Uma chamada de ferramenta → lista de ações normalizadas."""
    n = nome.replace(PREFIXO_CHROME, "")
    if n in INSTRUMENTACAO:
        return []
    if n.endswith("browser_batch"):
        out = []
        for sub in entrada.get("actions") or entrada.get("calls") or entrada.get("steps") or []:
            if isinstance(sub, dict):
                out += _classificar(sub.get("name") or sub.get("tool") or sub.get("type") or "",
                                    sub.get("input") or sub.get("args") or sub)
        return out
    if n == "navigate":
        url = entrada.get("url") or ""
        if url in ("back", "forward"):
            return [{"tipo": "clicar", "ferramenta": n, "detalhe": url}]
        return [{"tipo": "navegar", "ferramenta": n, "url": url}]
    if n == "computer":
        a = (entrada.get("action") or "").lower()
        if "click" in a or a in ("left_click_drag",):
            return [{"tipo": "clicar", "ferramenta": n, "detalhe": a}]
        if a == "type":
            return [{"tipo": "digitar", "ferramenta": n, "texto": entrada.get("text") or ""}]
        if a == "key":
            return [{"tipo": "tecla", "ferramenta": n, "detalhe": entrada.get("text")}]
        if a in ("scroll", "scroll_to"):
            return [{"tipo": "rolar", "ferramenta": n}]
        if a == "screenshot" or a == "zoom":
            return [{"tipo": "capturar_tela", "ferramenta": n}]
        if a in ("wait", "hover", "mouse_move"):
            return [{"tipo": "outro", "ferramenta": n, "detalhe": a}]
        return [{"tipo": "outro", "ferramenta": n, "detalhe": a}]
    if n == "form_input":
        return [{"tipo": "digitar", "ferramenta": n, "texto": str(entrada.get("value") or "")}]
    if n in ("get_page_text", "read_page", "find"):
        return [{"tipo": "ler_pagina", "ferramenta": n}]
    if n == "tabs_create_mcp":
        return [{"tipo": "clicar", "ferramenta": n, "detalhe": "nova aba"}]
    return [{"tipo": "outro", "ferramenta": n}]


def analisar(caminho_jsonl) -> dict:
    ev = ler_eventos(caminho_jsonl)
    acoes, urls, chars_lidos = [], [], 0
    tool_nomes = {}
    negadas = 0
    for e in ev:
        if e.get("type") == "assistant":
            for c in e.get("message", {}).get("content", []) or []:
                if c.get("type") == "tool_use":
                    tool_nomes[c.get("id")] = c.get("name", "")
                    if c.get("name", "").startswith(PREFIXO_CHROME):
                        novas = _classificar(c["name"], c.get("input") or {})
                        acoes += novas
                        urls += [a["url"] for a in novas if a.get("url")]
        elif e.get("type") == "user":
            for c in e.get("message", {}).get("content", []) or []:
                if not isinstance(c, dict) or c.get("type") != "tool_result":
                    continue
                txt = c.get("content")
                txt = json.dumps(txt, ensure_ascii=False) if not isinstance(txt, str) else txt
                nome = tool_nomes.get(c.get("tool_use_id"), "")
                if c.get("is_error") and "permission" in txt.lower():
                    negadas += 1
                if any(nome.endswith(x) for x in ("get_page_text", "read_page", "find")):
                    chars_lidos += len(txt)
                urls += [u.rstrip(".,;") for u in URL_RE.findall(txt)
                         if "tabId" in txt or nome.endswith("navigate")]
    fin = resultado_final(ev) or {}
    uso = fin.get("usage") or {}
    urls_norm = sorted({urldefrag(u)[0] for u in urls if u.startswith("http")})
    principais = [a for a in acoes if a["tipo"] != "outro"]
    return {
        "acoes": acoes,
        "n_acoes": len(principais),
        "n_acoes_por_tipo": dict(Counter(a["tipo"] for a in principais)),
        "n_paginas": len(urls_norm),
        "paginas": urls_norm,
        "n_documentos": len([u for u in urls_norm if DOC_RE.search(u)]),
        "tokens_entrada": (uso.get("input_tokens") or 0) + (uso.get("cache_read_input_tokens") or 0)
                          + (uso.get("cache_creation_input_tokens") or 0),
        "tokens_saida": uso.get("output_tokens"),
        "turnos": fin.get("num_turns"),
        "custo_usd": fin.get("total_cost_usd"),
        "subtipo_resultado": fin.get("subtype"),
        "texto_final": fin.get("result") or "",
        "tempo_humano_klm_s": klm.tempo_total(principais),
        "chars_lidos": chars_lidos,
        "ferramentas_negadas": negadas + len(fin.get("permission_denials") or []),
        "usou_chat": any("/assistente" in u for u in urls_norm),
    }
