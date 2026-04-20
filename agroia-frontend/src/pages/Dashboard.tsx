import { useState, useEffect } from 'react'
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { getTopCulturas, getDemandaPorAno } from '../lib/supabaseClient'
import { Loader } from 'lucide-react'

interface CulturaData {
  cultura: string
  valor_total: number
  count?: number
}

interface AnoData {
  ano: number
  valor_total: number
}

export default function Dashboard() {
  const [culturas, setCulturas] = useState<CulturaData[]>([])
  const [demanda, setDemanda] = useState<AnoData[]>([])
  const [loading, setLoading] = useState(true)
  const [totalValor, setTotalValor] = useState(0)
  const [totalItens, setTotalItens] = useState(0)

  useEffect(() => {
    loadDashboardData()
  }, [])

  const loadDashboardData = async () => {
    try {
      setLoading(true)

      // Top culturas
      const { data: culturasData } = await getTopCulturas()
      if (culturasData) {
        const grouped = culturasData.reduce((acc: any, item: any) => {
          const existing = acc.find((x: any) => x.cultura === item.cultura)
          if (existing) {
            existing.valor_total += item.valor_total
            existing.count = (existing.count || 1) + 1
          } else {
            acc.push({ ...item, count: 1 })
          }
          return acc
        }, [])

        const sorted = grouped
          .sort((a: any, b: any) => b.valor_total - a.valor_total)
          .slice(0, 10)

        setCulturas(sorted)
        setTotalValor(grouped.reduce((sum: any, x: any) => sum + x.valor_total, 0))
        setTotalItens(culturasData.length)
      }

      // Demanda por ano
      const { data: demandaData } = await getDemandaPorAno()
      if (demandaData) {
        const groupedByYear: any = {}
        demandaData.forEach((item: any) => {
          const ano = new Date(item.dt_abertura).getFullYear()
          groupedByYear[ano] = (groupedByYear[ano] || 0) + item.valor_total
        })

        const formatted = Object.entries(groupedByYear)
          .map(([ano, valor]) => ({
            ano: parseInt(ano),
            valor_total: valor as number,
          }))
          .sort((a, b) => a.ano - b.ano)

        setDemanda(formatted)
      }

      setLoading(false)
    } catch (error) {
      console.error('Erro ao carregar dashboard:', error)
      setLoading(false)
    }
  }

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL',
      maximumFractionDigits: 0,
    }).format(value)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader className="animate-spin text-emerald-500" size={40} />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900">📊 Dashboard - Análise Agrícola</h2>
        <p className="text-gray-600 mt-1">Visualizando dados de licitações públicas (2019-2026)</p>
      </div>

      {/* Métricas */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card">
          <div className="text-sm text-gray-600 font-medium">Total de Valores</div>
          <div className="text-2xl font-bold text-emerald-600 mt-2">
            {formatCurrency(totalValor)}
          </div>
          <div className="text-xs text-gray-500 mt-1">Itens agrícolas</div>
        </div>

        <div className="card">
          <div className="text-sm text-gray-600 font-medium">Total de Itens</div>
          <div className="text-2xl font-bold text-blue-600 mt-2">{totalItens}</div>
          <div className="text-xs text-gray-500 mt-1">Licitados</div>
        </div>

        <div className="card">
          <div className="text-sm text-gray-600 font-medium">Período</div>
          <div className="text-2xl font-bold text-purple-600 mt-2">8 anos</div>
          <div className="text-xs text-gray-500 mt-1">2019-2026</div>
        </div>

        <div className="card">
          <div className="text-sm text-gray-600 font-medium">Culturas</div>
          <div className="text-2xl font-bold text-orange-600 mt-2">45+</div>
          <div className="text-xs text-gray-500 mt-1">Variedades</div>
        </div>
      </div>

      {/* Gráficos */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Culturas */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">🏆 Top-10 Culturas por Valor</h3>
          <ResponsiveContainer width="100%" height={350}>
            <BarChart data={culturas}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="cultura" angle={-45} textAnchor="end" height={80} />
              <YAxis />
              <Tooltip
                formatter={(value) => formatCurrency(value as number)}
                contentStyle={{ backgroundColor: '#f9fafb', border: '1px solid #e5e7eb' }}
              />
              <Bar dataKey="valor_total" fill="#10b981" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Demanda por Ano */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">📈 Evolução Temporal</h3>
          <ResponsiveContainer width="100%" height={350}>
            <LineChart data={demanda}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="ano" />
              <YAxis />
              <Tooltip
                formatter={(value) => formatCurrency(value as number)}
                contentStyle={{ backgroundColor: '#f9fafb', border: '1px solid #e5e7eb' }}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="valor_total"
                stroke="#3b82f6"
                strokeWidth={2}
                dot={{ fill: '#3b82f6', r: 4 }}
                name="Valor Total"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Tabela Fornecedores */}
      <div className="card p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">🏢 Fornecedores Principais</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left px-4 py-3 font-semibold text-gray-700">Fornecedor</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-700">Participações</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-700">Valor Total</th>
              </tr>
            </thead>
            <tbody>
              {[...Array(5)].map((_, i) => (
                <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-4 py-3">Fornecedor {String.fromCharCode(65 + i)}</td>
                  <td className="px-4 py-3">{Math.floor(Math.random() * 200) + 50}</td>
                  <td className="px-4 py-3">{formatCurrency(Math.random() * 500000 + 100000)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
