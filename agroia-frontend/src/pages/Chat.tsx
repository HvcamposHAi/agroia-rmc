import { useState, useRef, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import ResponseRenderer from '../components/ResponseRenderer'
import { BotoesVoz, AvisoVoz, OuvirResposta } from '../components/VozControles'
import { streamChat } from '../lib/apiClient'
import { useVoz } from '../lib/useVoz'
import { defineMessages, useI18n, useT } from '../i18n'
import type { Lang } from '../i18n'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

function normalizeQuestion(q: string): string {
  return q.toLowerCase().trim().replace(/[^\w\s]/g, '')
}

const SUGGESTIONS: Record<Lang, string[]> = {
  pt: [
    '🥬 Quais hortaliças a prefeitura mais comprou nos últimos dois anos?',
    '💰 Qual foi o preço médio pago por kg de alface no PNAE em 2023?',
    '🍌 A prefeitura compra banana da terra? Quanto pagou no último ano?',
    '🌾 Qual programa compra mais de agricultores familiares — PNAE ou Armazém?',
    '📊 Quantos produtores forneceram alimentos para o PNAE em 2023?',
    '💵 Quanto a prefeitura gastou com compras de agricultura familiar em 2024?',
    '🍅 Como está o preço do tomate na CEASA hoje?',
    '📈 Qual cultura está com melhor preço esta semana?',
    '🥗 É bom momento para vender alface agora?',
  ],
  en: [
    '🥬 Which vegetables did the city buy most in the last two years?',
    '💰 What was the average price paid per kg of lettuce in PNAE in 2023?',
    '🍌 Does the city buy plantain? How much did it pay last year?',
    '🌾 Which program buys more from family farmers — PNAE or Armazém?',
    '📊 How many farmers supplied food to PNAE in 2023?',
    '💵 How much did the city spend on family farming purchases in 2024?',
    "🍅 What's the price of tomatoes at CEASA today?",
    '📈 Which crop has the best price this week?',
    '🥗 Is now a good time to sell lettuce?',
  ],
  es: [
    '🥬 ¿Qué hortalizas compró más la alcaldía en los últimos dos años?',
    '💰 ¿Cuál fue el precio medio pagado por kg de lechuga en el PNAE en 2023?',
    '🍌 ¿La alcaldía compra plátano macho? ¿Cuánto pagó el último año?',
    '🌾 ¿Qué programa compra más a los agricultores familiares — PNAE o Armazém?',
    '📊 ¿Cuántos productores suministraron alimentos al PNAE en 2023?',
    '💵 ¿Cuánto gastó la alcaldía en compras de agricultura familiar en 2024?',
    '🍅 ¿Cómo está el precio del tomate en la CEASA hoy?',
    '📈 ¿Qué cultivo tiene el mejor precio esta semana?',
    '🥗 ¿Es buen momento para vender lechuga ahora?',
  ],
}

const MSG = defineMessages({
  pt: {
    welcomeTitle: 'Olá! Como posso ajudar?',
    welcomeText: 'Consulte dados de licitações agrícolas da SMSAN/FAAC de Curitiba em linguagem natural.',
    analisando: '🔍 Analisando sua pergunta...',
    processando: '⏳ Processando...',
    erroConexao: '⚠️ Não foi possível conectar ao servidor. Verifique se o backend está rodando.',
    ouvindo: 'Ouvindo…',
    placeholder: 'Faça uma pergunta sobre licitações agrícolas...',
    rodape: 'Dados de licitações da SMSAN/FAAC 2019–2026 • AgroIA-RMC',
    enviar: 'Enviar',
  },
  en: {
    welcomeTitle: 'Hello! How can I help?',
    welcomeText: "Ask about agricultural bidding data from Curitiba's SMSAN/FAAC in plain language.",
    analisando: '🔍 Analyzing your question...',
    processando: '⏳ Processing...',
    erroConexao: "⚠️ Couldn't connect to the server. Check that the backend is running.",
    ouvindo: 'Listening…',
    placeholder: 'Ask a question about agricultural bidding...',
    rodape: 'SMSAN/FAAC bidding data 2019–2026 • AgroIA-RMC',
    enviar: 'Send',
  },
  es: {
    welcomeTitle: '¡Hola! ¿En qué puedo ayudar?',
    welcomeText: 'Consulte datos de licitaciones agrícolas de la SMSAN/FAAC de Curitiba en lenguaje natural.',
    analisando: '🔍 Analizando su pregunta...',
    processando: '⏳ Procesando...',
    erroConexao: '⚠️ No fue posible conectar con el servidor. Verifique que el backend esté funcionando.',
    ouvindo: 'Escuchando…',
    placeholder: 'Haga una pregunta sobre licitaciones agrícolas...',
    rodape: 'Datos de licitaciones de la SMSAN/FAAC 2019–2026 • AgroIA-RMC',
    enviar: 'Enviar',
  },
})

interface ChatProps {
  suggestions?: string[]
  welcomeIcon?: string
  welcomeTitle?: string
  welcomeText?: string
}

export default function Chat({
  suggestions: suggestionsProp,
  welcomeIcon = '🌾',
  welcomeTitle: welcomeTitleProp,
  welcomeText: welcomeTextProp,
}: ChatProps = {}) {
  const { lang } = useI18n()
  const t = useT(MSG)
  const suggestions = suggestionsProp ?? SUGGESTIONS[lang]
  const welcomeTitle = welcomeTitleProp ?? t('welcomeTitle')
  const welcomeText = welcomeTextProp ?? t('welcomeText')
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [statusMsg, setStatusMsg] = useState('')
  const [sessionId] = useState<string>()
  const [responseCache] = useState(new Map<string, string>())
  const [searchParams] = useSearchParams()
  const ultimoQ = useRef<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const voz = useVoz()

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading, statusMsg])

  // porVoz: pergunta falada no microfone → a resposta também é lida em voz alta.
  const send = async (text: string, porVoz = false) => {
    const trimmed = text.trim()
    if (!trimmed || loading) return
    voz.pararFala()
    const idResposta = `msg-${messages.length + 1}`
    const lerEmVoz = porVoz || voz.lerRespostas

    // Cache por idioma: a mesma pergunta em outro idioma pede outra resposta.
    const normalized = `${lang}:${normalizeQuestion(trimmed)}`
    const cached = responseCache.get(normalized)
    if (cached) {
      setMessages(prev => [...prev, { role: 'user', content: trimmed }, { role: 'assistant', content: cached }])
      setInput('')
      if (lerEmVoz) voz.falar(cached, idResposta)
      return
    }

    const userMsg: Message = { role: 'user', content: trimmed }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)
    setStatusMsg(t('analisando'))

    try {
      const assistantMsg: Message = { role: 'assistant', content: '' }
      setMessages(prev => [...prev, assistantMsg])

      let fullResponse = ''
      for await (const event of streamChat({ pergunta: trimmed, historico: messages.slice(-6), session_id: sessionId as string | undefined, idioma: lang })) {
        if (event.tipo === 'status') {
          setStatusMsg(event.msg || t('processando'))
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
          if (lerEmVoz) voz.falar(fullResponse, idResposta)
        }
      }
    } catch (err) {
      console.error('Stream error:', err)
      setMessages(prev => [...prev, { role: 'assistant', content: t('erroConexao') }])
    } finally {
      setLoading(false)
      setStatusMsg('')
    }
  }

  // Pergunta vinda por deep-link (ex.: barra/chips da Home → /assistente?q=...).
  // Envia quando o q muda (permite nova pergunta sem remontar), sem reenviar o mesmo.
  useEffect(() => {
    const q = searchParams.get('q')
    if (q && q !== ultimoQ.current) {
      ultimoQ.current = q
      send(q)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams])

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input) }
  }

  return (
    <div className="chat-container">
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-welcome">
            <span className="welcome-icon">{welcomeIcon}</span>
            <h3>{welcomeTitle}</h3>
            <p>{welcomeText}</p>
            <div className="suggestions">
              {suggestions.map(s => (
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
                <>
                  <ResponseRenderer content={msg.content} />
                  {!(loading && i === messages.length - 1) && (
                    <OuvirResposta voz={voz} id={`msg-${i}`} texto={msg.content} />
                  )}
                </>
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
            placeholder={voz.ouvindo ? t('ouvindo') : t('placeholder')}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
          />
          <BotoesVoz voz={voz} disabled={loading} onParcial={setInput} onFinal={t => send(t, true)} />
          <button className="send-btn" onClick={() => send(input)} disabled={!input.trim() || loading} aria-label={t('enviar')} title={t('enviar')}>
            <svg viewBox="0 0 24 24"><path d="M2 21l21-9L2 3v7l15 2-15 2v7z"/></svg>
          </button>
        </div>
        <AvisoVoz voz={voz} />
        <p style={{ fontSize: 11, color: 'var(--texto-suave)', textAlign: 'center', marginTop: 8 }}>
          {t('rodape')}
        </p>
      </div>
    </div>
  )
}
