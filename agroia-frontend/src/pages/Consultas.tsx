import { useEffect, useState, useMemo } from 'react'
import { NavLink } from 'react-router-dom'
import { useUrlState } from '../lib/useUrlState'
import { fetchItensAgro, type ItemAgro as Item } from '../lib/itensAgro'
import { defineMessages, useT, useI18n, fmtNum, fmtBRL, fmtData } from '../i18n'

const MSG = defineMessages({
  pt: {
    carregando: 'Carregando licitações...',
    buscarPh: 'Buscar por descrição, processo ou cultura...',
    limparBusca: 'Limpar busca',
    filtros: '⚙️ Filtros',
    limpar: '✕ Limpar',
    resultados: '{n} resultados',
    cultura: '🌱 CULTURA',
    canal: '🏪 CANAL',
    ano: '📅 ANO',
    todos: 'Todos',
    valorMin: '💰 VALOR MÍN',
    valorMax: '💰 VALOR MÁX',
    ex: 'Ex: {n}',
    ordenar: 'Ordenar:',
    sortData: '📅 Data',
    sortValor: '💰 Valor',
    sortQtd: '⚖️ Qtd',
    sortNome: '🔤 Nome',
    nenhum: 'Nenhum item encontrado',
    ajuste: 'Tente ajustar os filtros',
    precoMercado: '💰 Preço de mercado',
    documentos: '📄 Documentos',
    quemVende: '🧺 Quem vende',
  },
  en: {
    carregando: 'Loading biddings...',
    buscarPh: 'Search by description, process or crop...',
    limparBusca: 'Clear search',
    filtros: '⚙️ Filters',
    limpar: '✕ Clear',
    resultados: '{n} results',
    cultura: '🌱 CROP',
    canal: '🏪 CHANNEL',
    ano: '📅 YEAR',
    todos: 'All',
    valorMin: '💰 MIN VALUE',
    valorMax: '💰 MAX VALUE',
    ex: 'E.g.: {n}',
    ordenar: 'Sort:',
    sortData: '📅 Date',
    sortValor: '💰 Value',
    sortQtd: '⚖️ Qty',
    sortNome: '🔤 Name',
    nenhum: 'No items found',
    ajuste: 'Try adjusting the filters',
    precoMercado: '💰 Market price',
    documentos: '📄 Documents',
    quemVende: '🧺 Who sells',
  },
  es: {
    carregando: 'Cargando licitaciones...',
    buscarPh: 'Buscar por descripción, proceso o cultivo...',
    limparBusca: 'Limpiar búsqueda',
    filtros: '⚙️ Filtros',
    limpar: '✕ Limpiar',
    resultados: '{n} resultados',
    cultura: '🌱 CULTIVO',
    canal: '🏪 CANAL',
    ano: '📅 AÑO',
    todos: 'Todos',
    valorMin: '💰 VALOR MÍN',
    valorMax: '💰 VALOR MÁX',
    ex: 'Ej.: {n}',
    ordenar: 'Ordenar:',
    sortData: '📅 Fecha',
    sortValor: '💰 Valor',
    sortQtd: '⚖️ Cant.',
    sortNome: '🔤 Nombre',
    nenhum: 'No se encontraron ítems',
    ajuste: 'Intente ajustar los filtros',
    precoMercado: '💰 Precio de mercado',
    documentos: '📄 Documentos',
    quemVende: '🧺 Quién vende',
  },
})

const fmt = (v?: number) =>
  v != null ? fmtBRL(v, { maximumFractionDigits: 0 }) : '—'

const PAGE_SIZE = 20
type SortKey = 'dt_abertura' | 'valor_total' | 'qt_solicitada' | 'descricao'
type SortDir = 'asc' | 'desc'

export default function Consultas({ dataset }: { dataset?: Item[] } = {}) {
  // Quando `dataset` é fornecido (uso embutido na Demanda), reutiliza e não busca.
  const t = useT(MSG)
  const { locale } = useI18n()
  const [fetched, setFetched] = useState<Item[]>([])
  const items = dataset ?? fetched
  const [loading, setLoading] = useState(!dataset)
  const [busca, setBusca] = useUrlState('q')
  const [filCultura, setFilCultura] = useUrlState('cultura')
  const [filCanal, setFilCanal] = useUrlState('canal')
  const [filAno, setFilAno] = useUrlState('ano')
  const [valorMin, setValorMin] = useUrlState('vmin')
  const [valorMax, setValorMax] = useUrlState('vmax')
  const [sortKeyRaw, setSortKey] = useUrlState('sort', 'dt_abertura')
  const [sortDirRaw, setSortDir] = useUrlState('dir', 'desc')
  const [pageRaw, setPageRaw] = useUrlState('page', '1')
  const [showFilters, setShowFilters] = useState(false)

  const sortKey = sortKeyRaw as SortKey
  const sortDir = sortDirRaw as SortDir
  const page = Math.max(1, parseInt(pageRaw || '1', 10) || 1)
  const setPage = (p: number) => setPageRaw(String(p))

  useEffect(() => {
    if (dataset) return   // dataset veio por prop; não busca
    fetchItensAgro()
      .then(setFetched)
      .finally(() => setLoading(false))
  }, [dataset])

  const culturas = useMemo(() =>
    [...new Set(items.map(i => i.cultura).filter(Boolean))].sort(), [items])
  const canais = useMemo(() =>
    [...new Set(items.map(i => i.canal).filter(Boolean))].sort(), [items])
  const anos = useMemo(() =>
    [...new Set(items.map(i => i.dt_abertura?.slice(0, 4)).filter(Boolean))].sort().reverse(), [items])

  const filtered = useMemo(() => {
    let f = items
    if (busca) {
      const q = busca.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
      f = f.filter(i => {
        const desc = (i.descricao ?? '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
        const proc = (i.processo ?? '').toLowerCase()
        const cult = (i.cultura ?? '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
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
      const cmp = String(av).localeCompare(String(bv), locale, { numeric: true })
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [items, busca, filCultura, filCanal, filAno, valorMin, valorMax, sortKey, sortDir, locale])

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const pageItems = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const hasFilters = busca || filCultura || filCanal || filAno || valorMin || valorMax

  const clearFilters = () => {
    setBusca(''); setFilCultura(''); setFilCanal('')
    setFilAno(''); setValorMin(''); setValorMax(''); setPage(1)
  }

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
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
        <p style={{ marginTop: 16, color: 'var(--texto-suave)', fontWeight: 600 }}>{t('carregando')}</p>
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
              style={{ flex: 1, border: 'none', background: 'transparent', fontFamily: 'Inter', fontSize: 14, color: 'var(--texto)', outline: 'none' }}
              placeholder={t('buscarPh')}
              value={busca}
              onChange={e => { setBusca(e.target.value); setPage(1) }}
            />
            {busca && <button onClick={() => setBusca('')} aria-label={t('limparBusca')} title={t('limparBusca')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--cinza)', fontSize: 16 }}>×</button>}
          </div>
          <button onClick={() => setShowFilters(v => !v)}
            style={{ background: showFilters ? 'var(--verde-fundo)' : 'var(--cinza-claro)', border: `1.5px solid ${showFilters ? 'var(--verde)' : 'var(--borda)'}`, borderRadius: 10, padding: '9px 16px', fontFamily: 'Inter', fontSize: 13, fontWeight: 700, color: showFilters ? 'var(--verde)' : 'var(--texto)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap' }}>
            {t('filtros')}{hasFilters ? ` (${[busca,filCultura,filCanal,filAno,valorMin,valorMax].filter(Boolean).length})` : ''}
          </button>
          {hasFilters && (
            <button onClick={clearFilters}
              style={{ background: 'var(--terra-claro)', border: '1px solid #d6d3d1', borderRadius: 10, padding: '9px 14px', fontFamily: 'Inter', fontSize: 13, fontWeight: 700, color: 'var(--terra)', cursor: 'pointer' }}>
              {t('limpar')}
            </button>
          )}
          <span style={{ fontSize: 13, color: 'var(--texto-suave)', fontWeight: 600, whiteSpace: 'nowrap', marginLeft: 'auto' }}>
            {t('resultados', { n: fmtNum(filtered.length) })}
          </span>
        </div>

        {showFilters && (
          <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid var(--borda)', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 10 }}>
            {[
              { key: 'cultura', label: t('cultura'), value: filCultura, set: setFilCultura, opts: culturas },
              { key: 'canal', label: t('canal'), value: filCanal, set: setFilCanal, opts: canais },
              { key: 'ano', label: t('ano'), value: filAno, set: setFilAno, opts: anos },
            ].map(({ key, label, value, set, opts }) => (
              <div key={key}>
                <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--texto-suave)', display: 'block', marginBottom: 4 }}>{label}</label>
                <select className="filter-select" style={{ width: '100%' }} value={value}
                  onChange={e => { set(e.target.value); setPage(1) }}>
                  <option value="">{t('todos')}</option>
                  {opts.map(o => <option key={o} value={o}>{o}</option>)}
                </select>
              </div>
            ))}
            <div>
              <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--texto-suave)', display: 'block', marginBottom: 4 }}>{t('valorMin')}</label>
              <input type="number" className="search-input" style={{ width: '100%' }} placeholder={t('ex', { n: 10000 })}
                value={valorMin} onChange={e => { setValorMin(e.target.value); setPage(1) }} />
            </div>
            <div>
              <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--texto-suave)', display: 'block', marginBottom: 4 }}>{t('valorMax')}</label>
              <input type="number" className="search-input" style={{ width: '100%' }} placeholder={t('ex', { n: 500000 })}
                value={valorMax} onChange={e => { setValorMax(e.target.value); setPage(1) }} />
            </div>
          </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <span style={{ fontSize: 12, color: 'var(--texto-suave)', fontWeight: 700 }}>{t('ordenar')}</span>
        {([['dt_abertura', t('sortData')], ['valor_total', t('sortValor')], ['qt_solicitada', t('sortQtd')], ['descricao', t('sortNome')]] as [SortKey, string][]).map(([key, label]) => (
          <button key={key} onClick={() => toggleSort(key)}
            style={{ background: sortKey === key ? 'var(--verde-fundo)' : 'var(--branco)', border: `1px solid ${sortKey === key ? 'var(--verde)' : 'var(--borda)'}`, borderRadius: 8, padding: '5px 12px', fontFamily: 'Inter', fontSize: 12, fontWeight: 700, color: sortKey === key ? 'var(--verde)' : 'var(--texto-suave)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
            {label} {sortIcon(key)}
          </button>
        ))}
      </div>

      {pageItems.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '60px 24px', color: 'var(--texto-suave)' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>🔍</div>
          <p style={{ fontWeight: 700, fontSize: 16 }}>{t('nenhum')}</p>
          <p style={{ fontSize: 14, marginTop: 6 }}>{t('ajuste')}</p>
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
                  📅 {fmtData(item.dt_abertura)}
                </span>
              )}
            </div>
            <div className="item-title">{item.descricao ?? '—'}</div>
            <div className="item-meta" style={{ marginTop: 6 }}>
              {item.processo && <span style={{ background: 'var(--cinza-claro)', padding: '2px 8px', borderRadius: 6, fontSize: 11 }}>📋 {item.processo}</span>}
              {(item.qt_solicitada ?? 0) > 0 && <span>⚖️ {fmtNum(item.qt_solicitada ?? 0)} kg</span>}
              {(item.qt_solicitada ?? 0) > 0 && (item.valor_total ?? 0) > 0 && (
                <span style={{ color: 'var(--verde)', fontWeight: 700 }}>≈ {fmtBRL((item.valor_total ?? 0) / (item.qt_solicitada ?? 1), { minimumFractionDigits: 2, maximumFractionDigits: 2 })}/kg</span>
              )}
            </div>
            {item.cultura && (
              <div className="item-links">
                <NavLink to={`/mercado?produto=${encodeURIComponent(item.cultura)}`}>{t('precoMercado')}</NavLink>
                {item.processo && <NavLink to={`/documentos?q=${encodeURIComponent(item.processo)}`}>{t('documentos')}</NavLink>}
                <NavLink to={`/ofertas?q=${encodeURIComponent(item.cultura)}`}>{t('quemVende')}</NavLink>
              </div>
            )}
          </div>
          {(item.valor_total ?? 0) > 0 && <div className="item-valor">{fmt(item.valor_total)}</div>}
        </div>
      ))}

      {totalPages > 1 && (
        <div className="pagination">
          <button className="page-btn" onClick={() => setPage(1)} disabled={page === 1}>«</button>
          <button className="page-btn" onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1}>‹</button>
          {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
            const start = Math.max(1, Math.min(page - 2, totalPages - 4))
            const p = start + i
            return <button key={p} className={`page-btn${page === p ? ' active' : ''}`} onClick={() => setPage(p)}>{p}</button>
          })}
          <button className="page-btn" onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page === totalPages}>›</button>
          <button className="page-btn" onClick={() => setPage(totalPages)} disabled={page === totalPages}>»</button>
        </div>
      )}
    </div>
  )
}
