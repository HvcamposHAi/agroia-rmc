#!/usr/bin/env python3
"""
Script para obter dados SEMPRE ATUALIZADOS do banco - APENAS AGRICULTURA.
Filtra exclusivamente licitações com relevante_af = true.

Execução:
  python dados_atualizados_agro.py --resumo
  python dados_atualizados_agro.py --licitacoes-recentes 10
  python dados_atualizados_agro.py --status-coleta
"""

import os
import sys
import json
from datetime import datetime
from supabase import create_client

def carregar_supabase():
    """Carrega cliente Supabase do .env"""
    with open(".env") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                key, value = line.split("=", 1)
                os.environ[key] = value

    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def get_resumo_dados_agro():
    """Retorna resumo executivo dos dados AGRÍCOLAS atualizados"""
    sb = carregar_supabase()

    # Total de licitacoes AGRÍCOLAS
    result = sb.table("licitacoes").select("count", count="exact").eq("relevante_af", True).execute()
    total_licitacoes = result.count

    # Data minima e maxima (agrícolas)
    result = sb.table("licitacoes").select("*").eq("relevante_af", True).order("dt_abertura").limit(1).execute()
    data_minima = result.data[0]['dt_abertura'] if result.data else None

    result = sb.table("licitacoes").select("*").eq("relevante_af", True).order("dt_abertura", desc=True).limit(1).execute()
    data_maxima = result.data[0]['dt_abertura'] if result.data else None
    licitacao_mais_recente = result.data[0]['processo'] if result.data else None

    # Documentos EM LICITACOES AGRÍCOLAS
    result = sb.table("documentos_licitacao").select("licitacao_id").execute()
    docs_lic_ids = set(d['licitacao_id'] for d in result.data) if result.data else set()

    if docs_lic_ids:
        result = sb.table("licitacoes").select("count", count="exact").in_("id", list(docs_lic_ids)).eq("relevante_af", True).execute()
        total_documentos = result.count
    else:
        total_documentos = 0

    # Licitacoes agrícolas com documentos
    result = sb.table("documentos_licitacao").select("licitacao_id").execute()
    if result.data:
        doc_lics = set(d['licitacao_id'] for d in result.data)
        result = sb.table("licitacoes").select("id").in_("id", list(doc_lics)).eq("relevante_af", True).execute()
        lics_com_docs = len(result.data) if result.data else 0
    else:
        lics_com_docs = 0

    # Contagem por ano (agrícolas)
    por_ano = {}
    for ano in range(2019, 2027):
        inicio = f"{ano}-01-01"
        fim = f"{ano}-12-31"
        r = sb.table("licitacoes").select("count", count="exact").gte("dt_abertura", inicio).lte("dt_abertura", fim).eq("relevante_af", True).execute()
        if r.count > 0:
            por_ano[ano] = r.count

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "escopo": "APENAS AGRICULTURA (relevante_af=true)",
        "total_licitacoes_agro": total_licitacoes,
        "data_minima": data_minima,
        "data_maxima": data_maxima,
        "licitacao_mais_recente": licitacao_mais_recente,
        "documentos_em_licitacoes_agro": total_documentos,
        "licitacoes_agro_com_documentos": lics_com_docs,
        "cobertura_documentos_pct": round((lics_com_docs / total_licitacoes * 100), 1) if total_licitacoes > 0 else 0,
        "distribuicao_por_ano": por_ano
    }

def get_licitacoes_recentes_agro(limite=10):
    """Retorna as N licitacoes AGRÍCOLAS mais recentes"""
    sb = carregar_supabase()
    result = sb.table("licitacoes").select("processo, dt_abertura, objeto, situacao").eq("relevante_af", True).order("dt_abertura", desc=True).limit(limite).execute()

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "escopo": "APENAS AGRICULTURA",
        "total_retornado": len(result.data),
        "licitacoes": [
            {
                "processo": lic['processo'],
                "data_abertura": lic['dt_abertura'],
                "objeto": lic['objeto'][:100] if lic['objeto'] else None,
                "situacao": lic['situacao']
            }
            for lic in result.data
        ]
    }

def get_status_coleta_agro():
    """Retorna status da coleta de PDFs para licitações AGRÍCOLAS"""
    sb = carregar_supabase()

    # Total de docs
    result = sb.table("documentos_licitacao").select("licitacao_id").execute()
    if result.data:
        doc_lics = set(d['licitacao_id'] for d in result.data)

        # Docs em licitacoes agrícolas
        agro = sb.table("licitacoes").select("id").in_("id", list(doc_lics)).eq("relevante_af", True).execute()
        docs_agro = len(agro.data) if agro.data else 0

        # Docs em licitacoes NÃO agrícolas
        nao_agro = sb.table("licitacoes").select("id").in_("id", list(doc_lics)).eq("relevante_af", False).execute()
        docs_nao_agro = len(nao_agro.data) if nao_agro.data else 0
    else:
        docs_agro = 0
        docs_nao_agro = 0

    # Checkpoint local
    checkpoint = {}
    if os.path.exists("coleta_checkpoint.json"):
        with open("coleta_checkpoint.json") as f:
            checkpoint = json.load(f)

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "escopo": "APENAS AGRICULTURA",
        "documentos_total": docs_agro + docs_nao_agro,
        "documentos_em_licitacoes_agro": docs_agro,
        "documentos_em_licitacoes_nao_agro": docs_nao_agro,
        "checkpoint_local": checkpoint,
        "status": "⚠️ DESFOCADO - Maioria dos PDFs sao nao-agricolas!" if docs_nao_agro > docs_agro else "✅ OK"
    }

def main():
    if len(sys.argv) < 2:
        print("Uso: python dados_atualizados_agro.py [--resumo|--licitacoes-recentes|--status-coleta]")
        sys.exit(1)

    comando = sys.argv[1]

    try:
        if comando == "--resumo":
            resultado = get_resumo_dados_agro()
        elif comando == "--licitacoes-recentes":
            limite = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            resultado = get_licitacoes_recentes_agro(limite)
        elif comando == "--status-coleta":
            resultado = get_status_coleta_agro()
        else:
            print(f"Comando desconhecido: {comando}")
            sys.exit(1)

        print(json.dumps(resultado, indent=2, default=str))
    except Exception as e:
        print(json.dumps({
            "erro": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }, indent=2), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
