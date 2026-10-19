# Auditoria independente — pauta do Sacolão / planejamento de safra / projeção com clima

| Campo | Valor |
| --- | --- |
| Data | 2026-10-17 |
| Ramo auditado | `feat/pauta-safra-projecao` |
| Commit | `aac9935` |
| Base | tag `dissertacao-base` (`c808731`) |
| Escopo | `git diff dissertacao-base..feat/pauta-safra-projecao` (15 commits, 37 arquivos, +4921/−24) |
| Auditor | agente independente (não escreveu o código); só leitura no banco e no repositório, exceto este arquivo |

## Veredito

**NÃO APROVADO.** Os 15 itens têm evidência, mas há **2 achados de severidade alta abertos**
(A1 e A2). Os dois atingem resultados de pesquisa e a regra de publicação, não a API em produção:
as rotas `/pauta/safra/*`, os coletores e os contratos de não impacto estão corretos.

---

## Tabela dos 15 itens

| # | Item | Resultado | Evidência |
| --- | --- | --- | --- |
| 1 | Escopo do diff | **aprovado** | `git diff --name-status dissertacao-base..HEAD`: 31 arquivos **novos (A)** e 6 **existentes (M)**: `.github/workflows/ceasa_pr.yml` (inputs `inicio`/`fim` passados por `env`), `api/main.py` (+8: só o bloco `try/except` com `include_router(pauta_router)`), `agroia-frontend/src/App.tsx` (+2: import e `<Route path="safra">`), `agroia-frontend/src/i18n/nav.ts` (+3: `safra` em pt/en/es), `agroia-frontend/src/components/Layout.tsx` (+2: ícone `CalendarRange` e item `/safra`; só linhas novas), `chat/ceasa_pr_collector.py` (refazer janela dia a dia, status de erro na gravação, `--inicio/--fim`, `data_max` que não regride). Todos estão entre os 7 permitidos. `chat/agent.py` sem mudança. Nenhuma documentação foi alterada (ver item 8). |
| 2 | Contratos | **aprovado** | `python scripts/linha_base_contratos.py --comparar validacao/relatorios/base_2026-10-15.json` → `Contratos intactos.` (exit 0). Medição atual: 39 rotas (36 da base + `GET /pauta/safra/{catalogo,sazonal,comparar}`); `set(base) − set(atual) = ∅`; TOOLS_SCHEMA = 11 ferramentas (mesmos nomes); `git diff dissertacao-base..HEAD -- requirements-api.txt Dockerfile chat/prompts.py` vazio. Ressalva: a RPC `contrato_viewdefs` responde **404** (o SQL não foi aplicado), então as views são comparadas só pelos nomes de colunas (B9). |
| 3 | Chaves desligadas | **aprovado** | `git diff --stat dissertacao-base..HEAD -- chat/agent.py chat/tools.py` vazio. Os únicos `TOOLS_SCHEMA.append` do repositório estão em `chat/tools.py:1304` (código anterior, inalterado). No código novo, `TOOLS_SCHEMA` só aparece em `scripts/linha_base_contratos.py` (leitura para hash). |
| 4 | Segurança | **aprovado** (com ressalva) | `sql/clima.sql:68-85`: RLS ligado nas 5 tabelas, só políticas `for select to anon, authenticated`, nenhuma política de escrita, `grant select`. `sql/ceasa_pr_cotacoes.sql` não mudou no diff (políticas de leitura nas linhas 32-33, 78-80). `sql/contrato_viewdefs.sql:105-106`: `revoke ... from public, anon`, `security invoker`, só leitura de `pg_get_viewdef`. `api/pauta_api.py`: só `@router.get`; `produto`/`ceasa` validados contra a lista fechada do catálogo (`_validar`, l.67-75) e `max_length=40`; `unidade` com regex `^[A-Za-z]{1,4}$`; consultas pelo cliente PostgREST (sem SQL montado à mão). TestClient: `produto="alface'; drop table x;--"` → 422. Frontend: `Safra.tsx` e `lib/pauta.ts` sem `import.meta.env` (nenhuma chave nova). Workflows passam os inputs por `env` (sem interpolação `${{ }}` dentro do script). Nenhum dado pessoal (preços e clima). **Ressalva:** não foi possível conferir o RLS ao vivo — a chave anon de `agroia-frontend/.env.local` responde 401 "Invalid API key"; verificação só por leitura do SQL. |
| 5 | Tratamento de erro | **aprovado** | Coletor CEASA (`chat/ceasa_pr_collector.py:181-198, 257-263`): lote que falha → `falhas_gravacao` → `status='erro'`; `__main__` → `sys.exit(1)`. Portal sem cotações em ≥ 2 dias úteis → falha "estrutura do HTML mudou?" → erro. Coletor de clima (`chat/clima_collector.py:107-117, 179-205`): mesma regra. Testes offline passam: `test_tp0_coletor_ceasa_pr_gravacao_falha_e_erro`, `..._portal_sem_cotacoes_e_erro`, `..._isola_dia_com_erro_500`, `test_coleta_tabela_ausente_e_erro`. API (TestClient com o banco real, só leitura): produto inválido → 422 com a lista aceita; `produto` ausente → 422; 41 caracteres → 422; `unidade=KG1` → 422; CEASA desconhecida → 422; nenhuma resposta 500. `Safra.tsx:193-195`: erro mostra `aviso-box erro` com texto nos 3 idiomas, não tela vazia. Ressalvas menores: B1 (`ceasa=''` → 404 "em None") e B11. |
| 6 | Dependências da API | **aprovado** | `git diff dissertacao-base..HEAD -- requirements-api.txt Dockerfile` vazio. Imports (AST): `api/pauta_api.py` → `chat`, `chat.db`, `collections`, `datetime`, `fastapi`, `logging`, `statistics`, `time`; `chat/pauta.py` → `datetime`, `statistics`; `chat/db.py` → `dotenv`, `os`, `supabase`. Teste: com `sys.modules['pandas'|'numpy'|'scipy'|'sklearn'|'statsmodels'|'torch'] = None`, `import api.pauta_api` funciona e registra as 3 rotas. `ml/` (pandas/numpy/scipy) não é importado pela API. |
| 7 | Desempenho | **aprovado** (com ressalva) | TestClient + banco real: `catalogo` 0,29–1,21 s (com cache: 0,00 s); `sazonal` 0,42–1,24 s incluindo o catálogo (com cache: 0,00–0,01 s); `comparar` 0,20–0,31 s. Primeira requisição após o processo subir: 3,4–5,1 s (2,7 s só para criar o cliente Supabase + 3,4 s no primeiro acesso ao catálogo) — acima de 2 s só na partida a frio (B2). Paginação de 1000 em 1000 (`_paginar`); cache de 1 h. Problema de cache sem expurgo: M2. |
| 8 | Idiomas e documentação | **reprovado** (documentação) | Idiomas OK: `Safra.tsx` tem 31 chaves em pt, en e es (conjuntos iguais; `defineMessages` exige por tipo); `nav.ts` +`safra` nos 3. Documentação: `grep -i "clima\|/pauta\|safra\|ipca\|indice_enso\|checar_integridade\|linha_base"` em `CLAUDE.md` e `DOCUMENTACAO_ARQUITETURA.md` → **nenhuma ocorrência**. Tabelas `clima_*`, `ipca_mensal`, `indice_enso`, o workflow `clima.yml`, as rotas `/pauta/safra/*`, a página `/safra` e os scripts de integridade/contratos não estão documentados (M1). |
| 9 | Fidelidade à Portaria nº 175 | **não aplicável nesta fase** | E2 não implementada: `chat/pauta_dados.py` não existe; `test_tp1_cadastro_pauta_175` pula (`importorskip`). Nada finge ter a pauta: `api/pauta_api.py:8` declara `/pauta`, `/pauta/fundamentacao` e `/pauta/exportar` como pendentes; `Safra.tsx` não menciona Sacolão, Portaria nem Anexo I; `chat/pauta.py` só tem funções puras genéricas (`cobertura_subgrupo`, `acima_do_teto`) sem dados da portaria. |
| 10 | Corretude dos preços e do clima | **aprovado** | CEASA/PR, Curitiba, portal × `ceasa_pr_cotacoes`, dia inteiro: **15/10/2026** — 204 descrições no portal, 204 no banco, 0 só de um lado, 0 preços divergentes; **12/03/2024** — 308 × 308, 0 divergentes. Exemplos iguais: `TANGERINA IMPORTADA cx 10 kg` 100,00; `TANGERINA CRAVO cx 20 kg` 80,00 (2024); `TOMATE CEREJA BANDEJA bj 200 g` 4,00; `ALFACE AMERICANA cx 7,5 kg` 35,00 (2026) / 45,00 (2024). O HTML bruto de 12/03/2024 foi lido sem o parser: 1ª coluna de preço = Curitiba (`TANGERINA CRAVO cx 20 kg | 80,00 | 80,00 | - ...`). Clima `pr_colombo` × NASA POWER (API ao vivo): 19–21/07/2021 e 08–10/10/2026, 6 variáveis — todos iguais. Extra: ONI de 2025-01 em diante igual ao `oni.data` da NOAA (20 meses); IPCA 2017-01, 2020-06, 2024-12 iguais ao SIDRA. Observação metodológica: M3. |
| 11 | Integridade | **aprovado** | Checagens de `scripts/checar_integridade.py` executadas importando as funções (para não sobrescrever o `integridade_2026-10-17.json` versionado — ver B10), janela de 30 dias: I1 OK (0), I2 OK (0), I2b aviso (0), I3 OK (0), I6 aviso (31 variações atípicas), I4 OK (última de Curitiba 15/10/2026), I21 OK (status ok, `data_max` 15/10 = maior data da tabela), I14 OK (5 regiões de 2017-01-01 a 2026-10-12, cobertura 1,0, 0 impossíveis, atraso 5 dias), I17 OK (IPCA até 2026-09, sem lacuna). Último relatório versionado `validacao/relatorios/integridade_2026-10-17.json` (completo, 04:18 UTC): aprovado; I5 com 276 séries com lacuna > 3 meses (só aviso para o alerta FAO). |
| 12 | Vazamento temporal | **aprovado** (com ressalva) | `ml/atributos.py:34` corta a série em `index <= origem` antes de qualquer cálculo; `test_tp9_atributos_nao_veem_o_futuro` passa (muda o futuro ⇒ atributos iguais; muda a origem ⇒ diferentes). `rodar.py:113` e `ablacao_clima.py:87` treinam só com `alvo_data <= origem`. `ablacao_clima.py:47` usa clima com `index <= origem`; climatologia 1991–2020 (anterior aos preços de 2022+). Ressalva B4: `rodar.py:68` interpola a série inteira antes do corte (o ponto interpolado usa t+1) — hoje 94 pontos (0,9%) e **0 na janela de teste**, impacto atual nulo; T-P9 não cobre esse passo. Ressalva operacional: a semana-origem do clima cobre seg–dom e o POWER atrasa 2–7 dias, então o backtest supõe clima que, na operação, ainda não existiria no dia da origem. |
| 13 | Validação honesta | **reprovado** | Projeção: hiperparâmetros fixos (`max_iter=200, lr=0,05, max_leaf_nodes=15, min_samples_leaf=40`), sem busca; `git diff 4ef33ff d73cb1f` mostra que só mudaram os horizontes e a regra (mais rígida) — nenhum ajuste escolhido no teste. Não há janela de validação separada: as mesmas 52 origens servem para medir e decidir (aceitável para o veredito "não publicar", que é conservador). **Clima × preço: o resultado está errado (A1)** — o p por deslocamento circular tem piso artificial; refeito com todos os deslocamentos, nenhuma associação sobrevive. Os produtos da ablação vieram dessa análise, que inclui a janela de teste (seleção pós-teste; impacto pequeno, porque a ablação deu negativo). Outros pontos menores em B13. |
| 14 | Comparação com referência | **reprovado** | Fórmulas conferidas (`ml/avaliacao.py`): MASE = MAE/MAE do ingênuo sazonal dentro da amostra (l.64-78) ✔; DM com perda absoluta, d = \|e_modelo\| − \|e_ref\|, variância de longo prazo com h−1 autocovariâncias, correção HLN `sqrt((n+1−2h+h(h−1)/n)/n)`, t com n−1 g.l., cauda **inferior** (H1: modelo melhor) ✔; variância ≤ 0 → p `None` → não publica ✔ (conservador). Desvio pequeno: autocovariância dividida por n−k (B5). **Falha (A2):** previsões numericamente idênticas ao ingênuo passam como "melhores" — reproduzido com dados reais (mamão formosa, h = 8). |
| 15 | Textos | **aprovado** | `grep -i "garant\|certeza\|acerto\|promessa\|promise"` em `Safra.tsx`: só o rodapé `rodape` (l.43/76/109) "Material de apoio ao planejamento. Não é promessa de preço…" (pt/en/es), exibido em `Safra.tsx:295-299` quando há dados. Aviso de frete sempre visível na comparação (`data-testid="aviso-frete"`). Nenhuma interface fala em previsão. |

Suíte de testes: `python -m pytest tests validacao/tests -q -p no:cacheprovider -W ignore --ignore=tests/test_e2e_agente.py --ignore=tests/test_e2e_comparador.py` → **1 failed, 240 passed, 21 skipped** — a única falha é a pré-existente `tests/test_critical_hotfixes.py::test_logging_setup`. (Os dois e2e foram excluídos por regra da auditoria; sem backend, eles pulam de qualquer forma.)

Frontend: não registrado pelo auditor (a sessão foi interrompida antes). Verificação do autor em 19/10/2026: `npx tsc -b` e `npx eslint src/pages/Safra.tsx` sem erros.

---

## Achados (por severidade)

### Alta

**A1 — Clima × preço: p-valor com piso artificial; as "18 associações" e os "2 Granger" significativos não se sustentam.**
`analises/clima_preco/rodar.py:156-158`.
O nulo sorteia `N_BOOT = 999` deslocamentos em `rng.integers(26, n − 26)`. Com n = 228 há só
**176 deslocamentos distintos**; os 999 sorteios são repetições deles, e o p vira
`(1 + #)/(1 + 999)`, com piso 0,001, quando o piso real do teste é 1/177 = 0,00565.
Refiz o cálculo (mesmos dados, reprodução de r com erro máximo de 1e-16) enumerando os 176
deslocamentos: as 18 correlações têm p exato = 0,00565 (não 0,001) e, com o BH sobre os mesmos
665 testes, p ajustado = **0,179**. **0 de 595 correlações e 0 de 70 Granger sobrevivem.**
Um sinal disso já aparecia no relatório: 5 das 18 "significativas" têm IC 95% que cruza zero, e uma sexta (couve-flor, defasagem 9) encosta em zero (+0,00).
Consequência: a conclusão de `resultado_2026-10-16.md` ("18 associações sobrevivem") está errada, e a lista de produtos de
`ablacao_clima.py:32` foi escolhida a partir dela.
Correção: enumerar todos os deslocamentos `k = 26 … n−27` (o teste fica exato), p = (1 + #{|r_k| ≥ |r|})/(1 + K);
regenerar o CSV e o relatório; reescrever a conclusão (associação não detectada com ~4 anos de dados) e justificar a escolha dos
produtos da ablação por agronomia, não por esse resultado.

**A2 — A regra de publicação aprova previsões numericamente iguais ao ingênuo.**
`ml/avaliacao.py:121-141` (usada por `decidir_publicacao`, l.96-118).
Não há tolerância nem tamanho mínimo de efeito: d = |e_modelo| − |e_ref| de ordem 1e-10, mas
com sinal constante, tem variância ainda menor e dá p < 0,05. Reproduzido com dados reais:
ETS × ingênuo, mamão formosa, h = 8, 52 origens — |ETS − ingênuo| médio = **5,3e-9 R$**
(máx. 2,2e-8), d médio = −6,4e-10, MASE idênticos (0,562195 × 0,562195), DM p = **0,0376**. Por isso
`resultado_curitiba_2026-10-16.md` conta "ETS, h = 8: 1 publicável pela regra nova", o que é espúrio.
Na E6 em produção, `decidir_publicacao` publicaria um modelo que é o próprio ingênuo com ruído de ponto flutuante.
Correção: (a) se `max|e_modelo − e_ref| < ε` (ex.: 1e-6 × escala) ou se a redução relativa do MAE for menor que um mínimo
(ex.: 1–2%), considere que o modelo não supera a referência; (b) acrescente esse caso em `test_tp8_*`.

### Média

**M1 — Documentação não atualizada.** `CLAUDE.md` e `DOCUMENTACAO_ARQUITETURA.md` não citam:
as tabelas `clima_regiao`, `clima_diario`, `indice_enso`, `ipca_mensal` e `clima_status` (`sql/clima.sql`),
o workflow `clima.yml` (runner hospedado, com o `sql/clima.sql` como pré-requisito), as rotas `/pauta/safra/*`, a página `/safra`,
`ml/`, `scripts/checar_integridade.py`, `scripts/linha_base_contratos.py` e os inputs `inicio`/`fim` de `ceasa_pr.yml`. Correção: incluir uma seção em cada arquivo.

**M2 — Cache da API sem expurgo (crescimento de memória sem limite).** `api/pauta_api.py:32, 40-47, 144`.
A chave de `comparar` inclui `hoje.isoformat()`; entradas de dias anteriores nunca saem do `_cache`.
Cada entrada guarda as cotações de 30 dias de um produto (~200 dicts). Com uso diário dos 47
produtos, são ~9 mil dicts novos por dia, num processo de 512 MB (Render) que pode ficar semanas no ar.
Correção: em `_em_cache`, apagar as chaves expiradas (ou limitar o tamanho, p. ex. LRU de 200 entradas).

**M3 — "5 regiões" de clima são, na prática, 2 células do NASA POWER.** Em setembro de 2026,
`pr_curitiba`, `pr_colombo`, `pr_sjp` e `pr_araucaria` têm valores **idênticos** em `clima_diario` (mesma célula de 0,5°);
só `pr_mandirituba` difere. A "média simples de 5 pontos" (`analises/clima_preco/rodar.py:3-6, 68, 204`;
`ablacao_clima.py:5-6`) é 0,8 × célula A + 0,2 × célula B. Correção: dizer isso nos relatórios, escolher pontos em células
distintas (ou usar as 2 células explicitamente) e evitar gravar 4 cópias da mesma série.

**M4 — Regra de publicação sem correção para múltiplos testes.** `ml/avaliacao.py:96-118` com
`analises/projecao_viabilidade/rodar.py`: 47 séries × 2 modelos × 3 horizontes, cada um com α = 0,05.
Os 2 "publicáveis" restantes da regra nova (manga, GBM, h = 4, p × ingênuo = 0,048; inhame, GBM, h = 8) estão dentro do número
de falsos positivos esperado. A regra foi decidida pelo usuário; a recomendação é registrar isso na dissertação ou
aplicar BH entre as séries antes de publicar.

### Baixa

- **B1** `api/pauta_api.py:72` — `ceasa=''` vira `None`, passa na validação e consulta `eq('ceasa', None)` → 404 "sem cotações de alface em None". O esperado seria 422 ou o padrão CURITIBA.
- **B2** `api/pauta_api.py:54-64` — primeira requisição após a partida: 3,4–5,1 s (> 2 s); depois, de 0,2 a 1,3 s. Sugestão: aquecer o catálogo no startup.
- **B3** `chat/clima_collector.py:154-156, 184` — uma carga retroativa (`--inicio 2017-01-01 --fim 2017-12-31`) rebaixa `clima_status.data_max` para 2017-12-31. A correção 9548ffb, feita no coletor CEASA, não foi replicada aqui.
- **B4** `analises/projecao_viabilidade/rodar.py:68` (e `clima_preco/rodar.py:130`) — `interpolate(limit=2)` sobre a série inteira usa o valor de t+1. Hoje são 94 pontos (0,9%), nenhum na janela de teste. Sugestão: interpolar só dentro do corte por origem ou descartar a semana.
- **B5** `ml/avaliacao.py:133` — `np.mean` divide a autocovariância de defasagem k por n−k; DM/HLN usa 1/n. O efeito é pequeno (variância um pouco maior).
- **B6** `chat/pauta.py:116` — `indice <= -0.5` classifica −0,5 como "baixo"; na FAO, −0,5 ≤ IPA < 0,5 é "normal". Só afeta o limite exato.
- **B7** `api/pauta_api.py:57-58` — o catálogo usa `limit(1000)` sem paginação (hoje são 516 linhas, então é silencioso se crescer). Em `api/pauta_api.py:102-104`, a paginação por offset é ordenada por `data_coleta`, que não é única (pode repetir ou pular uma linha na fronteira da página).
- **B8** `tests/test_clima_collector.py:153` — `test_coleta_sem_regioes_cadastradas_e_erro` testa, na verdade, uma exceção na leitura; o caminho de lista vazia (`clima_collector.py:142-143`) fica sem teste.
- **B9** `scripts/linha_base_contratos.py:107, 116` — se a importação da API falhar (`rotas` vira dict) ou os modos de view diferirem, a comparação é pulada sem violação. `sql/contrato_viewdefs.sql` não está aplicado (RPC 404).
- **B10** `scripts/checar_integridade.py:233` — sempre grava `integridade_<hoje>.json` e sobrescreve o arquivo versionado do mesmo dia (o completo de hoje seria trocado pelo de 30 dias). Outros pontos: I17 não acusa IPCA parado no fim da série; I4 reprova em feriado.
- **B11** `agroia-frontend/src/pages/Safra.tsx:138-140` — `Promise.all`: se só `sazonal` falhar (404 de um par produto × CEASA sem dados, ou 422 de um `?produto=` inválido na URL), a comparação, que funcionaria, também some, e a mensagem é "tente novamente em instantes", que sugere um erro passageiro. Hoje, 516 dos 517 pares do seletor estão na view do catálogo, que vem de `prohort_precos`. O 517º, `uva rubi` × `CASCAVEL`, também responde 200, então o caso não foi observado com dados reais. Sugestão: usar `Promise.allSettled` e uma mensagem específica para 404/422.
- **B12** `api/pauta_api.py:126` — `consultado_em` mostra a hora do pedido, não a do dado em cache (até 1 h de diferença).
- **B13** `analises/clima_preco/rodar.py:129` — `deflator.reindex(mes).ffill()` segue a ordem de `id`; o mês ainda sem IPCA (out/2026) recebe o deflator da linha anterior na ordem do banco. Além disso, `chat/pauta.py:164-169` aceita o ano corrente com 10 meses (2026: jan–out), o que distorce a média do ano.
- **B14** `analises/projecao_viabilidade/ablacao_clima_2026-10-17.md` — o cabeçalho diz "Gerado em 2026-10-16" e o nome do arquivo diz 17 (duas chamadas a `date.today()`).

---

## Como reproduzir as evidências principais

- A1: recalcular `correlacao_defasada` com `ks = np.arange(26, n − 26)` (todos os deslocamentos), usando os dados de `clima_preco/rodar.py` (`semanal_clima(clima_diario())`, `semanal_preco(precos(), ipca())`), e reaplicar `benjamini_hochberg` sobre as 595 correlações + 70 Granger.
- A2: `series_semanais(carregar('CURITIBA'))['mamao formosa']`; origens `datas[-60:-8]`; `prever_ets(hist, 8)` × `hist.iat[-1]`; `diebold_mariano(real − ets, real − ing, h=8)` → p = 0,0376 com |ETS − ing| ~ 1e-9.

---

## Correções do autor (19/10/2026)

Seção acrescentada pelo autor do código; o texto acima é do auditor e não foi alterado.

| Achado | Correção | Commit |
| --- | --- | --- |
| A1 | Teste exato: todos os deslocamentos circulares (`analises/clima_preco/rodar.py`). Refeito: 0 de 595 correlações e 0 de 70 Granger sobrevivem ao BH (alface × chuva, Granger 4 semanas: p ajustado 0,073). Relatórios de 16/10 removidos; novo `resultado_2026-10-19.md` | `d79dc26` |
| A2 | `decidir_publicacao` exige redução de MAE ≥ 2% sobre cada ingênuo; teste `test_tp8_regra_publicacao_recusa_copia_do_ingenuo` | `d79dc26` |
| M1 | Seção 14 em `DOCUMENTACAO_ARQUITETURA.md` e seção nova em `CLAUDE.md` | este commit |
| M2 | Cache com expurgo das vencidas e teto de 300 entradas; teste | `57adbd0` |
| M3 | Análises usam só as células distintas do NASA POWER (2) e dizem isso; cadastro de regiões fica para E3 (procedência) | `d79dc26` |
| M4 | Registrado: 282 testes sem correção; com a regra nova restou 1 "publicável" (GBM, 8 semanas), compatível com acaso. A projeção segue desligada | — |
| B1, B7, B12 | `ceasa=""` → 422; catálogo paginado e ordem estável; `consultado_em` = hora da leitura | `57adbd0` |
| B2 | Não corrigido: só a primeira requisição após a partida passa de 2 s | — |
| B3, B8 | `data_max` do clima não regride; teste do caso sem regiões | `57adbd0` |
| B4, B5, B13, B14 | Sem interpolação com dado futuro; autocovariância com divisor n; deflação ordenada e ano corrente incompleto fora do índice sazonal; uma data por execução | `d79dc26`, `57adbd0` |
| B6 | −0,5 classificado como "normal" | `57adbd0` |
| B9, B10 | Rotas não medidas = violação; um arquivo de integridade por escopo e IPCA parado acusado | `57adbd0` |
| B11 | `/safra` com `allSettled` e mensagem própria para 404/422 | `57adbd0` |
