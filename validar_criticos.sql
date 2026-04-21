-- Validação: 25 Licitações com Empenhos agora têm PDFs?
-- Execute no Supabase após coleta concluir

SELECT
    l.id,
    l.processo,
    l.dt_abertura,
    l.situacao,
    COUNT(DISTINCT il.id) as qtd_itens_agro,
    COUNT(DISTINCT e.id) as qtd_empenhos,
    COUNT(DISTINCT d.id) as qtd_docs_NEW,
    CASE
        WHEN COUNT(DISTINCT d.id) > 0 THEN '✓ DOCUMENTADO'
        WHEN COUNT(DISTINCT e.id) > 0 THEN '✗ CRÍTICO - Empenhos sem docs'
        ELSE 'OK - Sem empenhos'
    END as status
FROM licitacoes l
JOIN itens_licitacao il ON l.id = il.licitacao_id AND il.relevante_agro = true
LEFT JOIN empenhos e ON e.item_id = il.id
LEFT JOIN documentos_licitacao d ON l.id = d.licitacao_id
WHERE COUNT(DISTINCT e.id) > 0  -- Apenas com empenhos
GROUP BY l.id, l.processo, l.dt_abertura, l.situacao
ORDER BY qtd_empenhos DESC
LIMIT 25;
