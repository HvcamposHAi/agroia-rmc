import { useEffect, useState } from 'react'
import { ChartColumn, List, CircleAlert } from 'lucide-react'
import { useUrlState } from '../lib/useUrlState'
import { fetchItensAgro, type ItemAgro } from '../lib/itensAgro'
import Dashboard from './Dashboard'
import Consultas from './Consultas'
import PageHeader from '../components/PageHeader'
import { defineMessages, useT, fmtNum } from '../i18n'

const MSG = defineMessages({
  pt: {
    carregando: 'Carregando demanda…',
    titulo: 'Demanda da prefeitura',
    subtitulo: 'O que a prefeitura de Curitiba compra da agricultura: valores, culturas, canais e evolução ao longo do tempo.',
    fonte: 'Fonte: Portal da Transparência de Curitiba (SMSAN/FAAC), 2019–2026 · somente itens agrícolas',
    resumo: 'Resumo',
    lista: 'Lista de itens',
    naBase: '{n} itens na base',
    semDados: 'Não foi possível carregar os dados agora. Tente novamente em instantes.',
  },
  en: {
    carregando: 'Loading demand…',
    titulo: 'City demand',
    subtitulo: 'What Curitiba city hall buys from agriculture: values, crops, channels and trends over time.',
    fonte: 'Source: Curitiba Transparency Portal (SMSAN/FAAC), 2019–2026 · agricultural items only',
    resumo: 'Summary',
    lista: 'Item list',
    naBase: '{n} items in the database',
    semDados: "Couldn't load the data right now. Please try again in a moment.",
  },
  es: {
    carregando: 'Cargando demanda…',
    titulo: 'Demanda de la alcaldía',
    subtitulo: 'Lo que la alcaldía de Curitiba compra de la agricultura: valores, cultivos, canales y evolución en el tiempo.',
    fonte: 'Fuente: Portal de Transparencia de Curitiba (SMSAN/FAAC), 2019–2026 · solo ítems agrícolas',
    resumo: 'Resumen',
    lista: 'Lista de ítems',
    naBase: '{n} ítems en la base',
    semDados: 'No fue posible cargar los datos ahora. Inténtelo de nuevo en unos instantes.',
  },
})

/**
 * "Demanda" unifica Dashboard (Resumo) e Consultas (Lista): um único fetch de
 * vw_itens_agro (via fetchItensAgro) alimenta as duas visões. Os filtros
 * (cultura/canal/ano…) vivem na URL e persistem ao alternar a visão
 * (?view=resumo|lista).
 */
export default function Demanda() {
  const t = useT(MSG)
  const [rows, setRows] = useState<ItemAgro[] | null>(null)
  const [view, setView] = useUrlState('view', 'resumo')

  useEffect(() => { fetchItensAgro().then(setRows) }, [])

  return (
    <div className="demanda-scroll">
      <div className="demanda-head">
        <PageHeader title={t('titulo')} subtitle={t('subtitulo')} source={t('fonte')} />
      </div>
      {!rows ? (
        <div className="page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 300 }}>
          <div style={{ textAlign: 'center' }} role="status">
            <span className="spinner" style={{ width: 36, height: 36, borderWidth: 3 }} />
            <p style={{ marginTop: 16, color: 'var(--texto-suave)', fontWeight: 600 }}>{t('carregando')}</p>
          </div>
        </div>
      ) : rows.length === 0 ? (
        // fetchItensAgro devolve [] quando a consulta falha: aviso em vez de painéis zerados
        <div className="page">
          <div className="aviso-box erro"><CircleAlert size={17} aria-hidden /> <span>{t('semDados')}</span></div>
        </div>
      ) : (
        <>
          <div className="demanda-toolbar">
            <div className="seg-control" role="tablist">
              <button role="tab" aria-selected={view === 'resumo'} className={`seg-btn${view === 'resumo' ? ' active' : ''}`} onClick={() => setView('resumo')}>
                <ChartColumn size={15} aria-hidden /> {t('resumo')}
              </button>
              <button role="tab" aria-selected={view === 'lista'} className={`seg-btn${view === 'lista' ? ' active' : ''}`} onClick={() => setView('lista')}>
                <List size={15} aria-hidden /> {t('lista')}
              </button>
            </div>
            <span style={{ fontSize: 12, color: 'var(--texto-suave)', fontWeight: 600 }}>
              {t('naBase', { n: fmtNum(rows.length) })}
            </span>
          </div>
          {view === 'lista'
            ? <Consultas dataset={rows} />
            : <Dashboard items={rows} />}
        </>
      )}
    </div>
  )
}
