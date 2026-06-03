import { useState, useEffect, useCallback, useRef } from 'react'
import { createClient } from '@supabase/supabase-js'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { SemaforoPreco } from '../components/SemaforoPreco'
import type { SemaforoCor } from '../components/SemaforoPreco'
import ResponseRenderer from '../components/ResponseRenderer'
import { streamPost } from '../lib/apiClient'
import type { SSEEvent } from '../lib/apiClient'

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

const CONV_SUGGESTIONS = [
  '🍅 Tomate, alface e cenoura — como estão os preços?',
  '📈 Quais produtos estão com melhor preço esta semana?',
  '🥔 Vale a pena vender batata agora?',
  '🧺 Quero vender repolho, couve e beterraba. Quanto pedir?',
]

// Cores das linhas do gráfico (recharts exige string de cor)
const CHART_VERDE = '#3a7d44'
const CHART_TERRA = '#8b5e3c'
const CHART_CEO   = '#4a9eda'

const fmtBRL = (v: number | null | undefined) =>
  v == null ? 'N/D' : `R$ ${v.toFixed(2).replace('.', ',')}`

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

// Réplica EXATA da fórmula do backend (chat/tools.py :: _prohort_preco_sugerido)
// para que o card "Sugerido" mostre o mesmo valor que o chat de preços.
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
  return Math.round(base * 100) / 100
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

  // Acompanha o fim SÓ se o usuário já estava no fim — rola apenas o container interno.
  useEffect(() => {
    const el = messagesRef.current
    if (el && atBottomRef.current) el.scrollTop = el.scrollHeight
  }, [convMsgs, convStatus])

  const enviarConversa = useCallback(async (texto: string) => {
    const msg = texto.trim()
    if (!msg || convLoading) return
    const labelCeasa = CEASAS.find((c) => c.value === ceasa)?.label ?? ceasa
    const historico = convMsgs.slice(-6)
    atBottomRef.current = true   // ao enviar, acompanha a própria pergunta/resposta na caixa
    setConvMsgs((p) => [...p, { role: 'user', content: msg }, { role: 'assistant', content: '' }])
    setConvInput('')
    setConvLoading(true)
    setConvStatus('🔍 Consultando preços...')
    try {
      const pergunta = `[CEASA de referência: ${labelCeasa} (${ceasa})]\n${msg}`
      let full = ''
      for await (const ev of streamPost<SSEEvent>('/prohort/chat/stream', { pergunta, historico })) {
        if (ev.tipo === 'status') setConvStatus(ev.msg || '⏳ Processando...')
        else if (ev.tipo === 'token') {
          full += ev.texto || ''
          setConvMsgs((p) => { const u = [...p]; u[u.length - 1].content = full; return u })
        } else if (ev.tipo === 'fim') setConvStatus('')
      }
    } catch {
      setConvMsgs((p) => {
        const u = [...p]
        u[u.length - 1].content = '⚠️ Não foi possível consultar agora. Verifique se o servidor está ativo e tente novamente.'
        return u
      })
    } finally {
      setConvLoading(false)
      setConvStatus('')
    }
  }, [convMsgs, convLoading, ceasa])

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

  const consultar = useCallback(async (prodArg?: string) => {
    const prod = (prodArg ?? produto).trim()
    if (!prod) return
    if (prodArg !== undefined) setProduto(prodArg)
    setCarregando(true)
    setErro(null)
    try {
      const termo = prod.toLowerCase()
      const [{ data: aData, error: aErr }, { data: sData, error: sErr }] = await Promise.all([
        supabase.from('v_prohort_analise').select('*')
          .ilike('produto_norm', `%${termo}%`).eq('ceasa', ceasa)
          .order('total_cotacoes', { ascending: false }).limit(1),
        supabase.from('v_prohort_serie_diaria')
          .select('data_coleta, preco_medio, preco_min, preco_max, unidade')
          .ilike('produto_norm', `%${termo}%`).eq('ceasa', ceasa)
          .order('data_coleta', { ascending: true }),
      ])
      if (aErr || sErr) throw new Error((aErr ?? sErr)?.message ?? 'Erro na consulta')
      if (!aData || aData.length === 0) {
        setAnalise(null); setSerie([])
        setErro(`Produto "${prod}" não encontrado na CEASA ${ceasa}. Escolha um da lista abaixo.`)
        return
      }
      setAnalise(aData[0] as Analise)
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
  const sugerido = analise ? precoSugerido(analise) : null
  const unidade = analise?.unidade || 'kg'

  return (
    <div className="page">
      {/* Cabeçalho */}
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontFamily: 'Fraunces, serif', fontSize: 22, fontWeight: 700, color: 'var(--texto)', margin: 0 }}>
          Preços de Mercado — CEASAs
        </h2>
        <p style={{ fontSize: 14, color: 'var(--texto-suave)', marginTop: 6 }}>
          Dados oficiais PROHORT/CONAB · atacado · atualização diária
        </p>
      </div>

      {/* ── Assistente conversacional de preços (IA) — destaque ───────────── */}
      <div className="chart-card" style={{ margin: '0 0 24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 14 }}>
          <h3 style={{ margin: 0 }}>💬 Pergunte sobre preços</h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 13, color: 'var(--texto-suave)', fontWeight: 600 }}>CEASA:</span>
            <select className="filter-select" value={ceasa} onChange={(e) => setCeasa(e.target.value)}>
              {CEASAS.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
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
                <div
                  key={i}
                  className={`msg ${m.role}`}
                  style={m.role === 'assistant' ? { maxWidth: '100%' } : undefined}
                >
                  <div className="msg-avatar">{m.role === 'assistant' ? '🌾' : '👤'}</div>
                  <div className="msg-bubble" style={m.role === 'assistant' ? { maxWidth: '100%', width: '100%' } : undefined}>
                    {m.role === 'assistant'
                      ? (m.content
                          ? <ResponseRenderer content={m.content} />
                          : <span style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                              <span className="spinner" />
                              <span style={{ color: 'var(--texto-suave)', fontSize: 13 }}>{convStatus || 'Processando...'}</span>
                            </span>)
                      : m.content}
                  </div>
                </div>
              ))}
            </div>

            {mostrarIrFim && (
              <button
                onClick={irParaFim}
                title="Ir para o fim"
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

        {/* Sugestões (estado inicial) */}
        {convMsgs.length === 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 14 }}>
            {CONV_SUGGESTIONS.map((s) => (
              <button key={s} className="suggestion-btn" onClick={() => enviarConversa(s.replace(/^[^\s]+\s/, ''))}>
                {s}
              </button>
            ))}
          </div>
        )}

        {/* Entrada */}
        <div className="chat-input-wrapper">
          <input
            className="chat-input"
            value={convInput}
            onChange={(e) => setConvInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') enviarConversa(convInput) }}
            placeholder="Ex: tomate, alface e cenoura — quanto pedir?"
            disabled={convLoading}
          />
          <button className="send-btn" onClick={() => enviarConversa(convInput)} disabled={convLoading || !convInput.trim()}>
            <svg viewBox="0 0 24 24"><path d="M2 21l21-9L2 3v7l15 2-15 2v7z" /></svg>
          </button>
        </div>
        <p style={{ fontSize: 11, color: 'var(--texto-suave)', marginTop: 8 }}>
          Traga sua lista de produtos. A IA responde com preço mínimo, médio, máximo e sugerido · Fonte: CONAB/PROHORT
        </p>
      </div>

      {/* ── Consulta detalhada por produto ───────────────────────────────── */}
      <h3 style={{ fontFamily: 'Fraunces, serif', fontSize: 17, fontWeight: 700, color: 'var(--texto)', margin: '0 0 12px' }}>
        Consulta detalhada por produto
      </h3>

      <div className="filters-bar" style={{ marginBottom: 16 }}>
        <input
          className="search-input"
          list="lista-produtos"
          value={produto}
          onChange={(e) => setProduto(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') consultar() }}
          placeholder="🔎 Digite ou escolha um produto..."
        />
        <datalist id="lista-produtos">
          {produtos.map((p) => <option key={p} value={p} />)}
        </datalist>

        <select className="filter-select" value={ceasa} onChange={(e) => setCeasa(e.target.value)}>
          {CEASAS.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>

        <select className="filter-select" value={periodo} onChange={(e) => setPeriodo(Number(e.target.value))}>
          {PERIODOS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
        </select>

        <button
          onClick={() => consultar()}
          disabled={!produto || carregando}
          style={{
            background: produto && !carregando ? 'var(--verde)' : 'var(--borda)',
            color: '#fff', border: 'none', borderRadius: 10, padding: '9px 22px',
            fontFamily: 'Nunito, sans-serif', fontWeight: 700, fontSize: 14,
            cursor: produto && !carregando ? 'pointer' : 'not-allowed',
          }}
        >
          {carregando ? 'Consultando...' : 'Consultar'}
        </button>

        {produtos.length > 0 && (
          <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--texto-suave)', fontWeight: 600 }}>
            {produtos.length} produtos
          </span>
        )}
      </div>

      {erro && (
        <div style={{ padding: '12px 16px', background: '#fee2e2', borderRadius: 10, color: '#dc2626', marginBottom: 16, fontSize: 14 }}>
          {erro}
        </div>
      )}

      {/* Chips de produtos disponíveis (ajuda a escolher) */}
      {produtos.length > 0 && !analise && (
        <div style={{ marginBottom: 24 }}>
          <p style={{ fontSize: 13, color: 'var(--texto-suave)', fontWeight: 600, margin: '0 0 10px' }}>
            Produtos disponíveis na CEASA {ceasa}:
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
          <div className="metrics-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', marginBottom: 16 }}>
            <div className="metric-card verde">
              <span className="metric-icon">⬇️</span>
              <div className="metric-label">Preço Mínimo</div>
              <div className="metric-value">{fmtBRL(analise.min_30d)}</div>
              <div className="metric-sub">/{unidade} · 30 dias</div>
            </div>
            <div className="metric-card ceu">
              <span className="metric-icon">📊</span>
              <div className="metric-label">Preço Médio</div>
              <div className="metric-value">{fmtBRL(analise.media_30d)}</div>
              <div className="metric-sub">/{unidade} · 30 dias</div>
            </div>
            <div className="metric-card terra">
              <span className="metric-icon">⬆️</span>
              <div className="metric-label">Preço Máximo</div>
              <div className="metric-value">{fmtBRL(analise.max_30d)}</div>
              <div className="metric-sub">/{unidade} · 30 dias</div>
            </div>
            <div className="metric-card amarelo">
              <span className="metric-icon">🎯</span>
              <div className="metric-label">Preço Sugerido</div>
              <div className="metric-value">{fmtBRL(sugerido)}</div>
              <div className="metric-sub">/{unidade} · referência de venda</div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', marginBottom: 24 }}>
            {semaforo && <SemaforoPreco semaforo={semaforo.cor} texto={semaforo.texto} />}
            {analise.variacao_semanal_pct != null && (
              <span style={{
                fontSize: 13, fontWeight: 700,
                color: analise.variacao_semanal_pct > 0 ? '#dc2626'
                  : analise.variacao_semanal_pct < 0 ? 'var(--verde)' : 'var(--texto-suave)',
              }}>
                {analise.variacao_semanal_pct > 0 ? '▲' : analise.variacao_semanal_pct < 0 ? '▼' : '▬'}{' '}
                {analise.variacao_semanal_pct > 0 ? '+' : ''}{analise.variacao_semanal_pct.toFixed(1)}% na semana
              </span>
            )}
            <span style={{ fontSize: 12, color: 'var(--texto-suave)' }}>
              Última cotação: {analise.ultima_cotacao ?? 'N/D'} · Fonte: CONAB/PROHORT
            </span>
          </div>
        </>
      )}

      {serie.length > 0 && (
        <div className="chart-card">
          <h3>Evolução do Preço — {produto.charAt(0).toUpperCase() + produto.slice(1)} / CEASA {ceasa}</h3>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={serie}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--cinza-claro)" />
              <XAxis dataKey="data_coleta" tickFormatter={formatarData} tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => `R$${v}`} />
              <Tooltip
                formatter={(value, name) => [`R$ ${Number(value ?? 0).toFixed(2)}`, name]}
                labelFormatter={(label) => `Data: ${formatarData(String(label))}`}
              />
              <Legend />
              <Line type="monotone" dataKey="preco_medio" name="Preço Médio" stroke={CHART_CEO} strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="preco_min" name="Mínimo" stroke={CHART_VERDE} strokeWidth={1} strokeDasharray="4 2" dot={false} />
              <Line type="monotone" dataKey="preco_max" name="Máximo" stroke={CHART_TERRA} strokeWidth={1} strokeDasharray="4 2" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {!analise && !carregando && !erro && produtos.length === 0 && (
        <div style={{ textAlign: 'center', padding: '48px 20px', color: 'var(--texto-suave)' }}>
          <p style={{ fontSize: 40, margin: 0 }}>🛒</p>
          <p style={{ marginTop: 12, fontFamily: 'Fraunces, serif', fontSize: 17, color: 'var(--texto)' }}>
            Selecione um produto e uma CEASA para ver os detalhes
          </p>
          <p style={{ fontSize: 13, marginTop: 4 }}>Dados do PROHORT/CONAB · atualizados diariamente</p>
        </div>
      )}
    </div>
  )
}
