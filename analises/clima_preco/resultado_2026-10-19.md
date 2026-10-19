# Clima × preço — análise preliminar (PROHORT Curitiba)

Gerado em 2026-10-19. Preços de 2022-06-01 a 2026-10-15, deflacionados pelo IPCA, em log, sem tendência e sazonalidade (STL). Clima: 5 pontos do cinturão verde da RMC que caem em 2 células distintas do NASA POWER (média das células), em anomalia contra 1991–2020. **Escopo provisório:** sem ponderação por procedência (P8/P9). Valor-p exato por todos os deslocamentos circulares (substitui a versão de 16/10, que tinha piso artificial — auditoria, A1).

Testes: 595 correlações (produto × variável × defasagem 0–16 semanas) e 70 testes de Granger, todos corrigidos juntos por Benjamini-Hochberg. Correlação é associação, não causa.

## Resultado: 0 associações sobrevivem à correção para múltiplos testes

| Produto | Variável | Defasagem (semanas) | r | IC 95% | p ajustado |
| --- | --- | --- | --- | --- | --- |
| — | nenhuma | — | — | — | — |

## Maior associação por produto (antes da correção)

| Produto | Variável | Defasagem | r | IC 95% | p bruto | p ajustado |
| --- | --- | --- | --- | --- | --- | --- |
| alface | umidade do solo | 3 | +0.29 | [+0.05; +0.56] | 0.017 | 0.305 |
| brocolo | dias com chuva ≥ 1 mm | 0 | -0.23 | [-0.34; -0.13] | 0.006 | 0.198 |
| couve | umidade do solo | 16 | +0.21 | [+0.03; +0.36] | 0.412 | 0.816 |
| couve-flor | chuva da semana (mm) | 9 | +0.24 | [-0.01; +0.45] | 0.006 | 0.198 |
| repolho | umidade do solo | 6 | +0.44 | [+0.11; +0.65] | 0.107 | 0.590 |

## Granger (clima → preço): 0 de 70 significativos após correção

| Produto | Variável | Defasagens | p bruto | p ajustado |
| --- | --- | --- | --- | --- |
| alface | chuva da semana (mm) | 4 | 0.0001 | 0.073 |
| alface | chuva da semana (mm) | 8 | 0.0009 | 0.198 |
| brocolo | dias de geada (mín ≤ 2 °C) | 8 | 0.0042 | 0.198 |
| brocolo | temperatura máxima média | 4 | 0.0096 | 0.301 |
| repolho | chuva da semana (mm) | 8 | 0.0140 | 0.305 |
| alface | dias com chuva ≥ 1 mm | 4 | 0.0147 | 0.305 |
| couve | temperatura máxima média | 8 | 0.0295 | 0.435 |
| alface | dias com chuva ≥ 1 mm | 8 | 0.0349 | 0.446 |
| brocolo | dias de geada (mín ≤ 2 °C) | 4 | 0.0363 | 0.446 |
| repolho | dias com chuva ≥ 1 mm | 8 | 0.0440 | 0.485 |
| alface | umidade do solo | 8 | 0.0575 | 0.555 |
| couve | temperatura máxima média | 4 | 0.0597 | 0.566 |

## Estacionariedade do resíduo de preço (ADF e KPSS)

| Produto | p ADF | p KPSS | Estacionário |
| --- | --- | --- | --- |
| alface | 0.016 | 0.100 | sim |
| brocolo | 0.001 | 0.100 | sim |
| couve | 0.108 | 0.100 | não |
| couve-flor | 0.000 | 0.100 | sim |
| repolho | 0.040 | 0.100 | sim |

Correlação, IC e p de todas as combinações: CSV ao lado deste relatório.
