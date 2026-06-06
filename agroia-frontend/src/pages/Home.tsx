import { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabaseClient'
import { getCache, setCache } from '../lib/sessionCache'
import { DEMANDA_CACHE_KEY } from './Demanda'

type Papel = 'gestor' | 'produtor'

interface Chip { icon: string; label: string; to: string }
interface Servico { to: string; icon: string; title: string; desc: string; destaque?: boolean }

const CHIPS: Record<Papel, Chip[]> = {
  gestor: [
    { icon: '💰', label: 'Preço do tomate', to: '/mercado?produto=tomate' },
    { icon: '📊', label: 'Demanda 2024', to: '/demanda?ano=2024&view=resumo' },
    { icon: '🧺', label: 'Quem vende alface?', to: '/ofertas?q=alface' },
    { icon: '🚨', label: 'Alertas de risco', to: '/alertas' },
    { icon: '🔎', label: 'Auditar dados', to: '/auditoria' },
  ],
  produtor: [
    { icon: '🧑‍🌾', label: 'Cadastrar minha produção', to: '/produtor' },
    { icon: '💰', label: 'Ver preços de mercado', to: '/mercado' },
    { icon: '🧺', label: 'Ver ofertas cadastradas', to: '/ofertas' },
  ],
}

const CATALOGO: Servico[] = [
  { to: '/assistente', icon: '💬', title: 'Assistente', desc: 'Pergunte em linguagem natural sobre licitações agrícolas.' },
  { to: '/demanda', icon: '📊', title: 'Demanda', desc: 'Resumo (gráficos) e lista de itens das compras públicas.' },
  { to: '/mercado', icon: '💰', title: 'Preços de Mercado', desc: 'Atacado CEASA/PROHORT × o que a prefeitura paga.' },
  { to: '/ofertas', icon: '🧺', title: 'Ofertas de Produtores', desc: 'O que a agricultura familiar tem disponível.' },
  { to: '/produtor', icon: '🧑‍🌾', title: 'Sou Produtor', desc: 'Cadastre suas ofertas conversando com a IA.', destaque: true },
  { to: '/documentos', icon: '📄', title: 'Documentos', desc: 'Editais, termos de referência e atas.' },
  { to: '/alertas', icon: '🚨', title: 'Alertas Inteligentes', desc: 'Riscos de preço, desabastecimento e superfaturamento.' },
  { to: '/auditoria', icon: '🔎', title: 'Auditoria', desc: 'Qualidade e consistência dos dados.' },
  { to: '/coleta', icon: '🔄', title: 'Atualização de Dados', desc: 'Coleta automática e agendamento.' },
]

const fmtMoeda = (v: number) =>
  v >= 1_000_000 ? `R$ ${(v / 1_000_000).toFixed(1)}M`
  : v >= 1_000 ? `R$ ${(v / 1_000).toFixed(0)}K`
  : `R$ ${v.toFixed(0)}`

export default function Home() {
  const navigate = useNavigate()
  const [papel, setPapel] = useState<Papel>(() => (localStorage.getItem('agroia_papel') as Papel) || 'gestor')
  const [pergunta, setPergunta] = useState('')
  const [kpis, setKpis] = useState<{ valor: number; itens: number; culturas: number } | null>(null)

  useEffect(() => { localStorage.setItem('agroia_papel', papel) }, [papel])

  // KPIs reaproveitam o MESMO cache da Demanda (sem fetch extra quando já visitada).
  useEffect(() => {
    async function load() {
      let rows = getCache<any[]>(DEMANDA_CACHE_KEY)
      if (!rows) {
        const { data } = await supabase
          .from('vw_itens_agro')
          .select('*')
          .order('dt_abertura', { ascending: false })
          .limit(1000)
        rows = data ?? []
        setCache(DEMANDA_CACHE_KEY, rows)
      }
      const valor = rows.reduce((s, r) => s + (r.valor_total ?? 0), 0)
      const culturas = new Set(rows.map(r => r.cultura).filter(Boolean)).size
      setKpis({ valor, itens: rows.length, culturas })
    }
    load()
  }, [])

  const perguntar = () => {
    const q = pergunta.trim()
    if (!q) return
    navigate('/assistente?q=' + encodeURIComponent(q))
  }

  return (
    <div className="page">
      <div className="home-hero">
        <div className="role-toggle">
          <button className={papel === 'gestor' ? 'active' : ''} onClick={() => setPapel('gestor')}>🏛️ Gestor</button>
          <button className={papel === 'produtor' ? 'active' : ''} onClick={() => setPapel('produtor')}>🧑‍🌾 Produtor</button>
        </div>

        <h1>🌾 O que você precisa hoje?</h1>
        <p className="home-sub">
          {papel === 'gestor'
            ? 'Pergunte em linguagem natural ou use um atalho. Dica: aperte ⌘K / Ctrl+K para buscar qualquer coisa.'
            : 'Cadastre o que você tem para vender e veja os preços de mercado. Dica: ⌘K / Ctrl+K busca qualquer coisa.'}
        </p>

        <div className="home-ask">
          <span style={{ fontSize: 18 }}>🔎</span>
          <input
            placeholder="Pergunte ou busque… ex.: a prefeitura paga acima do atacado no tomate?"
            value={pergunta}
            onChange={e => setPergunta(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') perguntar() }}
          />
          <button onClick={perguntar} disabled={!pergunta.trim()}>Perguntar →</button>
        </div>

        <div className="home-chips">
          {CHIPS[papel].map(c => (
            <NavLink key={c.to + c.label} to={c.to} className="chip">
              <span>{c.icon}</span> {c.label}
            </NavLink>
          ))}
        </div>
      </div>

      {/* KPIs ao vivo (clicáveis → Demanda) */}
      <div className="home-kpis">
        <NavLink to="/demanda?view=resumo" className="metric-card verde">
          <div className="metric-label">VALOR EM LICITAÇÕES (AGRO)</div>
          <div className="metric-value">{kpis ? fmtMoeda(kpis.valor) : '—'}</div>
        </NavLink>
        <NavLink to="/demanda?view=lista" className="metric-card amarelo">
          <div className="metric-label">ITENS AGRÍCOLAS</div>
          <div className="metric-value">{kpis ? kpis.itens.toLocaleString('pt-BR') : '—'}</div>
        </NavLink>
        <NavLink to="/demanda?view=resumo" className="metric-card ceu">
          <div className="metric-label">CULTURAS</div>
          <div className="metric-value">{kpis ? kpis.culturas.toLocaleString('pt-BR') : '—'}</div>
        </NavLink>
      </div>

      <div className="hub-section-title">Todos os serviços</div>
      <div className="hub-grid">
        {CATALOGO.map(s => (
          <NavLink key={s.to} to={s.to} className={`hub-card${s.destaque ? ' destaque' : ''}`}>
            <div className="hub-icon">{s.icon}</div>
            <h3>{s.title}</h3>
            <p>{s.desc}</p>
          </NavLink>
        ))}
      </div>
    </div>
  )
}
