#!/usr/bin/env python3
"""
Coleta PDFs apenas para licitações agrícolas que ainda não têm documento.
Baseado em etapa3_producao.py mas com foco em 313 licitações faltantes.
"""

import os
import json
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
from supabase import create_client
from googleapiclient.discovery import build

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

PORTAL_URL = (
    "http://consultalicitacao.curitiba.pr.gov.br:9090/"
    "ConsultaLicitacoes/pages/consulta/consultaProcessoDetalhada.jsf"
)

CHECKPOINT_FILE = "coleta_faltantes_checkpoint.json"
LOG_FILE = "coleta_faltantes.log"

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

def log(msg, level="INFO"):
    """Log message com timestamp"""
    ts = datetime.now().strftime("%H:%M:%S")
    linha = f"[{ts}] [{level}] {msg}"
    print(linha)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(linha + "\n")

def carregar_licitacoes_faltantes():
    """Carrega lista de licitações que faltam PDF."""
    if not Path("licitacoes_faltantes.json").exists():
        log("ERRO: licitacoes_faltantes.json nao encontrado!", "ERROR")
        return []

    with open("licitacoes_faltantes.json", "r") as f:
        data = json.load(f)

    ids_faltantes = data.get("ids_faltantes", [])
    log(f"Carregadas {len(ids_faltantes)} licitações para coletar")
    return ids_faltantes

def carregar_checkpoint():
    """Carrega checkpoint de onde parou."""
    if not Path(CHECKPOINT_FILE).exists():
        return {"processadas": [], "com_pdf": 0, "sem_pdf": 0}

    with open(CHECKPOINT_FILE, "r") as f:
        return json.load(f)

def salvar_checkpoint(data):
    """Salva checkpoint."""
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(data, f, indent=2)

def buscar_processo_por_id(driver, licitacao_id):
    """Busca o número do processo para uma licitacao_id."""
    try:
        result = sb.table("licitacoes").select("processo").eq("id", licitacao_id).single().execute()
        return result.data.get("processo") if result.data else None
    except:
        return None

def coletar_pdf_licitacao(driver, licitacao_id, processo):
    """Tenta coletar PDF de uma licitação específica."""
    try:
        # Navegar para portal
        driver.goto(PORTAL_URL, wait_until="networkidle")

        # Buscar pelo ID da licitação
        campo_id = driver.locator('[id="form:idProcessoInputDate"]')
        campo_id.fill(str(licitacao_id))

        # Clicar em pesquisar
        driver.locator('[id="form:pesquisar"]').click()
        driver.wait_for_load_state("networkidle", timeout=10000)

        # Verificar se encontrou resultado
        try:
            linhas = driver.locator('[id="form:tabela"] tbody tr')
            count = linhas.count()

            if count == 0:
                return None, "Nenhum resultado"

            # Clicar no primeiro resultado
            linhas.first.click()
            driver.wait_for_load_state("networkidle", timeout=10000)

            # Tentar baixar PDF (mesmo fluxo de etapa3_producao.py)
            # ... (implementar se necessário)

            return "OK", "Processo encontrado"
        except Exception as e:
            return None, f"Erro ao processar: {str(e)[:50]}"

    except Exception as e:
        return None, f"Erro na navegação: {str(e)[:50]}"

def main():
    print("=== Coleta de PDFs - Apenas Faltantes ===\n")

    # 1. Carregar licitações faltantes
    ids_faltantes = carregar_licitacoes_faltantes()
    if not ids_faltantes:
        print("Nenhuma licitação para coletar!")
        return

    # 2. Carregar checkpoint
    checkpoint = carregar_checkpoint()
    processadas = set(checkpoint.get("processadas", []))

    faltantes_para_coletar = [id for id in ids_faltantes if id not in processadas]

    print(f"Total faltantes: {len(ids_faltantes)}")
    print(f"Já processadas: {len(processadas)}")
    print(f"Restam: {len(faltantes_para_coletar)}\n")

    if not faltantes_para_coletar:
        print("Todas as licitações já foram processadas!")
        return

    # 3. Coletar apenas um teste primeiro
    print("ATENCAO: Este script é preparatório.")
    print("Para ativar coleta real, descomentar código em coletar_pdf_licitacao()")
    print()
    print("Próximas licitações a coletar:")
    for lid in faltantes_para_coletar[:10]:
        processo = buscar_processo_por_id(None, lid)
        print(f"  - ID {lid}: {processo}")

    print(f"\nTotal a coletar: {len(faltantes_para_coletar)}")
    print("Tempo estimado: ~{:.1f} horas (30 segundos por licitação)".format(len(faltantes_para_coletar) * 30 / 3600))

if __name__ == "__main__":
    main()
