-- AgroIA-RMC — Etapa 3: Tabela de índice de documentos
-- Execute no Supabase SQL Editor antes de rodar etapa3_documentos.py

CREATE TABLE IF NOT EXISTS documentos_licitacao (
    id              bigserial PRIMARY KEY,
    licitacao_id    bigint NOT NULL REFERENCES licitacoes(id) ON DELETE CASCADE,
    nome_arquivo    text NOT NULL,          -- nome real do arquivo (ex: edital.pdf)
    nome_doc        text,                   -- label exibido no portal (ex: "Edital")
    storage_path    text,                   -- caminho no bucket: {licitacao_id}/{nome_arquivo}
    url_publica     text,                   -- URL pública gerada pelo Supabase Storage
    tamanho_bytes   bigint,
    coletado_em     timestamptz DEFAULT now(),
    erro            text,                   -- preenchido se o download/upload falhou
    UNIQUE (licitacao_id, nome_arquivo)
);

-- Índice para consultas por licitação
CREATE INDEX IF NOT EXISTS idx_documentos_licitacao_id
    ON documentos_licitacao (licitacao_id);

-- Índice para filtrar erros
CREATE INDEX IF NOT EXISTS idx_documentos_erro
    ON documentos_licitacao (erro)
    WHERE erro IS NOT NULL;

-- ─── Criar bucket no Supabase Storage (via SQL) ──────────────────────────────
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'documentos-licitacoes',
    'documentos-licitacoes',
    true,           -- público: gera URLs permanentes sem autenticação
    52428800,       -- limite por arquivo: 50 MB
    ARRAY['application/pdf', 'application/octet-stream']
)
ON CONFLICT (id) DO NOTHING;

-- Política de leitura pública (SELECT) — qualquer um pode baixar
CREATE POLICY "Leitura pública documentos"
    ON storage.objects FOR SELECT
    USING (bucket_id = 'documentos-licitacoes');

-- Política de escrita para service_role (o script Python usa a service key)
CREATE POLICY "Upload service_role documentos"
    ON storage.objects FOR INSERT
    WITH CHECK (bucket_id = 'documentos-licitacoes');

-- Política de atualização (upsert sobrescreve arquivos existentes)
CREATE POLICY "Update service_role documentos"
    ON storage.objects FOR UPDATE
    USING (bucket_id = 'documentos-licitacoes');

-- ─── Verificação após coleta ─────────────────────────────────────────────────
-- SELECT COUNT(*) FROM documentos_licitacao;
-- SELECT COUNT(DISTINCT licitacao_id) FROM documentos_licitacao;
-- SELECT * FROM documentos_licitacao WHERE erro IS NOT NULL LIMIT 20;
