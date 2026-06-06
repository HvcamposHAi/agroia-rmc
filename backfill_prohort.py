"""
Backfill único de preços PROHORT/CONAB — base histórica de 24 meses das CEASAs alvo.

Rodar LOCALMENTE (não no Render free 512 MB) apontando para o Supabase de produção:

    python backfill_prohort.py            # 24 meses (730 dias)
    python backfill_prohort.py 365        # outra janela em dias
    python backfill_prohort.py completo   # todo o histórico da fonte (~4 anos)

Usa flush_por_chunk=True: deduplica e faz upsert por chunk (memória ~O(1 chunk),
gravação incremental resiliente a quedas). É idempotente — rodar 2x não duplica.
O job diário (api/coleta.py) continua coletando só os últimos 30 dias.
"""

import sys

from chat.prohort_collector import coletar_prohort


def main() -> None:
    arg = sys.argv[1].lower() if len(sys.argv) > 1 else "730"
    if arg in ("completo", "full", "none"):
        dias: int | None = None
    else:
        try:
            dias = int(arg)
        except ValueError:
            print(f"Argumento inválido: {arg!r}. Use um número de dias ou 'completo'.")
            sys.exit(2)

    print(f"Iniciando backfill PROHORT (dias_recentes={dias}, flush_por_chunk=True)...")
    resultado = coletar_prohort(dias_recentes=dias, flush_por_chunk=True)
    print(resultado)
    if "erro" in resultado:
        sys.exit(1)


if __name__ == "__main__":
    main()
