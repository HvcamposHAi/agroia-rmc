"""
Classificação de LICITAÇÕES (nível processo) — tipo, canal e relevante_af.

Regras idênticas às da Etapa 1 (ingestao_supabase.py, commit 1b7f874), que gerou
as 1.237 licitações do corpus. Conferido em 23/09/2026: reproduzem 100% dos
valores gravados de `canal` e `relevante_af` (0 divergências). NÃO alterar sem
reclassificar a base inteira — senão licitações novas e antigas ficam com
critérios diferentes (quebra a comparabilidade do corpus da dissertação).
"""

TIPOS = ["CR", "AD", "PE", "DS", "DE", "DT", "DM", "CH", "CP", "IN", "FN", "PP",
         "PL", "RE", "RD", "SG", "TP", "LE", "PQ", "CO", "CN", "CE"]


def classificar_tipo(processo: str) -> str:
    for s in TIPOS:
        if (processo or "").upper().startswith(s):
            return s
    return "OUTRO"


def classificar_canal(objeto: str) -> str:
    o = (objeto or "").lower()
    if any(x in o for x in ["armazém da família", "armazem da familia", "hortifrutigranjeiro",
                            "hortifruti", "credenciamento de agricultor"]):
        return "ARMAZEM_FAMILIA"
    if "programa de aquisição de alimentos" in o or " paa " in o:
        return "PAA"
    if "alimentação escolar" in o or "pnae" in o or "merenda" in o:
        return "PNAE"
    if "banco de alimentos" in o:
        return "BANCO_ALIMENTOS"
    if "mesa solidária" in o or "mesa solidaria" in o:
        return "MESA_SOLIDARIA"
    return "OUTRO"


def is_af(objeto: str) -> bool:
    return any(p in (objeto or "").lower() for p in [
        "agricultura familiar", "hortifrutigranjeiro", "hortifruti", "armazém da família",
        "armazem da familia", "credenciamento de agricultor", "paa", "programa de aquisição",
        "olericultura", "orgânico", "organico", "cooperativa", "associação de produtores"])
