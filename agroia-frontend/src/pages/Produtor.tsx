import { useState, useRef, useEffect } from 'react'
import ResponseRenderer from '../components/ResponseRenderer'
import { streamPost, uploadOfertasPlanilha } from '../lib/apiClient'
import type { SSEEvent, UploadOfertasResult } from '../lib/apiClient'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

const SUGESTOES = [
  '🥬 Tenho 200 kg de alface crespa para março, quero R$ 4/kg',
  '🍅 Quero cadastrar tomate italiano, 500 kg, o ano todo',
  '🥕 Sou cooperativa e tenho cenoura disponível',
]

// Colunas do modelo de planilha (mapeiam 1:1 para o cadastro de oferta)
const MODELO_COLUNAS = [
  'nome', 'cpf_cnpj', 'descricao', 'quantidade', 'unidade',
  'disponibilidade', 'preco_pretendido', 'municipio', 'contato', 'tipo',
]
const MODELO_EXEMPLO = [
  'João da Silva', '000.000.000-00', 'Alface crespa', '200', 'kg',
  'março a junho', '4,00', 'Curitiba', '(41) 99999-0000', 'PRODUTOR_INDIVIDUAL',
]

function baixarModelo() {
  // CSV separado por ; (padrão Excel BR), com BOM para acentuação correta
  const linhas = [MODELO_COLUNAS.join(';'), MODELO_EXEMPLO.join(';')]
  const blob = new Blob(['﻿' + linhas.join('\r\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'modelo_ofertas_agroia.csv'
  a.click()
  URL.revokeObjectURL(url)
}

export default function Produtor() {
  const [aba, setAba] = useState<'chat' | 'planilha'>('chat')

  // ── Estado do chat ──
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [statusMsg, setStatusMsg] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  // ── Estado da planilha ──
  const [arquivo, setArquivo] = useState<File | null>(null)
  const [enviando, setEnviando] = useState(false)
  const [resultado, setResultado] = useState<UploadOfertasResult | null>(null)
  const [erroUpload, setErroUpload] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading, statusMsg])

  const send = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || loading) return

    const userMsg: Message = { role: 'user', content: trimmed }
    const historico = messages.slice(-8)
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)
    setStatusMsg('🌱 Processando...')

    try {
      const assistantMsg: Message = { role: 'assistant', content: '' }
      setMessages(prev => [...prev, assistantMsg])

      let full = ''
      for await (const event of streamPost<SSEEvent>('/produtor/chat/stream', {
        pergunta: trimmed,
        historico,
      })) {
        if (event.tipo === 'status') {
          setStatusMsg(event.msg || '⏳ Processando...')
        } else if (event.tipo === 'token') {
          full += event.texto || ''
          setMessages(prev => {
            const updated = [...prev]
            updated[updated.length - 1].content = full
            return updated
          })
        } else if (event.tipo === 'fim') {
          setStatusMsg('')
        }
      }
    } catch (err) {
      console.error('Stream error:', err)
      setMessages(prev => [...prev, { role: 'assistant', content: '⚠️ Não foi possível conectar ao servidor. Tente novamente em instantes.' }])
    } finally {
      setLoading(false)
      setStatusMsg('')
    }
  }

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input) }
  }

  const enviarPlanilha = async () => {
    if (!arquivo || enviando) return
    setEnviando(true)
    setErroUpload('')
    setResultado(null)
    try {
      const res = await uploadOfertasPlanilha(arquivo)
      setResultado(res)
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      setErroUpload(detail || 'Não foi possível enviar a planilha. Verifique o arquivo e tente novamente.')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="chat-container">
      {/* Seletor de forma de cadastro */}
      <div style={{ display: 'flex', gap: 8, padding: '12px 16px 0', flexWrap: 'wrap' }}>
        <button
          onClick={() => setAba('chat')}
          style={tabStyle(aba === 'chat')}
        >💬 Conversar com o assistente</button>
        <button
          onClick={() => setAba('planilha')}
          style={tabStyle(aba === 'planilha')}
        >📄 Enviar planilha</button>
      </div>

      {aba === 'chat' ? (
        <>
          <div className="chat-messages">
            {messages.length === 0 && (
              <div className="chat-welcome">
                <span className="welcome-icon">🧑‍🌾</span>
                <h3>Cadastre o que você tem para vender</h3>
                <p>
                  Você pode cadastrar de duas formas: <strong>conversando com o assistente</strong> aqui
                  (informe produtos, quantidades e quando estarão disponíveis) ou, se tiver vários itens,
                  enviando uma <strong>planilha</strong> na aba “📄 Enviar planilha”. A prefeitura poderá
                  consultar suas ofertas. É rápido e não precisa de senha.
                </p>
                <div className="suggestions">
                  {SUGESTOES.map(s => (
                    <button key={s} className="suggestion-btn" onClick={() => send(s)}>{s}</button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} className={`msg ${msg.role}`}>
                <div className="msg-avatar">{msg.role === 'assistant' ? '🌱' : '🧑‍🌾'}</div>
                <div className="msg-bubble">
                  {msg.role === 'assistant' ? <ResponseRenderer content={msg.content} /> : msg.content}
                </div>
              </div>
            ))}

            {statusMsg && (
              <div className="msg assistant">
                <div className="msg-avatar">🌱</div>
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
                className="chat-input"
                rows={1}
                placeholder="Ex: tenho 200 kg de alface para março, quero R$ 4 o kg..."
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKey}
              />
              <button className="send-btn" onClick={() => send(input)} disabled={!input.trim() || loading}>
                <svg viewBox="0 0 24 24"><path d="M2 21l21-9L2 3v7l15 2-15 2v7z"/></svg>
              </button>
            </div>
            <p style={{ fontSize: 11, color: 'var(--texto-suave)', textAlign: 'center', marginTop: 8 }}>
              Cadastro de ofertas da agricultura familiar • AgroIA-RMC
            </p>
          </div>
        </>
      ) : (
        <div className="chat-messages" style={{ display: 'block' }}>
          <div style={{ maxWidth: 640, margin: '0 auto' }}>
            <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 16, padding: '24px' }}>
              <h3 style={{ margin: '0 0 8px', fontFamily: 'Fraunces, serif', color: 'var(--texto)' }}>
                📄 Enviar planilha de ofertas
              </h3>
              <p style={{ fontSize: 14, color: 'var(--texto-suave)', lineHeight: 1.5, marginTop: 0 }}>
                Tem vários produtos? Baixe o modelo, preencha uma linha por oferta e envie. Aceitamos
                arquivos <strong>.csv</strong> e <strong>.xlsx</strong> (até 500 linhas). As colunas
                obrigatórias são: <strong>nome, cpf_cnpj, descricao, quantidade</strong>.
              </p>

              <button
                onClick={baixarModelo}
                style={{ background: 'var(--cinza-claro)', border: '1.5px solid var(--borda)', borderRadius: 10, padding: '10px 16px', fontFamily: 'Nunito', fontSize: 13, fontWeight: 700, color: 'var(--texto)', cursor: 'pointer', marginBottom: 16 }}
              >⬇️ Baixar modelo (CSV)</button>

              <div style={{ border: '2px dashed var(--borda)', borderRadius: 12, padding: '20px', textAlign: 'center', background: 'var(--cinza-claro)' }}>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".csv,.xlsx"
                  style={{ display: 'none' }}
                  onChange={e => { setArquivo(e.target.files?.[0] || null); setResultado(null); setErroUpload('') }}
                />
                <button
                  onClick={() => fileRef.current?.click()}
                  style={{ background: 'var(--branco)', border: '1.5px solid var(--borda)', borderRadius: 10, padding: '9px 16px', fontFamily: 'Nunito', fontSize: 13, fontWeight: 700, color: 'var(--texto)', cursor: 'pointer' }}
                >📎 Escolher arquivo</button>
                <p style={{ fontSize: 13, color: 'var(--texto-suave)', marginTop: 10, marginBottom: 0 }}>
                  {arquivo ? `Selecionado: ${arquivo.name}` : 'Nenhum arquivo selecionado'}
                </p>
              </div>

              <button
                onClick={enviarPlanilha}
                disabled={!arquivo || enviando}
                style={{ width: '100%', marginTop: 16, background: arquivo && !enviando ? 'var(--verde)' : 'var(--cinza)', color: '#fff', border: 'none', borderRadius: 10, padding: '12px', fontFamily: 'Nunito', fontSize: 14, fontWeight: 800, cursor: arquivo && !enviando ? 'pointer' : 'not-allowed', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
              >
                {enviando ? <><span className="spinner" /> Enviando...</> : '🚀 Enviar ofertas'}
              </button>

              {erroUpload && (
                <div style={{ marginTop: 16, background: '#fdecea', border: '1px solid #f5c6cb', color: '#a02622', borderRadius: 10, padding: '12px 14px', fontSize: 13 }}>
                  ⚠️ {erroUpload}
                </div>
              )}

              {resultado && (
                <div style={{ marginTop: 16 }}>
                  <div style={{ background: resultado.inseridas > 0 ? '#e8f5e9' : '#fff8e1', border: '1px solid var(--borda)', borderRadius: 10, padding: '12px 14px', fontSize: 14, fontWeight: 700, color: 'var(--texto)' }}>
                    ✅ {resultado.inseridas} de {resultado.total} ofertas cadastradas.
                    {resultado.erros.length > 0 && ` ${resultado.erros.length} com problema.`}
                  </div>
                  {resultado.erros.length > 0 && (
                    <div style={{ marginTop: 10, background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 10, padding: '12px 14px' }}>
                      <p style={{ fontSize: 13, fontWeight: 700, margin: '0 0 6px', color: 'var(--texto)' }}>Linhas com problema:</p>
                      <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: 'var(--texto-suave)' }}>
                        {resultado.erros.map((e, i) => (
                          <li key={i} style={{ marginBottom: 4 }}>Linha {e.linha}: {e.motivo}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {resultado.inseridas > 0 && (
                    <p style={{ fontSize: 13, color: 'var(--texto-suave)', marginTop: 10 }}>
                      As ofertas já aparecem na página <strong>Ofertas</strong> para a prefeitura consultar.
                      Evite reenviar o mesmo arquivo para não duplicar os cadastros.
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function tabStyle(active: boolean): React.CSSProperties {
  return {
    flex: '1 1 auto',
    minWidth: 180,
    background: active ? 'var(--verde)' : 'var(--cinza-claro)',
    color: active ? '#fff' : 'var(--texto)',
    border: active ? 'none' : '1.5px solid var(--borda)',
    borderRadius: 10,
    padding: '10px 14px',
    fontFamily: 'Nunito',
    fontSize: 13,
    fontWeight: 800,
    cursor: 'pointer',
  }
}
