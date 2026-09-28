# Esquema real do Supabase (Fase 0)

Levantado em 26/09/2026 por consulta direta (`select * limit 1` e `count=exact`) ao projeto
`rsphlvcekuomvpvjqxqm`. O DDL das tabelas centrais não está versionado no repositório
(DOSSIE_TECNICO, seção 6); as colunas abaixo são as devolvidas pelo PostgREST.

## Contagens na data do levantamento

| Objeto | Linhas |
|---|---|
| `licitacoes` | 1.374 (838 com `relevante_af = true`; 378 com `url_detalhe` preenchido) |
| `itens_licitacao` | 8.473 |
| `fornecedores` | 3.183 |
| `participacoes` | 27.219 |
| `empenhos` | 4.236 |
| `documentos_licitacao` | 180 |
| `pdf_chunks` | 216 (estimativa do planejador) |
| `prohort_precos` | 298.999 (estimativa do planejador) |
| `vw_itens_agro` | 1.015 |
| `vw_licitacoes_agro_documentos` | 24 |
| `vw_cruzamento_precos_ceasa` | 198 |
| `ceasa_pr_cotacoes` | **não existe no banco** (PGRST205; o DDL `sql/ceasa_pr_cotacoes.sql` não foi aplicado) |

Os números do CLAUDE.md (715 licitações agrícolas) são anteriores à troca de fonte; a validação
usa sempre as contagens do snapshot da execução.

## Tabelas e chaves

### `licitacoes`
Colunas: `id`, `processo`, `tipo_processo`, `nr_edital`, `modalidade`, `orgao`, `empresa`, `setor`,
`objeto`, `dt_abertura`, `situacao`, `local_abertura`, `total_forn_retiraram_edital`,
`total_forn_participantes`, `canal`, `relevante_af`, `url_detalhe`, `coletado_em`.

- Chave natural: `processo` (formato `PE 3/2025 - SMSAN/FAAC`); unicidade `(processo, orgao)`.
- Chave de comparação com o portal: `processo` sem o sufixo ` - SMSAN/FAAC`, espaços normalizados.
- Ano do processo: sufixo `/AAAA` do número (é o filtro "Ano do processo" do portal).
- Não há coluna de valor estimado ou homologado; o valor por processo é derivado de
  `itens_licitacao.valor_total`.
- Origem do registro: `url_detalhe` nulo indica carga do portal JSF desativado.

### `itens_licitacao`
Colunas: `id`, `licitacao_id`, `seq`, `codigo`, `descricao`, `descricao_completa`, `observacao`,
`qt_solicitada`, `unidade_medida`, `valor_unitario`, `valor_total`, `cultura`, `categoria`
(legada), `categoria_v2`, `relevante_agro`.

- Unicidade `(licitacao_id, seq)`. `codigo` preenchido indica item do portal JSF.

### `fornecedores`
Colunas: `id`, `cpf_cnpj`, `razao_social`, `tipo`, `municipio`, `uf`, `habilitado_*`,
`primeira_participacao`, `ultima_participacao`, `total_processos`, `dap_caf_ativo`,
`situacao_cadastral`, `fonte`, `coletado_em`, `atualizado_em`.

- `cpf_cnpj` aparece com e sem pontuação (cerca de 1,4 mil duplicatas por grafia); a
  comparação usa somente os dígitos.

### `participacoes`
Colunas: `id`, `licitacao_id`, `fornecedor_id`, `retirou_edital`, `participou`, `habilitado`,
`vencedor`, `coletado_em`. Unicidade `(licitacao_id, fornecedor_id)`.

### `empenhos`
Colunas: `id`, `item_id`, `fornecedor_id`, `nr_empenho`, `ano`, `dt_empenho`, `valor_empenhado`,
`coletado_em`.

- Vínculo com a licitação passa pelo item (`item_id → itens_licitacao.licitacao_id`).
- Chave natural do empenho: `(nr_empenho, ano)`.

### `documentos_licitacao`
Colunas: `id`, `licitacao_id`, `nome_arquivo`, `nome_doc`, `storage_path`, `url_publica`,
`tamanho_bytes`, `coletado_em`, `erro`, `conteudo_agro`.

- **Não há hash do arquivo.** Há `tamanho_bytes`. URLs apontam para o Google Drive.

### `pdf_chunks`
Colunas: `id`, `licitacao_id`, `documento_id`, `processo`, `nome_doc`, `chunk_index`, `chunk_text`,
`embedding` (vector 384, omitido no snapshot), `tokens_aprox`, `indexado_em` e metadados
gravados pelo indexador.

### `prohort_precos`
Colunas: `id`, `data_coleta`, `ceasa`, `produto`, `produto_norm`, `unidade`, `preco_min`,
`preco_medio`, `preco_max`, `origem`, `criado_em`. Unicidade `(data_coleta, ceasa, produto)`.
Inclui as unidades da CEASA-PR (`CURITIBA`, `MARINGA`, `CASCAVEL`, `FOZ DO IGUACU`, ...).

### Views usadas
- `vw_itens_agro`: itens com dados da licitação (`processo`, `dt_abertura`, `canal`). A amostra
  de uma linha trouxe `relevante_agro = false`, portanto a view não filtra só itens agrícolas;
  as tarefas filtram explicitamente.
- `vw_cruzamento_precos_ceasa`: `ceasa`, `produto_norm`, `cultura`, `preco_kg_prefeitura`,
  `n_itens`, `ano_min`, `ano_max`, `preco_ceasa_medio`, `preco_ceasa_min`, `preco_ceasa_max`,
  `unidade_ceasa`, `unidades_compativeis`, `diferenca_pct`.
- `vw_licitacoes_agro_documentos`: documentos das licitações agrícolas (página Documentos).

## Tabelas excluídas do snapshot

`conversas`, `log_consultas_agente`, `coleta_status`, `coleta_execucoes`, `app_config`,
`benchmark_*`, `produtores`, `ofertas_produtores`: estado operacional, não entram nas
comparações. Views ancoradas em "hoje" (`v_prohort_analise`) também ficam de fora, porque
mudam sem nova coleta e quebrariam a estabilidade do hash.
