import { Mic, Square, Volume2, VolumeX } from 'lucide-react'
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
