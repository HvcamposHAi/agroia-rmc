import { useState, useRef, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { LucideIcon } from 'lucide-react'
import { Sprout, Info, Store, ChartColumn, Scale, Coins, TrendingUp, CalendarCheck, Landmark } from 'lucide-react'
import MensagemChat, { StatusChat } from '../components/MensagemChat'
import { BotoesVoz, AvisoVoz } from '../components/VozControles'
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

type Papel = 'gestor' | 'produtor'

// Exemplos por perfil (NN/g: poucos exemplos, do domínio, mostram em segundos o que a IA faz).
// O perfil vem da escolha feita na Início (localStorage 'agroia_papel').
const SUGGESTIONS: Record<Papel, Record<Lang, string[]>> = {
  gestor: {
    pt: [
      'Quais produtos a agricultura familiar tem disponível para venda?',
      'Quais hortaliças a prefeitura mais comprou nos últimos dois anos?',
      'O preço pago pela prefeitura está acima do atacado da CEASA?',
      'Quanto a prefeitura gastou com agricultura familiar em 2024?',
    ],
    en: [
      'Which products do family farmers have available for sale?',
      'Which vegetables did the city buy most in the last two years?',
      'Is the price paid by the city above the CEASA wholesale price?',
      'How much did the city spend on family farming in 2024?',
    ],
    es: [
      '¿Qué productos tiene disponibles para la venta la agricultura familiar?',
      '¿Qué hortalizas compró más la alcaldía en los últimos dos años?',
      '¿El precio pagado por la alcaldía está por encima del mayorista de la CEASA?',
      '¿Cuánto gastó la alcaldía en agricultura familiar en 2024?',
    ],
  },
  produtor: {
    pt: [
      'Quais hortaliças a prefeitura mais comprou nos últimos dois anos?',
      'Como está o preço do tomate na CEASA hoje?',
      'É bom momento para vender alface agora?',
      'Qual programa compra mais de agricultores familiares — PNAE ou Armazém?',
    ],
    en: [
      'Which vegetables did the city buy most in the last two years?',
      "What's the price of tomatoes at CEASA today?",
      'Is now a good time to sell lettuce?',
      'Which program buys more from family farmers — PNAE or Armazém?',
    ],
    es: [
      '¿Qué hortalizas compró más la alcaldía en los últimos dos años?',
      '¿Cómo está el precio del tomate en la CEASA hoy?',
      '¿Es buen momento para vender lechuga ahora?',
      '¿Qué programa compra más a los agricultores familiares — PNAE o Armazém?',
    ],
  },
}
const ICONES_SUGESTAO: Record<Papel, LucideIcon[]> = {
  gestor: [Store, ChartColumn, Scale, Coins],
  produtor: [ChartColumn, TrendingUp, CalendarCheck, Landmark],
}

function lerPapel(): Papel {
  try { return localStorage.getItem('agroia_papel') === 'produtor' ? 'produtor' : 'gestor' } catch { return 'gestor' }
}

const MSG = defineMessages({
  pt: {
    welcomeTitle: 'Olá! Como posso ajudar?',
    welcomeText: 'Pergunte sobre as compras de alimentos da prefeitura de Curitiba, preços de atacado e ofertas da agricultura familiar.',
    disclosure: 'Você está conversando com um assistente de inteligência artificial. As respostas são geradas automaticamente a partir de dados públicos e podem conter erros.',
    analisando: 'Analisando sua pergunta…',
    processando: 'Processando…',
    erroConexao: 'Não foi possível obter a resposta agora. Tente novamente em instantes.',
    ouvindo: 'Ouvindo…',
    placeholder: 'Escreva sua pergunta…',
    rodape: 'Fontes: Portal da Transparência de Curitiba (SMSAN/FAAC, 2019–2026), CEASA-PR e PROHORT/CONAB · Respostas geradas por IA',
    enviar: 'Enviar',
  },
  en: {
    welcomeTitle: 'Hello! How can I help?',
    welcomeText: "Ask about Curitiba city hall's food purchases, wholesale prices and family-farming offers.",
    disclosure: 'You are chatting with an artificial intelligence assistant. Answers are generated automatically from public data and may contain errors.',
    analisando: 'Analyzing your question…',
    processando: 'Processing…',
    erroConexao: "Couldn't get an answer right now. Please try again in a moment.",
    ouvindo: 'Listening…',
    placeholder: 'Type your question…',
    rodape: 'Sources: Curitiba Transparency Portal (SMSAN/FAAC, 2019–2026), CEASA-PR and PROHORT/CONAB · AI-generated answers',
    enviar: 'Send',
  },
  es: {
    welcomeTitle: '¡Hola! ¿En qué puedo ayudar?',
    welcomeText: 'Pregunte sobre las compras de alimentos de la alcaldía de Curitiba, precios mayoristas y ofertas de la agricultura familiar.',
    disclosure: 'Está conversando con un asistente de inteligencia artificial. Las respuestas se generan automáticamente a partir de datos públicos y pueden contener errores.',
    analisando: 'Analizando su pregunta…',
    processando: 'Procesando…',
    erroConexao: 'No fue posible obtener la respuesta ahora. Inténtelo de nuevo en unos instantes.',
    ouvindo: 'Escuchando…',
    placeholder: 'Escriba su pregunta…',
    rodape: 'Fuentes: Portal de Transparencia de Curitiba (SMSAN/FAAC, 2019–2026), CEASA-PR y PROHORT/CONAB · Respuestas generadas por IA',
    enviar: 'Enviar',
  },
})

export default function Chat() {
  const { lang } = useI18n()
  const t = useT(MSG)
  const [papel] = useState<Papel>(lerPapel)
  const suggestions = SUGGESTIONS[papel][lang]
  const icones = ICONES_SUGESTAO[papel]
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
      // Substitui o balão vazio (se o erro veio antes do 1º token) em vez de deixá-lo em branco.
      setMessages(prev => {
        const ultimo = prev[prev.length - 1]
        const base = ultimo?.role === 'assistant' && !ultimo.content ? prev.slice(0, -1) : prev
        return [...base, { role: 'assistant', content: t('erroConexao') }]
      })
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
            <span className="welcome-icon" aria-hidden><Sprout size={28} /></span>
            <h3>{t('welcomeTitle')}</h3>
            <p>{t('welcomeText')}</p>
            <p className="ai-disclosure"><Info size={15} aria-hidden /> {t('disclosure')}</p>
            <div className="suggestions">
              {suggestions.map((s, i) => {
                const Icon = icones[i % icones.length]
                return (
                  <button key={s} className="suggestion-btn" onClick={() => send(s)}>
                    <Icon size={16} aria-hidden /> {s}
                  </button>
                )
              })}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <MensagemChat
            key={i}
            role={msg.role}
            content={msg.content}
            emAndamento={loading && i === messages.length - 1}
            voz={voz}
            id={`msg-${i}`}
          />
        ))}

        {statusMsg && <StatusChat msg={statusMsg} />}
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
        <p className="chat-rodape">{t('rodape')}</p>
      </div>
    </div>
  )
}
