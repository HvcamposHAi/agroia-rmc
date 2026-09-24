import { useEffect, useRef, useState } from 'react'
import { Mic, SlidersHorizontal, Square, Volume2, VolumeX } from 'lucide-react'
import type { Voz } from '../lib/useVoz'
import { defineMessages, useT } from '../i18n'

const MSG = defineMessages({
  pt: {
    pararLer: 'Parar de ler as respostas em voz alta',
    ler: 'Ler as respostas em voz alta',
    pararOuvir: 'Parar de ouvir',
    falar: 'Falar a pergunta',
    ouvindo: '🎙️ Ouvindo… fale sua pergunta. Ela é enviada quando você parar de falar.',
    lendo: '🔊 Lendo a resposta…',
    parar: 'parar',
    pararBtn: '⏹ Parar',
    ouvir: '🔊 Ouvir',
    configurar: 'Escolher voz e velocidade',
    voz: 'Voz',
    automatica: 'Automática (a mais natural disponível)',
    naturais: 'Vozes naturais',
    doNavegador: 'Vozes deste navegador',
    velocidade: 'Velocidade',
    testar: '▶ Testar voz',
    amostra: 'Olá! Eu sou o assistente do AgroIA. O tomate está custando 4 reais e 50 centavos o quilo na Ceasa de Curitiba.',
    dicaEdge: 'Dica: no Microsoft Edge aparecem vozes naturais (Francisca, Antônio), bem menos robóticas.',
  },
  en: {
    pararLer: 'Stop reading answers aloud',
    ler: 'Read answers aloud',
    pararOuvir: 'Stop listening',
    falar: 'Speak your question',
    ouvindo: '🎙️ Listening… say your question. It is sent when you stop talking.',
    lendo: '🔊 Reading the answer…',
    parar: 'stop',
    pararBtn: '⏹ Stop',
    ouvir: '🔊 Listen',
    configurar: 'Choose voice and speed',
    voz: 'Voice',
    automatica: 'Automatic (most natural available)',
    naturais: 'Natural voices',
    doNavegador: 'Voices in this browser',
    velocidade: 'Speed',
    testar: '▶ Test voice',
    amostra: "Hi! I'm the AgroIA assistant. Tomatoes cost 4 reais and 50 cents per kilogram at the Curitiba wholesale market.",
    dicaEdge: 'Tip: Microsoft Edge offers natural voices (e.g. Ava, Andrew) that sound much less robotic.',
  },
  es: {
    pararLer: 'Dejar de leer las respuestas en voz alta',
    ler: 'Leer las respuestas en voz alta',
    pararOuvir: 'Dejar de escuchar',
    falar: 'Decir la pregunta',
    ouvindo: '🎙️ Escuchando… diga su pregunta. Se envía cuando deje de hablar.',
    lendo: '🔊 Leyendo la respuesta…',
    parar: 'detener',
    pararBtn: '⏹ Detener',
    ouvir: '🔊 Escuchar',
    configurar: 'Elegir voz y velocidad',
    voz: 'Voz',
    automatica: 'Automática (la más natural disponible)',
    naturais: 'Voces naturales',
    doNavegador: 'Voces de este navegador',
    velocidade: 'Velocidad',
    testar: '▶ Probar voz',
    amostra: '¡Hola! Soy el asistente de AgroIA. El tomate cuesta 4 reales y 50 centavos el kilo en la Ceasa de Curitiba.',
    dicaEdge: 'Consejo: en Microsoft Edge hay voces naturales (Elvira, Álvaro), mucho menos robóticas.',
  },
})

interface BotoesVozProps {
  voz: Voz
  disabled?: boolean
  onParcial: (texto: string) => void
  onFinal: (texto: string) => void
}

// Microfone (fala → pergunta) + alternador "ler respostas em voz alta".
// Fica dentro da caixa de digitação de cada chat, ao lado do botão enviar.
export function BotoesVoz({ voz, disabled, onParcial, onFinal }: BotoesVozProps) {
  const t = useT(MSG)
  return (
    <>
      <ConfigVoz voz={voz} />
      {voz.suportaFalar && (
        <button
          type="button"
          className={`voz-btn${voz.lerRespostas ? ' ligado' : ''}`}
          onClick={() => voz.setLerRespostas(!voz.lerRespostas)}
          title={voz.lerRespostas ? t('pararLer') : t('ler')}
          aria-pressed={voz.lerRespostas}
        >
          {voz.lerRespostas ? <Volume2 size={16} /> : <VolumeX size={16} />}
        </button>
      )}
      {voz.suportaOuvir && (
        <button
          type="button"
          className={`voz-btn${voz.ouvindo ? ' ouvindo' : ''}`}
          onClick={() => (voz.ouvindo ? voz.pararEscuta() : voz.iniciarEscuta({ onParcial, onFinal }))}
          disabled={disabled && !voz.ouvindo}
          title={voz.ouvindo ? t('pararOuvir') : t('falar')}
          aria-pressed={voz.ouvindo}
        >
          {voz.ouvindo ? <Square size={14} /> : <Mic size={16} />}
        </button>
      )}
    </>
  )
}

// Linha de estado abaixo da caixa: "ouvindo", "lendo" ou erro do microfone.
export function AvisoVoz({ voz }: { voz: Voz }) {
  const t = useT(MSG)
  if (voz.erro) return <p className="voz-aviso erro">{voz.erro}</p>
  if (voz.ouvindo) return <p className="voz-aviso">{t('ouvindo')}</p>
  if (voz.falandoId) {
    return (
      <p className="voz-aviso">
        {t('lendo')}{' '}
        <button type="button" className="voz-link" onClick={voz.pararFala}>{t('parar')}</button>
      </p>
    )
  }
  return null
}

// Botão "Ouvir" em cada resposta do assistente.
export function OuvirResposta({ voz, id, texto }: { voz: Voz; id: string; texto: string }) {
  const t = useT(MSG)
  if (!voz.suportaFalar || !texto.trim()) return null
  const tocando = voz.falandoId === id
  return (
    <button
      type="button"
      className="voz-link msg-ouvir"
      onClick={() => (tocando ? voz.pararFala() : voz.falar(texto, id))}
    >
      {tocando ? t('pararBtn') : t('ouvir')}
    </button>
  )
}

// Painel "voz e velocidade": vozes neurais do servidor (quando configuradas)
// e as do navegador, da mais natural para a mais robótica. Preferência salva.
function ConfigVoz({ voz }: { voz: Voz }) {
  const t = useT(MSG)
  const [aberto, setAberto] = useState(false)
  const caixaRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!aberto) return
    const fora = (e: MouseEvent) => {
      if (!caixaRef.current?.contains(e.target as Node)) setAberto(false)
    }
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setAberto(false) }
    document.addEventListener('mousedown', fora)
    document.addEventListener('keydown', esc)
    return () => {
      document.removeEventListener('mousedown', fora)
      document.removeEventListener('keydown', esc)
    }
  }, [aberto])

  const temNeural = voz.neuralDisponivel && voz.vozesNeurais.length > 0
  if (!temNeural && !voz.suportaFalar) return null
  const semVozNatural = !temNeural && !voz.vozesNavegador.some(v => /natural|neural|online/i.test(v.name))

  return (
    <div className="voz-config" ref={caixaRef}>
      <button
        type="button"
        className={`voz-btn${aberto ? ' ligado' : ''}`}
        onClick={() => setAberto(a => !a)}
        title={t('configurar')}
        aria-label={t('configurar')}
        aria-expanded={aberto}
      >
        <SlidersHorizontal size={16} />
      </button>
      {aberto && (
        <div className="voz-painel" role="dialog" aria-label={t('configurar')}>
          <label>
            {t('voz')}
            <select value={voz.vozEscolhida} onChange={e => voz.setVozEscolhida(e.target.value)}>
              <option value="auto">{t('automatica')}</option>
              {temNeural && (
                <optgroup label={t('naturais')}>
                  {voz.vozesNeurais.map(v => <option key={v.id} value={`neural:${v.id}`}>{v.nome}</option>)}
                </optgroup>
              )}
              {voz.vozesNavegador.length > 0 && (
                <optgroup label={t('doNavegador')}>
                  {voz.vozesNavegador.map(v => <option key={v.voiceURI} value={`nav:${v.voiceURI}`}>{v.name}</option>)}
                </optgroup>
              )}
            </select>
          </label>
          <label>
            {t('velocidade')} · {voz.velocidade.toFixed(2).replace(/0$/, '')}×
            <input
              type="range" min={0.8} max={1.3} step={0.05}
              value={voz.velocidade}
              onChange={e => voz.setVelocidade(Number(e.target.value))}
            />
          </label>
          <button type="button" className="voz-testar" onClick={() => voz.falar(t('amostra'), 'teste')}>
            {voz.falandoId === 'teste' ? '…' : t('testar')}
          </button>
          {semVozNatural && <p className="voz-dica">{t('dicaEdge')}</p>}
        </div>
      )}
    </div>
  )
}
