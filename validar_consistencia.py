#!/usr/bin/env python3
"""
Agente de validação de consistência entre Supabase e frontend.
Verifica: cobertura temporal, simulação de queries, row counts, views.

Uso:
  python validar_consistencia.py
  python validar_consistencia.py --json (output JSON ao invés de pretty-print)
"""

import os
import sys
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ ERRO: SUPABASE_URL e SUPABASE_KEY não encontradas em .env", file=sys.stderr)
    sys.exit(1)

sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# === Data structures ===

class Verificacao:
    def __init__(self, nome: str, status: str, detalhe: str):
        self.nome = nome
        self.status = status  # 'OK', 'AVISO', 'CRITICO'
        self.detalhe = detalhe

    def to_dict(self) -> Dict[str, Any]:
        return {
            'nome': self.nome,
            'status': self.status,
            'detalhe': self.detalhe,
        }


class RelatorioConsistencia:
    def __init__(self):
        self.gerado_em = datetime.now().isoformat()
        self.verificacoes: List[Verificacao] = []

    @property
    def status_geral(self) -> str:
        if any(v.status == 'CRITICO' for v in self.verificacoes):
            return 'CRITICO'
        if any(v.status == 'AVISO' for v in self.verificacoes):
            return 'AVISO'
        return 'OK'

    def add(self, verificacao: Verificacao):
        self.verificacoes.append(verificacao)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'gerado_em': self.gerado_em,
            'status_geral': self.status_geral,
            'verificacoes': [v.to_dict() for v in self.verificacoes],
        }


# === Verificações ===

def verificar_cobertura_temporal(sb: Client) -> Verificacao:
    """Verifica range de dt_abertura em tabelas e views chave."""
    try:
        # Tabela base: licitacoes
        resp_lic = sb.from_('licitacoes').select('dt_abertura').execute()
        lic_dates = [row['dt_abertura'] for row in resp_lic.data if row['dt_abertura']]
        lic_min = min(lic_dates) if lic_dates else None
        lic_max = max(lic_dates) if lic_dates else None

        # View: vw_itens_agro
        resp_agro = sb.from_('vw_itens_agro').select('dt_abertura').limit(10000).execute()
        agro_dates = [row['dt_abertura'] for row in resp_agro.data if row['dt_abertura']]
        agro_min = min(agro_dates) if agro_dates else None
        agro_max = max(agro_dates) if agro_dates else None

        # View: vw_itens_agro_puros
        resp_puros = sb.from_('vw_itens_agro_puros').select('dt_abertura').limit(10000).execute()
        puros_dates = [row['dt_abertura'] for row in resp_puros.data if row['dt_abertura']]
        puros_min = min(puros_dates) if puros_dates else None
        puros_max = max(puros_dates) if puros_dates else None

        detalhe = (
            f"licitacoes: {lic_min} a {lic_max} | "
            f"vw_itens_agro: {agro_min} a {agro_max} | "
            f"vw_itens_agro_puros: {puros_min} a {puros_max}"
        )

        # Se alguma view não tem 2026, avisar
        status = 'OK'
        if puros_max and puros_max.startswith('202') and puros_max < '2025':
            status = 'CRITICO'
            detalhe += " | ⚠️ vw_itens_agro_puros NÃO tem dados de 2025-2026!"
        elif agro_max and agro_max < '2025':
            status = 'AVISO'
            detalhe += " | ⚠️ vw_itens_agro sem dados recentes"

        return Verificacao('cobertura_temporal', status, detalhe)

    except Exception as e:
        return Verificacao('cobertura_temporal', 'CRITICO', f"Erro ao consultar: {str(e)}")


def verificar_simulacao_dashboard(sb: Client) -> Verificacao:
    """
    Simula exatamente a query do Dashboard.tsx (sem ORDER, sem LIMIT explícito).
    PostgREST default é 1000 rows. Se retorna < 1000, OK.
    Se retorna 1000 exato, AVISO (pode ter truncamento).
    """
    try:
        resp = sb.from_('vw_itens_agro_puros').select(
            'cultura, canal, valor_total, dt_abertura, qt_solicitada, categoria_v2'
        ).execute()

        rows_returned = len(resp.data) if resp.data else 0

        if resp.data:
            anos_retornados = sorted(set(
                row['dt_abertura'][:4] for row in resp.data
                if row['dt_abertura']
            ))
            anos_str = ', '.join(anos_retornados)
        else:
            anos_str = "(nenhum)"

        # Agora consulta o total real (sem limite)
        resp_total = sb.from_('vw_itens_agro_puros').select('id').execute()
        total_real = len(resp_total.data) if resp_total.data else 0

        detalhe = f"Dashboard retorna {rows_returned} de {total_real} rows (anos: {anos_str})"
        status = 'OK'

        if rows_returned == 1000 and total_real > 1000:
            status = 'AVISO'
            detalhe += " | ⚠️ PostgREST limitou a 1000! Dados de 2025-2026 podem estar fora."
        elif rows_returned < total_real * 0.5:
            status = 'CRITICO'
            detalhe += f" | ⚠️ CRÍTICO: Dashboard vê apenas ~{int(rows_returned/total_real*100)}% dos dados!"

        return Verificacao('simulacao_dashboard', status, detalhe)

    except Exception as e:
        return Verificacao('simulacao_dashboard', 'CRITICO', f"Erro ao simular: {str(e)}")


def verificar_simulacao_consultas(sb: Client) -> Verificacao:
    """
    Simula query de Consultas.tsx: ORDER BY dt_abertura DESC, LIMIT 1000.
    Verifica se retorna dados recentes.
    """
    try:
        resp = sb.from_('vw_itens_agro_puros').select(
            '*'
        ).order('dt_abertura', {'ascending': False}).limit(1000).execute()

        rows = len(resp.data) if resp.data else 0
        if resp.data:
            anos = sorted(set(
                row['dt_abertura'][:4] for row in resp.data
                if row['dt_abertura']
            ), reverse=True)
            anos_str = ', '.join(anos[:3])  # primeiros 3 anos
            primeiro_ano = anos[0] if anos else "?"
        else:
            anos_str = "(nenhum)"
            primeiro_ano = "?"

        detalhe = f"Consultas.tsx retorna {rows} rows, anos mais recentes: {anos_str}"
        status = 'OK'

        # Se o ano mais recente não é 2026, avisar
        if primeiro_ano < '2025':
            status = 'AVISO'
            detalhe += " | ⚠️ Dados mais recentes não são de 2026!"

        return Verificacao('simulacao_consultas', status, detalhe)

    except Exception as e:
        return Verificacao('simulacao_consultas', 'AVISO', f"Erro ao simular: {str(e)}")


def verificar_row_counts(sb: Client) -> Verificacao:
    """Conta linhas em tabelas e views chave."""
    try:
        counts = {}
        for table in ['licitacoes', 'itens_licitacao', 'fornecedores', 'participacoes', 'empenhos']:
            resp = sb.from_(table).select('id', count='exact').limit(0).execute()
            counts[table] = resp.count if resp.count is not None else -1

        # Views (sem count=exact, só contam com limit grande)
        for view in ['vw_itens_agro', 'vw_itens_agro_puros']:
            resp = sb.from_(view).select('id').limit(50000).execute()
            counts[view] = len(resp.data) if resp.data else 0

        detalhe = ' | '.join([f"{k}={v}" for k, v in counts.items()])

        # Se alguma tabela tiver 0 linhas, CRITICO
        if any(v == 0 for v in counts.values()):
            status = 'CRITICO'
            detalhe += " | ⚠️ CRÍTICO: Tabela/View com 0 linhas!"
        else:
            status = 'OK'

        return Verificacao('row_counts', status, detalhe)

    except Exception as e:
        return Verificacao('row_counts', 'AVISO', f"Erro ao contar: {str(e)}")


def verificar_views_funcionam(sb: Client) -> Verificacao:
    """Verifica se views retornam dados (não estão quebradas)."""
    try:
        status_views = {}
        for view in ['vw_itens_agro', 'vw_itens_agro_puros', 'vw_demanda_agro_ano']:
            resp = sb.from_(view).select('*').limit(1).execute()
            status_views[view] = 'OK' if resp.data else 'VAZIA'

        detalhe = ' | '.join([f"{k}={v}" for k, v in status_views.items()])
        status = 'CRITICO' if any(v == 'VAZIA' for v in status_views.values()) else 'OK'

        return Verificacao('views_funcionam', status, detalhe)

    except Exception as e:
        return Verificacao('views_funcionam', 'CRITICO', f"Erro ao verificar views: {str(e)}")


def verificar_threshold_alertas(sb: Client) -> Verificacao:
    """
    Verifica se o endpoint /alertas está usando threshold correto.
    Nota: Não conseguimos verificar o código Python direto, mas podemos avisar
    se há dados recentes que justificam revisão do threshold.
    """
    try:
        # Verifica o ano mais recente com dados
        resp = sb.from_('vw_itens_agro_puros').select('dt_abertura').limit(10000).execute()
        dates = [row['dt_abertura'] for row in resp.data if row['dt_abertura']]
        max_date = max(dates) if dates else None

        detalhe = f"Ano máximo nos dados: {max_date[:4] if max_date else '?'}"
        status = 'OK'

        # Se temos dados de 2026, o hardcoded "antes de 2025" está obsoleto
        if max_date and max_date >= '2025':
            status = 'AVISO'
            detalhe += " | ⚠️ /alertas usa threshold hardcoded 'antes de 2025' — revisar para rolling 12-meses"

        return Verificacao('threshold_alertas', status, detalhe)

    except Exception as e:
        return Verificacao('threshold_alertas', 'AVISO', f"Erro ao verificar: {str(e)}")


# === Color codes for pretty-print ===

COLORS = {
    'OK': '\033[92m',       # green
    'AVISO': '\033[93m',    # yellow
    'CRITICO': '\033[91m',  # red
    'RESET': '\033[0m',
    'BOLD': '\033[1m',
}


def print_relatorio(rel: RelatorioConsistencia, json_mode: bool = False):
    """Imprime relatório de forma colorida ou JSON."""
    if json_mode:
        print(json.dumps(rel.to_dict(), indent=2, ensure_ascii=False))
        return

    print(f"\n{COLORS['BOLD']}AgroIA-RMC — Validação de Consistência{COLORS['RESET']}")
    print(f"Gerado em: {rel.gerado_em}")
    print(f"Status Geral: {COLORS[rel.status_geral]}{rel.status_geral}{COLORS['RESET']}")
    print("\n" + "=" * 80)

    for v in rel.verificacoes:
        symbol = {
            'OK': '✓',
            'AVISO': '⚠',
            'CRITICO': '✗',
        }[v.status]
        color = COLORS[v.status]
        print(
            f"{color}{symbol} {v.nome.upper()}{COLORS['RESET']}\n"
            f"   {v.detalhe}\n"
        )

    print("=" * 80)


# === Main ===

def main():
    json_mode = '--json' in sys.argv

    print("Conectando ao Supabase...", file=sys.stderr)
    rel = RelatorioConsistencia()

    rel.add(verificar_cobertura_temporal(sb))
    rel.add(verificar_simulacao_dashboard(sb))
    rel.add(verificar_simulacao_consultas(sb))
    rel.add(verificar_row_counts(sb))
    rel.add(verificar_views_funcionam(sb))
    rel.add(verificar_threshold_alertas(sb))

    print_relatorio(rel, json_mode=json_mode)

    # Exit code baseado no status geral
    sys.exit(0 if rel.status_geral == 'OK' else 1)


if __name__ == '__main__':
    main()
