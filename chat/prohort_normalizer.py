"""
Dicionário de normalização de nomes de produtos PROHORT → nome canônico.
O PROHORT (coluna dsc_produto) usa variantes como "TOMATE SALADA", "TOMATE ITALIANO".
Este dicionário consolida para o nome que o produtor usa naturalmente.

Chaves comparadas em UPPER + strip. Produtos fora do dicionário caem no fallback
(nome em minúsculas), de modo que a coleta nunca descarta um item por falta de mapeamento.
"""

SINONIMOS: dict[str, str] = {
    # Tomate
    "TOMATE SALADA":       "tomate",
    "TOMATE ITALIANO":     "tomate",
    "TOMATE CEREJA":       "tomate",
    "TOMATE CAQUI":        "tomate",
    "TOMATE":              "tomate",
    # Alface
    "ALFACE CRESPA":       "alface",
    "ALFACE LISA":         "alface",
    "ALFACE AMERICANA":    "alface",
    "ALFACE ROXA":         "alface",
    "ALFACE":              "alface",
    # Cebola
    "CEBOLA NACIONAL":     "cebola",
    "CEBOLA IMPORTADA":    "cebola",
    "CEBOLA":              "cebola",
    # Batata
    "BATATA INGLESA":      "batata",
    "BATATA LAVADA":       "batata",
    "BATATA":              "batata",
    # Cenoura
    "CENOURA":             "cenoura",
    "CENOURA SORTIDA":     "cenoura",
    # Abobrinha
    "ABOBRINHA ITALIANA":  "abobrinha",
    "ABOBRINHA":           "abobrinha",
    # Pimentão
    "PIMENTAO VERDE":      "pimentão",
    "PIMENTAO VERMELHO":   "pimentão",
    "PIMENTAO AMARELO":    "pimentão",
    "PIMENTAO":            "pimentão",
    # Brócolis
    "BROCOLI":             "brócolis",
    "BROCOLIS":            "brócolis",
    # Couve
    "COUVE MANTEIGA":      "couve",
    "COUVE":               "couve",
    # Espinafre
    "ESPINAFRE":           "espinafre",
    # Rúcula
    "RUCULA":              "rúcula",
    # Repolho
    "REPOLHO VERDE":       "repolho",
    "REPOLHO ROXO":        "repolho",
    "REPOLHO":             "repolho",
    # Pepino
    "PEPINO CAIPIRA":      "pepino",
    "PEPINO JAPONES":      "pepino",
    "PEPINO":              "pepino",
    # Feijão vagem
    "FEIJAO VAGEM":        "feijão vagem",
    "VAGEM":               "feijão vagem",
    "VAGEM MACARRAO":      "feijão vagem",
    # Banana
    "BANANA PRATA":        "banana",
    "BANANA NANICA":       "banana",
    "BANANA DA TERRA":     "banana",
    "BANANA":              "banana",
    # Maçã
    "MACA NACIONAL":       "maçã",
    "MACA":                "maçã",
    # Laranja
    "LARANJA PERA":        "laranja",
    "LARANJA BAHIA":       "laranja",
    "LARANJA":             "laranja",
    # Limão
    "LIMAO TAITI":         "limão",
    "LIMAO SICILIANO":     "limão",
    "LIMAO":               "limão",
    # Mandioca
    "MANDIOCA":            "mandioca",
    "AIPIM":               "mandioca",
    # Milho
    "MILHO VERDE":         "milho verde",
    # Beterraba
    "BETERRABA":           "beterraba",
    # Chuchu
    "CHUCHU":              "chuchu",
}


def normalizar_produto(nome_prohort: str) -> str:
    """Retorna o nome canônico do produto dado o nome bruto do PROHORT (dsc_produto)."""
    if not nome_prohort:
        return ""
    chave = nome_prohort.strip().upper()
    return SINONIMOS.get(chave, nome_prohort.strip().lower())
