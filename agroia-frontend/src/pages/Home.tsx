import { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { fetchItensAgro, kpisFromRows, type KpisAgro } from '../lib/itensAgro'

type Papel = 'gestor' | 'produtor'

interface Chip { icon: string; label: string; to: string }
interface Servico { to: string; icon: string; title: string; desc: string; destaque?: boolean }
interface Grupo { titulo: string; accent: 'verde' | 'ceu' | 'teal'; servicos: Servico[] }

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

// Serviços agrupados por jornada (Consultar & Analisar · Agir · Operar & Monitorar).
const GRUPOS: Grupo[] = [
  {
    titulo: 'Consultar & Analisar',
    accent: 'verde',
    servicos: [
      { to: '/assistente', icon: '💬', title: 'Assistente', desc: 'Pergunte em linguagem natural sobre licitações agrícolas.' },
      { to: '/demanda', icon: '📊', title: 'Demanda', desc: 'Resumo (gráficos) e lista de itens das compras públicas.' },
      { to: '/mercado', icon: '💰', title: 'Preços de Mercado', desc: 'Atacado CEASA/PROHORT × o que a prefeitura paga.' },
      { to: '/documentos', icon: '📄', title: 'Documentos', desc: 'Editais, termos de referência e atas.' },
    ],
  },
  {
    titulo: 'Agir',
    accent: 'teal',
    servicos: [
      { to: '/produtor', icon: '🧑‍🌾', title: 'Sou Produtor', desc: 'Cadastre suas ofertas conversando com a IA.', destaque: true },
      { to: '/ofertas', icon: '🧺', title: 'Ofertas de Produtores', desc: 'O que a agricultura familiar tem disponível.' },
    ],
  },
  {
    titulo: 'Operar & Monitorar',
    accent: 'ceu',
    servicos: [
      { to: '/alertas', icon: '🚨', title: 'Alertas Inteligentes', desc: 'Riscos de preço, desabastecimento e superfaturamento.' },
      { to: '/auditoria', icon: '🔎', title: 'Auditoria', desc: 'Qualidade e consistência dos dados.' },
      { to: '/coleta', icon: '🔄', title: 'Atualização de Dados', desc: 'Coleta automática e agendamento.' },
    ],
  },
]

const fmtMoeda = (v: number) =>
  v >= 1_000_000 ? `R$ ${(v / 1_000_000).toFixed(1)}M`
  : v >= 1_000 ? `R$ ${(v / 1_000).toFixed(0)}K`
  : `R$ ${v.toFixed(0)}`

const fmtNum = (v: number) => v.toLocaleString('pt-BR')

export default function Home() {
  const navigate = useNavigate()
  const [papel, setPapel] = useState<Papel>(() => (localStorage.getItem('agroia_papel') as Papel) || 'gestor')
  const [pergunta, setPergunta] = useState('')
  const [kpis, setKpis] = useState<KpisAgro | null>(null)

  useEffect(() => { localStorage.setItem('agroia_papel', papel) }, [papel])

  // KPIs derivam da MESMA fonte (fetchItensAgro) usada por Demanda/Dashboard/Consultas.
  useEffect(() => {
    fetchItensAgro().then(rows => setKpis(kpisFromRows(rows)))
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

      {/* KPIs ao vivo (bento: 2 herói + 2 de apoio), clicáveis → Demanda */}
      <div className="home-kpis">
        <NavLink to="/demanda?view=resumo" className="metric-card verde heroi">
          <span className="metric-icon">💰</span>
          <div className="metric-label">Valor em licitações (agro)</div>
          <div className="metric-value">{kpis ? fmtMoeda(kpis.valor) : '—'}</div>
          <div className="metric-sub">{kpis ? `em ${fmtNum(kpis.licitacoes)} licitações · 2019–2026` : 'carregando…'}</div>
        </NavLink>
        <NavLink to="/demanda?view=lista" className="metric-card amarelo heroi">
          <span className="metric-icon">📦</span>
          <div className="metric-label">Itens agrícolas</div>
          <div className="metric-value">{kpis ? fmtNum(kpis.itens) : '—'}</div>
          <div className="metric-sub">registros classificados</div>
        </NavLink>
        <NavLink to="/demanda?view=resumo" className="metric-card ceu">
          <span className="metric-icon">🌱</span>
          <div className="metric-label">Culturas</div>
          <div className="metric-value">{kpis ? fmtNum(kpis.culturas) : '—'}</div>
          <div className="metric-sub">tipos distintos</div>
        </NavLink>
        <NavLink to="/demanda?view=lista" className="metric-card terra">
          <span className="metric-icon">📋</span>
          <div className="metric-label">Nº de licitações</div>
          <div className="metric-value">{kpis ? fmtNum(kpis.licitacoes) : '—'}</div>
          <div className="metric-sub">processos agro</div>
        </NavLink>
      </div>

      {GRUPOS.map(g => (
        <section key={g.titulo} className="hub-group">
          <div className="hub-section-title">{g.titulo}</div>
          <div className="hub-grid">
            {g.servicos.map(s => (
              <NavLink key={s.to} to={s.to} className={`hub-card accent-${g.accent}${s.destaque ? ' destaque' : ''}`}>
                <div className="hub-icon">{s.icon}</div>
                <h3>{s.title}</h3>
                <p>{s.desc}</p>
              </NavLink>
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}
