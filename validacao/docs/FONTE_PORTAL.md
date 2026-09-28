# Fonte: Portal da Transparência de Curitiba (órgão FAAC)

Levantamento da Fase 0, feito em 26/09/2026 lendo `coleta_transparencia.py` apenas para
descobrir rotas e campos, e confirmado por sondagem direta do portal com Playwright a partir
da rede do PC do usuário. Nenhum código do coletor foi copiado para `validacao/`.

## Rotas

| Uso | URL |
|---|---|
| Pesquisa (listagem) | `https://www.transparencia.curitiba.pr.gov.br/sgp/licitacoes.aspx` |
| Detalhe do processo | `https://www.transparencia.curitiba.pr.gov.br/Sgp/LicitacoesDetalhes.aspx?id={id}` |
| Arquivos (PDF, TIF) | `https://mid-transparencia.curitiba.pr.gov.br/contratos/licitacoes/{ano}/{ORGAO}_{ano}_{MOD}_{n}_{id}_{arq}.pdf` |
| Extrato de empenho | `https://www.transparencia.curitiba.pr.gov.br/sgp/despesaextrato.aspx?exercicio={ano}&empresa={e}&empenho={n}` |

Tecnologia: ASP.NET WebForms com UpdatePanel (postback assíncrono MS AJAX). O `id` do detalhe
não aparece na grade: o link "Ver detalhes" (`gdvLicitacao$ctlNN$lnbVerDetalhes`) dispara um
postback cuja resposta redireciona para a página de detalhe.

## Formulário de pesquisa

| Campo | Elemento | Valor usado |
|---|---|---|
| Órgão | `select#cphMasterPrincipal_ddlOrgao` | `FAAC` (texto: "FUNDO DE ABASTECIMENTO ALIMENTAR DE CURITIBA") |
| Ano do processo | `input#cphMasterPrincipal_txtAnoProcesso` | ano (padrão da página: ano corrente) |
| Pesquisar | `a#cphMasterPrincipal_lnbPesquisar` | postback assíncrono |
| Outros filtros | `txtProcessoCompra`, `ddlModalidade`, `txtDataInicial`, `txtDataFinal`, `ddlFornecedor`, `txtObjeto`, `ddlSituacao`, `chkCovid19` | não usados |

Observações da sondagem:

- Sem filtro aplicado, a grade padrão lista processos de todos os órgãos do ano corrente. O
  extrator confirma que todas as linhas pertencem ao órgão e ao ano pesquisados.
- O portal não entrega os scripts do ASP.NET a agentes de usuário que não se identificam como
  navegador. O extrator usa o UA do Chromium seguido da identificação acadêmica do projeto.
- Paginação: 15 linhas por página; links `ucPaginadorBaixo$<índice>_pg<página>`; o último link
  "..." avança para o bloco seguinte de 10 páginas.
- Volume observado: 2025 = 189 processos FAAC em 13 páginas.

## Grade de resultados (`table#cphMasterPrincipal_gdvLicitacao`)

Cabeçalhos: `Num Processo`, `Modalidade`, `Orgão`, `Objeto`, `Valor global`,
`Local execução/entrega`, `Celebração`, `Protocolo`, `Situação`.

Chave natural: `Num Processo` (ex.: `PE 3/2025`). Na base, `licitacoes.processo` guarda
`PE 3/2025 - SMSAN/FAAC`; a chave de comparação remove o sufixo e normaliza espaços.

## Página de detalhe

Título: `Detalhes Licitacao - PE 3 /2025`.

Quadro "Dados da Licitação/Contratação" (pares rótulo e valor em `td`):
`Licitação/Contratação` (objeto), `Empresa`, `Setor/Órgão`, `Modalidade da Contratação`,
`Prazo Contratual`, `Protocolo`, `Situação do Processo`, `Nº Edital`, `Data Abertura Edital`,
`Setor Edital`, `Total de Forn. que Retiraram o Edital`, `Total de Fornecedores Participantes`.

Grades (tabela vazia contém a linha "Nenhuma informação foi encontrada."):

| Grade | id | Cabeçalhos |
|---|---|---|
| Fornecedores participantes | `cphMasterPrincipal_gdvFornecedoresParticipantes` | CPF/CNPJ, Razão Social |
| Arquivos do processo | `cphMasterPrincipal_gdvArquivos` | Documento, Arquivo (link "Download") |
| Itens | `cphMasterPrincipal_gdvItensProcesso` | Item, Quantidade, Unidade Medida, Fornecedor/Contratado, CNPJ, [Contrato, Prazo Contratual,] Valor Unitário, Valor Total |
| Empenhos | `cphMasterPrincipal_gdvEmpenhoItens` | Órgão, Nome Contratado, CNPJ, Empenhado, Num Empenho, Liquidado, Anulado, Pago, A Pagar, Fonte Recursos, Documentos |
| Atas | `cphMasterPrincipal_gdvAtasProcesso` | (vazia nos processos sondados) |

A grade de itens não traz código do item nem número sequencial; a sequência é a ordem de
exibição. O ano do empenho vem do parâmetro `exercicio` do link "Detalhes".

## Documentos

Os arquivos ficam em `mid-transparencia.curitiba.pr.gov.br` (PDF e também TIF). A base da
plataforma (`documentos_licitacao`) guarda os PDFs coletados do portal JSF desativado,
hospedados no Google Drive (`url_publica` = `https://drive.google.com/file/d/<id>/view`),
com `tamanho_bytes`, **sem hash**. A camada A1.3 compara tamanho, número de páginas e
similaridade de texto (Jaccard sobre 5-gramas de palavras).

## Portal JSF desativado

`consultalicitacao.curitiba.pr.gov.br:9090` (fonte da carga histórica) não resolve DNS desde
23/09/2026. Registros da base que vieram dessa fonte e não aparecem no portal atual recebem o
status `NAO_VERIFICAVEL_FONTE_DESATIVADA`. Indicadores de origem legada na base: itens com
`codigo` preenchido e `licitacoes.url_detalhe` nulo.

## CEASA-PR (cotações por variedade)

| Uso | URL |
|---|---|
| Formulário | `https://celepar7.pr.gov.br/ceasa/cotprod_evolucao.asp` |
| Resultado (POST) | `https://celepar7.pr.gov.br/ceasa/result_evolucao_precos.asp` |

Domínios permitidos ao agente na condição PORTAL: `www.transparencia.curitiba.pr.gov.br`,
`mid-transparencia.curitiba.pr.gov.br`, `celepar7.pr.gov.br`.
