# Clima × preço — análise preliminar (PROHORT Curitiba)

Gerado em 2026-10-16. Preços de 2022-06-01 a 2026-10-15, deflacionados pelo IPCA, em log, sem tendência e sazonalidade (STL). Clima: média simples de 5 pontos do cinturão verde da RMC (NASA POWER), em anomalia contra 1991–2020. **Escopo provisório:** sem ponderação por procedência (P8/P9).

Testes: 595 correlações (produto × variável × defasagem 0–16 semanas) e 70 testes de Granger, todos corrigidos juntos por Benjamini-Hochberg. Correlação é associação, não causa.

## Resultado: 18 associações sobrevivem à correção para múltiplos testes

| Produto | Variável | Defasagem (semanas) | r | IC 95% | p ajustado |
| --- | --- | --- | --- | --- | --- |
| alface | chuva da semana (mm) | 3 | +0.23 | [+0.04; +0.43] | 0.033 |
| alface | chuva da semana (mm) | 4 | +0.23 | [+0.04; +0.40] | 0.033 |
| alface | chuva da semana (mm) | 5 | +0.23 | [-0.02; +0.41] | 0.033 |
| alface | temperatura mínima média | 10 | +0.18 | [+0.04; +0.31] | 0.033 |
| alface | temperatura mínima média | 11 | +0.21 | [+0.07; +0.33] | 0.033 |
| alface | temperatura mínima média | 13 | +0.19 | [+0.06; +0.30] | 0.033 |
| brocolo | dias com chuva ≥ 1 mm | 0 | -0.22 | [-0.33; -0.11] | 0.033 |
| couve-flor | chuva da semana (mm) | 8 | +0.19 | [-0.03; +0.37] | 0.033 |
| couve-flor | chuva da semana (mm) | 9 | +0.25 | [+0.00; +0.46] | 0.033 |
| couve-flor | chuva da semana (mm) | 10 | +0.24 | [+0.04; +0.40] | 0.033 |
| repolho | chuva da semana (mm) | 7 | +0.20 | [-0.02; +0.36] | 0.033 |
| repolho | chuva da semana (mm) | 8 | +0.21 | [+0.01; +0.37] | 0.033 |
| repolho | chuva da semana (mm) | 9 | +0.22 | [+0.01; +0.39] | 0.033 |
| repolho | chuva da semana (mm) | 10 | +0.23 | [+0.02; +0.39] | 0.033 |
| repolho | chuva da semana (mm) | 11 | +0.22 | [-0.01; +0.40] | 0.033 |
| repolho | chuva da semana (mm) | 12 | +0.20 | [-0.02; +0.39] | 0.033 |
| repolho | chuva da semana (mm) | 13 | +0.21 | [+0.03; +0.37] | 0.033 |
| repolho | chuva da semana (mm) | 14 | +0.19 | [+0.03; +0.32] | 0.033 |

## Maior associação por produto (antes da correção)

| Produto | Variável | Defasagem | r | IC 95% | p bruto | p ajustado |
| --- | --- | --- | --- | --- | --- | --- |
| alface | umidade do solo | 3 | +0.26 | [+0.05; +0.55] | 0.028 | 0.372 |
| brocolo | dias com chuva ≥ 1 mm | 0 | -0.22 | [-0.33; -0.11] | 0.001 | 0.033 |
| couve | umidade do solo | 7 | +0.20 | [-0.03; +0.44] | 0.443 | 0.754 |
| couve-flor | chuva da semana (mm) | 9 | +0.25 | [+0.00; +0.46] | 0.001 | 0.033 |
| repolho | umidade do solo | 6 | +0.45 | [+0.13; +0.66] | 0.020 | 0.302 |

## Granger (clima → preço): 2 de 70 significativos após correção

| Produto | Variável | Defasagens | p bruto | p ajustado |
| --- | --- | --- | --- | --- |
| alface | chuva da semana (mm) | 4 | 0.0001 | 0.033 |
| alface | chuva da semana (mm) | 8 | 0.0009 | 0.033 |
| brocolo | dias de geada (mín ≤ 2 °C) | 8 | 0.0031 | 0.098 |
| brocolo | temperatura máxima média | 4 | 0.0087 | 0.206 |
| repolho | chuva da semana (mm) | 8 | 0.0102 | 0.218 |
| repolho | dias com chuva ≥ 1 mm | 8 | 0.0173 | 0.287 |
| alface | dias com chuva ≥ 1 mm | 4 | 0.0187 | 0.301 |
| couve | temperatura máxima média | 8 | 0.0291 | 0.372 |
| alface | dias com chuva ≥ 1 mm | 8 | 0.0363 | 0.397 |
| brocolo | dias de geada (mín ≤ 2 °C) | 4 | 0.0376 | 0.397 |
| couve | temperatura máxima média | 4 | 0.0549 | 0.471 |
| couve-flor | chuva da semana (mm) | 8 | 0.0622 | 0.481 |

## Estacionariedade do resíduo de preço (ADF e KPSS)

| Produto | p ADF | p KPSS | Estacionário |
| --- | --- | --- | --- |
| alface | 0.016 | 0.100 | sim |
| brocolo | 0.001 | 0.100 | sim |
| couve | 0.108 | 0.100 | não |
| couve-flor | 0.000 | 0.100 | sim |
| repolho | 0.040 | 0.100 | sim |

Correlação, IC e p de todas as combinações: CSV ao lado deste relatório.
