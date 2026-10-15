"""
Coleta de clima histórico e índices de apoio à projeção de preços (plano v3, E4).

Fontes (públicas, sem cadastro):
  - NASA POWER, diário por ponto (CC BY 4.0, desde 1981; defasagem de 2 a 7 dias):
    https://power.larc.nasa.gov/api/temporal/daily/point
  - NOAA PSL, Índice Oceânico do Niño (ONI), mensal: https://psl.noaa.gov/data/correlation/oni.data
  - IBGE/SIDRA, IPCA número-índice (tabela 1737, variável 2266): https://apisidra.ibge.gov.br

Grava em clima_diario, indice_enso e ipca_mensal (sql/clima.sql) e o resumo em clima_status.
Mesma regra do coletor CEASA/PR: falha de gravação ou de busca sem nada gravado = 'erro'
e saída 1 — nunca "concluída sem novidades".

Uso:
    python -m chat.clima_collector                          # últimos 30 dias + ONI + IPCA
    python -m chat.clima_collector --inicio 2017-01-01      # carga histórica
    python -m chat.clima_collector --regiao pr_colombo --so-clima
"""

import argparse
import logging
import sys
import time
from datetime import date, datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
ONI_URL = "https://psl.noaa.gov/data/correlation/oni.data"
SIDRA_URL = "https://apisidra.ibge.gov.br/values/t/1737/n1/all/v/2266/p/all"

# Parâmetro do POWER → coluna de clima_diario
PARAMETROS = {
    "PRECTOTCORR": "chuva_mm",
    "T2M_MAX": "tmax_c",
    "T2M_MIN": "tmin_c",
    "T2M": "tmed_c",
    "RH2M": "umidade_rel",
    "GWETROOT": "umidade_solo",
}
LOTE_UPSERT = 500
PAUSA_SEG = 1.0


# ── Parsers (puros, testados offline) ────────────────────────────────────────

def parse_power(payload: dict, regiao_id: str) -> list[dict]:
    """JSON do POWER → linhas de clima_diario. Valor de preenchimento (-999) vira None;
    dia sem nenhum valor (cauda ainda não processada pela NASA) é descartado."""
    preench = payload.get("header", {}).get("fill_value", -999.0)
    series = payload["properties"]["parameter"]
    dias = sorted(set().union(*(s.keys() for s in series.values())))
    linhas = []
    for d in dias:
        linha = {"regiao_id": regiao_id, "data": f"{d[:4]}-{d[4:6]}-{d[6:8]}"}
        for param, coluna in PARAMETROS.items():
            v = series.get(param, {}).get(d)
            linha[coluna] = None if v is None or v == preench else round(float(v), 3)
        if any(linha[c] is not None for c in PARAMETROS.values()):
            linhas.append(linha)
    return linhas


def parse_oni(texto: str) -> list[dict]:
    """Arquivo oni.data da NOAA PSL → [{'mes': 'AAAA-MM-01', 'oni': x}]. -99.9 = ausente."""
    linhas = []
    for bruta in texto.splitlines():
        partes = bruta.split()
        if len(partes) != 13 or not partes[0].isdigit():
            continue
        ano = int(partes[0])
        for mes, v in enumerate(partes[1:], start=1):
            valor = float(v)
            if valor > -99:
                linhas.append({"mes": f"{ano:04d}-{mes:02d}-01", "oni": valor})
    return linhas


def parse_sidra(registros: list[dict]) -> list[dict]:
    """Resposta da API SIDRA (1ª linha = cabeçalho) → [{'mes': 'AAAA-MM-01', 'numero_indice': x}]."""
    linhas = []
    for r in registros[1:]:
        periodo, valor = r.get("D3C", ""), r.get("V", "")
        try:
            linhas.append({"mes": f"{periodo[:4]}-{periodo[4:6]}-01", "numero_indice": float(valor)})
        except ValueError:      # "..." ou "-" = sem dado
            continue
    return linhas


# ── Rede ─────────────────────────────────────────────────────────────────────

def buscar_power(client: httpx.Client, lat: float, lon: float, inicio: date, fim: date) -> dict:
    resp = client.get(POWER_URL, params={
        "parameters": ",".join(PARAMETROS), "community": "AG",
        "latitude": lat, "longitude": lon,
        "start": inicio.strftime("%Y%m%d"), "end": fim.strftime("%Y%m%d"), "format": "JSON",
    })
    resp.raise_for_status()
    return resp.json()


# ── Gravação ─────────────────────────────────────────────────────────────────

def _upsert(supabase, tabela: str, linhas: list[dict], chave: str, falhas: list[str]) -> int:
    gravadas = 0
    for i in range(0, len(linhas), LOTE_UPSERT):
        lote = linhas[i: i + LOTE_UPSERT]
        try:
            supabase.table(tabela).upsert(lote, on_conflict=chave).execute()
            gravadas += len(lote)
        except Exception as e:
            logger.error(f"Erro no upsert {tabela} lote {i}: {e}")
            falhas.append(f"gravacao {tabela} lote {i}:{str(e)[:80]}")
    return gravadas


def _registrar_status(supabase, **campos) -> None:
    try:
        supabase.table("clima_status").upsert({"id": 1, **campos}, on_conflict="id").execute()
    except Exception as e:
        logger.warning(f"Não foi possível gravar clima_status (ignorado): {e}")


def coletar_clima(inicio: date | None = None, fim: date | None = None, regiao: str | None = None,
                  so_clima: bool = False) -> dict:
    from chat.db import get_supabase_client

    supabase = get_supabase_client()
    fim = fim or date.today()
    inicio = inicio or fim - timedelta(days=29)
    falhas_busca, falhas_gravacao, total, data_max = [], [], 0, None

    try:
        q = supabase.table("clima_regiao").select("id,lat,lon")
        regioes = (q.eq("id", regiao) if regiao else q).execute().data or []
    except Exception as e:
        regioes = []
        falhas_gravacao.append(f"leitura clima_regiao:{str(e)[:80]}")
    if not regioes and not falhas_gravacao:
        falhas_busca.append(f"nenhuma região cadastrada{f' com id {regiao}' if regiao else ''}")

    with httpx.Client(timeout=120) as client:
        for r in regioes:
            try:
                linhas = parse_power(buscar_power(client, r["lat"], r["lon"], inicio, fim), r["id"])
            except Exception as e:
                logger.error(f"POWER {r['id']}: {e}")
                falhas_busca.append(f"power {r['id']}:{str(e)[:80]}")
                continue
            total += _upsert(supabase, "clima_diario", linhas, "regiao_id,data", falhas_gravacao)
            if linhas:
                maior = max(l["data"] for l in linhas)
                data_max = max(data_max or maior, maior)
            logger.info(f"POWER {r['id']}: {len(linhas)} dias")
            time.sleep(PAUSA_SEG)

        if not so_clima:
            for nome, url, parser, tabela in (
                ("ONI", ONI_URL, lambda resp: parse_oni(resp.text), "indice_enso"),
                ("IPCA", SIDRA_URL, lambda resp: parse_sidra(resp.json()), "ipca_mensal"),
            ):
                try:
                    resp = client.get(url)
                    resp.raise_for_status()
                    linhas = parser(resp)
                except Exception as e:
                    logger.error(f"{nome}: {e}")
                    falhas_busca.append(f"{nome}:{str(e)[:80]}")
                    continue
                if not linhas:
                    falhas_busca.append(f"{nome}: resposta sem dados (formato mudou?)")
                    continue
                total += _upsert(supabase, tabela, linhas, "mes", falhas_gravacao)
                logger.info(f"{nome}: {len(linhas)} meses")

    falhas = falhas_busca + falhas_gravacao
    if falhas_gravacao or (falhas and not total):
        status = "erro"
    else:
        status = "ok" if total else "sem_dados"
    _registrar_status(supabase, finalizado_em=datetime.now(timezone.utc).isoformat(),
                      data_max=data_max, linhas_inseridas=total, status=status,
                      erro="; ".join(falhas)[:500] or None)
    return {"linhas_inseridas": total, "data_max": data_max, "falhas": falhas, "status": status}


def _args(argv: list[str]):
    ap = argparse.ArgumentParser(description="Coleta de clima (NASA POWER), ONI e IPCA.")
    ap.add_argument("--inicio", type=date.fromisoformat, help="AAAA-MM-DD (padrão: fim − 29 dias)")
    ap.add_argument("--fim", type=date.fromisoformat, help="AAAA-MM-DD (padrão: hoje)")
    ap.add_argument("--regiao", help="só esta região (id de clima_regiao)")
    ap.add_argument("--so-clima", action="store_true", help="não atualiza ONI e IPCA")
    return ap.parse_args(argv)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    a = _args(sys.argv[1:])
    resultado = coletar_clima(a.inicio, a.fim, a.regiao, a.so_clima)
    print(resultado)
    if resultado["status"] == "erro":
        sys.exit(1)
