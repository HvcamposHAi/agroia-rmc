# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**AgroIA-RMC** — Mestrado PPGCA/UEPG. Platform to coordinate family farming supply with public institutional demand in the Metropolitan Region of Curitiba (RMC).

Data source: JSF/RichFaces portal at `http://consultalictacao.curitiba.pr.gov.br:9090/ConsultaLicitacoes/` (requires Playwright for scraping)  
Database: Supabase (`https://rsphlvcekuomvpvjqxqm.supabase.co`)

## Data Collection Architecture

The project is organized into **three collection phases**:

### Phase 1: Bidding Processes (Licitações)
- Source: Portal search with date range and organization filter
- Organization: `SMSAN/FAAC`
- Date range: `01/01/2019` to `31/12/2026`
- Status: ✅ ~1,237 bidding processes collected

### Phase 2: Items & Participants (`etapa2_itens_v9.py`)
Extracts from bidding detail pages:
- **itens_licitacao**: 7,882 items (99.8% coverage)
  - Columns: Seq, Código, Descrição, Qt. Solicitada, UN, Valor, classification (relevante_agro, categoria_v2)
- **fornecedores**: 3,081 suppliers
- **participacoes**: 26,211 participations (supplier bids)
- **empenhos**: 3,473 commitments (36% coverage — max possible due to portal data)

Key flags:
- `FORCAR_REPROCESSAR=False`: Set True to delete existing items before recollecting (fixes corrupt data)
- `REGS_POR_PAG=5`: Rows per page in portal
- `DELAY=2.0`: Seconds between requests

Run:
```bash
python etapa2_itens_v9.py
```

### Phase 3: PDFs (`etapa3_producao.py`)
Downloads bidding documents (PDFs) from modal dialogs and saves to Supabase Storage + Google Drive.

Implementation: `expect_page()` + `expect_download()` (Playwright context manager). Earlier attempts with `requests` failed due to session validation.

Run:
```bash
python etapa3_producao.py                  # Start from beginning
python etapa3_producao.py --resume          # Continue from last checkpoint
python etapa3_producao.py --limit 100       # Collect 100 processes
```

Checkpoint: `coleta_checkpoint.json`  
Log: `coleta_producao.log`

## Portal Integration Details

### JSF/RichFaces Quirks (Critical)

**CSS Selectors with colons**: JSF generates IDs like `form:campo`, breaking standard CSS.
```python
# WRONG:  page.locator("#form:dataInferiorInputDate")
# RIGHT:  page.locator('[id="form:dataInferiorInputDate"]')
```

**Date fields**: Cannot use `page.fill()`. Requires triple-click + `keyboard.type()` + Tab (onchange event requires Tab).

**Table IDs** (on detail page):
- Items: `form:tabelaItens` (datascroller: `form:tabelaItens:j_id140`)
- Supplier participants: `form:tabelaFornecedoresParticipantes`
- Commitments: `form:tabelaEmpenhosProcCompra` (columns: Número, Ano, Data Empenho — no Value column)

**Process links** (listing page): Pattern `form:tabela:N:j_id26` where N is 0-indexed row.

**Tab navigation** (critical bug fix): "Lista Licitações" is NOT an `<a>` but a RichFaces tab `<td id="form:abaPesquisa_lbl">`. Always return to list via:
```python
page.locator('[id="form:abaPesquisa_lbl"]').click()
```

## Database Schema

Tables in Supabase:
- `licitacoes`: Bidding processes
- `itens_licitacao`: Items with agro classification
- `fornecedores`: Suppliers
- `participacoes`: Bids/participations
- `empenhos`: Commitments (spending)
- `documentos_licitacao`: Metadata + download status

Key views (SQL in `criar_views_agro.sql`):
- `vw_itens_agro`: Classified items relevant to agriculture
- `vw_demanda_agro_ano`: Yearly demand by category
- `vw_cobertura_classificacao`: Coverage metrics

## Agricultural Classification

Module: `enriquecer_classificacao.py`

Functions:
- `classificar_item(descricao)` → category (e.g., FRUTAS, HORTIFRUTI, PROTEINA_ANIMAL)
- `is_relevante_agro(descricao)` → bool

Current data: 742 items marked as `relevante_agro=True` (9.4%).

## Testing & Diagnostics

Diagnostic scripts (safe to run, do not modify database):
- `diagnostico_documentos.py`: Inspect PDF modal structure
- `diagnostico_portal.py`: Portal connectivity test
- `teste_download_correto.py`: Test PDF download flow
- `verificar_status_db.py`: Check table row counts

## Common Commands

```bash
# Test portal connection
python diagnostico_portal.py

# Check database status
python verificar_status_db.py

# Run full phase 2 collection
python etapa2_itens_v9.py

# Run full phase 3 collection
python etapa3_producao.py

# Resume interrupted collection (saves time)
python etapa3_producao.py --resume
```

## Environment Variables

Required in `.env`:
```
SUPABASE_URL=https://rsphlvcekuomvpvjqxqm.supabase.co
SUPABASE_KEY=<key>
GOOGLE_DRIVE_FOLDER_ID=<folder_id>
```

## RAG (Retrieval-Augmented Generation) Schema

For semantic search and AI-powered analysis of bidding documents:

**Table: `pdf_chunks`** — Stores text chunks from PDFs with vector embeddings (pgvector)
- Columns: `id`, `licitacao_id`, `documento_id`, `processo`, `nome_doc`, `chunk_index`, `chunk_text`, `embedding (384-dim)`, `tokens_aprox`
- Indexes: HNSW for cosine similarity, process filter
- Function: `buscar_chunks_similares(query_embedding, limite, processo_filtro)` — returns chunks ranked by similarity

Setup in Supabase SQL Editor:
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS pdf_chunks (
    id            bigserial PRIMARY KEY,
    licitacao_id  bigint NOT NULL REFERENCES licitacoes(id) ON DELETE CASCADE,
    documento_id  bigint REFERENCES documentos_licitacao(id) ON DELETE SET NULL,
    processo      text NOT NULL,
    nome_doc      text,
    chunk_index   int NOT NULL,
    chunk_text    text NOT NULL,
    embedding     vector(384),
    tokens_aprox  int,
    indexado_em   timestamptz DEFAULT now(),
    UNIQUE (documento_id, chunk_index)
);

CREATE INDEX idx_pdf_chunks_embedding ON pdf_chunks 
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_pdf_chunks_processo ON pdf_chunks (processo);
```

**Usage**: Chunk PDFs → embed text (e.g., with Sentence Transformers, 384-dim) → insert to `pdf_chunks` → query with `buscar_chunks_similares(query_vec)`.

## Known Limitations

1. **Empenhos (Commitments)**: Max 36% coverage — 664 "Concluído" biddings have no empenhos in portal (expected for Dispensas)
2. **PDF Downloads**: 716/957 licitações could not download documents; modal dialogs are dynamic and require Playwright's full context
3. **Pagination**: Handled internally — do NOT try to script pagination manually; loop over pages in portal directly

## Key Dependencies

- `playwright`: Browser automation (Chromium headless)
- `supabase`: Database client
- `beautifulsoup4`: HTML parsing
- `python-dotenv`: Environment config
- `google-api-python-client`: Google Drive integration
- `pgvector` (Supabase extension): Vector similarity search (for RAG)

- `playwright`: Browser automation (Chromium headless)
- `supabase`: Database client
- `beautifulsoup4`: HTML parsing
- `python-dotenv`: Environment config
- `google-api-python-client`: Google Drive integration
