"""Pauta de referência do Sacolão da Família e do Sacolão Móvel — Portaria SMSAN nº 175/2026.

Fonte única em código (plano v3, E2). Transcrito do Anexo I da versão publicada no Diário
Oficial Eletrônico nº 159, de 26/08/2026 (republicação: a do DOM nº 156, de 21/08/2026, saiu
sem o anexo). Cópia oficial em docs/legislacao/portaria_smsan_175_26-08-2026_DOM159.pdf.

Estrutura do anexo: 2 estações × 5 subgrupos; cada subgrupo tem um mínimo de espécies que a
unidade deve ofertar (soma 26 por estação) e uma lista de espécies CANDIDATAS (43 por estação).
O título "26 espécies" do anexo é a soma dos mínimos, não o tamanho da lista.

Cada linha guarda `texto_original` exatamente como no anexo; quando a leitura exigiu
interpretação, `observacao` explica. As leituras foram conferidas no calendário oficial de
comercialização da CEASA-PR, unidade Curitiba (a pauta é definida pela oferta na CEASA-Curitiba);
`validar_smsan` = True só sobra para o que nenhuma fonte oficial resolve.
Python puro: importado pela API (sem pandas).
"""

from __future__ import annotations

ATO = {
    "id": "smsan-175-2026",
    "ato": "Portaria 175",
    "orgao": "SMSAN",
    "numero": 175,
    "ano": 2026,
    "data": "2026-08-26",
    "diario_oficial": 159,
    "republicacao_de": {"diario_oficial": 156, "data": "2026-08-21"},
    "sumula": ("Estabelece pauta de referência de produtos nas Unidades de Abastecimento dos "
               "Programas Sacolão da Família e Sacolão Móvel."),
    "fonte": ("https://legisladocexterno.curitiba.pr.gov.br/AtosConsultaExternaDownload.aspx"
              "?Id=477144&tipo=ass"),
}

OUTONO_INVERNO = "outono_inverno"
PRIMAVERA_VERAO = "primavera_verao"

# (ordem, grupo, subgrupo) — mesma ordem e nomes do anexo; o Art. 7º usa os mesmos subgrupos
SUBGRUPOS = [
    (1, "Hortaliças", "Hortaliças Herbáceas (folhosas)"),
    (2, "Hortaliças", "Hortaliças Frutos"),
    (3, "Hortaliças", "Hortaliças Raízes, tuberosas e bulbos"),
    (4, "Frutas", "Frutas"),
    (5, "Frutas", "Frutas Cítricas"),
]

# estação → ordem do subgrupo → mínimo de espécies
MINIMOS = {
    OUTONO_INVERNO: {1: 5, 2: 2, 3: 10, 4: 6, 5: 3},
    PRIMAVERA_VERAO: {1: 3, 2: 6, 3: 3, 4: 12, 5: 2},
}

_CAL = "calendário oficial da CEASA-PR (Curitiba)"
_ESPECIE_DUPLA = f"lida como duas espécies separadas por 'e'; o {_CAL} lista as duas separadas"
_MIMOSA = ("'mimosa' aparece sozinha na lista de cítricas; o " + _CAL + " lista 'Tangerina "
           "Mimosa/Comum' (mexerica) — confirmado; antes interpretada como tangerina mimosa "
           "(mexerica)")
_MURCOTE = f"grafia do anexo 'murcot'; o {_CAL} lista 'Tangerina Murcot' — confirmado"

# estação → ordem do subgrupo → [(especie, variedade, texto_original, observacao)]
_ANEXO = {
    OUTONO_INVERNO: {
        1: [("alface", None, "Alface", None),
            ("alho-poró", None, "alho poró", None),
            ("agrião", None, "agrião", None),
            ("almeirão", None, "almeirão", None),
            ("couve-flor", None, "couve-flor", f"brássica entre as folhosas, como no {_CAL} (Hortaliças Folhosas) — confirmado"),
            ("brócolis", None, "couve- brócolis", f"anexo grafa 'couve- brócolis'; o {_CAL} lista 'Brócolis' entre as Hortaliças Folhosas — confirmado"),
            ("couve", None, "couve", "o anexo traz um item vazio logo depois (', ,'), ignorado"),
            ("couve chinesa", None, "couve chinesa", None),
            ("cheiro-verde", None, "cheiro-verde", None),
            ("escarola", None, "escarola", None),
            ("espinafre", None, "espinafre", None),
            ("mostarda", None, "mostarda", None),
            ("rúcula", None, "rúcula", None)],
        2: [("abóbora", None, "Abóbora", None),
            ("chuchu", None, "chuchu", None),
            ("ervilha", None, "ervilha", None)],
        3: [("aipim", None, "Aipim", None),
            ("batata", None, "batata", None),
            ("batata-doce", None, "batata-doce", None),
            ("beterraba", None, "beterraba", None),
            ("cará", None, "cará", None),
            ("cenoura", None, "cenoura", None),
            ("cebola", None, "cebola", None),
            ("inhame", None, "inhame", None),
            ("nabo", None, "nabo e mandioquinha-salsa", _ESPECIE_DUPLA),
            ("mandioquinha-salsa", None, "nabo e mandioquinha-salsa", _ESPECIE_DUPLA),
            ("rabanete", None, "rabanete", None)],
        4: [("abacate", None, "Abacate", None),
            ("banana", None, "banana", None),
            ("caqui", None, "caqui", None),
            ("carambola", None, "ca r am bo la", "espaçamento do PDF corrigido"),
            ("kiwi", None, "kiwi", None),
            ("maçã", None, "maçã", None),
            ("mamão", None, "mamão", None),
            ("maracujá", None, "maracujá", None),
            ("melão", None, "melão", None)],
        5: [("laranja", "pera", "Laranja pera", None),
            ("laranja", "lima", "laranja lima", None),
            ("limão", "rosa", "limão rosa", None),
            ("limão", "tahiti", "limão tahiti", None),
            ("tangerina", "ponkan", "tangerina ponkan", None),
            ("tangerina", "mimosa", "mimosa", _MIMOSA),
            ("tangerina", "murcote", "murcot", "lida como tangerina; " + _MURCOTE)],
    },
    PRIMAVERA_VERAO: {
        1: [("alface", None, "Alface", None),
            ("agrião", None, "agrião", None),
            ("cheiro-verde", None, "cheiro verde", None),
            ("escarola", None, "escarola", None),
            ("almeirão", None, "almeirão", None),
            ("couve", None, "couve", None),
            ("repolho", None, "repolho", f"brássica entre as folhosas, como no {_CAL} (Hortaliças Folhosas) — confirmado")],
        2: [("abobrinha", None, "Abobrinha", None),
            ("berinjela", None, "berinjela", None),
            ("feijão-vagem", None, "feijão vagem", None),
            ("quiabo", None, "quiabo", None),
            ("maxixe", None, "maxixe", None),
            ("milho-verde", None, "milho verde", None),
            ("pimentão", None, "pimentão", None),
            ("pepino", None, "pepino e tomate", _ESPECIE_DUPLA),
            ("tomate", None, "pepino e tomate", _ESPECIE_DUPLA),
            ("pimenta", None, "pimenta", None)],
        3: [("batata", None, "Batata", None),
            ("beterraba", None, "beterraba", None),
            ("cenoura", None, "cenoura", None),
            ("cebola", None, "cebola e rabanete", _ESPECIE_DUPLA),
            ("rabanete", None, "cebola e rabanete", _ESPECIE_DUPLA)],
        4: [("abacaxi", None, "Abacaxi", None),
            ("abacate", None, "abacate", None),
            ("ameixa", None, "ameixa", None),
            ("banana", None, "banana", None),
            ("goiaba", None, "goiaba", None),
            ("mamão", None, "mamão", None),
            ("manga", None, "manga", None),
            ("melancia", None, "melancia", None),
            ("melão", None, "melão", None),
            ("maçã", None, "maçã", None),
            ("nectarina", None, "nectarina", None),
            ("pera", None, "pera", None),
            ("pêssego", None, "pêssego", None),
            ("pitaya", None, "pitaya", None),
            ("uva", None, "uva", None)],
        5: [("laranja", "pera", "Laranja pera", None),
            ("laranja", "lima", "laranja lima", None),
            ("limão", "rosa", "limão rosa", None),
            ("limão", "tahiti", "limão tahiti", None),
            ("tangerina", "mimosa", "mimosa", _MIMOSA),
            ("tangerina", "murcote", "tangerina murcot", _MURCOTE)],
    },
}


def _linhas() -> list[dict]:
    nomes = {o: (g, s) for o, g, s in SUBGRUPOS}
    linhas = []
    for estacao, subgrupos in _ANEXO.items():
        for ordem, especies in subgrupos.items():
            grupo, subgrupo = nomes[ordem]
            for especie, variedade, original, obs in especies:
                linhas.append({
                    "ato": ATO["ato"], "ato_id": ATO["id"], "estacao": estacao,
                    "ordem_subgrupo": ordem, "grupo": grupo, "subgrupo": subgrupo,
                    "minimo": MINIMOS[estacao][ordem], "especie": especie, "variedade": variedade,
                    "texto_original": original, "observacao": obs, "validar_smsan": obs is not None and "confirmado" not in obs
                    and _CAL not in obs and "espaçamento" not in obs and "item vazio" not in obs,
                })
    return linhas


PAUTA_175: list[dict] = _linhas()


def especies(estacao: str, ordem_subgrupo: int | None = None) -> list[dict]:
    """Linhas da pauta de uma estação (e, opcionalmente, de um subgrupo)."""
    return [l for l in PAUTA_175 if l["estacao"] == estacao
            and (ordem_subgrupo is None or l["ordem_subgrupo"] == ordem_subgrupo)]
