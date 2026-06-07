"""Query Agent — expansão de consulta alinhada ao vocabulário do banco.

NOVO ARQUIVO — síncrono, sem dependências async. Não modifica nada existente.

Baseado em Nachimovsky et al. (2025) — separação de papéis de agentes — e
Yang et al. (2025, AQE) — expansão alinhada ao objetivo de recuperação.

Responsabilidade: receber a pergunta bruta do usuário e produzir intenção
detectada, termos canônicos (via tabela `sinonimos_agricolas`), filtros
implícitos (ano, canal) e um "hint" curto que é injetado no contexto do
agente de chat para orientar a escolha de filtros nos tools EXISTENTES
(`query_itens_agro`, `query_licitacoes`, `prohort_*`...).

Degradação graciosa: qualquer falha (banco fora, tabela vazia) resulta em
expansão vazia — o fluxo de chat segue normalmente com a pergunta original.
"""

import time
from datetime import datetime
from typing import TypedDict

from chat.db import get_supabase_client


class QueryExpansion(TypedDict):
    consulta_original: str
    intencao: str                  # 'preco' | 'licitacao' | 'edital' | 'geral'
    termos_expandidos: list[dict]  # [{"original","canonico","tabela","coluna","match"}]
    filtros_sugeridos: dict        # {"ano": 2026, "canal": "PNAE"}
    contexto_hint: str             # string curta injetada no chat (vazia se nada a sugerir)
    latencia_ms: int


# Sinais textuais por intenção (contagem simples — sem LLM, 100% local)
INTENCOES = {
    "preco": ["preço", "preco", "valor", "cotação", "cotacao", "quanto custa",
              "quanto esta", "quanto está", "ceasa", "prohort", "mercado"],
    "licitacao": ["comprou", "compra", "comprado", "licitação", "licitacao",
                  "volume", "kg", "quilos", "adquiriu", "aquisição", "aquisicao",
                  "demanda", "licitou", "licitado"],
    "edital": ["edital", "chamamento", "processo", "publicado", "publicação",
               "publicacao", "resultado", "credenciamento", "abertura"],
}


def expandir_consulta(consulta: str) -> QueryExpansion:
    """Expande e estrutura a consulta do usuário. Nunca lança exceção."""
    inicio = time.time()
    consulta = consulta or ""
    c = consulta.lower().strip()

    intencao = _detectar_intencao(c)
    termos = _buscar_sinonimos(c)
    filtros = _extrair_filtros(c, termos)
    hint = _montar_hint(termos, filtros, intencao)

    return QueryExpansion(
        consulta_original=consulta,
        intencao=intencao,
        termos_expandidos=termos,
        filtros_sugeridos=filtros,
        contexto_hint=hint,
        latencia_ms=int((time.time() - inicio) * 1000),
    )


def _detectar_intencao(c: str) -> str:
    """Detecta a intenção dominante por contagem de sinais."""
    pontuacao = {intencao: 0 for intencao in INTENCOES}
    for intencao, sinais in INTENCOES.items():
        for sinal in sinais:
            if sinal in c:
                pontuacao[intencao] += 1
    melhor = max(pontuacao, key=pontuacao.get)
    return melhor if pontuacao[melhor] > 0 else "geral"


def _buscar_sinonimos(c: str) -> list[dict]:
    """Busca na tabela sinonimos_agricolas os termos presentes na consulta.

    Falha silenciosa: retorna [] se o banco estiver indisponível (F-01).
    """
    try:
        sb = get_supabase_client()
        rows = (
            sb.table("sinonimos_agricolas")
            .select("termo_usuario,termo_canonico,tabela_alvo,coluna_alvo,tipo_match")
            .eq("ativo", True)
            .execute()
            .data
            or []
        )
    except Exception:
        return []

    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for s in rows:
        termo = (s.get("termo_usuario") or "").lower()
        if termo and termo in c:
            chave = (s.get("coluna_alvo", ""), s.get("termo_canonico", ""))
            if chave not in seen:
                seen.add(chave)
                out.append({
                    "original": s.get("termo_usuario"),
                    "canonico": s.get("termo_canonico"),
                    "tabela": s.get("tabela_alvo"),
                    "coluna": s.get("coluna_alvo"),
                    "match": s.get("tipo_match"),
                })
    return out


def _extrair_filtros(c: str, termos: list[dict]) -> dict:
    """Extrai filtros implícitos: temporal (ano) e canal institucional."""
    filtros: dict = {}
    ano_atual = datetime.now().year

    if "este ano" in c or "esse ano" in c or str(ano_atual) in c:
        filtros["ano"] = ano_atual
    elif "ano passado" in c or "ano anterior" in c:
        filtros["ano"] = ano_atual - 1
    else:
        # Captura um ano explícito de 4 dígitos no intervalo plausível
        for token in c.replace("/", " ").replace("-", " ").split():
            if token.isdigit() and len(token) == 4 and 2018 <= int(token) <= ano_atual + 1:
                filtros["ano"] = int(token)
                break

    for t in termos:
        if t.get("coluna") == "canal" and "canal" not in filtros:
            filtros["canal"] = t.get("canonico")

    return filtros


def _montar_hint(termos: list[dict], filtros: dict, intencao: str) -> str:
    """Monta um hint curto e rotulado, sem inflar o contexto do LLM."""
    if not termos and not filtros:
        return ""

    culturas = sorted({t.get("canonico") for t in termos if t.get("coluna") == "cultura"})
    partes = [f"intenção={intencao}"]
    if culturas:
        partes.append("culturas=" + ", ".join(c for c in culturas[:5] if c))
    if "canal" in filtros:
        partes.append("canal=" + str(filtros["canal"]))
    if "ano" in filtros:
        partes.append("ano=" + str(filtros["ano"]))

    return "[contexto do sistema p/ escolha de filtros nos tools: " + "; ".join(partes) + "]"
