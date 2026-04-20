import { useState, useEffect, useRef } from 'react'
import { Send, Loader } from 'lucide-react'
import { sendChat } from '../lib/apiClient'
import type { ChatMessage } from '../lib/apiClient'

export default function Chat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const id = localStorage.getItem('agroia_session') || crypto.randomUUID()
    setSessionId(id)
    localStorage.setItem('agroia_session', id)
    loadHistory(id)
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const loadHistory = async (id: string) => {
    try {
      // const history = await loadConversationHistory(id)
      // setMessages(history)
      // Por enquanto, usar estado local
      const stored = localStorage.getItem(`agroia_chat_${id}`)
      if (stored) {
        setMessages(JSON.parse(stored))
      }
    } catch (error) {
      console.error('Erro ao carregar histórico:', error)
    }
  }

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || !sessionId) return

    const userMessage: ChatMessage = {
      role: 'user',
      content: input,
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const response = await sendChat({
        pergunta: input,
        session_id: sessionId,
        historico: messages,
      })

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response.resposta,
        tools_usadas: response.tools_usadas,
      }

      const newMessages = [...messages, userMessage, assistantMessage]
      setMessages(newMessages)
      localStorage.setItem(`agroia_chat_${sessionId}`, JSON.stringify(newMessages))

      // Salvar conversa na lista
      const conversas = JSON.parse(localStorage.getItem('agroia_conversas') || '[]')
      if (!conversas.find((c: any) => c.id === sessionId)) {
        conversas.unshift({
          id: sessionId,
          titulo: input.slice(0, 40) + '...',
          data_criacao: new Date().toISOString(),
        })
        localStorage.setItem('agroia_conversas', JSON.stringify(conversas.slice(0, 10)))
      }
    } catch (error) {
      console.error('Erro ao enviar mensagem:', error)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Desculpe, houve um erro ao processar sua mensagem. Tente novamente.',
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full max-h-screen bg-gray-50 rounded-lg border border-gray-200">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <h2 className="text-xl font-bold text-gray-900">💬 Chat - AgroIA-RMC</h2>
        <p className="text-sm text-gray-600 mt-1">Faça perguntas sobre licitações agrícolas</p>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <p className="text-gray-600 text-lg font-medium">Bem-vindo ao AgroIA!</p>
              <p className="text-gray-500 text-sm mt-2">Comece a conversa fazendo uma pergunta sobre:</p>
              <ul className="text-gray-500 text-sm mt-3 space-y-1">
                <li>• Top culturas por demanda</li>
                <li>• Fornecedores principais</li>
                <li>• Análise de licitações</li>
              </ul>
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-md px-4 py-3 rounded-lg ${
                    msg.role === 'user'
                      ? 'bg-blue-500 text-white'
                      : 'bg-white text-gray-900 border border-gray-200'
                  }`}
                >
                  <p className="text-sm">{msg.content}</p>
                  {msg.tools_usadas && msg.tools_usadas.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {msg.tools_usadas.map((tool, i) => (
                        <span
                          key={i}
                          className={`text-xs px-2 py-1 rounded ${
                            msg.role === 'user'
                              ? 'bg-blue-600'
                              : 'bg-gray-100 text-gray-700'
                          }`}
                        >
                          🔧 {tool}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-gray-100 text-gray-900 px-4 py-3 rounded-lg flex items-center gap-2">
                  <Loader size={16} className="animate-spin" />
                  <span className="text-sm">Processando...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input Area */}
      <div className="bg-white border-t border-gray-200 p-4">
        <form onSubmit={handleSendMessage} className="flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Escreva sua pergunta..."
            disabled={loading}
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:bg-gray-100"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="btn-primary flex items-center justify-center gap-2"
          >
            {loading ? <Loader size={18} className="animate-spin" /> : <Send size={18} />}
          </button>
        </form>
      </div>
    </div>
  )
}
