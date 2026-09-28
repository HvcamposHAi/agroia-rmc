import { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import type { LucideIcon } from 'lucide-react'
import {
  Landmark, Tractor, Search, ArrowRight, Sparkles, Coins, Package, Sprout, ClipboardList,
  MessageSquare, ChartColumn, TrendingUp, FileText, BellRing, ShieldCheck, RefreshCw,
  Database, Bot, Target, Scale, CircleHelp,
} from 'lucide-react'
import { fetchItensAgro, kpisFromRows, type KpisAgro } from '../lib/itensAgro'
import { defineMessages, useT, fmtNum } from '../i18n'

type Papel = 'gestor' | 'produtor'

const MSG = defineMessages({
  pt: {
    eyebrow: 'Plataforma de dados públicos · Região Metropolitana de Curitiba',
    titulo: 'Agricultura familiar e compras públicas de alimentos, lado a lado',
    subGestor: 'Veja o que a prefeitura compra, quanto paga e como isso se compara ao atacado, e encontre quem produz na região.',
    subProdutor: 'Descubra o que a prefeitura compra, acompanhe os preços de atacado e cadastre sua produção para ser encontrado.',
    gestor: 'Prefeitura',
    produtor: 'Cooperativas e produtores',
    papelAria: 'Escolha seu perfil',
    placeholder: 'Pergunte em linguagem natural… ex.: a prefeitura paga acima do atacado no tomate?',
    perguntar: 'Perguntar',
    notaIA: 'Respostas geradas por IA a partir de dados públicos. Confira sempre as fontes indicadas.',
    chipTomate: 'A prefeitura paga acima do atacado no tomate?',
    chipDemanda: 'Demanda de 2025',
    chipAlertas: 'Alertas de risco',
    chipCadastrar: 'Cadastrar minha produção',
    chipPrecos: 'Preços de atacado hoje',
    chipComprou: 'O que a prefeitura mais compra?',
    perguntaComprou: 'Quais hortaliças a prefeitura mais comprou nos últimos dois anos?',
    kpiValor: 'Valor em licitações agrícolas',
    kpiValorSub: 'em {n} licitações · 2019–2026',
    carregando: 'carregando…',
    indisponivel: 'dados indisponíveis no momento',
    kpiItens: 'Itens agrícolas',
    kpiItensSub: 'registros classificados',
    kpiCulturas: 'Culturas',
    kpiCulturasSub: 'tipos distintos',
    kpiLicitacoes: 'Licitações',
    kpiLicitacoesSub: 'processos no escopo agrícola',
    kpiFonte: 'Fonte: Portal da Transparência de Curitiba (SMSAN/FAAC) · somente itens da agricultura',
    grpAnalisar: 'Analisar a demanda',
    grpGestao: 'Gestão e qualidade',
    grpVender: 'Vender para a prefeitura',
    grpDuvidas: 'Tirar dúvidas',
    svcAssistente: 'Assistente',
    svcAssistenteDesc: 'Pergunte em linguagem natural sobre compras, preços e ofertas.',
    svcDemanda: 'Demanda',
    svcDemandaDesc: 'O que a prefeitura compra: gráficos e lista de itens.',
    svcDemandaDescProd: 'Veja quais alimentos a prefeitura compra, quanto e quando.',
    svcMercado: 'Mercado',
    svcMercadoDesc: 'Preços de atacado (CEASA/PROHORT) × preço pago nas licitações.',
    svcDocumentos: 'Documentos',
    svcDocumentosDesc: 'Editais, termos de referência e atas das licitações.',
    svcProdutor: 'Produtores',
    svcProdutorDesc: 'Ofertas da agricultura familiar cadastradas por conversa ou planilha.',
    svcProdutorDescProd: 'Cadastre o que você produz conversando com o assistente ou enviando uma planilha.',
    svcAlertas: 'Alertas de risco',
    svcAlertasDesc: 'Indícios de alta de preço, desabastecimento e sobrepreço.',
    svcAuditoria: 'Qualidade dos dados',
    svcAuditoriaDesc: 'Cobertura de documentos, empenhos e consistência da base.',
    svcColeta: 'Atualização de dados',
    svcColetaDesc: 'Coleta automática diária do Portal da Transparência.',
    sobreTitulo: 'Sobre os dados e a IA',
    fontesTitulo: 'De onde vêm os dados',
    fonte1: 'Licitações e itens: Portal da Transparência de Curitiba (SMSAN/FAAC), 2019–2026.',
    fonte2: 'Preços de atacado: CEASA-PR (por variedade) e PROHORT/CONAB.',
    fonte3: 'Ofertas: cadastradas pelos próprios produtores e cooperativas.',
    iaTitulo: 'Como a IA é usada',
    ia1: 'Um assistente de IA consulta a base e redige as respostas automaticamente.',
    ia2: 'As respostas podem conter erros: confira nos documentos e dados de origem.',
    ia3: 'A IA não toma decisões nem substitui orientação oficial.',
    escopoTitulo: 'Escopo e atualização',
    escopo1: 'Considera apenas compras da agricultura; as demais licitações ficam de fora.',
    escopo2: 'Os dados são atualizados automaticamente todos os dias.',
    escopo3: 'Cada página indica a fonte dos números que exibe.',
    rodape1: 'AgroIA-RMC',
    rodape2: 'Pesquisa de mestrado PPGCA/UEPG',
    rodape3: 'Dados públicos · uso institucional e acadêmico',
  },
  en: {
    eyebrow: 'Public data platform · Curitiba Metropolitan Region',
    titulo: 'Family farming and public food procurement, side by side',
    subGestor: 'See what the city buys, how much it pays and how that compares to wholesale, and find who produces in the region.',
    subProdutor: 'Find out what the city buys, follow wholesale prices and register your produce so buyers can find you.',
    gestor: 'City hall',
    produtor: 'Cooperatives and farmers',
    papelAria: 'Choose your profile',
    placeholder: 'Ask in plain language… e.g.: does the city pay above wholesale for tomatoes?',
    perguntar: 'Ask',
    notaIA: 'Answers are AI-generated from public data. Always check the sources provided.',
    chipTomate: 'Does the city pay above wholesale for tomatoes?',
    chipDemanda: '2025 demand',
    chipAlertas: 'Risk alerts',
    chipCadastrar: 'Register my produce',
    chipPrecos: "Today's wholesale prices",
    chipComprou: 'What does the city buy most?',
    perguntaComprou: 'Which vegetables did the city buy most in the last two years?',
    kpiValor: 'Value in agricultural tenders',
    kpiValorSub: 'in {n} tenders · 2019–2026',
    carregando: 'loading…',
    indisponivel: 'data unavailable right now',
    kpiItens: 'Agricultural items',
    kpiItensSub: 'classified records',
    kpiCulturas: 'Crops',
    kpiCulturasSub: 'distinct types',
    kpiLicitacoes: 'Tenders',
    kpiLicitacoesSub: 'processes in agricultural scope',
    kpiFonte: 'Source: Curitiba Transparency Portal (SMSAN/FAAC) · agricultural items only',
    grpAnalisar: 'Analyze demand',
    grpGestao: 'Management and quality',
    grpVender: 'Sell to the city',
    grpDuvidas: 'Get answers',
    svcAssistente: 'Assistant',
    svcAssistenteDesc: 'Ask in plain language about purchases, prices and offers.',
    svcDemanda: 'Demand',
    svcDemandaDesc: 'What the city buys: charts and item list.',
    svcDemandaDescProd: 'See which foods the city buys, how much and when.',
    svcMercado: 'Market',
    svcMercadoDesc: 'Wholesale prices (CEASA/PROHORT) × price paid in tenders.',
    svcDocumentos: 'Documents',
    svcDocumentosDesc: 'Calls for bids, terms of reference and minutes.',
    svcProdutor: 'Farmers',
    svcProdutorDesc: 'Family-farming offers registered by chat or spreadsheet.',
    svcProdutorDescProd: 'Register what you produce by chatting with the assistant or uploading a spreadsheet.',
    svcAlertas: 'Risk alerts',
    svcAlertasDesc: 'Signs of price increases, shortages and overpricing.',
    svcAuditoria: 'Data quality',
    svcAuditoriaDesc: 'Coverage of documents, commitments and database consistency.',
    svcColeta: 'Data update',
    svcColetaDesc: 'Daily automatic collection from the Transparency Portal.',
    sobreTitulo: 'About the data and the AI',
    fontesTitulo: 'Where the data comes from',
    fonte1: 'Tenders and items: Curitiba Transparency Portal (SMSAN/FAAC), 2019–2026.',
    fonte2: 'Wholesale prices: CEASA-PR (by variety) and PROHORT/CONAB.',
    fonte3: 'Offers: registered by farmers and cooperatives themselves.',
    iaTitulo: 'How AI is used',
    ia1: 'An AI assistant queries the database and writes the answers automatically.',
    ia2: 'Answers may contain errors: check the source documents and data.',
    ia3: 'The AI does not make decisions or replace official guidance.',
    escopoTitulo: 'Scope and updates',
    escopo1: 'Only agricultural purchases are considered; other tenders are excluded.',
    escopo2: 'Data is updated automatically every day.',
    escopo3: 'Each page states the source of the numbers it shows.',
    rodape1: 'AgroIA-RMC',
    rodape2: "Master's research PPGCA/UEPG",
    rodape3: 'Public data · institutional and academic use',
  },
  es: {
    eyebrow: 'Plataforma de datos públicos · Región Metropolitana de Curitiba',
    titulo: 'Agricultura familiar y compras públicas de alimentos, lado a lado',
    subGestor: 'Vea qué compra la alcaldía, cuánto paga y cómo se compara con el mayorista, y encuentre quién produce en la región.',
    subProdutor: 'Descubra qué compra la alcaldía, siga los precios mayoristas y registre su producción para que lo encuentren.',
    gestor: 'Alcaldía',
    produtor: 'Cooperativas y productores',
    papelAria: 'Elija su perfil',
    placeholder: 'Pregunte en lenguaje natural… ej.: ¿la alcaldía paga más que el mayorista por el tomate?',
    perguntar: 'Preguntar',
    notaIA: 'Respuestas generadas por IA a partir de datos públicos. Verifique siempre las fuentes indicadas.',
    chipTomate: '¿La alcaldía paga más que el mayorista por el tomate?',
    chipDemanda: 'Demanda de 2025',
    chipAlertas: 'Alertas de riesgo',
    chipCadastrar: 'Registrar mi producción',
    chipPrecos: 'Precios mayoristas de hoy',
    chipComprou: '¿Qué compra más la alcaldía?',
    perguntaComprou: '¿Qué hortalizas compró más la alcaldía en los últimos dos años?',
    kpiValor: 'Valor en licitaciones agrícolas',
    kpiValorSub: 'en {n} licitaciones · 2019–2026',
    carregando: 'cargando…',
    indisponivel: 'datos no disponibles por ahora',
    kpiItens: 'Ítems agrícolas',
    kpiItensSub: 'registros clasificados',
    kpiCulturas: 'Cultivos',
    kpiCulturasSub: 'tipos distintos',
    kpiLicitacoes: 'Licitaciones',
    kpiLicitacoesSub: 'procesos en el ámbito agrícola',
    kpiFonte: 'Fuente: Portal de Transparencia de Curitiba (SMSAN/FAAC) · solo ítems agrícolas',
    grpAnalisar: 'Analizar la demanda',
    grpGestao: 'Gestión y calidad',
    grpVender: 'Vender a la alcaldía',
    grpDuvidas: 'Resolver dudas',
    svcAssistente: 'Asistente',
    svcAssistenteDesc: 'Pregunte en lenguaje natural sobre compras, precios y ofertas.',
    svcDemanda: 'Demanda',
    svcDemandaDesc: 'Qué compra la alcaldía: gráficos y lista de ítems.',
    svcDemandaDescProd: 'Vea qué alimentos compra la alcaldía, cuánto y cuándo.',
    svcMercado: 'Mercado',
    svcMercadoDesc: 'Precios mayoristas (CEASA/PROHORT) × precio pagado en las licitaciones.',
    svcDocumentos: 'Documentos',
    svcDocumentosDesc: 'Pliegos, términos de referencia y actas de las licitaciones.',
    svcProdutor: 'Productores',
    svcProdutorDesc: 'Ofertas de la agricultura familiar registradas por chat o planilla.',
    svcProdutorDescProd: 'Registre lo que produce conversando con el asistente o enviando una planilla.',
    svcAlertas: 'Alertas de riesgo',
    svcAlertasDesc: 'Indicios de alza de precio, desabastecimiento y sobreprecio.',
    svcAuditoria: 'Calidad de datos',
    svcAuditoriaDesc: 'Cobertura de documentos, compromisos y consistencia de la base.',
    svcColeta: 'Actualización de datos',
    svcColetaDesc: 'Recolección automática diaria del Portal de Transparencia.',
    sobreTitulo: 'Sobre los datos y la IA',
    fontesTitulo: 'De dónde vienen los datos',
    fonte1: 'Licitaciones e ítems: Portal de Transparencia de Curitiba (SMSAN/FAAC), 2019–2026.',
    fonte2: 'Precios mayoristas: CEASA-PR (por variedad) y PROHORT/CONAB.',
    fonte3: 'Ofertas: registradas por los propios productores y cooperativas.',
    iaTitulo: 'Cómo se usa la IA',
    ia1: 'Un asistente de IA consulta la base y redacta las respuestas automáticamente.',
    ia2: 'Las respuestas pueden contener errores: verifique los documentos y datos de origen.',
    ia3: 'La IA no toma decisiones ni sustituye la orientación oficial.',
    escopoTitulo: 'Alcance y actualización',
    escopo1: 'Solo se consideran compras agrícolas; las demás licitaciones quedan fuera.',
    escopo2: 'Los datos se actualizan automáticamente todos los días.',
    escopo3: 'Cada página indica la fuente de los números que muestra.',
    rodape1: 'AgroIA-RMC',
    rodape2: 'Investigación de maestría PPGCA/UEPG',
    rodape3: 'Datos públicos · uso institucional y académico',
  },
})

type MsgKey = keyof typeof MSG.pt

interface Chip { icon: LucideIcon; label: MsgKey; to: string }
interface Servico { to: string; icon: LucideIcon; title: MsgKey; desc: MsgKey; destaque?: boolean }
interface Grupo { titulo: MsgKey; accent: 'verde' | 'ceu' | 'teal'; servicos: Servico[] }

// Serviços por público: a prefeitura analisa e gere; cooperativas vendem e tiram dúvidas.
const GRUPOS: Record<Papel, Grupo[]> = {
  gestor: [
    {
      titulo: 'grpAnalisar',
      accent: 'verde',
      servicos: [
        { to: '/assistente', icon: MessageSquare, title: 'svcAssistente', desc: 'svcAssistenteDesc', destaque: true },
        { to: '/demanda', icon: ChartColumn, title: 'svcDemanda', desc: 'svcDemandaDesc' },
        { to: '/mercado', icon: TrendingUp, title: 'svcMercado', desc: 'svcMercadoDesc' },
        { to: '/produtor', icon: Tractor, title: 'svcProdutor', desc: 'svcProdutorDesc' },
        { to: '/documentos', icon: FileText, title: 'svcDocumentos', desc: 'svcDocumentosDesc' },
      ],
    },
    {
      titulo: 'grpGestao',
      accent: 'ceu',
      servicos: [
        { to: '/alertas', icon: BellRing, title: 'svcAlertas', desc: 'svcAlertasDesc' },
        { to: '/auditoria', icon: ShieldCheck, title: 'svcAuditoria', desc: 'svcAuditoriaDesc' },
        { to: '/coleta', icon: RefreshCw, title: 'svcColeta', desc: 'svcColetaDesc' },
      ],
    },
  ],
  produtor: [
    {
      titulo: 'grpVender',
      accent: 'teal',
      servicos: [
        { to: '/produtor', icon: Tractor, title: 'svcProdutor', desc: 'svcProdutorDescProd', destaque: true },
        { to: '/demanda', icon: ChartColumn, title: 'svcDemanda', desc: 'svcDemandaDescProd' },
        { to: '/mercado', icon: TrendingUp, title: 'svcMercado', desc: 'svcMercadoDesc' },
      ],
    },
    {
      titulo: 'grpDuvidas',
      accent: 'verde',
      servicos: [
        { to: '/assistente', icon: MessageSquare, title: 'svcAssistente', desc: 'svcAssistenteDesc' },
        { to: '/documentos', icon: FileText, title: 'svcDocumentos', desc: 'svcDocumentosDesc' },
      ],
    },
  ],
}

const fmtMoeda = (v: number) =>
  v >= 1_000_000 ? `R$ ${(v / 1_000_000).toFixed(1)}M`
  : v >= 1_000 ? `R$ ${(v / 1_000).toFixed(0)}K`
  : `R$ ${v.toFixed(0)}`

export default function Home() {
  const t = useT(MSG)
  const navigate = useNavigate()
  const [papel, setPapel] = useState<Papel>(() => {
    try { return (localStorage.getItem('agroia_papel') as Papel) || 'gestor' } catch { return 'gestor' }
  })
  const [pergunta, setPergunta] = useState('')
  const [kpis, setKpis] = useState<KpisAgro | null>(null)
  const [semDados, setSemDados] = useState(false)

  useEffect(() => { try { localStorage.setItem('agroia_papel', papel) } catch { /* sem storage */ } }, [papel])

  // KPIs derivam da MESMA fonte (fetchItensAgro) usada por Demanda/Dashboard/Consultas.
  useEffect(() => {
    // Falha de consulta devolve lista vazia: mostra "—" em vez de "R$ 0" (nunca um zero falso).
    fetchItensAgro().then(rows => {
      if (rows.length) setKpis(kpisFromRows(rows))
      else setSemDados(true)
    })
  }, [])

  const perguntar = (texto = pergunta) => {
    const q = texto.trim()
    if (!q) return
    navigate('/assistente?q=' + encodeURIComponent(q))
  }

  const chips: Chip[] = papel === 'gestor'
    ? [
        { icon: Scale, label: 'chipTomate', to: '/assistente?q=' + encodeURIComponent(t('chipTomate')) },
        { icon: ChartColumn, label: 'chipDemanda', to: '/demanda?ano=2025&view=resumo' },
        { icon: BellRing, label: 'chipAlertas', to: '/alertas' },
      ]
    : [
        { icon: Tractor, label: 'chipCadastrar', to: '/produtor' },
        { icon: TrendingUp, label: 'chipPrecos', to: '/mercado' },
        { icon: CircleHelp, label: 'chipComprou', to: '/assistente?q=' + encodeURIComponent(t('perguntaComprou')) },
      ]

  return (
    <div className="page">
      <div className="home-wrap">
        <section className="home-hero">
          <div className="role-toggle" role="group" aria-label={t('papelAria')}>
            <button className={papel === 'gestor' ? 'active' : ''} aria-pressed={papel === 'gestor'} onClick={() => setPapel('gestor')}>
              <Landmark size={15} aria-hidden /> {t('gestor')}
            </button>
            <button className={papel === 'produtor' ? 'active' : ''} aria-pressed={papel === 'produtor'} onClick={() => setPapel('produtor')}>
              <Tractor size={15} aria-hidden /> {t('produtor')}
            </button>
          </div>

          <div className="page-eyebrow">{t('eyebrow')}</div>
          <h1>{t('titulo')}</h1>
          <p className="home-sub">{papel === 'gestor' ? t('subGestor') : t('subProdutor')}</p>

          <form className="home-ask" onSubmit={e => { e.preventDefault(); perguntar() }}>
            <Search size={19} aria-hidden />
            <input
              aria-label={t('perguntar')}
              placeholder={t('placeholder')}
              value={pergunta}
              onChange={e => setPergunta(e.target.value)}
            />
            <button type="submit" disabled={!pergunta.trim()}>
              {t('perguntar')} <ArrowRight size={16} aria-hidden />
            </button>
          </form>
          <div className="home-ask-note"><Sparkles size={13} aria-hidden /> {t('notaIA')}</div>

          <div className="home-chips">
            {chips.map(({ icon: Icon, label, to }) => (
              <NavLink key={label} to={to} className="chip">
                <Icon size={15} aria-hidden /> {t(label)}
              </NavLink>
            ))}
          </div>
        </section>

        {/* KPIs ao vivo (bento: 2 herói + 2 de apoio), clicáveis → Demanda */}
        <div className="home-kpis" style={{ marginBottom: 8 }}>
          <NavLink to="/demanda?view=resumo" className="metric-card verde heroi">
            <span className="metric-icon"><Coins size={19} aria-hidden /></span>
            <div className="metric-label">{t('kpiValor')}</div>
            <div className="metric-value">{kpis ? fmtMoeda(kpis.valor) : '—'}</div>
            <div className="metric-sub">{kpis ? t('kpiValorSub', { n: fmtNum(kpis.licitacoes) }) : semDados ? t('indisponivel') : t('carregando')}</div>
          </NavLink>
          <NavLink to="/demanda?view=lista" className="metric-card amarelo heroi">
            <span className="metric-icon"><Package size={19} aria-hidden /></span>
            <div className="metric-label">{t('kpiItens')}</div>
            <div className="metric-value">{kpis ? fmtNum(kpis.itens) : '—'}</div>
            <div className="metric-sub">{t('kpiItensSub')}</div>
          </NavLink>
          <NavLink to="/demanda?view=resumo" className="metric-card ceu">
            <span className="metric-icon"><Sprout size={19} aria-hidden /></span>
            <div className="metric-label">{t('kpiCulturas')}</div>
            <div className="metric-value">{kpis ? fmtNum(kpis.culturas) : '—'}</div>
            <div className="metric-sub">{t('kpiCulturasSub')}</div>
          </NavLink>
          <NavLink to="/demanda?view=lista" className="metric-card terra">
            <span className="metric-icon"><ClipboardList size={19} aria-hidden /></span>
            <div className="metric-label">{t('kpiLicitacoes')}</div>
            <div className="metric-value">{kpis ? fmtNum(kpis.licitacoes) : '—'}</div>
            <div className="metric-sub">{t('kpiLicitacoesSub')}</div>
          </NavLink>
        </div>
        <div className="page-source" style={{ marginTop: 0, marginBottom: 8 }}>
          <Database size={13} aria-hidden /> {t('kpiFonte')}
        </div>

        {GRUPOS[papel].map(g => (
          <section key={g.titulo} className="hub-group">
            <h2 className="hub-section-title">{t(g.titulo)}</h2>
            <div className="hub-grid">
              {g.servicos.map(({ to, icon: Icon, title, desc, destaque }) => (
                <NavLink key={to} to={to} className={`hub-card accent-${g.accent}${destaque ? ' destaque' : ''}`}>
                  <div className="hub-icon"><Icon size={22} aria-hidden /></div>
                  <h3>{t(title)} <ArrowRight size={16} aria-hidden /></h3>
                  <p>{t(desc)}</p>
                </NavLink>
              ))}
            </div>
          </section>
        ))}

        <section>
          <h2 className="hub-section-title">{t('sobreTitulo')}</h2>
          <div className="transparencia">
            <div className="card">
              <h4><Database size={17} aria-hidden /> {t('fontesTitulo')}</h4>
              <ul><li>{t('fonte1')}</li><li>{t('fonte2')}</li><li>{t('fonte3')}</li></ul>
            </div>
            <div className="card">
              <h4><Bot size={17} aria-hidden /> {t('iaTitulo')}</h4>
              <ul><li>{t('ia1')}</li><li>{t('ia2')}</li><li>{t('ia3')}</li></ul>
            </div>
            <div className="card">
              <h4><Target size={17} aria-hidden /> {t('escopoTitulo')}</h4>
              <ul><li>{t('escopo1')}</li><li>{t('escopo2')}</li><li>{t('escopo3')}</li></ul>
            </div>
          </div>
        </section>

        <footer className="site-footer">
          <strong>{t('rodape1')}</strong>
          <span>{t('rodape2')}</span>
          <span>{t('rodape3')}</span>
        </footer>
      </div>
    </div>
  )
}
