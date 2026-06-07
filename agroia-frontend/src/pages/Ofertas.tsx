import { useEffect, useState, useMemo } from 'react'
import { NavLink } from 'react-router-dom'
import { supabase } from '../lib/supabaseClient'
import { useUrlState } from '../lib/useUrlState'
import { getCache, setCache, clearCache } from '../lib/sessionCache'

interface Oferta {
  id: number
  descricao: string
  quantidade: number | null
  unidade: string
  disponibilidade: string | null
  preco_pretendido: number | null
  status: string
  criado_em: string
  produtor_nome: string
  produtor_tipo: string
  municipio: string | null
  contato: string | null
  origem?: string | null
}

const CACHE_KEY = 'ofertas_produtores_v2'

const norm = (s: string) =>
  (s ?? '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')

export default function Ofertas() {
  const [ofertas, setOfertas] = useState<Oferta[]>([])
  const [loading, setLoading] = useState(true)
  const [busca, setBusca] = useUrlState('q')
  const [filMunicipio, setFilMunicipio] = useUrlState('municipio')
  const [filStatus, setFilStatus] = useUrlState('status', 'ATIVA')

  async function load(force = false) {
    setLoading(true)
    try {
      if (!force) {
        const cached = getCache<Oferta[]>(CACHE_KEY)
        if (cached) { setOfertas(cached); setLoading(false); return }
      }
      const { data } = await supabase
        .from('vw_ofertas_produtores')
        .select('*')
        .order('criado_em', { ascending: false })
        .limit(1000)
      if (data) { setOfertas(data as Oferta[]); setCache(CACHE_KEY, data) }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const municipios = useMemo(
    () => [...new Set(ofertas.map(o => o.municipio).filter(Boolean))].sort() as string[],
    [ofertas],
  )

  const filtered = useMemo(() => {
    let f = ofertas
    if (filStatus) f = f.filter(o => o.status === filStatus)
    if (filMunicipio) f = f.filter(o => o.municipio === filMunicipio)
    if (busca) {
      const q = norm(busca)
      f = f.filter(o =>
        norm(o.descricao).includes(q) ||
        norm(o.produtor_nome).includes(q) ||
        norm(o.disponibilidade ?? '').includes(q),
      )
    }
    return f
  }, [ofertas, busca, filMunicipio, filStatus])

  if (loading) return (
    <div className="page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 300 }}>
      <div style={{ textAlign: 'center' }}>
        <span className="spinner" style={{ width: 36, height: 36, borderWidth: 3 }} />
        <p style={{ marginTop: 16, color: 'var(--texto-suave)', fontWeight: 600 }}>Carregando ofertas...</p>
      </div>
    </div>
  )

  return (
    <div className="page">
      <div style={{ marginBottom: 12 }}>
        <h2 style={{ margin: '0 0 2px', fontFamily: 'Inter, sans-serif', color: 'var(--texto)' }}>Ofertas da agricultura familiar</h2>
        <p style={{ margin: 0, fontSize: 13, color: 'var(--texto-suave)' }}>
          Consulta da prefeitura: produtos cadastrados pelos produtores. Enquanto não há ofertas cadastradas, são exibidas referências de preço das CEASAs do Paraná. Filtre por produto, disponibilidade, município ou situação.
        </p>
      </div>
      <div style={{ background: 'var(--branco)', border: '1px solid var(--borda)', borderRadius: 16, padding: '16px 20px', marginBottom: 12 }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 200, display: 'flex', alignItems: 'center', gap: 8, background: 'var(--cinza-claro)', border: '1.5px solid var(--borda)', borderRadius: 10, padding: '8px 14px' }}>
            <span style={{ fontSize: 16 }}>🔍</span>
            <input
              style={{ flex: 1, border: 'none', background: 'transparent', fontFamily: 'Inter', fontSize: 14, color: 'var(--texto)', outline: 'none' }}
              placeholder="Buscar por produto, produtor ou disponibilidade..."
              value={busca}
              onChange={e => setBusca(e.target.value)}
            />
            {busca && <button onClick={() => setBusca('')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--cinza)', fontSize: 16 }}>×</button>}
          </div>
          <select className="filter-select" value={filMunicipio} onChange={e => setFilMunicipio(e.target.value)}>
            <option value="">Todos os municípios</option>
            {municipios.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
          <select className="filter-select" value={filStatus} onChange={e => setFilStatus(e.target.value)}>
            <option value="ATIVA">Ativas</option>
            <option value="ATENDIDA">Atendidas</option>
            <option value="INATIVA">Inativas</option>
            <option value="">Todas</option>
          </select>
          <button onClick={() => { clearCache(CACHE_KEY); load(true) }}
            style={{ background: 'var(--cinza-claro)', border: '1.5px solid var(--borda)', borderRadius: 10, padding: '9px 14px', fontFamily: 'Inter', fontSize: 13, fontWeight: 700, color: 'var(--texto)', cursor: 'pointer' }}>
            🔄 Atualizar
          </button>
          <span style={{ fontSize: 13, color: 'var(--texto-suave)', fontWeight: 600, whiteSpace: 'nowrap', marginLeft: 'auto' }}>
            {filtered.length.toLocaleString('pt-BR')} ofertas
          </span>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '60px 24px', color: 'var(--texto-suave)' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>🧺</div>
          <p style={{ fontWeight: 700, fontSize: 16 }}>Nenhuma oferta encontrada</p>
          <p style={{ fontSize: 14, marginTop: 6 }}>Os produtores ainda não cadastraram ofertas com esses filtros.</p>
        </div>
      ) : filtered.map(o => (
        <div key={o.id} className="item-card">
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
              {o.municipio && (
                <span style={{ background: 'var(--ceu-claro)', color: 'var(--ceu)', fontSize: 11, fontWeight: 700, padding: '3px 9px', borderRadius: 7, border: '1px solid #b3d9f5' }}>
                  📍 {o.municipio}
                </span>
              )}
              {o.origem && (
                <span style={{ fontSize: 10, color: 'var(--texto-suave)', background: 'var(--cinza-claro)', border: '1px solid var(--borda)', padding: '2px 7px', borderRadius: 6, fontWeight: 700, marginLeft: 'auto' }}>
                  {o.origem === 'CEASA'
                    ? '🏷️ referência CEASA'
                    : o.origem === 'PLANILHA'
                      ? '📄 planilha'
                      : '💬 chat'}
                </span>
              )}
              <span style={{ fontSize: 11, color: 'var(--texto-suave)', marginLeft: o.origem ? 0 : 'auto' }}>
                📅 {new Date(o.criado_em).toLocaleDateString('pt-BR')}
              </span>
            </div>
            <div className="item-title">{o.descricao}</div>
            <div className="item-meta" style={{ marginTop: 6 }}>
              {o.quantidade != null && <span>⚖️ {o.quantidade.toLocaleString('pt-BR')} {o.unidade}</span>}
              {o.disponibilidade && <span>🗓️ {o.disponibilidade}</span>}
            </div>
            <div className="item-links">
              <NavLink to={`/mercado?produto=${encodeURIComponent(o.descricao)}`}>💰 Preço de mercado</NavLink>
              <NavLink to={`/demanda?view=lista&q=${encodeURIComponent(o.descricao)}`}>📊 Demanda da prefeitura</NavLink>
            </div>
          </div>
          {o.preco_pretendido != null && (
            <div className="item-valor">
              R$ {o.preco_pretendido.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}/{o.unidade}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
