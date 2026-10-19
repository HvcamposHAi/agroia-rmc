# Viabilidade da projeção — PROHORT CURITIBA

Gerado em 2026-10-19. Origem móvel nas últimas 52 semanas; MASE < 1 = melhor que o ingênuo sazonal. Regra v3: MASE < 1 e p < 0,05 contra o ingênuo sazonal. Regra nova (16/10/2026, com o ganho mínimo da auditoria de 17/10): além disso, p < 0,05 contra o ingênuo simples (último preço) e redução de MAE ≥ 2% sobre os dois ingênuos. p = Diebold-Mariano unilateral. São 47 séries × 2 modelos × 3 horizontes = 282 testes sem correção para múltiplos testes: alguns 'publicáveis' são esperados por acaso.

## Horizonte de 1 semana(s) — 47 séries

| Modelo | MASE mediano | Séries com MASE < 1 | Publicáveis, regra v3 | Publicáveis, regra nova |
| --- | --- | --- | --- | --- |
| ingenuo | 0.19 | 47 | — | — |
| ingenuo_sazonal | 0.88 | 32 | — | — |
| ets | 0.19 | 47 | 46 | 0 |
| gbm_global | 0.26 | 47 | 45 | 0 |

## Horizonte de 4 semana(s) — 47 séries

| Modelo | MASE mediano | Séries com MASE < 1 | Publicáveis, regra v3 | Publicáveis, regra nova |
| --- | --- | --- | --- | --- |
| ingenuo | 0.56 | 41 | — | — |
| ingenuo_sazonal | 0.89 | 33 | — | — |
| ets | 0.57 | 41 | 16 | 0 |
| gbm_global | 0.62 | 42 | 15 | 0 |

## Horizonte de 8 semana(s) — 47 séries

| Modelo | MASE mediano | Séries com MASE < 1 | Publicáveis, regra v3 | Publicáveis, regra nova |
| --- | --- | --- | --- | --- |
| ingenuo | 0.73 | 30 | — | — |
| ingenuo_sazonal | 0.91 | 31 | — | — |
| ets | 0.73 | 30 | 5 | 0 |
| gbm_global | 0.79 | 32 | 6 | 1 |

## Por produto (horizonte de 4 semanas)

| Produto | MASE ing. sazonal | MASE ingênuo | MASE ETS | MASE GBM | p GBM × sazonal | p GBM × ingênuo |
| --- | --- | --- | --- | --- | --- | --- |
| mandioquinha | 0.98 | 0.05 | 0.05 | 0.07 | 0.005 | 0.976 |
| laranja | 1.29 | 0.07 | 0.07 | 0.23 | 0.000 | 1.000 |
| abacaxi | 0.37 | 0.14 | 0.14 | 0.23 | 0.082 | 0.998 |
| cara | 0.86 | 0.19 | 0.19 | 0.28 | 0.006 | 0.879 |
| inhame | 1.18 | 0.30 | 0.30 | 0.29 | 0.002 | 0.403 |
| cebola | 0.60 | 0.29 | 0.29 | 0.32 | 0.031 | 0.830 |
| beterraba | 0.63 | 0.27 | 0.27 | 0.36 | 0.046 | 0.910 |
| abobora | 0.74 | 0.27 | 0.28 | 0.40 | 0.057 | 0.929 |
| coco verde | 0.58 | 0.27 | 0.27 | 0.41 | 0.277 | 0.962 |
| maçã | 0.83 | 0.36 | 0.37 | 0.41 | 0.012 | 0.785 |
| alface | 0.76 | 0.45 | 0.45 | 0.45 | 0.016 | 0.557 |
| repolho | 0.77 | 0.44 | 0.44 | 0.47 | 0.075 | 0.684 |
| batata | 0.67 | 0.47 | 0.47 | 0.48 | 0.054 | 0.637 |
| melao amarelo | 0.89 | 0.46 | 0.46 | 0.48 | 0.137 | 0.569 |
| tangerina | 0.87 | 0.34 | 0.34 | 0.48 | 0.128 | 0.972 |
| manga | 0.93 | 0.61 | 0.61 | 0.49 | 0.032 | 0.067 |
| banana | 0.52 | 0.43 | 0.43 | 0.51 | 0.489 | 0.938 |
| couve | 0.78 | 0.51 | 0.51 | 0.52 | 0.015 | 0.501 |
| uva italia | 0.89 | 0.51 | 0.51 | 0.53 | 0.084 | 0.623 |
| cenoura | 0.99 | 0.44 | 0.44 | 0.54 | 0.013 | 0.827 |
| uva rubi | 0.80 | 0.53 | 0.53 | 0.56 | 0.159 | 0.667 |
| ovos | 1.03 | 0.54 | 0.54 | 0.58 | 0.000 | 0.756 |
| mamao formosa | 0.77 | 0.56 | 0.56 | 0.58 | 0.080 | 0.639 |
| alho | 1.99 | 0.41 | 0.41 | 0.62 | 0.000 | 0.946 |
| abacate | 1.06 | 0.60 | 0.60 | 0.63 | 0.099 | 0.616 |
| goiaba | 0.73 | 0.74 | 0.74 | 0.72 | 0.481 | 0.398 |
| brocolo | 0.65 | 0.56 | 0.57 | 0.74 | 0.757 | 0.974 |
| mamao haway | 0.64 | 0.79 | 0.79 | 0.74 | 0.769 | 0.082 |
| feijão vagem | 0.93 | 0.99 | 0.94 | 0.75 | 0.089 | 0.017 |
| batata doce | 1.57 | 0.69 | 0.69 | 0.77 | 0.000 | 0.702 |
| couve-flor | 0.83 | 0.75 | 0.74 | 0.79 | 0.400 | 0.685 |
| milho verde | 0.52 | 0.73 | 0.73 | 0.81 | 0.843 | 0.831 |
| melancia | 0.98 | 0.84 | 0.84 | 0.84 | 0.264 | 0.498 |
| jilo | 1.13 | 0.77 | 0.77 | 0.85 | 0.147 | 0.803 |
| pera importada | 1.90 | 1.00 | 1.00 | 0.88 | 0.007 | 0.217 |
| pepino | 1.25 | 0.89 | 0.89 | 0.89 | 0.059 | 0.522 |
| uva niagara | 0.97 | 1.01 | 1.01 | 0.89 | 0.413 | 0.066 |
| maracuja azedo | 0.70 | 0.94 | 0.94 | 0.92 | 0.879 | 0.253 |
| mandioca | 0.94 | 0.70 | 0.70 | 0.94 | 0.509 | 0.999 |
| tomate | 0.82 | 0.98 | 0.99 | 0.97 | 0.814 | 0.405 |
| pimentão | 1.00 | 0.89 | 0.89 | 0.97 | 0.478 | 0.745 |
| limao tahiti | 1.17 | 0.87 | 0.87 | 0.99 | 0.265 | 0.933 |
| quiabo | 0.81 | 1.10 | 1.10 | 1.00 | 0.980 | 0.207 |
| abobrinha | 1.22 | 1.16 | 1.14 | 1.11 | 0.194 | 0.374 |
| morango | 0.91 | 1.04 | 1.04 | 1.25 | 0.982 | 0.890 |
| berinjela | 1.45 | 1.28 | 1.28 | 1.25 | 0.314 | 0.439 |
| chuchu | 1.26 | 1.61 | 1.63 | 1.37 | 0.696 | 0.098 |
