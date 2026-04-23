import { useState } from 'react'
import { Send } from 'lucide-react'
import { apiClient, streamPost } from '../lib/apiClient'

interface AuditoriaAlerta {
  tipo: string
  severidade: string
  mensagem: string
  processo?: string
  qtd_empenhos?: number
}

interface AuditoriaMetricas {
  total_licitacoes_agro: number
  lics_com_docs: number
  taxa_cobertura_pct: number
  total_empenhos: number
  lics_com_empenhos: number
  empenhos_sem_docs: number
  lics_concluidas_sem_docs: number
  alertas_criticos: number
  alertas_graves: number
}

interface AuditoriaResultado {
  metricas: AuditoriaMetricas
  alertas: AuditoriaAlerta[]
  executado_em: string
}

interface ChatMsg {
  role: 'user' | 'assistant'
  content: string
}

interface StreamEvent {
  tipo: 'status' | 'resultado' | 'erro' | 'fim'
  msg?: string
  dados?: AuditoriaResultado
}

const TIPO_CONFIG = {
  ERRO_BD: { icon: '🚨', label: 'Erro BD', cor: '#b91c1c', bg: '#fef2f2', borda: '#fca5a5' },
  INCONSISTENCIA_PORTAL: { icon: '⚠️', label: 'Inconsistência Portal', cor: '#b45309', bg: '#fef9ed', borda: '#fcd97d' },
  QUALIDADE: { icon: '🔍', label: 'Qualidade', cor: '#7c2d12', bg: '#fefce8', borda: '#fed7aa' },
}

const SEV_CONFIG = {
  CRITICO: { label: 'Crítico', bg: '#fef2f2', cor: '#b91c1c', borda: '#fca5a5' },
  GRAVE: { label: 'Grave', bg: '#fff7ed', cor: '#c2410c', borda: '#fdba74' },
  MEDIA: { label: 'Média', bg: '#fff7ed', cor: '#c2410c', borda: '#fdba74' },
  BAIXA: { label: 'Baixa', bg: '#f0fdf4', cor: '#15803d', borda: '#86efac' },
}

export default function Auditoria() {
  const [loading, setLoading] = useState(false)
  const [resultado, setResultado] = useState<AuditoriaResultado | null>(null)
  const [erro, setErro] = useState('')
  const [filtroTipo, setFiltroTipo] = useState<string>('todos')
  const [chatMsgs, setChatMsgs] = useState<ChatMsg[]>([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)

  const executarAuditoria = async () => {
    setLoading(true)
    setErro('')
    setChatMsgs([])
    try {
      for await (const event of streamPost<StreamEvent>('/auditoria/executar/stream')) {
        if (event.tipo === 'status') {
          // Update UI with status - keep same loading screen
        } else if (event.tipo === 'resultado' && event.dados) {
          setResultado(event.dados)
        } else if (event.tipo === 'erro') {
          setErro(event.msg || 'Erro desconhecido')
        } else if (event.tipo === 'fim') {
          setLoading(false)
        }
      }
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : 'Erro ao executar auditoria')
      setLoading(false)
    }
  }

  const enviarChatMsg = async () => {
    if (!chatInput.trim() || !resultado || chatLoading) return

    const novaMsg: ChatMsg = { role: 'user', content: chatInput }
    setChatMsgs(prev => [...prev, novaMsg])
    setChatInput('')
    setChatLoading(true)

    try {
      const data = await apiClient.post('/auditoria/chat', { pergunta: chatInput, contexto: resultado })
      setChatMsgs(prev => [...prev, { role: 'assistant', content: data.data.resposta }])
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : 'Erro na IA'
      setChatMsgs(prev => [...prev, { role: 'assistant', content: `Erro: ${errMsg}` }])
    } finally {
      setChatLoading(false)
    }
  }

  const alertasFiltrados = resultado?.alertas.filter(a => {
    if (filtroTipo !== 'todos' && a.tipo !== filtroTipo) return false
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
              🔎 Auditoria de Qualidade
            </h2>
            <p style={{ fontSize: 14, color: 'var(--texto-suave)', lineHeight: 1.6, maxWidth: 560 }}>
              Verifique a integridade dos dados coletados. Identifica licitações sem documentação,
              empenhos sem cobertura documental e inconsistências na base de dados.
            </p>
          </div>
          <button
            onClick={executarAuditoria}
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
              <><span className="spinner" style={{ width: 18, height: 18, borderWidth: 2, borderColor: 'rgba(255,255,255,0.3)', borderTopColor: '#fff' }} /> Executando...</>
            ) : (
              <>{resultado ? '🔄 Re-executar' : '▶️ Executar Auditoria'}</>
            )}
          </button>
        </div>
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
          <p style={{ marginTop: 20, fontFamily: 'Fraunces, serif', fontSize: 18, fontWeight: 700, color: 'var(--texto)' }}>Executando auditoria...</p>
          <p style={{ marginTop: 8, fontSize: 14, color: 'var(--texto-suave)' }}>Analisando licitações e documentos no banco de dados</p>
        </div>
      )}

      {/* ── Resultado ── */}
      {resultado && !loading && (
        <>
          {/* Cards de Métricas */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14, marginBottom: 20 }}>
            <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 14, padding: '18px 20px' }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--texto-suave)', textTransform: 'uppercase', marginBottom: 8 }}>📊 Total Licitações</div>
              <div style={{ fontSize: 32, fontFamily: 'Fraunces, serif', fontWeight: 700, color: 'var(--verde)' }}>{resultado.metricas.total_licitacoes_agro}</div>
              <div style={{ fontSize: 11, color: 'var(--texto-suave)', marginTop: 4 }}>Agrícolas no sistema</div>
            </div>

            <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 14, padding: '18px 20px' }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--texto-suave)', textTransform: 'uppercase', marginBottom: 8 }}>📄 Cobertura</div>
              <div style={{ fontSize: 32, fontFamily: 'Fraunces, serif', fontWeight: 700, color: 'var(--verde)' }}>{resultado.metricas.taxa_cobertura_pct}%</div>
              <div style={{ fontSize: 11, color: 'var(--texto-suave)', marginTop: 4 }}>{resultado.metricas.lics_com_docs} com documentação</div>
            </div>

            <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 14, padding: '18px 20px' }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--texto-suave)', textTransform: 'uppercase', marginBottom: 8 }}>🚨 Críticos</div>
              <div style={{ fontSize: 32, fontFamily: 'Fraunces, serif', fontWeight: 700, color: '#b91c1c' }}>{resultado.metricas.alertas_criticos}</div>
              <div style={{ fontSize: 11, color: 'var(--texto-suave)', marginTop: 4 }}>Empenhos sem docs</div>
            </div>

            <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 14, padding: '18px 20px' }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--texto-suave)', textTransform: 'uppercase', marginBottom: 8 }}>⚡ Empenhos</div>
              <div style={{ fontSize: 32, fontFamily: 'Fraunces, serif', fontWeight: 700, color: '#c2410c' }}>{resultado.metricas.empenhos_sem_docs}</div>
              <div style={{ fontSize: 11, color: 'var(--texto-suave)', marginTop: 4 }}>Sem documentação</div>
            </div>
          </div>

          {/* Resumo */}
          <div style={{ background: 'var(--verde-fundo)', border: '1px solid #b8dfc0', borderRadius: 14, padding: '18px 22px', marginBottom: 20 }}>
            <div style={{ fontSize: 12, fontWeight: 800, color: 'var(--verde)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>📋 Resumo</div>
            <p style={{ fontSize: 14, color: 'var(--texto)', lineHeight: 1.6 }}>
              {resultado.metricas.alertas_criticos > 0
                ? `⚠️ CRÍTICO: ${resultado.metricas.alertas_criticos} licitação(ões) com empenho(s) mas SEM documentação. `
                : '✅ Nenhum alerta crítico. '
              }
              Taxa de cobertura: {resultado.metricas.taxa_cobertura_pct}% ({resultado.metricas.lics_com_docs}/{resultado.metricas.total_licitacoes_agro}).
              {resultado.metricas.alertas_graves > 0 && ` ${resultado.metricas.alertas_graves} licitação(ões) concluída(s) sem documentação.`}
            </p>
          </div>

          {/* Filtros */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--texto-suave)' }}>Filtrar:</span>
            <button onClick={() => setFiltroTipo('todos')}
              style={{ background: filtroTipo === 'todos' ? 'var(--verde)' : 'var(--branco)', color: filtroTipo === 'todos' ? '#fff' : 'var(--texto-suave)', border: '1px solid var(--borda)', borderRadius: 8, padding: '5px 12px', fontFamily: 'Nunito', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>
              Todos
            </button>
            {Object.entries(TIPO_CONFIG).map(([tipo, cfg]) => (
              <button key={tipo} onClick={() => setFiltroTipo(filtroTipo === tipo ? 'todos' : tipo)}
                style={{ background: filtroTipo === tipo ? cfg.bg : 'var(--branco)', color: filtroTipo === tipo ? cfg.cor : 'var(--texto-suave)', border: `1px solid ${filtroTipo === tipo ? cfg.borda : 'var(--borda)'}`, borderRadius: 8, padding: '5px 12px', fontFamily: 'Nunito', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>
                {cfg.label} ({contPorTipo(tipo)})
              </button>
            ))}
            <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--texto-suave)', fontWeight: 600 }}>
              {alertasFiltrados.length} alerta(s)
            </span>
          </div>

          {/* Lista de Alertas */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 30 }}>
            {alertasFiltrados.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px 24px', color: 'var(--texto-suave)' }}>
                ✅ Nenhum alerta com os filtros selecionados
              </div>
            ) : (
              alertasFiltrados.map((alerta, i) => {
                const tipo = TIPO_CONFIG[alerta.tipo as keyof typeof TIPO_CONFIG] || TIPO_CONFIG.QUALIDADE
                const sev = SEV_CONFIG[alerta.severidade as keyof typeof SEV_CONFIG] || SEV_CONFIG.BAIXA
                return (
                  <div key={i} style={{ background: 'var(--branco)', border: `1px solid ${tipo.borda}`, borderLeft: `4px solid ${tipo.cor}`, borderRadius: 12, padding: '16px 18px' }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 8 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <span style={{ fontSize: 18 }}>{tipo.icon}</span>
                        <div>
                          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--texto)' }}>{alerta.mensagem}</div>
                          {alerta.processo && <div style={{ fontSize: 11, color: tipo.cor, fontWeight: 600, marginTop: 2 }}>Processo: <strong>{alerta.processo}</strong></div>}
                        </div>
                      </div>
                      <span style={{ background: sev.bg, color: sev.cor, border: `1px solid ${sev.borda}`, fontSize: 11, fontWeight: 700, padding: '4px 10px', borderRadius: 6, whiteSpace: 'nowrap' }}>
                        ● {sev.label}
                      </span>
                    </div>
                  </div>
                )
              })
            )}
          </div>

          {/* Chat com IA */}
          <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 16, padding: '20px', marginBottom: 20 }}>
            <h3 style={{ fontFamily: 'Fraunces, serif', fontSize: 16, fontWeight: 700, color: 'var(--texto)', marginBottom: 16 }}>
              💬 Discuta com IA
            </h3>

            {/* Chat Messages */}
            <div style={{ background: 'var(--cinza-claro)', borderRadius: 12, padding: '16px', maxHeight: 400, overflowY: 'auto', marginBottom: 16 }}>
              {chatMsgs.length === 0 ? (
                <p style={{ fontSize: 13, color: 'var(--texto-suave)', textAlign: 'center', padding: '20px 0' }}>
                  💡 Faça perguntas sobre os resultados da auditoria
                </p>
              ) : (
                chatMsgs.map((msg, i) => (
                  <div key={i} style={{ marginBottom: 12, display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
                    <div style={{
                      background: msg.role === 'user' ? 'var(--verde)' : 'var(--branco)',
                      color: msg.role === 'user' ? '#fff' : 'var(--texto)',
                      borderRadius: 10,
                      padding: '10px 14px',
                      maxWidth: '85%',
                      fontSize: 13,
                      lineHeight: 1.5,
                      border: msg.role === 'user' ? 'none' : '1px solid var(--borda)'
                    }}>
                      {msg.content}
                    </div>
                  </div>
                ))
              )}
              {chatLoading && (
                <div style={{ fontSize: 12, color: 'var(--texto-suave)', display: 'flex', gap: 4, alignItems: 'center' }}>
                  <span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> IA está digitando...
                </div>
              )}
            </div>

            {/* Chat Input */}
            <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end' }}>
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && enviarChatMsg()}
                placeholder="Faça uma pergunta sobre os resultados..."
                disabled={chatLoading}
                style={{
                  flex: 1,
                  padding: '10px 14px',
                  borderRadius: 10,
                  border: '1px solid var(--borda)',
                  fontFamily: 'Nunito',
                  fontSize: 13,
                  color: 'var(--texto)',
                  opacity: chatLoading ? 0.6 : 1,
                  cursor: chatLoading ? 'not-allowed' : 'text'
                }}
              />
              <button
                onClick={enviarChatMsg}
                disabled={!chatInput.trim() || chatLoading}
                style={{
                  background: chatInput.trim() && !chatLoading ? 'var(--verde)' : 'var(--borda)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 10,
                  padding: '10px 16px',
                  cursor: chatInput.trim() && !chatLoading ? 'pointer' : 'not-allowed',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  fontWeight: 700,
                  transition: 'background 0.15s'
                }}
              >
                <Send size={16} /> Enviar
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
