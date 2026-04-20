import { useState } from 'react'

interface Alerta {
  tipo: 'ALTA_PRECO' | 'DESABASTECIMENTO' | 'SUPERFATURAMENTO'
  severidade: 'ALTA' | 'MEDIA' | 'BAIXA'
  cultura: string
  titulo: string
  descricao: string
  recomendacao: string
}

interface ResultadoAlertas {
  alertas: Alerta[]
  resumo: string
}

const TIPO_CONFIG = {
  ALTA_PRECO: { icon: '📈', label: 'Alta de Preço', cor: '#e65c00', bg: '#fff3ed', borda: '#f5c4a0' },
  DESABASTECIMENTO: { icon: '⚠️', label: 'Risco de Desabastecimento', cor: '#b45309', bg: '#fef9ed', borda: '#fcd97d' },
  SUPERFATURAMENTO: { icon: '🚨', label: 'Superfaturamento', cor: '#b91c1c', bg: '#fef2f2', borda: '#fca5a5' },
}

const SEV_CONFIG = {
  ALTA: { label: 'Alta', bg: '#fef2f2', cor: '#b91c1c', borda: '#fca5a5' },
  MEDIA: { label: 'Média', bg: '#fff7ed', cor: '#c2410c', borda: '#fdba74' },
  BAIXA: { label: 'Baixa', bg: '#f0fdf4', cor: '#15803d', borda: '#86efac' },
}

export default function Alertas() {
  const [loading, setLoading] = useState(false)
  const [resultado, setResultado] = useState<ResultadoAlertas | null>(null)
  const [erro, setErro] = useState('')
  const [filtroTipo, setFiltroTipo] = useState<string>('todos')
  const [filtroSev, setFiltroSev] = useState<string>('todas')

  const analisar = async () => {
    setLoading(true)
    setErro('')
    setResultado(null)
    try {
      const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
      const res = await fetch(`${API}/alertas`, { method: 'POST' })
      if (!res.ok) throw new Error(`Erro ${res.status}`)
      const data = await res.json()
      setResultado(data)
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : 'Erro ao conectar ao servidor')
    } finally {
      setLoading(false)
    }
  }

  const alertasFiltrados = resultado?.alertas.filter(a => {
    if (filtroTipo !== 'todos' && a.tipo !== filtroTipo) return false
    if (filtroSev !== 'todas' && a.severidade !== filtroSev) return false
    return true
  }) ?? []

  const contPorTipo = (tipo: string) =>
    resultado?.alertas.filter(a => a.tipo === tipo).length ?? 0

  return (
    <div className="page">

      {/* ── Header ── */}
      <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 16, padding: '24px 28px', marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 20, flexWrap: 'wrap' }}>
          <div>
            <h2 style={{ fontFamily: 'Fraunces, serif', fontSize: 22, fontWeight: 700, color: 'var(--texto)', marginBottom: 8 }}>
              🤖 Alertas Inteligentes
            </h2>
            <p style={{ fontSize: 14, color: 'var(--texto-suave)', lineHeight: 1.6, maxWidth: 560 }}>
              A IA analisa o histórico de licitações da SMSAN/FAAC e identifica automaticamente
              riscos de alta de preço, desabastecimento e superfaturamento por cultura.
            </p>
          </div>
          <button
            onClick={analisar}
            disabled={loading}
            style={{
              background: loading ? 'var(--borda)' : 'var(--verde)',
              color: '#fff',
              border: 'none',
              borderRadius: 12,
              padding: '14px 28px',
              fontFamily: 'Nunito',
              fontSize: 15,
              fontWeight: 800,
              cursor: loading ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              whiteSpace: 'nowrap',
              transition: 'background 0.15s',
              flexShrink: 0,
            }}
          >
            {loading ? (
              <><span className="spinner" style={{ width: 18, height: 18, borderWidth: 2, borderColor: 'rgba(255,255,255,0.3)', borderTopColor: '#fff' }} /> Analisando...</>
            ) : (
              <>{resultado ? '🔄 Reanalisar' : '🔍 Analisar Dados'}</>
            )}
          </button>
        </div>

        {!resultado && !loading && !erro && (
          <div style={{ marginTop: 20, background: 'var(--cinza-claro)', borderRadius: 12, padding: '16px 20px', display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            {[
              { icon: '📈', label: 'Alta de Preço', desc: 'Variação acima de 20% entre períodos' },
              { icon: '⚠️', label: 'Desabastecimento', desc: 'Culturas sem compra há mais de 12 meses' },
              { icon: '🚨', label: 'Superfaturamento', desc: 'Preço/kg muito acima da média histórica' },
            ].map(item => (
              <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 10, flex: '1 1 200px' }}>
                <span style={{ fontSize: 24 }}>{item.icon}</span>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--texto)' }}>{item.label}</div>
                  <div style={{ fontSize: 12, color: 'var(--texto-suave)' }}>{item.desc}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Erro ── */}
      {erro && (
        <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 12, padding: '14px 18px', marginBottom: 16, color: '#b91c1c', fontSize: 14, fontWeight: 600 }}>
          ⚠️ {erro}
        </div>
      )}

      {/* ── Loading ── */}
      {loading && (
        <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 16, padding: '48px 24px', textAlign: 'center', marginBottom: 20 }}>
          <span className="spinner" style={{ width: 48, height: 48, borderWidth: 3 }} />
          <p style={{ marginTop: 20, fontFamily: 'Fraunces, serif', fontSize: 18, fontWeight: 700, color: 'var(--texto)' }}>Analisando dados históricos...</p>
          <p style={{ marginTop: 8, fontSize: 14, color: 'var(--texto-suave)' }}>A IA está processando o histórico de licitações da SMSAN/FAAC</p>
        </div>
      )}

      {/* ── Resultado ── */}
      {resultado && !loading && (
        <>
          {/* Resumo */}
          <div style={{ background: 'var(--verde-fundo)', border: '1px solid #b8dfc0', borderRadius: 14, padding: '18px 22px', marginBottom: 20 }}>
            <div style={{ fontSize: 12, fontWeight: 800, color: 'var(--verde)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>📋 Resumo da Análise</div>
            <p style={{ fontSize: 14, color: 'var(--texto)', lineHeight: 1.7 }}>{resultado.resumo}</p>
          </div>

          {/* Cards de contagem */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginBottom: 20 }}>
            {[
              { tipo: 'ALTA_PRECO', ...TIPO_CONFIG.ALTA_PRECO },
              { tipo: 'DESABASTECIMENTO', ...TIPO_CONFIG.DESABASTECIMENTO },
              { tipo: 'SUPERFATURAMENTO', ...TIPO_CONFIG.SUPERFATURAMENTO },
            ].map(({ tipo, icon, label, cor, bg, borda }) => (
              <div key={tipo}
                onClick={() => setFiltroTipo(filtroTipo === tipo ? 'todos' : tipo)}
                style={{ background: filtroTipo === tipo ? bg : 'var(--branco)', border: `1.5px solid ${filtroTipo === tipo ? borda : 'var(--borda)'}`, borderRadius: 14, padding: '16px 18px', cursor: 'pointer', transition: 'all 0.15s' }}>
                <div style={{ fontSize: 24, marginBottom: 8 }}>{icon}</div>
                <div style={{ fontSize: 28, fontFamily: 'Fraunces, serif', fontWeight: 700, color: cor }}>{contPorTipo(tipo)}</div>
                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--texto-suave)', marginTop: 4 }}>{label}</div>
              </div>
            ))}
            <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 14, padding: '16px 18px' }}>
              <div style={{ fontSize: 24, marginBottom: 8 }}>🔔</div>
              <div style={{ fontSize: 28, fontFamily: 'Fraunces, serif', fontWeight: 700, color: 'var(--texto)' }}>{resultado.alertas.length}</div>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--texto-suave)', marginTop: 4 }}>Total de Alertas</div>
            </div>
          </div>

          {/* Filtros */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--texto-suave)' }}>Filtrar:</span>
            <button onClick={() => setFiltroTipo('todos')}
              style={{ background: filtroTipo === 'todos' ? 'var(--verde)' : 'var(--branco)', color: filtroTipo === 'todos' ? '#fff' : 'var(--texto-suave)', border: '1px solid var(--borda)', borderRadius: 8, padding: '5px 12px', fontFamily: 'Nunito', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>
              Todos
            </button>
            {(['ALTA', 'MEDIA', 'BAIXA'] as const).map(sev => (
              <button key={sev} onClick={() => setFiltroSev(filtroSev === sev ? 'todas' : sev)}
                style={{ background: filtroSev === sev ? SEV_CONFIG[sev].bg : 'var(--branco)', color: filtroSev === sev ? SEV_CONFIG[sev].cor : 'var(--texto-suave)', border: `1px solid ${filtroSev === sev ? SEV_CONFIG[sev].borda : 'var(--borda)'}`, borderRadius: 8, padding: '5px 12px', fontFamily: 'Nunito', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>
                Severidade {SEV_CONFIG[sev].label}
              </button>
            ))}
            <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--texto-suave)', fontWeight: 600 }}>
              {alertasFiltrados.length} alertas
            </span>
          </div>

          {/* Lista de alertas */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {alertasFiltrados.map((alerta, i) => {
              const tipo = TIPO_CONFIG[alerta.tipo]
              const sev = SEV_CONFIG[alerta.severidade]
              return (
                <div key={i} style={{ background: 'var(--branco)', border: `1px solid ${tipo.borda}`, borderLeft: `4px solid ${tipo.cor}`, borderRadius: 14, padding: '18px 20px' }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 10 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span style={{ fontSize: 20 }}>{tipo.icon}</span>
                      <div>
                        <div style={{ fontSize: 15, fontWeight: 800, color: 'var(--texto)' }}>{alerta.titulo}</div>
                        <div style={{ fontSize: 12, color: tipo.cor, fontWeight: 700, marginTop: 2 }}>{tipo.label} · <span style={{ background: tipo.bg, padding: '1px 8px', borderRadius: 6, border: `1px solid ${tipo.borda}` }}>{alerta.cultura}</span></div>
                      </div>
                    </div>
                    <span style={{ background: sev.bg, color: sev.cor, border: `1px solid ${sev.borda}`, fontSize: 11, fontWeight: 800, padding: '4px 12px', borderRadius: 8, whiteSpace: 'nowrap' }}>
                      ● {sev.label}
                    </span>
                  </div>
                  <p style={{ fontSize: 13, color: 'var(--texto)', lineHeight: 1.6, marginBottom: 10 }}>{alerta.descricao}</p>
                  <div style={{ background: 'var(--cinza-claro)', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: 'var(--texto-suave)', display: 'flex', gap: 8 }}>
                    <span style={{ flexShrink: 0 }}>💡</span>
                    <span><strong style={{ color: 'var(--texto)' }}>Recomendação:</strong> {alerta.recomendacao}</span>
                  </div>
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
