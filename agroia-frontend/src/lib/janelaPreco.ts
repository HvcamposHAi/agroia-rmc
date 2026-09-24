/**
 * Janela de período da Consulta de Mercado (cliente).
 *
 * A série diária (v_prohort_serie_diaria) já traz min/médio/máx por dia; qualquer
 * janela (hoje, semana, N dias, custom) é recortada e agregada aqui no front — sem
 * refetch e sem alteração de banco. Funções puras → testáveis isoladamente.
 *
 * data_coleta é 'yyyy-mm-dd' (ISO ordena lexicograficamente → comparação por string).
 */

export interface PontoSerie {
  data_coleta: string
  preco_medio: number
  preco_min: number
  preco_max: number
  unidade: string | null
}

export interface JanelaAgg {
  min: number | null
  media: number | null
  max: number | null
  unidade: string | null
  n: number
}

import type { Lang } from '../i18n'

// value é string: 'hoje' (último dia), 'N' (últimos N dias) ou 'custom' (faixa livre).
// `label` (pt) mantido por compatibilidade; `labels` traz o rótulo em cada idioma.
export const PERIODOS = [
  { value: 'hoje',   label: 'Hoje',                  labels: { pt: 'Hoje', en: 'Today', es: 'Hoy' } },
  { value: '7',      label: 'Última semana',         labels: { pt: 'Última semana', en: 'Last week', es: 'Última semana' } },
  { value: '30',     label: '30 dias',               labels: { pt: '30 dias', en: '30 days', es: '30 días' } },
  { value: '60',     label: '60 dias',               labels: { pt: '60 dias', en: '60 days', es: '60 días' } },
  { value: '90',     label: '90 dias',               labels: { pt: '90 dias', en: '90 days', es: '90 días' } },
  { value: '180',    label: '6 meses',               labels: { pt: '6 meses', en: '6 months', es: '6 meses' } },
  { value: '365',    label: '12 meses',              labels: { pt: '12 meses', en: '12 months', es: '12 meses' } },
  { value: '730',    label: '24 meses',              labels: { pt: '24 meses', en: '24 months', es: '24 meses' } },
  { value: 'custom', label: 'Período personalizado', labels: { pt: 'Período personalizado', en: 'Custom period', es: 'Período personalizado' } },
] as const

const TXT_PERIODO: Record<Lang, string> = { pt: 'período', en: 'period', es: 'período' }
const TXT_DIAS: Record<Lang, string> = { pt: 'dias', en: 'days', es: 'días' }

/** Rótulo do período (opção do seletor) no idioma pedido. */
export function rotuloPeriodo(value: string, lang: Lang = 'pt'): string {
  const p = PERIODOS.find((x) => x.value === value)
  return p ? p.labels[lang] : `${value} ${TXT_DIAS[lang]}`
}

// Subtrai `dias` de uma data ISO 'yyyy-mm-dd' e devolve ISO.
export function isoMenosDias(iso: string, dias: number): string {
  const dt = new Date(iso + 'T00:00:00')
  dt.setDate(dt.getDate() - dias)
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`
}

// Recorta a série conforme o período. Âncora = última data DISPONÍVEL na série
// (robusto à defasagem da fonte: "hoje" = dia mais recente coletado, não Date.now()).
export function recortarJanela(serie: PontoSerie[], periodo: string, de: string, ate: string): PontoSerie[] {
  if (serie.length === 0) return serie
  const maxData = serie[serie.length - 1].data_coleta   // série vem ordenada asc
  if (periodo === 'custom') {
    // datas invertidas → troca; vazias → limites da própria série.
    let ini = de || serie[0].data_coleta
    let fim = ate || maxData
    if (ini > fim) { const t = ini; ini = fim; fim = t }
    return serie.filter((p) => p.data_coleta >= ini && p.data_coleta <= fim)
  }
  if (periodo === 'hoje') {
    return serie.filter((p) => p.data_coleta === maxData)
  }
  const n = Number(periodo) || 30
  const cutoff = isoMenosDias(maxData, n - 1)
  return serie.filter((p) => p.data_coleta >= cutoff)
}

// Agrega min/médio/máx sobre os pontos recortados.
export function agregarJanela(pts: PontoSerie[]): JanelaAgg {
  if (pts.length === 0) return { min: null, media: null, max: null, unidade: null, n: 0 }
  let min = Infinity, max = -Infinity, soma = 0
  for (const p of pts) {
    if (p.preco_min < min) min = p.preco_min
    if (p.preco_max > max) max = p.preco_max
    soma += p.preco_medio
  }
  return { min, media: soma / pts.length, max, unidade: pts[pts.length - 1].unidade, n: pts.length }
}

// Rótulo curto do período para os sublabels dos cards (lang opcional; padrão pt).
export function labelPeriodo(periodo: string, de: string, ate: string, pts: PontoSerie[], lang: Lang = 'pt'): string {
  if (periodo === 'custom') {
    const fmt = (d: string) => { const x = new Date(d + 'T00:00:00'); return `${String(x.getDate()).padStart(2, '0')}/${String(x.getMonth() + 1).padStart(2, '0')}` }
    const ini = de || pts[0]?.data_coleta
    const fim = ate || pts[pts.length - 1]?.data_coleta
    return ini && fim ? `${fmt(ini)}–${fmt(fim)}` : TXT_PERIODO[lang]
  }
  return rotuloPeriodo(periodo, lang)
}
