# Reverificação da auditoria — correções do autor (19/10/2026)

| Campo | Valor |
| --- | --- |
| Data | 2026-10-19 |
| Ramo | `feat/pauta-safra-projecao` |
| Commits reverificados | `d79dc26` (A1, A2, M3, B4, B5, B13, B14), `57adbd0` (M2, B1, B3, B6–B13), `4533a78` (M1 e análises refeitas) |
| Relatório original | `validacao/relatorios/auditoria_2026-10-17.md` |
| Auditor | o mesmo agente independente de 17/10 (não escreveu o código); só leitura no banco e no repositório, exceto este arquivo |

## Veredito

**APROVADO.** Os dois achados de severidade alta (A1 e A2) estão resolvidos, com evidência
independente. Nenhuma regressão de severidade alta ou média foi encontrada. Ficam 6 pontos novos
de severidade baixa ou informativa (N1–N6), nenhum bloqueante; o mais relevante é N1 (condição de
corrida no expurgo do cache da API) e N2 (frase falsa no `CLAUDE.md`).

## Verificações executadas

| Verificação | Resultado |
| --- | --- |
| `python -m pytest tests validacao/tests -q -p no:cacheprovider -W ignore --ignore=tests/test_e2e_agente.py --ignore=tests/test_e2e_comparador.py` | **1 failed, 253 passed, 21 skipped** (48 s). A única falha é a pré-existente `tests/test_critical_hotfixes.py::test_logging_setup`. Linha de base de 17/10: 240 passed → +13 testes novos, todos passando. |
| `python scripts/linha_base_contratos.py --comparar validacao/relatorios/base_2026-10-15.json` | `Contratos intactos.`, **exit 0**. A RPC `contrato_viewdefs` continua respondendo 404 (SQL não aplicado), então as views seguem comparadas pelos nomes de colunas. |
| `cd agroia-frontend && npx tsc -b` | sem erros (exit 0) |
| `npx eslint src/pages/Safra.tsx src/lib/pauta.ts` | sem erros nem avisos |
| `git status` depois das verificações | nenhum arquivo versionado alterado |

## Tabela dos achados

| Achado | Situação | Evidência |
| --- | --- | --- |
| **A1** — p com piso artificial no clima × preço | **resolvido** | `analises/clima_preco/rodar.py:169-173`: o nulo agora enumera `range(26, n − 26)` (176 deslocamentos para n = 228) e p = (1 + #)/(1 + K). No CSV novo `resultado_2026-10-19_correlacoes.csv`: n = 228 em todas as 595 linhas; **todos** os p são múltiplos exatos de 1/177; p mínimo = 0,005650 = 1/177 (não mais 0,001). BH recalculado por mim sobre os 595 p + 70 Granger = 665 testes: igual a `p_bh` dos dois CSVs (`np.allclose` verdadeiro); 0 correlações e 0 Granger com p ajustado < 0,05. **Recálculo independente a partir dos dados brutos** (cache do POWER + IPCA + `prohort_precos` lido do banco), com o meu próprio laço de deslocamentos: `brocolo × dias_chuva, defasagem 0`: r = −0,231610 / p = 0,005650 (CSV: iguais); `repolho × umidade_solo, 6`: r = +0,440696 / p = 0,107345 (iguais); `alface × chuva_mm, 4`: r = +0,226794 / p = 0,005650 (iguais). O relatório `resultado_2026-10-19.md` é coerente: "0 associações sobrevivem", Granger "0 de 70", menor p ajustado 0,073 (alface × chuva, 4 semanas = 0,00011 × 665 / 1), e o texto explica a troca do teste. Os relatórios de 16/10 foram removidos e não há referência a eles fora do relatório de auditoria. A escolha dos produtos da ablação passou a ser justificada por agronomia (`ablacao_clima.py:1-9`). Ver ressalva N5. |
| **A2** — regra de publicação aprova cópia do ingênuo | **resolvido** | `ml/avaliacao.py:68-79`: além do DM, exige `ganho = 1 − MAE/MAE_ref ≥ 0,02` sobre **cada** ingênuo; `mae_ref ≤ 0` ou NaN ⇒ ganho 0 ⇒ recusa. O teste `test_tp8_regra_publicacao_recusa_copia_do_ingenuo` é significativo: com as mesmas entradas e `ganho_minimo=-1e9` (regra antiga), `publicar=True` (p × ingênuo = 2e-45, ganho 4,9e-9); com a regra nova, `publicar=False`, motivo "ganho sobre o ingênuo simples de 0,0%". Contraexemplos testados: cópia do ingênuo **sazonal** → recusada (ganho 0%); ganho de 2,3% concentrado em um ponto, p = 0,162 → recusada pelo DM; série com NaN em `real` → recusada (falha fechada); previsão 2,1% melhor que o ingênuo com p ≈ 1e-30 → publicada, **aceitável pela regra decidida pelo usuário**. Não encontrei caminho em que uma previsão ≈ ingênuo seja publicada. Dados reais: no CSV `resultado_curitiba_2026-10-19.csv` o ETS h = 8 (mamão formosa) já não passa nem sem o ganho mínimo (efeito de B4); o único "publicável" é inhame, GBM, h = 8: ganho 37,5% sobre o ingênuo simples e 70,0% sobre o sazonal, p = 0,0005 e 0,035 — não é cópia do ingênuo. `rodar.py:153-155, 180-181` aplica o mesmo ganho mínimo à contagem do relatório. |
| **M1** — documentação | **resolvido** (com ressalva N2) | `CLAUDE.md:238-254` e `DOCUMENTACAO_ARQUITETURA.md:456-500` (seção 14) citam tudo o que M1 listou: tabelas `clima_regiao`, `clima_diario`, `clima_status`, `indice_enso`, `ipca_mensal`; `clima.yml`; `/pauta/safra/catalogo|sazonal|comparar`; página `/safra`; `ml/`; `checar_integridade.py`; `linha_base_contratos.py`; `inicio`/`fim` de `ceasa_pr.yml`. Afirmações conferidas no banco e no código: `ceasa_pr_cotacoes` com **784.318** linhas (doc: ~785 mil) desde **2021-07-01**; Maringá e Foz do Iguaçu com última cotação em 30/09/2026 e 0 linhas em out/2026; Londrina 540 linhas em out/2026 (publica pouco); `ceasa_pr.yml` e `clima.yml` com `runs-on: ubuntu-latest` e `concurrency` com `cancel-in-progress: false`; os dois coletores com `sys.exit(1)`; item `/safra` no grupo "Gestão" de `Layout.tsx:28-34`; nome `integridade_<data>_<escopo>.json` igual ao código; checagens I1–I6, I14, I17, I21 presentes. **Falsa:** `CLAUDE.md:252` "Hoje nenhuma série passa" (N2). Não verificável por mim: "375 MB de 500 MB" (exige painel do Supabase). Detalhe omitido: a doc não diz que `clima.yml` exige o `sql/clima.sql` aplicado antes (diz só "SQL em …"). |
| **M2** — cache sem expurgo | **resolvido** (com regressão N1) | `api/pauta_api.py:41-55`: expurga vencidas a cada gravação e limita a `CACHE_MAX = 300`, descartando a mais antiga. `test_cache_expurga_vencidas_e_respeita_teto` passa. Todos os chamadores de `_em_cache` (agora devolve tupla) foram ajustados: `_catalogo` usa `[0]` (l.73), `safra_sazonal` desempacota (l.132), `safra_comparar` desempacota (l.153); não há outro chamador no repositório. `_agora` é definido na l.58, depois de `_em_cache`, mas só é chamado em tempo de execução — sem erro (testado). |
| **M3** — 5 regiões = 2 células | **parcialmente resolvido / aceito** | Análises: `clima_preco/rodar.py:67-79` remove séries idênticas antes da média; executado por mim: `CELULAS_DISTINTAS = 2`; o relatório novo diz "5 pontos … em 2 células distintas"; `ablacao_clima.py` usa o mesmo `clima_diario()`. Doc: `CLAUDE.md:248` e seção 14.1. O banco continua com as 5 regiões em `clima_regiao` (4 cópias da mesma célula em `clima_diario`); o autor adiou para E3 — aceito, porque nada em produção faz média dessas linhas. |
| **M4** — sem correção para múltiplos testes | **aceito** | Decisão do usuário; o relatório de projeção agora declara "282 testes sem correção … alguns 'publicáveis' são esperados por acaso" e a projeção segue desligada. |
| **B1** — `ceasa=""` | **resolvido** | `pauta_api.py:81-83`: `ceasa=""` vira `""`, não `None`, e falha na lista fechada → 422. Coberto por `test_sazonal_entrada_invalida_e_422[params0]`. |
| **B2** — partida a frio > 2 s | **aceito** (não corrigido) | Declarado pelo autor; só a 1ª requisição. |
| **B3** — `data_max` do clima regride | **resolvido** | `clima_collector.py:120-125, 192-193`: `max(atual, anterior)` com leitura protegida por `try`. Teste `test_carga_retroativa_nao_rebaixa_data_max` passa. Banco hoje: `clima_status.data_max = 2026-10-12`, `ok`. |
| **B4** — interpolação com t+1 | **resolvido** na projeção; **aceito** no clima × preço | `projecao_viabilidade/rodar.py:69-71`: sem `interpolate`; `ml/atributos.py` usa defasagens por data, então lacunas não desalinham os atributos. `clima_preco/rodar.py:143` mantém `interpolate(limit=2)`: é análise retrospectiva com STL bilateral (sem previsão), então não há vazamento relevante. |
| **B5** — divisor da autocovariância | **resolvido** | `ml/avaliacao.py:98`: `np.sum(...) / n`. |
| **B6** — −0,5 "baixo" | **resolvido** | `chat/pauta.py:116`: `indice < -LIMIAR_MODERADO`. Teste `test_tp3_limite_menos_meio_e_normal` (−0,5 → normal; −0,51 → baixo). |
| **B7** — catálogo sem paginação / ordem instável | **resolvido** | `pauta_api.py:65-67`: `_paginar` + `order(produto_norm, ceasa)`; `sazonal` ordena por `data_coleta, id` (l.113); `comparar` por `id` (l.149). |
| **B8** — caso sem regiões sem teste | **resolvido** | `tests/test_clima_collector.py`: `test_coleta_sem_regioes_cadastradas_e_erro` agora usa `regioes=[]` e exige `status == "erro"` e falha "nenhuma região"; o caso antigo foi renomeado para `test_coleta_leitura_de_regioes_falha_e_erro`. |
| **B9** — comparação de contratos pulada | **resolvido** (código); RPC ainda não aplicada | `linha_base_contratos.py:107-110`: rotas não medidas viram violação; l.120-126: modos diferentes comparam ao menos o conjunto de views e avisam. `contrato_viewdefs` continua 404. |
| **B10** — arquivo sobrescrito, IPCA parado | **parcialmente resolvido** | `checar_integridade.py:239-241`: `integridade_<data>_completo.json` / `_<n>d.json`; l.204-212: I17 reprova com atraso > 2 meses (hoje: último 2026-09, atraso 1 → OK). Não tratado: I4 continua reprovando em feriado (ponto secundário de B10; o autor não o listou). |
| **B11** — `Promise.all` em `/safra` | **resolvido** | `Safra.tsx:117-123, 150-168`: `allSettled`; 404/422 → aviso "sem cotações nesta CEASA" (pt/en/es); outro erro → `falha`. Erro de rede sem `response`: `(r.reason)?.response?.status` é `undefined` → `falha` (mensagem "tente novamente"), correto. `apiClient` é axios sem interceptador de resposta, então `response.status` existe nos erros HTTP. A comparação continua visível quando só o calendário falha. |
| **B12** — `consultado_em` | **resolvido** | `_em_cache` grava `_agora()` junto com o valor e devolve a mesma hora nos acertos; `test_cache_devolve_hora_da_leitura_do_banco` passa. |
| **B13** — deflação por ordem do banco; ano corrente incompleto | **resolvido** | `clima_preco/rodar.py:138-142`: `sort_index` + `reindex` sobre a união ordenada dos meses; `ipca()` é monotônica e única (1979-12 a 2026-09, 562 meses). `chat/pauta.py:166-169`: o último ano só entra completo. **Séries que terminam em dezembro não quebram**: o último ano tem 12 meses e entra; os testes antigos de T-P6 (`_serie_mensal(anos=4)`, jan–dez) continuam contando 4 anos; o novo `test_tp6_ano_corrente_incompleto_fica_fora` cobre jan–out. Efeito colateral cosmético em N6. |
| **B14** — duas datas por execução | **resolvido** no escopo do achado | `ablacao_clima.py:25` e `projecao_viabilidade/rodar.py:31`: `HOJE` único. O mesmo padrão persiste em `clima_preco/rodar.py` (N4). |

## Regressões e achados novos

| # | Severidade | Onde | Descrição |
| --- | --- | --- | --- |
| **N1** | baixa | `api/pauta_api.py:50-53` | **Condição de corrida no expurgo do cache (regressão de M2).** As rotas são `def` síncronas (o FastAPI as roda num pool de threads) e o expurgo itera `_cache.items()` e faz `del _cache[k]` sem trava. Duas requisições com falta de cache ao mesmo tempo podem gerar `RuntimeError: dictionary changed size during iteration` ou `KeyError` (a mesma chave apagada duas vezes) → resposta 500. Reproduzido em teste de estresse artificial (16 threads × 3000 chamadas, `sys.setswitchinterval(1e-6)`, `CACHE_SEG = 0,0005`): 16.090 `RuntimeError` e 1.406 `KeyError`. Com o código antigo (só `get`/atribuição) isso não acontecia. Em produção a probabilidade é pequena (o expurgo só roda em falta de cache e o dicionário tem ≤ 300 entradas). Correção: `threading.Lock` em volta de leitura+expurgo+gravação, ou `_cache.pop(k, None)` sobre `list(_cache)`. |
| **N2** | baixa | `CLAUDE.md:252` | Afirmação falsa: "Hoje nenhuma série passa: a projeção fica desligada." `resultado_curitiba_2026-10-19.md` mostra **1** série publicável pela regra nova (inhame, GBM, h = 8); o próprio commit 4533a78 e a tabela do autor dizem "1 publicável". A projeção está desligada por decisão, não porque nada passa. `DOCUMENTACAO_ARQUITETURA.md:492` ("nenhuma série atende à regra de forma robusta") é defensável, mas deveria citar o caso único. |
| **N3** | baixa | `analises/projecao_viabilidade/ablacao_clima.py:107-108` | O cabeçalho do relatório da ablação ainda descreve a regra como "MASE < 1 e p < 0,05 contra os dois ingênuos", sem o ganho mínimo de 2% que a coluna "Motivo" já aplica (`ablacao_clima_2026-10-19.md`). |
| **N4** | informativa | `analises/clima_preco/rodar.py:217, 274` | Duas chamadas a `date.today()` (cabeçalho e nome do arquivo): o mesmo padrão de B14 continua nesta análise. |
| **N5** | informativa (metodológica) | `analises/clima_preco/resultado_2026-10-19.md` | Resolução do teste exato: com K = 176, o menor p possível é 1/177 = 0,00565; com BH sobre 665 testes, uma correlação só sobreviveria se ≈ 75 testes estivessem no piso (hoje são ≈ 19, p ajustado 0,198). Ou seja, com ~4 anos de dados a parte de correlação quase não tem poder; só o Granger (paramétrico) poderia sobreviver. O relatório e a doc ("não detectou associação") estão corretos, mas devem dizer que a ausência é de **detecção** com esse desenho, não evidência de ausência de efeito. |
| **N6** | informativa | `agroia-frontend/src/pages/Safra.tsx:173-176, 228-231`; `api/pauta_api.py:126` | Depois de B13, "Resumo de {n} anos ({de} a {ate})" conta só os anos usados (o ano corrente fica fora), mas o período mostrado vai até a última cotação (out/2026). Cosmético. |

Sem regressões encontradas em: chamadores de `_em_cache`; ordem de definição de `_agora`;
séries de `indice_sazonal` que terminam em dezembro; `classificarFalha` com erro de rede;
contratos (rotas, `TOOLS_SCHEMA`, prompts, views); tipos e lint do frontend.

## Como reproduzir

- A1: importar `analises/clima_preco/rodar.py` (`clima_diario`, `semanal_clima`, `semanal_preco(precos(), ipca())`)
  e calcular `corr(y_t, x_{t−lag})` e p com `np.roll(xv, k)` para `k in range(26, n − 26)`; comparar com o CSV de 19/10.
- A2: entradas de `test_tp8_regra_publicacao_recusa_copia_do_ingenuo` em `decidir_publicacao(..., ganho_minimo=-1e9)` (publica) e com o padrão (recusa).
- N1: 16 threads chamando `pauta_api._em_cache(("x", t, i % 50), ...)` com `CACHE_SEG` mínimo e `sys.setswitchinterval(1e-6)`.
