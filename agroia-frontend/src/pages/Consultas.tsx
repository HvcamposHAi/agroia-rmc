import { useEffect, useState } from 'react'
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL ?? '',
  import.meta.env.VITE_SUPABASE_ANON_KEY ?? ''
)

interface Item {
  id: number
  processo: string
  descricao: string
  cultura: string
  canal: string
  valor_total: number
  dt_abertura: string
  qt_solicitada: number
}

const fmt = (v: number) =>
  v?.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }) ?? '—'

const PAGE_SIZE = 20

export default function Consultas() {
  const [items, setItems] = useState<Item[]>([])
  const [filtered, setFiltered] = useState<Item[]>([])
  const [culturas, setCulturas] = useState<string[]>([])
  const [canais, setCanais] = useState<string[]>([])
  const [busca, setBusca] = useState('')
  const [filCultura, setFilCultura] = useState('')
  const [filCanal, setFilCanal] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      const { data } = await supabase
        .from('vw_itens_agro')
        .select('*')
        .order('dt_abertura', { ascending: false })
        .limit(500)

      if (data) {
        setItems(data)
        setFiltered(data)
        setCulturas([...new Set(data.map((d: Item) => d.cultura).filter(Boolean))].sort())
        setCanais([...new Set(data.map((d: Item) => d.canal).filter(Boolean))].sort())
      }
      setLoading(false)
    }
    load()
  }, [])

  useEffect(() => {
    let f = items
    if (busca) f = f.filter(i => i.descricao?.toLowerCase().includes(busca.toLowerCase()))
    if (filCultura) f = f.filter(i => i.cultura === filCultura)
    if (filCanal) f = f.filter(i => i.canal === filCanal)
    setFiltered(f)
    setPage(1)
  }, [busca, filCultura, filCanal, items])

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const pageItems = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  if (loading) return (
    <div className="page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 300 }}>
      <div style={{ textAlign: 'center' }}>
        <span className="spinner" style={{ width: 36, height: 36, borderWidth: 3 }} />
        <p style={{ marginTop: 16, color: 'var(--texto-suave)', fontWeight: 600 }}>Carregando licitações...</p>
      </div>
    </div>
  )

  return (
    <div className="page">
      <div className="filters-bar">
        <input
          className="search-input"
          placeholder="🔍  Buscar por descrição..."
          value={busca}
          onChange={e => setBusca(e.target.value)}
        />
        <select className="filter-select" value={filCultura} onChange={e => setFilCultura(e.target.value)}>
          <option value="">🌱 Todas as culturas</option>
          {culturas.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select className="filter-select" value={filCanal} onChange={e => setFilCanal(e.target.value)}>
          <option value="">🏪 Todos os canais</option>
          {canais.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <span style={{ fontSize: 13, color: 'var(--texto-suave)', fontWeight: 600, whiteSpace: 'nowrap' }}>
          {filtered.length.toLocaleString('pt-BR')} resultados
        </span>
      </div>

      {pageItems.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '60px 24px', color: 'var(--texto-suave)' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>🔍</div>
          <p style={{ fontWeight: 700, fontSize: 16 }}>Nenhum item encontrado</p>
          <p style={{ fontSize: 14, marginTop: 6 }}>Tente ajustar os filtros de busca</p>
        </div>
      ) : (
        pageItems.map(item => (
          <div key={item.id} className="item-card">
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6, flexWrap: 'wrap' }}>
                {item.cultura && <span className="item-cultura-badge">{item.cultura}</span>}
                {item.canal && (
                  <span style={{ background: 'var(--ceu-claro)', color: 'var(--ceu)', fontSize: 12, fontWeight: 700, padding: '4px 10px', borderRadius: 8, border: '1px solid #b3d9f5' }}>
                    {item.canal}
                  </span>
                )}
              </div>
              <div className="item-title">{item.descricao ?? '—'}</div>
              <div className="item-meta">
                {item.processo && <span>📋 {item.processo}</span>}
                {item.dt_abertura && <span>📅 {new Date(item.dt_abertura).toLocaleDateString('pt-BR')}</span>}
                {item.qt_solicitada && <span>⚖️ {item.qt_solicitada.toLocaleString('pt-BR')} kg</span>}
              </div>
            </div>
            {item.valor_total > 0 && (
              <div className="item-valor">{fmt(item.valor_total)}</div>
            )}
          </div>
        ))
      )}

      {totalPages > 1 && (
        <div className="pagination">
          <button className="page-btn" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>‹</button>
          {Array.from({ length: Math.min(7, totalPages) }, (_, i) => {
            const p = Math.max(1, Math.min(page - 3, totalPages - 6)) + i
            return (
              <button key={p} className={`page-btn${page === p ? ' active' : ''}`} onClick={() => setPage(p)}>
                {p}
              </button>
            )
          })}
          <button className="page-btn" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}>›</button>
        </div>
      )}
    </div>
  )
}
