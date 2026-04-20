import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, MessageSquare, LogOut } from 'lucide-react'

interface Conversation {
  id: string
  titulo?: string
  data_criacao?: string
}

export default function Sidebar() {
  const navigate = useNavigate()
  const [conversas, setConversas] = useState<Conversation[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadConversas()
  }, [])

  const loadConversas = async () => {
    try {
      // Simular carregamento de conversas - será integrado com a API
      const stored = localStorage.getItem('agroia_conversas')
      if (stored) {
        setConversas(JSON.parse(stored).slice(0, 5))
      }
      setLoading(false)
    } catch (error) {
      console.error('Erro ao carregar conversas:', error)
      setLoading(false)
    }
  }

  const novaConversa = () => {
    const sessionId = crypto.randomUUID()
    localStorage.setItem('agroia_session', sessionId)
    navigate('/')
    window.location.reload()
  }

  return (
    <div className="p-6 h-full flex flex-col">
      {/* Logo */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-emerald-600">🌾 AgroIA-RMC</h1>
        <p className="text-sm text-gray-600 mt-1">Assistente Agrícola</p>
      </div>

      {/* Nova Conversa */}
      <button
        onClick={novaConversa}
        className="btn-primary w-full flex items-center justify-center gap-2 mb-8"
      >
        <Plus size={18} />
        Nova Conversa
      </button>

      {/* Histórico */}
      <div className="mb-8">
        <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <MessageSquare size={18} />
          Conversas Recentes
        </h3>
        <div className="space-y-2">
          {loading ? (
            <p className="text-sm text-gray-500">Carregando...</p>
          ) : conversas.length === 0 ? (
            <p className="text-sm text-gray-500">Nenhuma conversa salva</p>
          ) : (
            conversas.map((conv) => (
              <button
                key={conv.id}
                onClick={() => {
                  localStorage.setItem('agroia_session', conv.id)
                  navigate('/')
                }}
                className="w-full text-left px-3 py-2 text-sm rounded-lg hover:bg-gray-200 text-gray-700 truncate"
              >
                • {conv.titulo || 'Conversa ' + conv.id.slice(0, 8)}
              </button>
            ))
          )}
        </div>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Settings */}
      <div className="border-t border-gray-200 pt-4">
        <div className="text-xs text-gray-600 mb-3">
          User: {localStorage.getItem('agroia_user') || 'Anônimo'}
        </div>
        <button className="w-full flex items-center justify-center gap-2 text-sm text-gray-700 hover:text-red-600 transition-colors">
          <LogOut size={16} />
          Logout
        </button>
      </div>
    </div>
  )
}
