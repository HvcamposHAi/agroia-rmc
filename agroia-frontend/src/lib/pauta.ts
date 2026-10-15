import { apiClient } from './apiClient'

/**
 * Pauta do Sacolão e planejamento de safra (plano v3, E8): chamadas às rotas só de
 * leitura /pauta/* da API e funções puras de apresentação. Arquivo novo — apiClient.ts
 * não muda.
 */

export interface MesSazonal {
  mes: number
  indice: number | null
  anos: number
  confiavel: boolean
}

export interface SafraSazonal {
  produto: string
  ceasa: string
  unidade: string
  fonte: string
  periodo: { inicio: string; fim: string }
  meses: MesSazonal[]
  consultado_em: string
}

export interface CeasaRanking {
  ceasa: string
  mediana: number
  cotacoes: number
  ultima_data: string
}

export interface SafraComparar {
  produto: string
  unidade: string
  ranking: CeasaRanking[]
  excluidas: { ceasa: string; motivo: string }[]
  fonte: string
  consultado_em: string
}

export async function getSafraSazonal(produto: string, ceasa: string): Promise<SafraSazonal> {
  const r = await apiClient.get<SafraSazonal>('/pauta/safra/sazonal', { params: { produto, ceasa } })
  return r.data
}

export async function getSafraComparar(produto: string): Promise<SafraComparar> {
  const r = await apiClient.get<SafraComparar>('/pauta/safra/comparar', { params: { produto } })
  return r.data
}

/** Produtos e CEASAs aceitos pelas rotas de safra (mesma lista fechada da API). */
export async function getCatalogoProhort(): Promise<{ produtos: string[]; ceasas: string[] }> {
  try {
    const r = await apiClient.get<{ produtos: string[]; ceasas: string[] }>('/pauta/safra/catalogo')
    return { produtos: r.data.produtos, ceasas: r.data.ceasas }
  } catch {
    return { produtos: [], ceasas: [] }
  }
}

/** Faixa do índice sazonal: ≥ 5% acima da média do ano = alta; ≥ 5% abaixo = baixa. */
export type FaixaSazonal = 'alta' | 'baixa' | 'normal' | 'sem_dado'

export function faixaSazonal(indice: number | null, margem = 0.05): FaixaSazonal {
  if (indice === null) return 'sem_dado'
  if (indice >= 1 + margem) return 'alta'
  if (indice <= 1 - margem) return 'baixa'
  return 'normal'
}

/** Diferença percentual de uma mediana contra a de referência (Curitiba). */
export function diferencaPct(valor: number, referencia: number | undefined): number | null {
  if (!referencia) return null
  return (valor / referencia - 1) * 100
}

/** 'AAAA-MM-DD' → Date ao meio-dia local (new Date('AAAA-MM-DD') é meia-noite UTC: dia anterior no Brasil). */
export function dataIso(iso: string): Date {
  return new Date(`${iso.slice(0, 10)}T12:00:00`)
}

export function rotuloProduto(p: string): string {
  return p.charAt(0).toUpperCase() + p.slice(1)
}

export function rotuloCeasa(c: string): string {
  return c.toLowerCase().replace(/(^|\s)\S/g, (s) => s.toUpperCase())
}
