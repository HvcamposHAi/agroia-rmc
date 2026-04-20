import { useEffect, useState, useMemo } from 'react'
import { createClient } from '@supabase/supabase-js'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  Area, AreaChart, PieChart, Pie, Cell, Legend,
} from 'recharts'

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL ?? '',
  import.meta.env.VITE_SUPABASE_ANON_KEY ?? ''
)

const fmt = (v: number) =>
  v >= 1_000_000 ? `R$ ${(v / 1_000_000).toFixed(1)}M`
  : v >= 1_000 ? `R$ ${(v / 1_000).toFixed(0)}K`
  : `R$ ${v.toFixed(0)}`

const fmtFull = (v: number) =>
  v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 })

const CANAL_COLORS: Record<string, string> = {
  ARMAZEM_FAMILIA: '#3a7d44',
  PNAE: '#f5a623',
  PAA: '#4a9eda',
  BANCO_ALIMENTOS: '#8b5e3c',
}
const DEFAULT_COLOR = '#6b7280'

interface RawItem {
  cultura: string
  canal: string
  valor_total: number
  dt_abertura: string
  qt_solicitada: number
}

export default function Dashboard() {
  const [raw, setRaw] = useState<RawItem[]>([])
  const [loading, setLoading] = useState(true)
  const [filAno, setFilAno] = useState('todos')
  const [filCanal, setFilCanal] = useState('todos')
  const [filCultura, setFilCultura] = useState('todas')
  const [topN, setTopN] = useState(10)

  useEffect(() => {
    supabase.from('vw_itens_agro')
      .select('cultura, canal, valor_total, dt_abertura, qt_solicitada')
      .then(({ data }) => { if (data) setRaw(data as RawItem[]) })
      .finally(() => setLoading(false))
  }, [])

  const anos = useMemo(() =>
    [...new Set(raw.map(r => r.dt_abertura?.slice(0, 4)).filter(Boolean))].sort(), [raw])
  const canais = useMemo(() =>
    [...new Set(raw.map(r => r.canal).filter(Boolean))].sort(), [raw])
  const culturas = useMemo(() =>
    [...new Set(raw.map(r => r.cultura).filter(Boolean))].sort(), [raw])

  const filtered = useMemo(() => raw.filter(r => {
    if (filAno !== 'todos' && r.dt_abertura?.slice(0, 4) !== filAno) return false
    if (filCanal !== 'todos' && r.canal !== filCanal) return false
    if (filCultura !== 'todas' && r.cultura !== filCultura) return false
    return true
  }), [raw, filAno, filCanal, filCultura])

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
        <p style={{ marginTop: 16, color: 'var(--texto-suave)', fontWeight: 600 }}>Carregando dados...</p>
      </div>
    </div>
  )

  return (
    <div className="page">
      <div className="filters-bar" style={{ marginBottom: 20 }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--texto-suave)', whiteSpace: 'nowrap' }}>🔎 Filtrar:</span>
        <select className="filter-select" value={filAno} onChange={e => setFilAno(e.target.value)}>
          <option value="todos">📅 Todos os anos</option>
          {anos.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
        <select className="filter-select" value={filCanal} onChange={e => setFilCanal(e.target.value)}>
          <option value="todos">🏪 Todos os canais</option>
          {canais.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select className="filter-select" value={filCultura} onChange={e => setFilCultura(e.target.value)}>
          <option value="todas">🌱 Todas as culturas</option>
          {culturas.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        {(filAno !== 'todos' || filCanal !== 'todos' || filCultura !== 'todas') && (
          <button onClick={() => { setFilAno('todos'); setFilCanal('todos'); setFilCultura('todas') }}
            style={{ background: 'var(--terra-claro)', border: '1px solid #e0c9bc', borderRadius: 8, padding: '8px 14px', fontFamily: 'Nunito', fontSize: 13, fontWeight: 700, color: 'var(--terra)', cursor: 'pointer' }}>
            ✕ Limpar
          </button>
        )}
        <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--texto-suave)', fontWeight: 600 }}>
          {totalItens.toLocaleString('pt-BR')} itens
        </span>
      </div>

      <div className="metrics-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))' }}>
        <div className="metric-card verde">
          <span className="metric-icon">💰</span>
          <div className="metric-label">Valor Total</div>
          <div className="metric-value">{fmt(valorTotal)}</div>
          <div className="metric-sub">{fmtFull(valorTotal)}</div>
        </div>
        <div className="metric-card amarelo">
          <span className="metric-icon">📦</span>
          <div className="metric-label">Total de Itens</div>
          <div className="metric-value">{totalItens.toLocaleString('pt-BR')}</div>
          <div className="metric-sub">registros filtrados</div>
        </div>
        <div className="metric-card ceu">
          <span className="metric-icon">🌱</span>
          <div className="metric-label">Culturas</div>
          <div className="metric-value">{totalCulturas}</div>
          <div className="metric-sub">tipos distintos</div>
        </div>
        <div className="metric-card terra">
          <span className="metric-icon">🎟️</span>
          <div className="metric-label">Ticket Médio</div>
          <div className="metric-value" style={{ fontSize: 20 }}>{fmt(ticketMedio)}</div>
          <div className="metric-sub">por item licitado</div>
        </div>
        <div className="metric-card verde">
          <span className="metric-icon">⚖️</span>
          <div className="metric-label">Preço Médio/kg</div>
          <div className="metric-value" style={{ fontSize: 20 }}>{precoMedioKg > 0 ? `R$ ${precoMedioKg.toFixed(2)}` : '—'}</div>
          <div className="metric-sub">{qtTotal.toLocaleString('pt-BR')} kg total</div>
        </div>
        <div className="metric-card amarelo">
          <span className="metric-icon">🏪</span>
          <div className="metric-label">Canais Ativos</div>
          <div className="metric-value">{porCanal.length}</div>
          <div className="metric-sub">canais de distribuição</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 20, marginBottom: 20 }}>
        <div className="chart-card" style={{ margin: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <h3 style={{ margin: 0 }}>🏆 Top Culturas por Valor</h3>
            <select className="filter-select" style={{ fontSize: 12, padding: '5px 10px' }} value={topN} onChange={e => setTopN(Number(e.target.value))}>
              <option value={5}>Top 5</option>
              <option value={10}>Top 10</option>
              <option value={20}>Top 20</option>
            </select>
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={topCulturas} margin={{ top: 4, right: 8, left: 8, bottom: 70 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e8e2d8" />
              <XAxis dataKey="cultura" tick={{ fontSize: 10, fill: '#6b6458', fontFamily: 'Nunito' }} angle={-40} textAnchor="end" interval={0} />
              <YAxis tickFormatter={v => fmt(v)} tick={{ fontSize: 10, fill: '#6b6458', fontFamily: 'Nunito' }} />
              <Tooltip formatter={(v) => [fmt(Number(v ?? 0)), 'Valor']} contentStyle={{ fontFamily: 'Nunito', fontSize: 12, borderRadius: 10, border: '1px solid #d9d0c4' }} />
              <Bar dataKey="total" fill="#3a7d44" radius={[5, 5, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card" style={{ margin: 0 }}>
          <h3>🏪 Por Canal</h3>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={porCanal} dataKey="total" nameKey="canal" cx="50%" cy="43%" outerRadius={85}
                label={({ percent }) => `${(percent * 100).toFixed(0)}%`} labelLine={false}>
                {porCanal.map((entry) => (
                  <Cell key={entry.canal} fill={CANAL_COLORS[entry.canal] ?? DEFAULT_COLOR} />
                ))}
              </Pie>
              <Tooltip formatter={(v) => [fmt(Number(v ?? 0)), 'Valor']} contentStyle={{ fontFamily: 'Nunito', fontSize: 12, borderRadius: 10 }} />
              <Legend formatter={(v) => <span style={{ fontSize: 11, fontFamily: 'Nunito' }}>{v}</span>} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="chart-card">
        <h3>{filAno !== 'todos' ? `📈 Evolução Mensal — ${filAno}` : '📈 Evolução Anual da Demanda'}</h3>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={filAno !== 'todos' ? evolucaoMensal : evolucao} margin={{ top: 4, right: 8, left: 8, bottom: 4 }}>
            <defs>
              <linearGradient id="gradVerde" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3a7d44" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#3a7d44" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#e8e2d8" />
            <XAxis dataKey={filAno !== 'todos' ? 'mes' : 'ano'} tick={{ fontSize: 11, fill: '#6b6458', fontFamily: 'Nunito' }} />
            <YAxis tickFormatter={v => fmt(v)} tick={{ fontSize: 10, fill: '#6b6458', fontFamily: 'Nunito' }} />
            <Tooltip formatter={(v) => [fmt(Number(v ?? 0)), 'Valor']} contentStyle={{ fontFamily: 'Nunito', fontSize: 12, borderRadius: 10, border: '1px solid #d9d0c4' }} />
            <Area type="monotone" dataKey="total" stroke="#3a7d44" strokeWidth={2.5} fill="url(#gradVerde)" dot={{ fill: '#3a7d44', r: 3 }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
