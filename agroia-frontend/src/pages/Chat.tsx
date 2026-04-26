import { useState, useRef, useEffect } from 'react'
import ResponseRenderer from '../components/ResponseRenderer'
import { streamChat } from '../lib/apiClient'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

function normalizeQuestion(q: string): string {
  return q.toLowerCase().trim().replace(/[^\w\s]/g, '')
}

const SUGGESTIONS = [
  '🥬 Quais hortaliças a prefeitura mais comprou nos últimos dois anos?',
  '💰 Qual foi o preço médio pago por kg de alface no PNAE em 2023?',
  '🍌 A prefeitura compra banana da terra? Quanto pagou no último ano?',
  '🌾 Qual programa compra mais de agricultores familiares — PNAE ou Armazém?',
  '📊 Quantos produtores forneceram alimentos para o PNAE em 2023?',
  '💵 Quanto a prefeitura gastou com compras de agricultura familiar em 2024?',
]

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [statusMsg, setStatusMsg] = useState('')
  const [sessionId] = useState<string>()
  const [responseCache] = useState(new Map<string, string>())
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading, statusMsg])

  const send = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || loading) return

    const normalized = normalizeQuestion(trimmed)
    const cached = responseCache.get(normalized)
    if (cached) {
      setMessages(prev => [...prev, { role: 'user', content: trimmed }, { role: 'assistant', content: cached }])
      return
    }

    const userMsg: Message = { role: 'user', content: trimmed }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)
    setStatusMsg('🔍 Analisando sua pergunta...')

    try {
      const assistantMsg: Message = { role: 'assistant', content: '' }
      setMessages(prev => [...prev, assistantMsg])

      let fullResponse = ''
      for await (const event of streamChat({ pergunta: trimmed, historico: messages.slice(-6), session_id: sessionId as string | undefined })) {
        if (event.tipo === 'status') {
          setStatusMsg(event.msg || '⏳ Processando...')
        } else if (event.tipo === 'token') {
          fullResponse += event.texto || ''
          setMessages(prev => {
            const updated = [...prev]
            updated[updated.length - 1].content = fullResponse
            return updated
          })
        } else if (event.tipo === 'fim') {
          responseCache.set(normalized, fullResponse)
          setStatusMsg('')
        }
      }
    } catch (err) {
      console.error('Stream error:', err)
      setMessages(prev => [...prev, { role: 'assistant', content: '⚠️ Não foi possível conectar ao servidor. Verifique se o backend está rodando.' }])
    } finally {
      setLoading(false)
      setStatusMsg('')
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
            <div className="msg-bubble">
              {msg.role === 'assistant' ? (
                <ResponseRenderer content={msg.content} />
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}

        {statusMsg && (
          <div className="msg assistant">
            <div className="msg-avatar">🌾</div>
            <div className="msg-bubble" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span className="spinner" />
              <span style={{ color: 'var(--texto-suave)', fontSize: 13 }}>{statusMsg}</span>
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
