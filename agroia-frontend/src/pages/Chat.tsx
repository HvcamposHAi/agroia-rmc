import { useState, useRef, useEffect } from 'react'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

const SUGGESTIONS = [
  '🥬 Qual a demanda de alface em Curitiba?',
  '🥕 Top culturas compradas pela prefeitura',
  '📅 Licitações abertas em 2024',
  '💰 Valor total de compras de hortaliças',
  '🏫 Compras do PNAE neste ano',
  '📦 Fornecedores de agricultura familiar',
]

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const send = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || loading) return

    const userMsg: Message = { role: 'user', content: trimmed }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
      const res = await fetch(`${API}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pergunta: trimmed, historico: messages }),
      })
      const data = await res.json()
      setMessages(prev => [...prev, { role: 'assistant', content: data.resposta ?? 'Sem resposta do servidor.' }])
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: '⚠️ Não foi possível conectar ao servidor. Verifique se o backend está rodando.' }])
    } finally {
      setLoading(false)
    }
  }

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input) }
  }

  return (
    <div className="chat-container">
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-welcome">
            <span className="welcome-icon">🌾</span>
            <h3>Olá! Como posso ajudar?</h3>
            <p>Consulte dados de licitações agrícolas da SMSAN/FAAC de Curitiba em linguagem natural.</p>
            <div className="suggestions">
              {SUGGESTIONS.map(s => (
                <button key={s} className="suggestion-btn" onClick={() => send(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`msg ${msg.role}`}>
            <div className="msg-avatar">
              {msg.role === 'assistant' ? '🌾' : '👤'}
            </div>
            <div className="msg-bubble">{msg.content}</div>
          </div>
        ))}

        {loading && (
          <div className="msg assistant">
            <div className="msg-avatar">🌾</div>
            <div className="msg-bubble" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span className="spinner" />
              <span style={{ color: 'var(--texto-suave)', fontSize: 13 }}>Consultando os dados...</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="chat-input-area">
        <div className="chat-input-wrapper">
          <textarea
            ref={textareaRef}
            className="chat-input"
            rows={1}
            placeholder="Faça uma pergunta sobre licitações agrícolas..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
          />
          <button className="send-btn" onClick={() => send(input)} disabled={!input.trim() || loading}>
            <svg viewBox="0 0 24 24"><path d="M2 21l21-9L2 3v7l15 2-15 2v7z"/></svg>
          </button>
        </div>
        <p style={{ fontSize: 11, color: 'var(--texto-suave)', textAlign: 'center', marginTop: 8 }}>
          Dados de licitações da SMSAN/FAAC 2019–2026 • AgroIA-RMC
        </p>
      </div>
    </div>
  )
}
