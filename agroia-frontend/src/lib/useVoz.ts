import { useCallback, useEffect, useRef, useState } from 'react'
import { defineMessages, langInfo, useI18n, useT } from '../i18n'

// Conversa por voz nos chats, usando só a Web Speech API do navegador
// (sem backend, sem custo): SpeechRecognition para ouvir a pergunta e
// speechSynthesis para ler a resposta. Reconhecimento existe no Chrome/Edge/
// Safari; no Firefox só a leitura em voz alta funciona (o microfone some).

// Tipos mínimos — o lib DOM do TypeScript não declara SpeechRecognition.
interface ResultadoFala {
  isFinal: boolean
  0: { transcript: string }
}
interface EventoResultado {
  resultIndex: number
  results: ArrayLike<ResultadoFala>
}
interface EventoErro {
  error: string
}
interface Reconhecedor {
  lang: string
  continuous: boolean
  interimResults: boolean
  onresult: ((e: EventoResultado) => void) | null
  onerror: ((e: EventoErro) => void) | null
  onend: (() => void) | null
  start(): void
  stop(): void
  abort(): void
}
type ConstrutorReconhecedor = new () => Reconhecedor

const CHAVE_LER = 'agroia_ler_respostas'

function construtorReconhecedor(): ConstrutorReconhecedor | null {
  if (typeof window === 'undefined') return null
  const w = window as unknown as {
    SpeechRecognition?: ConstrutorReconhecedor
    webkitSpeechRecognition?: ConstrutorReconhecedor
  }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

const MSG = defineMessages({
  pt: {
    'not-allowed': 'Permita o uso do microfone no navegador para falar com o assistente.',
    'audio-capture': 'Nenhum microfone encontrado.',
    'network': 'Sem conexão para reconhecer a voz. Tente novamente.',
    naoEntendeu: 'Não foi possível entender o áudio. Tente novamente.',
    semMicrofone: 'Não foi possível ativar o microfone.',
    tabela: 'A tabela está na tela.',
  },
  en: {
    'not-allowed': 'Allow microphone access in your browser to talk to the assistant.',
    'audio-capture': 'No microphone found.',
    'network': 'No connection for speech recognition. Please try again.',
    naoEntendeu: "Couldn't understand the audio. Please try again.",
    semMicrofone: "Couldn't turn on the microphone.",
    tabela: 'The table is on the screen.',
  },
  es: {
    'not-allowed': 'Permita el uso del micrófono en el navegador para hablar con el asistente.',
    'audio-capture': 'No se encontró ningún micrófono.',
    'network': 'Sin conexión para reconocer la voz. Inténtelo de nuevo.',
    naoEntendeu: 'No se pudo entender el audio. Inténtelo de nuevo.',
    semMicrofone: 'No se pudo activar el micrófono.',
    tabela: 'La tabla está en la pantalla.',
  },
})

// Converte a resposta (markdown + emojis + tabelas) em texto bom de ouvir.
export function textoParaFala(md: string, avisoTabela = MSG.pt.tabela): string {
  return md
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/(^\|.*\|[ \t]*(\n|$))+/gm, `${avisoTabela}\n`)
    .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/^#{1,6}\s*/gm, '')
    .replace(/^[ \t]*[-*+][ \t]+/gm, '')
    .replace(/[*_`~>]/g, '')
    .replace(/\p{Extended_Pictographic}|️|‍/gu, '')
    .replace(/[ \t]+$/gm, '')
    .replace(/([^.!?:;,\n])\n/g, '$1.\n')  // pausa no fim de título/item de lista
    .replace(/\n+/g, ' ')
    .replace(/\s+([.,;:!?])/g, '$1')
    .replace(/([:;,!?])\s*\./g, '$1')
    .replace(/(\.\s*){2,}/g, '. ')
    .replace(/\s{2,}/g, ' ')
    .trim()
}

// O Chrome corta falas longas (~15 s); por isso a resposta vai em frases.
function partirEmFrases(texto: string, max = 200): string[] {
  const frases = texto.match(/[^.!?;]+[.!?;]*/g) ?? [texto]
  const partes: string[] = []
  let atual = ''
  for (const f of frases) {
    if ((atual + f).length > max && atual) {
      partes.push(atual.trim())
      atual = ''
    }
    atual += f
  }
  if (atual.trim()) partes.push(atual.trim())
  return partes
}

function escolherVoz(lang: string): SpeechSynthesisVoice | undefined {
  const prefixo = lang.slice(0, 2)
  const vozes = window.speechSynthesis.getVoices()
    .map(v => ({ v, lang: v.lang.replace('_', '-') }))
    .filter(x => x.lang.startsWith(prefixo))
  return (
    vozes.find(x => x.lang === lang && /natural|online|google/i.test(x.v.name)) ??
    vozes.find(x => x.lang === lang) ??
    vozes[0]
  )?.v
}

function lerPreferencia(): boolean {
  try { return localStorage.getItem(CHAVE_LER) === '1' } catch { return false }
}

interface OpcoesEscuta {
  onParcial?: (texto: string) => void
  onFinal: (texto: string) => void
}

export function useVoz() {
  const { lang } = useI18n()
  const t = useT(MSG)
  const LANG = langInfo(lang).speech  // pt-BR | en-US | es-ES
  const suportaOuvir = construtorReconhecedor() !== null
  const suportaFalar = typeof window !== 'undefined' && 'speechSynthesis' in window

  const [ouvindo, setOuvindo] = useState(false)
  const [falandoId, setFalandoId] = useState<string | null>(null)
  const [erro, setErro] = useState('')
  const [lerRespostas, setLerRespostasState] = useState(lerPreferencia)
  const recRef = useRef<Reconhecedor | null>(null)

  const setLerRespostas = useCallback((v: boolean) => {
    setLerRespostasState(v)
    try { localStorage.setItem(CHAVE_LER, v ? '1' : '0') } catch { /* sem storage: só nesta sessão */ }
    if (!v && suportaFalar) {
      window.speechSynthesis.cancel()
      setFalandoId(null)
    }
  }, [suportaFalar])

  const pararFala = useCallback(() => {
    if (suportaFalar) window.speechSynthesis.cancel()
    setFalandoId(null)
  }, [suportaFalar])

  const falar = useCallback((markdown: string, id = 'fala') => {
    if (!suportaFalar) return
    const texto = textoParaFala(markdown, t('tabela'))
    window.speechSynthesis.cancel()
    if (!texto) { setFalandoId(null); return }
    const voz = escolherVoz(LANG)
    const partes = partirEmFrases(texto)
    partes.forEach((parte, i) => {
      const u = new SpeechSynthesisUtterance(parte)
      u.lang = LANG
      if (voz) u.voice = voz
      if (i === partes.length - 1) {
        u.onend = () => setFalandoId(atual => (atual === id ? null : atual))
      }
      u.onerror = () => setFalandoId(atual => (atual === id ? null : atual))
      window.speechSynthesis.speak(u)
    })
    setFalandoId(id)
  }, [suportaFalar, LANG, t])

  const pararEscuta = useCallback(() => {
    recRef.current?.stop()
  }, [])

  const iniciarEscuta = useCallback(({ onParcial, onFinal }: OpcoesEscuta) => {
    const Rec = construtorReconhecedor()
    if (!Rec) return
    recRef.current?.abort()
    pararFala()  // não ouvir o próprio assistente falando
    setErro('')

    const rec = new Rec()
    rec.lang = LANG
    rec.continuous = false
    rec.interimResults = true
    let final = ''

    rec.onresult = (e) => {
      let parcial = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i]
        if (r.isFinal) final += r[0].transcript
        else parcial += r[0].transcript
      }
      onParcial?.((final + parcial).trim())
    }
    rec.onerror = (e) => {
      if (e.error !== 'no-speech' && e.error !== 'aborted') {
        const chave = e.error === 'service-not-allowed' ? 'not-allowed' : e.error
        setErro(chave === 'not-allowed' || chave === 'audio-capture' || chave === 'network' ? t(chave) : t('naoEntendeu'))
      }
    }
    rec.onend = () => {
      setOuvindo(false)
      recRef.current = null
      const texto = final.trim()
      if (texto) onFinal(texto)
    }

    recRef.current = rec
    try {
      rec.start()
      setOuvindo(true)
    } catch {
      setErro(t('semMicrofone'))
    }
  }, [pararFala, LANG, t])

  // No Chrome a lista de vozes carrega de forma assíncrona; pedir cedo
  // garante que a voz do idioma escolhido já esteja disponível na primeira resposta.
  useEffect(() => {
    if (suportaFalar) window.speechSynthesis.getVoices()
  }, [suportaFalar])

  // Sair da página não deixa microfone aberto nem voz falando.
  useEffect(() => () => {
    recRef.current?.abort()
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) window.speechSynthesis.cancel()
  }, [])

  return {
    suportaOuvir, suportaFalar,
    ouvindo, iniciarEscuta, pararEscuta,
    falandoId, falar, pararFala,
    lerRespostas, setLerRespostas,
    erro,
  }
}

export type Voz = ReturnType<typeof useVoz>
