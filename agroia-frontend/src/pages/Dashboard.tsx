import { useEffect, useState, useMemo } from 'react'
import { useUrlState } from '../lib/useUrlState'
import { fetchItensAgro, type ItemAgro } from '../lib/itensAgro'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  Area, AreaChart, PieChart, Pie, Cell, Legend,
} from 'recharts'
import { defineMessages, useT, useI18n, fmtNum, fmtBRL } from '../i18n'

const MSG = defineMessages({
  pt: {
    carregando: 'Carregando dados...',
    filtrar: '🔎 Filtrar:',
    todosAnos: '📅 Todos os anos',
    todosCanais: '🏪 Todos os canais',
    todasCategorias: '📂 Todas as categorias',
    todasCulturas: '🌱 Todas as culturas',
    limpar: '✕ Limpar',
    nItens: '{n} itens',
    valorTotal: 'Valor Total',
    totalItens: 'Total de Itens',
    registrosFiltrados: 'registros filtrados',
    culturas: 'Culturas',
    tiposDistintos: 'tipos distintos',
    ticketMedio: 'Ticket Médio',
    porItem: 'por item licitado',
    precoMedioKg: 'Preço Médio/kg',
    kgTotal: '{n} kg total',
    canaisAtivos: 'Canais Ativos',
    canaisDistribuicao: 'canais de distribuição',
    topCulturas: '🏆 Top Culturas por Valor',
    top: 'Top {n}',
    valor: 'Valor',
    porCanal: '🏪 Por Canal',
    evolucaoMensal: '📈 Evolução Mensal — {ano}',
    evolucaoAnual: '📈 Evolução Anual da Demanda',
  },
  en: {
    carregando: 'Loading data...',
    filtrar: '🔎 Filter:',
    todosAnos: '📅 All years',
    todosCanais: '🏪 All channels',
    todasCategorias: '📂 All categories',
    todasCulturas: '🌱 All crops',
    limpar: '✕ Clear',
    nItens: '{n} items',
    valorTotal: 'Total Value',
    totalItens: 'Total Items',
    registrosFiltrados: 'filtered records',
    culturas: 'Crops',
    tiposDistintos: 'distinct types',
    ticketMedio: 'Average Ticket',
    porItem: 'per bid item',
    precoMedioKg: 'Average Price/kg',
    kgTotal: '{n} kg total',
    canaisAtivos: 'Active Channels',
    canaisDistribuicao: 'distribution channels',
    topCulturas: '🏆 Top Crops by Value',
    top: 'Top {n}',
    valor: 'Value',
    porCanal: '🏪 By Channel',
    evolucaoMensal: '📈 Monthly Trend — {ano}',
    evolucaoAnual: '📈 Annual Demand Trend',
  },
  es: {
    carregando: 'Cargando datos...',
    filtrar: '🔎 Filtrar:',
    todosAnos: '📅 Todos los años',
    todosCanais: '🏪 Todos los canales',
    todasCategorias: '📂 Todas las categorías',
    todasCulturas: '🌱 Todos los cultivos',
    limpar: '✕ Limpiar',
    nItens: '{n} ítems',
    valorTotal: 'Valor Total',
    totalItens: 'Total de Ítems',
    registrosFiltrados: 'registros filtrados',
    culturas: 'Cultivos',
    tiposDistintos: 'tipos distintos',
    ticketMedio: 'Ticket Promedio',
    porItem: 'por ítem licitado',
    precoMedioKg: 'Precio Promedio/kg',
    kgTotal: '{n} kg en total',
    canaisAtivos: 'Canales Activos',
    canaisDistribuicao: 'canales de distribución',
    topCulturas: '🏆 Top Cultivos por Valor',
    top: 'Top {n}',
    valor: 'Valor',
    porCanal: '🏪 Por Canal',
    evolucaoMensal: '📈 Evolución Mensual — {ano}',
    evolucaoAnual: '📈 Evolución Anual de la Demanda',
  },
})

const fmt = (v: number) =>
  v >= 1_000_000 ? `R$ ${(v / 1_000_000).toFixed(1)}M`
  : v >= 1_000 ? `R$ ${(v / 1_000).toFixed(0)}K`
  : `R$ ${v.toFixed(0)}`

const fmtFull = (v: number) =>
  fmtBRL(v, { maximumFractionDigits: 0 })

const CANAL_COLORS: Record<string, string> = {
  ARMAZEM_FAMILIA: '#334155',
  PNAE: '#b45309',
  PAA: '#1e3a5f',
  BANCO_ALIMENTOS: '#78716c',
}
const DEFAULT_COLOR = '#64748b'

export default function Dashboard({ items }: { items?: ItemAgro[] } = {}) {
  // Quando `items` é fornecido (uso embutido na Demanda), reutiliza o dataset e não busca.
  const t = useT(MSG)
  const { locale } = useI18n()
  const [fetched, setFetched] = useState<ItemAgro[]>([])
  const raw = items ?? fetched
  const [loading, setLoading] = useState(!items)
  const [filAno, setFilAno] = useUrlState('ano', 'todos')
  const [filCanal, setFilCanal] = useUrlState('canal', 'todos')
  const [filCategoria, setFilCategoria] = useUrlState('categoria', 'todas')
  const [filCultura, setFilCultura] = useUrlState('cultura', 'todas')
  const [topNRaw, setTopN] = useUrlState('top', '10')
  const topN = Number(topNRaw) || 10

  useEffect(() => {
    if (items) return   // dataset veio por prop; não busca
    fetchItensAgro()
      .then(setFetched)
      .finally(() => setLoading(false))
  }, [items])

  const anos = useMemo(() =>
    [...new Set(raw.map(r => r.dt_abertura?.slice(0, 4)).filter(Boolean))].sort(), [raw])
  const canais = useMemo(() =>
    [...new Set(raw.map(r => r.canal).filter(Boolean))].sort(), [raw])
  const categorias = useMemo(() =>
    [...new Set(raw.map(r => r.categoria_v2).filter(Boolean))].sort(), [raw])
  const culturas = useMemo(() => {
    let filtered = raw
    if (filCategoria !== 'todas') filtered = filtered.filter(r => r.categoria_v2 === filCategoria)
    return [...new Set(filtered.map(r => r.cultura).filter(Boolean))].sort()
  }, [raw, filCategoria])

  const filtered = useMemo(() => raw.filter(r => {
    if (filAno !== 'todos' && r.dt_abertura?.slice(0, 4) !== filAno) return false
    if (filCanal !== 'todos' && r.canal !== filCanal) return false
    if (filCategoria !== 'todas' && r.categoria_v2 !== filCategoria) return false
    if (filCultura !== 'todas' && r.cultura !== filCultura) return false
    return true
  }), [raw, filAno, filCanal, filCategoria, filCultura])

  const valorTotal = useMemo(() => filtered.reduce((s, r) => s + (r.valor_total ?? 0), 0), [filtered])
  const totalItens = filtered.length
  const totalCulturas = useMemo(() => new Set(filtered.map(r => r.cultura).filter(Boolean)).size, [filtered])
  const ticketMedio = totalItens > 0 ? valorTotal / totalItens : 0
  const qtTotal = useMemo(() => filtered.reduce((s, r) => s + (r.qt_solicitada ?? 0), 0), [filtered])
  const precoMedioKg = qtTotal > 0 ? valorTotal / qtTotal : 0

  const topCulturas = useMemo(() => {
    const m: Record<string, number> = {}
    filtered.forEach(r => { if (r.cultura) m[r.cultura] = (m[r.cultura] ?? 0) + (r.valor_total ?? 0) })
    return Object.entries(m).map(([cultura, total]) => ({ cultura, total }))
      .sort((a, b) => b.total - a.total).slice(0, topN)
  }, [filtered, topN])

  const evolucao = useMemo(() => {
    const m: Record<string, number> = {}
    filtered.forEach(r => {
      const ano = r.dt_abertura?.slice(0, 4)
      if (ano) m[ano] = (m[ano] ?? 0) + (r.valor_total ?? 0)
    })
    return Object.entries(m).sort(([a], [b]) => a.localeCompare(b)).map(([ano, total]) => ({ ano, total }))
  }, [filtered])

  const porCanal = useMemo(() => {
    const m: Record<string, number> = {}
    filtered.forEach(r => { if (r.canal) m[r.canal] = (m[r.canal] ?? 0) + (r.valor_total ?? 0) })
    return Object.entries(m).map(([canal, total]) => ({ canal, total })).sort((a, b) => b.total - a.total)
  }, [filtered])

  const evolucaoMensal = useMemo(() => {
    if (filAno === 'todos') return []
    const m: Record<string, number> = {}
    filtered.forEach(r => {
      const mes = r.dt_abertura?.slice(0, 7)
      if (mes) m[mes] = (m[mes] ?? 0) + (r.valor_total ?? 0)
    })
    return Object.entries(m).sort(([a], [b]) => a.localeCompare(b))
      .map(([mes, total]) => ({ mes: mes.slice(5) + '/' + mes.slice(2, 4), total }))
  }, [filtered, filAno])

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
      <div className="filters-bar" style={{ marginBottom: 20 }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--texto-suave)', whiteSpace: 'nowrap' }}>{t('filtrar')}</span>
        <select className="filter-select" value={filAno} onChange={e => setFilAno(e.target.value)}>
          <option value="todos">{t('todosAnos')}</option>
          {anos.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
        <select className="filter-select" value={filCanal} onChange={e => setFilCanal(e.target.value)}>
          <option value="todos">{t('todosCanais')}</option>
          {canais.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select className="filter-select" value={filCategoria} onChange={e => { setFilCategoria(e.target.value); setFilCultura('todas') }}>
          <option value="todas">{t('todasCategorias')}</option>
          {categorias.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select className="filter-select" value={filCultura} onChange={e => setFilCultura(e.target.value)}>
          <option value="todas">{t('todasCulturas')}</option>
          {culturas.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        {(filAno !== 'todos' || filCanal !== 'todos' || filCategoria !== 'todas' || filCultura !== 'todas') && (
          <button onClick={() => { setFilAno('todos'); setFilCanal('todos'); setFilCategoria('todas'); setFilCultura('todas') }}
            style={{ background: 'var(--terra-claro)', border: '1px solid #d6d3d1', borderRadius: 8, padding: '8px 14px', fontFamily: 'Inter', fontSize: 13, fontWeight: 700, color: 'var(--terra)', cursor: 'pointer' }}>
            {t('limpar')}
          </button>
        )}
        <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--texto-suave)', fontWeight: 600 }}>
          {t('nItens', { n: fmtNum(totalItens) })}
        </span>
      </div>

      <div className="metrics-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))' }}>
        <div className="metric-card verde">
          <span className="metric-icon">💰</span>
          <div className="metric-label">{t('valorTotal')}</div>
          <div className="metric-value">{fmt(valorTotal)}</div>
          <div className="metric-sub">{fmtFull(valorTotal)}</div>
        </div>
        <div className="metric-card amarelo">
          <span className="metric-icon">📦</span>
          <div className="metric-label">{t('totalItens')}</div>
          <div className="metric-value">{fmtNum(totalItens)}</div>
          <div className="metric-sub">{t('registrosFiltrados')}</div>
        </div>
        <div className="metric-card ceu">
          <span className="metric-icon">🌱</span>
          <div className="metric-label">{t('culturas')}</div>
          <div className="metric-value">{totalCulturas}</div>
          <div className="metric-sub">{t('tiposDistintos')}</div>
        </div>
        <div className="metric-card terra">
          <span className="metric-icon">🎟️</span>
          <div className="metric-label">{t('ticketMedio')}</div>
          <div className="metric-value" style={{ fontSize: 20 }}>{fmt(ticketMedio)}</div>
          <div className="metric-sub">{t('porItem')}</div>
        </div>
        <div className="metric-card verde">
          <span className="metric-icon">⚖️</span>
          <div className="metric-label">{t('precoMedioKg')}</div>
          <div className="metric-value" style={{ fontSize: 20 }}>{precoMedioKg > 0 ? fmtBRL(precoMedioKg, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}</div>
          <div className="metric-sub">{t('kgTotal', { n: qtTotal.toLocaleString(locale) })}</div>
        </div>
        <div className="metric-card amarelo">
          <span className="metric-icon">🏪</span>
          <div className="metric-label">{t('canaisAtivos')}</div>
          <div className="metric-value">{porCanal.length}</div>
          <div className="metric-sub">{t('canaisDistribuicao')}</div>
        </div>
      </div>

      <div className="grid-main-side" style={{ marginBottom: 20 }}>
        <div className="chart-card" style={{ margin: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <h3 style={{ margin: 0 }}>{t('topCulturas')}</h3>
            <select className="filter-select" style={{ fontSize: 12, padding: '5px 10px' }} value={topN} onChange={e => setTopN(e.target.value)}>
              <option value={5}>{t('top', { n: 5 })}</option>
              <option value={10}>{t('top', { n: 10 })}</option>
              <option value={20}>{t('top', { n: 20 })}</option>
            </select>
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={topCulturas} margin={{ top: 4, right: 8, left: 8, bottom: 70 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e8e2d8" />
              <XAxis dataKey="cultura" tick={{ fontSize: 10, fill: '#64748b', fontFamily: 'Inter' }} angle={-40} textAnchor="end" interval={0} />
              <YAxis tickFormatter={v => fmt(v)} tick={{ fontSize: 10, fill: '#64748b', fontFamily: 'Inter' }} />
              <Tooltip formatter={(v) => [fmt(Number(v ?? 0)), t('valor')]} contentStyle={{ fontFamily: 'Inter', fontSize: 12, borderRadius: 10, border: '1px solid #e2e8f0' }} />
              <Bar dataKey="total" fill="#334155" radius={[5, 5, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card" style={{ margin: 0 }}>
          <h3>{t('porCanal')}</h3>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={porCanal} dataKey="total" nameKey="canal" cx="50%" cy="43%" outerRadius={85}
                label={({ percent }) => `${((percent ?? 0) * 100).toFixed(0)}%`} labelLine={false}>
                {porCanal.map((entry) => (
                  <Cell key={entry.canal} fill={CANAL_COLORS[entry.canal] ?? DEFAULT_COLOR} />
                ))}
              </Pie>
              <Tooltip formatter={(v) => [fmt(Number(v ?? 0)), t('valor')]} contentStyle={{ fontFamily: 'Inter', fontSize: 12, borderRadius: 10 }} />
              <Legend formatter={(v) => <span style={{ fontSize: 11, fontFamily: 'Inter' }}>{v}</span>} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="chart-card">
        <h3>{filAno !== 'todos' ? t('evolucaoMensal', { ano: filAno }) : t('evolucaoAnual')}</h3>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={(filAno !== 'todos' ? evolucaoMensal : evolucao) as any[]} margin={{ top: 4, right: 8, left: 8, bottom: 4 }}>
            <defs>
              <linearGradient id="gradVerde" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#334155" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#334155" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#e8e2d8" />
            <XAxis dataKey={filAno !== 'todos' ? 'mes' : 'ano'} tick={{ fontSize: 11, fill: '#64748b', fontFamily: 'Inter' }} />
            <YAxis tickFormatter={v => fmt(v)} tick={{ fontSize: 10, fill: '#64748b', fontFamily: 'Inter' }} />
            <Tooltip formatter={(v) => [fmt(Number(v ?? 0)), t('valor')]} contentStyle={{ fontFamily: 'Inter', fontSize: 12, borderRadius: 10, border: '1px solid #e2e8f0' }} />
            <Area type="monotone" dataKey="total" stroke="#334155" strokeWidth={2.5} fill="url(#gradVerde)" dot={{ fill: '#334155', r: 3 }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
