import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabaseClient'
import { useUrlState } from '../lib/useUrlState'
import { getCache, setCache } from '../lib/sessionCache'
import Dashboard from './Dashboard'
import Consultas from './Consultas'

// Chave compartilhada com a Home (KPIs) para evitar fetch duplicado.
export const DEMANDA_CACHE_KEY = 'demanda_itens_agro_v1'

/**
 * "Demanda" unifica Dashboard (Resumo) e Consultas (Lista): um único fetch de
 * vw_itens_agro alimenta as duas visões. Os filtros (cultura/canal/ano…) vivem na
 * URL e persistem ao alternar a visão (?view=resumo|lista).
 */
export default function Demanda() {
  const [rows, setRows] = useState<any[] | null>(null)
  const [view, setView] = useUrlState('view', 'resumo')

  useEffect(() => {
    async function load() {
      const cached = getCache<any[]>(DEMANDA_CACHE_KEY)
      if (cached) { setRows(cached); return }
      const { data } = await supabase
        .from('vw_itens_agro')
        .select('*')
        .order('dt_abertura', { ascending: false })
        .limit(1000)
      const arr = data ?? []
      setRows(arr)
      setCache(DEMANDA_CACHE_KEY, arr)
    }
    load()
  }, [])

  if (!rows) return (
    <div className="page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 300 }}>
      <div style={{ textAlign: 'center' }}>
        <span className="spinner" style={{ width: 36, height: 36, borderWidth: 3 }} />
        <p style={{ marginTop: 16, color: 'var(--texto-suave)', fontWeight: 600 }}>Carregando demanda...</p>
      </div>
    </div>
  )

  return (
    <>
      <div className="demanda-toolbar">
        <div className="seg-control">
          <button className={`seg-btn${view === 'resumo' ? ' active' : ''}`} onClick={() => setView('resumo')}>
            📊 Resumo
          </button>
          <button className={`seg-btn${view === 'lista' ? ' active' : ''}`} onClick={() => setView('lista')}>
            🔍 Lista
          </button>
        </div>
        <span style={{ fontSize: 12, color: 'var(--texto-suave)', fontWeight: 600 }}>
          {rows.length.toLocaleString('pt-BR')} itens na base
        </span>
      </div>
      {view === 'lista'
        ? <Consultas dataset={rows} />
        : <Dashboard items={rows} />}
    </>
  )
}
