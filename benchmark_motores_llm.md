# Avaliação Comparativa de Motores LLM no AgroIA-RMC
## Proposta Metodológica para Dissertação de Mestrado

**Programa:** PPGCA/UEPG — Computação Aplicada  
**Linha:** Inteligência Computacional  
**Aluno:** Humberto Vinicius Aparecido de Campos  
**Orientador:** Prof. Jonathan de Matos  
**Norma:** ABNT NBR 6023/2002

---

## 1. Motores LLM Selecionados para Avaliação

A seleção dos motores obedece a dois critérios complementares: representatividade técnica (cobertura de diferentes arquiteturas e tamanhos de modelo) e relevância contextual (adequação ao idioma português e ao domínio de políticas públicas brasileiras).

### 1.1 Claude Haiku 4.5 — Motor de Referência (Baseline)

| Atributo | Valor |
|---|---|
| Provedor | Anthropic |
| Modelo | `claude-haiku-4-5-20251001` |
| Parâmetros | Não divulgado (estimado: 20B) |
| Contexto máximo | 200.000 tokens |
| Suporte a tool_use | Nativo |
| Custo (entrada) | USD 0,80 / 1M tokens |
| Custo (saída) | USD 4,00 / 1M tokens |
| Idioma nativo | Inglês (forte suporte a PT-BR) |
| Status no projeto | Em produção — `chat/agent.py` |

> Justificativa: Motor já integrado ao sistema. Funciona como linha de base para comparação. A escolha inicial do Claude Haiku se deve ao suporte nativo ao padrão `tool_use`, essencial para o loop agêntico de consultas ao Supabase.

---

### 1.2 Llama 3.1 8B — Motor Open-Source

| Atributo | Valor |
|---|---|
| Provedor | Meta AI (open-weights) |
| Modelo | `llama-3.1-8b-instant` (via Groq API) |
| Parâmetros | 8 bilhões |
| Contexto máximo | 128.000 tokens |
| Suporte a tool_use | Sim (function calling via OpenAI-compatible API) |
| Custo (Groq free tier) | Gratuito (limitado a 14.400 tokens/min) |
| Custo (Groq pay) | USD 0,05 / 1M tokens |
| Idioma nativo | Inglês (suporte razoável a PT-BR) |
| Acesso | `https://api.groq.com/openai/v1` |

> Justificativa: O Llama 3.1 representa a principal referência open-weights da atualidade. O acesso via Groq API elimina a necessidade de infraestrutura GPU local, viabilizando os experimentos em ambiente acadêmico com custo próximo de zero. A Groq oferece latência ultra-baixa por hardware especializado (LPU), o que torna a comparação de latência especialmente relevante.

---

### 1.3 Sabiá-3 — Iniciativa Brasileira

| Atributo | Valor |
|---|---|
| Provedor | Maritaca AI (empresa brasileira) |
| Modelo | `sabia-3` |
| Parâmetros | Não divulgado |
| Contexto máximo | 8.192 tokens |
| Suporte a tool_use | Sim (OpenAI-compatible function calling) |
| Custo (entrada) | BRL 0,40 / 1M tokens |
| Custo (saída) | BRL 2,00 / 1M tokens |
| Idioma nativo | **Português brasileiro (treinamento primário)** |
| Acesso | `https://chat.maritaca.ai/api` (OpenAI-compatible) |
| Reconhecimento governamental | Citado pelo MCTI como uma das três iniciativas nacionais de LLM em português |

> Justificativa: O Sabiá-3 é o único motor da seleção treinado primariamente em português brasileiro, com dados culturais e legislativos nacionais. A Ministra de Ciência, Tecnologia e Inovação, em abril de 2025, citou o Sabiá entre as três iniciativas nacionais de LLM em português consideradas pelo governo federal para composição de um LLM soberano brasileiro (Web Summit Rio, abril/2025). O modelo é mantido pela Maritaca AI, empresa com raízes na UNICAMP e parcerias com FAPESP e BNDES. A inclusão deste motor possui relevância acadêmica direta: o domínio do AgroIA-RMC (licitações públicas, agricultura familiar, PNAE, PAA) é intrinsecamente brasileiro, tornando o desempenho em português técnico um critério diferenciador.

---

### 1.4 Quadro Comparativo Geral

| Critério | Claude Haiku 4.5 | Llama 3.1 8B | Sabiá-3 |
|---|---|---|---|
| Tipo | Proprietário | Open-weights | Proprietário (BR) |
| Origem | EUA | EUA | Brasil |
| Português nativo | Não | Não | **Sim** |
| Tool use | Nativo | Via OpenAI compat. | Via OpenAI compat. |
| Custo / query (est.) | Médio | Baixo | Baixo (BRL) |
| Latência esperada | Média | **Baixa (Groq LPU)** | Média |
| Contexto | 200k tokens | 128k tokens | 8k tokens |
| Dados gov. BR | Não | Não | **Sim (parcial)** |

---

## 2. Adaptação da Arquitetura para Variação de Motor

### 2.1 Princípio: Padrão Strategy (GoF)

A solução adota o padrão de projeto **Strategy** para desacoplar o motor LLM do loop agêntico. A chamada à API Anthropic, hoje acoplada diretamente em `chat/agent.py`, é extraída para uma camada de abstração `LLMProvider`.

### 2.2 Nova Estrutura de Diretórios

```
chat/
├── agent.py          # Loop agêntico — SEM referência a SDK específico
├── tools.py          # Sem alteração
├── prompts.py        # Sem alteração
├── db.py             # Sem alteração
└── providers/
    ├── __init__.py
    ├── base.py        # Classe abstrata LLMProvider
    ├── claude.py      # Implementação Anthropic
    ├── groq_llama.py  # Implementação Groq/Llama
    └── maritaca.py    # Implementação Sabiá-3
```

### 2.3 Classe Abstrata (`chat/providers/base.py`)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

@dataclass
class LLMResponse:
    texto: str
    stop_reason: str            # "end_turn" | "tool_use"
    tool_calls: list[dict] = field(default_factory=list)
    tokens_entrada: int = 0
    tokens_saida: int = 0
    latencia_ms: float = 0.0

class LLMProvider(ABC):
    """Interface comum para todos os motores LLM."""

    @abstractmethod
    def completar(
        self,
        messages: list[dict],
        system: str,
        tools: list[dict],
        max_tokens: int = 2048,
        timeout: float = 30.0
    ) -> LLMResponse:
        ...

    @property
    @abstractmethod
    def nome(self) -> str:
        ...

    @property
    @abstractmethod
    def custo_por_token_entrada(self) -> float:
        """Custo em USD por token de entrada."""
        ...

    @property
    @abstractmethod
    def custo_por_token_saida(self) -> float:
        """Custo em USD por token de saída."""
        ...
```

### 2.4 Implementação Claude (`chat/providers/claude.py`)

```python
import time
import anthropic
from .base import LLMProvider, LLMResponse

class ClaudeProvider(LLMProvider):
    nome = "claude-haiku-4-5"
    custo_por_token_entrada = 0.80 / 1_000_000   # USD
    custo_por_token_saida   = 4.00 / 1_000_000

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    def completar(self, messages, system, tools, max_tokens=2048, timeout=30.0):
        t0 = time.monotonic()
        resp = self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            messages=messages,
            timeout=timeout
        )
        latencia = (time.monotonic() - t0) * 1000

        tool_calls = []
        if resp.stop_reason == "tool_use":
            tool_calls = [
                {"id": b.id, "name": b.name, "input": b.input}
                for b in resp.content if b.type == "tool_use"
            ]

        texto = next(
            (b.text for b in resp.content if hasattr(b, "text")), ""
        )

        return LLMResponse(
            texto=texto,
            stop_reason=resp.stop_reason,
            tool_calls=tool_calls,
            tokens_entrada=resp.usage.input_tokens,
            tokens_saida=resp.usage.output_tokens,
            latencia_ms=latencia
        )
```

### 2.5 Implementação Groq/Llama (`chat/providers/groq_llama.py`)

```python
import time
from openai import OpenAI
from .base import LLMProvider, LLMResponse

class GroqLlamaProvider(LLMProvider):
    nome = "llama-3.1-8b"
    custo_por_token_entrada = 0.05 / 1_000_000
    custo_por_token_saida   = 0.08 / 1_000_000

    def __init__(self, api_key: str):
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1"
        )

    def completar(self, messages, system, tools, max_tokens=2048, timeout=30.0):
        t0 = time.monotonic()
        msgs = [{"role": "system", "content": system}] + messages

        # Converter tool schema Anthropic → OpenAI
        oai_tools = [
            {"type": "function", "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"]
            }} for t in tools
        ] if tools else None

        resp = self.client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=msgs,
            tools=oai_tools,
            max_tokens=max_tokens,
            timeout=timeout
        )
        latencia = (time.monotonic() - t0) * 1000
        choice = resp.choices[0]

        tool_calls = []
        stop_reason = "end_turn"
        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            stop_reason = "tool_use"
            import json
            tool_calls = [
                {"id": tc.id, "name": tc.function.name,
                 "input": json.loads(tc.function.arguments)}
                for tc in choice.message.tool_calls
            ]

        return LLMResponse(
            texto=choice.message.content or "",
            stop_reason=stop_reason,
            tool_calls=tool_calls,
            tokens_entrada=resp.usage.prompt_tokens,
            tokens_saida=resp.usage.completion_tokens,
            latencia_ms=latencia
        )
```

### 2.6 Implementação Sabiá-3 (`chat/providers/maritaca.py`)

```python
import time
from openai import OpenAI
from .base import LLMProvider, LLMResponse

class MariticaSabiaProvider(LLMProvider):
    nome = "sabia-3"
    custo_por_token_entrada = 0.40 / 1_000_000  # BRL (converter para USD se necessário)
    custo_por_token_saida   = 2.00 / 1_000_000

    def __init__(self, api_key: str):
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://chat.maritaca.ai/api"
        )

    def completar(self, messages, system, tools, max_tokens=2048, timeout=30.0):
        t0 = time.monotonic()
        msgs = [{"role": "system", "content": system}] + messages

        oai_tools = [
            {"type": "function", "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"]
            }} for t in tools
        ] if tools else None

        resp = self.client.chat.completions.create(
            model="sabia-3",
            messages=msgs,
            tools=oai_tools,
            max_tokens=max_tokens,
            timeout=timeout
        )
        latencia = (time.monotonic() - t0) * 1000
        choice = resp.choices[0]

        tool_calls = []
        stop_reason = "end_turn"
        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            stop_reason = "tool_use"
            import json
            tool_calls = [
                {"id": tc.id, "name": tc.function.name,
                 "input": json.loads(tc.function.arguments)}
                for tc in choice.message.tool_calls
            ]

        return LLMResponse(
            texto=choice.message.content or "",
            stop_reason=stop_reason,
            tool_calls=tool_calls,
            tokens_entrada=resp.usage.prompt_tokens,
            tokens_saida=resp.usage.completion_tokens,
            latencia_ms=latencia
        )
```

### 2.7 Factory e Seleção via Variável de Ambiente (`chat/providers/__init__.py`)

```python
import os
from .base import LLMProvider
from .claude import ClaudeProvider
from .groq_llama import GroqLlamaProvider
from .maritaca import MariticaSabiaProvider

def get_provider() -> LLMProvider:
    motor = os.getenv("LLM_PROVIDER", "claude").lower()
    match motor:
        case "claude":
            return ClaudeProvider(os.getenv("ANTHROPIC_API_KEY"))
        case "llama":
            return GroqLlamaProvider(os.getenv("GROQ_API_KEY"))
        case "sabia":
            return MariticaSabiaProvider(os.getenv("MARITACA_API_KEY"))
        case _:
            raise ValueError(f"Motor desconhecido: {motor}")
```

### 2.8 Variável de Ambiente no `.env`

```dotenv
# Motor LLM ativo: claude | llama | sabia
LLM_PROVIDER=claude

# Chaves por motor
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...
MARITACA_API_KEY=...
```

### 2.9 Agent Refatorado (`chat/agent.py`)

```python
# Única mudança necessária no agent.py existente:

from .providers import get_provider   # ← substituir import anthropic

def chat(pergunta: str, historico: list[dict] = None) -> dict:
    provider = get_provider()         # ← substituir client = anthropic.Anthropic(...)
    messages = historico + [{"role": "user", "content": pergunta}]
    tools_usadas = []
    iteracao = 0

    while iteracao < 10:
        iteracao += 1
        resp = provider.completar(    # ← substituir client.messages.create(...)
            messages=messages,
            system=SYSTEM_PROMPT,
            tools=TOOLS_SCHEMA,
            timeout=30.0
        )

        if resp.stop_reason == "end_turn":
            return {"resposta": resp.texto, "tools_usadas": tools_usadas,
                    "motor": provider.nome, "latencia_ms": resp.latencia_ms,
                    "tokens": resp.tokens_entrada + resp.tokens_saida}

        elif resp.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": resp.texto or ""})
            tool_results = []
            for tc in resp.tool_calls:
                tools_usadas.append(tc["name"])
                resultado = executar_tool(tc["name"], tc["input"])
                tool_results.append({
                    "role": "tool",             # OpenAI format
                    "tool_call_id": tc["id"],
                    "content": json.dumps(resultado, ensure_ascii=False)
                })
            messages.append({"role": "user", "content": tool_results})
    # ...
```

> **Nota:** O campo `content` no formato tool_result diverge entre Anthropic e OpenAI. O provider abstrato normaliza esse detalhe internamente antes de enviar ao cliente SDK correspondente.

---

## 3. Indicadores de Avaliação

### 3.1 Conjunto de Perguntas de Teste (Benchmark Fixo)

Para garantir a validade interna do experimento, define-se um conjunto fixo de **20 perguntas de avaliação**, distribuídas em três categorias:

| Categoria | Quantidade | Exemplo |
|---|---|---|
| Consulta factual simples | 8 | "Qual foi o volume total de tomate licitado em 2023 no PNAE?" |
| Consulta agregada com filtros | 7 | "Quais cooperativas mais participaram de licitações do PAA entre 2021 e 2023?" |
| Consulta documental (RAG) | 5 | "Quais os critérios de habilitação do edital AD_3_2019?" |

Cada pergunta é submetida **3 vezes por motor** para estabilização estatística. Total: 20 × 3 motores × 3 repetições = **180 chamadas**.

---

### 3.2 Indicadores Quantitativos

#### I1 — Latência Média de Resposta (ms)

```
L_motor = média(latencia_ms) para todas as N respostas do motor
```

Coleta: campo `latencia_ms` do `LLMResponse`, medido com `time.monotonic()` do envio até o recebimento completo da resposta.

#### I2 — Custo Estimado por Consulta (USD)

```
C_query = (tokens_entrada × custo_entrada) + (tokens_saida × custo_saida)
C_motor = média(C_query) para todas as N respostas do motor
```

Para o Sabiá-3 (cotado em BRL), aplicar conversão cambial da data do experimento.

#### I3 — Taxa de Erro (%)

```
E_motor = (respostas_com_erro / total_respostas) × 100
```

Erros incluem: timeout, exceção HTTP, resposta vazia, tool_call com parâmetros inválidos rejeitados pelo Supabase.

#### I4 — Taxa de Acionamento Correto de Ferramentas (%)

```
F_motor = (tool_calls_corretas / total_tool_calls_esperadas) × 100
```

Para cada pergunta do benchmark, define-se previamente qual tool deveria ser acionada (gabarito). Avalia-se se o motor acionou a ferramenta correta com os parâmetros semanticamente adequados.

---

### 3.3 Indicadores Qualitativos

#### I5 — Qualidade de Resposta (Rubrica 1-5)

Avaliação humana (pelo pesquisador e, se possível, por um especialista do domínio) com a seguinte rubrica:

| Nota | Critério |
|---|---|
| 5 | Resposta completa, factualmente correta, em português claro e contextualizado |
| 4 | Resposta correta com pequena omissão ou imprecisão menor |
| 3 | Resposta parcialmente correta; dados corretos mas incompletos |
| 2 | Resposta com erro factual recuperável (dado errado mas estrutura correta) |
| 1 | Resposta incorreta, incoerente ou fora do escopo |

#### I6 — Adequação ao Domínio (Português Técnico-Jurídico)

Avaliação binária por pergunta: a terminologia utilizada na resposta é adequada ao domínio de licitações públicas brasileiras? (1 = sim, 0 = não)

```
D_motor = (respostas_adequadas / total_respostas) × 100
```

---

### 3.4 Consolidação dos Indicadores

| Indicador | Tipo | Unidade | Melhor valor | Peso sugerido |
|---|---|---|---|---|
| I1 — Latência média | Quantitativo | ms | Menor | 20% |
| I2 — Custo por consulta | Quantitativo | USD | Menor | 20% |
| I3 — Taxa de erro | Quantitativo | % | Menor | 20% |
| I4 — Precisão de tool use | Quantitativo | % | Maior | 20% |
| I5 — Qualidade (rubrica) | Qualitativo | 1-5 | Maior | 15% |
| I6 — Adequação ao domínio | Qualitativo | % | Maior | 5% |

O **Índice de Desempenho Composto (IDC)** pode ser calculado como:

```
IDC = 0,20 × norm(1/L) + 0,20 × norm(1/C) + 0,20 × norm(1-E) 
    + 0,20 × norm(F) + 0,15 × norm(Q) + 0,05 × norm(D)
```

Onde `norm()` é a normalização min-max no intervalo [0,1] entre os motores avaliados.

---

## 4. Tabela de Resultados Temporais das Coletas

### 4.1 Script de Registro (`benchmark_executor.py`)

```python
import json, csv, time, uuid
from datetime import datetime
from chat.providers import get_provider
from chat.agent import chat
from supabase import create_client
import os

PERGUNTAS_BENCHMARK = [
    {"id": "Q01", "categoria": "factual_simples",
     "pergunta": "Qual foi o volume total de tomate licitado em 2023 no PNAE?",
     "tool_esperada": "query_itens_agro"},
    # ... demais 19 perguntas
]

def executar_benchmark(motor: str):
    os.environ["LLM_PROVIDER"] = motor
    resultados = []

    for q in PERGUNTAS_BENCHMARK:
        for rep in range(1, 4):  # 3 repetições
            t_inicio = datetime.utcnow().isoformat()
            try:
                resultado = chat(q["pergunta"], [])
                status = "ok"
            except Exception as e:
                resultado = {"resposta": "", "latencia_ms": 0,
                             "tokens": 0, "tools_usadas": []}
                status = f"erro: {str(e)}"

            resultados.append({
                "run_id": str(uuid.uuid4()),
                "motor": motor,
                "questao_id": q["id"],
                "categoria": q["categoria"],
                "repeticao": rep,
                "dt_execucao": t_inicio,
                "latencia_ms": resultado.get("latencia_ms", 0),
                "tokens_total": resultado.get("tokens", 0),
                "tools_usadas": json.dumps(resultado.get("tools_usadas", [])),
                "status": status,
                "resposta": resultado.get("resposta", "")[:500]  # truncar
            })

    # Salvar CSV
    with open(f"benchmark_{motor}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
              "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=resultados[0].keys())
        writer.writeheader()
        writer.writerows(resultados)

    return resultados

if __name__ == "__main__":
    for motor in ["claude", "llama", "sabia"]:
        print(f"\n=== Executando benchmark: {motor} ===")
        executar_benchmark(motor)
```

---

### 4.2 Tabela de Resultados Temporais das Coletas de Dados (Etapas do AgroIA-RMC)

A tabela a seguir registra a evolução temporal da coleta de dados que constitui a base empírica da dissertação, consolidando as etapas de raspagem, processamento e indexação.

| Etapa | Descrição | Data Início | Data Fim (est.) | Registros Alvo | Registros Coletados | Cobertura (%) | Duração (h) | Script | Status |
|---|---|---|---|---|---|---|---|---|---|
| 1.0 | Coleta de processos (cabeçalho licitações) | 2025-03 | 2025-03 | — | 1.237 | 100,0 | ~2,0 | `etapa1_licitacoes.py` | Concluída |
| 2.0 | Coleta de itens, fornecedores e empenhos | 2026-04 | 2026-04 (em andamento) | 1.237 processos | ~7.882 itens | 99,8 | ~3,0 | `etapa2_itens_v9.py` | Em execução |
| 2.1 | Classificação agrícola dos itens | 2026-04 | 2026-04 | 7.882 itens | 743 (agro) | 9,4 | ~0,5 | `classificar_itens.py` | Concluída |
| 3.0 | Download de PDFs (editais e termos) | 2026-04 | 2026-04 | 1.237 + 23 | 544 | 43,9 | ~1,5 | `etapa3_producao.py` | Concluída* |
| 3.5 | Indexação de PDFs (OCR + embeddings) | 2026-04 | 2026-04 | 544 | 56 | 10,3 | ~0,5 | `indexar_pdfs.py` | Concluída |
| 4.0 | Benchmark de motores LLM | 2026-05 | 2026-05 | 180 calls | — | — | ~1,5 | `benchmark_executor.py` | Planejada |
| 5.0 | Análise qualitativa e consolidação | 2026-05 | 2026-06 | — | — | — | — | — | Planejada |

*544 de 1.260 tentativas (716 falharam por limitação do portal — documentado como limitação metodológica).

---

### 4.3 Tabela de Resultados do Benchmark (Modelo para Preenchimento)

A tabela abaixo apresenta o modelo de coleta de resultados a ser preenchido após a execução do benchmark. Os valores são exemplificativos.

| Motor | Qtd. Consultas | Latência Média (ms) | Desvio Padrão (ms) | Latência Mín. (ms) | Latência Máx. (ms) | Custo Médio/Query (USD) | Taxa de Erro (%) | Precisão Tool Use (%) | Qualidade Média (1-5) | Adequação Domínio (%) | IDC |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Claude Haiku 4.5 | 60 | — | — | — | — | — | — | — | — | — | — |
| Llama 3.1 8B | 60 | — | — | — | — | — | — | — | — | — | — |
| Sabiá-3 | 60 | — | — | — | — | — | — | — | — | — | — |

---

### 4.4 Tabela por Categoria de Pergunta (Modelo para Preenchimento)

| Motor | Categoria | Latência Média (ms) | Precisão Tool Use (%) | Qualidade Média (1-5) |
|---|---|---|---|---|
| Claude Haiku 4.5 | Factual simples | — | — | — |
| Claude Haiku 4.5 | Agregada com filtros | — | — | — |
| Claude Haiku 4.5 | Documental (RAG) | — | — | — |
| Llama 3.1 8B | Factual simples | — | — | — |
| Llama 3.1 8B | Agregada com filtros | — | — | — |
| Llama 3.1 8B | Documental (RAG) | — | — | — |
| Sabiá-3 | Factual simples | — | — | — |
| Sabiá-3 | Agregada com filtros | — | — | — |
| Sabiá-3 | Documental (RAG) | — | — | — |

---

## 5. Referências para a Dissertação (ABNT NBR 6023/2002)

MARITACA AI. **Sabiá-3: modelo de linguagem em português brasileiro**. Campinas: Maritaca AI, 2024. Disponível em: https://maritaca.ai. Acesso em: 21 abr. 2026.

META AI. **Llama 3.1: open foundation and fine-tuned chat models**. Menlo Park: Meta Platforms, 2024. Disponível em: https://ai.meta.com/blog/meta-llama-3-1. Acesso em: 21 abr. 2026.

ANTHROPIC. **Claude Haiku 4.5: technical specification**. San Francisco: Anthropic, 2025. Disponível em: https://docs.anthropic.com. Acesso em: 21 abr. 2026.

BRASIL. Ministério da Ciência, Tecnologia e Inovação. **Plano Brasileiro de Inteligência Artificial (PBIA) 2024-2028**. Brasília: MCTI, 2024. Disponível em: https://www.gov.br/mcti. Acesso em: 21 abr. 2026.

SANTOS, Luciana. Governo federal considera combinar LLMs nacionais em português. In: **WEB SUMMIT RIO**, 2025, Rio de Janeiro. [Declaração]. Reportagem: TELETIME, 28 abr. 2025.

SERPRO. **Serpro LLM Tupi Guarani: modelo de linguagem para o serviço público brasileiro**. Brasília: Serviço Federal de Processamento de Dados, 2025. Disponível em: https://www.serpro.gov.br. Acesso em: 21 abr. 2026.

---

*Documento gerado em 21/04/2026 — AgroIA-RMC v1.0*
