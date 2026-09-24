import { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { fetchItensAgro, kpisFromRows, type KpisAgro } from '../lib/itensAgro'

import { defineMessages, useT, fmtNum } from '../i18n'

type Papel = 'gestor' | 'produtor'

const MSG = defineMessages({
  pt: {
    chipTomate: 'Preço do tomate',
    chipDemanda: 'Demanda 2024',
    chipAlface: 'Quem vende alface?',
    chipAlertas: 'Alertas de risco',
    chipAuditar: 'Auditar dados',
    chipCadastrar: 'Cadastrar minha produção',
    chipPrecos: 'Ver preços de mercado',
    chipOfertas: 'Ver ofertas cadastradas',
    grpConsultar: 'Consultar & Analisar',
    grpAgir: 'Agir',
    grpOperar: 'Operar & Monitorar',
    svcAssistente: 'Assistente',
    svcAssistenteDesc: 'Pergunte em linguagem natural sobre licitações agrícolas.',
    svcDemanda: 'Demanda',
    svcDemandaDesc: 'Resumo (gráficos) e lista de itens das compras públicas.',
    svcMercado: 'Preços de Mercado',
    svcMercadoDesc: 'Atacado CEASA/PROHORT × o que a prefeitura paga.',
    svcDocumentos: 'Documentos',
    svcDocumentosDesc: 'Editais, termos de referência e atas.',
    svcProdutor: 'Sou Produtor',
    svcProdutorDesc: 'Cadastre suas ofertas conversando com a IA.',
    svcOfertas: 'Ofertas de Produtores',
    svcOfertasDesc: 'O que a agricultura familiar tem disponível.',
    svcAlertas: 'Alertas Inteligentes',
    svcAlertasDesc: 'Riscos de preço, desabastecimento e superfaturamento.',
    svcAuditoria: 'Auditoria',
    svcAuditoriaDesc: 'Qualidade e consistência dos dados.',
    svcColeta: 'Atualização de Dados',
    svcColetaDesc: 'Coleta automática e agendamento.',
    gestor: '🏛️ Gestor',
    produtor: '🧑‍🌾 Produtor',
    titulo: '🌾 O que você precisa hoje?',
    subGestor: 'Pergunte em linguagem natural ou use um atalho. Dica: aperte ⌘K / Ctrl+K para buscar qualquer coisa.',
    subProdutor: 'Cadastre o que você tem para vender e veja os preços de mercado. Dica: ⌘K / Ctrl+K busca qualquer coisa.',
    placeholder: 'Pergunte ou busque… ex.: a prefeitura paga acima do atacado no tomate?',
    perguntar: 'Perguntar →',
    kpiValor: 'Valor em licitações (agro)',
    kpiValorSub: 'em {n} licitações · 2019–2026',
    carregando: 'carregando…',
    kpiItens: 'Itens agrícolas',
    kpiItensSub: 'registros classificados',
    kpiCulturas: 'Culturas',
    kpiCulturasSub: 'tipos distintos',
    kpiLicitacoes: 'Nº de licitações',
    kpiLicitacoesSub: 'processos agro',
  },
  en: {
    chipTomate: 'Tomato price',
    chipDemanda: 'Demand 2024',
    chipAlface: 'Who sells lettuce?',
    chipAlertas: 'Risk alerts',
    chipAuditar: 'Audit data',
    chipCadastrar: 'Register my produce',
    chipPrecos: 'See market prices',
    chipOfertas: 'See registered offers',
    grpConsultar: 'Explore & Analyze',
    grpAgir: 'Act',
    grpOperar: 'Operate & Monitor',
    svcAssistente: 'Assistant',
    svcAssistenteDesc: 'Ask in natural language about agricultural biddings.',
    svcDemanda: 'Demand',
    svcDemandaDesc: 'Summary (charts) and item list of public purchases.',
    svcMercado: 'Market Prices',
    svcMercadoDesc: 'CEASA/PROHORT wholesale × what the city pays.',
    svcDocumentos: 'Documents',
    svcDocumentosDesc: 'Calls for bids, terms of reference and minutes.',
    svcProdutor: "I'm a Farmer",
    svcProdutorDesc: 'Register your offers by chatting with the AI.',
    svcOfertas: 'Farmer Offers',
    svcOfertasDesc: 'What family farming has available.',
    svcAlertas: 'Smart Alerts',
    svcAlertasDesc: 'Price, shortage and overpricing risks.',
    svcAuditoria: 'Audit',
    svcAuditoriaDesc: 'Data quality and consistency.',
    svcColeta: 'Data Update',
    svcColetaDesc: 'Automatic collection and scheduling.',
    gestor: '🏛️ Manager',
    produtor: '🧑‍🌾 Farmer',
    titulo: '🌾 What do you need today?',
    subGestor: 'Ask in natural language or use a shortcut. Tip: press ⌘K / Ctrl+K to search anything.',
    subProdutor: 'Register what you have to sell and see market prices. Tip: ⌘K / Ctrl+K searches anything.',
    placeholder: 'Ask or search… e.g.: does the city pay above wholesale for tomatoes?',
    perguntar: 'Ask →',
    kpiValor: 'Value in biddings (agro)',
    kpiValorSub: 'in {n} biddings · 2019–2026',
    carregando: 'loading…',
    kpiItens: 'Agricultural items',
    kpiItensSub: 'classified records',
    kpiCulturas: 'Crops',
    kpiCulturasSub: 'distinct types',
    kpiLicitacoes: 'No. of biddings',
    kpiLicitacoesSub: 'agro processes',
  },
  es: {
    chipTomate: 'Precio del tomate',
    chipDemanda: 'Demanda 2024',
    chipAlface: '¿Quién vende lechuga?',
    chipAlertas: 'Alertas de riesgo',
    chipAuditar: 'Auditar datos',
    chipCadastrar: 'Registrar mi producción',
    chipPrecos: 'Ver precios de mercado',
    chipOfertas: 'Ver ofertas registradas',
    grpConsultar: 'Consultar y Analizar',
    grpAgir: 'Actuar',
    grpOperar: 'Operar y Monitorear',
    svcAssistente: 'Asistente',
    svcAssistenteDesc: 'Pregunte en lenguaje natural sobre licitaciones agrícolas.',
    svcDemanda: 'Demanda',
    svcDemandaDesc: 'Resumen (gráficos) y lista de ítems de las compras públicas.',
    svcMercado: 'Precios de Mercado',
    svcMercadoDesc: 'Mayorista CEASA/PROHORT × lo que paga la alcaldía.',
    svcDocumentos: 'Documentos',
    svcDocumentosDesc: 'Pliegos, términos de referencia y actas.',
    svcProdutor: 'Soy Productor',
    svcProdutorDesc: 'Registre sus ofertas conversando con la IA.',
    svcOfertas: 'Ofertas de Productores',
    svcOfertasDesc: 'Lo que la agricultura familiar tiene disponible.',
    svcAlertas: 'Alertas Inteligentes',
    svcAlertasDesc: 'Riesgos de precio, desabastecimiento y sobreprecio.',
    svcAuditoria: 'Auditoría',
    svcAuditoriaDesc: 'Calidad y consistencia de los datos.',
    svcColeta: 'Actualización de Datos',
    svcColetaDesc: 'Recolección automática y programación.',
    gestor: '🏛️ Gestor',
    produtor: '🧑‍🌾 Productor',
    titulo: '🌾 ¿Qué necesita hoy?',
    subGestor: 'Pregunte en lenguaje natural o use un atajo. Consejo: pulse ⌘K / Ctrl+K para buscar cualquier cosa.',
    subProdutor: 'Registre lo que tiene para vender y vea los precios de mercado. Consejo: ⌘K / Ctrl+K busca cualquier cosa.',
    placeholder: 'Pregunte o busque… ej.: ¿la alcaldía paga más que el mayorista por el tomate?',
    perguntar: 'Preguntar →',
    kpiValor: 'Valor en licitaciones (agro)',
    kpiValorSub: 'en {n} licitaciones · 2019–2026',
    carregando: 'cargando…',
    kpiItens: 'Ítems agrícolas',
    kpiItensSub: 'registros clasificados',
    kpiCulturas: 'Cultivos',
    kpiCulturasSub: 'tipos distintos',
    kpiLicitacoes: 'N.º de licitaciones',
    kpiLicitacoesSub: 'procesos agro',
  },
})

type MsgKey = keyof typeof MSG.pt

interface Chip { icon: string; label: MsgKey; to: string }
interface Servico { to: string; icon: string; title: MsgKey; desc: MsgKey; destaque?: boolean }
interface Grupo { titulo: MsgKey; accent: 'verde' | 'ceu' | 'teal'; servicos: Servico[] }

const CHIPS: Record<Papel, Chip[]> = {
  gestor: [
    { icon: '💰', label: 'chipTomate', to: '/mercado?produto=tomate' },
    { icon: '📊', label: 'chipDemanda', to: '/demanda?ano=2024&view=resumo' },
    { icon: '🧺', label: 'chipAlface', to: '/ofertas?q=alface' },
    { icon: '🚨', label: 'chipAlertas', to: '/alertas' },
    { icon: '🔎', label: 'chipAuditar', to: '/auditoria' },
  ],
  produtor: [
    { icon: '🧑‍🌾', label: 'chipCadastrar', to: '/produtor' },
    { icon: '💰', label: 'chipPrecos', to: '/mercado' },
    { icon: '🧺', label: 'chipOfertas', to: '/ofertas' },
  ],
}

// Serviços agrupados por jornada (Consultar & Analisar · Agir · Operar & Monitorar).
const GRUPOS: Grupo[] = [
  {
    titulo: 'grpConsultar',
    accent: 'verde',
    servicos: [
      { to: '/assistente', icon: '💬', title: 'svcAssistente', desc: 'svcAssistenteDesc' },
      { to: '/demanda', icon: '📊', title: 'svcDemanda', desc: 'svcDemandaDesc' },
      { to: '/mercado', icon: '💰', title: 'svcMercado', desc: 'svcMercadoDesc' },
      { to: '/documentos', icon: '📄', title: 'svcDocumentos', desc: 'svcDocumentosDesc' },
    ],
  },
  {
    titulo: 'grpAgir',
    accent: 'teal',
    servicos: [
      { to: '/produtor', icon: '🧑‍🌾', title: 'svcProdutor', desc: 'svcProdutorDesc', destaque: true },
      { to: '/ofertas', icon: '🧺', title: 'svcOfertas', desc: 'svcOfertasDesc' },
    ],
  },
  {
    titulo: 'grpOperar',
    accent: 'ceu',
    servicos: [
      { to: '/alertas', icon: '🚨', title: 'svcAlertas', desc: 'svcAlertasDesc' },
      { to: '/auditoria', icon: '🔎', title: 'svcAuditoria', desc: 'svcAuditoriaDesc' },
      { to: '/coleta', icon: '🔄', title: 'svcColeta', desc: 'svcColetaDesc' },
    ],
  },
]

const fmtMoeda = (v: number) =>
  v >= 1_000_000 ? `R$ ${(v / 1_000_000).toFixed(1)}M`
  : v >= 1_000 ? `R$ ${(v / 1_000).toFixed(0)}K`
  : `R$ ${v.toFixed(0)}`

export default function Home() {
  const t = useT(MSG)
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
          <button className={papel === 'gestor' ? 'active' : ''} onClick={() => setPapel('gestor')}>{t('gestor')}</button>
          <button className={papel === 'produtor' ? 'active' : ''} onClick={() => setPapel('produtor')}>{t('produtor')}</button>
        </div>

        <h1>{t('titulo')}</h1>
        <p className="home-sub">
          {papel === 'gestor'
            ? t('subGestor')
            : t('subProdutor')}
        </p>

        <div className="home-ask">
          <span style={{ fontSize: 18 }}>🔎</span>
          <input
            placeholder={t('placeholder')}
            value={pergunta}
            onChange={e => setPergunta(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') perguntar() }}
          />
          <button onClick={perguntar} disabled={!pergunta.trim()}>{t('perguntar')}</button>
        </div>

        <div className="home-chips">
          {CHIPS[papel].map(c => (
            <NavLink key={c.to + c.label} to={c.to} className="chip">
              <span>{c.icon}</span> {t(c.label)}
            </NavLink>
          ))}
        </div>
      </div>

      {/* KPIs ao vivo (bento: 2 herói + 2 de apoio), clicáveis → Demanda */}
      <div className="home-kpis">
        <NavLink to="/demanda?view=resumo" className="metric-card verde heroi">
          <span className="metric-icon">💰</span>
          <div className="metric-label">{t('kpiValor')}</div>
          <div className="metric-value">{kpis ? fmtMoeda(kpis.valor) : '—'}</div>
          <div className="metric-sub">{kpis ? t('kpiValorSub', { n: fmtNum(kpis.licitacoes) }) : t('carregando')}</div>
        </NavLink>
        <NavLink to="/demanda?view=lista" className="metric-card amarelo heroi">
          <span className="metric-icon">📦</span>
          <div className="metric-label">{t('kpiItens')}</div>
          <div className="metric-value">{kpis ? fmtNum(kpis.itens) : '—'}</div>
          <div className="metric-sub">{t('kpiItensSub')}</div>
        </NavLink>
        <NavLink to="/demanda?view=resumo" className="metric-card ceu">
          <span className="metric-icon">🌱</span>
          <div className="metric-label">{t('kpiCulturas')}</div>
          <div className="metric-value">{kpis ? fmtNum(kpis.culturas) : '—'}</div>
          <div className="metric-sub">{t('kpiCulturasSub')}</div>
        </NavLink>
        <NavLink to="/demanda?view=lista" className="metric-card terra">
          <span className="metric-icon">📋</span>
          <div className="metric-label">{t('kpiLicitacoes')}</div>
          <div className="metric-value">{kpis ? fmtNum(kpis.licitacoes) : '—'}</div>
          <div className="metric-sub">{t('kpiLicitacoesSub')}</div>
        </NavLink>
      </div>

      {GRUPOS.map(g => (
        <section key={g.titulo} className="hub-group">
          <div className="hub-section-title">{t(g.titulo)}</div>
          <div className="hub-grid">
            {g.servicos.map(s => (
              <NavLink key={s.to} to={s.to} className={`hub-card accent-${g.accent}${s.destaque ? ' destaque' : ''}`}>
                <div className="hub-icon">{s.icon}</div>
                <h3>{t(s.title)}</h3>
                <p>{t(s.desc)}</p>
              </NavLink>
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}
