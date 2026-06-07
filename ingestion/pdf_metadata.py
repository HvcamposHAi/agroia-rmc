"""Helpers puros de extração de metadados de chunks de editais.

NOVO ARQUIVO — funções determinísticas, testáveis offline (sem DB, sem rede).
Usado por `indexar_pdfs.py` para enriquecer os registros de `pdf_chunks` com:
`culturas_mencionadas`, `ano_referencia`, `canal`, `tipo_documento`.

Importante (decisão de plano F-09): o `canal` autoritativo de cada documento
vem do JOIN `processo -> licitacoes.canal` feito no pipeline de indexação.
`inferir_canal()` aqui é apenas um FALLBACK heurístico para quando o canal
não está disponível via banco — nunca deve sobrescrever o valor do banco.
"""

import re

# Vocabulário de culturas — forma EXATA (com acento) de itens_licitacao.cultura,
# verificada contra os valores DISTINCT reais do banco. Mantém a coerência com a
# coluna culturas_mencionadas (que deve refletir o domínio de itens_licitacao).
CULTURAS_VOCABULARIO = [
    "ABACATE", "ABACAXI", "ABÓBORA", "ABOBRINHA", "AGRIÃO", "ALFACE", "ALHO",
    "AMEIXA", "BANANA", "BATATA", "BERINJELA", "BETERRABA", "BRÓCOLIS", "CAQUI",
    "CEBOLINHA", "CEBOLA", "CENOURA", "CHUCHU", "COENTRO", "COUVE", "ERVILHA",
    "ESPINAFRE", "FIGO", "GOIABA", "HORTELÃ", "INHAME", "JILÓ", "KIWI", "LARANJA",
    "LIMÃO", "MAÇÃ", "MAMÃO", "MANDIOCA", "MANGA", "MARACUJÁ", "MELANCIA", "MELÃO",
    "MORANGO", "PEPINO", "PÊSSEGO", "PERA", "PIMENTÃO", "PIMENTA", "QUIABO",
    "RABANETE", "REPOLHO", "RÚCULA", "TANGERINA", "TOMATE", "UVA", "VAGEM",
]

# Canais institucionais reais (licitacoes.canal). Valores DISTINCT no banco:
# ARMAZEM_FAMILIA, BANCO_ALIMENTOS, MESA_SOLIDARIA, OUTRO. Não há PNAE/PAA neste
# escopo (SMSAN/FAAC), por isso não constam aqui. O canal autoritativo vem do
# JOIN processo->licitacoes; este mapa é só fallback heurístico.
CANAL_SINAIS = {
    "ARMAZEM_FAMILIA": ["armazém da família", "armazem da familia", "armazém da familia"],
    "BANCO_ALIMENTOS": ["banco de alimentos", "banco de alimento"],
    "MESA_SOLIDARIA": ["mesa solidária", "mesa solidaria"],
}

PATTERN_ANO = re.compile(r"\b(20[12]\d)\b")
PATTERN_DATA = re.compile(r"\b(\d{2}/\d{2}/(20\d{2}))\b")


def identificar_culturas_no_chunk(chunk: str) -> list[str]:
    """Retorna a lista (sem duplicatas) de culturas mencionadas no chunk."""
    if not chunk:
        return []
    chunk_upper = chunk.upper()
    encontradas = []
    for cultura in CULTURAS_VOCABULARIO:
        if cultura in chunk_upper and cultura not in encontradas:
            encontradas.append(cultura)
    return encontradas


def inferir_ano(texto: str) -> int | None:
    """Infere o ano de referência. Prioriza data dd/mm/aaaa; senão ano isolado."""
    if not texto:
        return None
    cabecalho = texto[:3000]
    m_data = PATTERN_DATA.search(cabecalho)
    if m_data:
        return int(m_data.group(2))
    m_ano = PATTERN_ANO.search(cabecalho)
    if m_ano:
        return int(m_ano.group(1))
    return None


def inferir_canal(texto: str) -> str | None:
    """FALLBACK heurístico para canal a partir do texto do edital.

    Só deve ser usado quando o canal do banco (via processo->licitacoes) é nulo.
    """
    if not texto:
        return None
    t = texto.lower()
    for canal, sinais in CANAL_SINAIS.items():
        if any(s in t for s in sinais):
            return canal
    return None


def inferir_tipo_documento(nome_arquivo: str, texto: str) -> str:
    """Infere tipo do documento: 'edital', 'cartilha_faep', 'idr' ou 'documento_geral'."""
    nome = (nome_arquivo or "").lower()
    cab = (texto or "")[:500].lower()
    alvo = nome + " " + cab
    if any(t in alvo for t in ["edital", "chamamento", "licitação", "licitacao", "pregão", "pregao", "dispensa"]):
        return "edital"
    if any(t in alvo for t in ["cartilha", "faep", "manual"]):
        return "cartilha_faep"
    if any(t in alvo for t in ["idr", "emater", "técnico", "tecnico"]):
        return "idr"
    return "documento_geral"
