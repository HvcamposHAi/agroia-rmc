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
from pydantic import BaseModel

logger = logging.getLogger(__name__)

STATUS_FILE = "coleta_status.json"
PROCESS_PID = None

# A coleta usa Playwright + Chromium, que não roda de forma confiável no Render
# (sem display, navegador ausente, RAM limitada, FS efêmero). Por padrão a coleta
# é habilitada (execução LOCAL no Windows). Em produção/Render, setar
# COLETA_ENABLED=false: a página passa a exibir apenas status/estatísticas.
def coleta_habilitada() -> bool:
    return os.getenv("COLETA_ENABLED", "true").lower() in ("1", "true", "yes")

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

    # No ambiente de nuvem (Render) a coleta via navegador não roda — execute localmente.
    if not coleta_habilitada():
        return False, ("Coleta deve ser executada na máquina local. "
                       "Esta página exibe apenas status e estatísticas.")

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
    Retorna contagens por relevante_af, categoria_v2, documentação, e por ano.
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

        # Total de itens AGRÍCOLAS — mesma fonte da Home/Demanda (vw_itens_agro,
        # nível item, relevante_agro=true). Mantém coerência de escopo com o resto
        # do app (CLAUDE.md: agricultura exclusivamente). NOTA: `relevante_af` é
        # nível LICITAÇÃO; `relevante_agro` é nível ITEM (filtro da view) —
        # granularidades intencionalmente diferentes.
        resp_itens_agro = sb.from_("vw_itens_agro").select("id", count="exact").eq("relevante_agro", True).execute()
        total_itens = resp_itens_agro.count if resp_itens_agro.count else 0

        # Contagem bruta (todos os itens, agrícolas ou não) — referência apenas.
        resp_itens_bruto = sb.table("itens_licitacao").select("id", count="exact").execute()
        total_itens_bruto = resp_itens_bruto.count if resp_itens_bruto.count else 0

        # Itens agrícolas por categoria — paginado para evitar a truncagem do
        # PostgREST em 1000 linhas (a contagem por categoria precisa de TODAS as linhas).
        from collections import Counter
        cat_counts = Counter()
        offset = 0
        PAGINA = 1000
        while True:
            resp_cat = (
                sb.from_("vw_itens_agro")
                .select("categoria_v2")
                .eq("relevante_agro", True)
                .range(offset, offset + PAGINA - 1)
                .execute()
            )
            linhas = resp_cat.data or []
            if not linhas:
                break
            cat_counts.update((x.get("categoria_v2") or "NAO_CLASSIFICADO") for x in linhas)
            if len(linhas) < PAGINA:
                break
            offset += PAGINA
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

        # Licitações com e sem documentação (agrícolas)
        resp_docs = sb.table("documentos_licitacao").select("licitacao_id", count="exact").execute()
        lics_com_docs = set(row["licitacao_id"] for row in resp_docs.data) if resp_docs.data else set()
        lics_agro_com_docs = 0
        lics_agro_sem_docs = 0

        # Contar agrícolas com e sem docs
        resp_agro_lics = sb.table("licitacoes").select("id").eq("relevante_af", True).execute()
        for lic in resp_agro_lics.data:
            if lic["id"] in lics_com_docs:
                lics_agro_com_docs += 1
            else:
                lics_agro_sem_docs += 1

        # Média de itens por licitação
        resp_itens_por_lic = sb.table("itens_licitacao").select("licitacao_id").execute()
        from collections import Counter
        if resp_itens_por_lic.data:
            lics_count = Counter(x.get("licitacao_id") for x in resp_itens_por_lic.data)
            media_itens_por_lic = round(len(resp_itens_por_lic.data) / len(lics_count), 1) if lics_count else 0
        else:
            media_itens_por_lic = 0

        # Cobertura agrícola
        cobertura_pct = round((total_agro / total_licitacoes * 100) if total_licitacoes > 0 else 0, 1)
        cobertura_docs_agro = round((lics_agro_com_docs / total_agro * 100) if total_agro > 0 else 0, 1)

        return {
            "timestamp": datetime.now().isoformat(),
            "total_licitacoes": total_licitacoes,
            "total_agricolas": total_agro,
            "total_nao_agricolas": total_nao_agro,
            "cobertura_agricola_pct": cobertura_pct,
            "total_itens": total_itens,
            "total_itens_bruto": total_itens_bruto,
            "media_itens_por_licitacao": media_itens_por_lic,
            "licitacoes_agro_com_docs": lics_agro_com_docs,
            "licitacoes_agro_sem_docs": lics_agro_sem_docs,
            "cobertura_documentos_agro_pct": cobertura_docs_agro,
            "itens_por_categoria": categorias_dict,
            "licitacoes_agricolas_por_ano": agro_por_ano
        }

    except Exception as e:
        logger.error(f"Erro ao buscar estatísticas: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


def get_ultima_execucao() -> Optional[dict]:
    """Retorna a última execução de coleta registrada em coleta_execucoes,
    ou None se não houver registro / em caso de erro."""
    try:
        sb = get_supabase_client()
        resp = (
            sb.table("coleta_execucoes")
            .select("*")
            .order("finalizado_em", desc=True)
            .limit(1)
            .execute()
        )
        if resp.data and len(resp.data) > 0:
            return resp.data[0]
        return None
    except Exception as e:
        logger.error(f"Erro ao buscar última execução: {e}")
        return None


def get_historico_execucoes(limite: int = 10) -> list:
    """Retorna as últimas `limite` execuções (mais recentes primeiro)."""
    try:
        sb = get_supabase_client()
        resp = (
            sb.table("coleta_execucoes")
            .select("*")
            .order("finalizado_em", desc=True)
            .limit(limite)
            .execute()
        )
        return resp.data or []
    except Exception as e:
        logger.error(f"Erro ao buscar histórico de execuções: {e}")
        return []


# ─── Agendamento ─────────────────────────────────────────────────────────────

scheduler = None


def proxima_execucao_iso() -> Optional[str]:
    """Calcula o próximo disparo da coleta semanal a partir do agendamento salvo
    (coleta_config.json), usando o mesmo CronTrigger do APScheduler. Retorna ISO
    ou None se a coleta não estiver habilitada / em caso de erro."""
    try:
        if not coleta_habilitada():
            return None
        config = get_config()
        trigger = CronTrigger(
            day_of_week=config.get("dia_semana", 0),
            hour=config.get("hora", 6),
            minute=config.get("minuto", 0),
        )
        proxima = trigger.get_next_fire_time(None, datetime.now())
        return proxima.isoformat() if proxima else None
    except Exception as e:
        logger.error(f"Erro ao calcular próxima execução: {e}")
        return None


def job_coleta_semanal():
    """Job que roda toda segunda-feira às 06:00 (horário local)."""
    logger.info("Job semanal de coleta iniciado")
    sucesso, msg = iniciar_coleta()
    if sucesso:
        logger.info(f"Coleta semanal: {msg}")
    else:
        logger.warning(f"Coleta semanal falhou: {msg}")


CONFIG_FILE = "coleta_config.json"

def get_config() -> Dict[str, Any]:
    """Lê configuração do agendamento."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Erro ao ler config: {e}")

    return {"dia_semana": 0, "hora": 6, "minuto": 0}

def salvar_config(config: Dict[str, Any]) -> None:
    """Salva configuração do agendamento."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        logger.info(f"Configuração salva: dia_semana={config.get('dia_semana')}, hora={config.get('hora')}, minuto={config.get('minuto')}")
    except Exception as e:
        logger.error(f"Erro ao salvar config: {e}")

def job_prohort_diario():
    """Coleta incremental diária de preços PROHORT (últimos 30 dias). Import lazy."""
    try:
        from chat.prohort_collector import coletar_prohort
        resultado = coletar_prohort(dias_recentes=30)
        logger.info(f"Job PROHORT diário concluído: {resultado}")
    except Exception as e:
        logger.error(f"Erro no job PROHORT diário: {e}")


def configurar_agendamento(app):
    """Configura APScheduler com job semanal."""
    global scheduler

    try:
        scheduler = BackgroundScheduler(daemon=True)

        # Carregar configuração
        config = get_config()
        dia_semana = config.get("dia_semana", 0)
        hora = config.get("hora", 6)
        minuto = config.get("minuto", 0)

        # Segunda-feira às 06:00 (weekday 0 = Monday) - ou conforme config.
        # Só agenda a coleta por navegador onde ela pode rodar (local). No Render
        # (COLETA_ENABLED=false) não agenda — evita falhas silenciosas semanais.
        if coleta_habilitada():
            trigger = CronTrigger(day_of_week=dia_semana, hour=hora, minute=minuto)
            scheduler.add_job(
                job_coleta_semanal,
                trigger=trigger,
                id="coleta_semanal",
                name="Coleta de dados semanal",
                replace_existing=True
            )
        else:
            logger.info("COLETA_ENABLED=false → job semanal de coleta NÃO agendado (execução local).")

        # Job diário PROHORT (preços de atacado CEASA) — 06:30 todos os dias
        scheduler.add_job(
            job_prohort_diario,
            trigger=CronTrigger(hour=6, minute=30),
            id="prohort_diario",
            name="Coleta diária de preços PROHORT",
            replace_existing=True
        )
        logger.info("Job PROHORT diário agendado (todos os dias 06:30)")

        scheduler.start()
        dias = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]
        logger.info(f"APScheduler iniciado com job semanal ({dias[dia_semana]} {hora:02d}:{minuto:02d})")

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
