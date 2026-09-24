import { useEffect, useState } from 'react'
import { useUrlState } from '../lib/useUrlState'
import { fetchItensAgro, type ItemAgro } from '../lib/itensAgro'
import Dashboard from './Dashboard'
import Consultas from './Consultas'
import { defineMessages, useT, fmtNum } from '../i18n'

const MSG = defineMessages({
  pt: { carregando: 'Carregando demanda...', resumo: '📊 Resumo', lista: '🔍 Lista', naBase: '{n} itens na base' },
  en: { carregando: 'Loading demand...', resumo: '📊 Summary', lista: '🔍 List', naBase: '{n} items in the database' },
  es: { carregando: 'Cargando demanda...', resumo: '📊 Resumen', lista: '🔍 Lista', naBase: '{n} ítems en la base' },
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

  if (!rows) return (
    <div className="page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 300 }}>
      <div style={{ textAlign: 'center' }}>
        <span className="spinner" style={{ width: 36, height: 36, borderWidth: 3 }} />
        <p style={{ marginTop: 16, color: 'var(--texto-suave)', fontWeight: 600 }}>{t('carregando')}</p>
      </div>
    </div>
  )

  return (
    <>
      <div className="demanda-toolbar">
        <div className="seg-control">
          <button className={`seg-btn${view === 'resumo' ? ' active' : ''}`} onClick={() => setView('resumo')}>
            {t('resumo')}
          </button>
          <button className={`seg-btn${view === 'lista' ? ' active' : ''}`} onClick={() => setView('lista')}>
            {t('lista')}
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
  )
}
