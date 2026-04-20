import { useEffect, useState } from 'react'
import { createClient } from '@supabase/supabase-js'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, Area, AreaChart,
} from 'recharts'

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL ?? '',
  import.meta.env.VITE_SUPABASE_ANON_KEY ?? ''
)

const fmt = (v: number) =>
  v >= 1_000_000
    ? `R$ ${(v / 1_000_000).toFixed(1)}M`
    : v >= 1_000
    ? `R$ ${(v / 1_000).toFixed(0)}K`
    : `R$ ${v.toFixed(0)}`

export default function Dashboard() {
  const [culturas, setCulturas] = useState<{ cultura: string; total: number }[]>([])
  const [evolucao, setEvolucao] = useState<{ ano: string; total: number }[]>([])
  const [metrics, setMetrics] = useState({ valorTotal: 0, totalItens: 0, totalCulturas: 0, anos: '' })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        const { data: raw } = await supabase
          .from('vw_itens_agro')
          .select('cultura, valor_total, dt_abertura')

        if (!raw) return

        const valorTotal = raw.reduce((s, r) => s + (r.valor_total ?? 0), 0)
        const anos = [...new Set(raw.map(r => r.dt_abertura?.slice(0, 4)).filter(Boolean))].sort()

        const cultMap: Record<string, number> = {}
        raw.forEach(r => {
          if (r.cultura) cultMap[r.cultura] = (cultMap[r.cultura] ?? 0) + (r.valor_total ?? 0)
        })
        const topCulturas = Object.entries(cultMap)
          .map(([cultura, total]) => ({ cultura, total }))
          .sort((a, b) => b.total - a.total)
          .slice(0, 10)

        const anoMap: Record<string, number> = {}
        raw.forEach(r => {
          const ano = r.dt_abertura?.slice(0, 4)
          if (ano) anoMap[ano] = (anoMap[ano] ?? 0) + (r.valor_total ?? 0)
        })
        const evoData = Object.entries(anoMap)
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([ano, total]) => ({ ano, total }))

        setCulturas(topCulturas)
        setEvolucao(evoData)
        setMetrics({
          valorTotal,
          totalItens: raw.length,
          totalCulturas: Object.keys(cultMap).length,
          anos: anos.length > 0 ? `${anos[0]}–${anos[anos.length - 1]}` : '—',
        })
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

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
      <div className="metrics-grid">
        <div className="metric-card verde">
          <span className="metric-icon">💰</span>
          <div className="metric-label">Valor Total Licitado</div>
          <div className="metric-value">{fmt(metrics.valorTotal)}</div>
          <div className="metric-sub">em compras institucionais</div>
        </div>
        <div className="metric-card amarelo">
          <span className="metric-icon">📦</span>
          <div className="metric-label">Total de Itens</div>
          <div className="metric-value">{metrics.totalItens.toLocaleString('pt-BR')}</div>
          <div className="metric-sub">itens em licitações</div>
        </div>
        <div className="metric-card ceu">
          <span className="metric-icon">🌱</span>
          <div className="metric-label">Culturas Distintas</div>
          <div className="metric-value">{metrics.totalCulturas}</div>
          <div className="metric-sub">tipos de produtos</div>
        </div>
        <div className="metric-card terra">
          <span className="metric-icon">📅</span>
          <div className="metric-label">Período</div>
          <div className="metric-value" style={{ fontSize: 22 }}>{metrics.anos}</div>
          <div className="metric-sub">série histórica</div>
        </div>
      </div>

      <div className="chart-card">
        <h3>🏆 Top 10 Culturas por Valor Licitado</h3>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={culturas} margin={{ top: 4, right: 8, left: 8, bottom: 60 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e8e2d8" />
            <XAxis
              dataKey="cultura"
              tick={{ fontSize: 11, fill: '#6b6458', fontFamily: 'Nunito' }}
              angle={-35}
              textAnchor="end"
              interval={0}
            />
            <YAxis tickFormatter={v => fmt(v)} tick={{ fontSize: 11, fill: '#6b6458', fontFamily: 'Nunito' }} />
            <Tooltip
              formatter={(v: number) => [fmt(v), 'Valor']}
              contentStyle={{ fontFamily: 'Nunito', fontSize: 13, borderRadius: 10, border: '1px solid #d9d0c4' }}
            />
            <Bar dataKey="total" fill="#3a7d44" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-card">
        <h3>📈 Evolução Anual da Demanda Institucional</h3>
        <ResponsiveContainer width="100%" height={240}>
          <AreaChart data={evolucao} margin={{ top: 4, right: 8, left: 8, bottom: 4 }}>
            <defs>
              <linearGradient id="gradVerde" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3a7d44" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#3a7d44" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#e8e2d8" />
            <XAxis dataKey="ano" tick={{ fontSize: 12, fill: '#6b6458', fontFamily: 'Nunito' }} />
            <YAxis tickFormatter={v => fmt(v)} tick={{ fontSize: 11, fill: '#6b6458', fontFamily: 'Nunito' }} />
            <Tooltip
              formatter={(v: number) => [fmt(v), 'Valor']}
              contentStyle={{ fontFamily: 'Nunito', fontSize: 13, borderRadius: 10, border: '1px solid #d9d0c4' }}
            />
            <Area type="monotone" dataKey="total" stroke="#3a7d44" strokeWidth={2.5} fill="url(#gradVerde)" dot={{ fill: '#3a7d44', r: 4 }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
