# Viabilidade da projeção — PROHORT CURITIBA

Gerado em 2026-10-16. Origem móvel nas últimas 52 semanas; MASE < 1 = melhor que o ingênuo sazonal. Regra v3: MASE < 1 e p < 0,05 contra o ingênuo sazonal. Regra nova (16/10/2026): além disso, p < 0,05 contra o ingênuo simples (último preço). p = Diebold-Mariano unilateral.

## Horizonte de 1 semana(s) — 47 séries

| Modelo | MASE mediano | Séries com MASE < 1 | Publicáveis, regra v3 | Publicáveis, regra nova |
| --- | --- | --- | --- | --- |
| ingenuo | 0.19 | 47 | — | — |
| ingenuo_sazonal | 0.87 | 31 | — | — |
| ets | 0.19 | 47 | 46 | 0 |
| gbm_global | 0.26 | 47 | 45 | 0 |

## Horizonte de 4 semana(s) — 47 séries

| Modelo | MASE mediano | Séries com MASE < 1 | Publicáveis, regra v3 | Publicáveis, regra nova |
| --- | --- | --- | --- | --- |
| ingenuo | 0.57 | 40 | — | — |
| ingenuo_sazonal | 0.90 | 33 | — | — |
| ets | 0.58 | 39 | 15 | 0 |
| gbm_global | 0.61 | 42 | 14 | 1 |

## Horizonte de 8 semana(s) — 47 séries

| Modelo | MASE mediano | Séries com MASE < 1 | Publicáveis, regra v3 | Publicáveis, regra nova |
| --- | --- | --- | --- | --- |
| ingenuo | 0.73 | 31 | — | — |
| ingenuo_sazonal | 0.89 | 30 | — | — |
| ets | 0.72 | 31 | 5 | 1 |
| gbm_global | 0.78 | 32 | 5 | 1 |

## Por produto (horizonte de 4 semanas)

| Produto | MASE ing. sazonal | MASE ingênuo | MASE ETS | MASE GBM | p GBM × sazonal | p GBM × ingênuo |
| --- | --- | --- | --- | --- | --- | --- |
| mandioquinha | 0.99 | 0.05 | 0.05 | 0.07 | 0.006 | 0.986 |
| laranja | 1.30 | 0.07 | 0.07 | 0.24 | 0.000 | 1.000 |
| abacaxi | 0.38 | 0.14 | 0.14 | 0.24 | 0.084 | 0.998 |
| inhame | 1.18 | 0.30 | 0.30 | 0.29 | 0.002 | 0.362 |
| cara | 0.86 | 0.19 | 0.19 | 0.31 | 0.010 | 0.924 |
| cebola | 0.60 | 0.29 | 0.29 | 0.31 | 0.028 | 0.752 |
| coco verde | 0.59 | 0.28 | 0.28 | 0.38 | 0.228 | 0.885 |
| beterraba | 0.64 | 0.27 | 0.27 | 0.38 | 0.055 | 0.946 |
| abobora | 0.73 | 0.27 | 0.28 | 0.40 | 0.068 | 0.920 |
| maçã | 0.84 | 0.37 | 0.37 | 0.40 | 0.008 | 0.684 |
| repolho | 0.75 | 0.43 | 0.43 | 0.46 | 0.080 | 0.712 |
| alface | 0.77 | 0.45 | 0.45 | 0.47 | 0.016 | 0.616 |
| melao amarelo | 0.91 | 0.47 | 0.47 | 0.48 | 0.135 | 0.540 |
| batata | 0.66 | 0.46 | 0.47 | 0.48 | 0.069 | 0.782 |
| manga | 0.95 | 0.62 | 0.62 | 0.48 | 0.028 | 0.048 |
| tangerina | 0.90 | 0.35 | 0.35 | 0.50 | 0.143 | 0.977 |
| cenoura | 0.99 | 0.44 | 0.44 | 0.50 | 0.014 | 0.735 |
| couve | 0.78 | 0.51 | 0.51 | 0.51 | 0.022 | 0.521 |
| banana | 0.53 | 0.43 | 0.43 | 0.52 | 0.496 | 0.950 |
| uva italia | 0.90 | 0.51 | 0.51 | 0.55 | 0.096 | 0.675 |
| mamao formosa | 0.76 | 0.56 | 0.56 | 0.57 | 0.070 | 0.566 |
| uva rubi | 0.81 | 0.53 | 0.53 | 0.58 | 0.173 | 0.709 |
| ovos | 1.05 | 0.55 | 0.55 | 0.59 | 0.000 | 0.708 |
| alho | 2.02 | 0.41 | 0.42 | 0.61 | 0.000 | 0.940 |
| abacate | 1.07 | 0.61 | 0.61 | 0.66 | 0.124 | 0.671 |
| goiaba | 0.73 | 0.74 | 0.74 | 0.72 | 0.488 | 0.409 |
| mamao haway | 0.63 | 0.78 | 0.78 | 0.73 | 0.773 | 0.083 |
| feijão vagem | 0.90 | 0.96 | 0.91 | 0.74 | 0.107 | 0.016 |
| milho verde | 0.49 | 0.70 | 0.70 | 0.75 | 0.821 | 0.772 |
| brocolo | 0.65 | 0.57 | 0.58 | 0.75 | 0.765 | 0.976 |
| melancia | 0.93 | 0.80 | 0.80 | 0.77 | 0.214 | 0.391 |
| batata doce | 1.57 | 0.69 | 0.69 | 0.78 | 0.000 | 0.719 |
| couve-flor | 0.82 | 0.74 | 0.74 | 0.79 | 0.436 | 0.730 |
| maracuja azedo | 0.67 | 0.90 | 0.90 | 0.83 | 0.830 | 0.026 |
| jilo | 1.15 | 0.78 | 0.78 | 0.86 | 0.154 | 0.822 |
| pepino | 1.23 | 0.87 | 0.87 | 0.87 | 0.057 | 0.456 |
| uva niagara | 0.98 | 1.01 | 1.01 | 0.88 | 0.391 | 0.050 |
| pera importada | 1.93 | 1.02 | 1.02 | 0.94 | 0.007 | 0.279 |
| tomate | 0.83 | 0.99 | 1.00 | 0.95 | 0.771 | 0.302 |
| quiabo | 0.80 | 1.08 | 1.08 | 0.98 | 0.980 | 0.202 |
| mandioca | 0.94 | 0.70 | 0.70 | 0.98 | 0.541 | 0.997 |
| limao tahiti | 1.19 | 0.89 | 0.89 | 1.00 | 0.250 | 0.915 |
| pimentão | 1.04 | 0.92 | 0.92 | 1.01 | 0.480 | 0.744 |
| abobrinha | 1.22 | 1.16 | 1.14 | 1.09 | 0.148 | 0.320 |
| morango | 0.91 | 1.03 | 1.03 | 1.19 | 0.982 | 0.861 |
| berinjela | 1.42 | 1.25 | 1.25 | 1.26 | 0.348 | 0.537 |
| chuchu | 1.26 | 1.61 | 1.63 | 1.39 | 0.707 | 0.079 |
