import { useEffect, useState } from 'react'
import ResponseRenderer from './ResponseRenderer'
import {
  getConfigMotor, setMotorAtivo, compararMotores,
  type MotorInfo, type ComparadorEvent,
} from '../lib/apiClient'

const COR_MOTOR: Record<string, string> = {
  claude: '#334155', gemini: '#1e3a5f', groq_llama: '#0f766e', maritaca: '#b45309',
}
const cor = (m: string) => COR_MOTOR[m] ?? '#64748b'
const LS_KEY = 'agroia_motores_comparador'

export default function ComparadorVivo() {
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
      .catch(() => setErro('Não foi possível carregar os motores (backend offline?).'))
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
      setErro(e?.response?.data?.detail || 'Erro ao trocar o motor ativo.')
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
      setErro(e?.message || 'Erro ao comparar motores.')
    } finally {
      setExecutando(false)
    }
  }

  const rotuloDe = (m: string) => motores.find(x => x.motor === m)?.rotulo ?? m

  return (
    <>
      {/* Switch global do motor ativo */}
      <div className="chart-card">
        <h3>🔌 Motor ativo do sistema</h3>
        <p style={{ color: 'var(--texto-suave)', fontSize: 13, marginTop: -6 }}>
          Define qual motor LLM responde em <strong>todos os agentes</strong> (Assistente, preços, produtor, alertas, auditoria, PDFs/RAG).
        </p>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          {motores.map(m => (
            <button
              key={m.motor}
              disabled={!m.disponivel || trocando}
              onClick={() => trocarMotorGlobal(m.motor)}
              title={m.disponivel ? '' : 'Configure a chave deste motor no servidor (Render).'}
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
              {m.rotulo}{m.baseline ? ' • baseline' : ''}{!m.disponivel ? ' (sem chave)' : ''}
            </button>
          ))}
        </div>
        <p style={{ fontSize: 12, color: 'var(--texto-suave)', marginTop: 10 }}>
          Ativo agora: <strong>{rotuloDe(motorAtivo)}</strong>. {motorAtivo !== 'claude' && 'Motores ≠ Claude não fazem streaming token a token (resposta aparece de uma vez).'}
        </p>
      </div>

      {/* Comparador ao vivo */}
      <div className="chart-card">
        <h3>⚖️ Comparador ao Vivo</h3>
        <p style={{ color: 'var(--texto-suave)', fontSize: 13, marginTop: -6 }}>
          Faça uma pergunta e veja as respostas de cada motor lado a lado (não altera o motor ativo do sistema).
        </p>
        <div className="filters-bar" style={{ flexWrap: 'wrap' }}>
          <span style={{ fontSize: 13 }}>Motores:</span>
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
          placeholder="Ex.: quanto de alface a merenda comprou em 2025?"
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
          {executando ? '⏳ Comparando...' : '⚖️ Comparar motores'}
        </button>
        {erro && <p style={{ color: '#b91c1c', fontSize: 13, marginTop: 10 }}>{erro}</p>}

        {/* Cartões lado a lado */}
        {(executando || Object.keys(resultados).length > 0) && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16, marginTop: 18 }}>
            {selecionados.map(m => {
              const r = resultados[m]
              return (
                <div key={m} className="chart-card" style={{ margin: 0, borderTop: `3px solid ${cor(m)}` }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <span style={{ width: 10, height: 10, borderRadius: 3, background: cor(m) }} />
                    <strong>{rotuloDe(m)}</strong>
                  </div>
                  {!r ? (
                    <p style={{ color: 'var(--texto-suave)', fontSize: 13 }}>⏳ aguardando…</p>
                  ) : r.erro ? (
                    <p style={{ color: '#b91c1c', fontSize: 13 }}>❌ {r.erro}</p>
                  ) : (
                    <>
                      <div style={{ fontSize: 13.5 }}><ResponseRenderer content={r.resposta || ''} /></div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12, fontSize: 11, color: 'var(--texto-suave)' }}>
                        <span title="latência">⏱️ {r.latencia_ms} ms</span>
                        <span title="tokens entrada/saída">🔤 {r.tokens_entrada}/{r.tokens_saida}</span>
                        <span title="custo estimado">💵 US$ {(r.custo_usd ?? 0).toFixed(6)}</span>
                        <span title="iterações do loop">🔁 {r.iteracoes}</span>
                        {!!r.tools_usadas?.length && <span title="ferramentas" style={{ fontFamily: 'monospace' }}>🛠️ {r.tools_usadas.join(', ')}</span>}
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
