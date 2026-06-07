"""Pacote de benchmark de motores LLM (AgroIA-RMC).

Pacote ISOLADO: importa apenas LEITURA de chat.tools (TOOLS_SCHEMA, executar_tool)
e chat.prompts (SYSTEM_PROMPT). NUNCA importa chat.agent — reimplementa um mini-loop
agêntico próprio (benchmark.agentic_loop) para não tocar o caminho de produção.

Uso típico:
    python -m benchmark.benchmark_executor --motores claude --reps 1 --perguntas L02
"""
