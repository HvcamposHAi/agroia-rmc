import { useEffect, useState } from 'react'
import ResponseRenderer from './ResponseRenderer'
import {
  getConfigMotor, setMotorAtivo, compararMotores,
  type MotorInfo, type ComparadorEvent,
} from '../lib/apiClient'
import { defineMessages, useT } from '../i18n'
import { Plug, Scale, Check, CircleAlert, Timer, Hash, Coins, Repeat, Wrench } from 'lucide-react'

const MSG = defineMessages({
  pt: {
    erroCarregar: 'Não foi possível carregar os motores (backend offline?).',
    erroTrocar: 'Erro ao trocar o motor ativo.',
    erroComparar: 'Erro ao comparar motores.',
    tituloAtivo: 'Motor ativo do sistema',
    descAtivoAntes: 'Define qual motor LLM responde em ',
    descAtivoForte: 'todos os agentes',
    descAtivoDepois: ' (Assistente, preços, produtor, alertas, auditoria, PDFs/RAG).',
    semChaveTitle: 'Configure a chave deste motor no servidor (Render).',
    semChave: ' (sem chave)',
    ativoAgora: 'Ativo agora:',
    semStreaming: 'Motores ≠ Claude não fazem streaming token a token (resposta aparece de uma vez).',
    tituloComparador: 'Comparador ao Vivo',
    descComparador: 'Faça uma pergunta e veja as respostas de cada motor lado a lado (não altera o motor ativo do sistema).',
    motores: 'Motores:',
    placeholder: 'Ex.: quanto de alface a merenda comprou em 2025?',
    comparando: 'Comparando...',
    comparar: 'Comparar motores',
    aguardando: 'aguardando…',
    latencia: 'latência',
    tokens: 'tokens entrada/saída',
    custo: 'custo estimado',
    iteracoes: 'iterações do loop',
    ferramentas: 'ferramentas usadas',
  },
  en: {
    erroCarregar: 'Could not load the engines (backend offline?).',
    erroTrocar: 'Error switching the active engine.',
    erroComparar: 'Error comparing engines.',
    tituloAtivo: 'System active engine',
    descAtivoAntes: 'Sets which LLM engine answers in ',
    descAtivoForte: 'all agents',
    descAtivoDepois: ' (Assistant, prices, producer, alerts, audit, PDFs/RAG).',
    semChaveTitle: "Configure this engine's key on the server (Render).",
    semChave: ' (no key)',
    ativoAgora: 'Active now:',
    semStreaming: 'Engines other than Claude do not stream token by token (the answer appears all at once).',
    tituloComparador: 'Live Comparison',
    descComparador: "Ask a question and see each engine's answer side by side (does not change the system active engine).",
    motores: 'Engines:',
    placeholder: 'E.g.: how much lettuce did school meals buy in 2025?',
    comparando: 'Comparing...',
    comparar: 'Compare engines',
    aguardando: 'waiting…',
    latencia: 'latency',
    tokens: 'input/output tokens',
    custo: 'estimated cost',
    iteracoes: 'loop iterations',
    ferramentas: 'tools used',
  },
  es: {
    erroCarregar: 'No se pudieron cargar los motores (¿backend fuera de línea?).',
    erroTrocar: 'Error al cambiar el motor activo.',
    erroComparar: 'Error al comparar motores.',
    tituloAtivo: 'Motor activo del sistema',
    descAtivoAntes: 'Define qué motor LLM responde en ',
    descAtivoForte: 'todos los agentes',
    descAtivoDepois: ' (Asistente, precios, productor, alertas, auditoría, PDFs/RAG).',
    semChaveTitle: 'Configure la clave de este motor en el servidor (Render).',
    semChave: ' (sin clave)',
    ativoAgora: 'Activo ahora:',
    semStreaming: 'Los motores ≠ Claude no hacen streaming token a token (la respuesta aparece de una vez).',
    tituloComparador: 'Comparador en Vivo',
    descComparador: 'Haga una pregunta y vea las respuestas de cada motor lado a lado (no cambia el motor activo del sistema).',
    motores: 'Motores:',
    placeholder: 'Ej.: ¿cuánta lechuga compró la alimentación escolar en 2025?',
    comparando: 'Comparando...',
    comparar: 'Comparar motores',
    aguardando: 'esperando…',
    latencia: 'latencia',
    tokens: 'tokens de entrada/salida',
    custo: 'costo estimado',
    iteracoes: 'iteraciones del bucle',
    ferramentas: 'herramientas usadas',
  },
})

// Cor categórica por motor (paleta Okabe-Ito, segura p/ daltonismo). Sempre acompanhada do nome.
const COR_MOTOR: Record<string, string> = {
  claude: 'var(--cat-1)', gemini: 'var(--cat-2)', groq_llama: 'var(--cat-3)', maritaca: 'var(--cat-4)',
}
const cor = (m: string) => COR_MOTOR[m] ?? 'var(--cat-5)'
const TITULO_ICONE = { display: 'flex', alignItems: 'center', gap: 8 } as const
const METRICA = { display: 'inline-flex', alignItems: 'center', gap: 4 } as const
const LS_KEY = 'agroia_motores_comparador'

export default function ComparadorVivo() {
  const t = useT(MSG)
  const [motores, setMotores] = useState<MotorInfo[]>([])
  const [motorAtivo, setAtivo] = useState<string>('claude')
  const [trocando, setTrocando] = useState(false)
  const [selecionados, setSelecionados] = useState<string[]>([])
  const [pergunta, setPergunta] = useState('')
  const [executando, setExecutando] = useState(false)
  const [resultados, setResultados] = useState<Record<string, ComparadorEvent>>({})
  const [erro, setErro] = useState('')

  useEffect(() => {
    getConfigMotor()
      .then(cfg => {
        setMotores(cfg.motores)
        setAtivo(cfg.motor_ativo)
        const salvos = localStorage.getItem(LS_KEY)
        if (salvos) {
          setSelecionados(JSON.parse(salvos))
        } else {
          setSelecionados(cfg.motores.filter(m => m.disponivel).map(m => m.motor))
        }
      })
      .catch(() => setErro(t('erroCarregar')))
  }, [])

  useEffect(() => {
    if (selecionados.length) localStorage.setItem(LS_KEY, JSON.stringify(selecionados))
  }, [selecionados])

  const trocarMotorGlobal = async (motor: string) => {
    setTrocando(true)
    setErro('')
    try {
      const cfg = await setMotorAtivo(motor)
      setAtivo(cfg.motor_ativo)
    } catch (e: any) {
      setErro(e?.response?.data?.detail || t('erroTrocar'))
    } finally {
      setTrocando(false)
    }
  }

  const toggleSelecionado = (motor: string) => {
    setSelecionados(prev => prev.includes(motor) ? prev.filter(m => m !== motor) : [...prev, motor])
  }

  const comparar = async () => {
    const q = pergunta.trim()
    if (!q || executando || !selecionados.length) return
    setExecutando(true)
    setErro('')
    setResultados({})
    try {
      for await (const ev of compararMotores(q, selecionados)) {
        if (ev.tipo === 'motor' && ev.motor) {
          setResultados(prev => ({ ...prev, [ev.motor as string]: ev }))
        }
      }
    } catch (e: any) {
      setErro(e?.message || t('erroComparar'))
    } finally {
      setExecutando(false)
    }
  }

  const rotuloDe = (m: string) => motores.find(x => x.motor === m)?.rotulo ?? m

  return (
    <>
      {/* Switch global do motor ativo */}
      <div className="chart-card">
        <h3 style={TITULO_ICONE}><Plug size={18} aria-hidden /> {t('tituloAtivo')}</h3>
        <p style={{ color: 'var(--texto-suave)', fontSize: 13, marginTop: -6 }}>
          {t('descAtivoAntes')}<strong>{t('descAtivoForte')}</strong>{t('descAtivoDepois')}
        </p>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          {motores.map(m => {
            const ativo = motorAtivo === m.motor
            return (
              <button
                key={m.motor}
                className="btn btn-secundario btn-sm"
                disabled={!m.disponivel || trocando}
                onClick={() => trocarMotorGlobal(m.motor)}
                title={m.disponivel ? '' : t('semChaveTitle')}
                aria-pressed={ativo}
                style={ativo ? {
                  borderColor: 'var(--verde)', background: 'var(--verde-fundo)', color: 'var(--verde)', fontWeight: 700,
                } : undefined}
              >
                {ativo
                  ? <Check size={14} strokeWidth={3} aria-hidden />
                  : <span aria-hidden style={{ width: 9, height: 9, borderRadius: 3, background: cor(m.motor) }} />}
                {m.rotulo}{m.baseline ? ' • baseline' : ''}{!m.disponivel ? t('semChave') : ''}
              </button>
            )
          })}
        </div>
        <p style={{ fontSize: 12, color: 'var(--texto-suave)', marginTop: 10 }}>
          {t('ativoAgora')} <strong>{rotuloDe(motorAtivo)}</strong>. {motorAtivo !== 'claude' && t('semStreaming')}
        </p>
      </div>

      {/* Comparador ao vivo */}
      <div className="chart-card">
        <h3 style={TITULO_ICONE}><Scale size={18} aria-hidden /> {t('tituloComparador')}</h3>
        <p style={{ color: 'var(--texto-suave)', fontSize: 13, marginTop: -6 }}>
          {t('descComparador')}
        </p>
        <div className="filters-bar" style={{ flexWrap: 'wrap' }}>
          <span style={{ fontSize: 13 }}>{t('motores')}</span>
          {motores.map(m => (
            <label key={m.motor} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 13, opacity: m.disponivel ? 1 : 0.45 }}>
              <input type="checkbox" disabled={!m.disponivel}
                checked={selecionados.includes(m.motor)} onChange={() => toggleSelecionado(m.motor)} />
              <span aria-hidden style={{ width: 9, height: 9, borderRadius: 3, background: cor(m.motor), display: 'inline-block' }} />
              {m.rotulo}
            </label>
          ))}
        </div>
        <textarea
          className="filter-select"
          style={{ width: '100%', minHeight: 70, marginTop: 12, resize: 'vertical', fontFamily: 'Inter' }}
          placeholder={t('placeholder')}
          value={pergunta}
          onChange={e => setPergunta(e.target.value)}
        />
        <button
          className="btn btn-primario"
          onClick={comparar}
          disabled={executando || !pergunta.trim() || !selecionados.length}
          style={{ marginTop: 12 }}
        >
          {executando
            ? <><span className="spinner" aria-hidden style={{ width: 14, height: 14 }} /> {t('comparando')}</>
            : <><Scale size={16} aria-hidden /> {t('comparar')}</>}
        </button>
        {erro && (
          <div className="aviso-box erro" role="alert" style={{ marginTop: 12 }}>
            <CircleAlert size={16} aria-hidden /> <span>{erro}</span>
          </div>
        )}

        {/* Cartões lado a lado */}
        {(executando || Object.keys(resultados).length > 0) && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(280px, 100%), 1fr))', gap: 16, marginTop: 18 }}>
            {selecionados.map(m => {
              const r = resultados[m]
              return (
                <div key={m} className="chart-card" style={{ margin: 0, borderTop: `3px solid ${cor(m)}` }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <span aria-hidden style={{ width: 10, height: 10, borderRadius: 3, background: cor(m) }} />
                    <strong>{rotuloDe(m)}</strong>
                  </div>
                  {!r ? (
                    <p style={{ color: 'var(--texto-suave)', fontSize: 13, display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className="spinner" aria-hidden style={{ width: 14, height: 14 }} /> {t('aguardando')}
                    </p>
                  ) : r.erro ? (
                    <div className="aviso-box erro" style={{ fontSize: 13 }}>
                      <CircleAlert size={16} aria-hidden /> <span>{r.erro}</span>
                    </div>
                  ) : (
                    <>
                      <div style={{ fontSize: 13.5 }}><ResponseRenderer content={r.resposta || ''} /></div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 12px', marginTop: 12, fontSize: 11, color: 'var(--texto-suave)' }}>
                        <span title={t('latencia')} style={METRICA}><Timer size={12} aria-hidden /> {r.latencia_ms} ms</span>
                        <span title={t('tokens')} style={METRICA}><Hash size={12} aria-hidden /> {r.tokens_entrada}/{r.tokens_saida}</span>
                        <span title={t('custo')} style={METRICA}><Coins size={12} aria-hidden /> US$ {(r.custo_usd ?? 0).toFixed(6)}</span>
                        <span title={t('iteracoes')} style={METRICA}><Repeat size={12} aria-hidden /> {r.iteracoes}</span>
                        {!!r.tools_usadas?.length && <span title={t('ferramentas')} style={{ ...METRICA, fontFamily: 'monospace' }}><Wrench size={12} aria-hidden /> {r.tools_usadas.join(', ')}</span>}
                      </div>
                    </>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </>
  )
}
