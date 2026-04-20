import { useEffect, useState, useMemo } from 'react'
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL ?? '',
  import.meta.env.VITE_SUPABASE_ANON_KEY ?? ''
)

interface DocComLic {
  id: number
  licitacao_id: number
  nome_arquivo: string
  nome_doc: string
  url_publica: string
  tamanho_bytes: number
  coletado_em: string
  processo: string
  modalidade: string  // tipo_processo
  objeto: string
  dt_abertura: string
  situacao: string
  canal: string
}

const toEmbedUrl = (url: string): string => {
  const matchView = url.match(/drive\.google\.com\/file\/d\/([^/]+)\//)
  if (matchView) return `https://drive.google.com/file/d/${matchView[1]}/preview`
  const matchUc = url.match(/drive\.google\.com\/uc\?id=([^&]+)/)
  if (matchUc) return `https://drive.google.com/file/d/${matchUc[1]}/preview`
  return url
}

const toDownloadUrl = (url: string): string => {
  const matchView = url.match(/drive\.google\.com\/file\/d\/([^/]+)\//)
  if (matchView) return `https://drive.google.com/uc?id=${matchView[1]}&export=download`
  return url
}

const fmtBytes = (b: number) =>
  b > 1_000_000 ? `${(b / 1_000_000).toFixed(1)} MB`
  : b > 1_000 ? `${(b / 1_000).toFixed(0)} KB`
  : `${b} B`

const PAGE_SIZE = 15

export default function Documentos() {
  const [docs, setDocs] = useState<DocComLic[]>([])
  const [loading, setLoading] = useState(true)
  const [pdfAberto, setPdfAberto] = useState<DocComLic | null>(null)

  // Filtros
  const [busca, setBusca] = useState('')
  const [filAno, setFilAno] = useState('')
  const [filMes, setFilMes] = useState('')
  const [filModalidade, setFilModalidade] = useState('')
  const [filSituacao, setFilSituacao] = useState('')
  const [filCanal, setFilCanal] = useState('')
  const [showFilters, setShowFilters] = useState(false)
  const [page, setPage] = useState(1)

  useEffect(() => {
    async function load() {
      try {
        const { data } = await supabase
          .from('documentos_licitacao')
          .select(`
            id, licitacao_id, nome_arquivo, nome_doc,
            url_publica, tamanho_bytes, coletado_em,
            licitacoes (
              processo, tipo_processo, objeto,
              dt_abertura, situacao, canal
            )
          `)
          .order('coletado_em', { ascending: false })
          .limit(500)

        if (data) {
          const flat = data.map((d: any) => ({
            ...d,
            processo: d.licitacoes?.processo ?? '',
            modalidade: d.licitacoes?.tipo_processo ?? '',
            objeto: d.licitacoes?.objeto ?? '',
            dt_abertura: d.licitacoes?.dt_abertura ?? '',
            situacao: d.licitacoes?.situacao ?? '',
            canal: d.licitacoes?.canal ?? '',
          }))
          setDocs(flat)
        }
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const anos = useMemo(() =>
    [...new Set(docs.map(d => d.dt_abertura?.slice(0, 4)).filter(Boolean))].sort().reverse(), [docs])
  const modalidades = useMemo(() =>
    [...new Set(docs.map(d => d.modalidade).filter(Boolean))].sort(), [docs])
  const situacoes = useMemo(() =>
    [...new Set(docs.map(d => d.situacao).filter(Boolean))].sort(), [docs])
  const canais = useMemo(() =>
    [...new Set(docs.map(d => d.canal).filter(Boolean))].sort(), [docs])

  const MESES = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']

  const filtered = useMemo(() => {
    let f = docs
    if (busca) {
      const q = busca.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      f = f.filter(d => {
        const nome = (d.nome_doc ?? d.nome_arquivo ?? '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        const obj = (d.objeto ?? '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        const proc = (d.processo ?? '').toLowerCase()
        return nome.includes(q) || obj.includes(q) || proc.includes(q)
      })
    }
    if (filAno) f = f.filter(d => d.dt_abertura?.slice(0, 4) === filAno)
    if (filMes) f = f.filter(d => d.dt_abertura?.slice(5, 7) === filMes)
    if (filModalidade) f = f.filter(d => d.modalidade === filModalidade)
    if (filSituacao) f = f.filter(d => d.situacao === filSituacao)
    if (filCanal) f = f.filter(d => d.canal === filCanal)
    return f
  }, [docs, busca, filAno, filMes, filModalidade, filSituacao, filCanal])

  const hasFilters = busca || filAno || filMes || filModalidade || filSituacao || filCanal
  const clearFilters = () => {
    setBusca(''); setFilAno(''); setFilMes('')
    setFilModalidade(''); setFilSituacao(''); setFilCanal(''); setPage(1)
  }

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const pageItems = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  const situacaoCor = (s: string) => {
    if (!s) return { bg: 'var(--cinza-claro)', cor: 'var(--texto-suave)' }
    const sl = s.toLowerCase()
    if (sl.includes('vencedor') || sl.includes('empenhado')) return { bg: 'var(--verde-fundo)', cor: 'var(--verde)' }
    if (sl.includes('fracassado') || sl.includes('cancelado')) return { bg: '#fef2f2', cor: '#b91c1c' }
    return { bg: 'var(--amarelo-claro)', cor: '#b45309' }
  }

  if (loading) return (
    <div className="page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 300 }}>
      <div style={{ textAlign: 'center' }}>
        <span className="spinner" style={{ width: 36, height: 36, borderWidth: 3 }} />
        <p style={{ marginTop: 16, color: 'var(--texto-suave)', fontWeight: 600 }}>Carregando documentos...</p>
      </div>
    </div>
  )

  return (
    <div className="page">

      {/* ── Modal PDF ── */}
      {pdfAberto && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', zIndex: 1000, display: 'flex', flexDirection: 'column' }}>
          <div style={{ background: 'var(--branco)', padding: '14px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--borda)', flexShrink: 0, gap: 16 }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontFamily: 'Fraunces, serif', fontWeight: 700, fontSize: 16, color: 'var(--texto)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                📄 {pdfAberto.nome_doc || pdfAberto.nome_arquivo}
              </div>
              <div style={{ fontSize: 12, color: 'var(--texto-suave)', marginTop: 3, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                {pdfAberto.processo && <span>📋 {pdfAberto.processo}</span>}
                {pdfAberto.dt_abertura && <span>📅 {new Date(pdfAberto.dt_abertura).toLocaleDateString('pt-BR')}</span>}
                {pdfAberto.modalidade && <span>🏷️ {pdfAberto.modalidade}</span>}
              </div>
              {pdfAberto.objeto && (
                <div style={{ fontSize: 12, color: 'var(--texto-suave)', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {pdfAberto.objeto.slice(0, 100)}...
                </div>
              )}
            </div>
            <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
              <a href={toDownloadUrl(pdfAberto.url_publica)} target="_blank" rel="noopener noreferrer"
                style={{ background: 'var(--verde)', color: '#fff', border: 'none', borderRadius: 8, padding: '8px 14px', fontFamily: 'Nunito', fontSize: 13, fontWeight: 700, cursor: 'pointer', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 6 }}>
                ⬇️ Baixar
              </a>
              <button onClick={() => setPdfAberto(null)}
                style={{ background: 'var(--cinza-claro)', border: '1px solid var(--borda)', borderRadius: 8, padding: '8px 14px', fontFamily: 'Nunito', fontSize: 13, fontWeight: 700, cursor: 'pointer', color: 'var(--texto)' }}>
                ✕ Fechar
              </button>
            </div>
          </div>
          <iframe src={toEmbedUrl(pdfAberto.url_publica)}
            style={{ flex: 1, border: 'none', width: '100%', background: '#525659' }}
            title={pdfAberto.nome_doc} />
        </div>
      )}

      {/* ── Barra de busca + filtros ── */}
      <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 16, padding: '16px 20px', marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 200, display: 'flex', alignItems: 'center', gap: 8, background: 'var(--cinza-claro)', border: '1.5px solid var(--borda)', borderRadius: 10, padding: '8px 14px' }}>
            <span>🔍</span>
            <input
              style={{ flex: 1, border: 'none', background: 'transparent', fontFamily: 'Nunito', fontSize: 14, color: 'var(--texto)', outline: 'none' }}
              placeholder="Buscar por nome, processo ou objeto..."
              value={busca}
              onChange={e => { setBusca(e.target.value); setPage(1) }}
            />
            {busca && <button onClick={() => setBusca('')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--cinza)', fontSize: 16 }}>×</button>}
          </div>
          <button onClick={() => setShowFilters(v => !v)}
            style={{ background: showFilters ? 'var(--verde-fundo)' : 'var(--cinza-claro)', border: `1.5px solid ${showFilters ? 'var(--verde)' : 'var(--borda)'}`, borderRadius: 10, padding: '9px 16px', fontFamily: 'Nunito', fontSize: 13, fontWeight: 700, color: showFilters ? 'var(--verde)' : 'var(--texto)', cursor: 'pointer', whiteSpace: 'nowrap' }}>
            ⚙️ Filtros{hasFilters ? ` (${[filAno,filMes,filModalidade,filSituacao,filCanal].filter(Boolean).length})` : ''}
          </button>
          {hasFilters && (
            <button onClick={clearFilters}
              style={{ background: 'var(--terra-claro)', border: '1px solid #e0c9bc', borderRadius: 10, padding: '9px 14px', fontFamily: 'Nunito', fontSize: 13, fontWeight: 700, color: 'var(--terra)', cursor: 'pointer' }}>
              ✕ Limpar
            </button>
          )}
          <span style={{ fontSize: 13, color: 'var(--texto-suave)', fontWeight: 600, marginLeft: 'auto', whiteSpace: 'nowrap' }}>
            {filtered.length} documentos
          </span>
        </div>

        {showFilters && (
          <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid var(--borda)', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 10 }}>
            <div>
              <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--texto-suave)', display: 'block', marginBottom: 4 }}>📅 ANO</label>
              <select className="filter-select" style={{ width: '100%' }} value={filAno} onChange={e => { setFilAno(e.target.value); setPage(1) }}>
                <option value="">Todos</option>
                {anos.map(a => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>
            <div>
              <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--texto-suave)', display: 'block', marginBottom: 4 }}>📆 MÊS</label>
              <select className="filter-select" style={{ width: '100%' }} value={filMes} onChange={e => { setFilMes(e.target.value); setPage(1) }}>
                <option value="">Todos</option>
                {MESES.map((m, i) => <option key={i} value={String(i + 1).padStart(2, '0')}>{m}</option>)}
              </select>
            </div>
            <div>
              <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--texto-suave)', display: 'block', marginBottom: 4 }}>🏷️ MODALIDADE</label>
              <select className="filter-select" style={{ width: '100%' }} value={filModalidade} onChange={e => { setFilModalidade(e.target.value); setPage(1) }}>
                <option value="">Todas</option>
                {modalidades.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <div>
              <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--texto-suave)', display: 'block', marginBottom: 4 }}>✅ SITUAÇÃO</label>
              <select className="filter-select" style={{ width: '100%' }} value={filSituacao} onChange={e => { setFilSituacao(e.target.value); setPage(1) }}>
                <option value="">Todas</option>
                {situacoes.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--texto-suave)', display: 'block', marginBottom: 4 }}>🏪 CANAL</label>
              <select className="filter-select" style={{ width: '100%' }} value={filCanal} onChange={e => { setFilCanal(e.target.value); setPage(1) }}>
                <option value="">Todos</option>
                {canais.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
          </div>
        )}
      </div>

      {/* ── Lista ── */}
      {pageItems.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '60px 24px', color: 'var(--texto-suave)' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>📂</div>
          <p style={{ fontWeight: 700, fontSize: 16 }}>Nenhum documento encontrado</p>
          <p style={{ fontSize: 14, marginTop: 6 }}>Tente ajustar os filtros</p>
        </div>
      ) : pageItems.map(doc => {
        const sc = situacaoCor(doc.situacao)
        return (
          <div key={doc.id} className="item-card" style={{ cursor: 'pointer', alignItems: 'flex-start' }}
            onClick={() => setPdfAberto(doc)}>
            <div style={{ width: 44, height: 44, background: '#fef2f2', borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, flexShrink: 0 }}>
              📄
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="item-title" style={{ marginBottom: 6 }}>{doc.nome_doc || doc.nome_arquivo}</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 6 }}>
                {doc.processo && (
                  <span style={{ background: 'var(--cinza-claro)', padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700 }}>
                    📋 {doc.processo}
                  </span>
                )}
                {doc.dt_abertura && (
                  <span style={{ fontSize: 11, color: 'var(--texto-suave)' }}>
                    📅 {new Date(doc.dt_abertura).toLocaleDateString('pt-BR')}
                  </span>
                )}
                {doc.modalidade && (
                  <span style={{ background: 'var(--ceu-claro)', color: 'var(--ceu)', fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 6, border: '1px solid #b3d9f5' }}>
                    {doc.modalidade}
                  </span>
                )}
                {doc.situacao && (
                  <span style={{ background: sc.bg, color: sc.cor, fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 6 }}>
                    {doc.situacao}
                  </span>
                )}
              </div>
              {doc.objeto && (
                <div style={{ fontSize: 12, color: 'var(--texto-suave)', lineHeight: 1.4 }}>
                  {doc.objeto.slice(0, 130)}{doc.objeto.length > 130 ? '...' : ''}
                </div>
              )}
            </div>
            <div style={{ textAlign: 'right', flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
              {doc.tamanho_bytes > 0 && (
                <span style={{ fontSize: 11, color: 'var(--texto-suave)', fontWeight: 600 }}>{fmtBytes(doc.tamanho_bytes)}</span>
              )}
              <span style={{ background: 'var(--verde-fundo)', color: 'var(--verde)', fontSize: 11, fontWeight: 700, padding: '4px 10px', borderRadius: 7, border: '1px solid #b8dfc0', whiteSpace: 'nowrap' }}>
                👁️ Visualizar
              </span>
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
