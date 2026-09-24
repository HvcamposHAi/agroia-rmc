import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { NavLink } from 'react-router-dom'
import { SemaforoPreco } from '../components/SemaforoPreco'
import VariedadesCeasaPR from '../components/VariedadesCeasaPR'
import type { SemaforoCor } from '../components/SemaforoPreco'
import ResponseRenderer from '../components/ResponseRenderer'
import { streamPost, getProhortStatus } from '../lib/apiClient'
import type { SSEEvent, ProhortStatus } from '../lib/apiClient'
import { supabase } from '../lib/supabaseClient'
import { useUrlState } from '../lib/useUrlState'
import { formatarDataHora, formatarDataCurta } from '../lib/format'
import { PERIODOS, recortarJanela, agregarJanela, labelPeriodo } from '../lib/janelaPreco'
import type { PontoSerie } from '../lib/janelaPreco'
import { defineMessages, useI18n, useT, fmtBRL as fmtBRLi, fmtData } from '../i18n'
import type { Lang } from '../i18n'

interface Analise {
  produto_norm: string
  ceasa: string
  ultima_cotacao: string | null
  media_30d: number | null
  media_90d: number | null
  min_30d: number | null
  max_30d: number | null
  variacao_semanal_pct: number | null
  unidade: string | null
  total_cotacoes?: number | null
  // Baseline histórica de 24 meses (view companheira v_prohort_baseline_24m)
  media_24m?: number | null
  min_24m?: number | null
  max_24m?: number | null
  total_24m?: number | null
}

interface Baseline24m {
  ceasa: string
  produto_norm: string
  media_24m: number | null
  min_24m: number | null
  max_24m: number | null
  total_24m: number | null
}

interface Cruz {
  ceasa: string
  preco_kg_prefeitura: number | null
  preco_ceasa_medio: number | null
  unidade_ceasa: string | null
  unidades_compativeis: boolean | null
  diferenca_pct: number | null
  ano_min: number | null
  ano_max: number | null
}

interface LinhaComp { ceasa: string; analise: Analise | null; cruz: Cruz | null }

// Entrepostos coletados (mesmo contrato do coletor/backend). Agrupados por UF na tela.
const CEASAS = [
  { value: 'CURITIBA',              label: 'Curitiba/PR (RMC)',    uf: 'PR' },
  { value: 'MARINGA',               label: 'Maringá/PR',           uf: 'PR' },
  { value: 'FOZ DO IGUACU',         label: 'Foz do Iguaçu/PR',     uf: 'PR' },
  { value: 'CASCAVEL',              label: 'Cascavel/PR',          uf: 'PR' },
  { value: 'SAO PAULO',             label: 'São Paulo/SP',         uf: 'SP' },
  { value: 'RIBEIRAO PRETO',        label: 'Ribeirão Preto/SP',    uf: 'SP' },
  { value: 'SAO JOSE DO RIO PRETO', label: 'S.J. Rio Preto/SP',    uf: 'SP' },
  { value: 'SAO JOSE DOS CAMPOS',   label: 'S.J. Campos/SP',       uf: 'SP' },
  { value: 'SOROCABA',              label: 'Sorocaba/SP',          uf: 'SP' },
  { value: 'FLORIANOPOLIS',         label: 'Gde Florianópolis/SC', uf: 'SC' },
  { value: 'PORTO ALEGRE',          label: 'Porto Alegre/RS',      uf: 'RS' },
]
const UFS = ['PR', 'SP', 'SC', 'RS']   // ordem de exibição (PR primeiro — RMC)

const CONV_SUGGESTIONS: Record<Lang, string[]> = {
  pt: [
    '🍅 Tomate, alface e cenoura — como estão os preços?',
    '🏙️ Compare o preço do tomate em todas as CEASAs',
    '🏛️ A prefeitura paga acima ou abaixo do atacado? (tomate, batata, mandioca)',
    '🥔 Vale a pena vender batata agora?',
  ],
  en: [
    '🍅 Tomato, lettuce and carrot — how are prices?',
    '🏙️ Compare tomato prices across all CEASAs',
    '🏛️ Does the city pay above or below wholesale? (tomato, potato, cassava)',
    '🥔 Is it worth selling potatoes now?',
  ],
  es: [
    '🍅 Tomate, lechuga y zanahoria — ¿cómo están los precios?',
    '🏙️ Compara el precio del tomate en todas las CEASAs',
    '🏛️ ¿La alcaldía paga por encima o por debajo del mayorista? (tomate, papa, yuca)',
    '🥔 ¿Vale la pena vender papa ahora?',
  ],
}

const MSG = defineMessages({
  pt: {
    nd: 'N/D',
    semAbaixo24: 'Preço abaixo da média de 24 meses',
    semAcima24: 'Preço acima da média de 24 meses',
    semDentro24: 'Preço dentro da média de 24 meses',
    semAbaixoHist: 'Preço abaixo da média histórica',
    semAcimaHist: 'Preço acima da média histórica',
    semDentroHist: 'Preço dentro da média histórica',
    semInsuf: 'Histórico insuficiente',
    consultandoPrecos: '🔍 Consultando preços...',
    processandoEmoji: '⏳ Processando...',
    erroConv: '⚠️ Não foi possível consultar agora. Verifique se o servidor está ativo e tente novamente.',
    semCotacao: 'Produto "{prod}" sem cotação PROHORT/CONAB nas CEASAs selecionadas. Veja as variedades da CEASA/PR abaixo (se houver) ou escolha um da lista.',
    erroDesconhecido: 'Erro desconhecido',
    dias30: '30 dias',
    titulo: 'Preços de Mercado — CEASAs',
    subtitulo: 'Atacado PROHORT/CONAB × o que a prefeitura paga nas licitações · atualização diária',
    ultimaColeta: '🕒 Última coleta: {d}',
    dadosMercado: '📅 Dados de mercado',
    dadosAte: ' · dados até {d}',
    pergunte: '💬 Pergunte sobre preços',
    processando: 'Processando...',
    irFim: 'Ir para o fim',
    placeholderConv: 'Ex: a prefeitura paga acima do atacado em tomate e mandioca?',
    rodapeConv: 'Preço mín./médio/máx./sugerido, comparação entre CEASAs e cruzamento com o que a prefeitura paga · Fonte: CONAB/PROHORT + licitações',
    consultaDetalhada: 'Consulta detalhada por produto',
    placeholderProduto: '🔎 Digite ou escolha um produto...',
    dataInicial: 'Data inicial',
    ate: 'até',
    dataFinal: 'Data final',
    consultando: 'Consultando...',
    consultar: 'Consultar',
    produtosDisponiveis: 'Produtos disponíveis na CEASA {c}:',
    verDemanda: '📊 Ver demanda da prefeitura',
    quemVende: '🧺 Quem vende {p}',
    minimo: 'Mínimo',
    medio: 'Médio',
    maximo: 'Máximo',
    sugerido: 'Sugerido',
    refVenda: 'referência de venda',
    media24: 'Média 24m',
    baseHist: 'base histórica',
    nCotacoes: ' · {n} cotações',
    naSemana: '% na semana',
    ultimaCotacao: 'Última cotação: {d}',
    ceasaPref: '🏛️ CEASA × Prefeitura — {p}',
    medioAtacado: 'Médio (atacado)',
    prefPagou: 'Prefeitura pagou',
    diferenca: 'Diferença',
    unid: 'Unid.',
    semRegistro: 'sem registro',
    unDif: 'un. dif. ({u})',
    acima: 'acima',
    abaixo: 'abaixo',
    notaPref1: '"Prefeitura pagou" = mediana histórica das licitações de agricultura familiar',
    notaPref2: ', em R$/kg. A diferença só é calculada quando a unidade do CEASA é kg. O preço de atacado é dos últimos 30 dias (descasamento temporal). Fonte: CONAB/PROHORT + licitações SMSAN/FAAC.',
    evolucao: 'Evolução do Preço — {p} / CEASA {c}',
    dataLabel: 'Data: {d}',
    precoMedio: 'Preço Médio',
    vazioTitulo: 'Selecione um produto e uma ou mais CEASAs para ver os detalhes',
    vazioSub: 'Dados do PROHORT/CONAB · atualizados diariamente',
  },
  en: {
    nd: 'N/A',
    semAbaixo24: 'Price below the 24-month average',
    semAcima24: 'Price above the 24-month average',
    semDentro24: 'Price within the 24-month average',
    semAbaixoHist: 'Price below the historical average',
    semAcimaHist: 'Price above the historical average',
    semDentroHist: 'Price within the historical average',
    semInsuf: 'Insufficient history',
    consultandoPrecos: '🔍 Checking prices...',
    processandoEmoji: '⏳ Processing...',
    erroConv: '⚠️ Could not check right now. Make sure the server is running and try again.',
    semCotacao: 'Product "{prod}" has no PROHORT/CONAB quote in the selected CEASAs. See the CEASA/PR varieties below (if any) or pick one from the list.',
    erroDesconhecido: 'Unknown error',
    dias30: '30 days',
    titulo: 'Market Prices — CEASAs',
    subtitulo: 'PROHORT/CONAB wholesale × what the city pays in public tenders · updated daily',
    ultimaColeta: '🕒 Last collection: {d}',
    dadosMercado: '📅 Market data',
    dadosAte: ' · data up to {d}',
    pergunte: '💬 Ask about prices',
    processando: 'Processing...',
    irFim: 'Go to bottom',
    placeholderConv: 'E.g.: does the city pay above wholesale for tomato and cassava?',
    rodapeConv: 'Min./avg./max./suggested price, comparison across CEASAs and cross-check with what the city pays · Source: CONAB/PROHORT + public tenders',
    consultaDetalhada: 'Detailed lookup by product',
    placeholderProduto: '🔎 Type or choose a product...',
    dataInicial: 'Start date',
    ate: 'to',
    dataFinal: 'End date',
    consultando: 'Searching...',
    consultar: 'Search',
    produtosDisponiveis: 'Products available at CEASA {c}:',
    verDemanda: "📊 See the city's demand",
    quemVende: '🧺 Who sells {p}',
    minimo: 'Minimum',
    medio: 'Average',
    maximo: 'Maximum',
    sugerido: 'Suggested',
    refVenda: 'selling reference',
    media24: '24m average',
    baseHist: 'historical baseline',
    nCotacoes: ' · {n} quotes',
    naSemana: '% this week',
    ultimaCotacao: 'Last quote: {d}',
    ceasaPref: '🏛️ CEASA × City — {p}',
    medioAtacado: 'Average (wholesale)',
    prefPagou: 'City paid',
    diferenca: 'Difference',
    unid: 'Unit',
    semRegistro: 'no record',
    unDif: 'diff. unit ({u})',
    acima: 'above',
    abaixo: 'below',
    notaPref1: '"City paid" = historical median of family-farming tenders',
    notaPref2: ', in R$/kg. The difference is only calculated when the CEASA unit is kg. The wholesale price covers the last 30 days (time mismatch). Source: CONAB/PROHORT + SMSAN/FAAC tenders.',
    evolucao: 'Price Trend — {p} / CEASA {c}',
    dataLabel: 'Date: {d}',
    precoMedio: 'Average Price',
    vazioTitulo: 'Select a product and one or more CEASAs to see the details',
    vazioSub: 'PROHORT/CONAB data · updated daily',
  },
  es: {
    nd: 'N/D',
    semAbaixo24: 'Precio por debajo del promedio de 24 meses',
    semAcima24: 'Precio por encima del promedio de 24 meses',
    semDentro24: 'Precio dentro del promedio de 24 meses',
    semAbaixoHist: 'Precio por debajo del promedio histórico',
    semAcimaHist: 'Precio por encima del promedio histórico',
    semDentroHist: 'Precio dentro del promedio histórico',
    semInsuf: 'Historial insuficiente',
    consultandoPrecos: '🔍 Consultando precios...',
    processandoEmoji: '⏳ Procesando...',
    erroConv: '⚠️ No fue posible consultar ahora. Verifica que el servidor esté activo e inténtalo de nuevo.',
    semCotacao: 'El producto "{prod}" no tiene cotización PROHORT/CONAB en las CEASAs seleccionadas. Mira las variedades de la CEASA/PR abajo (si las hay) o elige uno de la lista.',
    erroDesconhecido: 'Error desconocido',
    dias30: '30 días',
    titulo: 'Precios de Mercado — CEASAs',
    subtitulo: 'Mayorista PROHORT/CONAB × lo que paga la alcaldía en las licitaciones · actualización diaria',
    ultimaColeta: '🕒 Última recolección: {d}',
    dadosMercado: '📅 Datos de mercado',
    dadosAte: ' · datos hasta {d}',
    pergunte: '💬 Pregunta sobre precios',
    processando: 'Procesando...',
    irFim: 'Ir al final',
    placeholderConv: 'Ej.: ¿la alcaldía paga por encima del mayorista en tomate y yuca?',
    rodapeConv: 'Precio mín./medio/máx./sugerido, comparación entre CEASAs y cruce con lo que paga la alcaldía · Fuente: CONAB/PROHORT + licitaciones',
    consultaDetalhada: 'Consulta detallada por producto',
    placeholderProduto: '🔎 Escribe o elige un producto...',
    dataInicial: 'Fecha inicial',
    ate: 'hasta',
    dataFinal: 'Fecha final',
    consultando: 'Consultando...',
    consultar: 'Consultar',
    produtosDisponiveis: 'Productos disponibles en la CEASA {c}:',
    verDemanda: '📊 Ver demanda de la alcaldía',
    quemVende: '🧺 Quién vende {p}',
    minimo: 'Mínimo',
    medio: 'Medio',
    maximo: 'Máximo',
    sugerido: 'Sugerido',
    refVenda: 'referencia de venta',
    media24: 'Promedio 24m',
    baseHist: 'base histórica',
    nCotacoes: ' · {n} cotizaciones',
    naSemana: '% en la semana',
    ultimaCotacao: 'Última cotización: {d}',
    ceasaPref: '🏛️ CEASA × Alcaldía — {p}',
    medioAtacado: 'Medio (mayorista)',
    prefPagou: 'Alcaldía pagó',
    diferenca: 'Diferencia',
    unid: 'Unid.',
    semRegistro: 'sin registro',
    unDif: 'unid. dif. ({u})',
    acima: 'por encima',
    abaixo: 'por debajo',
    notaPref1: '"Alcaldía pagó" = mediana histórica de las licitaciones de agricultura familiar',
    notaPref2: ', en R$/kg. La diferencia solo se calcula cuando la unidad de la CEASA es kg. El precio mayorista es de los últimos 30 días (desfase temporal). Fuente: CONAB/PROHORT + licitaciones SMSAN/FAAC.',
    evolucao: 'Evolución del Precio — {p} / CEASA {c}',
    dataLabel: 'Fecha: {d}',
    precoMedio: 'Precio Medio',
    vazioTitulo: 'Selecciona un producto y una o más CEASAs para ver los detalles',
    vazioSub: 'Datos de PROHORT/CONAB · actualizados diariamente',
  },
})

type TFn = (chave: keyof typeof MSG.pt & string, vars?: Record<string, string | number>) => string

// Cores das linhas do gráfico (recharts exige string de cor)
const CHART_VERDE = '#0f766e'
const CHART_TERRA = '#78716c'
const CHART_CEO   = '#1e3a5f'

function calcularSemaforo(a: Analise, t: TFn): { cor: SemaforoCor; texto: string } {
  const m30 = a.media_30d
  // Baseline de 24 meses quando há histórico; senão, referência de 90 dias.
  const base = a.media_24m != null ? a.media_24m : a.media_90d
  const b24 = a.media_24m != null
  if (m30 != null && base != null && base > 0) {
    const desvio = ((m30 - base) / base) * 100
    if (desvio < -10) return { cor: 'verde', texto: t(b24 ? 'semAbaixo24' : 'semAbaixoHist') }
    if (desvio > 10)  return { cor: 'vermelho', texto: t(b24 ? 'semAcima24' : 'semAcimaHist') }
    return { cor: 'amarelo', texto: t(b24 ? 'semDentro24' : 'semDentroHist') }
  }
  return { cor: 'cinza', texto: t('semInsuf') }
}

// Réplica EXATA da fórmula do backend (chat/tools.py :: _prohort_preco_sugerido).
// Alterar as duas juntas: base 30d + tendência, limitada à faixa 30d e à faixa de 24 meses.
function precoSugerido(a: Analise): number | null {
  const m30 = a.media_30d
  if (m30 == null) return null
  let base = m30
  const v = a.variacao_semanal_pct
  if (v != null) {
    if (v > 5) base = m30 * 1.05
    else if (v < -5) base = m30
  }
  if (a.min_30d != null) base = Math.max(base, a.min_30d)
  if (a.max_30d != null) base = Math.min(base, a.max_30d)
  if (a.min_24m != null) base = Math.max(base, a.min_24m)
  if (a.max_24m != null) base = Math.min(base, a.max_24m)
  return Math.round(base * 100) / 100
}

const labelCeasa = (v: string) => CEASAS.find((c) => c.value === v)?.label ?? v

export default function Mercado() {
  const { lang } = useI18n()
  const t = useT(MSG)
  const fmtBRL = (v: number | null | undefined) =>
    v == null ? t('nd') : fmtBRLi(v, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  const [produtos, setProdutos]     = useState<string[]>([])
  const [produto, setProduto]       = useUrlState('produto')
  const [ceasasRaw, setCeasasRaw]   = useUrlState('ceasas', 'CURITIBA')
  const ceasasSelRaw = ceasasRaw.split(',').filter(Boolean)
  const ceasasSel = ceasasSelRaw.length ? ceasasSelRaw : ['CURITIBA']
  const [periodo, setPeriodo]       = useUrlState('periodo', '30')   // 'hoje' | 'N' | 'custom'
  const [de, setDe]                 = useUrlState('de')    // custom: data inicial ISO
  const [ate, setAte]               = useUrlState('ate')   // custom: data final ISO
  const [analise, setAnalise]       = useState<Analise | null>(null)   // CEASA principal
  const [comparativo, setComparativo] = useState<LinhaComp[]>([])
  const [serieCompleta, setSerieCompleta] = useState<PontoSerie[]>([])  // série inteira (recortada na exibição)
  const [consultado, setConsultado] = useState('')   // produto da última consulta (painel de variedades)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro]             = useState<string | null>(null)

  // Última atualização dos preços (cabeçalho). Falha silenciosa: nunca bloqueia a página.
  const [statusPreco, setStatusPreco] = useState<ProhortStatus | null>(null)
  useEffect(() => {
    let ativo = true
    getProhortStatus()
      .then((s) => { if (ativo) setStatusPreco(s) })
      .catch(() => { /* sem indicador de data — cabeçalho permanece com o texto padrão */ })
    return () => { ativo = false }
  }, [])

  const primaria = ceasasSel[0]

  // Assistente conversacional de preços (IA)
  const [convMsgs, setConvMsgs]   = useState<{ role: 'user' | 'assistant'; content: string }[]>([])
  const [convInput, setConvInput] = useState('')
  const [convLoading, setConvLoading] = useState(false)
  const [convStatus, setConvStatus]   = useState('')

  // Scroll APENAS dentro da caixa de mensagens (a página nunca se move)
  const messagesRef = useRef<HTMLDivElement>(null)
  const atBottomRef = useRef(true)
  const [mostrarIrFim, setMostrarIrFim] = useState(false)

  const aoRolarMensagens = () => {
    const el = messagesRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40
    atBottomRef.current = atBottom
    setMostrarIrFim(!atBottom)
  }
  const irParaFim = () => {
    const el = messagesRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
    atBottomRef.current = true
    setMostrarIrFim(false)
  }
  useEffect(() => {
    const el = messagesRef.current
    if (el && atBottomRef.current) el.scrollTop = el.scrollHeight
  }, [convMsgs, convStatus])

  const toggleCeasa = (v: string) => {
    const has = ceasasSel.includes(v)
    let next = has ? ceasasSel.filter((x) => x !== v) : [...ceasasSel, v]
    if (next.length === 0) next = ceasasSel   // garante ≥1 selecionada
    setCeasasRaw(next.join(','))
  }

  const enviarConversa = useCallback(async (texto: string) => {
    const msg = texto.trim()
    if (!msg || convLoading) return
    const ctx = ceasasSel.map(labelCeasa).join(', ')
    const historico = convMsgs.slice(-6)
    atBottomRef.current = true
    setConvMsgs((p) => [...p, { role: 'user', content: msg }, { role: 'assistant', content: '' }])
    setConvInput('')
    setConvLoading(true)
    setConvStatus(t('consultandoPrecos'))
    try {
      const pergunta = `[CEASAs de referência: ${ctx} (${ceasasSel.join(', ')})]\n${msg}`
      let full = ''
      for await (const ev of streamPost<SSEEvent>('/prohort/chat/stream', { pergunta, historico })) {
        if (ev.tipo === 'status') setConvStatus(ev.msg || t('processandoEmoji'))
        else if (ev.tipo === 'token') {
          full += ev.texto || ''
          setConvMsgs((p) => { const u = [...p]; u[u.length - 1].content = full; return u })
        } else if (ev.tipo === 'fim') setConvStatus('')
      }
    } catch {
      setConvMsgs((p) => {
        const u = [...p]
        u[u.length - 1].content = t('erroConv')
        return u
      })
    } finally {
      setConvLoading(false)
      setConvStatus('')
    }
  }, [convMsgs, convLoading, ceasasSel, t])

  // Lista de produtos disponíveis (CEASA principal)
  useEffect(() => {
    let ativo = true
    supabase
      .from('v_prohort_analise')
      .select('produto_norm')
      .eq('ceasa', primaria)
      .then(({ data }) => {
        if (!ativo) return
        const unicos = Array.from(
          new Set((data ?? []).map((r: { produto_norm: string }) => r.produto_norm).filter(Boolean))
        ).sort()
        setProdutos(unicos)
      })
    return () => { ativo = false }
  }, [primaria])

  const consultar = useCallback(async (prodArg?: string) => {
    const prod = (prodArg ?? produto).trim()
    if (!prod) return
    if (prodArg !== undefined) setProduto(prodArg)
    setConsultado(prod)
    setCarregando(true)
    setErro(null)
    try {
      const termo = prod.toLowerCase()
      const [aRes, cRes, bRes] = await Promise.all([
        supabase.from('v_prohort_analise').select('*')
          .ilike('produto_norm', `%${termo}%`).in('ceasa', ceasasSel),
        supabase.from('vw_cruzamento_precos_ceasa').select('*')
          .ilike('produto_norm', `%${termo}%`).in('ceasa', ceasasSel),
        // baseline histórica de 24 meses (view companheira; ignora se ainda não existe)
        supabase.from('v_prohort_baseline_24m').select('*')
          .ilike('produto_norm', `%${termo}%`).in('ceasa', ceasasSel),
      ])
      if (aRes.error) throw new Error(aRes.error.message)
      const aData = (aRes.data ?? []) as Analise[]
      if (aData.length === 0) {
        setAnalise(null); setComparativo([]); setSerieCompleta([])
        setErro(t('semCotacao', { prod }))
        return
      }
      // melhor linha por CEASA (mais cotações)
      const bestA: Record<string, Analise> = {}
      for (const r of aData) {
        const c = r.ceasa
        if (!bestA[c] || (r.total_cotacoes ?? 0) > (bestA[c].total_cotacoes ?? 0)) bestA[c] = r
      }
      // mescla a baseline de 24 meses por (ceasa, produto_norm) na melhor linha
      const bData = (bRes.error ? [] : (bRes.data ?? [])) as Baseline24m[]
      for (const c of Object.keys(bestA)) {
        const b = bData.find((x) => x.ceasa === c && x.produto_norm === bestA[c].produto_norm)
        if (b) {
          bestA[c] = { ...bestA[c], media_24m: b.media_24m, min_24m: b.min_24m, max_24m: b.max_24m, total_24m: b.total_24m }
        }
      }
      // cruzamento (ignora se a view ainda não existe)
      const cData = (cRes.error ? [] : (cRes.data ?? [])) as Cruz[]
      const bestC: Record<string, Cruz> = {}
      for (const r of cData) bestC[r.ceasa] = r

      const comp: LinhaComp[] = ceasasSel
        .filter((c) => bestA[c])
        .map((c) => ({ ceasa: c, analise: bestA[c], cruz: bestC[c] ?? null }))
      setComparativo(comp)
      setAnalise(bestA[primaria] ?? comp[0]?.analise ?? null)

      // Série do gráfico: produto_norm EXATO (evita truncamento de 1000 linhas do PostgREST
      // quando o ilike casa vários produtos em janelas longas de 24 meses).
      const prodExato = (bestA[primaria] ?? comp[0]?.analise)?.produto_norm
      let todos: PontoSerie[] = []
      if (prodExato) {
        const sRes = await supabase.from('v_prohort_serie_diaria')
          .select('data_coleta, preco_medio, preco_min, preco_max, unidade')
          .eq('produto_norm', prodExato).eq('ceasa', primaria)
          .order('data_coleta', { ascending: true })
        todos = (sRes.data ?? []) as PontoSerie[]
      }
      setSerieCompleta(todos)   // recorte por janela é derivado na exibição (useMemo)
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : t('erroDesconhecido'))
      setAnalise(null); setComparativo([]); setSerieCompleta([])
    } finally {
      setCarregando(false)
    }
  }, [produto, ceasasSel, primaria, t])

  // Restaura a consulta ao voltar para a página (produto vindo da URL)
  const restaurado = useRef(false)
  useEffect(() => {
    if (!restaurado.current && produto.trim()) {
      restaurado.current = true
      consultar()
    }
  }, [produto, consultar])

  const formatarData = (d: string) =>
    fmtData(new Date(d + 'T00:00:00'), { day: '2-digit', month: '2-digit' })

  const semaforo = analise ? calcularSemaforo(analise, t) : null
  const sugerido = analise ? precoSugerido(analise) : null
  const unidade = analise?.unidade || 'kg'
  const periodoPref = comparativo.find((l) => l.cruz?.ano_min != null)?.cruz

  // Recorte da série pela janela escolhida + agregados dos cards (reativos, sem refetch).
  const serie = useMemo(() => recortarJanela(serieCompleta, periodo, de, ate), [serieCompleta, periodo, de, ate])
  const janelaAgg = useMemo(() => agregarJanela(serie), [serie])
  const periodoLabel = labelPeriodo(periodo, de, ate, serieCompleta, lang)
  // MÍN/MÉD/MÁX vêm da janela; fallback à view de 30d quando a série está vazia.
  const temJanela = janelaAgg.n > 0
  const cardMin   = temJanela ? janelaAgg.min   : analise?.min_30d ?? null
  const cardMedia = temJanela ? janelaAgg.media : analise?.media_30d ?? null
  const cardMax   = temJanela ? janelaAgg.max   : analise?.max_30d ?? null
  const cardSub   = temJanela ? periodoLabel : t('dias30')

  return (
    <div className="page">
      {/* Cabeçalho */}
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontFamily: 'Inter, sans-serif', fontSize: 22, fontWeight: 700, color: 'var(--texto)', margin: 0 }}>
          {t('titulo')}
        </h2>
        <p style={{ fontSize: 14, color: 'var(--texto-suave)', marginTop: 6 }}>
          {t('subtitulo')}
        </p>
        {statusPreco && (statusPreco.finalizado_em || statusPreco.data_max) && (
          <p style={{ fontSize: 12, color: 'var(--texto-suave)', marginTop: 4, fontWeight: 600 }}>
            {statusPreco.finalizado_em
              ? t('ultimaColeta', { d: formatarDataHora(statusPreco.finalizado_em) })
              : t('dadosMercado')}
            {statusPreco.data_max ? t('dadosAte', { d: formatarDataCurta(statusPreco.data_max) }) : ''}
          </p>
        )}
      </div>

      {/* ── Assistente conversacional de preços (IA) — destaque ───────────── */}
      <div className="chart-card" style={{ margin: '0 0 24px' }}>
        <div style={{ marginBottom: 14 }}>
          <h3 style={{ margin: '0 0 10px' }}>{t('pergunte')}</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {UFS.map((uf) => (
              <div key={uf} style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 11, fontWeight: 800, color: 'var(--texto-suave)', minWidth: 24 }}>{uf}</span>
                {CEASAS.filter((c) => c.uf === uf).map((c) => {
                  const on = ceasasSel.includes(c.value)
                  return (
                    <button
                      key={c.value}
                      onClick={() => toggleCeasa(c.value)}
                      className="suggestion-btn"
                      style={{
                        padding: '4px 10px', fontSize: 12,
                        borderColor: on ? 'var(--verde)' : 'var(--borda)',
                        background: on ? 'var(--verde-fundo)' : 'var(--branco)',
                        color: on ? 'var(--verde)' : 'var(--texto)', fontWeight: on ? 700 : 600,
                      }}
                    >
                      {on ? '✓ ' : ''}{c.label}
                    </button>
                  )
                })}
              </div>
            ))}
          </div>
        </div>

        {/* Caixa de mensagens — rola POR DENTRO; a página fica parada */}
        {convMsgs.length > 0 && (
          <div style={{ position: 'relative', marginBottom: 14 }}>
            <div
              ref={messagesRef}
              onScroll={aoRolarMensagens}
              style={{ display: 'flex', flexDirection: 'column', gap: 16, maxHeight: 440, overflowY: 'auto', padding: '4px 2px' }}
            >
              {convMsgs.map((m, i) => (
                <div key={i} className={`msg ${m.role}`} style={m.role === 'assistant' ? { maxWidth: '100%' } : undefined}>
                  <div className="msg-avatar">{m.role === 'assistant' ? '🌾' : '👤'}</div>
                  <div className="msg-bubble" style={m.role === 'assistant' ? { maxWidth: '100%', width: '100%' } : undefined}>
                    {m.role === 'assistant'
                      ? (m.content
                          ? <ResponseRenderer content={m.content} />
                          : <span style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                              <span className="spinner" />
                              <span style={{ color: 'var(--texto-suave)', fontSize: 13 }}>{convStatus || t('processando')}</span>
                            </span>)
                      : m.content}
                  </div>
                </div>
              ))}
            </div>
            {mostrarIrFim && (
              <button
                onClick={irParaFim}
                title={t('irFim')}
                aria-label={t('irFim')}
                style={{
                  position: 'absolute', bottom: 8, right: 8, width: 34, height: 34, borderRadius: '50%',
                  border: '1px solid var(--borda)', background: 'var(--branco)', color: 'var(--verde)',
                  cursor: 'pointer', boxShadow: '0 2px 8px rgba(0,0,0,0.12)', fontSize: 16, lineHeight: 1,
                }}
              >
                ↓
              </button>
            )}
          </div>
        )}

        {convMsgs.length === 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 14 }}>
            {CONV_SUGGESTIONS[lang].map((s) => (
              <button key={s} className="suggestion-btn" onClick={() => enviarConversa(s.replace(/^[^\s]+\s/, ''))}>
                {s}
              </button>
            ))}
          </div>
        )}

        <div className="chat-input-wrapper">
          <input
            className="chat-input"
            value={convInput}
            onChange={(e) => setConvInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') enviarConversa(convInput) }}
            placeholder={t('placeholderConv')}
            disabled={convLoading}
          />
          <button className="send-btn" onClick={() => enviarConversa(convInput)} disabled={convLoading || !convInput.trim()}>
            <svg viewBox="0 0 24 24"><path d="M2 21l21-9L2 3v7l15 2-15 2v7z" /></svg>
          </button>
        </div>
        <p style={{ fontSize: 11, color: 'var(--texto-suave)', marginTop: 8 }}>
          {t('rodapeConv')}
        </p>
      </div>

      {/* ── Consulta detalhada por produto ───────────────────────────────── */}
      <h3 style={{ fontFamily: 'Inter, sans-serif', fontSize: 17, fontWeight: 700, color: 'var(--texto)', margin: '0 0 12px' }}>
        {t('consultaDetalhada')}
      </h3>

      <div className="filters-bar" style={{ marginBottom: 16 }}>
        <input
          className="search-input"
          list="lista-produtos"
          value={produto}
          onChange={(e) => setProduto(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') consultar() }}
          placeholder={t('placeholderProduto')}
        />
        <datalist id="lista-produtos">
          {produtos.map((p) => <option key={p} value={p} />)}
        </datalist>

        <select className="filter-select" value={periodo} onChange={(e) => setPeriodo(e.target.value)}>
          {PERIODOS.map((p) => <option key={p.value} value={p.value}>{p.labels[lang]}</option>)}
        </select>

        {periodo === 'custom' && (
          <>
            <input
              type="date" className="filter-select" value={de} max={ate || undefined}
              onChange={(e) => setDe(e.target.value)} aria-label={t('dataInicial')}
            />
            <span style={{ color: 'var(--texto-suave)', fontSize: 13 }}>{t('ate')}</span>
            <input
              type="date" className="filter-select" value={ate} min={de || undefined}
              onChange={(e) => setAte(e.target.value)} aria-label={t('dataFinal')}
            />
          </>
        )}

        <button
          onClick={() => consultar()}
          disabled={!produto || carregando}
          style={{
            background: produto && !carregando ? 'var(--verde)' : 'var(--borda)',
            color: '#fff', border: 'none', borderRadius: 10, padding: '9px 22px',
            fontFamily: 'Inter, sans-serif', fontWeight: 700, fontSize: 14,
            cursor: produto && !carregando ? 'pointer' : 'not-allowed',
          }}
        >
          {carregando ? t('consultando') : t('consultar')}
        </button>

        <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--texto-suave)', fontWeight: 600 }}>
          CEASAs: {ceasasSel.map(labelCeasa).join(', ')}
        </span>
      </div>

      {erro && (
        <div style={{ padding: '12px 16px', background: '#fee2e2', borderRadius: 10, color: '#dc2626', marginBottom: 16, fontSize: 14 }}>
          {erro}
        </div>
      )}

      {/* Chips de produtos disponíveis */}
      {produtos.length > 0 && !analise && (
        <div style={{ marginBottom: 24 }}>
          <p style={{ fontSize: 13, color: 'var(--texto-suave)', fontWeight: 600, margin: '0 0 10px' }}>
            {t('produtosDisponiveis', { c: labelCeasa(primaria) })}
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            {produtos.map((p) => (
              <button key={p} className="suggestion-btn" style={{ textTransform: 'capitalize' }} onClick={() => consultar(p)}>
                {p}
              </button>
            ))}
          </div>
        </div>
      )}

      {analise && (
        <>
          <div className="item-links" style={{ marginBottom: 14 }}>
            <NavLink to={`/demanda?view=lista&q=${encodeURIComponent(produto)}`}>{t('verDemanda')}</NavLink>
            <NavLink to={`/ofertas?q=${encodeURIComponent(produto)}`}>{t('quemVende', { p: produto })}</NavLink>
          </div>
          {/* KPI da CEASA principal */}
          <div className="metrics-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', marginBottom: 16 }}>
            <div className="metric-card verde">
              <span className="metric-icon">⬇️</span>
              <div className="metric-label">{t('minimo')} · {labelCeasa(primaria)}</div>
              <div className="metric-value">{fmtBRL(cardMin)}</div>
              <div className="metric-sub">/{unidade} · {cardSub}</div>
            </div>
            <div className="metric-card ceu">
              <span className="metric-icon">📊</span>
              <div className="metric-label">{t('medio')}</div>
              <div className="metric-value">{fmtBRL(cardMedia)}</div>
              <div className="metric-sub">/{unidade} · {cardSub}</div>
            </div>
            <div className="metric-card terra">
              <span className="metric-icon">⬆️</span>
              <div className="metric-label">{t('maximo')}</div>
              <div className="metric-value">{fmtBRL(cardMax)}</div>
              <div className="metric-sub">/{unidade} · {cardSub}</div>
            </div>
            <div className="metric-card amarelo">
              <span className="metric-icon">🎯</span>
              <div className="metric-label">{t('sugerido')}</div>
              <div className="metric-value">{fmtBRL(sugerido)}</div>
              <div className="metric-sub">/{unidade} · {t('refVenda')}</div>
            </div>
            <div className="metric-card ceu">
              <span className="metric-icon">📅</span>
              <div className="metric-label">{t('media24')}</div>
              <div className="metric-value">{fmtBRL(analise.media_24m)}</div>
              <div className="metric-sub">
                /{unidade} · {t('baseHist')}{analise.total_24m != null ? t('nCotacoes', { n: analise.total_24m }) : ''}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', marginBottom: 20 }}>
            {semaforo && <SemaforoPreco semaforo={semaforo.cor} texto={semaforo.texto} />}
            {analise.variacao_semanal_pct != null && (
              <span style={{
                fontSize: 13, fontWeight: 700,
                color: analise.variacao_semanal_pct > 0 ? '#dc2626'
                  : analise.variacao_semanal_pct < 0 ? 'var(--verde)' : 'var(--texto-suave)',
              }}>
                {analise.variacao_semanal_pct > 0 ? '▲' : analise.variacao_semanal_pct < 0 ? '▼' : '▬'}{' '}
                {analise.variacao_semanal_pct > 0 ? '+' : ''}{analise.variacao_semanal_pct.toFixed(1)}{t('naSemana')}
              </span>
            )}
            <span style={{ fontSize: 12, color: 'var(--texto-suave)' }}>
              {t('ultimaCotacao', { d: analise.ultima_cotacao ?? t('nd') })}
            </span>
          </div>

          {/* Tabela comparativa CEASA × Prefeitura */}
          <div className="chart-card" style={{ marginBottom: 20, padding: '18px 20px' }}>
            <h3 style={{ margin: '0 0 12px' }}>{t('ceasaPref', { p: produto.charAt(0).toUpperCase() + produto.slice(1) })}</h3>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ background: 'var(--verde-fundo)', color: 'var(--verde)' }}>
                    <th style={thStyle}>CEASA</th>
                    <th style={thStyle}>{t('medioAtacado')}</th>
                    <th style={thStyle}>{t('sugerido')}</th>
                    <th style={thStyle}>{t('prefPagou')}</th>
                    <th style={thStyle}>{t('diferenca')}</th>
                    <th style={thStyle}>{t('unid')}</th>
                  </tr>
                </thead>
                <tbody>
                  {comparativo.map((l) => {
                    const a = l.analise
                    const c = l.cruz
                    const un = a?.unidade || 'kg'
                    let dif: ReactNode = <span style={{ color: 'var(--texto-suave)' }}>{t('semRegistro')}</span>
                    if (c && c.preco_kg_prefeitura != null) {
                      if (!c.unidades_compativeis) {
                        dif = <span style={{ color: 'var(--texto-suave)' }}>{t('unDif', { u: c.unidade_ceasa ?? '' })}</span>
                      } else if (c.diferenca_pct != null) {
                        const acima = c.diferenca_pct > 0
                        dif = <span style={{ color: acima ? '#dc2626' : 'var(--verde)', fontWeight: 700 }}>
                          {acima ? '▲ +' : '▼ '}{c.diferenca_pct.toFixed(1)}% {acima ? t('acima') : t('abaixo')}
                        </span>
                      }
                    }
                    return (
                      <tr key={l.ceasa} style={{ borderBottom: '1px solid var(--borda)' }}>
                        <td style={{ ...tdStyle, fontWeight: 700 }}>{labelCeasa(l.ceasa)}</td>
                        <td style={tdStyle}>{fmtBRL(a?.media_30d)}</td>
                        <td style={tdStyle}>{fmtBRL(a ? precoSugerido(a) : null)}</td>
                        <td style={tdStyle}>{c?.preco_kg_prefeitura != null ? `${fmtBRL(c.preco_kg_prefeitura)}/kg` : <span style={{ color: 'var(--texto-suave)' }}>—</span>}</td>
                        <td style={tdStyle}>{dif}</td>
                        <td style={tdStyle}>{un}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <p style={{ fontSize: 11, color: 'var(--texto-suave)', margin: '10px 0 0', lineHeight: 1.5 }}>
              {t('notaPref1')}
              {periodoPref ? ` (${periodoPref.ano_min}–${periodoPref.ano_max})` : ''}{t('notaPref2')}
            </p>
          </div>
        </>
      )}

      {consultado && <VariedadesCeasaPR produto={consultado} unidadeInicial={primaria} />}

      {serie.length > 0 && (
        <div className="chart-card">
          <h3>{t('evolucao', { p: produto.charAt(0).toUpperCase() + produto.slice(1), c: labelCeasa(primaria) })}</h3>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={serie}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--cinza-claro)" />
              <XAxis dataKey="data_coleta" tickFormatter={formatarData} tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => `R$${v}`} />
              <Tooltip
                formatter={(value, name) => [fmtBRL(Number(value ?? 0)), name]}
                labelFormatter={(label) => t('dataLabel', { d: formatarData(String(label)) })}
              />
              <Legend />
              <Line type="monotone" dataKey="preco_medio" name={t('precoMedio')} stroke={CHART_CEO} strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="preco_min" name={t('minimo')} stroke={CHART_VERDE} strokeWidth={1} strokeDasharray="4 2" dot={false} />
              <Line type="monotone" dataKey="preco_max" name={t('maximo')} stroke={CHART_TERRA} strokeWidth={1} strokeDasharray="4 2" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {!analise && !carregando && !erro && produtos.length === 0 && (
        <div style={{ textAlign: 'center', padding: '48px 20px', color: 'var(--texto-suave)' }}>
          <p style={{ fontSize: 40, margin: 0 }}>🛒</p>
          <p style={{ marginTop: 12, fontFamily: 'Inter, sans-serif', fontSize: 17, color: 'var(--texto)' }}>
            {t('vazioTitulo')}
          </p>
          <p style={{ fontSize: 13, marginTop: 4 }}>{t('vazioSub')}</p>
        </div>
      )}
    </div>
  )
}

const thStyle: CSSProperties = {
  padding: '10px 12px', textAlign: 'left', fontWeight: 700, fontSize: 12,
  borderBottom: '2px solid var(--verde-claro)',
}
const tdStyle: CSSProperties = { padding: '9px 12px', color: 'var(--texto)' }
