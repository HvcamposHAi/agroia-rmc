import { useState, useRef, useEffect } from 'react'
import { Tractor, Info, MessageSquare, FileSpreadsheet, Download, Paperclip, Upload, CircleAlert, CircleCheck, TriangleAlert, Leaf, Carrot, Users } from 'lucide-react'
import MensagemChat, { StatusChat } from '../components/MensagemChat'
import { BotoesVoz, AvisoVoz } from '../components/VozControles'
import { streamPost, uploadOfertasPlanilha } from '../lib/apiClient'
import type { SSEEvent, UploadOfertasResult } from '../lib/apiClient'
import { useVoz } from '../lib/useVoz'
import { defineMessages, useI18n, useT } from '../i18n'
import type { Lang } from '../i18n'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

const SUGESTOES: Record<Lang, string[]> = {
  pt: [
    'Tenho 200 kg de alface crespa para março, quero R$ 4/kg',
    'Quero cadastrar tomate italiano, 500 kg, o ano todo',
    'Sou cooperativa e tenho cenoura disponível',
  ],
  en: [
    'I have 200 kg of curly lettuce for March, asking R$ 4/kg',
    'I want to register Italian tomatoes, 500 kg, all year round',
    'We are a cooperative and have carrots available',
  ],
  es: [
    'Tengo 200 kg de lechuga crespa para marzo, quiero R$ 4/kg',
    'Quiero registrar tomate italiano, 500 kg, todo el año',
    'Somos una cooperativa y tenemos zanahoria disponible',
  ],
}

const MSG = defineMessages({
  pt: {
    processando: 'Processando…',
    processandoPadrao: 'Processando…',
    erroConexao: 'Não foi possível conectar ao servidor. Tente novamente em instantes.',
    erroUpload: 'Não foi possível enviar a planilha. Verifique o arquivo e tente novamente.',
    abaChat: 'Conversar com o assistente',
    abaPlanilha: 'Enviar planilha',
    boasVindasTitulo: 'Cadastre o que você tem para vender',
    boasVindas1: 'Você pode cadastrar de duas formas: ',
    boasVindasForte1: 'conversando com o assistente',
    boasVindas2: ' aqui (informe produtos, quantidades e quando estarão disponíveis) ou, se tiver vários itens, enviando uma ',
    boasVindasForte2: 'planilha',
    boasVindas3: ' na aba “Enviar planilha”. A prefeitura poderá consultar suas ofertas. É rápido e não precisa de senha.',
    ouvindo: 'Ouvindo…',
    placeholder: 'Ex: tenho 200 kg de alface para março, quero R$ 4 o kg...',
    rodape: 'Cadastro de ofertas da agricultura familiar · as respostas do assistente são geradas por IA',
    disclosure: 'Você está conversando com um assistente de inteligência artificial. Ele organiza sua oferta e pede confirmação antes de cadastrar.',
    planilhaTitulo: 'Enviar planilha de ofertas',
    planilha1: 'Tem vários produtos? Baixe o modelo, preencha uma linha por oferta e envie. Aceitamos arquivos ',
    planilhaE: ' e ',
    planilha2: ' (até 500 linhas). As colunas obrigatórias são: ',
    baixarModelo: 'Baixar modelo (CSV)',
    escolherArquivo: 'Escolher arquivo',
    selecionado: 'Selecionado: {nome}',
    nenhumArquivo: 'Nenhum arquivo selecionado',
    enviando: 'Enviando...',
    enviarOfertas: 'Enviar ofertas',
    resultado: '{n} de {total} ofertas cadastradas.',
    comProblema: ' {n} com problema.',
    linhasProblema: 'Linhas com problema:',
    linha: 'Linha {n}:',
    sucesso1: 'As ofertas já podem ser consultadas pela prefeitura no ',
    sucessoPagina: 'Assistente',
    sucesso2: '. Evite reenviar o mesmo arquivo para não duplicar os cadastros.',
  },
  en: {
    processando: 'Processing…',
    processandoPadrao: 'Processing…',
    erroConexao: 'Could not connect to the server. Please try again shortly.',
    erroUpload: 'Could not upload the spreadsheet. Check the file and try again.',
    abaChat: 'Chat with the assistant',
    abaPlanilha: 'Upload spreadsheet',
    boasVindasTitulo: 'Register what you have to sell',
    boasVindas1: 'You can register in two ways: ',
    boasVindasForte1: 'chatting with the assistant',
    boasVindas2: ' here (tell us the products, quantities and when they will be available) or, if you have many items, by uploading a ',
    boasVindasForte2: 'spreadsheet',
    boasVindas3: ' in the “Upload spreadsheet” tab. The city will be able to see your offers. It is quick and needs no password.',
    ouvindo: 'Listening…',
    placeholder: 'E.g.: I have 200 kg of lettuce for March, asking R$ 4 per kg...',
    rodape: 'Family-farming offer registration · assistant answers are AI-generated',
    disclosure: 'You are chatting with an artificial intelligence assistant. It organizes your offer and asks for confirmation before registering it.',
    planilhaTitulo: 'Upload offers spreadsheet',
    planilha1: 'Have many products? Download the template, fill in one row per offer and upload it. We accept ',
    planilhaE: ' and ',
    planilha2: ' files (up to 500 rows). Required columns: ',
    baixarModelo: 'Download template (CSV)',
    escolherArquivo: 'Choose file',
    selecionado: 'Selected: {nome}',
    nenhumArquivo: 'No file selected',
    enviando: 'Uploading...',
    enviarOfertas: 'Submit offers',
    resultado: '{n} of {total} offers registered.',
    comProblema: ' {n} with problems.',
    linhasProblema: 'Rows with problems:',
    linha: 'Row {n}:',
    sucesso1: 'The city can now look up the offers in the ',
    sucessoPagina: 'Assistant',
    sucesso2: '. Avoid re-uploading the same file to prevent duplicate entries.',
  },
  es: {
    processando: 'Procesando…',
    processandoPadrao: 'Procesando…',
    erroConexao: 'No fue posible conectar con el servidor. Inténtelo de nuevo en unos instantes.',
    erroUpload: 'No fue posible enviar la planilla. Verifique el archivo e inténtelo de nuevo.',
    abaChat: 'Conversar con el asistente',
    abaPlanilha: 'Enviar planilla',
    boasVindasTitulo: 'Registre lo que tiene para vender',
    boasVindas1: 'Puede registrar de dos formas: ',
    boasVindasForte1: 'conversando con el asistente',
    boasVindas2: ' aquí (indique productos, cantidades y cuándo estarán disponibles) o, si tiene varios artículos, enviando una ',
    boasVindasForte2: 'planilla',
    boasVindas3: ' en la pestaña “Enviar planilla”. La alcaldía podrá consultar sus ofertas. Es rápido y no necesita contraseña.',
    ouvindo: 'Escuchando…',
    placeholder: 'Ej.: tengo 200 kg de lechuga para marzo, quiero R$ 4 el kg...',
    rodape: 'Registro de ofertas de la agricultura familiar · las respuestas del asistente son generadas por IA',
    disclosure: 'Está conversando con un asistente de inteligencia artificial. Organiza su oferta y pide confirmación antes de registrarla.',
    planilhaTitulo: 'Enviar planilla de ofertas',
    planilha1: '¿Tiene varios productos? Descargue el modelo, complete una fila por oferta y envíela. Aceptamos archivos ',
    planilhaE: ' y ',
    planilha2: ' (hasta 500 filas). Las columnas obligatorias son: ',
    baixarModelo: 'Descargar modelo (CSV)',
    escolherArquivo: 'Elegir archivo',
    selecionado: 'Seleccionado: {nome}',
    nenhumArquivo: 'Ningún archivo seleccionado',
    enviando: 'Enviando...',
    enviarOfertas: 'Enviar ofertas',
    resultado: '{n} de {total} ofertas registradas.',
    comProblema: ' {n} con problemas.',
    linhasProblema: 'Filas con problemas:',
    linha: 'Fila {n}:',
    sucesso1: 'La alcaldía ya puede consultar las ofertas en el ',
    sucessoPagina: 'Asistente',
    sucesso2: '. Evite reenviar el mismo archivo para no duplicar los registros.',
  },
})

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
  const { lang } = useI18n()
  const t = useT(MSG)

  // ── Estado do chat ──
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [statusMsg, setStatusMsg] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const voz = useVoz()

  // ── Estado da planilha ──
  const [arquivo, setArquivo] = useState<File | null>(null)
  const [enviando, setEnviando] = useState(false)
  const [resultado, setResultado] = useState<UploadOfertasResult | null>(null)
  const [erroUpload, setErroUpload] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading, statusMsg])

  // porVoz: o produtor falou no microfone → a resposta também é lida em voz alta.
  const send = async (text: string, porVoz = false) => {
    const trimmed = text.trim()
    if (!trimmed || loading) return
    voz.pararFala()
    const idResposta = `msg-${messages.length + 1}`
    const lerEmVoz = porVoz || voz.lerRespostas

    const userMsg: Message = { role: 'user', content: trimmed }
    const historico = messages.slice(-8)
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)
    setStatusMsg(t('processando'))

    try {
      const assistantMsg: Message = { role: 'assistant', content: '' }
      setMessages(prev => [...prev, assistantMsg])

      let full = ''
      for await (const event of streamPost<SSEEvent>('/produtor/chat/stream', {
        pergunta: trimmed,
        historico,
      })) {
        if (event.tipo === 'status') {
          setStatusMsg(event.msg || t('processandoPadrao'))
        } else if (event.tipo === 'token') {
          full += event.texto || ''
          setMessages(prev => {
            const updated = [...prev]
            updated[updated.length - 1].content = full
            return updated
          })
        } else if (event.tipo === 'fim') {
          setStatusMsg('')
          if (lerEmVoz) voz.falar(full, idResposta)
        }
      }
    } catch (err) {
      console.error('Stream error:', err)
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
      setErroUpload(detail || t('erroUpload'))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="chat-container">
      {/* Forma de cadastro: conversa guiada ou planilha (vários itens) */}
      <div className="tabs-bar">
        <div className="seg-control" role="tablist">
          <button role="tab" aria-selected={aba === 'chat'} className={`seg-btn${aba === 'chat' ? ' active' : ''}`} onClick={() => setAba('chat')}>
            <MessageSquare size={15} aria-hidden /> {t('abaChat')}
          </button>
          <button role="tab" aria-selected={aba === 'planilha'} className={`seg-btn${aba === 'planilha' ? ' active' : ''}`} onClick={() => { voz.pararFala(); setAba('planilha') }}>
            <FileSpreadsheet size={15} aria-hidden /> {t('abaPlanilha')}
          </button>
        </div>
      </div>

      {aba === 'chat' ? (
        <>
          <div className="chat-messages">
            {messages.length === 0 && (
              <div className="chat-welcome">
                <span className="welcome-icon" aria-hidden><Tractor size={28} /></span>
                <h3>{t('boasVindasTitulo')}</h3>
                <p>
                  {t('boasVindas1')}<strong>{t('boasVindasForte1')}</strong>{t('boasVindas2')}
                  <strong>{t('boasVindasForte2')}</strong>{t('boasVindas3')}
                </p>
                <p className="ai-disclosure"><Info size={15} aria-hidden /> {t('disclosure')}</p>
                <div className="suggestions">
                  {SUGESTOES[lang].map((s, i) => {
                    const Icon = [Leaf, Carrot, Users][i % 3]
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
                className="chat-input"
                rows={1}
                aria-label={t('placeholder')}
                placeholder={voz.ouvindo ? t('ouvindo') : t('placeholder')}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKey}
              />
              <BotoesVoz voz={voz} disabled={loading} onParcial={setInput} onFinal={t => send(t, true)} />
              <button className="send-btn" onClick={() => send(input)} disabled={!input.trim() || loading} aria-label={t('enviarOfertas')}>
                <svg viewBox="0 0 24 24"><path d="M2 21l21-9L2 3v7l15 2-15 2v7z"/></svg>
              </button>
            </div>
            <AvisoVoz voz={voz} />
            <p className="chat-rodape">{t('rodape')}</p>
          </div>
        </>
      ) : (
        <div className="chat-messages" style={{ display: 'block' }}>
          <div className="card" style={{ maxWidth: 680, margin: '0 auto' }}>
            <h2 className="page-title" style={{ fontSize: 20 }}>{t('planilhaTitulo')}</h2>
            <p className="page-subtitle" style={{ marginBottom: 16 }}>
              {t('planilha1')}<strong>.csv</strong>{t('planilhaE')}<strong>.xlsx</strong>{t('planilha2')}
              <strong>nome, cpf_cnpj, descricao, quantidade</strong>.
            </p>

            <button className="btn btn-secundario" onClick={baixarModelo} style={{ marginBottom: 16 }}>
              <Download size={16} aria-hidden /> {t('baixarModelo')}
            </button>

            <div style={{ border: '2px dashed var(--borda-forte)', borderRadius: 'var(--raio)', padding: 20, textAlign: 'center', background: 'var(--cinza-claro)' }}>
              <input
                ref={fileRef}
                type="file"
                accept=".csv,.xlsx"
                style={{ display: 'none' }}
                onChange={e => { setArquivo(e.target.files?.[0] || null); setResultado(null); setErroUpload('') }}
              />
              <button className="btn btn-secundario" onClick={() => fileRef.current?.click()}>
                <Paperclip size={16} aria-hidden /> {t('escolherArquivo')}
              </button>
              <p style={{ fontSize: 13, color: 'var(--texto-suave)', marginTop: 10 }}>
                {arquivo ? t('selecionado', { nome: arquivo.name }) : t('nenhumArquivo')}
              </p>
            </div>

            <button className="btn btn-primario" onClick={enviarPlanilha} disabled={!arquivo || enviando} style={{ width: '100%', marginTop: 16, padding: 12 }}>
              {enviando ? <><span className="spinner" /> {t('enviando')}</> : <><Upload size={16} aria-hidden /> {t('enviarOfertas')}</>}
            </button>

            {erroUpload && (
              <div className="aviso-box erro" style={{ marginTop: 16 }}>
                <CircleAlert size={17} aria-hidden /> <span>{erroUpload}</span>
              </div>
            )}

            {resultado && (
              <div style={{ marginTop: 16 }}>
                <div className={`aviso-box ${resultado.inseridas > 0 ? 'ok' : 'aviso'}`} style={{ fontWeight: 600 }}>
                  {resultado.inseridas > 0 ? <CircleCheck size={17} aria-hidden /> : <TriangleAlert size={17} aria-hidden />}
                  <span>
                    {t('resultado', { n: resultado.inseridas, total: resultado.total })}
                    {resultado.erros.length > 0 && t('comProblema', { n: resultado.erros.length })}
                  </span>
                </div>
                {resultado.erros.length > 0 && (
                  <div className="card" style={{ marginTop: 10, padding: '12px 14px', boxShadow: 'none' }}>
                    <p style={{ fontSize: 13, fontWeight: 700, margin: '0 0 6px' }}>{t('linhasProblema')}</p>
                    <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: 'var(--texto-suave)' }}>
                      {resultado.erros.map((e, i) => (
                        <li key={i} style={{ marginBottom: 4 }}>{t('linha', { n: e.linha })} {e.motivo}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {resultado.inseridas > 0 && (
                  <p style={{ fontSize: 13, color: 'var(--texto-suave)', marginTop: 10 }}>
                    {t('sucesso1')}<strong>{t('sucessoPagina')}</strong>{t('sucesso2')}
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
