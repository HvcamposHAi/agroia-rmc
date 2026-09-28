# Validação autônoma do AgroIA-RMC

Sistema que, a cada execução, produz as evidências da dissertação sem intervenção humana:

- **Parte A (tese):** A1 fidelidade (portal × base: censo, campo a campo com duas leituras,
  documentos, agregados) e A2 facilitação do acesso (o mesmo agente resolve tarefas no Portal da
  Transparência e no AgroIA-RMC; H1 a H5).
- **Parte B (motores LLM):** benchmark de Claude Haiku 4.5, Llama 3.1 8B, Sabiá-4 e Gemini 2.0
  Flash pelo caminho de produção `/chat/stream`, com relatório separado.

Cada execução gera `metodologia_A`, `resultados_A`, `metodologia_B` e `resultados_B` (MD e HTML),
os dados brutos e as evidências em `validacao/execucoes/<run_id>/`.

## Configuração única (checklist)

`python -m validacao.saude.checagens` verifica cada item automaticamente.

- [ ] Perfil do Chrome dedicado `agroia-validacao`, sem contas pessoais logadas.
- [ ] Extensão **Claude in Chrome** (1.0.36 ou superior) instalada nesse perfil.
- [ ] Claude Code instalado e autenticado com `/login` (conta do plano; chave de API e token de
      `claude setup-token` não funcionam com o Chrome).
- [ ] No Claude Code: `/chrome` → **Enabled by default** → selecionar o perfil `agroia-validacao`.
- [ ] Permissões de site da extensão **somente** para `www.transparencia.curitiba.pr.gov.br`,
      `mid-transparencia.curitiba.pr.gov.br`, `celepar7.pr.gov.br` e `agroia-rmc.pages.dev`.
- [ ] Runner self-hosted em **sessão interativa** (não como serviço do Windows): `run.cmd`
      iniciado no logon, ou tarefa agendada "executar somente quando o usuário estiver conectado"
      (`scripts/setup-runner-autostart.ps1` já configura assim). Como serviço, o Chrome não abre.
- [ ] `validacao/.env` (fora do git) ou `.env` da raiz: `SUPABASE_URL`, `SUPABASE_KEY` (de
      preferência um papel somente leitura), `API_SECRET_KEY` (Parte B).
- [ ] GitHub → Settings → Secrets: `SUPABASE_URL`, `SUPABASE_KEY`, `API_SECRET_KEY`.
- [ ] Deploy do backend com os campos `motor`, `sem_cache` e `rastreio` em `/chat/stream`
      (ver `docs/API.md`), ou `b.modo_motor: switch_global` no `config.yaml`.
- [ ] `pip install -r requirements_validacao.txt` e `python -m playwright install chromium`.
- [ ] Pré-registro: conferir `preregistro/hipoteses_v1.md` e commitar `hipoteses_v1.sha256`
      antes da primeira execução completa.

## Uso

**Página de testes:** dê dois cliques em `INICIAR_VALIDACAO.bat` (raiz do repositório). Ele sobe o
servidor local e abre a página no navegador (porta 8765 ou a próxima livre; o endereço também fica
em `validacao/execucoes/_coordenacao_url.txt`). Na página: "Verificar novamente" roda as checagens,
os botões disparam as etapas, a seção Progresso mostra o andamento ao vivo e a tabela Execuções dá
acesso aos relatórios. Mantenha a janela preta aberta enquanto usar a página.

Linha de comando (equivalente):

```powershell
# tudo, do início ao fim (sem interação)
python -m validacao.run_all --etapas snapshot,a1,a2,b,relatorios

# pilotos
python -m validacao.run_all --etapas snapshot,a1,relatorios --a1-limite 10
python -m validacao.run_all --etapas a2,relatorios --reusar <RUN> --a2-piloto
python -m validacao.run_all --etapas b,relatorios --reusar <RUN> --b-piloto

# retomar uma execução interrompida (só roda o que não está concluído)
python -m validacao.run_all --retomar <RUN>

# refazer relatórios sobre um snapshot anterior, sem nova coleta
python -m validacao.relatorios.gerar --run-id <RUN>

# auditoria humana da Parte B: preencher b/auditoria.csv (coluna acerto_humano: 1/0) e rodar
python -m validacao.b_benchmark.analise --run-id <RUN> --auditoria

# página de coordenação local
python -m validacao.coordenacao.app      # http://127.0.0.1:8765

# testes offline
python -m pytest validacao/tests -q
```

Workflow agendado: `.github/workflows/validacao.yml` (domingo 01:00 BRT e disparo manual), no
mesmo grupo de concorrência da coleta, com os relatórios anexados como artefato.

## Estrutura

| Pasta | Conteúdo |
|---|---|
| `docs/` | Fase 0: `FONTE_PORTAL.md`, `ESQUEMA.md`, `API.md` |
| `preregistro/` | hipóteses, métricas, testes e exclusões, com hash SHA-256 |
| `snapshot/` | Etapa 0: cópia congelada do Supabase em Parquet, hash de conteúdo estável |
| `a1_fidelidade/` | extrator Playwright independente, extrator Claude in Chrome, censo, amostra, comparações |
| `a2_facilitacao/` | catálogo de tarefas (`tarefas/modelos.yaml`), gabaritos por SQL, executor, parser, KLM, pontuação, análise |
| `b_benchmark/` | gabaritos por SQL, execução via `/chat/stream`, pontuação determinística, análise e auditoria |
| `estatistica/` | Wilson, McNemar exato, Wilcoxon, Cliff, Fisher, Cochran Q, Friedman, Holm, κ de Cohen e de Fleiss |
| `relatorios/` | templates Jinja2 e gerador MD + HTML (figuras embutidas) |
| `saude/` | checagens de pré-requisitos |
| `coordenacao/` | FastAPI local + página única |
| `execucoes/` | saídas (fora do git) |

## Regras que o código garante

- Independência do verificador: nada em `validacao/` importa `coleta_transparencia.py` ou
  módulos de coleta; o extrator do portal foi escrito do zero sobre o DOM renderizado.
- Nenhum gabarito é digitado: todos saem de SQL (DuckDB) sobre o snapshot da execução, e os
  parâmetros da A2 só vêm de registros confirmados na A1.
- Autonomia: todo subprocesso tem tempo limite; falha de extensão, portal ou API vira desfecho
  classificado (`ERRO_INFRA_CHROME`, `TIMEOUT`, `BLOQUEADO`, `ERRO_INFRA_429`...) e a execução segue.
- Acesso ao portal: no máximo 1 requisição a cada 2 s, cache local por execução, agente de
  usuário com a identificação acadêmica e data e hora de cada captura.
