import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { defineMessages, langInfo, useI18n, useT } from '../i18n'
import type { Lang } from '../i18n'
import { apiClient } from './apiClient'

// Conversa por voz nos chats.
// - Ouvir: SpeechRecognition do navegador (Chrome/Edge/Safari; o Firefox não
//   tem — lá o microfone some).
// - Falar: voz neural do servidor (Azure, via /voz/tts — soa humana) quando
//   configurada; senão, ou se falhar no meio, a voz do próprio navegador
//   (speechSynthesis), priorizando as vozes "Natural/Online" do Edge.

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
const CHAVE_VEL = 'agroia_voz_velocidade'
const chaveVoz = (lang: Lang) => `agroia_voz_${lang}`

// ── Voz neural do servidor ──────────────────────────────────────────────
export interface VozNeural { id: string; nome: string }
interface StatusNeural { neural: boolean; vozes: Partial<Record<Lang, VozNeural[]>> }

const SEM_NEURAL: StatusNeural = { neural: false, vozes: {} }
let statusNeural: Promise<StatusNeural> | null = null
let neuralFalhou = false  // falhou nesta sessão (cota, chave, rede) → não insistir

function carregarStatusNeural(): Promise<StatusNeural> {
  statusNeural ??= apiClient.get<StatusNeural>('/voz/status')
    .then(r => r.data)
    .catch(() => SEM_NEURAL)
  return statusNeural
}

function lerStorage(chave: string): string | null {
  try { return localStorage.getItem(chave) } catch { return null }
}
function gravarStorage(chave: string, valor: string) {
  try { localStorage.setItem(chave, valor) } catch { /* sem storage: só nesta sessão */ }
}

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

// Siglas lidas como palavra (em maiúsculas, algumas vozes soletram).
const SIGLAS_PALAVRA: Record<string, string> = { CEASA: 'Ceasa', CEASAS: 'Ceasas', CONAB: 'Conab', PROHORT: 'Prohort' }
// Estas ficam como estão (a voz decide; em geral soletra ou já conhece).
const SIGLAS_SOLETRADAS = new Set(['SMSAN', 'CNPJ', 'PNAE', 'FAAC'])

function reais(int: string, cent: string | undefined, lang: Lang): string {
  const [um, varios, centavo, centavos, e] = lang === 'es'
    ? ['real', 'reales', 'centavo', 'centavos', 'y']
    : lang === 'en' ? ['real', 'reais', 'cent', 'cents', 'and'] : ['real', 'reais', 'centavo', 'centavos', 'e']
  const moeda = int === '1' ? um : varios
  const c = cent ? Number(cent) : 0
  return c ? `${int} ${moeda} ${e} ${c} ${c === 1 ? centavo : centavos}` : `${int} ${moeda}`
}

// Ajusta o que as vozes leem ao pé da letra ("R$ 4,50/kg", "CEASA", "cx").
export function normalizarFala(texto: string, lang: Lang = 'pt'): string {
  const [porQuilo, quilos] = lang === 'en' ? ['per kilogram', 'kilograms'] : lang === 'es' ? ['por kilo', 'kilos'] : ['o quilo', 'quilos']
  return texto
    .replace(/R\$\s?\/\s?kg\b/gi, lang === 'en' ? 'reais per kilogram' : lang === 'es' ? 'reales por kilo' : 'reais por quilo')
    .replace(lang === 'en' ? /R\$\s?(\d{1,3}(?:,\d{3})+|\d+)\.(\d{2})\b/g : /R\$\s?(\d{1,3}(?:\.\d{3})+|\d+),(\d{2})\b/g,
      (_, i: string, c: string) => reais(i, c, lang))
    .replace(/R\$\s?(\d[\d.,]*\d|\d)/g, (_, i: string) => reais(i, undefined, lang))
    .replace(/\s?\/\s?kg\b/gi, ` ${porQuilo}`)
    .replace(/(\d)\s?kg\b/gi, `$1 ${quilos}`)
    .replace(/\bkg\b/gi, quilos)
    .replace(/\bcx\b\.?(\s?\d)?/gi, (_, n?: string) =>
      (lang === 'en' ? 'box' : lang === 'es' ? 'caja' : 'caixa') + (n ? `${lang === 'en' ? ' of' : ' de'} ${n.trim()}` : ''))
    .replace(/\bn[º°]\s?/gi, lang === 'en' ? 'number ' : 'número ')
    .replace(/(?<![\p{L}\d])\p{Lu}{4,}(?![\p{L}\d])/gu, w =>
      SIGLAS_PALAVRA[w] ?? (SIGLAS_SOLETRADAS.has(w) ? w : w.charAt(0) + w.slice(1).toLowerCase()))
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

// Vozes do navegador para o idioma, das mais humanas para as mais robóticas:
// "Natural"/"Online" (neurais do Edge) > Google > vozes locais do Windows.
function vozesDoNavegador(lang: string): SpeechSynthesisVoice[] {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) return []
  const prefixo = lang.slice(0, 2)
  const nota = (v: SpeechSynthesisVoice) =>
    (v.lang.replace('_', '-') === lang ? 10 : 0) +
    (/natural|neural/i.test(v.name) ? 6 : 0) +
    (/online/i.test(v.name) ? 3 : 0) +
    (/google/i.test(v.name) ? 2 : 0) +
    (v.localService ? 0 : 1)
  return window.speechSynthesis.getVoices()
    .filter(v => v.lang.replace('_', '-').startsWith(prefixo))
    .sort((a, b) => nota(b) - nota(a))
}

function lerPreferencia(): boolean {
  try { return localStorage.getItem(CHAVE_LER) === '1' } catch { return false }
}

function lerVelocidade(): number {
  const v = Number(lerStorage(CHAVE_VEL))
  return v >= 0.7 && v <= 1.4 ? v : 1
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
  const [status, setStatus] = useState<StatusNeural>(SEM_NEURAL)
  const [vozesNavegador, setVozesNavegador] = useState<SpeechSynthesisVoice[]>(() => vozesDoNavegador(LANG))
  // 'auto' | 'neural:<id Azure>' | 'nav:<voiceURI>'
  const [vozEscolhida, setVozEscolhidaState] = useState(() => lerStorage(chaveVoz(lang)) ?? 'auto')
  const [velocidade, setVelocidadeState] = useState(lerVelocidade)
  // A escolha de voz é por idioma: trocar o idioma recarrega a preferência.
  const [langDaVoz, setLangDaVoz] = useState(lang)
  if (langDaVoz !== lang) {
    setLangDaVoz(lang)
    setVozEscolhidaState(lerStorage(chaveVoz(lang)) ?? 'auto')
  }
  const recRef = useRef<Reconhecedor | null>(null)
  const geracaoRef = useRef(0)                       // cada fala nova invalida a anterior
  const audioRef = useRef<{ audio: HTMLAudioElement; fim: () => void } | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const neuralDisponivel = status.neural && !neuralFalhou
  const vozesNeurais = useMemo(() => status.vozes[lang] ?? [], [status, lang])

  const setVozEscolhida = useCallback((v: string) => {
    setVozEscolhidaState(v)
    gravarStorage(chaveVoz(lang), v)
  }, [lang])

  const setVelocidade = useCallback((v: number) => {
    setVelocidadeState(v)
    gravarStorage(CHAVE_VEL, String(v))
  }, [])

  // Interrompe qualquer fala em curso (neural ou do navegador).
  const cancelarTudo = useCallback(() => {
    geracaoRef.current++
    abortRef.current?.abort()
    abortRef.current = null
    if (audioRef.current) {
      audioRef.current.audio.pause()
      audioRef.current.fim()
      audioRef.current = null
    }
    if (suportaFalar) window.speechSynthesis.cancel()
  }, [suportaFalar])

  const setLerRespostas = useCallback((v: boolean) => {
    setLerRespostasState(v)
    gravarStorage(CHAVE_LER, v ? '1' : '0')
    if (!v) {
      cancelarTudo()
      setFalandoId(null)
    }
  }, [cancelarTudo])

  const pararFala = useCallback(() => {
    cancelarTudo()
    setFalandoId(null)
  }, [cancelarTudo])

  const falarNoNavegador = useCallback((texto: string, geracao: number, terminar: () => void) => {
    if (!suportaFalar || geracao !== geracaoRef.current) { terminar(); return }
    const lista = vozesDoNavegador(LANG)
    const voz = (vozEscolhida.startsWith('nav:') && lista.find(v => v.voiceURI === vozEscolhida.slice(4))) || lista[0]
    const partes = partirEmFrases(texto)
    partes.forEach((parte, i) => {
      const u = new SpeechSynthesisUtterance(parte)
      u.lang = LANG
      u.rate = velocidade
      if (voz) u.voice = voz
      if (i === partes.length - 1) u.onend = terminar
      u.onerror = terminar
      window.speechSynthesis.speak(u)
    })
  }, [suportaFalar, LANG, vozEscolhida, velocidade])

  // Toca um MP3; resolve true ao terminar, false se o navegador bloquear o áudio.
  const tocar = useCallback((blob: Blob) => new Promise<boolean>(resolve => {
    const url = URL.createObjectURL(blob)
    const audio = new Audio(url)
    let feito = false
    const fim = (ok: boolean) => {
      if (feito) return
      feito = true
      URL.revokeObjectURL(url)
      resolve(ok)
    }
    audioRef.current = { audio, fim: () => fim(true) }
    audio.onended = () => fim(true)
    audio.onerror = () => fim(false)
    audio.play().catch(() => fim(false))
  }), [])

  const falarNeural = useCallback(async (texto: string, vozId: string, geracao: number, terminar: () => void) => {
    const partes = partirEmFrases(texto, 400)
    const ctrl = new AbortController()
    abortRef.current = ctrl
    const baixar = (p: string) => apiClient
      .post<Blob>('/voz/tts', { texto: p, voz: vozId, velocidade }, { responseType: 'blob', signal: ctrl.signal })
      .then(r => r.data)

    let proximo = baixar(partes[0])
    for (let i = 0; i < partes.length; i++) {
      let blob: Blob
      try {
        blob = await proximo
      } catch {
        if (geracao !== geracaoRef.current) return
        neuralFalhou = true  // cota/chave/rede: o resto da sessão usa o navegador
        falarNoNavegador(partes.slice(i).join(' '), geracao, terminar)
        return
      }
      if (geracao !== geracaoRef.current) return
      if (i + 1 < partes.length) {
        proximo = baixar(partes[i + 1])   // baixa o próximo trecho enquanto este toca
        proximo.catch(() => {})
      }
      const ok = await tocar(blob)
      if (geracao !== geracaoRef.current) return
      if (!ok) {  // navegador bloqueou o áudio (autoplay): segue com a voz dele
        falarNoNavegador(partes.slice(i).join(' '), geracao, terminar)
        return
      }
    }
    terminar()
  }, [velocidade, tocar, falarNoNavegador])

  const falar = useCallback((markdown: string, id = 'fala') => {
    cancelarTudo()
    const geracao = geracaoRef.current
    const texto = normalizarFala(textoParaFala(markdown, t('tabela')), lang)
    if (!texto) { setFalandoId(null); return }
    const terminar = () => {
      if (geracao === geracaoRef.current) setFalandoId(atual => (atual === id ? null : atual))
    }
    let vozNeural: string | null = null
    if (status.neural && !neuralFalhou && !vozEscolhida.startsWith('nav:')) {
      const pedida = vozEscolhida.startsWith('neural:') ? vozEscolhida.slice(7) : ''
      vozNeural = vozesNeurais.find(v => v.id === pedida)?.id ?? vozesNeurais[0]?.id ?? null
    }
    if (!vozNeural && !suportaFalar) return
    setFalandoId(id)
    if (vozNeural) void falarNeural(texto, vozNeural, geracao, terminar)
    else falarNoNavegador(texto, geracao, terminar)
  }, [cancelarTudo, t, lang, status.neural, vozEscolhida, vozesNeurais, suportaFalar, falarNeural, falarNoNavegador])

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

  // No Chrome a lista de vozes carrega de forma assíncrona (voiceschanged).
  useEffect(() => {
    if (!suportaFalar) return
    const s = window.speechSynthesis
    const atualizar = () => setVozesNavegador(vozesDoNavegador(LANG))
    atualizar()
    s.addEventListener('voiceschanged', atualizar)
    return () => s.removeEventListener('voiceschanged', atualizar)
  }, [suportaFalar, LANG])

  useEffect(() => {
    let vivo = true
    carregarStatusNeural().then(s => { if (vivo) setStatus(s) })
    return () => { vivo = false }
  }, [])

  // Sair da página não deixa microfone aberto nem voz falando.
  useEffect(() => () => {
    recRef.current?.abort()
    cancelarTudo()
  }, [cancelarTudo])

  return {
    suportaOuvir, suportaFalar,
    ouvindo, iniciarEscuta, pararEscuta,
    falandoId, falar, pararFala,
    lerRespostas, setLerRespostas,
    neuralDisponivel, vozesNeurais, vozesNavegador,
    vozEscolhida, setVozEscolhida, velocidade, setVelocidade,
    erro,
  }
}

export type Voz = ReturnType<typeof useVoz>
