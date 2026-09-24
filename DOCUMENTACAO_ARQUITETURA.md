# AgroIA-RMC — Arquitetura e Desenvolvimento da Plataforma

Documentação técnica para a dissertação de Mestrado em Computação Aplicada
(PPGCA/UEPG).

**Última verificação dos dados:** 22 de setembro de 2026.

---

## 1. Visão geral

O **AgroIA-RMC** é uma plataforma que aproxima a oferta da **agricultura
familiar** da demanda institucional pública de alimentos na Região Metropolitana
de Curitiba (RMC).

O problema que motiva a plataforma é de **assimetria de informação**: as compras
públicas de alimentos são registradas em um portal de licitações de consulta
difícil, cujos dados não são publicados em formato aberto. O agricultor familiar
não tem como saber o que a prefeitura compra, em que volume, a que preço e com
qual periodicidade — informação que orienta decisões de plantio e de
comercialização.

A plataforma responde a isso em três movimentos:

1. **Extrair** os dados do portal público, que não oferece API
2. **Estruturar e classificar** o que é relevante para a agricultura
3. **Disponibilizar** em linguagem natural, por um assistente conversacional

### Recorte dos dados

| Dimensão | Definição |
|---|---|
| Órgão | SMSAN/FAAC — Secretaria Municipal de Segurança Alimentar e Nutricional / Fundo de Abastecimento Alimentar de Curitiba |
| Período | 30/08/2019 a 08/04/2026 |
| Escopo | Exclusivamente agrícola (`relevante_af = true`) |

---

## 2. Base de dados atual

Contagens verificadas diretamente no banco em 22/09/2026:

| Entidade | Registros | Observação |
|---|---|---|
| Licitações (total coletado) | 1.237 | universo SMSAN/FAAC no período |
| **Licitações agrícolas** | **715** | 57,8% — escopo da pesquisa |
| Itens de licitação | 7.882 | 99,8% de cobertura |
| Itens classificados como agrícolas | 742 | nível item |
| Fornecedores | 3.081 | |
| Participações (propostas) | 26.211 | |
| Empenhos | 3.473 | 36% de cobertura (ver §9) |
| Documentos (PDFs) baixados | 180 | 14,6% das licitações |
| Trechos indexados (RAG) | 216 | de 161 documentos |

> **Nota sobre granularidade.** `relevante_af` (licitação) e `relevante_agro`
> (item) são medidas **intencionalmente distintas**: uma licitação é agrícola
> quando seu objeto pertence ao abastecimento alimentar; um item é agrícola
> quando o produto específico o é. Uma licitação agrícola pode conter itens não
> agrícolas (embalagens, transporte). Os dois números não devem ser comparados
> diretamente.

---

## 3. Arquitetura geral

A plataforma se organiza em quatro camadas, com responsabilidades separadas e
hospedagens independentes.

```
┌───────────────────────────────────────────────────────────────┐
│ APRESENTAÇÃO          React + TypeScript + Vite               │
│                       Cloudflare Pages (CDN global)           │
└──────────────────────────────┬────────────────────────────────┘
                               │ HTTPS · X-API-Key
┌──────────────────────────────▼────────────────────────────────┐
│ APLICAÇÃO             FastAPI (Python 3.11)                   │
│                       Render · 30 endpoints                   │
│                       ├─ Agente conversacional (12 tools)     │
│                       ├─ Orquestração da coleta               │
│                       └─ Auditoria de consistência            │
└──────┬─────────────────────────────────────┬──────────────────┘
       │                                     │
┌──────▼──────────────────┐      ┌───────────▼──────────────────┐
│ INTELIGÊNCIA            │      │ PERSISTÊNCIA                 │
│ Claude (Anthropic)      │      │ Supabase (PostgreSQL)        │
│ + pgvector (RAG)        │      │ + pgvector · Storage         │
└─────────────────────────┘      └───────────▲──────────────────┘
                                             │
┌────────────────────────────────────────────┴──────────────────┐
│ COLETA                GitHub Actions (runner self-hosted)     │
│                       Playwright + Chromium                   │
│                       └─ Portal de Licitações de Curitiba     │
└───────────────────────────────────────────────────────────────┘
```

### Por que as camadas são separadas

A separação não é estética: cada camada tem um **requisito de infraestrutura
incompatível** com as demais.

- A **coleta** exige navegador real e IP residencial brasileiro (§5.1)
- A **aplicação** precisa responder rápido e de forma contínua
- A **apresentação** é estática e se beneficia de distribuição em CDN
- A **persistência** precisa de disponibilidade independente das anteriores

---

## 4. Camada de coleta

### 4.1 O desafio técnico

O portal de licitações de Curitiba
(`consultalicitacao.curitiba.pr.gov.br:9090`) é uma aplicação **JSF/RichFaces**
sem API pública. Isso impõe restrições que determinaram toda a estratégia de
coleta:

| Característica do portal | Consequência |
|---|---|
| IDs gerados com dois-pontos (`form:campo`) | Seletores CSS padrão não funcionam; é preciso usar `[id="form:campo"]` |
| Campos de data com validação por evento | `fill()` não dispara `onchange`; exige digitação simulada + Tab |
| Navegação por abas RichFaces | "Lista Licitações" não é link, é `<td>` com comportamento JS |
| Documentos em modais dinâmicos | Requer contexto completo de navegador; requisições HTTP diretas falham |
| Paginação server-side com estado | Não pode ser reproduzida por URL |

A consequência prática é que **a coleta não pode ser feita por requisições
HTTP**. Ela exige automação de navegador (Playwright + Chromium).

### 4.2 A restrição de rede

Durante o desenvolvimento verificou-se que **o portal resolve no DNS público mas
recusa conexões originadas de IPs de datacenter**. Isso foi confirmado por
sondagem: tanto os runners hospedados do GitHub (Azure) quanto o servidor de
aplicação retornaram falha de conexão, enquanto a mesma requisição de uma rede
residencial brasileira foi atendida.

Essa constatação tem uma implicação arquitetural forte: **a coleta não pode ser
executada em nuvem**. Ela exige um nó em rede brasileira aceita pelo portal.

A solução adotada foi um **runner self-hosted** do GitHub Actions, executado em
uma máquina local, configurado para iniciar automaticamente no boot
(`scripts/setup-runner-autostart.ps1`). A plataforma permanece integralmente em
nuvem; apenas o coletor é local.

### 4.3 As três fases da coleta

**Fase 1 — Licitações.** Busca no portal por intervalo de datas e órgão,
percorrendo a paginação. Resultado: 1.237 processos.

**Fase 2 — Itens, fornecedores e empenhos** (`etapa2_itens_v9.py`). Para cada
licitação, abre a página de detalhe e extrai três tabelas: itens licitados,
fornecedores participantes e empenhos. Aplica a classificação agrícola (§6) no
momento da inserção.

**Fase 3 — Documentos** (`etapa3_producao.py`). Baixa os PDFs anexos, que estão
em modais dinâmicos. A implementação usa os gerenciadores de contexto
`expect_page()` e `expect_download()` do Playwright — tentativas anteriores com
a biblioteca `requests` falharam por validação de sessão do portal.

A execução é **idempotente e retomável**: um arquivo de checkpoint
(`coleta_checkpoint.json`) permite continuar de onde parou.

### 4.4 Agendamento e observabilidade

| Workflow | Frequência | Runner |
|---|---|---|
| `coleta.yml` | Segundas, 06:00 BRT | self-hosted |
| `prohort.yml` | Diário, 14:00 BRT | ubuntu-latest |
| `benchmark.yml` | Sob demanda | ubuntu-latest |

O progresso é gravado em tempo real na tabela `coleta_status` do Supabase. O
backend lê essa tabela e a retransmite por **Server-Sent Events**, de modo que o
indicador "Em andamento" funciona em qualquer máquina, não só na que executa a
coleta.

Há **auto-cura de estado**: uma coleta marcada como `running` que deixa de
atualizar seu status por mais que um limite configurável é convertida em erro
persistido e auditado. Isso evita o estado contraditório de um painel indicando
execução enquanto o processo já morreu.

---

## 5. Camada de persistência

Banco PostgreSQL gerenciado pelo **Supabase**, com a extensão **pgvector**.

### 5.1 Tabelas principais

| Tabela | Conteúdo |
|---|---|
| `licitacoes` | Processos licitatórios; `relevante_af` marca o escopo agrícola |
| `itens_licitacao` | Itens; `relevante_agro` e `categoria_v2` guardam a classificação |
| `fornecedores` | Empresas e cooperativas participantes |
| `participacoes` | Propostas por fornecedor e item |
| `empenhos` | Compromissos de despesa |
| `documentos_licitacao` | Metadados e status de download dos PDFs |
| `pdf_chunks` | Trechos de documentos com embeddings de 384 dimensões |
| `conversas` | Histórico do assistente, por sessão |
| `coleta_status` / `coleta_execucoes` | Estado ao vivo e auditoria das coletas |
| `ofertas_produtores` / `produtores` | Oferta declarada pelos agricultores |

### 5.2 Visões

As visões consolidam as regras de escopo, garantindo que todas as telas e o
assistente usem a mesma definição:

- `vw_itens_agro` — itens com `relevante_agro = true`, fonte única das métricas
  de item
- `vw_demanda_agro_ano` — demanda anual por categoria
- `vw_cruzamento_precos_ceasa` — confronto entre preço pago pela prefeitura e
  preço de mercado
- `v_prohort_analise` — série de preços da CEASA

---

## 6. Classificação agrícola

Módulo `enriquecer_classificacao.py`, aplicado na ingestão.

Duas funções operam sobre a descrição textual do item:

- `is_relevante_agro(descricao) → bool` — o item pertence ao escopo agrícola?
- `classificar_item(descricao) → categoria` — a qual grupo pertence?

As categorias agrupadoras (`categoria_v2`) são: `HORTIFRUTI`, `FRUTAS`,
`PROTEINA_ANIMAL`, `LATICINIOS`, `GRAOS_CEREAIS`, `PROCESSADOS_AF`,
`INSUMOS_NAO_AGRO`, `OUTRO` e `NAO_CLASSIFICADO`. Abaixo delas há reconhecimento
de culturas específicas (alface, tomate, abóbora, etc.).

A abordagem é **determinística, baseada em regras léxicas**, não estatística.
Essa escolha tem uma justificativa metodológica: em pesquisa, a classificação
precisa ser **reproduzível e auditável**. Um classificador por regras permite
rastrear exatamente por que cada item recebeu cada rótulo — o que um modelo
estatístico tornaria opaco.

---

## 7. Camada de aplicação

API em **FastAPI** (Python 3.11), com 30 endpoints. Os principais:

| Grupo | Endpoints | Função |
|---|---|---|
| Assistente | `/chat`, `/chat/stream` | Conversa com o agente |
| Preços | `/prohort/status`, `/prohort/chat/stream` | Consulta de mercado |
| Produtor | `/produtor/ofertas/upload`, `/produtor/chat/stream` | Cadastro de oferta |
| Coleta | `/coleta/iniciar`, `/coleta/stream`, `/coleta/status` | Orquestração |
| Auditoria | `/auditoria/consistencia`, `/auditoria/executar` | Verificação dos dados |
| Motores | `/config/motor`, `/benchmark/comparar/stream` | Troca e comparação de LLMs |
| Saúde | `/health` | Monitoramento |

### 7.1 Segurança

- Autenticação por cabeçalho `X-API-Key` nos endpoints sensíveis
- **CORS** com lista explícita de origens (`ALLOWED_ORIGINS`)
- Sanitização de entrada antes das consultas
- Segredos exclusivamente em variáveis de ambiente, nunca versionados

### 7.2 Streaming

Endpoints de conversa usam **Server-Sent Events**, entregando a resposta token a
token. A escolha reduz a latência percebida: o usuário vê a resposta se formar
em vez de aguardar o processamento completo, que pode levar dezenas de segundos
quando o agente encadeia várias consultas.

---

## 8. Camada de inteligência

### 8.1 Agente com ferramentas

O assistente é um agente em laço (*agentic loop*) sobre **Claude Haiku 4.5**. Ele
não recebe os dados prontos: decide quais consultas fazer, executa, avalia os
resultados e pode encadear novas consultas antes de responder.

São **12 ferramentas**, em quatro famílias:

**Compras públicas**
`query_licitacoes` · `query_itens_agro` · `query_fornecedores`

**Documentos**
`buscar_chunks_rag`

**Preços de mercado (CEASA/PROHORT)**
`consultar_preco_produto` · `comparar_preco_historico` ·
`ranking_melhores_precos` · `consultar_precos_lista` · `comparar_ceasas` ·
`cruzar_preco_prefeitura`

**Oferta do produtor**
`query_ofertas_produtores` · `registrar_oferta_produtor`

A ferramenta `cruzar_preco_prefeitura` merece destaque: ela confronta o preço
pago em licitação com o preço de mercado do mesmo produto, permitindo perguntas
como *"a prefeitura pagou acima ou abaixo do mercado?"* — exatamente o tipo de
análise que a assimetria de informação impedia.

### 8.2 Busca semântica (RAG)

Os documentos são indexados em `pdf_chunks`, com embeddings de 384 dimensões
gerados pelo modelo `paraphrase-multilingual-MiniLM-L12-v2`. A busca por
similaridade usa a função `buscar_chunks_similares`, apoiada em **índice HNSW**
do pgvector — o cálculo ocorre no banco, não na aplicação.

**Como os documentos são lidos.** A extração de texto não usa um analisador de
PDF convencional. Cada página é convertida em imagem (150 dpi) e submetida ao
**Claude Vision** com um prompt contextualizado ao domínio de licitações de
alimentos (`indexar_pdfs.py`). A escolha se justifica porque boa parte dos
documentos é digitalizada, e analisadores tradicionais falham nesses casos.

Isso tem duas consequências que precisam ser explicitadas em qualquer uso
analítico do RAG:

1. O texto indexado é **interpretado**, não transcrito literalmente. O prompt
   pede análise, de modo que os trechos contêm sínteses e marcações do modelo,
   não o texto original do edital.
2. A extração é limitada às **10 primeiras páginas** de cada documento.

### 8.3 Comparação de motores

A plataforma permite trocar o motor de linguagem e comparar respostas ao vivo,
com medição de latência, tokens e custo:

| Motor | Modelo |
|---|---|
| Claude (referência) | Haiku 4.5 |
| Gemini | 2.0 Flash |
| Llama (via Groq) | 3.1 8B |
| Maritaca | Sabiá-4 |

Esse recurso serve diretamente à pesquisa: permite avaliar empiricamente se
modelos menores, mais baratos ou treinados em português atendem ao caso de uso
com qualidade comparável.

---

## 9. Camada de apresentação

Aplicação **React 19 + TypeScript**, construída com **Vite** e distribuída pelo
**Cloudflare Pages**.

| Rota | Função |
|---|---|
| `/inicio` | Panorama geral |
| `/assistente` | Conversa em linguagem natural |
| `/demanda` | Demanda institucional por categoria e período |
| `/mercado` | Preços da CEASA |
| `/ofertas` · `/produtor` | Oferta dos agricultores |
| `/documentos` | Documentos das licitações |
| `/alertas` | Sinalizações automáticas |
| `/auditoria` | Verificação de consistência |
| `/benchmark` | Comparação de motores |
| `/coleta` | Atualização dos dados |

---

## 10. Implantação

| Camada | Serviço | Plano |
|---|---|---|
| Frontend | Cloudflare Pages | gratuito |
| Backend | Render | gratuito |
| Banco e Storage | Supabase | gratuito |
| Coleta | GitHub Actions + runner local | gratuito |
| LLM | API Anthropic | por uso |

A configuração é feita inteiramente por variáveis de ambiente, sem segredos no
código. O frontend recebe `VITE_API_URL` e `VITE_API_SECRET_KEY` em tempo de
build; o backend recebe credenciais de banco, chave de LLM e lista de origens
autorizadas em tempo de execução.

### Lições de operação

Duas limitações de infraestrutura gratuita afetaram o projeto e merecem registro
por serem replicáveis em trabalhos semelhantes:

1. **Cotas mudam sem aviso.** Em abril de 2026 a franquia de banda do provedor
   de aplicação foi reduzida de 100 GB para 5 GB mensais, com migração forçada
   dos planos antigos em agosto. Serviços que operavam dentro do limite passaram
   a ser suspensos sem alteração no próprio uso.
2. **Cotas são compartilhadas por conta, não por projeto.** Um segundo serviço
   na mesma conta consumiu a franquia e derrubou a plataforma junto. Projetos
   acadêmicos que dependem de camada gratuita devem isolar-se de outros
   serviços.

---

## 11. Limitações conhecidas

Registradas com transparência por afetarem a interpretação dos resultados.

**Cobertura de empenhos — 36%.** Dos processos concluídos, 664 não possuem
empenho registrado no portal. Não é falha de coleta: é característica do próprio
registro público, esperada em dispensas de licitação. O teto de 36% é o máximo
extraível da fonte.

**Cobertura documental — 14,6%.** Apenas 180 das 1.237 licitações tiveram
documentos baixados. Os modais são dinâmicos e nem todos os processos
disponibilizam anexos.

**Alcance do RAG — 216 trechos.** Cobrem 161 documentos de 153 licitações, ou
12,4% da base. A busca semântica é, portanto, **complementar** às consultas
estruturadas, não sua substituta. As análises quantitativas da dissertação devem
se apoiar nas tabelas, não no RAG.

**Natureza do texto indexado.** Conforme §8.2, os trechos são interpretações
geradas por modelo de visão, limitadas a 10 páginas por documento. Citações
literais de editais não devem ser extraídas do RAG sem conferência no PDF
original.

**Dependência de nó local.** A coleta exige uma máquina em rede brasileira
ligada. Se ela estiver desligada no horário agendado, a coleta falha — e o
sistema registra o erro em vez de mascará-lo.

---

## 12. Decisões de arquitetura

Síntese das escolhas estruturais e suas razões.

| Decisão | Alternativa descartada | Razão |
|---|---|---|
| Playwright para coleta | Requisições HTTP diretas | O portal valida sessão e usa modais dinâmicos |
| Runner self-hosted | Runner em nuvem | O portal recusa IPs de datacenter |
| Classificação por regras | Modelo estatístico | Reprodutibilidade e auditabilidade |
| Similaridade no banco (pgvector) | Cálculo na aplicação | Usa índice HNSW; não transfere vetores pela rede |
| Claude Vision para ler PDFs | Analisador de PDF | Documentos majoritariamente digitalizados |
| Agente com ferramentas | Consultas fixas | O agente encadeia consultas conforme a pergunta |
| SSE para respostas | Requisição-resposta | Reduz a latência percebida |
| Visões como fonte única | Regras repetidas no código | Impede divergência entre telas e assistente |

---

## 13. Reprodutibilidade

O código está versionado em https://github.com/HvcamposHAi/agroia-rmc.

**Para reexecutar a coleta:**

```bash
python etapa2_itens_v9.py      # itens, fornecedores, empenhos
python etapa3_producao.py --resume   # documentos, retomando o checkpoint
```

**Para verificar o estado dos dados:**

```bash
python dados_atualizados.py --resumo
```

Esse script consulta o banco diretamente, sem cache, e retorna JSON com
timestamp UTC — de modo que qualquer número citado na dissertação pode ser
reconferido na data da defesa.

**Para subir o ambiente completo localmente:** `INICIAR_DESENVOLVIMENTO.bat`
(backend em `localhost:8000`, frontend em `localhost:5173`).
