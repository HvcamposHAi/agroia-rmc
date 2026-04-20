import { useEffect, useState, useMemo } from 'react'
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL ?? '',
  import.meta.env.VITE_SUPABASE_ANON_KEY ?? ''
)

interface Documento {
  id: number
  licitacao_id: number
  nome_arquivo: string
  nome_doc: string
  url_publica: string
  tamanho_bytes: number
  coletado_em: string
}

interface Licitacao {
  id: number
  numero_processo: string
  objeto: string
  dt_abertura: string
  situacao: string
}

const fmtBytes = (b: number) =>
  b > 1_000_000 ? `${(b / 1_000_000).toFixed(1)} MB`
  : b > 1_000 ? `${(b / 1_000).toFixed(0)} KB`
  : `${b} B`

const PAGE_SIZE = 15

export default function Documentos() {
  const [docs, setDocs] = useState<Documento[]>([])
  const [lics, setLics] = useState<Record<number, Licitacao>>({})
  const [loading, setLoading] = useState(true)
  const [busca, setBusca] = useState('')
  const [pdfAberto, setPdfAberto] = useState<Documento | null>(null)
  const [page, setPage] = useState(1)

  useEffect(() => {
    async function load() {
      try {
        const { data: docsData } = await supabase
          .from('documentos_licitacao')
          .select('*')
          .not('url_publica', 'is', null)
          .order('coletado_em', { ascending: false })
          .limit(500)

        if (!docsData) return
        setDocs(docsData as Documento[])

        // Busca licitações únicas referenciadas
        const ids = [...new Set(docsData.map((d: Documento) => d.licitacao_id))]
        if (ids.length > 0) {
          const { data: licsData } = await supabase
            .from('licitacoes')
            .select('id, numero_processo, objeto, dt_abertura, situacao')
            .in('id', ids.slice(0, 100))

          if (licsData) {
            const map: Record<number, Licitacao> = {}
            licsData.forEach((l: Licitacao) => { map[l.id] = l })
            setLics(map)
          }
        }
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const filtered = useMemo(() => {
    if (!busca) return docs
    const q = busca.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    return docs.filter(d => {
      const nome = (d.nome_doc ?? d.nome_arquivo ?? '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      const lic = lics[d.licitacao_id]
      const obj = (lic?.objeto ?? '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      const proc = (lic?.numero_processo ?? '').toLowerCase()
      return nome.includes(q) || obj.includes(q) || proc.includes(q)
    })
  }, [docs, busca, lics])

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const pageItems = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  if (loading) return (
    <div className="page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 300 }}>
      <div style={{ textAlign: 'center' }}>
        <span className="spinner" style={{ width: 36, height: 36, borderWidth: 3 }} />
        <p style={{ marginTop: 16, color: 'var(--texto-suave)', fontWeight: 600 }}>Carregando documentos...</p>
      </div>
    </div>
  )

  return (
    <div className="page" style={{ position: 'relative' }}>

      {/* ── Modal PDF ── */}
      {pdfAberto && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 1000, display: 'flex', flexDirection: 'column' }}>
          <div style={{ background: 'var(--branco)', padding: '12px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--borda)', flexShrink: 0 }}>
            <div>
              <div style={{ fontFamily: 'Fraunces, serif', fontWeight: 700, fontSize: 16, color: 'var(--texto)' }}>
                📄 {pdfAberto.nome_doc || pdfAberto.nome_arquivo}
              </div>
              {lics[pdfAberto.licitacao_id] && (
                <div style={{ fontSize: 12, color: 'var(--texto-suave)', marginTop: 2 }}>
                  {lics[pdfAberto.licitacao_id].numero_processo} — {lics[pdfAberto.licitacao_id].objeto?.slice(0, 80)}...
                </div>
              )}
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <a
                href={pdfAberto.url_publica}
                target="_blank"
                rel="noopener noreferrer"
                style={{ background: 'var(--verde)', color: '#fff', border: 'none', borderRadius: 8, padding: '8px 16px', fontFamily: 'Nunito', fontSize: 13, fontWeight: 700, cursor: 'pointer', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 6 }}
              >
                ⬇️ Baixar
              </a>
              <button
                onClick={() => setPdfAberto(null)}
                style={{ background: 'var(--cinza-claro)', border: '1px solid var(--borda)', borderRadius: 8, padding: '8px 16px', fontFamily: 'Nunito', fontSize: 13, fontWeight: 700, cursor: 'pointer', color: 'var(--texto)' }}
              >
                ✕ Fechar
              </button>
            </div>
          </div>
          <iframe
            src={pdfAberto.url_publica}
            style={{ flex: 1, border: 'none', width: '100%', background: '#525659' }}
            title={pdfAberto.nome_doc}
          />
        </div>
      )}

      {/* ── Header + busca ── */}
      <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 16, padding: '16px 20px', marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 200, display: 'flex', alignItems: 'center', gap: 8, background: 'var(--cinza-claro)', border: '1.5px solid var(--borda)', borderRadius: 10, padding: '8px 14px' }}>
            <span>🔍</span>
            <input
              style={{ flex: 1, border: 'none', background: 'transparent', fontFamily: 'Nunito', fontSize: 14, color: 'var(--texto)', outline: 'none' }}
              placeholder="Buscar por nome do documento, processo ou objeto..."
              value={busca}
              onChange={e => { setBusca(e.target.value); setPage(1) }}
            />
            {busca && <button onClick={() => setBusca('')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--cinza)', fontSize: 16 }}>×</button>}
          </div>
          <span style={{ fontSize: 13, color: 'var(--texto-suave)', fontWeight: 600, whiteSpace: 'nowrap' }}>
            {filtered.length.toLocaleString('pt-BR')} documentos
          </span>
        </div>
      </div>

      {/* ── Lista de documentos ── */}
      {pageItems.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '60px 24px', color: 'var(--texto-suave)' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>📂</div>
          <p style={{ fontWeight: 700, fontSize: 16 }}>Nenhum documento encontrado</p>
        </div>
      ) : pageItems.map(doc => {
        const lic = lics[doc.licitacao_id]
        return (
          <div key={doc.id} className="item-card" style={{ cursor: 'pointer' }}
            onClick={() => setPdfAberto(doc)}>
            <div style={{ width: 44, height: 44, background: '#fef2f2', borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, flexShrink: 0 }}>
              📄
            </div>
            <div style={{ flex: 1 }}>
              <div className="item-title">{doc.nome_doc || doc.nome_arquivo}</div>
              {lic && (
                <div style={{ fontSize: 12, color: 'var(--texto-suave)', marginTop: 4, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                  <span style={{ background: 'var(--cinza-claro)', padding: '2px 8px', borderRadius: 6 }}>📋 {lic.numero_processo}</span>
                  {lic.dt_abertura && <span>📅 {new Date(lic.dt_abertura).toLocaleDateString('pt-BR')}</span>}
                  {lic.situacao && (
                    <span style={{ background: lic.situacao.toLowerCase().includes('vencedor') ? 'var(--verde-fundo)' : 'var(--cinza-claro)', color: lic.situacao.toLowerCase().includes('vencedor') ? 'var(--verde)' : 'var(--texto-suave)', padding: '2px 8px', borderRadius: 6 }}>
                      {lic.situacao}
                    </span>
                  )}
                </div>
              )}
              {lic?.objeto && (
                <div style={{ fontSize: 12, color: 'var(--texto-suave)', marginTop: 4, lineHeight: 1.4 }}>
                  {lic.objeto.slice(0, 120)}{lic.objeto.length > 120 ? '...' : ''}
                </div>
              )}
            </div>
            <div style={{ textAlign: 'right', flexShrink: 0 }}>
              {doc.tamanho_bytes > 0 && (
                <div style={{ fontSize: 12, color: 'var(--texto-suave)', fontWeight: 600 }}>{fmtBytes(doc.tamanho_bytes)}</div>
              )}
              <div style={{ marginTop: 8, background: 'var(--verde-fundo)', color: 'var(--verde)', fontSize: 11, fontWeight: 700, padding: '4px 10px', borderRadius: 7, border: '1px solid #b8dfc0', whiteSpace: 'nowrap' }}>
                👁️ Visualizar
              </div>
            </div>
          </div>
        )
      })}

      {/* ── Paginação ── */}
      {totalPages > 1 && (
        <div className="pagination">
          <button className="page-btn" onClick={() => setPage(1)} disabled={page === 1}>«</button>
          <button className="page-btn" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>‹</button>
          {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
            const start = Math.max(1, Math.min(page - 2, totalPages - 4))
            const p = start + i
            return <button key={p} className={`page-btn${page === p ? ' active' : ''}`} onClick={() => setPage(p)}>{p}</button>
          })}
          <button className="page-btn" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}>›</button>
          <button className="page-btn" onClick={() => setPage(totalPages)} disabled={page === totalPages}>»</button>
        </div>
      )}
    </div>
  )
}
