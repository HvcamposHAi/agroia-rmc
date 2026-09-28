import { Sprout, User, Sparkles } from 'lucide-react'
import ResponseRenderer from './ResponseRenderer'
import { OuvirResposta } from './VozControles'
import type { Voz } from '../lib/useVoz'
import { defineMessages, useT } from '../i18n'

const MSG = defineMessages({
  pt: { geradoIA: 'Gerado por IA', confira: 'Confira os números nas fontes antes de decidir.' },
  en: { geradoIA: 'AI-generated', confira: 'Check the figures against the sources before deciding.' },
  es: { geradoIA: 'Generado por IA', confira: 'Verifique las cifras en las fuentes antes de decidir.' },
})

interface MensagemChatProps {
  role: 'user' | 'assistant'
  content: string
  /** Resposta ainda chegando (streaming): oculta o rodapé "Gerado por IA / Ouvir". */
  emAndamento?: boolean
  voz: Voz
  id: string
}

// Uma mensagem do chat (Assistente e Produtores). Respostas do assistente levam
// o selo "Gerado por IA" (transparência — AI Act art. 50 / GOV.UK Chat).
export default function MensagemChat({ role, content, emAndamento, voz, id }: MensagemChatProps) {
  const t = useT(MSG)
  return (
    <div className={`msg ${role}`}>
      <div className="msg-avatar" aria-hidden>
        {role === 'assistant' ? <Sprout size={18} /> : <User size={17} />}
      </div>
      <div className="msg-bubble">
        {role === 'assistant' ? (
          <>
            <ResponseRenderer content={content} />
            {!emAndamento && content.trim() && (
              <div className="ai-note">
                <span className="ai-label"><Sparkles size={12} aria-hidden /> {t('geradoIA')}</span>
                <span>{t('confira')}</span>
                <OuvirResposta voz={voz} id={id} texto={content} />
              </div>
            )}
          </>
        ) : content}
      </div>
    </div>
  )
}

// Indicador de progresso enquanto o agente trabalha (mostra a etapa atual).
export function StatusChat({ msg }: { msg: string }) {
  return (
    <div className="msg assistant" role="status" aria-live="polite">
      <div className="msg-avatar" aria-hidden><Sprout size={18} /></div>
      <div className="msg-bubble" style={{ display: 'flex', alignItems: 'center', gap: 10, flex: '0 1 auto' }}>
        <span className="spinner" />
        <span style={{ color: 'var(--texto-suave)', fontSize: 13 }}>{msg}</span>
      </div>
    </div>
  )
}
