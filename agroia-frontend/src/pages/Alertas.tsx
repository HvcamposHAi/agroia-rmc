import { useState } from 'react'
import {
  BadgeDollarSign, BellRing, CircleAlert, Info, Lightbulb, PackageX, RefreshCw,
  Search, SearchX, Sparkles, TrendingUp, TriangleAlert,
} from 'lucide-react'
import StatusBadge from '../components/StatusBadge'
import { TONS, type Tom } from '../lib/tons'
import PageHeader from '../components/PageHeader'
import { streamPost } from '../lib/apiClient'
import { defineMessages, useI18n, useT } from '../i18n'

const MSG = defineMessages({
  pt: {
    tipoAlta: 'Alta de Preço',
    tipoDesab: 'Risco de Desabastecimento',
    tipoDesabCurto: 'Desabastecimento',
    tipoSuper: 'Superfaturamento',
    sevAlta: 'Alta',
    sevMedia: 'Média',
    sevBaixa: 'Baixa',
    erroDesconhecido: 'Erro desconhecido',
    erroConexao: 'Erro ao conectar ao servidor',
    eyebrow: 'Gestão',
    titulo: 'Alertas de risco',
    subtitulo: 'A IA analisa o histórico de licitações da SMSAN/FAAC e identifica automaticamente riscos de alta de preço, desabastecimento e superfaturamento por cultura.',
    fonte: 'Fonte: licitações SMSAN/FAAC — Portal da Transparência de Curitiba',
    analisando: 'Analisando...',
    reanalisar: 'Reanalisar',
    analisar: 'Analisar dados',
    descAlta: 'Variação acima de 20% entre períodos',
    descDesab: 'Culturas sem compra há mais de 12 meses',
    descSuper: 'Preço/kg muito acima da média histórica',
    carregandoTitulo: 'Analisando dados históricos...',
    carregandoSub: 'A IA está processando o histórico de licitações da SMSAN/FAAC',
    resumo: 'Resumo da análise',
    geradoIa: 'Gerado por IA',
    avisoIa: 'Os alertas são indicações automáticas: confira-os nos dados de origem (licitações e itens) antes de qualquer decisão.',
    totalAlertas: 'Total de Alertas',
    filtrar: 'Filtrar:',
    todos: 'Todos',
    severidade: 'Severidade {s}',
    nAlertas: '{n} alertas',
    recomendacao: 'Recomendação:',
    semAlertasTitulo: 'Nenhum alerta',
    semAlertas: 'Nenhum alerta corresponde aos filtros selecionados.',
  },
  en: {
    tipoAlta: 'Price Increase',
    tipoDesab: 'Shortage Risk',
    tipoDesabCurto: 'Shortage',
    tipoSuper: 'Overpricing',
    sevAlta: 'High',
    sevMedia: 'Medium',
    sevBaixa: 'Low',
    erroDesconhecido: 'Unknown error',
    erroConexao: 'Error connecting to the server',
    eyebrow: 'Management',
    titulo: 'Risk alerts',
    subtitulo: 'The AI analyzes the SMSAN/FAAC bidding history and automatically identifies price increase, shortage and overpricing risks by crop.',
    fonte: 'Source: SMSAN/FAAC biddings — Curitiba Transparency Portal',
    analisando: 'Analyzing...',
    reanalisar: 'Analyze again',
    analisar: 'Analyze data',
    descAlta: 'Change above 20% between periods',
    descDesab: 'Crops not purchased for over 12 months',
    descSuper: 'Price/kg well above the historical average',
    carregandoTitulo: 'Analyzing historical data...',
    carregandoSub: 'The AI is processing the SMSAN/FAAC bidding history',
    resumo: 'Analysis summary',
    geradoIa: 'AI-generated',
    avisoIa: 'Alerts are automated indications: check them against the source data (biddings and items) before making any decision.',
    totalAlertas: 'Total Alerts',
    filtrar: 'Filter:',
    todos: 'All',
    severidade: '{s} severity',
    nAlertas: '{n} alerts',
    recomendacao: 'Recommendation:',
    semAlertasTitulo: 'No alerts',
    semAlertas: 'No alerts match the selected filters.',
  },
  es: {
    tipoAlta: 'Alza de Precio',
    tipoDesab: 'Riesgo de Desabastecimiento',
    tipoDesabCurto: 'Desabastecimiento',
    tipoSuper: 'Sobrefacturación',
    sevAlta: 'Alta',
    sevMedia: 'Media',
    sevBaixa: 'Baja',
    erroDesconhecido: 'Error desconocido',
    erroConexao: 'Error al conectar con el servidor',
    eyebrow: 'Gestión',
    titulo: 'Alertas de riesgo',
    subtitulo: 'La IA analiza el historial de licitaciones de la SMSAN/FAAC e identifica automáticamente riesgos de alza de precio, desabastecimiento y sobrefacturación por cultivo.',
    fonte: 'Fuente: licitaciones SMSAN/FAAC — Portal de la Transparencia de Curitiba',
    analisando: 'Analizando...',
    reanalisar: 'Volver a analizar',
    analisar: 'Analizar datos',
    descAlta: 'Variación superior al 20% entre períodos',
    descDesab: 'Cultivos sin compra hace más de 12 meses',
    descSuper: 'Precio/kg muy por encima del promedio histórico',
    carregandoTitulo: 'Analizando datos históricos...',
    carregandoSub: 'La IA está procesando el historial de licitaciones de la SMSAN/FAAC',
    resumo: 'Resumen del análisis',
    geradoIa: 'Generado por IA',
    avisoIa: 'Las alertas son indicaciones automáticas: verifíquelas en los datos de origen (licitaciones e ítems) antes de cualquier decisión.',
    totalAlertas: 'Total de Alertas',
    filtrar: 'Filtrar:',
    todos: 'Todos',
    severidade: 'Severidad {s}',
    nAlertas: '{n} alertas',
    recomendacao: 'Recomendación:',
    semAlertasTitulo: 'Ninguna alerta',
    semAlertas: 'Ninguna alerta coincide con los filtros seleccionados.',
  },
})

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

interface StreamEvent {
  tipo: 'status' | 'resultado' | 'erro' | 'fim'
  msg?: string
  dados?: ResultadoAlertas
}

// Tipo de alerta: ícone + família de cor de status (tokens do index.css).
const TIPO_CONFIG = {
  ALTA_PRECO: { Icon: TrendingUp, label: 'tipoAlta', tom: 'aviso' as Tom },
  DESABASTECIMENTO: { Icon: PackageX, label: 'tipoDesab', tom: 'info' as Tom },
  SUPERFATURAMENTO: { Icon: BadgeDollarSign, label: 'tipoSuper', tom: 'erro' as Tom },
} as const

// Severidade: sempre texto + ícone (não depende só da cor — WCAG 1.4.1).
const SEV_CONFIG = {
  ALTA: { Icon: TriangleAlert, label: 'sevAlta', tom: 'erro' as Tom },
  MEDIA: { Icon: CircleAlert, label: 'sevMedia', tom: 'aviso' as Tom },
  BAIXA: { Icon: Info, label: 'sevBaixa', tom: 'info' as Tom },
} as const


export default function Alertas() {
  const [loading, setLoading] = useState(false)
  const [resultado, setResultado] = useState<ResultadoAlertas | null>(null)
  const [erro, setErro] = useState('')
  const [filtroTipo, setFiltroTipo] = useState<string>('todos')
  const [filtroSev, setFiltroSev] = useState<string>('todas')
  const t = useT(MSG)
  const { lang } = useI18n()

  // Os alertas são gerados pela IA no idioma escolhido: ao trocar o idioma,
  // descarta o resultado anterior para não exibir texto em outro idioma.
  const [langAnterior, setLangAnterior] = useState(lang)
  if (lang !== langAnterior) {
    setLangAnterior(lang)
    setResultado(null)
    setErro('')
  }

  const analisar = async () => {
    setLoading(true)
    setErro('')
    setResultado(null)
    try {
      for await (const event of streamPost<StreamEvent>('/alertas/stream')) {
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
      setErro(e instanceof Error ? e.message : t('erroConexao'))
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

      {/* ── Cabeçalho ── */}
      <PageHeader
        eyebrow={t('eyebrow')}
        title={t('titulo')}
        subtitle={t('subtitulo')}
        source={t('fonte')}
        actions={
          <button className="btn btn-primario" onClick={analisar} disabled={loading}>
            {loading ? (
              <><span className="spinner" style={{ width: 16, height: 16, borderWidth: 2, borderColor: 'rgba(255,255,255,0.3)', borderTopColor: '#fff' }} /> {t('analisando')}</>
            ) : resultado ? (
              <><RefreshCw size={16} aria-hidden /> {t('reanalisar')}</>
            ) : (
              <><Search size={16} aria-hidden /> {t('analisar')}</>
            )}
          </button>
        }
      />

      {/* ── O que é analisado (antes da primeira análise) ── */}
      {!resultado && !loading && !erro && (
        <div className="card lista-pontos" style={{ marginBottom: 20 }}>
          {[
            { Icon: TrendingUp, label: t('tipoAlta'), desc: t('descAlta') },
            { Icon: PackageX, label: t('tipoDesabCurto'), desc: t('descDesab') },
            { Icon: BadgeDollarSign, label: t('tipoSuper'), desc: t('descSuper') },
          ].map(({ Icon, label, desc }) => (
            <div key={label}>
              <Icon size={18} aria-hidden />
              <div>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--texto)' }}>{label}</div>
                <div style={{ fontSize: 12, color: 'var(--texto-suave)' }}>{desc}</div>
              </div>
            </div>
          ))}
        </div>
      )}

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

      {/* ── Resultado (gerado por IA) ── */}
      {resultado && !loading && (
        <>
          {/* Resumo + selo de IA + aviso de verificação */}
          <div style={{ background: 'var(--verde-fundo)', border: '1px solid var(--borda)', borderRadius: 'var(--raio)', padding: '18px 22px', marginBottom: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
              <div style={{ fontSize: 12, fontWeight: 800, color: 'var(--verde)', textTransform: 'uppercase', letterSpacing: 0.5 }}>{t('resumo')}</div>
              <span className="ai-label"><Sparkles size={12} aria-hidden /> {t('geradoIa')}</span>
            </div>
            <p style={{ fontSize: 14, color: 'var(--texto)', lineHeight: 1.7 }}>{resultado.resumo}</p>
            <p style={{ display: 'flex', gap: 6, alignItems: 'flex-start', marginTop: 10, fontSize: 12.5, color: 'var(--texto-suave)', lineHeight: 1.5 }}>
              <Info size={14} aria-hidden style={{ flexShrink: 0, marginTop: 2 }} />
              {t('avisoIa')}
            </p>
          </div>

          {/* Cards de contagem (clicáveis = filtro por tipo) */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginBottom: 20 }}>
            {(['ALTA_PRECO', 'DESABASTECIMENTO', 'SUPERFATURAMENTO'] as const).map(tipo => {
              const { Icon, label, tom } = TIPO_CONFIG[tipo]
              const { cor, bg, borda } = TONS[tom]
              const ativo = filtroTipo === tipo
              return (
                <button key={tipo} type="button" aria-pressed={ativo}
                  onClick={() => setFiltroTipo(ativo ? 'todos' : tipo)}
                  style={{ textAlign: 'left', font: 'inherit', background: ativo ? bg : 'var(--branco)', border: `1.5px solid ${ativo ? borda : 'var(--borda)'}`, borderRadius: 'var(--raio)', padding: '16px 18px', cursor: 'pointer', transition: 'all 0.15s', boxShadow: 'var(--sombra-1)' }}>
                  <Icon size={20} aria-hidden style={{ color: cor, marginBottom: 8 }} />
                  <div style={{ fontSize: 28, fontFamily: 'Inter, sans-serif', fontWeight: 700, color: cor }}>{contPorTipo(tipo)}</div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--texto-suave)', marginTop: 4 }}>{t(label)}</div>
                </button>
              )
            })}
            <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 'var(--raio)', padding: '16px 18px', boxShadow: 'var(--sombra-1)' }}>
              <BellRing size={20} aria-hidden style={{ color: 'var(--texto-suave)', marginBottom: 8 }} />
              <div style={{ fontSize: 28, fontFamily: 'Inter, sans-serif', fontWeight: 700, color: 'var(--texto)' }}>{resultado.alertas.length}</div>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--texto-suave)', marginTop: 4 }}>{t('totalAlertas')}</div>
            </div>
          </div>

          {/* Filtros */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--texto-suave)' }}>{t('filtrar')}</span>
            <button type="button" className="chip-filtro" aria-pressed={filtroTipo === 'todos'}
              onClick={() => setFiltroTipo('todos')}>
              {t('todos')}
            </button>
            {(['ALTA', 'MEDIA', 'BAIXA'] as const).map(sev => {
              const { Icon, label, tom } = SEV_CONFIG[sev]
              const ativo = filtroSev === sev
              return (
                <button key={sev} type="button" className={`chip-filtro ${tom}`} aria-pressed={ativo}
                  onClick={() => setFiltroSev(ativo ? 'todas' : sev)}>
                  <Icon size={14} aria-hidden /> {t('severidade', { s: t(label) })}
                </button>
              )
            })}
            <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--texto-suave)', fontWeight: 600 }}>
              {t('nAlertas', { n: alertasFiltrados.length })}
            </span>
          </div>

          {/* Lista de alertas */}
          {alertasFiltrados.length === 0 ? (
            <div className="card empty-state">
              <SearchX size={32} aria-hidden />
              <strong>{t('semAlertasTitulo')}</strong>
              {t('semAlertas')}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {alertasFiltrados.map((alerta, i) => {
                const tipo = TIPO_CONFIG[alerta.tipo] ?? TIPO_CONFIG.ALTA_PRECO
                const sev = SEV_CONFIG[alerta.severidade] ?? SEV_CONFIG.BAIXA
                const TipoIcon = tipo.Icon
                const corTipo = TONS[tipo.tom]
                return (
                  <div key={i} style={{ background: 'var(--branco)', border: `1px solid ${corTipo.borda}`, borderLeft: `4px solid ${corTipo.cor}`, borderRadius: 'var(--raio)', padding: '18px 20px', boxShadow: 'var(--sombra-1)' }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 10 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <TipoIcon size={20} aria-hidden style={{ color: corTipo.cor, flexShrink: 0 }} />
                        <div>
                          <div style={{ fontSize: 15, fontWeight: 800, color: 'var(--texto)' }}>{alerta.titulo}</div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: corTipo.cor, fontWeight: 700, marginTop: 4 }}>{t(tipo.label)} · <StatusBadge tom={tipo.tom}>{alerta.cultura}</StatusBadge></div>
                        </div>
                      </div>
                      <StatusBadge tom={sev.tom} icon={sev.Icon}>{t('severidade', { s: t(sev.label) })}</StatusBadge>
                    </div>
                    <p style={{ fontSize: 13, color: 'var(--texto)', lineHeight: 1.6, marginBottom: 10 }}>{alerta.descricao}</p>
                    <div style={{ background: 'var(--cinza-claro)', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: 'var(--texto-suave)', display: 'flex', gap: 8 }}>
                      <Lightbulb size={16} aria-hidden style={{ flexShrink: 0, marginTop: 1, color: 'var(--amarelo)' }} />
                      <span><strong style={{ color: 'var(--texto)' }}>{t('recomendacao')}</strong> {alerta.recomendacao}</span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </>
      )}
    </div>
  )
}
