"""
Lógica para coleta de dados (manual + semanal).
Gerencia subprocess, progresso em JSON, agendamento.
"""

import os
import json
import subprocess
import signal
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Tuple, Dict, Any, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from chat.db import get_supabase_client

logger = logging.getLogger(__name__)

STATUS_FILE = "coleta_status.json"
PROCESS_PID = None

# ─── Funções auxiliares ──────────────────────────────────────────────────────

def get_data_mais_recente() -> str:
    """Retorna MAX(dt_abertura) como DD/MM/YYYY, ou 01/01/2019 se vazio."""
    try:
        sb = get_supabase_client()
        resp = sb.table("licitacoes").select("dt_abertura").order("dt_abertura", desc=True).limit(1).execute()
        if resp.data and len(resp.data) > 0:
            dt_str = resp.data[0]["dt_abertura"]
            if dt_str:
                d = datetime.strptime(dt_str, "%Y-%m-%d").date()
                return d.strftime("%d/%m/%Y")
        return "01/01/2019"
    except Exception as e:
        logger.error(f"Erro ao buscar data mais recente: {e}")
        return "01/01/2019"


def get_status() -> dict:
    """Lê coleta_status.json ou retorna status idle."""
    try:
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Erro ao ler {STATUS_FILE}: {e}")

    return {
        "status": "idle",
        "etapa": "nenhuma",
        "processados": 0,
        "novos": 0,
        "pulados": 0,
        "erros": 0,
        "itens_coletados": 0,
        "fornecedores": 0,
        "empenhos": 0,
        "iniciado_em": None,
        "atualizado_em": datetime.now().isoformat(),
        "pid": None
    }


def iniciar_coleta(dt_inicio: Optional[str] = None, dt_fim: Optional[str] = None) -> Tuple[bool, str]:
    """
    Inicia uma coleta de dados via subprocess (etapa2_itens_v9.py).
    Retorna (sucesso: bool, mensagem: str).
    """
    global PROCESS_PID

    # Verificar se já há coleta em andamento
    status = get_status()
    if status.get("status") == "running":
        return False, f"Coleta já em andamento (PID: {status.get('pid')})"

    # Resolver datas
    if not dt_inicio:
        dt_inicio = get_data_mais_recente()
    if not dt_fim:
        dt_fim = datetime.now().strftime("%d/%m/%Y")

    logger.info(f"Iniciando coleta: {dt_inicio} → {dt_fim}")

    try:
        # Lançar subprocess com arguments
        cmd = [
            "python",
            "etapa2_itens_v9.py",
            "--dt-inicio", dt_inicio,
            "--dt-fim", dt_fim,
            "--progress-file", STATUS_FILE
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        PROCESS_PID = process.pid

        logger.info(f"Processo iniciado: PID {process.pid}")
        return True, f"Coleta iniciada com sucesso (PID: {process.pid})"

    except Exception as e:
        logger.error(f"Erro ao iniciar coleta: {e}")
        return False, f"Erro ao iniciar coleta: {str(e)}"


def cancelar_coleta() -> Tuple[bool, str]:
    """
    Envia SIGTERM ao processo de coleta.
    Retorna (sucesso: bool, mensagem: str).
    """
    global PROCESS_PID
    status = get_status()

    if status.get("status") != "running":
        return False, "Nenhuma coleta em andamento"

    pid = status.get("pid")
    if not pid:
        return False, "PID não encontrado no arquivo de status"

    try:
        os.kill(pid, signal.SIGTERM)
        logger.info(f"SIGTERM enviado ao PID {pid}")
        return True, f"Sinal de cancelamento enviado ao PID {pid}"
    except ProcessLookupError:
        logger.warning(f"Processo {pid} não encontrado")
        return False, f"Processo {pid} não encontrado (talvez já tenha terminado)"
    except Exception as e:
        logger.error(f"Erro ao cancelar coleta: {e}")
        return False, f"Erro ao cancelar: {str(e)}"


def get_stats_classificacao() -> Dict[str, Any]:
    """
    Query Supabase: estatísticas sobre classificação agrícola.
    Retorna contagens por relevante_af, categoria_v2, e por ano.
    """
    try:
        sb = get_supabase_client()

        # Total de licitações
        resp_total = sb.table("licitacoes").select("id", count="exact").execute()
        total_licitacoes = resp_total.count if resp_total.count else 0

        # Licitações agrícolas
        resp_agro = sb.table("licitacoes").select("id", count="exact").eq("relevante_af", True).execute()
        total_agro = resp_agro.count if resp_agro.count else 0

        # Licitações não-agrícolas
        total_nao_agro = total_licitacoes - total_agro

        # Total de itens
        resp_itens_total = sb.table("itens_licitacao").select("id", count="exact").execute()
        total_itens = resp_itens_total.count if resp_itens_total.count else 0

        # Itens por categoria
        resp_categorias = sb.table("itens_licitacao").select("categoria_v2", count="exact").execute()
        categorias_dict = {}
        if resp_categorias.data:
            # Agrupar manualmente por categoria
            resp_by_cat = sb.table("itens_licitacao").select("categoria_v2").execute()
            from collections import Counter
            cat_counts = Counter(x.get("categoria_v2", "NAO_CLASSIFICADO") for x in resp_by_cat.data)
            categorias_dict = dict(cat_counts)

        # Licitações agrícolas por ano
        resp_agro_anos = sb.table("licitacoes").select("dt_abertura").eq("relevante_af", True).execute()
        agro_por_ano = {}
        if resp_agro_anos.data:
            from collections import defaultdict
            anos_dict = defaultdict(int)
            for row in resp_agro_anos.data:
                if row.get("dt_abertura"):
                    year = row["dt_abertura"][:4]
                    anos_dict[year] += 1
            agro_por_ano = dict(sorted(anos_dict.items()))

        # Cobertura agrícola
        cobertura_pct = round((total_agro / total_licitacoes * 100) if total_licitacoes > 0 else 0, 1)

        return {
            "timestamp": datetime.now().isoformat(),
            "total_licitacoes": total_licitacoes,
            "total_agricolas": total_agro,
            "total_nao_agricolas": total_nao_agro,
            "cobertura_agricola_pct": cobertura_pct,
            "total_itens": total_itens,
            "itens_por_categoria": categorias_dict,
            "licitacoes_agricolas_por_ano": agro_por_ano
        }

    except Exception as e:
        logger.error(f"Erro ao buscar estatísticas: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# ─── Agendamento ─────────────────────────────────────────────────────────────

scheduler = None


def job_coleta_semanal():
    """Job que roda toda segunda-feira às 06:00 (horário local)."""
    logger.info("Job semanal de coleta iniciado")
    sucesso, msg = iniciar_coleta()
    if sucesso:
        logger.info(f"Coleta semanal: {msg}")
    else:
        logger.warning(f"Coleta semanal falhou: {msg}")


def configurar_agendamento(app):
    """Configura APScheduler com job semanal."""
    global scheduler

    try:
        scheduler = BackgroundScheduler(daemon=True)

        # Segunda-feira às 06:00 (weekday 0 = Monday)
        trigger = CronTrigger(day_of_week=0, hour=6, minute=0)
        scheduler.add_job(
            job_coleta_semanal,
            trigger=trigger,
            id="coleta_semanal",
            name="Coleta de dados semanal",
            replace_existing=True
        )

        scheduler.start()
        logger.info("APScheduler iniciado com job semanal (seg 06:00)")

        # Cleanup ao desligar app
        def shutdown_scheduler():
            if scheduler and scheduler.running:
                scheduler.shutdown()

        # Para FastAPI 0.93+, usar lifespan
        # Para versões antigas, usar on_event
        @app.on_event("shutdown")
        async def shutdown_event():
            shutdown_scheduler()

    except Exception as e:
        logger.error(f"Erro ao configurar agendamento: {e}")
