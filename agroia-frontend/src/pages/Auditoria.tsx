import { useState } from 'react'
import { Send } from 'lucide-react'
import { BotoesVoz, AvisoVoz, OuvirResposta } from '../components/VozControles'
import { apiClient, streamPost } from '../lib/apiClient'
import { useVoz } from '../lib/useVoz'
import { defineMessages, useI18n, useT } from '../i18n'

const MSG = defineMessages({
  pt: {
    tipoErroBd: 'Erro BD',
    tipoInconsist: 'Inconsistência Portal',
    tipoQualidade: 'Qualidade',
    sevCritico: 'Crítico',
    sevGrave: 'Grave',
    sevMedia: 'Média',
    sevBaixa: 'Baixa',
    erroDesconhecido: 'Erro desconhecido',
    erroExecutar: 'Erro ao executar auditoria',
    erroIa: 'Erro na IA',
    erroPrefixo: 'Erro: {msg}',
    titulo: '🔎 Auditoria de Qualidade',
    subtitulo: 'Verifique a integridade dos dados coletados. Identifica licitações sem documentação, empenhos sem cobertura documental e inconsistências na base de dados.',
    executando: 'Executando...',
    reexecutar: '🔄 Re-executar',
    executar: '▶️ Executar Auditoria',
    carregandoTitulo: 'Executando auditoria...',
    carregandoSub: 'Analisando licitações e documentos no banco de dados',
    mTotalLics: '📊 Total Licitações',
    mTotalLicsSub: 'Agrícolas no sistema',
    mCobertura: '📄 Cobertura',
    mCoberturaSub: '{n} com documentação',
    mCriticos: '🚨 Críticos',
    mCriticosSub: 'Empenhos sem docs',
    mEmpenhos: '⚡ Empenhos',
    mEmpenhosSub: 'Sem documentação',
    resumo: '📋 Resumo',
    resumoCritico: '⚠️ CRÍTICO: {n} licitação(ões) com empenho(s) mas SEM documentação. ',
    resumoSemCritico: '✅ Nenhum alerta crítico. ',
    resumoCobertura: 'Taxa de cobertura: {pct}% ({com}/{total}).',
    resumoGraves: ' {n} licitação(ões) concluída(s) sem documentação.',
    filtrar: 'Filtrar:',
    todos: 'Todos',
    nAlertas: '{n} alerta(s)',
    nenhumAlerta: '✅ Nenhum alerta com os filtros selecionados',
    processo: 'Processo:',
    chatTitulo: '💬 Discuta com IA',
    chatVazio: '💡 Faça perguntas sobre os resultados da auditoria',
    digitando: 'IA está digitando...',
    ouvindo: 'Ouvindo…',
    placeholder: 'Faça uma pergunta sobre os resultados...',
    enviar: 'Enviar',
  },
  en: {
    tipoErroBd: 'DB Error',
    tipoInconsist: 'Portal Inconsistency',
    tipoQualidade: 'Quality',
    sevCritico: 'Critical',
    sevGrave: 'Severe',
    sevMedia: 'Medium',
    sevBaixa: 'Low',
    erroDesconhecido: 'Unknown error',
    erroExecutar: 'Error running the audit',
    erroIa: 'AI error',
    erroPrefixo: 'Error: {msg}',
    titulo: '🔎 Data Quality Audit',
    subtitulo: 'Check the integrity of the collected data. Identifies biddings without documents, commitments without document coverage and inconsistencies in the database.',
    executando: 'Running...',
    reexecutar: '🔄 Run again',
    executar: '▶️ Run Audit',
    carregandoTitulo: 'Running audit...',
    carregandoSub: 'Analyzing biddings and documents in the database',
    mTotalLics: '📊 Total Biddings',
    mTotalLicsSub: 'Agricultural in the system',
    mCobertura: '📄 Coverage',
    mCoberturaSub: '{n} with documents',
    mCriticos: '🚨 Critical',
    mCriticosSub: 'Commitments without docs',
    mEmpenhos: '⚡ Commitments',
    mEmpenhosSub: 'Without documents',
    resumo: '📋 Summary',
    resumoCritico: '⚠️ CRITICAL: {n} bidding(s) with commitment(s) but NO documents. ',
    resumoSemCritico: '✅ No critical alerts. ',
    resumoCobertura: 'Coverage rate: {pct}% ({com}/{total}).',
    resumoGraves: ' {n} completed bidding(s) without documents.',
    filtrar: 'Filter:',
    todos: 'All',
    nAlertas: '{n} alert(s)',
    nenhumAlerta: '✅ No alerts match the selected filters',
    processo: 'Process:',
    chatTitulo: '💬 Discuss with AI',
    chatVazio: '💡 Ask questions about the audit results',
    digitando: 'AI is typing...',
    ouvindo: 'Listening…',
    placeholder: 'Ask a question about the results...',
    enviar: 'Send',
  },
  es: {
    tipoErroBd: 'Error BD',
    tipoInconsist: 'Inconsistencia Portal',
    tipoQualidade: 'Calidad',
    sevCritico: 'Crítico',
    sevGrave: 'Grave',
    sevMedia: 'Media',
    sevBaixa: 'Baja',
    erroDesconhecido: 'Error desconocido',
    erroExecutar: 'Error al ejecutar la auditoría',
    erroIa: 'Error de la IA',
    erroPrefixo: 'Error: {msg}',
    titulo: '🔎 Auditoría de Calidad',
    subtitulo: 'Verifique la integridad de los datos recolectados. Identifica licitaciones sin documentación, compromisos sin cobertura documental e inconsistencias en la base de datos.',
    executando: 'Ejecutando...',
    reexecutar: '🔄 Volver a ejecutar',
    executar: '▶️ Ejecutar Auditoría',
    carregandoTitulo: 'Ejecutando auditoría...',
    carregandoSub: 'Analizando licitaciones y documentos en la base de datos',
    mTotalLics: '📊 Total Licitaciones',
    mTotalLicsSub: 'Agrícolas en el sistema',
    mCobertura: '📄 Cobertura',
    mCoberturaSub: '{n} con documentación',
    mCriticos: '🚨 Críticos',
    mCriticosSub: 'Compromisos sin docs',
    mEmpenhos: '⚡ Compromisos',
    mEmpenhosSub: 'Sin documentación',
    resumo: '📋 Resumen',
    resumoCritico: '⚠️ CRÍTICO: {n} licitación(es) con compromiso(s) pero SIN documentación. ',
    resumoSemCritico: '✅ Ninguna alerta crítica. ',
    resumoCobertura: 'Tasa de cobertura: {pct}% ({com}/{total}).',
    resumoGraves: ' {n} licitación(es) concluida(s) sin documentación.',
    filtrar: 'Filtrar:',
    todos: 'Todos',
    nAlertas: '{n} alerta(s)',
    nenhumAlerta: '✅ Ninguna alerta con los filtros seleccionados',
    processo: 'Proceso:',
    chatTitulo: '💬 Converse con la IA',
    chatVazio: '💡 Haga preguntas sobre los resultados de la auditoría',
    digitando: 'La IA está escribiendo...',
    ouvindo: 'Escuchando…',
    placeholder: 'Haga una pregunta sobre los resultados...',
    enviar: 'Enviar',
  },
})

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
  ERRO_BD: { icon: '🚨', label: 'tipoErroBd', cor: '#b91c1c', bg: '#fef2f2', borda: '#fca5a5' },
  INCONSISTENCIA_PORTAL: { icon: '⚠️', label: 'tipoInconsist', cor: '#b45309', bg: '#fef9ed', borda: '#fcd97d' },
  QUALIDADE: { icon: '🔍', label: 'tipoQualidade', cor: '#7c2d12', bg: '#fefce8', borda: '#fed7aa' },
} as const

const SEV_CONFIG = {
  CRITICO: { label: 'sevCritico', bg: '#fef2f2', cor: '#b91c1c', borda: '#fca5a5' },
  GRAVE: { label: 'sevGrave', bg: '#fff7ed', cor: '#c2410c', borda: '#fdba74' },
  MEDIA: { label: 'sevMedia', bg: '#fff7ed', cor: '#c2410c', borda: '#fdba74' },
  BAIXA: { label: 'sevBaixa', bg: '#e6f2f1', cor: '#0f766e', borda: '#9fcdc8' },
} as const

export default function Auditoria() {
  const [loading, setLoading] = useState(false)
  const [resultado, setResultado] = useState<AuditoriaResultado | null>(null)
  const [erro, setErro] = useState('')
  const [filtroTipo, setFiltroTipo] = useState<string>('todos')
  const [chatMsgs, setChatMsgs] = useState<ChatMsg[]>([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const voz = useVoz()
  const t = useT(MSG)
  const { lang } = useI18n()

  // Mensagens dos alertas e respostas do chat vêm no idioma escolhido:
  // ao trocar o idioma, descarta o resultado para não misturar idiomas.
  const [langAnterior, setLangAnterior] = useState(lang)
  if (lang !== langAnterior) {
    setLangAnterior(lang)
    setResultado(null)
    setErro('')
    setChatMsgs([])
  }

  const executarAuditoria = async () => {
    setLoading(true)
    setErro('')
    setChatMsgs([])
    voz.pararFala()
    try {
      for await (const event of streamPost<StreamEvent>('/auditoria/executar/stream')) {
        if (event.tipo === 'status') {
          // Update UI with status - keep same loading screen
        } else if (event.tipo === 'resultado' && event.dados) {
          setResultado(event.dados)
        } else if (event.tipo === 'erro') {
          setErro(event.msg || t('erroDesconhecido'))
        } else if (event.tipo === 'fim') {
          setLoading(false)
        }
      }
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : t('erroExecutar'))
      setLoading(false)
    }
  }

  // porVoz: pergunta falada no microfone → a resposta também é lida em voz alta.
  const enviarChatMsg = async (texto = chatInput, porVoz = false) => {
    if (!texto.trim() || !resultado || chatLoading) return
    voz.pararFala()
    const idResposta = `msg-${chatMsgs.length + 1}`

    const novaMsg: ChatMsg = { role: 'user', content: texto }
    setChatMsgs(prev => [...prev, novaMsg])
    setChatInput('')
    setChatLoading(true)

    try {
      const data = await apiClient.post('/auditoria/chat', { pergunta: texto, contexto: resultado })
      setChatMsgs(prev => [...prev, { role: 'assistant', content: data.data.resposta }])
      if (porVoz || voz.lerRespostas) voz.falar(data.data.resposta, idResposta)
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : t('erroIa')
      setChatMsgs(prev => [...prev, { role: 'assistant', content: t('erroPrefixo', { msg: errMsg }) }])
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
            <h2 style={{ fontFamily: 'Inter, sans-serif', fontSize: 22, fontWeight: 700, color: 'var(--texto)', marginBottom: 8 }}>
              {t('titulo')}
            </h2>
            <p style={{ fontSize: 14, color: 'var(--texto-suave)', lineHeight: 1.6, maxWidth: 560 }}>
              {t('subtitulo')}
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
              fontFamily: 'Inter',
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
              <><span className="spinner" style={{ width: 18, height: 18, borderWidth: 2, borderColor: 'rgba(255,255,255,0.3)', borderTopColor: '#fff' }} /> {t('executando')}</>
            ) : (
              <>{resultado ? t('reexecutar') : t('executar')}</>
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
          <p style={{ marginTop: 20, fontFamily: 'Inter, sans-serif', fontSize: 18, fontWeight: 700, color: 'var(--texto)' }}>{t('carregandoTitulo')}</p>
          <p style={{ marginTop: 8, fontSize: 14, color: 'var(--texto-suave)' }}>{t('carregandoSub')}</p>
        </div>
      )}

      {/* ── Resultado ── */}
      {resultado && !loading && (
        <>
          {/* Cards de Métricas */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14, marginBottom: 20 }}>
            <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 14, padding: '18px 20px' }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--texto-suave)', textTransform: 'uppercase', marginBottom: 8 }}>{t('mTotalLics')}</div>
              <div style={{ fontSize: 32, fontFamily: 'Inter, sans-serif', fontWeight: 700, color: 'var(--verde)' }}>{resultado.metricas.total_licitacoes_agro}</div>
              <div style={{ fontSize: 11, color: 'var(--texto-suave)', marginTop: 4 }}>{t('mTotalLicsSub')}</div>
            </div>

            <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 14, padding: '18px 20px' }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--texto-suave)', textTransform: 'uppercase', marginBottom: 8 }}>{t('mCobertura')}</div>
              <div style={{ fontSize: 32, fontFamily: 'Inter, sans-serif', fontWeight: 700, color: 'var(--verde)' }}>{resultado.metricas.taxa_cobertura_pct}%</div>
              <div style={{ fontSize: 11, color: 'var(--texto-suave)', marginTop: 4 }}>{t('mCoberturaSub', { n: resultado.metricas.lics_com_docs })}</div>
            </div>

            <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 14, padding: '18px 20px' }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--texto-suave)', textTransform: 'uppercase', marginBottom: 8 }}>{t('mCriticos')}</div>
              <div style={{ fontSize: 32, fontFamily: 'Inter, sans-serif', fontWeight: 700, color: '#b91c1c' }}>{resultado.metricas.alertas_criticos}</div>
              <div style={{ fontSize: 11, color: 'var(--texto-suave)', marginTop: 4 }}>{t('mCriticosSub')}</div>
            </div>

            <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 14, padding: '18px 20px' }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--texto-suave)', textTransform: 'uppercase', marginBottom: 8 }}>{t('mEmpenhos')}</div>
              <div style={{ fontSize: 32, fontFamily: 'Inter, sans-serif', fontWeight: 700, color: '#c2410c' }}>{resultado.metricas.empenhos_sem_docs}</div>
              <div style={{ fontSize: 11, color: 'var(--texto-suave)', marginTop: 4 }}>{t('mEmpenhosSub')}</div>
            </div>
          </div>

          {/* Resumo */}
          <div style={{ background: 'var(--verde-fundo)', border: '1px solid var(--borda)', borderRadius: 14, padding: '18px 22px', marginBottom: 20 }}>
            <div style={{ fontSize: 12, fontWeight: 800, color: 'var(--verde)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>{t('resumo')}</div>
            <p style={{ fontSize: 14, color: 'var(--texto)', lineHeight: 1.6 }}>
              {resultado.metricas.alertas_criticos > 0
                ? t('resumoCritico', { n: resultado.metricas.alertas_criticos })
                : t('resumoSemCritico')
              }
              {t('resumoCobertura', { pct: resultado.metricas.taxa_cobertura_pct, com: resultado.metricas.lics_com_docs, total: resultado.metricas.total_licitacoes_agro })}
              {resultado.metricas.alertas_graves > 0 && t('resumoGraves', { n: resultado.metricas.alertas_graves })}
            </p>
          </div>

          {/* Filtros */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--texto-suave)' }}>{t('filtrar')}</span>
            <button onClick={() => setFiltroTipo('todos')}
              style={{ background: filtroTipo === 'todos' ? 'var(--verde)' : 'var(--branco)', color: filtroTipo === 'todos' ? '#fff' : 'var(--texto-suave)', border: '1px solid var(--borda)', borderRadius: 8, padding: '5px 12px', fontFamily: 'Inter', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>
              {t('todos')}
            </button>
            {Object.entries(TIPO_CONFIG).map(([tipo, cfg]) => (
              <button key={tipo} onClick={() => setFiltroTipo(filtroTipo === tipo ? 'todos' : tipo)}
                style={{ background: filtroTipo === tipo ? cfg.bg : 'var(--branco)', color: filtroTipo === tipo ? cfg.cor : 'var(--texto-suave)', border: `1px solid ${filtroTipo === tipo ? cfg.borda : 'var(--borda)'}`, borderRadius: 8, padding: '5px 12px', fontFamily: 'Inter', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>
                {t(cfg.label)} ({contPorTipo(tipo)})
              </button>
            ))}
            <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--texto-suave)', fontWeight: 600 }}>
              {t('nAlertas', { n: alertasFiltrados.length })}
            </span>
          </div>

          {/* Lista de Alertas */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 30 }}>
            {alertasFiltrados.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px 24px', color: 'var(--texto-suave)' }}>
                {t('nenhumAlerta')}
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
                          {alerta.processo && <div style={{ fontSize: 11, color: tipo.cor, fontWeight: 600, marginTop: 2 }}>{t('processo')} <strong>{alerta.processo}</strong></div>}
                        </div>
                      </div>
                      <span style={{ background: sev.bg, color: sev.cor, border: `1px solid ${sev.borda}`, fontSize: 11, fontWeight: 700, padding: '4px 10px', borderRadius: 6, whiteSpace: 'nowrap' }}>
                        ● {t(sev.label)}
                      </span>
                    </div>
                  </div>
                )
              })
            )}
          </div>

          {/* Chat com IA */}
          <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 16, padding: '20px', marginBottom: 20 }}>
            <h3 style={{ fontFamily: 'Inter, sans-serif', fontSize: 16, fontWeight: 700, color: 'var(--texto)', marginBottom: 16 }}>
              {t('chatTitulo')}
            </h3>

            {/* Chat Messages */}
            <div style={{ background: 'var(--cinza-claro)', borderRadius: 12, padding: '16px', maxHeight: 400, overflowY: 'auto', marginBottom: 16 }}>
              {chatMsgs.length === 0 ? (
                <p style={{ fontSize: 13, color: 'var(--texto-suave)', textAlign: 'center', padding: '20px 0' }}>
                  {t('chatVazio')}
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
                      {msg.role === 'assistant' && (
                        <OuvirResposta voz={voz} id={`msg-${i}`} texto={msg.content} />
                      )}
                    </div>
                  </div>
                ))
              )}
              {chatLoading && (
                <div style={{ fontSize: 12, color: 'var(--texto-suave)', display: 'flex', gap: 4, alignItems: 'center' }}>
                  <span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> {t('digitando')}
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
                placeholder={voz.ouvindo ? t('ouvindo') : t('placeholder')}
                disabled={chatLoading}
                style={{
                  flex: 1,
                  padding: '10px 14px',
                  borderRadius: 10,
                  border: '1px solid var(--borda)',
                  fontFamily: 'Inter',
                  fontSize: 13,
                  color: 'var(--texto)',
                  opacity: chatLoading ? 0.6 : 1,
                  cursor: chatLoading ? 'not-allowed' : 'text'
                }}
              />
              <BotoesVoz voz={voz} disabled={chatLoading} onParcial={setChatInput} onFinal={txt => enviarChatMsg(txt, true)} />
              <button
                onClick={() => enviarChatMsg()}
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
                <Send size={16} /> {t('enviar')}
              </button>
            </div>
            <AvisoVoz voz={voz} />
          </div>
        </>
      )}
    </div>
  )
}
