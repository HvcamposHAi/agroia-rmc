import { useState, useEffect } from 'react'
import { Search, Loader, ChevronLeft, ChevronRight } from 'lucide-react'
import { queryItensAgro, getCulturas, getCanais } from '../lib/supabaseClient'

interface Filtros {
  busca: string
  cultura: string
  canal: string
  offset: number
}

interface Item {
  id?: number
  processo?: string
  descricao?: string
  cultura?: string
  canal?: string
  valor_total?: number
  dt_abertura?: string
  qt_solicitada?: number
}

export default function Consultas() {
  const [filtros, setFiltros] = useState<Filtros>({
    busca: '',
    cultura: 'Todas',
    canal: 'Todas',
    offset: 0,
  })

  const [itens, setItens] = useState<Item[]>([])
  const [loading, setLoading] = useState(false)
  const [culturas, setCulturas] = useState<string[]>([])
  const [canais, setCanais] = useState<string[]>([])
  const [total, setTotal] = useState(0)

  useEffect(() => {
    loadDropdownOptions()
  }, [])

  useEffect(() => {
    loadItens()
  }, [filtros])

  const loadDropdownOptions = async () => {
    try {
      const { data: culturasData } = await getCulturas()
      const { data: canaisData } = await getCanais()

      if (culturasData) {
        const culturasList = culturasData.map((x: any) => x.cultura).filter(Boolean)
        setCulturas(['Todas', ...culturasList])
      }

      if (canaisData) {
        const canaisList = canaisData.map((x: any) => x.canal).filter(Boolean)
        setCanais(['Todas', ...canaisList])
      }
    } catch (error) {
      console.error('Erro ao carregar filtros:', error)
    }
  }

  const loadItens = async () => {
    try {
      setLoading(true)
      const { data } = await queryItensAgro({
        cultura: filtros.cultura,
        canal: filtros.canal,
        offset: filtros.offset,
        limit: 20,
      })

      if (data) {
        setItens(data)
        setTotal(data.length)
      }
      setLoading(false)
    } catch (error) {
      console.error('Erro ao carregar itens:', error)
      setLoading(false)
    }
  }

  const handleFiltrosChange = (key: keyof Filtros, value: string | number) => {
    setFiltros((prev) => ({
      ...prev,
      [key]: value,
      offset: 0, // Reset pagination
    }))
  }

  const pagina = Math.floor(filtros.offset / 20) + 1
  const temProxima = total === 20

  const formatCurrency = (value?: number) => {
    if (!value) return 'R$ 0,00'
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL',
    }).format(value)
  }

  const formatData = (data?: string) => {
    if (!data) return '-'
    return new Date(data).toLocaleDateString('pt-BR')
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900">🔍 Consultar Licitações</h2>
        <p className="text-gray-600 mt-1">Busque e filtre itens agrícolas nas licitações públicas</p>
      </div>

      {/* Filtros */}
      <div className="card p-6 space-y-4">
        <h3 className="font-semibold text-gray-900">Filtros</h3>

        {/* Busca */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Buscar por descrição</label>
          <div className="relative">
            <Search className="absolute left-3 top-3 text-gray-400" size={18} />
            <input
              type="text"
              value={filtros.busca}
              onChange={(e) => handleFiltrosChange('busca', e.target.value)}
              placeholder="Digite uma descrição..."
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>
        </div>

        {/* Filtros Avançados */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Cultura</label>
            <select
              value={filtros.cultura}
              onChange={(e) => handleFiltrosChange('cultura', e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              {culturas.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Canal</label>
            <select
              value={filtros.canal}
              onChange={(e) => handleFiltrosChange('canal', e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              {canais.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-end gap-2">
            <button
              onClick={() => setFiltros({ busca: '', cultura: 'Todas', canal: 'Todas', offset: 0 })}
              className="btn-ghost flex-1"
            >
              Limpar
            </button>
          </div>
        </div>
      </div>

      {/* Resultados */}
      <div className="card p-6">
        <div className="mb-4">
          <p className="text-gray-600 font-medium">Resultados: {itens.length} itens encontrados</p>
        </div>

        {loading ? (
          <div className="flex justify-center py-8">
            <Loader className="animate-spin text-emerald-500" size={32} />
          </div>
        ) : itens.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-gray-500">Nenhum resultado encontrado</p>
          </div>
        ) : (
          <>
            <div className="space-y-3 mb-6">
              {itens.map((item, idx) => (
                <div key={idx} className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors">
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <h4 className="font-semibold text-gray-900">📋 Processo: {item.processo || '-'}</h4>
                      <p className="text-sm text-gray-700 mt-1">{item.descricao || '-'}</p>
                    </div>
                    <button className="text-sm text-emerald-600 hover:text-emerald-700 font-medium">
                      Ver Detalhes →
                    </button>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm mt-3 pt-3 border-t border-gray-200">
                    <div>
                      <span className="text-gray-600">Cultura:</span>
                      <p className="font-medium text-gray-900">{item.cultura || '-'}</p>
                    </div>
                    <div>
                      <span className="text-gray-600">Valor:</span>
                      <p className="font-medium text-gray-900">{formatCurrency(item.valor_total)}</p>
                    </div>
                    <div>
                      <span className="text-gray-600">Canal:</span>
                      <p className="font-medium text-gray-900">{item.canal || '-'}</p>
                    </div>
                    <div>
                      <span className="text-gray-600">Data:</span>
                      <p className="font-medium text-gray-900">{formatData(item.dt_abertura)}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Paginação */}
            <div className="flex items-center justify-between border-t border-gray-200 pt-4">
              <button
                disabled={filtros.offset === 0}
                onClick={() => handleFiltrosChange('offset', Math.max(0, filtros.offset - 20))}
                className="flex items-center gap-1 px-4 py-2 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100 rounded-lg"
              >
                <ChevronLeft size={18} />
                Anterior
              </button>

              <span className="text-sm text-gray-600">
                Página {pagina}
              </span>

              <button
                disabled={!temProxima}
                onClick={() => handleFiltrosChange('offset', filtros.offset + 20)}
                className="flex items-center gap-1 px-4 py-2 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100 rounded-lg"
              >
                Próximo
                <ChevronRight size={18} />
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
