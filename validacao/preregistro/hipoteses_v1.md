# Pré-registro da validação do AgroIA-RMC, versão 1

Data do registro: 27/09/2026. Este arquivo é gravado com hash SHA-256 (`hipoteses_v1.sha256`)
antes da primeira execução completa com dados reais. Toda alteração posterior gera nova
versão (`hipoteses_v2.md`) e é reportada como desvio no relatório de metodologia.

## 1. Tese

A plataforma AgroIA-RMC e a organização de dados adotada facilitam o acesso às informações
sobre licitações de alimentos do Fundo de Abastecimento Alimentar de Curitiba (FAAC), em
comparação com o acesso pelas fontes públicas originais.

"Facilitar o acesso" é operacionalizado pelas dimensões de usabilidade da ISO 9241-11:2018
mensuráveis sem participantes humanos: eficácia (sucesso na tarefa), eficiência (ações,
páginas, documentos, tempo e tempo humano estimado pelo KLM) e cobertura funcional (tipos de
tarefa resolvidos). A satisfação não é medida nesta etapa; ela é objeto da avaliação com
usuários (TAM), que exige aprovação do CEP.

## 2. Parte A1: fidelidade (pré-condição)

Medidas, sem hipótese inferencial:

- Completude do censo = |P ∩ B| / |P| e precisão de existência = |P ∩ B| / |B verificável|,
  por ano e global. Registros da base vindos do portal JSF desativado e ausentes da fonte atual
  recebem `NAO_VERIFICAVEL_FONTE_DESATIVADA` e ficam fora do denominador da precisão.
- Taxa de correspondência por campo e global, com intervalo de Wilson de 95%, sobre amostra
  estratificada por ano e modalidade de P ∩ B (escopo `relevante_af = true`), tamanho pela
  fórmula de Cochran com correção de população finita (confiança 95%, margem 5%, p = 0,5),
  semente 20260927.
- Duas leituras independentes da fonte (Playwright e Claude in Chrome). Campo com leituras
  discordantes: `DIVERGENCIA_EXTRACAO`, fora da taxa principal, contado à parte; concordância
  entre extratores por proporção e κ de Cohen (campos categóricos).
- Documentos: disponibilidade, integridade (tamanho, páginas, Jaccard de 5-gramas; SHA-256
  quando houver par), cobertura e cobertura do RAG.
- Agregados por ano (processos, itens, valor empenhado, 10 maiores credores).

Só entram na A2 tarefas cujos parâmetros vêm de processos com todos os campos necessários
confirmados na A1, e anos com completude de censo ≥ 0,95.

## 3. Parte A2: hipóteses

- **H1 (eficácia):** a taxa de sucesso na condição AGROIA é maior que na condição PORTAL.
- **H2 (eficiência):** o número de ações por tarefa bem-sucedida é menor na condição AGROIA.
- **H3 (eficiência):** o tempo humano estimado (KLM) é menor na condição AGROIA.
- **H4 (cobertura):** a proporção de tipos de tarefa resolvidos ao menos uma vez é maior na
  condição AGROIA.
- **H5 (abstenção):** na tarefa T12, a condição AGROIA declara corretamente a inexistência da
  informação com frequência igual ou maior que a condição PORTAL.

### 3.1 Desenho

Unidade experimental: tarefa instanciada (modelo T01 a T12 com parâmetros sorteados).
Condições pareadas dentro da tarefa: PORTAL (Portal da Transparência de Curitiba e cotações
da CEASA-PR) e AGROIA (`agroia-rmc.pages.dev`). Mesmo agente (Claude Code com Claude in Chrome,
modelo fixado em `config.yaml`), mesmo orçamento de turnos, mesmo prompt-base e formato de
resposta. Padrão: 12 modelos × 2 instâncias × 2 condições × 3 repetições. Ordem aleatorizada
com semente, condições intercaladas. Aquecimento do backend antes de cada execução AGROIA,
com a latência registrada à parte.

### 3.2 Métricas

Sucesso (regra de pontuação do modelo), pontuação contínua quando aplicável, desfecho
(`CORRETO`, `INCORRETO`, `NAO_ENCONTROU_DECLARADO`, `BLOQUEADO`, `TIMEOUT`, `ERRO_INFRA`),
nº de ações de navegador, ações por tipo, páginas distintas, documentos abertos, tempo de
relógio, tokens, turnos, tempo humano KLM (limite inferior; K = 0,28 s, P = 1,1 s, B = 0,1 s,
H = 0,4 s, M = 1,35 s) e uso do Chat na condição AGROIA.

### 3.3 Testes

- Agregação por tarefa e condição: sucesso = maioria das 3 repetições (principal); proporção
  de sucesso nas repetições (sensibilidade).
- H1: McNemar exato sobre os pares; tabela 2×2, p-valor e razão de chances com IC 95%.
- H2 e H3: Wilcoxon pareado sobre a mediana das repetições por tarefa; principal com tarefas
  bem-sucedidas nas duas condições; sensibilidade com todas as tarefas, atribuindo às falhas o
  orçamento máximo (H2: `max_turns`; H3: maior KLM observado). Efeito: r = Z/√N e δ de Cliff.
- H4: descritiva por tipo, sem teste inferencial.
- H5: proporções com IC de Wilson; Fisher exato se houver variação.
- Correção de Holm sobre H1, H2, H3 e H5. α = 0,05.
- Decisão: "sustentada" quando p ajustado < α e o efeito tem o sentido previsto; "não
  sustentada" quando p ajustado < α e o efeito tem sentido contrário; "inconclusiva" nos
  demais casos. H4 e H5 (descritivas) são decididas pela comparação direta das proporções.

### 3.4 Regras de exclusão

- `ERRO_INFRA` e `ERRO_INFRA_CHROME`: a execução é repetida até 2 vezes; persistindo, a
  tarefa sai da análise principal nas duas condições (pareamento) e é listada.
- `BLOQUEADO` e `TIMEOUT` (inclui orçamento de turnos esgotado): insucesso na análise
  principal (intenção de tratar); excluídos na análise de sensibilidade.
- Nenhuma outra exclusão após a coleta.

## 4. Parte B: benchmark de motores (análise separada)

Pergunta: qual motor LLM sustenta melhor o agente da plataforma, com tudo o mais constante.
Motores: Claude Haiku 4.5, Llama 3.1 8B (Groq), Sabiá-4 (Maritaca), Gemini 2.0 Flash.

- Caminho de produção `/chat/stream`, motor por requisição, sem cache de respostas, com
  rastreio das ferramentas. Mesmo prompt de sistema e ferramentas para todos.
- Parâmetros de geração: os do caminho de produção (a rota `/chat/stream` não expõe
  temperatura; o valor efetivo de cada provedor é registrado no relatório). Isto difere do
  plano original (temperatura 0) e é reportado como desvio.
- Base fixa durante a janela: assinatura da base viva (contagens, maior id, última cotação)
  comparada antes e depois; mudança é reportada.
- Dataset de 30 perguntas (A: 24; B: 6 de abstenção). Gabaritos do conjunto A recalculados por
  SQL sobre o snapshot de cada execução; perguntas documentais ou abertas sem gabarito factual
  têm como acerto principal o uso de ferramenta pertinente (AF@3 > 0).
- k = 5 repetições por pergunta e motor; ordem aleatorizada, motores intercalados.
- Métricas: acurácia factual, AF@k (`benchmark/metricas.py`), fidelidade às ferramentas,
  uso correto de ferramentas (JSON Schema), abstenção e falsa abstenção, consistência
  (mesmo desfecho e κ de Fleiss), latência p50/p90/p95 (total e até o 1º token), custo,
  taxonomia de erros.
- Testes: Q de Cochran sobre as perguntas do conjunto A (maioria das repetições); se
  significativo, McNemar exato par a par com Holm. Latência e custo: Friedman; se
  significativo, Wilcoxon par a par com Holm; δ de Cliff. Abstenção: Wilson.
- Duas análises: principal (falha de infraestrutura = erro) e sensibilidade (exclui falhas de
  infraestrutura).
- Poder: menor efeito detectável reportado; resultado não significativo é inconclusivo, não
  equivalência.
- Auditoria humana de 20% das respostas (estratificada por motor e desfecho), com κ de Cohen
  entre pontuação automática e humana. Não há LLM como juiz na análise principal.

## 5. Ameaças previstas

Agente como proxy de usuário; um único órgão e município; fonte JSF desativada; variação do
portal durante a coleta; partida a frio do Render; estocasticidade dos modelos; poder
estatístico limitado (n de tarefas e de perguntas).
