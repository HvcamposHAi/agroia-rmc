"""Grava a pauta da Portaria SMSAN nº 175/2026 no banco (plano v3, E2).

Fonte: chat/pauta_dados.py (transcrição do Anexo I, testada contra o texto oficial).
Pré-requisito: sql/pauta_referencia.sql aplicado no Supabase.

    python scripts/seed_pauta_175.py            # simulação: mostra o que seria gravado
    python scripts/seed_pauta_175.py --gravar   # grava (upsert idempotente)

Linhas que já estão no banco e não existem mais no código são só LISTADAS, nunca apagadas.
Os campos validado_por/validado_em (validação da SMSAN) não são sobrescritos.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from chat.pauta_dados import ATO, PAUTA_175  # noqa: E402

CHAVE = ("estacao", "especie", "variedade")


def linhas_para_banco() -> list[dict]:
    campos = ("ato_id", "estacao", "ordem_subgrupo", "grupo", "subgrupo", "minimo", "especie",
              "texto_original", "observacao", "validar_smsan")
    return [{**{c: l[c] for c in campos}, "variedade": l["variedade"] or ""} for l in PAUTA_175]


def registro_ato() -> dict:
    return {"id": ATO["id"], "ato": ATO["ato"], "orgao": ATO["orgao"], "numero": ATO["numero"],
            "ano": ATO["ano"], "data": ATO["data"], "diario_oficial": ATO["diario_oficial"],
            "sumula": ATO["sumula"], "fonte": ATO["fonte"], "vigente": True}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gravar", action="store_true", help="grava no banco (sem isso, só simula)")
    a = ap.parse_args()

    linhas = linhas_para_banco()
    print(f"{ATO['ato']}/{ATO['ano']} (DOM {ATO['diario_oficial']}): {len(linhas)} linhas, "
          f"{sum(l['validar_smsan'] for l in linhas)} a validar com a SMSAN")

    from dotenv import load_dotenv
    from supabase import create_client
    load_dotenv(RAIZ / ".env")
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    try:
        no_banco = sb.table("pauta_referencia").select("estacao,especie,variedade") \
            .eq("ato_id", ATO["id"]).execute().data or []
    except Exception as e:
        sys.exit(f"Tabela pauta_referencia indisponível ({e}). Aplique sql/pauta_referencia.sql.")

    codigo = {tuple(l[c] for c in CHAVE) for l in linhas}
    banco = {tuple(l[c] for c in CHAVE) for l in no_banco}
    print(f"no banco: {len(banco)} | novas: {len(codigo - banco)} | só no banco: {len(banco - codigo)}")
    for extra in sorted(banco - codigo):
        print("  só no banco (não apagada):", extra)

    if not a.gravar:
        print("Simulação: nada gravado. Use --gravar para gravar.")
        return
    sb.table("pauta_ato").upsert(registro_ato(), on_conflict="id").execute()
    sb.table("pauta_referencia").upsert(linhas, on_conflict="ato_id,estacao,especie,variedade").execute()
    total = sb.table("pauta_referencia").select("id", count="exact").eq("ato_id", ATO["id"]).execute().count
    print(f"Gravado. pauta_referencia agora tem {total} linhas deste ato.")
    if total != len(linhas):
        sys.exit(f"ATENÇÃO: esperado {len(linhas)}, banco tem {total}.")


if __name__ == "__main__":
    main()
