"""Indicadores da pauta do Sacolão e do planejamento de safra (plano v3, E5).

Funções PURAS (sem banco, sem pandas): a API importa este módulo e o build da API
não tem pandas/numpy (requirements-api.txt). Séries mensais entram como
{'AAAA-MM': preço}; quem chama decide a agregação (mediana do mês) e a deflação.

  variacao_mensal / variacao_anual   variação % contra o mês anterior / mesmo mês do ano anterior
  indicador_anomalia_fao             anomalia de preço (método FAO, ODS 2.c.1)
  indice_sazonal                     índice por mês do ano (preço ÷ média do ano, mediana entre anos)
  cobertura_subgrupo                 espécies com preço × mínimo do subgrupo (Portaria nº 175)
  acima_do_teto                      espécies acima do preço máximo (Art. 7º)
  comparar_ceasas                    ranking de CEASAs pela mediana recente, com exclusões e aviso de frete
"""

from __future__ import annotations

from datetime import date, timedelta
from statistics import mean, median, pstdev

# ── Método FAO (indicador ODS 2.c.1) ─────────────────────────────────────────
PESO_TRIMESTRAL = 0.4        # peso da taxa de crescimento composto trimestral (CQGR)
PESO_ANUAL = 0.6             # peso da taxa de crescimento composto anual (CAGR)
LIMIAR_MODERADO = 0.5        # índice ≥ 0,5: moderadamente alto
LIMIAR_ANORMAL = 1.0         # índice ≥ 1: anormalmente alto
MIN_MESES_HISTORICO = 60     # 5 anos de série
MAX_LACUNA_MESES = 3         # lacuna maior exclui a série (regra FAO; integridade I5)
MIN_ANOS_PADRAO = 3          # observações do mesmo mês para estimar média e desvio

# ── Índice sazonal e comparação ──────────────────────────────────────────────
MIN_MESES_ANO = 10           # ano com menos meses distorce a média anual
MIN_ANOS_CONFIAVEL = 3
JANELA_COMPARACAO_DIAS = 30
FRESCOR_DIAS = 15
AVISO_FRETE = ("Diferença bruta de preço entre CEASAs: não desconta frete, perdas nem custo de "
               "acesso ao box da CEASA de destino.")


# ── Utilidades de mês ────────────────────────────────────────────────────────

def _mes(chave: str) -> tuple[int, int]:
    ano, mes = chave.split("-")[:2]
    return int(ano), int(mes)


def _chave(ano: int, mes: int) -> str:
    return f"{ano:04d}-{mes:02d}"


def _deslocar(chave: str, meses: int) -> str:
    ano, mes = _mes(chave)
    k = ano * 12 + (mes - 1) + meses
    return _chave(k // 12, k % 12 + 1)


def _indice_mes(chave: str) -> int:
    ano, mes = _mes(chave)
    return ano * 12 + mes - 1


def _valor(serie: dict, chave: str) -> float | None:
    v = serie.get(chave)
    return v if v is not None and v > 0 else None


# ── Variação ─────────────────────────────────────────────────────────────────

def _variacao(atual: float | None, anterior: float | None) -> float | None:
    if atual is None or anterior is None:
        return None
    return (atual / anterior - 1) * 100


def variacao_mensal(serie: dict, mes: str) -> float | None:
    """Variação % do mês contra o mês anterior; None sem algum dos dois."""
    return _variacao(_valor(serie, mes), _valor(serie, _deslocar(mes, -1)))


def variacao_anual(serie: dict, mes: str) -> float | None:
    """Variação % do mês contra o mesmo mês do ano anterior; None sem algum dos dois."""
    return _variacao(_valor(serie, mes), _valor(serie, _deslocar(mes, -12)))


# ── Anomalia de preço (FAO) ──────────────────────────────────────────────────

def _crescimento(serie: dict, mes: str, defasagem: int) -> float | None:
    """Taxa de crescimento composto mensal entre mes-defasagem e mes."""
    p, p0 = _valor(serie, mes), _valor(serie, _deslocar(mes, -defasagem))
    if p is None or p0 is None:
        return None
    return (p / p0) ** (1 / defasagem) - 1


def _maior_lacuna(serie: dict, ate: str) -> int:
    meses = sorted(_indice_mes(k) for k in serie if _valor(serie, k) and k <= ate)
    return max((b - a - 1 for a, b in zip(meses, meses[1:])), default=0)


def _z(serie: dict, mes: str, defasagem: int) -> float | None:
    atual = _crescimento(serie, mes, defasagem)
    ano, m = _mes(mes)
    historico = [g for a in range(ano - 1, ano - 100, -1)
                 if (g := _crescimento(serie, _chave(a, m), defasagem)) is not None]
    if atual is None or len(historico) < MIN_ANOS_PADRAO:
        return None
    desvio = pstdev(historico)
    if desvio == 0:
        return None
    return (atual - mean(historico)) / desvio


def classificar_anomalia(indice: float) -> str:
    if indice >= LIMIAR_ANORMAL:
        return "anormalmente_alto"
    if indice >= LIMIAR_MODERADO:
        return "moderadamente_alto"
    if indice <= -LIMIAR_MODERADO:
        return "baixo"
    return "normal"


def indicador_anomalia_fao(serie: dict, mes: str) -> dict:
    """Índice de anomalia de preço (IPA) da FAO para `mes`.

    IPA = 0,4·z(CQGR) + 0,6·z(CAGR), em que cada taxa de crescimento composto é padronizada
    pela média e pelo desvio-padrão da mesma taxa no MESMO mês dos anos anteriores.
    A série deve vir em preços reais (deflacionada pelo IPCA) — responsabilidade de quem chama.
    Simplificação documentada: média e desvio sem os pesos temporais da FAO.
    """
    def indisponivel(motivo: str) -> dict:
        return {"disponivel": False, "indice": None, "classe": "indisponivel", "motivo": motivo}

    validos = [k for k in serie if _valor(serie, k) and k <= mes]
    if not validos:
        return indisponivel("série vazia")
    meses_historico = _indice_mes(mes) - _indice_mes(min(validos)) + 1
    if meses_historico < MIN_MESES_HISTORICO:
        return indisponivel(f"histórico de {meses_historico} meses; o método exige "
                            f"{MIN_MESES_HISTORICO} (5 anos)")
    lacuna = _maior_lacuna(serie, mes)
    if lacuna > MAX_LACUNA_MESES:
        return indisponivel(f"lacuna de {lacuna} meses seguidos na série")
    z_tri, z_anual = _z(serie, mes, 3), _z(serie, mes, 12)
    if z_tri is None or z_anual is None:
        return indisponivel("sem preço no mês de referência ou histórico insuficiente do mesmo mês")
    indice = PESO_TRIMESTRAL * z_tri + PESO_ANUAL * z_anual
    return {"disponivel": True, "indice": indice, "classe": classificar_anomalia(indice),
            "z_trimestral": z_tri, "z_anual": z_anual, "motivo": None}


# ── Índice sazonal ───────────────────────────────────────────────────────────

def indice_sazonal(serie: dict) -> dict[int, dict]:
    """{mês 1..12: {'indice', 'anos', 'confiavel'}}.

    Dentro de cada ano: preço do mês ÷ média do ano (remove a inflação entre anos sem
    deflator); entre anos: mediana. Anos com menos de MIN_MESES_ANO meses ficam fora.
    """
    por_ano: dict[int, dict[int, float]] = {}
    for chave, preco in serie.items():
        if preco is not None and preco > 0:
            ano, mes = _mes(chave)
            por_ano.setdefault(ano, {})[mes] = preco
    razoes: dict[int, list[float]] = {m: [] for m in range(1, 13)}
    for meses in por_ano.values():
        if len(meses) < MIN_MESES_ANO:
            continue
        media_ano = mean(meses.values())
        for mes, preco in meses.items():
            razoes[mes].append(preco / media_ano)
    return {m: {"indice": median(r) if r else None, "anos": len(r),
                "confiavel": len(r) >= MIN_ANOS_CONFIAVEL}
            for m, r in razoes.items()}


# ── Portaria nº 175: mínimos (Art. 3º) e teto (Art. 7º) ──────────────────────

def cobertura_subgrupo(precos: list[float | None], minimo: int) -> dict:
    """Quantas espécies do subgrupo têm preço e se isso atende ao mínimo exigido."""
    com_preco = sum(1 for p in precos if p is not None and p > 0)
    return {"com_preco": com_preco, "minimo": minimo, "atende": com_preco >= minimo}


def acima_do_teto(itens: list[dict], teto: float) -> list[dict]:
    """Itens com preço ESTRITAMENTE acima do teto; sem preço não entra. Ordem preservada."""
    return [i for i in itens if i.get("preco") is not None and i["preco"] > teto]


# ── Comparação entre CEASAs ──────────────────────────────────────────────────

def _data(d) -> date:
    return d if isinstance(d, date) else date.fromisoformat(str(d)[:10])


def comparar_ceasas(cotacoes: list[dict], hoje: date, unidade: str,
                    janela_dias: int = JANELA_COMPARACAO_DIAS,
                    frescor_dias: int = FRESCOR_DIAS) -> dict:
    """Ranking decrescente das CEASAs pela mediana dos últimos `janela_dias`.

    Exclui (com motivo) CEASA sem cotação na unidade pedida e CEASA cuja última cotação
    tem mais de `frescor_dias`. cotacoes: [{'ceasa', 'unidade', 'data', 'preco'}].
    """
    inicio = hoje - timedelta(days=janela_dias - 1)
    por_ceasa: dict[str, list[dict]] = {}
    for c in cotacoes:
        if c.get("preco") is not None and c["preco"] > 0:
            por_ceasa.setdefault(c["ceasa"], []).append(c)

    ranking, excluidas = [], []
    for ceasa, linhas in sorted(por_ceasa.items()):
        mesma_un = [c for c in linhas if c["unidade"] == unidade]
        if not mesma_un:
            outras = ", ".join(sorted({c["unidade"] for c in linhas}))
            excluidas.append({"ceasa": ceasa, "motivo": f"cotada em {outras}, não em {unidade}"})
            continue
        ultima = max(_data(c["data"]) for c in mesma_un)
        atraso = (hoje - ultima).days
        if atraso > frescor_dias:
            excluidas.append({"ceasa": ceasa, "motivo": f"sem cotação há {atraso} dias "
                                                        f"(última em {ultima.isoformat()})"})
            continue
        janela = [c["preco"] for c in mesma_un if inicio <= _data(c["data"]) <= hoje]
        ranking.append({"ceasa": ceasa, "mediana": median(janela), "cotacoes": len(janela),
                        "ultima_data": ultima.isoformat()})
    ranking.sort(key=lambda x: (-x["mediana"], x["ceasa"]))
    return {"unidade": unidade, "ranking": ranking, "excluidas": excluidas,
            "aviso_frete": AVISO_FRETE}


__all__ = [
    "PESO_TRIMESTRAL", "PESO_ANUAL", "LIMIAR_MODERADO", "LIMIAR_ANORMAL", "AVISO_FRETE",
    "variacao_mensal", "variacao_anual", "indicador_anomalia_fao", "classificar_anomalia",
    "indice_sazonal", "cobertura_subgrupo", "acima_do_teto", "comparar_ceasas",
]
