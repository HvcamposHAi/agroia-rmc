"""
Pipeline de coleta do PROHORT/CONAB (preços de atacado das CEASAs).

Fonte oficial:
  CONAB. Portal de Informações Agropecuárias: Prohort Diário.
  https://portaldeinformacoes.conab.gov.br/downloads/arquivos/ProhortDiario.txt
  Acesso diário, uso não comercial autorizado citando a fonte.

Formato real do arquivo (confirmado por inspeção):
  - latin-1, separador ";", ~174 MB, ~1.02 M linhas, histórico diário desde 2022-06.
  - Colunas: municipio_ceasa; cod_ibge_municipio; uf_ceasa; dsc_ceasa; dsc_produto;
             sig_unidade_medida; data_preco; preco_diario
  - data_preco: "AAAA/MM/DD 00:00:00.000"  |  preco_diario: decimal com ponto, 1 só valor.
  - min/médio/máx NÃO existem na fonte → derivados nas views por agregação na janela.

Estratégia (memória controlada p/ Render free 512 MB):
  download em streaming → arquivo temporário em disco → parse em chunks (pandas chunksize)
  → filtra CEASAs alvo por chunk → upsert idempotente em lotes.
"""

import os
import logging
import tempfile
from datetime import date, timedelta

import httpx
import pandas as pd

from chat.db import get_supabase_client
from chat.prohort_normalizer import normalizar_produto

logger = logging.getLogger(__name__)

PROHORT_DIARIO_URL = (
    "https://portaldeinformacoes.conab.gov.br/downloads/arquivos/ProhortDiario.txt"
)

# dsc_ceasa (UPPER+strip) → chave curta guardada na coluna `ceasa`.
# LONDRINA não existe no PROHORT; referências PR disponíveis: Cascavel, Foz do Iguaçu.
CEASA_ALIAS: dict[str, str] = {
    "CEASA/PR - CURITIBA":  "CURITIBA",
    "CEASA/PR - MARINGA":   "MARINGA",
    "CEAGESP - SAO PAULO":  "SAO PAULO",
}
CEASAS_ALVO = set(CEASA_ALIAS.keys())

CHUNKSIZE = 100_000
LOTE_UPSERT = 500


def _to_float(valor) -> float | None:
    """Converte preço PROHORT (decimal com ponto) para float; vírgula tratada por robustez."""
    try:
        s = str(valor).strip()
        if not s or s.lower() in ("nan", "none"):
            return None
        # diário usa ponto; trata vírgula caso a CONAB altere o formato sem aviso
        if "," in s and "." not in s:
            s = s.replace(",", ".")
        return round(float(s), 2)
    except (ValueError, TypeError):
        return None


def _baixar_para_tempfile() -> str:
    """Baixa o ProhortDiario.txt em streaming para um arquivo temporário. Retorna o caminho."""
    fd, caminho = tempfile.mkstemp(suffix=".txt", prefix="prohort_")
    total = 0
    with os.fdopen(fd, "wb") as f:
        with httpx.Client(timeout=300, follow_redirects=True) as client:
            with client.stream("GET", PROHORT_DIARIO_URL) as resp:
                resp.raise_for_status()
                for bloco in resp.iter_bytes(chunk_size=1024 * 256):
                    f.write(bloco)
                    total += len(bloco)
    logger.info(f"PROHORT baixado: {total / 1e6:.1f} MB em {caminho}")
    return caminho


def coletar_prohort(dias_recentes: int | None = 30) -> dict:
    """
    Baixa o ProhortDiario.txt, filtra as CEASAs alvo, normaliza e faz upsert em prohort_precos.

    dias_recentes:
        None → backfill completo (todo o histórico das CEASAs alvo, ~4 anos).
        N    → apenas linhas com data_preco >= hoje - N dias (coleta diária incremental).

    Retorna dict: {linhas_inseridas, total_filtradas, ceasas, data_coleta} ou {erro,...}.
    """
    logger.info(f"Iniciando coleta PROHORT (dias_recentes={dias_recentes})...")

    try:
        caminho = _baixar_para_tempfile()
    except Exception as e:
        logger.error(f"Falha no download PROHORT: {e}")
        return {"erro": f"download:{e}", "linhas_inseridas": 0}

    cutoff = None
    if dias_recentes is not None:
        cutoff = pd.Timestamp(date.today() - timedelta(days=dias_recentes))

    supabase = get_supabase_client()
    dedup: dict[tuple, dict] = {}
    total_filtradas = 0

    try:
        for chunk in pd.read_csv(
            caminho, sep=";", encoding="latin-1", dtype=str,
            on_bad_lines="skip", chunksize=CHUNKSIZE,
        ):
            chunk.columns = [c.strip() for c in chunk.columns]
            obrig = {"dsc_ceasa", "dsc_produto", "data_preco", "preco_diario"}
            if not obrig.issubset(chunk.columns):
                logger.error(f"Colunas inesperadas no PROHORT: {list(chunk.columns)}")
                return {"erro": "colunas_inesperadas", "linhas_inseridas": 0}

            chunk["_ceasa_key"] = chunk["dsc_ceasa"].str.strip().str.upper().map(CEASA_ALIAS)
            chunk = chunk[chunk["_ceasa_key"].notna()]
            if chunk.empty:
                continue

            chunk["_data"] = pd.to_datetime(
                chunk["data_preco"], format="%Y/%m/%d %H:%M:%S.%f", errors="coerce"
            )
            chunk = chunk[chunk["_data"].notna()]
            if cutoff is not None:
                chunk = chunk[chunk["_data"] >= cutoff]
            if chunk.empty:
                continue

            total_filtradas += len(chunk)
            for row in chunk.itertuples(index=False):
                d = getattr(row, "_data")
                preco = _to_float(getattr(row, "preco_diario"))
                if preco is None:
                    continue
                produto_raw = str(getattr(row, "dsc_produto")).strip()
                ceasa = getattr(row, "_ceasa_key")
                data_iso = d.date().isoformat()
                chave = (data_iso, ceasa, produto_raw)
                dedup[chave] = {
                    "data_coleta": data_iso,
                    "ceasa": ceasa,
                    "produto": produto_raw,
                    "produto_norm": normalizar_produto(produto_raw),
                    "unidade": str(getattr(row, "sig_unidade_medida")).strip() or None,
                    "preco_min": preco,
                    "preco_medio": preco,
                    "preco_max": preco,
                    "origem": str(getattr(row, "dsc_ceasa")).strip() or None,
                }
    except Exception as e:
        logger.error(f"Erro ao processar PROHORT: {e}", exc_info=True)
        return {"erro": f"parse:{e}", "linhas_inseridas": 0}
    finally:
        try:
            os.remove(caminho)
        except OSError:
            pass

    registros = list(dedup.values())
    if not registros:
        logger.warning("Nenhum registro PROHORT para as CEASAs alvo no período.")
        return {"erro": "sem_dados", "linhas_inseridas": 0, "total_filtradas": total_filtradas}

    total_inseridos = 0
    for i in range(0, len(registros), LOTE_UPSERT):
        lote = registros[i: i + LOTE_UPSERT]
        try:
            supabase.table("prohort_precos").upsert(
                lote, on_conflict="data_coleta,ceasa,produto"
            ).execute()
            total_inseridos += len(lote)
        except Exception as e:
            logger.error(f"Erro no upsert PROHORT lote {i}: {e}")

    ceasas = sorted({r["ceasa"] for r in registros})
    logger.info(f"Coleta PROHORT concluída: {total_inseridos} registros (CEASAs: {ceasas}).")
    return {
        "linhas_inseridas": total_inseridos,
        "total_filtradas": total_filtradas,
        "registros_unicos": len(registros),
        "ceasas": ceasas,
        "data_coleta": date.today().isoformat(),
    }
