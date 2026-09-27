"""Keystroke-Level Model (CARD; MORAN; NEWELL, 1980): tempo humano estimado de operação.

Operadores (tempos do artigo original): K = 0,28 s (digitador médio), P = 1,1 s,
B = 0,1 s (pressionar ou soltar), H = 0,4 s, M = 1,35 s.

Mapeamento das ações do agente:
  clicar                   → M + P + B + B
  digitar n caracteres     → M + H + n·K + H
  navegar (URL digitada)   → M + H + len(URL)·K + H
  tecla (Enter, Tab, ...)  → K
  rolar                    → P + B + B (por evento)
  ler página               → fora do KLM (reportado como volume de texto lido)

O resultado é uma estimativa de LIMITE INFERIOR do tempo humano de operação.
"""

from __future__ import annotations

K, P, B, H, M = 0.28, 1.1, 0.1, 0.4, 1.35

OPERADORES = {"K": K, "P": P, "B": B, "H": H, "M": M}


def tempo_acao(acao: dict) -> float:
    t = acao.get("tipo")
    if t == "clicar":
        return M + P + 2 * B
    if t == "digitar":
        return M + H + len(acao.get("texto") or "") * K + H
    if t == "navegar":
        return M + H + len(acao.get("url") or "") * K + H
    if t == "tecla":
        return K
    if t == "rolar":
        return P + 2 * B
    return 0.0


def tempo_total(acoes: list[dict]) -> float:
    return round(sum(tempo_acao(a) for a in acoes), 2)
