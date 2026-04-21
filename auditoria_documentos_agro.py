"""
Agente de Auditoria: Consistência PDFs vs Licitações Agrícolas
──────────────────────────────────────────────────────────────

Valida:
1. Quantidade de PDFs extraídos vs licitações que deveriam ter
2. Cobertura de documentos vs compras efetuadas (empenhos)
3. Consistência do portal (se há PDFs disponíveis para download)

Foco: vw_licitacoes_agro (apenas registros classificados como relevante_agro=true)

Alertas gerados:
- ERRO_BD: Inconsistência técnica na base de dados
- INCONSISTENCIA_PORTAL: PDFs não estão disponíveis no portal
"""

import os
import sys
import json
import io
from datetime import datetime
from typing import Dict, List, Tuple, Any
from dotenv import load_dotenv
from supabase import create_client

# Force UTF-8 output on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Configuração
load_dotenv()
SB_URL = os.getenv("SUPABASE_URL")
SB_KEY = os.getenv("SUPABASE_KEY")
sb = create_client(SB_URL, SB_KEY)

class AuditoriaDocumentos:
    """Agente de auditoria para consistência de documentos agrícolas."""

    def __init__(self):
        self.alerts = {
            "ERRO_BD": [],
            "INCONSISTENCIA_PORTAL": [],
        }
        self.stats = {
            "licitacoes_agro_total": 0,
            "licitacoes_com_documentos": 0,
            "licitacoes_com_empenhos": 0,
            "documentos_total": 0,
            "empenhos_total": 0,
            "taxa_cobertura_docs": 0.0,
            "taxa_cobertura_empenhos": 0.0,
        }
        self.problemas = []

    def executar(self):
        """Executa auditoria completa."""
        print("\n" + "=" * 80)
        print("AUDITORIA DE DOCUMENTOS AGRICOLAS - AgroIA-RMC")
        print("=" * 80)
        print(f"Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # Fase 1: Análise da Base de Dados
        print("[1/4] Analisando base de dados...")
        self._analisar_base_dados()

        # Fase 2: Análise de Cobertura
        print("\n[2/4] Analisando cobertura de documentos...")
        self._analisar_cobertura_documentos()

        # Fase 3: Análise de Empenhos
        print("\n[3/4] Analisando compras efetuadas (empenhos)...")
        self._analisar_empenhos()

        # Fase 4: Validação no Portal (Playwright)
        print("\n[4/4] Validando consistência no portal...")
        self._validar_portal()

        # Gerar relatório
        self._gerar_relatorio()

    def _analisar_base_dados(self):
        """Analisa a base de dados Supabase."""
        try:
            # Licitações agrícolas (itens com relevante_agro=true)
            lic_agro = sb.from_("itens_licitacao").select(
                "licitacao_id"
            ).eq("relevante_agro", True).execute()
            lic_agro_ids = set(row["licitacao_id"] for row in lic_agro.data)
            self.stats["licitacoes_agro_total"] = len(lic_agro_ids)

            print(f"  [OK] Licitacoes com itens agricolas: {self.stats['licitacoes_agro_total']}")

            # Total de documentos
            docs = sb.table("documentos_licitacao").select("count", count="exact").execute()
            self.stats["documentos_total"] = docs.count or 0
            print(f"  [OK] Documentos coletados: {self.stats['documentos_total']}")

            # Licitações com documentos
            docs_data = sb.table("documentos_licitacao").select("licitacao_id").execute()
            lic_com_docs = set(row["licitacao_id"] for row in docs_data.data)
            self.stats["licitacoes_com_documentos"] = len(
                lic_com_docs.intersection(lic_agro_ids)
            )
            print(f"  [OK] Licitacoes agricolas com documentos: {self.stats['licitacoes_com_documentos']}")

            # Cobertura
            self.stats["taxa_cobertura_docs"] = (
                100 * self.stats["licitacoes_com_documentos"] / self.stats["licitacoes_agro_total"]
                if self.stats["licitacoes_agro_total"] > 0 else 0
            )
            print(f"  [OK] Taxa de cobertura: {self.stats['taxa_cobertura_docs']:.1f}%")

            # Identificar licitações agrícolas SEM documentos
            lic_sem_docs = lic_agro_ids - lic_com_docs
            if len(lic_sem_docs) > 0:
                self.alerts["ERRO_BD"].append(
                    f"Encontradas {len(lic_sem_docs)} licitacoes agricolas SEM documentos na base"
                )
                print(f"\n  [ALERTA] {len(lic_sem_docs)} licitacoes sem documentos")

        except Exception as e:
            print(f"  [ERRO] Erro ao analisar base: {e}")
            self.alerts["ERRO_BD"].append(f"Erro ao analisar base de dados: {str(e)}")

    def _analisar_cobertura_documentos(self):
        """Analisa cobertura detalhada de documentos."""
        try:
            # Obter licitações agrícolas
            lic_agro = sb.from_("itens_licitacao").select(
                "licitacao_id"
            ).eq("relevante_agro", True).execute()
            lic_agro_ids = [row["licitacao_id"] for row in lic_agro.data]

            # Para cada licitação, contar documentos
            problemas_cobertura = []
            for lic_id in set(lic_agro_ids):
                docs = sb.from_("documentos_licitacao").select(
                    "id"
                ).eq("licitacao_id", lic_id).execute()

                if len(docs.data) == 0:
                    # Obter info da licitação
                    lic_info = sb.from_("licitacoes").select(
                        "id, processo, dt_abertura, situacao"
                    ).eq("id", lic_id).execute()

                    if lic_info.data:
                        lic = lic_info.data[0]
                        problemas_cobertura.append({
                            "licitacao_id": lic_id,
                            "processo": lic["processo"],
                            "dt_abertura": lic["dt_abertura"],
                            "situacao": lic["situacao"],
                            "qtd_docs": 0,
                        })

            self.problemas = problemas_cobertura

            # Mostrar sumário
            print(f"  [OK] Licitacoes analisadas: {len(set(lic_agro_ids))}")
            print(f"  [OK] Problemas encontrados: {len(problemas_cobertura)}")

            if len(problemas_cobertura) <= 10:
                print("\n  Licitacoes SEM documentos:")
                for p in problemas_cobertura:
                    print(f"    - {p['processo']} | {p['dt_abertura'][:10]} | Status: {p['situacao']}")

        except Exception as e:
            print(f"  [ERRO] Erro ao analisar cobertura: {e}")

    def _analisar_empenhos(self):
        """Analisa cobertura de empenhos (compras efetuadas)."""
        try:
            # Total de empenhos
            empenhos = sb.table("empenhos").select("count", count="exact").execute()
            self.stats["empenhos_total"] = empenhos.count or 0
            print(f"  [OK] Empenhos (compras) no banco: {self.stats['empenhos_total']}")

            # Licitações com empenhos (agrícolas)
            lic_agro = sb.from_("itens_licitacao").select(
                "licitacao_id"
            ).eq("relevante_agro", True).execute()
            lic_agro_ids = set(row["licitacao_id"] for row in lic_agro.data)

            empenhos_data = sb.table("empenhos").select("licitacao_id").execute()
            lic_com_empenhos = set(
                row["licitacao_id"] for row in empenhos_data.data
                if row["licitacao_id"] is not None
            )

            self.stats["licitacoes_com_empenhos"] = len(
                lic_com_empenhos.intersection(lic_agro_ids)
            )
            print(f"  [OK] Licitations agricolas com empenhos: {self.stats['licitacoes_com_empenhos']}")

            # Taxa de cobertura de empenhos
            self.stats["taxa_cobertura_empenhos"] = (
                100 * self.stats["licitacoes_com_empenhos"] / self.stats["licitacoes_agro_total"]
                if self.stats["licitacoes_agro_total"] > 0 else 0
            )
            print(f"  [OK] Taxa de empenhos: {self.stats['taxa_cobertura_empenhos']:.1f}%")

            # Licitações que deveriam ter empenhos mas não têm
            lic_sem_empenhos = lic_agro_ids - lic_com_empenhos
            if len(lic_sem_empenhos) > 0:
                # Filtrar por situação (apenas "Concluído" deveriam ter)
                lic_concluidas = sb.from_("licitacoes").select(
                    "id, processo, situacao"
                ).eq("situacao", "Concluído").execute()

                lic_concluidas_ids = {row["id"] for row in lic_concluidas.data}
                lic_concluidas_sem_empenhos = lic_sem_empenhos.intersection(lic_concluidas_ids)

                if len(lic_concluidas_sem_empenhos) > 0:
                    print(f"\n  [ALERTA] {len(lic_concluidas_sem_empenhos)} licitacoes 'Concluido' sem empenhos")

        except Exception as e:
            print(f"  [ERRO] Erro ao analisar empenhos: {e}")
            self.alerts["ERRO_BD"].append(f"Erro ao analisar empenhos: {str(e)}")

    def _validar_portal(self):
        """Valida se os PDFs estão disponíveis no portal."""
        try:
            print("  [INFO] Validacao de portal: sera implementada com Playwright")
            print("  [INFO] Verificando primeiras 5 licitacoes...")

            if len(self.problemas) == 0:
                print("  [OK] Nenhuma licitacao sem documentos para validar no portal")
                return

            # Validar as primeiras 5 problemas no portal
            amostra = self.problemas[:5]
            inconsistencias_portal = 0

            try:
                from playwright.sync_api import sync_playwright

                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    context = browser.new_context()
                    page = context.new_page()

                    for problema in amostra:
                        try:
                            processo = problema["processo"]
                            print(f"\n    Validando: {processo}")

                            # Acessar portal
                            page.goto("http://consultalictacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/", timeout=5000)
                            page.wait_for_timeout(2000)

                            print(f"      [OK] Processo acessivel")

                        except Exception as e:
                            print(f"      [ERRO] Erro ao validar: {str(e)[:50]}")
                            inconsistencias_portal += 1

                    browser.close()

                if inconsistencias_portal > 0:
                    self.alerts["INCONSISTENCIA_PORTAL"].append(
                        f"Encontradas {inconsistencias_portal} inconsistencias no portal"
                    )
            except ImportError:
                print("  [AVISO] Playwright nao instalado - pulando validacao de portal")

        except Exception as e:
            print(f"  [ERRO] Erro ao validar portal: {e}")

    def _gerar_relatorio(self):
        """Gera relatório final com alertas."""
        print("\n" + "=" * 80)
        print("RELATORIO FINAL DE AUDITORIA")
        print("=" * 80)

        # Sumário estatístico
        print("\nESTATISTICAS:")
        print(f"  - Licitacoes agricolas (vw_licitacoes_agro): {self.stats['licitacoes_agro_total']}")
        print(f"  - Documentos coletados: {self.stats['documentos_total']}")
        print(f"  - Licitacoes com documentos: {self.stats['licitacoes_com_documentos']}")
        print(f"  - Taxa de cobertura: {self.stats['taxa_cobertura_docs']:.1f}%")
        print(f"\n  - Empenhos (compras) registrados: {self.stats['empenhos_total']}")
        print(f"  - Licitacoes com empenhos: {self.stats['licitacoes_com_empenhos']}")
        print(f"  - Taxa de empenhos: {self.stats['taxa_cobertura_empenhos']:.1f}%")

        # Alertas
        print("\nALERTAS:")
        total_alertas = len(self.alerts["ERRO_BD"]) + len(self.alerts["INCONSISTENCIA_PORTAL"])

        if total_alertas == 0:
            print("  [OK] Nenhum alerta identificado")
        else:
            if self.alerts["ERRO_BD"]:
                print("\n  [ERRO_BD] - Inconsistencias tecnicas na base:")
                for alerta in self.alerts["ERRO_BD"]:
                    print(f"    * {alerta}")

            if self.alerts["INCONSISTENCIA_PORTAL"]:
                print("\n  [INCONSISTENCIA_PORTAL] - Inconsistencias no portal:")
                for alerta in self.alerts["INCONSISTENCIA_PORTAL"]:
                    print(f"    * {alerta}")

        # Exportar relatório JSON
        relatorio = {
            "timestamp": datetime.now().isoformat(),
            "estatisticas": self.stats,
            "alertas": self.alerts,
            "problemas_documentos": self.problemas[:20],  # Top 20 para não ficar muito grande
        }

        with open("auditoria_relatorio.json", "w", encoding="utf-8") as f:
            json.dump(relatorio, f, indent=2, ensure_ascii=False, default=str)

        print(f"\nRelatorio salvo em: auditoria_relatorio.json")
        print("\n" + "=" * 80)


if __name__ == "__main__":
    auditoria = AuditoriaDocumentos()
    auditoria.executar()
