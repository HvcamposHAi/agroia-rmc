import { useState } from 'react'
import {
  CircleAlert, CircleCheck, ClipboardList, Database, FileCheck, FileText, FileWarning,
  Info, Lightbulb, MessageSquare, OctagonAlert, Play, ReceiptText, RefreshCw, Send,
  Sparkles, TriangleAlert,
} from 'lucide-react'
import StatusBadge from '../components/StatusBadge'
import { TONS, type Tom } from '../lib/tons'
import PageHeader from '../components/PageHeader'
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
    eyebrow: 'Gestão',
    titulo: 'Qualidade dos dados',
    subtitulo: 'Verifique a integridade dos dados coletados. Identifica licitações sem documentação, empenhos sem cobertura documental e inconsistências na base de dados.',
    fonte: 'Fonte: licitações SMSAN/FAAC — Portal da Transparência de Curitiba',
    executando: 'Executando...',
    reexecutar: 'Executar novamente',
    executar: 'Executar auditoria',
    carregandoTitulo: 'Executando auditoria...',
    carregandoSub: 'Analisando licitações e documentos no banco de dados',
    mTotalLics: 'Total Licitações',
    mTotalLicsSub: 'Agrícolas no sistema',
    mCobertura: 'Cobertura',
    mCoberturaSub: '{n} com documentação',
    mCriticos: 'Críticos',
    mCriticosSub: 'Empenhos sem docs',
    mEmpenhos: 'Empenhos',
    mEmpenhosSub: 'Sem documentação',
    resumo: 'Resumo',
    resumoCritico: 'CRÍTICO: {n} licitação(ões) com empenho(s) mas SEM documentação. ',
    resumoSemCritico: 'Nenhum alerta crítico. ',
    resumoCobertura: 'Taxa de cobertura: {pct}% ({com}/{total}).',
    resumoGraves: ' {n} licitação(ões) concluída(s) sem documentação.',
    filtrar: 'Filtrar:',
    todos: 'Todos',
    nAlertas: '{n} alerta(s)',
    nenhumAlertaTitulo: 'Nenhum alerta',
    nenhumAlerta: 'Nenhum alerta com os filtros selecionados',
    processo: 'Processo:',
    chatTitulo: 'Discuta com IA',
    geradoIa: 'Respostas geradas por IA',
    chatVazio: 'Faça perguntas sobre os resultados da auditoria',
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
    eyebrow: 'Management',
    titulo: 'Data quality',
    subtitulo: 'Check the integrity of the collected data. Identifies biddings without documents, commitments without document coverage and inconsistencies in the database.',
    fonte: 'Source: SMSAN/FAAC biddings — Curitiba Transparency Portal',
    executando: 'Running...',
    reexecutar: 'Run again',
    executar: 'Run audit',
    carregandoTitulo: 'Running audit...',
    carregandoSub: 'Analyzing biddings and documents in the database',
    mTotalLics: 'Total Biddings',
    mTotalLicsSub: 'Agricultural in the system',
    mCobertura: 'Coverage',
    mCoberturaSub: '{n} with documents',
    mCriticos: 'Critical',
    mCriticosSub: 'Commitments without docs',
    mEmpenhos: 'Commitments',
    mEmpenhosSub: 'Without documents',
    resumo: 'Summary',
    resumoCritico: 'CRITICAL: {n} bidding(s) with commitment(s) but NO documents. ',
    resumoSemCritico: 'No critical alerts. ',
    resumoCobertura: 'Coverage rate: {pct}% ({com}/{total}).',
    resumoGraves: ' {n} completed bidding(s) without documents.',
    filtrar: 'Filter:',
    todos: 'All',
    nAlertas: '{n} alert(s)',
    nenhumAlertaTitulo: 'No alerts',
    nenhumAlerta: 'No alerts match the selected filters',
    processo: 'Process:',
    chatTitulo: 'Discuss with AI',
    geradoIa: 'AI-generated answers',
    chatVazio: 'Ask questions about the audit results',
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
    eyebrow: 'Gestión',
    titulo: 'Calidad de datos',
    subtitulo: 'Verifique la integridad de los datos recolectados. Identifica licitaciones sin documentación, compromisos sin cobertura documental e inconsistencias en la base de datos.',
    fonte: 'Fuente: licitaciones SMSAN/FAAC — Portal de la Transparencia de Curitiba',
    executando: 'Ejecutando...',
    reexecutar: 'Volver a ejecutar',
    executar: 'Ejecutar auditoría',
    carregandoTitulo: 'Ejecutando auditoría...',
    carregandoSub: 'Analizando licitaciones y documentos en la base de datos',
    mTotalLics: 'Total Licitaciones',
    mTotalLicsSub: 'Agrícolas en el sistema',
    mCobertura: 'Cobertura',
    mCoberturaSub: '{n} con documentación',
    mCriticos: 'Críticos',
    mCriticosSub: 'Compromisos sin docs',
    mEmpenhos: 'Compromisos',
    mEmpenhosSub: 'Sin documentación',
    resumo: 'Resumen',
    resumoCritico: 'CRÍTICO: {n} licitación(es) con compromiso(s) pero SIN documentación. ',
    resumoSemCritico: 'Ninguna alerta crítica. ',
    resumoCobertura: 'Tasa de cobertura: {pct}% ({com}/{total}).',
    resumoGraves: ' {n} licitación(es) concluida(s) sin documentación.',
    filtrar: 'Filtrar:',
    todos: 'Todos',
    nAlertas: '{n} alerta(s)',
    nenhumAlertaTitulo: 'Ninguna alerta',
    nenhumAlerta: 'Ninguna alerta con los filtros seleccionados',
    processo: 'Proceso:',
    chatTitulo: 'Converse con la IA',
    geradoIa: 'Respuestas generadas por IA',
    chatVazio: 'Haga preguntas sobre los resultados de la auditoría',
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

// Tipo de alerta: ícone + família de cor de status (tokens do index.css).
const TIPO_CONFIG = {
  ERRO_BD: { Icon: Database, label: 'tipoErroBd', tom: 'erro' as Tom },
  INCONSISTENCIA_PORTAL: { Icon: FileWarning, label: 'tipoInconsist', tom: 'aviso' as Tom },
  QUALIDADE: { Icon: ClipboardList, label: 'tipoQualidade', tom: 'info' as Tom },
} as const

// Severidade: sempre texto + ícone (não depende só da cor — WCAG 1.4.1).
const SEV_CONFIG = {
  CRITICO: { Icon: OctagonAlert, label: 'sevCritico', tom: 'erro' as Tom },
  GRAVE: { Icon: TriangleAlert, label: 'sevGrave', tom: 'aviso' as Tom },
  MEDIA: { Icon: CircleAlert, label: 'sevMedia', tom: 'aviso' as Tom },
  BAIXA: { Icon: Info, label: 'sevBaixa', tom: 'info' as Tom },
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
      {/* ── Cabeçalho ── */}
      <PageHeader
        eyebrow={t('eyebrow')}
        title={t('titulo')}
        subtitle={t('subtitulo')}
        source={t('fonte')}
        actions={
          <button className="btn btn-primario" onClick={executarAuditoria} disabled={loading}>
            {loading ? (
              <><span className="spinner" style={{ width: 16, height: 16, borderWidth: 2, borderColor: 'rgba(255,255,255,0.3)', borderTopColor: '#fff' }} /> {t('executando')}</>
            ) : resultado ? (
              <><RefreshCw size={16} aria-hidden /> {t('reexecutar')}</>
            ) : (
              <><Play size={16} aria-hidden /> {t('executar')}</>
            )}
          </button>
        }
      />

      {/* ── Erro ── */}
      {erro && (
        <div className="aviso-box erro" role="alert" style={{ marginBottom: 16 }}>
          <CircleAlert size={16} aria-hidden />
          <span>{erro}</span>
        </div>
      )}

      {/* ── Loading ── */}
      {loading && (
        <div className="card" style={{ padding: '48px 24px', textAlign: 'center', marginBottom: 20 }} role="status">
          <span className="spinner" style={{ width: 48, height: 48, borderWidth: 3 }} />
          <p style={{ marginTop: 20, fontFamily: 'Inter, sans-serif', fontSize: 18, fontWeight: 700, color: 'var(--texto)' }}>{t('carregandoTitulo')}</p>
          <p style={{ marginTop: 8, fontSize: 14, color: 'var(--texto-suave)' }}>{t('carregandoSub')}</p>
        </div>
      )}

      {/* ── Resultado ── */}
      {resultado && !loading && (
        <>
          {/* Cards de Métricas */}
          <div className="metrics-grid" style={{ marginBottom: 20 }}>
            <div className="metric-card verde">
              <span className="metric-icon"><FileText size={18} aria-hidden /></span>
              <div className="metric-label">{t('mTotalLics')}</div>
              <div className="metric-value" style={{ color: 'var(--verde)' }}>{resultado.metricas.total_licitacoes_agro}</div>
              <div className="metric-sub">{t('mTotalLicsSub')}</div>
            </div>
            <div className="metric-card ceu">
              <span className="metric-icon"><FileCheck size={18} aria-hidden /></span>
              <div className="metric-label">{t('mCobertura')}</div>
              <div className="metric-value" style={{ color: 'var(--verde)' }}>{resultado.metricas.taxa_cobertura_pct}%</div>
              <div className="metric-sub">{t('mCoberturaSub', { n: resultado.metricas.lics_com_docs })}</div>
            </div>
            <div className="metric-card terra">
              <span className="metric-icon" style={{ background: 'var(--erro-fundo)', color: 'var(--erro)' }}><OctagonAlert size={18} aria-hidden /></span>
              <div className="metric-label">{t('mCriticos')}</div>
              <div className="metric-value" style={{ color: 'var(--erro)' }}>{resultado.metricas.alertas_criticos}</div>
              <div className="metric-sub">{t('mCriticosSub')}</div>
            </div>
            <div className="metric-card amarelo">
              <span className="metric-icon"><ReceiptText size={18} aria-hidden /></span>
              <div className="metric-label">{t('mEmpenhos')}</div>
              <div className="metric-value" style={{ color: 'var(--aviso)' }}>{resultado.metricas.empenhos_sem_docs}</div>
              <div className="metric-sub">{t('mEmpenhosSub')}</div>
            </div>
          </div>

          {/* Resumo */}
          <div style={{ background: 'var(--verde-fundo)', border: '1px solid var(--borda)', borderRadius: 'var(--raio)', padding: '18px 22px', marginBottom: 20 }}>
            <div style={{ fontSize: 12, fontWeight: 800, color: 'var(--verde)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>{t('resumo')}</div>
            <p style={{ fontSize: 14, color: 'var(--texto)', lineHeight: 1.6 }}>
              {resultado.metricas.alertas_criticos > 0 ? (
                <strong style={{ color: 'var(--erro)' }}>
                  <TriangleAlert size={15} aria-hidden style={{ verticalAlign: '-2px', marginRight: 4 }} />
                  {t('resumoCritico', { n: resultado.metricas.alertas_criticos })}
                </strong>
              ) : (
                <span style={{ color: 'var(--ok)', fontWeight: 600 }}>
                  <CircleCheck size={15} aria-hidden style={{ verticalAlign: '-2px', marginRight: 4 }} />
                  {t('resumoSemCritico')}
                </span>
              )}
              {t('resumoCobertura', { pct: resultado.metricas.taxa_cobertura_pct, com: resultado.metricas.lics_com_docs, total: resultado.metricas.total_licitacoes_agro })}
              {resultado.metricas.alertas_graves > 0 && t('resumoGraves', { n: resultado.metricas.alertas_graves })}
            </p>
          </div>

          {/* Filtros */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--texto-suave)' }}>{t('filtrar')}</span>
            <button type="button" className="chip-filtro" aria-pressed={filtroTipo === 'todos'}
              onClick={() => setFiltroTipo('todos')}>
              {t('todos')}
            </button>
            {Object.entries(TIPO_CONFIG).map(([tipo, cfg]) => {
              const ativo = filtroTipo === tipo
              const Icon = cfg.Icon
              return (
                <button key={tipo} type="button" className={`chip-filtro ${cfg.tom}`} aria-pressed={ativo}
                  onClick={() => setFiltroTipo(ativo ? 'todos' : tipo)}>
                  <Icon size={14} aria-hidden /> {t(cfg.label)} ({contPorTipo(tipo)})
                </button>
              )
            })}
            <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--texto-suave)', fontWeight: 600 }}>
              {t('nAlertas', { n: alertasFiltrados.length })}
            </span>
          </div>

          {/* Lista de Alertas */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 30 }}>
            {alertasFiltrados.length === 0 ? (
              <div className="card empty-state">
                <CircleCheck size={32} aria-hidden />
                <strong>{t('nenhumAlertaTitulo')}</strong>
                {t('nenhumAlerta')}
              </div>
            ) : (
              alertasFiltrados.map((alerta, i) => {
                const tipo = TIPO_CONFIG[alerta.tipo as keyof typeof TIPO_CONFIG] || TIPO_CONFIG.QUALIDADE
                const sev = SEV_CONFIG[alerta.severidade as keyof typeof SEV_CONFIG] || SEV_CONFIG.BAIXA
                const TipoIcon = tipo.Icon
                const corTipo = TONS[tipo.tom]
                return (
                  <div key={i} style={{ background: 'var(--branco)', border: `1px solid ${corTipo.borda}`, borderLeft: `4px solid ${corTipo.cor}`, borderRadius: 'var(--raio)', padding: '16px 18px', boxShadow: 'var(--sombra-1)' }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <TipoIcon size={18} aria-hidden style={{ color: corTipo.cor, flexShrink: 0 }} />
                        <div>
                          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--texto)' }}>{alerta.mensagem}</div>
                          {alerta.processo && <div style={{ fontSize: 11, color: corTipo.cor, fontWeight: 600, marginTop: 2 }}>{t('processo')} <strong>{alerta.processo}</strong></div>}
                        </div>
                      </div>
                      <StatusBadge tom={sev.tom} icon={sev.Icon}>{t(sev.label)}</StatusBadge>
                    </div>
                  </div>
                )
              })
            )}
          </div>

          {/* Chat com IA */}
          <div className="card" style={{ marginBottom: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
              <h3 style={{ display: 'flex', alignItems: 'center', gap: 8, fontFamily: 'Inter, sans-serif', fontSize: 16, fontWeight: 700, color: 'var(--texto)', margin: 0 }}>
                <MessageSquare size={18} aria-hidden style={{ color: 'var(--verde)' }} /> {t('chatTitulo')}
              </h3>
              <span className="ai-label"><Sparkles size={12} aria-hidden /> {t('geradoIa')}</span>
            </div>

            {/* Chat Messages */}
            <div style={{ background: 'var(--cinza-claro)', borderRadius: 'var(--raio)', padding: '16px', maxHeight: 400, overflowY: 'auto', marginBottom: 16 }}>
              {chatMsgs.length === 0 ? (
                <p style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, fontSize: 13, color: 'var(--texto-suave)', textAlign: 'center', padding: '20px 0' }}>
                  <Lightbulb size={15} aria-hidden /> {t('chatVazio')}
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
                <div style={{ fontSize: 12, color: 'var(--texto-suave)', display: 'flex', gap: 4, alignItems: 'center' }} role="status">
                  <span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> {t('digitando')}
                </div>
              )}
            </div>

            {/* Chat Input */}
            <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end', flexWrap: 'wrap' }}>
              <input
                type="text"
                className="search-input"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && enviarChatMsg()}
                placeholder={voz.ouvindo ? t('ouvindo') : t('placeholder')}
                aria-label={t('placeholder')}
                disabled={chatLoading}
                style={{ opacity: chatLoading ? 0.6 : 1 }}
              />
              <BotoesVoz voz={voz} disabled={chatLoading} onParcial={setChatInput} onFinal={txt => enviarChatMsg(txt, true)} />
              <button
                className="btn btn-primario"
                onClick={() => enviarChatMsg()}
                disabled={!chatInput.trim() || chatLoading}
              >
                <Send size={16} aria-hidden /> {t('enviar')}
              </button>
            </div>
            <AvisoVoz voz={voz} />
          </div>
        </>
      )}
    </div>
  )
}
