import { useEffect, useState } from 'react'
import ResponseRenderer from './ResponseRenderer'
import {
  getConfigMotor, setMotorAtivo, compararMotores,
  type MotorInfo, type ComparadorEvent,
} from '../lib/apiClient'
import { defineMessages, useT } from '../i18n'

const MSG = defineMessages({
  pt: {
    erroCarregar: 'Não foi possível carregar os motores (backend offline?).',
    erroTrocar: 'Erro ao trocar o motor ativo.',
    erroComparar: 'Erro ao comparar motores.',
    tituloAtivo: '🔌 Motor ativo do sistema',
    descAtivoAntes: 'Define qual motor LLM responde em ',
    descAtivoForte: 'todos os agentes',
    descAtivoDepois: ' (Assistente, preços, produtor, alertas, auditoria, PDFs/RAG).',
    semChaveTitle: 'Configure a chave deste motor no servidor (Render).',
    semChave: ' (sem chave)',
    ativoAgora: 'Ativo agora:',
    semStreaming: 'Motores ≠ Claude não fazem streaming token a token (resposta aparece de uma vez).',
    tituloComparador: '⚖️ Comparador ao Vivo',
    descComparador: 'Faça uma pergunta e veja as respostas de cada motor lado a lado (não altera o motor ativo do sistema).',
    motores: 'Motores:',
    placeholder: 'Ex.: quanto de alface a merenda comprou em 2025?',
    comparando: '⏳ Comparando...',
    comparar: '⚖️ Comparar motores',
    aguardando: '⏳ aguardando…',
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
    tituloAtivo: '🔌 System active engine',
    descAtivoAntes: 'Sets which LLM engine answers in ',
    descAtivoForte: 'all agents',
    descAtivoDepois: ' (Assistant, prices, producer, alerts, audit, PDFs/RAG).',
    semChaveTitle: "Configure this engine's key on the server (Render).",
    semChave: ' (no key)',
    ativoAgora: 'Active now:',
    semStreaming: 'Engines other than Claude do not stream token by token (the answer appears all at once).',
    tituloComparador: '⚖️ Live Comparison',
    descComparador: "Ask a question and see each engine's answer side by side (does not change the system active engine).",
    motores: 'Engines:',
    placeholder: 'E.g.: how much lettuce did school meals buy in 2025?',
    comparando: '⏳ Comparing...',
    comparar: '⚖️ Compare engines',
    aguardando: '⏳ waiting…',
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
    tituloAtivo: '🔌 Motor activo del sistema',
    descAtivoAntes: 'Define qué motor LLM responde en ',
    descAtivoForte: 'todos los agentes',
    descAtivoDepois: ' (Asistente, precios, productor, alertas, auditoría, PDFs/RAG).',
    semChaveTitle: 'Configure la clave de este motor en el servidor (Render).',
    semChave: ' (sin clave)',
    ativoAgora: 'Activo ahora:',
    semStreaming: 'Los motores ≠ Claude no hacen streaming token a token (la respuesta aparece de una vez).',
    tituloComparador: '⚖️ Comparador en Vivo',
    descComparador: 'Haga una pregunta y vea las respuestas de cada motor lado a lado (no cambia el motor activo del sistema).',
    motores: 'Motores:',
    placeholder: 'Ej.: ¿cuánta lechuga compró la alimentación escolar en 2025?',
    comparando: '⏳ Comparando...',
    comparar: '⚖️ Comparar motores',
    aguardando: '⏳ esperando…',
    latencia: 'latencia',
    tokens: 'tokens de entrada/salida',
    custo: 'costo estimado',
    iteracoes: 'iteraciones del bucle',
    ferramentas: 'herramientas usadas',
  },
})

const COR_MOTOR: Record<string, string> = {
  claude: '#334155', gemini: '#1e3a5f', groq_llama: '#0f766e', maritaca: '#b45309',
}
const cor = (m: string) => COR_MOTOR[m] ?? '#64748b'
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
        <h3>{t('tituloAtivo')}</h3>
        <p style={{ color: 'var(--texto-suave)', fontSize: 13, marginTop: -6 }}>
          {t('descAtivoAntes')}<strong>{t('descAtivoForte')}</strong>{t('descAtivoDepois')}
        </p>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          {motores.map(m => (
            <button
              key={m.motor}
              disabled={!m.disponivel || trocando}
              onClick={() => trocarMotorGlobal(m.motor)}
              title={m.disponivel ? '' : t('semChaveTitle')}
              style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '8px 14px', borderRadius: 10, fontSize: 13, fontWeight: 700,
                cursor: (!m.disponivel || trocando) ? 'not-allowed' : 'pointer',
                opacity: m.disponivel ? 1 : 0.45,
                border: motorAtivo === m.motor ? `2px solid ${cor(m.motor)}` : '1px solid var(--borda)',
                background: motorAtivo === m.motor ? cor(m.motor) : '#fff',
                color: motorAtivo === m.motor ? '#fff' : 'var(--texto)',
              }}
            >
              <span style={{ width: 9, height: 9, borderRadius: 3, background: motorAtivo === m.motor ? '#fff' : cor(m.motor) }} />
              {m.rotulo}{m.baseline ? ' • baseline' : ''}{!m.disponivel ? t('semChave') : ''}
            </button>
          ))}
        </div>
        <p style={{ fontSize: 12, color: 'var(--texto-suave)', marginTop: 10 }}>
          {t('ativoAgora')} <strong>{rotuloDe(motorAtivo)}</strong>. {motorAtivo !== 'claude' && t('semStreaming')}
        </p>
      </div>

      {/* Comparador ao vivo */}
      <div className="chart-card">
        <h3>{t('tituloComparador')}</h3>
        <p style={{ color: 'var(--texto-suave)', fontSize: 13, marginTop: -6 }}>
          {t('descComparador')}
        </p>
        <div className="filters-bar" style={{ flexWrap: 'wrap' }}>
          <span style={{ fontSize: 13 }}>{t('motores')}</span>
          {motores.map(m => (
            <label key={m.motor} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 13, opacity: m.disponivel ? 1 : 0.45 }}>
              <input type="checkbox" disabled={!m.disponivel}
                checked={selecionados.includes(m.motor)} onChange={() => toggleSelecionado(m.motor)} />
              <span style={{ width: 9, height: 9, borderRadius: 3, background: cor(m.motor), display: 'inline-block' }} />
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
          onClick={comparar}
          disabled={executando || !pergunta.trim() || !selecionados.length}
          style={{
            marginTop: 12, background: executando ? 'var(--borda)' : 'var(--verde)', color: '#fff',
            border: 'none', borderRadius: 12, padding: '12px 24px', fontSize: 14, fontWeight: 800,
            cursor: (executando || !pergunta.trim() || !selecionados.length) ? 'not-allowed' : 'pointer',
          }}
        >
          {executando ? t('comparando') : t('comparar')}
        </button>
        {erro && <p style={{ color: '#b91c1c', fontSize: 13, marginTop: 10 }}>{erro}</p>}

        {/* Cartões lado a lado */}
        {(executando || Object.keys(resultados).length > 0) && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(280px, 100%), 1fr))', gap: 16, marginTop: 18 }}>
            {selecionados.map(m => {
              const r = resultados[m]
              return (
                <div key={m} className="chart-card" style={{ margin: 0, borderTop: `3px solid ${cor(m)}` }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <span style={{ width: 10, height: 10, borderRadius: 3, background: cor(m) }} />
                    <strong>{rotuloDe(m)}</strong>
                  </div>
                  {!r ? (
                    <p style={{ color: 'var(--texto-suave)', fontSize: 13 }}>{t('aguardando')}</p>
                  ) : r.erro ? (
                    <p style={{ color: '#b91c1c', fontSize: 13 }}>❌ {r.erro}</p>
                  ) : (
                    <>
                      <div style={{ fontSize: 13.5 }}><ResponseRenderer content={r.resposta || ''} /></div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12, fontSize: 11, color: 'var(--texto-suave)' }}>
                        <span title={t('latencia')}>⏱️ {r.latencia_ms} ms</span>
                        <span title={t('tokens')}>🔤 {r.tokens_entrada}/{r.tokens_saida}</span>
                        <span title={t('custo')}>💵 US$ {(r.custo_usd ?? 0).toFixed(6)}</span>
                        <span title={t('iteracoes')}>🔁 {r.iteracoes}</span>
                        {!!r.tools_usadas?.length && <span title={t('ferramentas')} style={{ fontFamily: 'monospace' }}>🛠️ {r.tools_usadas.join(', ')}</span>}
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
