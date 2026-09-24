---
title: AgroIA RMC API
emoji: 🌾
colorFrom: green
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
---

# AgroIA-RMC — API

Backend do **AgroIA-RMC**, plataforma que coordena a oferta da agricultura
familiar com a demanda institucional pública de alimentos na Região
Metropolitana de Curitiba.

Projeto de dissertação do Mestrado em Computação Aplicada — PPGCA/UEPG.

O código-fonte completo fica em
https://github.com/HvcamposHAi/agroia-rmc — esta branch existe apenas para
hospedar a API aqui.

## Endpoints principais

| Rota | O que faz |
|---|---|
| `GET /health` | Verifica a conexão com o banco |
| `POST /chat` | Pergunta ao assistente sobre licitações agrícolas |
| `POST /chat/stream` | O mesmo, em streaming |

As rotas exigem o cabeçalho `X-API-Key`.

## Variáveis necessárias

Configuradas em **Settings → Variables and secrets**:

`SUPABASE_URL`, `SUPABASE_KEY`, `ANTHROPIC_API_KEY`, `API_SECRET_KEY`,
`ALLOWED_ORIGINS`

## Escopo dos dados

Licitações da SMSAN/FAAC (Curitiba), 2019–2026, filtradas para agricultura
(`relevante_af = true`).
