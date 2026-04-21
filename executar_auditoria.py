#!/usr/bin/env python3
"""
Launcher - Selecione e execute auditorias de documentos agrícolas
"""

import os
import sys
import subprocess
from datetime import datetime

def menu():
    """Exibe menu de opções."""
    print("\n" + "=" * 70)
    print("AUDITORIA DE DOCUMENTOS AGRÍCOLAS - AgroIA-RMC")
    print("=" * 70)
    print("\nEscolha uma opção:\n")
    print("  [1] Auditoria Rápida (análise básica de cobertura)")
    print("  [2] Auditoria Avançada (análise completa com validação)")
    print("  [3] Executar Queries SQL no Supabase (manual)")
    print("  [4] Ver Último Relatório Gerado")
    print("  [5] Ver Guia Completo (AUDITORIA_GUIA.md)")
    print("  [0] Sair")
    print("\n" + "-" * 70)
    return input("Opção: ").strip()

def executar_auditoria_rapida():
    """Executa auditoria simples."""
    print("\n🚀 Iniciando Auditoria Rápida...\n")
    try:
        result = subprocess.run(
            [sys.executable, "auditoria_documentos_agro.py"],
            check=True
        )
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao executar: {e}")
        return False

def executar_auditoria_avancada():
    """Executa auditoria avançada."""
    print("\n🚀 Iniciando Auditoria Avançada...\n")
    try:
        result = subprocess.run(
            [sys.executable, "auditoria_avancada.py"],
            check=True
        )
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao executar: {e}")
        return False

def exibir_ultimo_relatorio():
    """Exibe o último relatório gerado."""
    import json
    import glob

    arquivos = sorted(glob.glob("auditoria_relatorio_*.json"), reverse=True)
    if not arquivos:
        arquivos_antigos = ["auditoria_relatorio.json"]
        arquivos = [f for f in arquivos_antigos if os.path.exists(f)]

    if not arquivos:
        print("\n❌ Nenhum relatório encontrado.")
        return

    arquivo = arquivos[0]
    print(f"\n📄 Último Relatório: {arquivo}\n")

    try:
        with open(arquivo, "r", encoding="utf-8") as f:
            relatorio = json.load(f)

        # Exibir resumo
        resumo = relatorio.get("resumo", {})
        print("📊 RESUMO EXECUTIVO:")
        print(f"  • Licitações agrícolas: {resumo.get('licitacoes_agro_total', 0)}")
        print(f"  • Documentos coletados: {resumo.get('documentos_coletados', 0)}")
        print(f"  • Taxa de cobertura: {resumo.get('taxa_cobertura_pct', 0):.1f}%")
        print(f"  • Alertas críticos: {resumo.get('alertas_criticos', 0)}")
        print(f"  • Alertas graves: {resumo.get('alertas_graves', 0)}")

        # Exibir alertas
        alertas = relatorio.get("alertas", {})
        if alertas.get("ERRO_BD"):
            print(f"\n🚨 ALERTAS ERRO_BD:")
            for alerta in alertas["ERRO_BD"][:3]:
                print(f"  • {alerta[:70]}")

        if alertas.get("INCONSISTENCIA_PORTAL"):
            print(f"\n⚠️ ALERTAS INCONSISTENCIA_PORTAL:")
            for alerta in alertas["INCONSISTENCIA_PORTAL"][:3]:
                print(f"  • {alerta[:70]}")

        print(f"\n💾 Relatório completo salvo em: {arquivo}")

    except json.JSONDecodeError:
        print(f"❌ Erro ao ler JSON: {arquivo}")
    except Exception as e:
        print(f"❌ Erro: {e}")

def exibir_guia():
    """Exibe o guia de auditoria."""
    try:
        with open("AUDITORIA_GUIA.md", "r", encoding="utf-8") as f:
            conteudo = f.read()
        print("\n" + conteudo)
    except FileNotFoundError:
        print("\n❌ Arquivo AUDITORIA_GUIA.md não encontrado")

def exibir_menu_sql():
    """Menu para exibir queries SQL."""
    print("\n📋 QUERIES SQL DISPONÍVEIS:\n")
    print("  [1] Q1: Sumário Geral")
    print("  [2] Q2: Licitações Sem Documentos (ERRO_BD)")
    print("  [3] Q3: Cobertura por Situação")
    print("  [4] Q4: Análise por Categoria Agrícola")
    print("  [5] Q5: Inconsistência Portal")
    print("  [6] Q6: Distribuição Temporal")
    print("  [7] Q7: Duplicados/Qualidade")
    print("  [8] Q8: Empenhos vs Documentos")
    print("  [9] Q9: Sumário Executivo de Alertas")
    print("  [10] Q10: Relatório Detalhado (TOP 50)")
    print("  [0] Voltar")
    print("\n" + "-" * 70)

    opcao = input("Opção: ").strip()

    if opcao == "0":
        return

    # Mapear opção para query
    queries_map = {
        "1": ("Sumário Geral", "sumario"),
        "2": ("Licitações Sem Documentos", "sem_documentos"),
        "3": ("Cobertura por Situação", "cobertura"),
        "4": ("Análise por Categoria", "categoria"),
        "5": ("Inconsistência Portal", "inconsistencia_portal"),
        "6": ("Distribuição Temporal", "temporal"),
        "7": ("Duplicados/Qualidade", "duplicados"),
        "8": ("Empenhos vs Documentos", "empenhos"),
        "9": ("Sumário Executivo", "sumario_exec"),
        "10": ("Relatório Detalhado", "relatorio_detalhado"),
    }

    if opcao not in queries_map:
        print("❌ Opção inválida")
        return

    titulo, nome_query = queries_map[opcao]

    print(f"\n📊 {titulo.upper()}\n")
    print("Instruções:")
    print("1. Abra: https://supabase.com → Seu Projeto → SQL Editor")
    print("2. Copie a query abaixo")
    print("3. Cole no editor e execute (Ctrl+Enter)\n")
    print("-" * 70)

    # Ler queries do arquivo SQL
    try:
        with open("auditoria_queries.sql", "r", encoding="utf-8") as f:
            conteudo = f.read()

        # Extrair a query específica
        # Format: -- VIEW/QUERY X: ...
        lines = conteudo.split("\n")
        inicio = None
        fim = None

        for i, line in enumerate(lines):
            if f"QUERY {opcao}" in line or f"VIEW {opcao}" in line or f"Q{opcao}:" in line:
                inicio = i
            elif inicio is not None and line.startswith("--"):
                fim = i
                break

        if inicio is not None:
            if fim is None:
                fim = len(lines)

            query = "\n".join(lines[inicio:fim]).strip()
            # Remover comentários de cabeçalho
            query_lines = [
                l for l in query.split("\n")
                if not l.strip().startswith("--")
            ]
            query = "\n".join(query_lines).strip()

            print(query)
            print("\n" + "-" * 70)
            print("\n✅ Query copiada para clipboard (copie manualmente se necessário)")

    except FileNotFoundError:
        print("❌ Arquivo auditoria_queries.sql não encontrado")

def main():
    """Loop principal."""
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    while True:
        opcao = menu()

        if opcao == "1":
            sucesso = executar_auditoria_rapida()
            if sucesso:
                print("\n✅ Auditoria concluída!")
                exibir_ultimo_relatorio()

        elif opcao == "2":
            sucesso = executar_auditoria_avancada()
            if sucesso:
                print("\n✅ Auditoria concluída!")
                exibir_ultimo_relatorio()

        elif opcao == "3":
            exibir_menu_sql()

        elif opcao == "4":
            exibir_ultimo_relatorio()

        elif opcao == "5":
            exibir_guia()

        elif opcao == "0":
            print("\n👋 Até logo!\n")
            break

        else:
            print("\n❌ Opção inválida")

        input("\nPressione Enter para continuar...")

if __name__ == "__main__":
    main()
