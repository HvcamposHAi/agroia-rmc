# 📋 Manual de Teste — AgroIA-RMC (Front-end)

**Data:** 26 de abril de 2026  
**Versão:** 1.0  
**Objetivo:** Validar todas as funcionalidades visíveis ao usuário via navegador  
**Público-alvo:** Gestores SMSAN, testadores, stakeholders (não requer conhecimento técnico)

---

## 🚀 Como Começar

### Pré-requisitos

Antes de iniciar os testes, certifique-se de que:

1. **Frontend rodando:**
   ```bash
   cd agroia-frontend
   npm run dev
   ```
   Acesse: http://localhost:5173

2. **Backend rodando:**
   ```bash
   cd api
   uvicorn main:app --reload
   ```
   Disponível em: http://localhost:8000

3. **Banco de dados conectado:**
   - Arquivo `.env` na raiz contém `SUPABASE_URL`, `SUPABASE_KEY`, `ANTHROPIC_API_KEY`
   - Execute `python dados_atualizados.py --resumo` para confirmar que dados estão presentes

4. **Navegador recomendado:**
   - Chrome/Edge (versão recente)
   - Firefox
   - Safari (Mac)

5. **Limpeza inicial (opcional):**
   Para começar do zero, abra DevTools (F12) e execute no console:
   ```javascript
   localStorage.clear()
   ```

---

## ⚡ Teste Rápido de Sanidade (5 minutos)

Execute este teste antes de qualquer coisa para confirmar que a plataforma está operacional:

| # | Ação | Resultado Esperado | ✓ |
|---|---|---|---|
| 1 | Abra http://localhost:5173 | Página carrega; sidebar com logo visível; badge "Sistema Ativo" (verde) no topo |  |
| 2 | No chat, clique em "Qual a demanda de alface?" | Texto preenche input; spinner aparece; resposta chega em < 15s |  |
| 3 | Clique em "Dashboard" (sidebar) | Página Dashboard carrega; 6 cards com números aparecem |  |
| 4 | Selecione "2023" no dropdown "Ano" | Gráficos e números atualizam para dados de 2023 |  |
| 5 | Clique em "Documentos" (sidebar) | Página carrega; lista de documentos com PDFs aparece |  |
| 6 | Clique em um documento → botão "Visualizar" | PDF abre em modal; pode fazer download |  |

**Se todos os passos acima funcionarem: ✅ Plataforma está pronta para testes detalhados**

---

## 📖 Testes Detalhados por Página

Cada seção abaixo corresponde a uma página da plataforma. Use a tabela para rastrear o status de cada teste.

### Legenda de Status:
- ⬜ **Não testado**
- 🟢 **Passou** (funciona conforme esperado)
- 🟡 **Atenção** (comportamento parcialmente correto)
- 🔴 **Falha** (não funciona como esperado)
- ⛔ **Bloqueado** (não consegue testar por outro motivo)

---

## 1. Layout Global (Sidebar + Topbar)

Estes testes verificam a navegação e estrutura de todas as páginas.

| ID | Caso de Teste | Passos | Resultado Esperado | Status | Observações |
|---|---|---|---|---|---|
| **TC-01** | Sidebar presente em todas as páginas | 1. Abra http://localhost:5173<br>2. Clique em cada link do menu (Assistente, Dashboard, Consultas, Alertas, Auditoria, Documentos)<br>3. Verifique se sidebar continua visível | Sidebar com logo e 6 links aparece em TODAS as páginas | ⬜ |  |
| **TC-02** | Link ativo destaca-se | 1. Clique em "Dashboard"<br>2. Verifique se o link está destacado (cor diferente)<br>3. Clique em "Consultas"<br>4. Verifique se o destaque mudou | O link da página atual sempre fica destacado; demais não | ⬜ |  |
| **TC-03** | Card "Gestor SMSAN" visível | 1. Abra qualquer página<br>2. Olhe a sidebar (parte inferior) | Card com "Gestor SMSAN / Curitiba – PR" aparece | ⬜ |  |
| **TC-04** | Badge "Sistema Ativo" na topbar | 1. Abra qualquer página<br>2. Olhe a barra no topo (topbar) | Badge verde escrito "Sistema Ativo" aparece no topo direito | ⬜ |  |
| **TC-05** | Título da página muda | 1. Abra `/`<br>2. Verifique o título no topbar<br>3. Vá para `/dashboard`<br>4. Verifique que o título mudou | Títulos por página: `/` = "Assistente Agricola"; `/dashboard` = "Painel de Dados"; `/consultas` = "Consultas de Licitacoes"; `/alertas` = "Alertas Inteligentes"; `/auditoria` = "Auditoria de Dados"; `/documentos` = "Documentos das Licitacoes" | ⬜ |  |
| **TC-06** | Rota inválida | 1. Abra http://localhost:5173/nao-existe | Página mostra erro 404 OU redireciona para `/` sem travar | ⬜ |  |

---

## 2. Chat (Assistente Agrícola)

O chat é o coração da plataforma. Aqui o usuário faz perguntas sobre licitações.

| ID | Caso de Teste | Passos | Resultado Esperado | Status | Observações |
|---|---|---|---|---|---|
| **TC-10** | Tela de boas-vindas | 1. Limpe localStorage (F12 → Console → `localStorage.clear()`)<br>2. Abra http://localhost:5173 | 6 chips de sugestão aparecem (ex: "Qual a demanda de alface?", "Top culturas compradas pela prefeitura")<br>Campo de texto vazio | ⬜ |  |
| **TC-11** | Envio via chip de sugestão | 1. Clique em "Qual a demanda de alface?"<br>2. Aguarde resposta | Texto preenche input → spinner + status ("Consultando banco de dados...") → resposta em markdown chega em < 15s | ⬜ |  |
| **TC-12** | Envio via Enter | 1. Digite "Quais as principais culturas compradas em 2023?"<br>2. Pressione Enter | Mensagem enviada; resposta chega com dados sobre culturas | ⬜ |  |
| **TC-13** | Shift+Enter quebra linha | 1. Digite "Teste"<br>2. Pressione Shift+Enter<br>3. Digite "segunda linha" | Nova linha aparece NO textarea; mensagem **NÃO** foi enviada | ⬜ |  |
| **TC-14** | Botão enviar desabilitado vazio | 1. Deixe textarea vazio<br>2. Tente clicar no botão enviar (ou ícone de paper plane) | Botão não responde (ou fica cinza/desabilitado) | ⬜ |  |
| **TC-15** | Spinner durante resposta | 1. Envie qualquer pergunta<br>2. Observe enquanto aguarda resposta | Spinner com rotação aparece com texto de status (ex: "Analisando sua pergunta...", "Consultando o banco de dados...") | ⬜ |  |
| **TC-16** | Resposta com tabela formatada | 1. Envie "Quais os top 5 culturas por valor total?"<br>2. Aguarde resposta | Resposta inclui tabela HTML formatada (NOT texto bruto com pipes `\|`) | ⬜ |  |
| **TC-17** | Cache de pergunta repetida | 1. Envie "Demanda de tomate em 2022"<br>2. Aguarde a resposta<br>3. Envie EXATAMENTE a mesma pergunta novamente | Segunda resposta aparece **instantaneamente** (sem spinner) e é idêntica à primeira | ⬜ | Isso ocorre se a pergunta for normalizada de forma idêntica |
| **TC-18** | Histórico como contexto | 1. Envie "Fale sobre demanda de alface"<br>2. Aguarde<br>3. Envie "E qual é a sazonalidade?"<br>4. Leia a resposta | Resposta sobre sazonalidade referencia "alface" do turno anterior; não é resposta genérica sobre sazonalidade | ⬜ | O agente recebe histórico como contexto |
| **TC-19** | Persistência no localStorage | 1. Envie 3+ mensagens<br>2. Feche a aba ou navegue para outra página<br>3. Volte a http://localhost:5173 | Histórico de conversa é restaurado (mensagens anteriores aparecem) | ⬜ |  |
| **TC-20** | Erro de API | 1. Pare o backend (Ctrl+C em `uvicorn`)<br>2. Envie uma pergunta no chat<br>3. Aguarde a tentativa de resposta | Mensagem de erro clara ao usuário (não spinner infinito); UI não trava | ⬜ |  |

---

## 3. Dashboard (Painel de Dados)

O Dashboard exibe gráficos e métricas resumidas de licitações agrícolas.

| ID | Caso de Teste | Passos | Resultado Esperado | Status | Observações |
|---|---|---|---|---|---|
| **TC-30** | Carregamento dos KPIs | 1. Clique em "Dashboard" (sidebar)<br>2. Aguarde página carregar | 6 cards de métricas aparecem com valores numéricos (não zero/NaN):<br>- Valor Total<br>- Total Itens<br>- Culturas (contagem)<br>- Ticket Médio<br>- Preço Médio/kg<br>- Canais Ativos | ⬜ |  |
| **TC-31** | Filtro por Ano | 1. Selecione "2023" no dropdown "Ano"<br>2. Aguarde gráficos atualizarem | KPIs e todos os gráficos refletem apenas 2023; gráfico de evolução muda para mostrar meses (não anos) | ⬜ |  |
| **TC-32** | Filtro por Canal | 1. Selecione "PNAE" no dropdown "Canal"<br>2. Aguarde atualização | KPIs filtrados para PNAE; pie chart de "Distribuição por Canal" mostra apenas PNAE | ⬜ |  |
| **TC-33** | Filtro por Categoria | 1. Selecione "FRUTAS" no dropdown "Categoria"<br>2. Aguarde atualização | KPIs mostram apenas itens da categoria FRUTAS | ⬜ |  |
| **TC-34** | Filtro por Cultura | 1. Selecione uma cultura (ex: "ALFACE") no dropdown "Cultura"<br>2. Aguarde atualização | Dados filtrados para alface apenas | ⬜ |  |
| **TC-35** | Limpar filtros | 1. Aplique um ou mais filtros (ex: Ano=2023, Canal=PNAE)<br>2. Clique em "Limpar"<br>3. Observe os dropdowns e gráficos | Todos os dropdowns voltam para "Todos"; gráficos mostram dados globais novamente | ⬜ |  |
| **TC-36** | Seletor Top 5/10/20 | 1. No gráfico "Top Culturas", clique em "5"<br>2. Depois em "10"<br>3. Depois em "20" | Gráfico de barras exibe 5, 10 ou 20 culturas conforme selecionado | ⬜ |  |
| **TC-37** | Tooltips nos gráficos | 1. Passe mouse (hover) sobre uma barra no gráfico "Top Culturas"<br>2. Passe mouse sobre uma fatia do pie chart | Tooltip aparece com valor formatado (ex: "R$ 123.456,78" ou "1.234 kg") | ⬜ |  |
| **TC-38** | Gráfico evolução anual vs mensal | 1. Sem filtro de ano: verifique gráfico de evolução (deve mostrar ANOS)<br>2. Selecione um ano (ex: 2023)<br>3. Gráfico deve mudar para exibir MESES | Comportamento correto: anos quando sem ano selecionado; meses quando ano selecionado | ⬜ |  |
| **TC-39** | Dados 2025-2026 aparecem | 1. Abra Dashboard<br>2. No dropdown "Ano", verifique se 2025 e 2026 aparecem<br>3. Selecione 2025 e verifique dados | Anos 2025 e 2026 aparecem nas opções; dados aparecem quando selecionados | ⬜ | Bug anterior: PostgREST truncava dados de 2025+ |

---

## 4. Consultas (Busca de Itens de Licitação)

Página para buscar e filtrar itens (alimentos) das licitações.

| ID | Caso de Teste | Passos | Resultado Esperado | Status | Observações |
|---|---|---|---|---|---|
| **TC-40** | Carregamento inicial | 1. Clique em "Consultas" (sidebar)<br>2. Aguarde página | Lista de itens carrega; contador no topo mostra total (≤ 1000) | ⬜ |  |
| **TC-41** | Busca por descrição | 1. Digite "alface" no campo "Buscar"<br>2. Observe lista atualizar | Lista filtra em TEMPO REAL; apenas itens com "alface" na descrição aparecem | ⬜ |  |
| **TC-42** | Busca com diacríticos | 1. Digite "feijão" (com til)<br>2. Observe resultados | Retorna itens com "feijão" E "feijao" (busca normalizada; acentos são ignorados) | ⬜ |  |
| **TC-43** | Busca por número de processo | 1. Encontre um número de processo conhecido<br>2. Digite na busca<br>3. Observe | Item correspondente aparece | ⬜ |  |
| **TC-44** | Toggle de filtros avançados | 1. Clique no botão "Filtros Avançados" (ou ícone de filtro)<br>2. Clique novamente | Painel de filtros aparece e desaparece suavemente | ⬜ |  |
| **TC-45** | Filtros combinados | 1. Abra filtros avançados<br>2. Selecione Cultura="TOMATE", Canal="PNAE", Ano="2022"<br>3. Observe lista | Apenas itens que satisfazem TODOS os 3 critérios aparecem | ⬜ |  |
| **TC-46** | Filtro por valor (Min/Max) | 1. Abra filtros avançados<br>2. Digite Min=1000, Max=5000<br>3. Observe | Apenas itens com valor total entre R$1.000 e R$5.000 listados | ⬜ |  |
| **TC-47** | Limpar filtros avançados | 1. Aplique qualquer filtro<br>2. Clique em "Limpar"<br>3. Verifique dropdowns, inputs e busca | Todos os filtros voltam ao estado inicial; busca textual também limpa | ⬜ |  |
| **TC-48** | Ordenação por Data | 1. Clique no botão "Data" uma vez<br>2. Itens reordenam<br>3. Clique em "Data" novamente | Primeiro clique: ascendente (antigas primeiro); segundo clique: descendente (recentes primeiro) | ⬜ |  |
| **TC-49** | Ordenação por Valor | 1. Clique em "Valor" | Itens reordenados por valor total (menor → maior ou vice-versa) | ⬜ |  |
| **TC-50** | Paginação avançar/voltar | 1. Se houver página 2, clique "Próximo"<br>2. Verifique página 2 com itens diferentes<br>3. Clique "Anterior" | Página 2 exibe itens diferentes; "Anterior" volta corretamente; página atual fica destacada | ⬜ |  |
| **TC-51** | Paginação — página específica | 1. Clique no número de página 3 (se existir) | Salta diretamente para página 3 | ⬜ |  |
| **TC-52** | Estado vazio | 1. Busque por texto inexistente (ex: "xyzabc123999")<br>2. Observe | Ilustração de "nenhum resultado" exibida com mensagem clara (não lista vazia branca) | ⬜ |  |
| **TC-53** | Card de item — conteúdo | 1. Abra página com itens<br>2. Verifique um card | Presentes e corretos:<br>- Badge de cultura (ex: ALFACE)<br>- Badge de canal (PNAE, ARMAZEM_FAMILIA, etc)<br>- Data do processo<br>- Descrição do item<br>- Número do processo<br>- Quantidade (kg)<br>- Preço/kg calculado<br>- Valor total (R$ com separadores) | ⬜ |  |

---

## 5. Alertas (Análise de Risco com IA)

Página que usa IA para gerar alertas sobre potenciais anomalias nos dados.

| ID | Caso de Teste | Passos | Resultado Esperado | Status | Observações |
|---|---|---|---|---|---|
| **TC-60** | Tela inicial | 1. Clique em "Alertas" (sidebar)<br>2. Se for primeira análise, observe | Painel informativo explica 3 tipos de alerta; botão "Analisar Dados" presente | ⬜ |  |
| **TC-61** | Trigger de análise | 1. Clique em "Analisar Dados"<br>2. Aguarde | Spinner "Analisando dados históricos..." aparece; ao concluir (< 30s), alertas listados | ⬜ |  |
| **TC-62** | Cards de contagem por tipo | 1. Após análise, observe cards no topo | 3 cards: ALTA_PRECO, DESABASTECIMENTO, SUPERFATURAMENTO — cada com contagem numérica | ⬜ |  |
| **TC-63** | Filtro por tipo | 1. Clique no card "ALTA_PRECO"<br>2. Observe lista e card | Lista filtra para apenas aquele tipo; card fica destacado | ⬜ |  |
| **TC-64** | Filtro por severidade | 1. Clique em "Alta" (severidade)<br>2. Depois em "Média"<br>3. Depois em "Baixa" | Lista filtra corretamente; badge de severidade colorida em cada item | ⬜ |  |
| **TC-65** | Filtro combinado | 1. Selecione Tipo=SUPERFATURAMENTO<br>2. Selecione Severidade=Alta | Apenas alertas com ambos os critérios | ⬜ |  |
| **TC-66** | Card de alerta — conteúdo | 1. Abra resultado de análise<br>2. Verifique um card | Presentes:<br>- Ícone por tipo (preço, abastecimento, etc)<br>- Título do alerta<br>- Nome da cultura<br>- Tipo (badge)<br>- Severidade (badge colorido)<br>- Descrição<br>- Caixa com recomendação IA | ⬜ |  |
| **TC-67** | Reanalisar | 1. Após análise, clique "Reanalisar"<br>2. Aguarde | Nova análise dispara; spinner aparece; resultado pode diferir | ⬜ |  |
| **TC-68** | Erro de API | 1. Pare o backend<br>2. Clique "Analisar"<br>3. Aguarde | Mensagem de erro clara; botão volta para "Analisar"; UI não trava | ⬜ |  |

---

## 6. Auditoria (Validação Interna de Dados)

Página que executa auditoria no banco para detectar inconsistências.

| ID | Caso de Teste | Passos | Resultado Esperado | Status | Observações |
|---|---|---|---|---|---|
| **TC-70** | Tela inicial | 1. Clique em "Auditoria" (sidebar) | Botão "Executar Auditoria" visível; painel de resultados vazio | ⬜ |  |
| **TC-71** | Execução da auditoria | 1. Clique em "Executar Auditoria"<br>2. Aguarde | Spinner aparece; ao concluir, aparecem 4 cards de métricas + painel de resumo + lista de alertas | ⬜ |  |
| **TC-72** | Cards de métricas | 1. Após auditoria, observe 4 cards | Presentes com valores:<br>- Total Licitações<br>- Cobertura (%)<br>- Alertas Críticos<br>- Empenhos sem docs | ⬜ |  |
| **TC-73** | Painel de resumo | 1. Leia o texto do resumo | Texto gerado pela IA menciona taxa de cobertura e/ou alertas críticos (dados reais) | ⬜ |  |
| **TC-74** | Filtro por tipo de alerta | 1. Clique em "Erro BD", "Inconsistência Portal", "Qualidade"<br>2. Observe contagem | Lista filtra corretamente; contagem ao lado do botão bate com itens visíveis | ⬜ |  |
| **TC-75** | Alerta individual | 1. Verifique um item de alerta | Presentes:<br>- Ícone por tipo<br>- Mensagem<br>- Número de processo<br>- Badge de severidade (colorido) | ⬜ |  |
| **TC-76** | Estado vazio após filtro | 1. Aplique filtro que resulte em zero alertas<br>2. Observe | Mensagem "Nenhum alerta com os filtros selecionados" aparece | ⬜ |  |
| **TC-77** | Chat contextual | 1. Após auditoria, observe se mini-chat aparece | Chat contextual com campo de input visível (pode fazer perguntas sobre auditoria) | ⬜ |  |
| **TC-78** | Chat — envio de pergunta | 1. Digite "Quais processos têm mais inconsistências?"<br>2. Pressione Enter ou clique enviar | Resposta aparece relacionada ao contexto da auditoria | ⬜ |  |
| **TC-79** | Re-executar auditoria | 1. Clique em "Re-executar"<br>2. Aguarde | Nova execução dispara; spinner aparece; resultados atualizam | ⬜ |  |

---

## 7. Documentos (Visualização de PDFs)

Página para visualizar documentos (PDF) das licitações.

| ID | Caso de Teste | Passos | Resultado Esperado | Status | Observações |
|---|---|---|---|---|---|
| **TC-80** | Carregamento inicial | 1. Clique em "Documentos" (sidebar)<br>2. Aguarde página | Lista de documentos carrega; contador mostra total (≤ 500) | ⬜ |  |
| **TC-81** | Busca por nome | 1. Digite parte do nome de um documento conhecido | Lista filtra em tempo real | ⬜ |  |
| **TC-82** | Busca por descrição do objeto | 1. Digite "alface" | Documentos de processos com "alface" no objeto aparecem | ⬜ |  |
| **TC-83** | Busca por processo | 1. Digite número de processo completo | Documentos daquele processo aparecem | ⬜ |  |
| **TC-84** | Toggle filtros avançados | 1. Clique em "Filtros Avançados" (ou ícone)<br>2. Clique novamente | Painel expande/colapsa | ⬜ |  |
| **TC-85** | Filtro por Ano | 1. Abra filtros avançados<br>2. Selecione Ano="2023" | Apenas documentos de 2023 listados | ⬜ |  |
| **TC-86** | Filtro por Mês | 1. Abra filtros avançados<br>2. Selecione Mês="Março" | Apenas documentos de março (qualquer ano ou combinado com filtro de ano) | ⬜ |  |
| **TC-87** | Filtro por Modalidade | 1. Selecione uma modalidade (ex: "Pregão") | Lista filtra corretamente | ⬜ |  |
| **TC-88** | Filtro por Situação | 1. Selecione "Vencedor" | Documentos com situação "vencedor" destacados em verde | ⬜ |  |
| **TC-89** | Card de documento | 1. Observe um card na lista | Presentes:<br>- Ícone de arquivo<br>- Nome do documento<br>- Número de processo<br>- Data<br>- Modalidade<br>- Situação (color-coded)<br>- Descrição (truncada a ~130 caracteres)<br>- Tamanho do arquivo<br>- Botão "Visualizar" | ⬜ |  |
| **TC-90** | Abrir PDF em modal | 1. Clique em um card de documento<br>2. Aguarde modal abrir | Modal tela cheia abre; iframe do Google Drive carrega PDF; metadata no header visível | ⬜ |  |
| **TC-91** | Download de PDF | 1. No modal aberto, clique em "Download"<br>2. Aguarde | Download inicia do Google Drive; arquivo é um PDF válido | ⬜ |  |
| **TC-92** | Fechar modal | 1. Clique no botão "Fechar" ou tente pressionar Escape | Modal fecha; volta à lista de documentos | ⬜ |  |
| **TC-93** | Paginação | 1. Se houver página 2, clique "Próximo"<br>2. Verifique | Página 2 exibe 15 itens diferentes; controles de paginação funcionam | ⬜ |  |

---

## 8. Testes de Erro e Edge Cases

Testes para situações anormais ou extremas.

| ID | Caso de Teste | Passos | Resultado Esperado | Status | Observações |
|---|---|---|---|---|---|
| **TC-100** | Sem conexão com Supabase | 1. Simule falha de rede: DevTools (F12) → Network → marque "Offline"<br>2. Navigue para `/dashboard`<br>3. Aguarde | Mensagem de erro clara OU spinner sem ficar preso indefinidamente | ⬜ |  |
| **TC-101** | API Key inválida | 1. Abra DevTools<br>2. Modifique `VITE_API_SECRET_KEY` no localStorage para valor errado<br>3. Envie mensagem no chat | Erro 401/403 tratado com mensagem clara ao usuário (não console error) | ⬜ |  |
| **TC-102** | Pergunta fora do escopo | 1. No chat, envie "Quais são os melhores restaurantes de Curitiba?"<br>2. Aguarde resposta | Resposta gentilmente recusa ou redireciona para escopo agrícola (SMSAN/FAAC) | ⬜ |  |
| **TC-103** | Pergunta sobre licitações não-agrícolas | 1. Pergunte sobre licitação específica fora do escopo<br>2. Aguarde resposta | Agente responde que está fora do escopo OU não encontra dados (filtro `relevante_af = true` aplicado) | ⬜ |  |

---

## 9. Performance e Responsividade

Testes para garantir boa experiência em diferentes condições.

| ID | Caso de Teste | Passos | Resultado Esperado | Status | Observações |
|---|---|---|---|---|---|
| **TC-110** | Tempo de resposta do chat | 1. Envie pergunta simples (ex: "Demanda de tomate")<br>2. Meça tempo até primeiro token de resposta aparecer | Primeiro token de resposta em < 10 segundos para perguntas simples | ⬜ | Use DevTools → Network → XHR para ver tempo |
| **TC-111** | Tempo de carregamento do Dashboard | 1. Abra Dashboard (limpe cache se necessário)<br>2. Meça até KPIs + gráficos renderizarem | KPIs e gráficos totalmente renderizados em < 5 segundos | ⬜ |  |
| **TC-112** | Responsividade do layout | 1. Redimensione janela para 1280×768 (tablet)<br>2. Verifique sidebar e conteúdo<br>3. Redimensione para 1920×1080 (desktop)<br>4. Verifique novamente | Sidebar não quebra; gráficos se ajustam; sem overflow horizontal em nenhuma resolução | ⬜ |  |
| **TC-113** | Navegação apenas com teclado | 1. Pressione Tab repetidas vezes para navegar entre elementos<br>2. Use Enter/Space para clicar<br>3. Use Setas para navegar dropdowns | Todos os elementos interativos são focáveis; ordem de foco é lógica (esquerda → direita, cima → baixo) | ⬜ |  |

---

## 📊 Resumo de Execução

Use esta tabela para compilar resultados finais:

| Página/Seção | Total Testes | Passou (🟢) | Atenção (🟡) | Falha (🔴) | Bloqueado (⛔) | Taxa de Sucesso |
|---|---|---|---|---|---|---|
| Layout Global | 6 | | | | | |
| Chat | 11 | | | | | |
| Dashboard | 10 | | | | | |
| Consultas | 14 | | | | | |
| Alertas | 9 | | | | | |
| Auditoria | 10 | | | | | |
| Documentos | 14 | | | | | |
| Erros/Edge Cases | 4 | | | | | |
| Performance | 4 | | | | | |
| **TOTAL** | **82** | | | | | **_%** |

---

## 🐛 Reportar Problemas

Quando encontrar um problema:

1. **Anote:**
   - ID do caso de teste (ex: TC-45)
   - Descrição clara do que esperava vs o que viu
   - Passos para reproduzir
   - Navegador e versão
   - Screenshot/vídeo (se aplicável)

2. **Reporte em:**
   - Slack channel `#agroia-testes` (se disponível)
   - Email para `humberto@hai.expert`
   - GitHub Issues (se público)

**Exemplo de relatório:**
```
Caso: TC-50 (Paginação)
Descrição: Ao clicar "Próximo" na página de Consultas, a página 2 carrega, 
mas os controles de paginação não mostram que estou na página 2.
Passos: 1. Abra Consultas → 2. Clique "Próximo" → 3. Observe os botões de página
Navegador: Chrome 124.0
Screenshot: [link]
```

---

## 📝 Observações Técnicas

- **LocalStorage:** Conversa do chat e preferências do usuário são salvos em localStorage. Para limpar: `localStorage.clear()` no console (F12).
- **Cookies:** Nenhum cookie é usado (autenticação via API Key no header).
- **Cache do navegador:** Se vir dados antigos, use Ctrl+Shift+R (hard refresh).
- **DevTools útil:** F12 → Network → filter "XHR" para ver chamadas da API em tempo real.

---

## ✅ Checklist Final

Antes de considerar a plataforma "pronta para produção":

- [ ] Todos os 82 testes passaram (taxa de sucesso ≥ 90%)
- [ ] Nenhuma falha crítica (bloqueio de fluxo principal do chat/dashboard)
- [ ] Tempo de resposta aceitável (chat < 10s, dashboard < 5s)
- [ ] Responsividade confirmada em desktop e tablet
- [ ] Documentação de erros conhecidos criada (se houver)
- [ ] Stakeholders confirmaram aceitação

---

**Documento criado em:** 26 de abril de 2026  
**Versão:** 1.0  
**Próxima revisão:** Após cada release ou mudança significativa
