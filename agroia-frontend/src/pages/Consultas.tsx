import { useEffect, useState, useMemo } from 'react'
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
type SortKey = 'dt_abertura' | 'valor_total' | 'qt_solicitada' | 'descricao'
type SortDir = 'asc' | 'desc'

export default function Consultas() {
  const [items, setItems] = useState<Item[]>([])
  const [loading, setLoading] = useState(true)
  const [busca, setBusca] = useState('')
  const [filCultura, setFilCultura] = useState('')
  const [filCanal, setFilCanal] = useState('')
  const [filAno, setFilAno] = useState('')
  const [valorMin, setValorMin] = useState('')
  const [valorMax, setValorMax] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('dt_abertura')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [page, setPage] = useState(1)
  const [showFilters, setShowFilters] = useState(false)

  useEffect(() => {
    async function load() {
      try {
        const { data } = await supabase
          .from('vw_itens_agro')
          .select('*')
          .order('dt_abertura', { ascending: false })
          .limit(1000)
        if (data) setItems(data as Item[])
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const culturas = useMemo(() =>
    [...new Set(items.map(i => i.cultura).filter(Boolean))].sort(), [items])
  const canais = useMemo(() =>
    [...new Set(items.map(i => i.canal).filter(Boolean))].sort(), [items])
  const anos = useMemo(() =>
    [...new Set(items.map(i => i.dt_abertura?.slice(0, 4)).filter(Boolean))].sort().reverse(), [items])

  const filtered = useMemo(() => {
    let f = items
    if (busca) {
      const q = busca.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      f = f.filter(i => {
        const desc = (i.descricao ?? '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        const proc = (i.processo ?? '').toLowerCase()
        const cult = (i.cultura ?? '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        return desc.includes(q) || proc.includes(q) || cult.includes(q)
      })
    }
    if (filCultura) f = f.filter(i => i.cultura === filCultura)
    if (filCanal) f = f.filter(i => i.canal === filCanal)
    if (filAno) f = f.filter(i => i.dt_abertura?.slice(0, 4) === filAno)
    if (valorMin) f = f.filter(i => (i.valor_total ?? 0) >= Number(valorMin))
    if (valorMax) f = f.filter(i => (i.valor_total ?? 0) <= Number(valorMax))
    return [...f].sort((a, b) => {
      const av = a[sortKey] ?? ''
      const bv = b[sortKey] ?? ''
      const cmp = String(av).localeCompare(String(bv), 'pt-BR', { numeric: true })
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [items, busca, filCultura, filCanal, filAno, valorMin, valorMax, sortKey, sortDir])

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const pageItems = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const hasFilters = busca || filCultura || filCanal || filAno || valorMin || valorMax

  const clearFilters = () => {
    setBusca(''); setFilCultura(''); setFilCanal('')
    setFilAno(''); setValorMin(''); setValorMax(''); setPage(1)
  }

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
    setPage(1)
  }

  const sortIcon = (key: SortKey) =>
    sortKey !== key
      ? <span style={{ color: 'var(--borda)', fontSize: 10 }}>↕</span>
      : <span style={{ color: 'var(--verde)', fontSize: 10 }}>{sortDir === 'asc' ? '↑' : '↓'}</span>

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
      <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 16, padding: '16px 20px', marginBottom: 12 }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 200, display: 'flex', alignItems: 'center', gap: 8, background: 'var(--cinza-claro)', border: '1.5px solid var(--borda)', borderRadius: 10, padding: '8px 14px' }}>
            <span style={{ fontSize: 16 }}>🔍</span>
            <input
              style={{ flex: 1, border: 'none', background: 'transparent', fontFamily: 'Nunito', fontSize: 14, color: 'var(--texto)', outline: 'none' }}
              placeholder="Buscar por descrição, processo ou cultura..."
              value={busca}
              onChange={e => { setBusca(e.target.value); setPage(1) }}
            />
            {busca && <button onClick={() => setBusca('')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--cinza)', fontSize: 16 }}>×</button>}
          </div>
          <button onClick={() => setShowFilters(v => !v)}
            style={{ background: showFilters ? 'var(--verde-fundo)' : 'var(--cinza-claro)', border: `1.5px solid ${showFilters ? 'var(--verde)' : 'var(--borda)'}`, borderRadius: 10, padding: '9px 16px', fontFamily: 'Nunito', fontSize: 13, fontWeight: 700, color: showFilters ? 'var(--verde)' : 'var(--texto)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap' }}>
            ⚙️ Filtros{hasFilters ? ` (${[busca,filCultura,filCanal,filAno,valorMin,valorMax].filter(Boolean).length})` : ''}
          </button>
          {hasFilters && (
            <button onClick={clearFilters}
              style={{ background: 'var(--terra-claro)', border: '1px solid #e0c9bc', borderRadius: 10, padding: '9px 14px', fontFamily: 'Nunito', fontSize: 13, fontWeight: 700, color: 'var(--terra)', cursor: 'pointer' }}>
              ✕ Limpar
            </button>
          )}
          <span style={{ fontSize: 13, color: 'var(--texto-suave)', fontWeight: 600, whiteSpace: 'nowrap', marginLeft: 'auto' }}>
            {filtered.length.toLocaleString('pt-BR')} resultados
          </span>
        </div>

        {showFilters && (
          <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid var(--borda)', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 10 }}>
            {[
              { label: '🌱 CULTURA', value: filCultura, set: setFilCultura, opts: culturas },
              { label: '🏪 CANAL', value: filCanal, set: setFilCanal, opts: canais },
              { label: '📅 ANO', value: filAno, set: setFilAno, opts: anos },
            ].map(({ label, value, set, opts }) => (
              <div key={label}>
                <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--texto-suave)', display: 'block', marginBottom: 4 }}>{label}</label>
                <select className="filter-select" style={{ width: '100%' }} value={value}
                  onChange={e => { set(e.target.value); setPage(1) }}>
                  <option value="">Todos</option>
                  {opts.map(o => <option key={o} value={o}>{o}</option>)}
                </select>
              </div>
            ))}
            <div>
              <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--texto-suave)', display: 'block', marginBottom: 4 }}>💰 VALOR MÍN</label>
              <input type="number" className="search-input" style={{ width: '100%' }} placeholder="Ex: 10000"
                value={valorMin} onChange={e => { setValorMin(e.target.value); setPage(1) }} />
            </div>
            <div>
              <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--texto-suave)', display: 'block', marginBottom: 4 }}>💰 VALOR MÁX</label>
              <input type="number" className="search-input" style={{ width: '100%' }} placeholder="Ex: 500000"
                value={valorMax} onChange={e => { setValorMax(e.target.value); setPage(1) }} />
            </div>
          </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <span style={{ fontSize: 12, color: 'var(--texto-suave)', fontWeight: 700 }}>Ordenar:</span>
        {([['dt_abertura', '📅 Data'], ['valor_total', '💰 Valor'], ['qt_solicitada', '⚖️ Qtd'], ['descricao', '🔤 Nome']] as [SortKey, string][]).map(([key, label]) => (
          <button key={key} onClick={() => toggleSort(key)}
            style={{ background: sortKey === key ? 'var(--verde-fundo)' : 'var(--branco)', border: `1px solid ${sortKey === key ? 'var(--verde)' : 'var(--borda)'}`, borderRadius: 8, padding: '5px 12px', fontFamily: 'Nunito', fontSize: 12, fontWeight: 700, color: sortKey === key ? 'var(--verde)' : 'var(--texto-suave)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
            {label} {sortIcon(key)}
          </button>
        ))}
      </div>

      {pageItems.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '60px 24px', color: 'var(--texto-suave)' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>🔍</div>
          <p style={{ fontWeight: 700, fontSize: 16 }}>Nenhum item encontrado</p>
          <p style={{ fontSize: 14, marginTop: 6 }}>Tente ajustar os filtros</p>
        </div>
      ) : pageItems.map(item => (
        <div key={item.id} className="item-card">
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
              {item.cultura && <span className="item-cultura-badge">{item.cultura}</span>}
              {item.canal && (
                <span style={{ background: 'var(--ceu-claro)', color: 'var(--ceu)', fontSize: 11, fontWeight: 700, padding: '3px 9px', borderRadius: 7, border: '1px solid #b3d9f5', whiteSpace: 'nowrap' }}>
                  {item.canal}
                </span>
              )}
              {item.dt_abertura && (
                <span style={{ fontSize: 11, color: 'var(--texto-suave)', marginLeft: 'auto' }}>
                  📅 {new Date(item.dt_abertura).toLocaleDateString('pt-BR')}
                </span>
              )}
            </div>
            <div className="item-title">{item.descricao ?? '—'}</div>
            <div className="item-meta" style={{ marginTop: 6 }}>
              {item.processo && <span style={{ background: 'var(--cinza-claro)', padding: '2px 8px', borderRadius: 6, fontSize: 11 }}>📋 {item.processo}</span>}
              {item.qt_solicitada > 0 && <span>⚖️ {item.qt_solicitada.toLocaleString('pt-BR')} kg</span>}
              {item.qt_solicitada > 0 && item.valor_total > 0 && (
                <span style={{ color: 'var(--verde)', fontWeight: 700 }}>≈ R$ {(item.valor_total / item.qt_solicitada).toFixed(2)}/kg</span>
              )}
            </div>
          </div>
          {item.valor_total > 0 && <div className="item-valor">{fmt(item.valor_total)}</div>}
        </div>
      ))}

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
