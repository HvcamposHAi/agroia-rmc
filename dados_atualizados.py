#!/usr/bin/env python3
"""
Script para obter dados SEMPRE ATUALIZADOS do banco de dados Supabase.
Usado pelo Assistente para garantir que nunca mostre dados desatualizados.

Execução:
  python dados_atualizados.py --resumo
  python dados_atualizados.py --licitacoes-recentes 10
  python dados_atualizados.py --status-coleta
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

def get_resumo_dados():
    """Retorna um resumo executivo dos dados atualizados"""
    sb = carregar_supabase()

    # Total de licitacoes
    result = sb.table("licitacoes").select("count", count="exact").execute()
    total_licitacoes = result.count

    # Data minima e maxima
    result = sb.table("licitacoes").select("*").order("dt_abertura").limit(1).execute()
    data_minima = result.data[0]['dt_abertura'] if result.data else None

    result = sb.table("licitacoes").select("*").order("dt_abertura", desc=True).limit(1).execute()
    data_maxima = result.data[0]['dt_abertura'] if result.data else None
    licitacao_mais_recente = result.data[0]['processo'] if result.data else None

    # Documentos
    result = sb.table("documentos_licitacao").select("count", count="exact").execute()
    total_documentos = result.count

    # Licitacoes com documentos
    result = sb.table("documentos_licitacao").select("licitacao_id").execute()
    lics_com_docs = len(set(d['licitacao_id'] for d in result.data)) if result.data else 0

    # Contagem por ano
    result = sb.table("licitacoes").select("*").execute()
    por_ano = {}
    for ano in range(2019, 2027):
        inicio = f"{ano}-01-01"
        fim = f"{ano}-12-31"
        r = sb.table("licitacoes").select("count", count="exact").gte("dt_abertura", inicio).lte("dt_abertura", fim).execute()
        if r.count > 0:
            por_ano[ano] = r.count

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "total_licitacoes": total_licitacoes,
        "data_minima": data_minima,
        "data_maxima": data_maxima,
        "licitacao_mais_recente": licitacao_mais_recente,
        "total_documentos": total_documentos,
        "licitacoes_com_documentos": lics_com_docs,
        "cobertura_documentos_pct": round((lics_com_docs / total_licitacoes * 100), 1) if total_licitacoes > 0 else 0,
        "distribuicao_por_ano": por_ano
    }

def get_licitacoes_recentes(limite=10):
    """Retorna as N licitacoes mais recentes"""
    sb = carregar_supabase()
    result = sb.table("licitacoes").select("processo, dt_abertura, objeto, situacao").order("dt_abertura", desc=True).limit(limite).execute()

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
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

def get_status_coleta():
    """Retorna status da coleta de PDFs"""
    sb = carregar_supabase()

    # Documentos OK e com erro
    ok = sb.table("documentos_licitacao").select("count", count="exact").is_("erro", "null").execute()
    com_erro = sb.table("documentos_licitacao").select("count", count="exact").not_.is_("erro", "null").execute()

    # Checkpoint local
    checkpoint = {}
    if os.path.exists("coleta_checkpoint.json"):
        with open("coleta_checkpoint.json") as f:
            checkpoint = json.load(f)

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "documentos_total": ok.count + com_erro.count,
        "documentos_ok": ok.count,
        "documentos_com_erro": com_erro.count,
        "checkpoint_local": checkpoint,
        "status": "COMPLETO" if checkpoint.get("ultima_pagina") == 0 else "EM_PROGRESSO"
    }

def main():
    if len(sys.argv) < 2:
        print("Uso: python dados_atualizados.py [--resumo|--licitacoes-recentes|--status-coleta]")
        sys.exit(1)

    comando = sys.argv[1]

    try:
        if comando == "--resumo":
            resultado = get_resumo_dados()
        elif comando == "--licitacoes-recentes":
            limite = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            resultado = get_licitacoes_recentes(limite)
        elif comando == "--status-coleta":
            resultado = get_status_coleta()
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
