import { useState, useEffect, useCallback } from 'react'
import type { CSSProperties } from 'react'
import { createClient } from '@supabase/supabase-js'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { SemaforoPreco } from '../components/SemaforoPreco'
import type { SemaforoCor } from '../components/SemaforoPreco'

// Lê as views PROHORT diretamente do Supabase (mesmo padrão do Dashboard).
const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL ?? '',
  import.meta.env.VITE_SUPABASE_ANON_KEY ?? ''
)

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
}

interface PontoSerie {
  data_coleta: string
  preco_medio: number
  preco_min: number
  preco_max: number
  unidade: string | null
}

const CEASAS = [
  { value: 'CURITIBA',  label: 'CEASA Curitiba/PR (RMC)' },
  { value: 'MARINGA',   label: 'CEASA Maringá/PR' },
  { value: 'SAO PAULO', label: 'CEAGESP São Paulo/SP' },
]

const PERIODOS = [
  { value: 30, label: '30 dias' },
  { value: 60, label: '60 dias' },
  { value: 90, label: '90 dias' },
]

const COR_VERDE = '#3a7d44'
const COR_TERRA = '#8b5e3c'
const COR_CEO   = '#4a9eda'
const COR_BG    = '#fffdf9'

function calcularSemaforo(a: Analise): { cor: SemaforoCor; texto: string } {
  const m30 = a.media_30d
  const m90 = a.media_90d
  if (m30 != null && m90 != null && m90 > 0) {
    const desvio = ((m30 - m90) / m90) * 100
    if (desvio < -10) return { cor: 'verde', texto: 'Preço abaixo da média histórica' }
    if (desvio > 10)  return { cor: 'vermelho', texto: 'Preço acima da média histórica' }
    return { cor: 'amarelo', texto: 'Preço dentro da média histórica' }
  }
  return { cor: 'cinza', texto: 'Histórico insuficiente' }
}

export default function Mercado() {
  const [produtos, setProdutos]     = useState<string[]>([])
  const [produto, setProduto]       = useState('')
  const [ceasa, setCeasa]           = useState('CURITIBA')
  const [periodo, setPeriodo]       = useState(30)
  const [analise, setAnalise]       = useState<Analise | null>(null)
  const [serie, setSerie]           = useState<PontoSerie[]>([])
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro]             = useState<string | null>(null)

  // Lista de produtos disponíveis ao mudar CEASA
  useEffect(() => {
    let ativo = true
    supabase
      .from('v_prohort_analise')
      .select('produto_norm')
      .eq('ceasa', ceasa)
      .then(({ data }) => {
        if (!ativo) return
        const unicos = Array.from(
          new Set((data ?? []).map((r: { produto_norm: string }) => r.produto_norm).filter(Boolean))
        ).sort()
        setProdutos(unicos)
      })
    return () => { ativo = false }
  }, [ceasa])

  const consultar = useCallback(async () => {
    if (!produto) return
    setCarregando(true)
    setErro(null)
    try {
      const [{ data: aData, error: aErr }, { data: sData, error: sErr }] = await Promise.all([
        supabase.from('v_prohort_analise').select('*')
          .ilike('produto_norm', `%${produto.toLowerCase()}%`).eq('ceasa', ceasa).limit(1),
        supabase.from('v_prohort_serie_diaria')
          .select('data_coleta, preco_medio, preco_min, preco_max, unidade')
          .ilike('produto_norm', `%${produto.toLowerCase()}%`).eq('ceasa', ceasa)
          .order('data_coleta', { ascending: true }),
      ])
      if (aErr || sErr) throw new Error((aErr ?? sErr)?.message ?? 'Erro na consulta')
      if (!aData || aData.length === 0) {
        setAnalise(null); setSerie([])
        setErro(`Produto "${produto}" não encontrado na CEASA ${ceasa}.`)
        return
      }
      setAnalise(aData[0] as Analise)
      // recorta os últimos N dias da série
      const todos = (sData ?? []) as PontoSerie[]
      setSerie(todos.slice(Math.max(0, todos.length - periodo)))
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : 'Erro desconhecido')
      setAnalise(null); setSerie([])
    } finally {
      setCarregando(false)
    }
  }, [produto, ceasa, periodo])

  const formatarData = (d: string) => {
    const dt = new Date(d + 'T00:00:00')
    return `${dt.getDate().toString().padStart(2, '0')}/${(dt.getMonth() + 1).toString().padStart(2, '0')}`
  }

  const semaforo = analise ? calcularSemaforo(analise) : null

  return (
    <div style={{ padding: '24px', backgroundColor: COR_BG, minHeight: '100vh', fontFamily: 'Nunito, sans-serif' }}>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '1.6rem', color: COR_VERDE, fontFamily: 'Fraunces, serif', margin: 0 }}>
          Preços de Mercado — CEASAs
        </h1>
        <p style={{ color: '#6b7280', marginTop: '4px', fontSize: '0.9rem' }}>
          Dados oficiais PROHORT/CONAB · atacado · atualização diária
        </p>
      </div>

      {/* Filtros */}
      <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '24px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', minWidth: '220px' }}>
          <label style={labelStyle}>Produto</label>
          <input
            list="lista-produtos"
            value={produto}
            onChange={(e) => setProduto(e.target.value)}
            placeholder="Ex: tomate, alface..."
            style={inputStyle}
          />
          <datalist id="lista-produtos">
            {produtos.map((p) => <option key={p} value={p} />)}
          </datalist>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <label style={labelStyle}>CEASA</label>
          <select value={ceasa} onChange={(e) => setCeasa(e.target.value)} style={inputStyle}>
            {CEASAS.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
          </select>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <label style={labelStyle}>Período</label>
          <select value={periodo} onChange={(e) => setPeriodo(Number(e.target.value))} style={inputStyle}>
            {PERIODOS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'flex-end' }}>
          <button
            onClick={consultar}
            disabled={!produto || carregando}
            style={{
              padding: '10px 24px',
              backgroundColor: produto ? COR_VERDE : '#d1d5db',
              color: 'white', border: 'none', borderRadius: '8px',
              cursor: produto ? 'pointer' : 'not-allowed',
              fontFamily: 'Nunito, sans-serif', fontWeight: 700, fontSize: '0.95rem',
            }}
          >
            {carregando ? 'Consultando...' : 'Consultar'}
          </button>
        </div>
      </div>

      {erro && (
        <div style={{ padding: '12px 16px', backgroundColor: '#fee2e2', borderRadius: '8px', color: '#dc2626', marginBottom: '16px' }}>
          {erro}
        </div>
      )}

      {analise && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '16px', marginBottom: '24px' }}>
            <CardPreco titulo="Preço Mínimo" valor={analise.min_30d} unidade={analise.unidade} cor={COR_VERDE} />
            <CardPreco titulo="Preço Médio" valor={analise.media_30d} unidade={analise.unidade} cor={COR_CEO} destaque />
            <CardPreco titulo="Preço Máximo" valor={analise.max_30d} unidade={analise.unidade} cor={COR_TERRA} />
            <div style={cardStyle}>
              <span style={cardTituloStyle}>Variação Semanal</span>
              <span style={{
                fontSize: '1.6rem', fontWeight: 800,
                color: analise.variacao_semanal_pct != null
                  ? (analise.variacao_semanal_pct > 0 ? '#dc2626' : (analise.variacao_semanal_pct < 0 ? COR_VERDE : '#374151'))
                  : '#374151',
              }}>
                {analise.variacao_semanal_pct != null
                  ? `${analise.variacao_semanal_pct > 0 ? '+' : ''}${analise.variacao_semanal_pct.toFixed(1)}%`
                  : 'N/D'}
              </span>
            </div>
          </div>

          {semaforo && (
            <div style={{ marginBottom: '24px' }}>
              <SemaforoPreco semaforo={semaforo.cor} texto={semaforo.texto} />
              <span style={{ marginLeft: '12px', fontSize: '0.8rem', color: '#9ca3af' }}>
                Última cotação: {analise.ultima_cotacao ?? 'N/D'} · Fonte: CONAB/PROHORT
              </span>
            </div>
          )}
        </>
      )}

      {serie.length > 0 && (
        <div style={{ backgroundColor: 'white', borderRadius: '12px', padding: '24px', boxShadow: '0 1px 4px rgba(0,0,0,0.06)', marginBottom: '24px' }}>
          <h3 style={{ margin: '0 0 16px', fontSize: '1rem', color: '#374151' }}>
            Evolução do Preço — {produto.charAt(0).toUpperCase() + produto.slice(1)} / CEASA {ceasa}
          </h3>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={serie}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
              <XAxis dataKey="data_coleta" tickFormatter={formatarData} tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => `R$${v}`} />
              <Tooltip
                formatter={(value, name) => [`R$ ${Number(value ?? 0).toFixed(2)}`, name]}
                labelFormatter={(label) => `Data: ${formatarData(String(label))}`}
              />
              <Legend />
              <Line type="monotone" dataKey="preco_medio" name="Preço Médio" stroke={COR_CEO} strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="preco_min" name="Mínimo" stroke={COR_VERDE} strokeWidth={1} strokeDasharray="4 2" dot={false} />
              <Line type="monotone" dataKey="preco_max" name="Máximo" stroke={COR_TERRA} strokeWidth={1} strokeDasharray="4 2" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {!analise && !carregando && !erro && (
        <div style={{ textAlign: 'center', padding: '60px 20px', color: '#9ca3af' }}>
          <p style={{ fontSize: '2.5rem', margin: 0 }}>🛒</p>
          <p style={{ marginTop: '12px', fontFamily: 'Fraunces, serif', fontSize: '1.1rem' }}>
            Selecione um produto e uma CEASA para consultar preços de atacado
          </p>
          <p style={{ fontSize: '0.85rem', marginTop: '4px' }}>
            Dados do PROHORT/CONAB · atualizados diariamente
          </p>
        </div>
      )}
    </div>
  )
}

function CardPreco({ titulo, valor, unidade, cor, destaque = false }: {
  titulo: string; valor: number | null; unidade: string | null; cor: string; destaque?: boolean
}) {
  return (
    <div style={{ ...cardStyle, border: destaque ? `2px solid ${cor}` : '1px solid #e5e7eb' }}>
      <span style={cardTituloStyle}>{titulo}</span>
      <span style={{ fontSize: '1.6rem', fontWeight: 800, color: cor }}>
        {valor != null ? `R$ ${valor.toFixed(2)}` : 'N/D'}
      </span>
      <span style={{ fontSize: '0.75rem', color: '#9ca3af' }}>/{unidade || 'kg'}</span>
    </div>
  )
}

const labelStyle: CSSProperties = { fontSize: '0.8rem', color: '#374151', fontWeight: 600 }

const cardTituloStyle: CSSProperties = {
  fontSize: '0.75rem', color: '#6b7280', fontWeight: 600, textTransform: 'uppercase',
}

const inputStyle: CSSProperties = {
  padding: '9px 12px', border: '1.5px solid #d1d5db', borderRadius: '8px',
  fontFamily: 'Nunito, sans-serif', fontSize: '0.9rem', color: '#111827',
  backgroundColor: 'white', outline: 'none', minWidth: '180px',
}

const cardStyle: CSSProperties = {
  backgroundColor: 'white', borderRadius: '12px', padding: '16px 20px',
  display: 'flex', flexDirection: 'column', gap: '4px',
  boxShadow: '0 1px 4px rgba(0,0,0,0.06)', border: '1px solid #e5e7eb',
}
