import { useState } from 'react'
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
    titulo: '🤖 Alertas Inteligentes',
    subtitulo: 'A IA analisa o histórico de licitações da SMSAN/FAAC e identifica automaticamente riscos de alta de preço, desabastecimento e superfaturamento por cultura.',
    analisando: 'Analisando...',
    reanalisar: '🔄 Reanalisar',
    analisar: '🔍 Analisar Dados',
    descAlta: 'Variação acima de 20% entre períodos',
    descDesab: 'Culturas sem compra há mais de 12 meses',
    descSuper: 'Preço/kg muito acima da média histórica',
    carregandoTitulo: 'Analisando dados históricos...',
    carregandoSub: 'A IA está processando o histórico de licitações da SMSAN/FAAC',
    resumo: '📋 Resumo da Análise',
    totalAlertas: 'Total de Alertas',
    filtrar: 'Filtrar:',
    todos: 'Todos',
    severidade: 'Severidade {s}',
    nAlertas: '{n} alertas',
    recomendacao: 'Recomendação:',
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
    titulo: '🤖 Smart Alerts',
    subtitulo: 'The AI analyzes the SMSAN/FAAC bidding history and automatically identifies price increase, shortage and overpricing risks by crop.',
    analisando: 'Analyzing...',
    reanalisar: '🔄 Analyze again',
    analisar: '🔍 Analyze Data',
    descAlta: 'Change above 20% between periods',
    descDesab: 'Crops not purchased for over 12 months',
    descSuper: 'Price/kg well above the historical average',
    carregandoTitulo: 'Analyzing historical data...',
    carregandoSub: 'The AI is processing the SMSAN/FAAC bidding history',
    resumo: '📋 Analysis Summary',
    totalAlertas: 'Total Alerts',
    filtrar: 'Filter:',
    todos: 'All',
    severidade: '{s} severity',
    nAlertas: '{n} alerts',
    recomendacao: 'Recommendation:',
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
    titulo: '🤖 Alertas Inteligentes',
    subtitulo: 'La IA analiza el historial de licitaciones de la SMSAN/FAAC e identifica automáticamente riesgos de alza de precio, desabastecimiento y sobrefacturación por cultivo.',
    analisando: 'Analizando...',
    reanalisar: '🔄 Volver a analizar',
    analisar: '🔍 Analizar Datos',
    descAlta: 'Variación superior al 20% entre períodos',
    descDesab: 'Cultivos sin compra hace más de 12 meses',
    descSuper: 'Precio/kg muy por encima del promedio histórico',
    carregandoTitulo: 'Analizando datos históricos...',
    carregandoSub: 'La IA está procesando el historial de licitaciones de la SMSAN/FAAC',
    resumo: '📋 Resumen del Análisis',
    totalAlertas: 'Total de Alertas',
    filtrar: 'Filtrar:',
    todos: 'Todos',
    severidade: 'Severidad {s}',
    nAlertas: '{n} alertas',
    recomendacao: 'Recomendación:',
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

const TIPO_CONFIG = {
  ALTA_PRECO: { icon: '📈', label: 'tipoAlta', cor: '#e65c00', bg: '#fff3ed', borda: '#f5c4a0' },
  DESABASTECIMENTO: { icon: '⚠️', label: 'tipoDesab', cor: '#b45309', bg: '#fef9ed', borda: '#fcd97d' },
  SUPERFATURAMENTO: { icon: '🚨', label: 'tipoSuper', cor: '#b91c1c', bg: '#fef2f2', borda: '#fca5a5' },
} as const

const SEV_CONFIG = {
  ALTA: { label: 'sevAlta', bg: '#fef2f2', cor: '#b91c1c', borda: '#fca5a5' },
  MEDIA: { label: 'sevMedia', bg: '#fff7ed', cor: '#c2410c', borda: '#fdba74' },
  BAIXA: { label: 'sevBaixa', bg: '#e6f2f1', cor: '#0f766e', borda: '#9fcdc8' },
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
            onClick={analisar}
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
              <><span className="spinner" style={{ width: 18, height: 18, borderWidth: 2, borderColor: 'rgba(255,255,255,0.3)', borderTopColor: '#fff' }} /> {t('analisando')}</>
            ) : (
              <>{resultado ? t('reanalisar') : t('analisar')}</>
            )}
          </button>
        </div>

        {!resultado && !loading && !erro && (
          <div style={{ marginTop: 20, background: 'var(--cinza-claro)', borderRadius: 12, padding: '16px 20px', display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            {[
              { icon: '📈', label: t('tipoAlta'), desc: t('descAlta') },
              { icon: '⚠️', label: t('tipoDesabCurto'), desc: t('descDesab') },
              { icon: '🚨', label: t('tipoSuper'), desc: t('descSuper') },
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
          <p style={{ marginTop: 20, fontFamily: 'Inter, sans-serif', fontSize: 18, fontWeight: 700, color: 'var(--texto)' }}>{t('carregandoTitulo')}</p>
          <p style={{ marginTop: 8, fontSize: 14, color: 'var(--texto-suave)' }}>{t('carregandoSub')}</p>
        </div>
      )}

      {/* ── Resultado ── */}
      {resultado && !loading && (
        <>
          {/* Resumo */}
          <div style={{ background: 'var(--verde-fundo)', border: '1px solid var(--borda)', borderRadius: 14, padding: '18px 22px', marginBottom: 20 }}>
            <div style={{ fontSize: 12, fontWeight: 800, color: 'var(--verde)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8 }}>{t('resumo')}</div>
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
                <div style={{ fontSize: 28, fontFamily: 'Inter, sans-serif', fontWeight: 700, color: cor }}>{contPorTipo(tipo)}</div>
                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--texto-suave)', marginTop: 4 }}>{t(label)}</div>
              </div>
            ))}
            <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 14, padding: '16px 18px' }}>
              <div style={{ fontSize: 24, marginBottom: 8 }}>🔔</div>
              <div style={{ fontSize: 28, fontFamily: 'Inter, sans-serif', fontWeight: 700, color: 'var(--texto)' }}>{resultado.alertas.length}</div>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--texto-suave)', marginTop: 4 }}>{t('totalAlertas')}</div>
            </div>
          </div>

          {/* Filtros */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--texto-suave)' }}>{t('filtrar')}</span>
            <button onClick={() => setFiltroTipo('todos')}
              style={{ background: filtroTipo === 'todos' ? 'var(--verde)' : 'var(--branco)', color: filtroTipo === 'todos' ? '#fff' : 'var(--texto-suave)', border: '1px solid var(--borda)', borderRadius: 8, padding: '5px 12px', fontFamily: 'Inter', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>
              {t('todos')}
            </button>
            {(['ALTA', 'MEDIA', 'BAIXA'] as const).map(sev => (
              <button key={sev} onClick={() => setFiltroSev(filtroSev === sev ? 'todas' : sev)}
                style={{ background: filtroSev === sev ? SEV_CONFIG[sev].bg : 'var(--branco)', color: filtroSev === sev ? SEV_CONFIG[sev].cor : 'var(--texto-suave)', border: `1px solid ${filtroSev === sev ? SEV_CONFIG[sev].borda : 'var(--borda)'}`, borderRadius: 8, padding: '5px 12px', fontFamily: 'Inter', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>
                {t('severidade', { s: t(SEV_CONFIG[sev].label) })}
              </button>
            ))}
            <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--texto-suave)', fontWeight: 600 }}>
              {t('nAlertas', { n: alertasFiltrados.length })}
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
                        <div style={{ fontSize: 12, color: tipo.cor, fontWeight: 700, marginTop: 2 }}>{t(tipo.label)} · <span style={{ background: tipo.bg, padding: '1px 8px', borderRadius: 6, border: `1px solid ${tipo.borda}` }}>{alerta.cultura}</span></div>
                      </div>
                    </div>
                    <span style={{ background: sev.bg, color: sev.cor, border: `1px solid ${sev.borda}`, fontSize: 11, fontWeight: 800, padding: '4px 12px', borderRadius: 8, whiteSpace: 'nowrap' }}>
                      ● {t(sev.label)}
                    </span>
                  </div>
                  <p style={{ fontSize: 13, color: 'var(--texto)', lineHeight: 1.6, marginBottom: 10 }}>{alerta.descricao}</p>
                  <div style={{ background: 'var(--cinza-claro)', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: 'var(--texto-suave)', display: 'flex', gap: 8 }}>
                    <span style={{ flexShrink: 0 }}>💡</span>
                    <span><strong style={{ color: 'var(--texto)' }}>{t('recomendacao')}</strong> {alerta.recomendacao}</span>
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
