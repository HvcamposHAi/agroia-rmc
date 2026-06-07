/**
 * Fonte ÚNICA dos itens agrícolas (vw_itens_agro) para o frontend.
 *
 * Antes, Home/Demanda/Dashboard/Consultas buscavam a view em pontos separados,
 * com caches distintos e regras de `.limit()` divergentes (algumas com limit 1000,
 * outras sem) — o que faria os números (valor, itens, culturas) divergirem entre
 * telas assim que a base passasse de 1000 linhas (teto do PostgREST).
 *
 * Aqui centralizamos: um único cache, ordenação fixa e paginação por `.range()`
 * em loop, de modo que TODAS as superfícies derivem do mesmo array completo.
 *
 * NOTA: vw_itens_agro já retorna apenas relevante_agro = true (filtro na view).
 */
import { supabase } from './supabaseClient'
import { getCache, setCache } from './sessionCache'

export const ITENS_AGRO_KEY = 'itens_agro_v2'

const PAGE = 1000
const MAX_PAGES = 20 // teto rígido de segurança: até 20k linhas (evita loop infinito)

/** Linha bruta da view. Campos opcionais pois nem toda tela usa todos. */
export interface ItemAgro {
  id: number
  processo?: string
  descricao?: string
  cultura?: string
  canal?: string
  categoria_v2?: string
  valor_total?: number
  qt_solicitada?: number
  dt_abertura?: string
  [key: string]: unknown
}

export interface KpisAgro {
  valor: number
  itens: number
  culturas: number
  licitacoes: number
}

/**
 * Busca TODOS os itens agrícolas (paginado), com cache de sessão compartilhado.
 * Retorna sempre o conjunto completo — sem truncamento silencioso.
 */
export async function fetchItensAgro(): Promise<ItemAgro[]> {
  const cached = getCache<ItemAgro[]>(ITENS_AGRO_KEY)
  if (cached) return cached

  const out: ItemAgro[] = []
  let failed = false
  for (let page = 0; page < MAX_PAGES; page++) {
    const from = page * PAGE
    const { data, error } = await supabase
      .from('vw_itens_agro')
      .select('*')
      .order('dt_abertura', { ascending: false })
      .range(from, from + PAGE - 1)

    if (error) {
      // Falha de rede/permissão: devolve o que já temos (não quebra a tela) e
      // NÃO cacheia, para que a próxima montagem tente de novo.
      console.warn('[fetchItensAgro] erro ao paginar vw_itens_agro:', error.message)
      failed = true
      break
    }
    const rows = (data ?? []) as ItemAgro[]
    out.push(...rows)
    if (rows.length < PAGE) break // última página
    if (page === MAX_PAGES - 1) {
      console.warn(`[fetchItensAgro] teto de ${MAX_PAGES} páginas atingido — dados podem estar incompletos`)
    }
  }

  if (!failed) setCache(ITENS_AGRO_KEY, out)
  return out
}

/** Calcula os KPIs a partir de um conjunto de linhas (fonte única de cálculo). */
export function kpisFromRows(rows: ItemAgro[]): KpisAgro {
  return {
    valor: rows.reduce((s, r) => s + (r.valor_total ?? 0), 0),
    itens: rows.length,
    culturas: new Set(rows.map(r => r.cultura).filter(Boolean)).size,
    licitacoes: new Set(rows.map(r => r.processo).filter(Boolean)).size,
  }
}
