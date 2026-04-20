import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://rsphlvcekuomvpvjqxqm.supabase.co'
const supabaseKey = import.meta.env.VITE_SUPABASE_ANON_KEY || ''

export const supabase = createClient(supabaseUrl, supabaseKey)

export async function queryItensAgro(filters?: {
  cultura?: string
  canal?: string
  offset?: number
  limit?: number
}) {
  let query = supabase
    .from('vw_itens_agro')
    .select('*')

  if (filters?.cultura && filters.cultura !== 'Todas') {
    query = query.eq('cultura', filters.cultura)
  }
  if (filters?.canal && filters.canal !== 'Todas') {
    query = query.eq('canal', filters.canal)
  }

  const offset = filters?.offset || 0
  const limit = filters?.limit || 20

  const { data, error } = await query
    .range(offset, offset + limit - 1)
    .order('dt_abertura', { ascending: false })

  return { data, error }
}

export async function getTopCulturas() {
  const { data, error } = await supabase
    .from('vw_itens_agro')
    .select('cultura, valor_total')
    .order('valor_total', { ascending: false })
    .limit(10)

  return { data, error }
}

export async function getDemandaPorAno() {
  const { data, error } = await supabase
    .from('vw_itens_agro')
    .select('dt_abertura, valor_total')
    .order('dt_abertura')

  return { data, error }
}

export async function getTopFornecedores() {
  const { data, error } = await supabase
    .from('fornecedores')
    .select('nome, id')
    .limit(5)

  return { data, error }
}

export async function getCulturas() {
  const { data, error } = await supabase
    .from('vw_itens_agro')
    .select('cultura')
    .order('cultura')

  if (data) {
    const unique = Array.from(new Set(data.map((x: any) => x.cultura).filter(Boolean)))
    return { data: unique.map((cultura) => ({ cultura })), error }
  }

  return { data, error }
}

export async function getCanais() {
  const { data, error } = await supabase
    .from('vw_itens_agro')
    .select('canal')
    .order('canal')

  if (data) {
    const unique = Array.from(new Set(data.map((x: any) => x.canal).filter(Boolean)))
    return { data: unique.map((canal) => ({ canal })), error }
  }

  return { data, error }
}
