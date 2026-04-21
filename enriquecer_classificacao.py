"""
enriquecer_classificacao.py
============================
Reclassifica itens_licitacao existentes no banco Supabase:
  - Recalcula o campo `cultura` com o dicionário expandido
  - Popula `categoria_v2` (HORTIFRUTI, FRUTAS, GRAOS_CEREAIS, etc.)
  - Define `relevante_agro` (True para itens de origem agropecuária)

PRÉ-REQUISITO: rodar migracao_classificacao.sql antes.

Uso:
    python enriquecer_classificacao.py
"""

import os
import re
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing required env vars: SUPABASE_URL, SUPABASE_KEY")

# ──────────────────────────────────────────────────────────────
# 1. DICIONÁRIO DE CLASSIFICAÇÃO
# ──────────────────────────────────────────────────────────────

# Cada entrada: "KEYWORD_MAIUSCULO" → ("CULTURA_CANONICA", "CATEGORIA")
# A busca é feita como substring no campo descricao (uppercase).
# A ordem importa: a primeira correspondência vence.

CLASSIFICACAO: list[tuple[str, str, str]] = [
    # ── HORTALIÇAS / HORTIFRUTI ────────────────────────────────
    ("ALFACE",        "ALFACE",        "HORTIFRUTI"),
    ("ALMEIRÃO",      "ALMEIRÃO",      "HORTIFRUTI"),
    ("ALMEIRÃO",      "ALMEIRÃO",      "HORTIFRUTI"),
    ("ALMEIRAO",      "ALMEIRÃO",      "HORTIFRUTI"),
    ("ACELGA",        "ACELGA",        "HORTIFRUTI"),
    ("AGRIÃO",        "AGRIÃO",        "HORTIFRUTI"),
    ("AGRAO",         "AGRIÃO",        "HORTIFRUTI"),
    ("RÚCULA",        "RÚCULA",        "HORTIFRUTI"),
    ("RUCULA",        "RÚCULA",        "HORTIFRUTI"),
    ("ESPINAFRE",     "ESPINAFRE",     "HORTIFRUTI"),
    ("COUVE-FLOR",    "COUVE-FLOR",    "HORTIFRUTI"),
    ("COUVE FLOR",    "COUVE-FLOR",    "HORTIFRUTI"),
    ("COUVE",         "COUVE",         "HORTIFRUTI"),
    ("BRÓCOLIS",      "BRÓCOLIS",      "HORTIFRUTI"),
    ("BROCOLIS",      "BRÓCOLIS",      "HORTIFRUTI"),
    ("REPOLHO",       "REPOLHO",       "HORTIFRUTI"),
    ("TOMATE",        "TOMATE",        "HORTIFRUTI"),
    ("TOMATE CEREJA", "TOMATE CEREJA", "HORTIFRUTI"),
    ("PEPINO",        "PEPINO",        "HORTIFRUTI"),
    ("PIMENTÃO",      "PIMENTÃO",      "HORTIFRUTI"),
    ("PIMENTAO",      "PIMENTÃO",      "HORTIFRUTI"),
    ("PIMENTA",       "PIMENTA",       "HORTIFRUTI"),
    ("BERINJELA",     "BERINJELA",     "HORTIFRUTI"),
    ("ABOBRINHA",     "ABOBRINHA",     "HORTIFRUTI"),
    ("ABÓBORA",       "ABÓBORA",       "HORTIFRUTI"),
    ("ABOBORA",       "ABÓBORA",       "HORTIFRUTI"),
    ("CHUCHU",        "CHUCHU",        "HORTIFRUTI"),
    ("QUIABO",        "QUIABO",        "HORTIFRUTI"),
    ("JILÓ",          "JILÓ",          "HORTIFRUTI"),
    ("JILO",          "JILÓ",          "HORTIFRUTI"),
    ("VAGEM",         "VAGEM",         "HORTIFRUTI"),
    ("ERVILHA TORTA", "ERVILHA TORTA", "HORTIFRUTI"),
    ("CENOURA",       "CENOURA",       "HORTIFRUTI"),
    ("BETERRABA",     "BETERRABA",     "HORTIFRUTI"),
    ("RABANETE",      "RABANETE",      "HORTIFRUTI"),
    ("NABO",          "NABO",          "HORTIFRUTI"),
    ("BATATA-DOCE",   "BATATA-DOCE",   "HORTIFRUTI"),
    ("BATATA DOCE",   "BATATA-DOCE",   "HORTIFRUTI"),
    ("BATATA BAROA",  "BATATA BAROA",  "HORTIFRUTI"),
    ("BATATA",        "BATATA",        "HORTIFRUTI"),
    ("MANDIOCA",      "MANDIOCA",      "HORTIFRUTI"),
    ("MACAXEIRA",     "MANDIOCA",      "HORTIFRUTI"),
    ("AIPIM",         "MANDIOCA",      "HORTIFRUTI"),
    ("INHAME",        "INHAME",        "HORTIFRUTI"),
    ("TARO",          "INHAME",        "HORTIFRUTI"),
    ("CEBOLA",        "CEBOLA",        "HORTIFRUTI"),
    ("ALHO",          "ALHO",          "HORTIFRUTI"),
    ("ALHO-PORÓ",     "ALHO-PORÓ",     "HORTIFRUTI"),
    ("ALHO PORO",     "ALHO-PORÓ",     "HORTIFRUTI"),
    ("CEBOLINHA",     "CEBOLINHA",     "HORTIFRUTI"),
    ("SALSA",         "SALSA",         "HORTIFRUTI"),
    ("SALSINHA",      "SALSA",         "HORTIFRUTI"),
    ("COENTRO",       "COENTRO",       "HORTIFRUTI"),
    ("MANJERICÃO",    "MANJERICÃO",    "HORTIFRUTI"),
    ("MANJERICAO",    "MANJERICÃO",    "HORTIFRUTI"),
    ("HORTELÃ",       "HORTELÃ",       "HORTIFRUTI"),
    ("HORTELA",       "HORTELÃ",       "HORTIFRUTI"),
    ("ERVAS",         "ERVAS",         "HORTIFRUTI"),
    ("TEMPERO",       "TEMPERO",       "HORTIFRUTI"),
    ("VERDURA",       "VERDURA",       "HORTIFRUTI"),
    ("HORTALIÇA",     "HORTALIÇA",     "HORTIFRUTI"),
    ("HORTALICA",     "HORTALIÇA",     "HORTIFRUTI"),
    ("OLERICOLA",     "OLERÍCOLA",     "HORTIFRUTI"),
    ("OLERÍCOLA",     "OLERÍCOLA",     "HORTIFRUTI"),

    # ── FRUTAS ────────────────────────────────────────────────
    ("BANANA",        "BANANA",        "FRUTAS"),
    ("LARANJA",       "LARANJA",       "FRUTAS"),
    ("TANGERINA",     "TANGERINA",     "FRUTAS"),
    ("MEXERICA",      "TANGERINA",     "FRUTAS"),
    ("LIMÃO",         "LIMÃO",         "FRUTAS"),
    ("LIMAO",         "LIMÃO",         "FRUTAS"),
    ("MAÇÃ",          "MAÇÃ",          "FRUTAS"),
    ("MACA",          "MAÇÃ",          "FRUTAS"),
    ("PERA",          "PERA",          "FRUTAS"),
    ("UVA",           "UVA",           "FRUTAS"),
    ("MORANGO",       "MORANGO",       "FRUTAS"),
    ("AMEIXA",        "AMEIXA",        "FRUTAS"),
    ("PÊSSEGO",       "PÊSSEGO",       "FRUTAS"),
    ("PESSEGO",       "PÊSSEGO",       "FRUTAS"),
    ("CAQUI",         "CAQUI",         "FRUTAS"),
    ("GOIABA",        "GOIABA",        "FRUTAS"),
    ("MAMÃO",         "MAMÃO",         "FRUTAS"),
    ("MAMAO",         "MAMÃO",         "FRUTAS"),
    ("MANGA",         "MANGA",         "FRUTAS"),
    ("ABACAXI",       "ABACAXI",       "FRUTAS"),
    ("MELÃO",         "MELÃO",         "FRUTAS"),
    ("MELAO",         "MELÃO",         "FRUTAS"),
    ("MELANCIA",      "MELANCIA",      "FRUTAS"),
    ("MARACUJÁ",      "MARACUJÁ",      "FRUTAS"),
    ("MARACUJA",      "MARACUJÁ",      "FRUTAS"),
    ("ABACATE",       "ABACATE",       "FRUTAS"),
    ("KIWI",          "KIWI",          "FRUTAS"),
    ("MARMELO",       "MARMELO",       "FRUTAS"),
    ("FIGO",          "FIGO",          "FRUTAS"),
    ("ROMÃ",          "ROMÃ",          "FRUTAS"),
    ("FRUTA",         "FRUTA",         "FRUTAS"),
    ("CÍTRICO",       "CÍTRICO",       "FRUTAS"),
    ("CITRICO",       "CÍTRICO",       "FRUTAS"),

    # ── GRÃOS E CEREAIS ───────────────────────────────────────
    ("FEIJÃO",        "FEIJÃO",        "GRAOS_CEREAIS"),
    ("FEIJAO",        "FEIJÃO",        "GRAOS_CEREAIS"),
    ("GRÃO-DE-BICO",  "GRÃO-DE-BICO",  "GRAOS_CEREAIS"),
    ("GRAO DE BICO",  "GRÃO-DE-BICO",  "GRAOS_CEREAIS"),
    ("LENTILHA",      "LENTILHA",      "GRAOS_CEREAIS"),
    ("ERVILHA",       "ERVILHA",       "GRAOS_CEREAIS"),
    ("ARROZ",         "ARROZ",         "GRAOS_CEREAIS"),
    ("MILHO",         "MILHO",         "GRAOS_CEREAIS"),
    ("TRIGO",         "TRIGO",         "GRAOS_CEREAIS"),
    ("AVEIA",         "AVEIA",         "GRAOS_CEREAIS"),
    ("CENTEIO",       "CENTEIO",       "GRAOS_CEREAIS"),
    ("CEVADA",        "CEVADA",        "GRAOS_CEREAIS"),
    ("SOJA",          "SOJA",          "GRAOS_CEREAIS"),
    ("AMENDOIM",      "AMENDOIM",      "GRAOS_CEREAIS"),
    ("GERGELIM",      "GERGELIM",      "GRAOS_CEREAIS"),
    ("LINHAÇA",       "LINHAÇA",       "GRAOS_CEREAIS"),
    ("LINHACA",       "LINHAÇA",       "GRAOS_CEREAIS"),
    ("CHIA",          "CHIA",          "GRAOS_CEREAIS"),
    ("QUINOA",        "QUINOA",        "GRAOS_CEREAIS"),

    # ── LÁCTEOS ───────────────────────────────────────────────
    ("LEITE",         "LEITE",         "LATICINIOS"),
    ("QUEIJO",        "QUEIJO",        "LATICINIOS"),
    ("IOGURTE",       "IOGURTE",       "LATICINIOS"),
    ("YOGURTE",       "IOGURTE",       "LATICINIOS"),
    ("MANTEIGA",      "MANTEIGA",      "LATICINIOS"),
    ("REQUEIJÃO",     "REQUEIJÃO",     "LATICINIOS"),
    ("REQUEIJAO",     "REQUEIJÃO",     "LATICINIOS"),
    ("CREME DE LEITE","CREME DE LEITE","LATICINIOS"),
    ("NATA",          "NATA",          "LATICINIOS"),
    ("RICOTA",        "RICOTA",        "LATICINIOS"),
    ("COALHADA",      "COALHADA",      "LATICINIOS"),
    ("MUSSARELA",     "MUSSARELA",     "LATICINIOS"),

    # ── PROTEÍNAS ANIMAIS ─────────────────────────────────────
    ("OVO",           "OVO",           "PROTEINA_ANIMAL"),
    ("FRANGO",        "FRANGO",        "PROTEINA_ANIMAL"),
    ("GALINHA",       "GALINHA",       "PROTEINA_ANIMAL"),
    ("CARNE BOVINA",  "CARNE BOVINA",  "PROTEINA_ANIMAL"),
    ("CARNE SUÍNA",   "CARNE SUÍNA",   "PROTEINA_ANIMAL"),
    ("CARNE SUINA",   "CARNE SUÍNA",   "PROTEINA_ANIMAL"),
    ("CARNE",         "CARNE",         "PROTEINA_ANIMAL"),
    ("PEIXE",         "PEIXE",         "PROTEINA_ANIMAL"),
    ("TILÁPIA",       "TILÁPIA",       "PROTEINA_ANIMAL"),
    ("TILAPIA",       "TILÁPIA",       "PROTEINA_ANIMAL"),
    ("SARDINHA",      "SARDINHA",      "PROTEINA_ANIMAL"),
    ("ATUM",          "ATUM",          "PROTEINA_ANIMAL"),
    ("CAMARÃO",       "CAMARÃO",       "PROTEINA_ANIMAL"),
    ("CAMARAO",       "CAMARÃO",       "PROTEINA_ANIMAL"),
    ("SUÍNO",         "SUÍNO",         "PROTEINA_ANIMAL"),
    ("SUINO",         "SUÍNO",         "PROTEINA_ANIMAL"),
    ("BOVINO",        "BOVINO",        "PROTEINA_ANIMAL"),

    # ── PROCESSADOS DE ORIGEM FAMILIAR ────────────────────────
    ("FARINHA DE MANDIOCA", "FARINHA DE MANDIOCA", "PROCESSADOS_AF"),
    ("FARINHA DE MILHO",    "FARINHA DE MILHO",    "PROCESSADOS_AF"),
    ("FARINHA DE TRIGO",    "FARINHA DE TRIGO",    "PROCESSADOS_AF"),
    ("FARINHA",             "FARINHA",             "PROCESSADOS_AF"),
    ("POLVILHO",            "POLVILHO",            "PROCESSADOS_AF"),
    ("AMIDO",               "AMIDO",               "PROCESSADOS_AF"),
    ("FUBÁ",                "FUBÁ",                "PROCESSADOS_AF"),
    ("FUBA",                "FUBÁ",                "PROCESSADOS_AF"),
    ("CANJICA",             "CANJICA",             "PROCESSADOS_AF"),
    ("CURAL",               "CURAU",               "PROCESSADOS_AF"),
    ("MEL",                 "MEL",                 "PROCESSADOS_AF"),
    ("GELEIA",              "GELEIA",              "PROCESSADOS_AF"),
    ("GELEÍA",              "GELEIA",              "PROCESSADOS_AF"),
    ("DOCE",                "DOCE",                "PROCESSADOS_AF"),
    ("CONSERVA",            "CONSERVA",            "PROCESSADOS_AF"),
    ("EXTRATO DE TOMATE",   "EXTRATO DE TOMATE",   "PROCESSADOS_AF"),
    ("MOLHO DE TOMATE",     "MOLHO DE TOMATE",     "PROCESSADOS_AF"),
    ("AÇÚCAR MASCAVO",      "AÇÚCAR MASCAVO",      "PROCESSADOS_AF"),
    ("ACUCAR MASCAVO",      "AÇÚCAR MASCAVO",      "PROCESSADOS_AF"),
    ("RAPADURA",            "RAPADURA",            "PROCESSADOS_AF"),
    ("CACHAÇA",             "CACHAÇA",             "PROCESSADOS_AF"),
    ("CACHACA",             "CACHAÇA",             "PROCESSADOS_AF"),
    ("VINAGRE",             "VINAGRE",             "PROCESSADOS_AF"),
    ("AZEITE",              "AZEITE",              "PROCESSADOS_AF"),
    ("ÓLEO VEGETAL",        "ÓLEO VEGETAL",        "PROCESSADOS_AF"),
    ("OLEO VEGETAL",        "ÓLEO VEGETAL",        "PROCESSADOS_AF"),
    ("PÃO",                 "PÃO",                 "PROCESSADOS_AF"),
    ("PAO",                 "PÃO",                 "PROCESSADOS_AF"),
    ("BISCOITO",            "BISCOITO",            "PROCESSADOS_AF"),

    # ── INSUMOS / NÃO-AGRO ────────────────────────────────────
    # Listados DEPOIS dos agro para não sobrescrever (mas a busca para na 1ª match)
    ("EMBALAGEM",           "EMBALAGEM",           "INSUMOS_NAO_AGRO"),
    ("SACOLA",              "SACOLA",              "INSUMOS_NAO_AGRO"),
    ("SACO PLÁSTICO",       "SACO PLÁSTICO",       "INSUMOS_NAO_AGRO"),
    ("SACO PLASTICO",       "SACO PLÁSTICO",       "INSUMOS_NAO_AGRO"),
    ("BANDEJA",             "BANDEJA",             "INSUMOS_NAO_AGRO"),
    ("ISOPOR",              "ISOPOR",              "INSUMOS_NAO_AGRO"),
    ("CAIXA DE PAPELÃO",    "CAIXA PAPELÃO",       "INSUMOS_NAO_AGRO"),
    ("CAIXA PAPELAO",       "CAIXA PAPELÃO",       "INSUMOS_NAO_AGRO"),
    ("ETIQUETA",            "ETIQUETA",            "INSUMOS_NAO_AGRO"),
    ("FARDAMENTO",          "FARDAMENTO",          "INSUMOS_NAO_AGRO"),
    ("UNIFORME",            "UNIFORME",            "INSUMOS_NAO_AGRO"),
    ("EQUIPAMENTO",         "EQUIPAMENTO",         "INSUMOS_NAO_AGRO"),
    ("SERVIÇO",             "SERVIÇO",             "INSUMOS_NAO_AGRO"),
    ("SERVICO",             "SERVIÇO",             "INSUMOS_NAO_AGRO"),
    ("LOCAÇÃO",             "LOCAÇÃO",             "INSUMOS_NAO_AGRO"),
    ("LOCACAO",             "LOCAÇÃO",             "INSUMOS_NAO_AGRO"),
    ("TRANSPORTE",          "TRANSPORTE",          "INSUMOS_NAO_AGRO"),
    ("VEÍCULO",             "VEÍCULO",             "INSUMOS_NAO_AGRO"),
    ("VEICULO",             "VEÍCULO",             "INSUMOS_NAO_AGRO"),
    ("COMBUSTÍVEL",         "COMBUSTÍVEL",         "INSUMOS_NAO_AGRO"),
    ("COMBUSTIVEL",         "COMBUSTÍVEL",         "INSUMOS_NAO_AGRO"),
    ("MATERIAL DE LIMPEZA", "LIMPEZA",             "INSUMOS_NAO_AGRO"),
    ("DETERGENTE",          "LIMPEZA",             "INSUMOS_NAO_AGRO"),
    ("DESINFETANTE",        "LIMPEZA",             "INSUMOS_NAO_AGRO"),
    ("PAPEL TOALHA",        "LIMPEZA",             "INSUMOS_NAO_AGRO"),
    ("INFORMATICA",         "INFORMÁTICA",         "INSUMOS_NAO_AGRO"),
    ("INFORMÁTICA",         "INFORMÁTICA",         "INSUMOS_NAO_AGRO"),
    ("COMPUTADOR",          "INFORMÁTICA",         "INSUMOS_NAO_AGRO"),
    ("IMPRESSORA",          "INFORMÁTICA",         "INSUMOS_NAO_AGRO"),
]

# Categorias que são efetivamente agropecuárias para a dissertação.
# Foco em produtos frescos que agricultores familiares entregam diretamente.
# Excluídos: GRAOS_CEREAIS, LATICINIOS, PROCESSADOS_AF (farinha, biscoito, etc.)
CATEGORIAS_AGRO = {
    "HORTIFRUTI",
    "FRUTAS",
    "PROTEINA_ANIMAL",
}


# ──────────────────────────────────────────────────────────────
# 2. FUNÇÕES DE CLASSIFICAÇÃO
# ──────────────────────────────────────────────────────────────

def classificar_item(descricao: str) -> tuple[str, str]:
    """
    Retorna (cultura_canonica, categoria_v2) para um item.
    Busca por substring no descricao em maiúsculas.
    """
    desc = (descricao or "").upper()
    for keyword, cultura, categoria in CLASSIFICACAO:
        if keyword in desc:
            return cultura, categoria
    return "OUTRO", "NAO_CLASSIFICADO"


def is_relevante_agro(categoria: str) -> bool:
    return categoria in CATEGORIAS_AGRO


# ──────────────────────────────────────────────────────────────
# 3. LOTE DE ATUALIZAÇÃO NO SUPABASE
# ──────────────────────────────────────────────────────────────

BATCH_SIZE = 500  # itens por requisição


def enriquecer(sb, dry_run: bool = False) -> dict:
    """
    Lê todos os itens, reclassifica e atualiza no banco.
    dry_run=True apenas imprime sem gravar.
    Retorna estatísticas.
    """
    stats = {
        "total": 0,
        "atualizados": 0,
        "ja_corretos": 0,
        "erros": 0,
    }

    offset = 0
    while True:
        r = sb.table("itens_licitacao").select(
            "id, descricao, cultura, categoria_v2, relevante_agro"
        ).range(offset, offset + BATCH_SIZE - 1).execute()

        if not r.data:
            break

        updates = []
        for item in r.data:
            nova_cultura, nova_categoria = classificar_item(item["descricao"])
            novo_relevante = is_relevante_agro(nova_categoria)

            # Só atualiza se algum campo mudou
            if (
                item.get("cultura") != nova_cultura
                or item.get("categoria_v2") != nova_categoria
                or item.get("relevante_agro") != novo_relevante
            ):
                updates.append({
                    "id": item["id"],
                    "cultura": nova_cultura,
                    "categoria_v2": nova_categoria,
                    "relevante_agro": novo_relevante,
                })
            else:
                stats["ja_corretos"] += 1

        stats["total"] += len(r.data)

        if updates:
            if dry_run:
                print(f"[DRY RUN] {len(updates)} itens seriam atualizados (offset={offset})")
                for u in updates[:5]:
                    print(f"  id={u['id']}: cultura={u['cultura']} cat={u['categoria_v2']} agro={u['relevante_agro']}")
            else:
                # Agrupa por (cultura, categoria_v2, relevante_agro) para minimizar
                # chamadas à API: uma única .update().in_() por grupo de valores.
                from collections import defaultdict
                grupos: dict[tuple, list[int]] = defaultdict(list)
                for u in updates:
                    key = (u["cultura"], u["categoria_v2"], u["relevante_agro"])
                    grupos[key].append(u["id"])

                n_ok = 0
                for (cultura, cat, agro), ids in grupos.items():
                    try:
                        sb.table("itens_licitacao").update({
                            "cultura":       cultura,
                            "categoria_v2":  cat,
                            "relevante_agro": agro,
                        }).in_("id", ids).execute()
                        n_ok += len(ids)
                    except Exception as e:
                        print(f"  [ERRO] grupo ({cultura},{cat}): {e}")
                        stats["erros"] += len(ids)

                stats["atualizados"] += n_ok
                print(f"  Atualizados {n_ok} itens em {len(grupos)} grupos (offset={offset})")

        if len(r.data) < BATCH_SIZE:
            break
        offset += BATCH_SIZE

    return stats


# ──────────────────────────────────────────────────────────────
# 4. MAIN
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("[ERRO] SUPABASE_URL ou SUPABASE_KEY não definidos no .env")
        sys.exit(1)

    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("[MODO DRY-RUN] Nenhuma alteração será gravada.")

    print(f"Conectando ao Supabase: {SUPABASE_URL[:40]}...")
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("\nIniciando enriquecimento de itens_licitacao...")
    stats = enriquecer(sb, dry_run=dry_run)

    print("\n── Resultado ──────────────────────────────")
    print(f"  Total de itens processados : {stats['total']}")
    print(f"  Já classificados corretamente: {stats['ja_corretos']}")
    print(f"  Atualizados                : {stats['atualizados']}")
    print(f"  Erros                      : {stats['erros']}")
    print("────────────────────────────────────────────")

    if not dry_run:
        print("\nVerifique o resultado com a query Q6 em queries_dissertacao.sql")
