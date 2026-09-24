import { useEffect, useMemo, useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Cell,
} from 'recharts'
import ComparadorVivo from '../components/ComparadorVivo'
import { defineMessages, useT, fmtDataHora } from '../i18n'

const MSG = defineMessages({
  pt: {
    titulo: '⚡ Benchmark de Motores LLM',
    carregando: 'Carregando resultados agregados…',
    semDados: 'Dashboard agregado ainda sem dados.',
    rodeBenchmark: 'Rode o benchmark completo (offline ou via GitHub Actions) para preencher:',
    resultadosAgregados: '📈 Resultados agregados',
    resumoRun: '{reps} repetições × {n} perguntas · gerado em {data} · dados coletados offline',
    menorLatencia: 'Menor latência (p50)',
    menorCusto: 'Menor custo / 1k',
    maiorAf1: 'Maior AF@1',
    acertoFerramenta: '{pct}% acerto de ferramenta',
    maiorConsistencia: 'Maior consistência',
    comparacaoMotor: '📋 Comparação por motor',
    colMotor: 'Motor',
    colCusto: 'Custo/1k (US$)',
    colConsist: 'Consist.',
    colErro: 'Erro',
    baseline: ' (baseline)',
    notaSignif: 'Superescritos {sup} = melhora estatisticamente significativa (teste t pareado + Bonferroni, α=0,05) sobre o motor de índice correspondente. Baseline em negrito.',
    graficoLatencia: '⏱️ Latência p50 vs p95 (ms)',
    graficoAcuracia: '🎯 Acurácia de Ferramenta (AF@k)',
    graficoCusto: '💵 Custo por 1k consultas (US$)',
    custo1k: 'Custo/1k',
    graficoDominio: '🧭 Intra-domínio (A) vs Extra-domínio (B) — AF@1',
    conjuntoA: 'Conjunto A (intra)',
    conjuntoB: 'Conjunto B (extra)',
    porCategoria: '📊 AF@1 por categoria de pergunta',
    todasCategorias: 'Todas as categorias',
    cat_preco: 'Preço',
    cat_licitacao: 'Licitação',
    cat_edital: 'Edital',
    cat_geral: 'Geral',
    exemplos: '🔬 Exemplos qualitativos (perguntas onde os motores divergem)',
    todasClassif: 'Todas as classificações',
    cl_CORRETO: 'Correto',
    cl_PARCIAL: 'Parcial',
    cl_INCORRETO: 'Incorreto',
    cl_RECUSA: 'Recusa',
    colPergunta: 'Pergunta',
    colFerramenta: 'Ferramenta',
    colParametros: 'Parâmetros',
    colClassif: 'Classif.',
    colResposta: 'Resposta',
  },
  en: {
    titulo: '⚡ LLM Engine Benchmark',
    carregando: 'Loading aggregated results…',
    semDados: 'Aggregated dashboard has no data yet.',
    rodeBenchmark: 'Run the full benchmark (offline or via GitHub Actions) to populate it:',
    resultadosAgregados: '📈 Aggregated results',
    resumoRun: '{reps} repetitions × {n} questions · generated on {data} · data collected offline',
    menorLatencia: 'Lowest latency (p50)',
    menorCusto: 'Lowest cost / 1k',
    maiorAf1: 'Highest AF@1',
    acertoFerramenta: '{pct}% tool accuracy',
    maiorConsistencia: 'Highest consistency',
    comparacaoMotor: '📋 Comparison by engine',
    colMotor: 'Engine',
    colCusto: 'Cost/1k (USD)',
    colConsist: 'Consist.',
    colErro: 'Error',
    baseline: ' (baseline)',
    notaSignif: 'Superscripts {sup} = statistically significant improvement (paired t-test + Bonferroni, α=0.05) over the engine with the corresponding index. Baseline in bold.',
    graficoLatencia: '⏱️ Latency p50 vs p95 (ms)',
    graficoAcuracia: '🎯 Tool Accuracy (AF@k)',
    graficoCusto: '💵 Cost per 1k queries (USD)',
    custo1k: 'Cost/1k',
    graficoDominio: '🧭 In-domain (A) vs Out-of-domain (B) — AF@1',
    conjuntoA: 'Set A (in-domain)',
    conjuntoB: 'Set B (out-of-domain)',
    porCategoria: '📊 AF@1 by question category',
    todasCategorias: 'All categories',
    cat_preco: 'Price',
    cat_licitacao: 'Procurement',
    cat_edital: 'Tender notice',
    cat_geral: 'General',
    exemplos: '🔬 Qualitative examples (questions where engines diverge)',
    todasClassif: 'All classifications',
    cl_CORRETO: 'Correct',
    cl_PARCIAL: 'Partial',
    cl_INCORRETO: 'Incorrect',
    cl_RECUSA: 'Refusal',
    colPergunta: 'Question',
    colFerramenta: 'Tool',
    colParametros: 'Parameters',
    colClassif: 'Class.',
    colResposta: 'Answer',
  },
  es: {
    titulo: '⚡ Benchmark de Motores LLM',
    carregando: 'Cargando resultados agregados…',
    semDados: 'El panel agregado aún no tiene datos.',
    rodeBenchmark: 'Ejecute el benchmark completo (offline o vía GitHub Actions) para llenarlo:',
    resultadosAgregados: '📈 Resultados agregados',
    resumoRun: '{reps} repeticiones × {n} preguntas · generado el {data} · datos recopilados offline',
    menorLatencia: 'Menor latencia (p50)',
    menorCusto: 'Menor costo / 1k',
    maiorAf1: 'Mayor AF@1',
    acertoFerramenta: '{pct}% de acierto de herramienta',
    maiorConsistencia: 'Mayor consistencia',
    comparacaoMotor: '📋 Comparación por motor',
    colMotor: 'Motor',
    colCusto: 'Costo/1k (USD)',
    colConsist: 'Consist.',
    colErro: 'Error',
    baseline: ' (baseline)',
    notaSignif: 'Superíndices {sup} = mejora estadísticamente significativa (prueba t pareada + Bonferroni, α=0,05) sobre el motor del índice correspondiente. Baseline en negrita.',
    graficoLatencia: '⏱️ Latencia p50 vs p95 (ms)',
    graficoAcuracia: '🎯 Precisión de Herramienta (AF@k)',
    graficoCusto: '💵 Costo por 1k consultas (USD)',
    custo1k: 'Costo/1k',
    graficoDominio: '🧭 Intra-dominio (A) vs Extra-dominio (B) — AF@1',
    conjuntoA: 'Conjunto A (intra)',
    conjuntoB: 'Conjunto B (extra)',
    porCategoria: '📊 AF@1 por categoría de pregunta',
    todasCategorias: 'Todas las categorías',
    cat_preco: 'Precio',
    cat_licitacao: 'Licitación',
    cat_edital: 'Pliego',
    cat_geral: 'General',
    exemplos: '🔬 Ejemplos cualitativos (preguntas donde los motores divergen)',
    todasClassif: 'Todas las clasificaciones',
    cl_CORRETO: 'Correcto',
    cl_PARCIAL: 'Parcial',
    cl_INCORRETO: 'Incorrecto',
    cl_RECUSA: 'Rechazo',
    colPergunta: 'Pregunta',
    colFerramenta: 'Herramienta',
    colParametros: 'Parámetros',
    colClassif: 'Clasif.',
    colResposta: 'Respuesta',
  },
})

type ChaveMsg = keyof typeof MSG.pt
const CATEGORIAS = ['preco', 'licitacao', 'edital', 'geral'] as const
const CLASSIFICACOES = ['CORRETO', 'PARCIAL', 'INCORRETO', 'RECUSA'] as const

// ---------------------------------------------------------------------------
// Tipos do resultados.json (gerado por benchmark/benchmark_executor.py)
// ---------------------------------------------------------------------------
interface MotorResumo {
  motor: string
  rotulo: string
  baseline: boolean
  n: number
  latencia_p50_ms: number
  latencia_p95_ms: number
  latencia_media_ms: number
  custo_usd_1k: number
  af1_pct: number
  af2_pct: number
  af3_pct: number
  taxa_erro_pct: number
  af1_conjunto_A: number
  af1_conjunto_B: number
  consistencia: number | null
  significancia: { latencia?: string; af1?: string }
}

interface CategoriaResumo {
  motor: string
  categoria: string
  af1_pct: number
  latencia_p50_ms: number
}

interface Exemplo {
  questao_id: string
  pergunta: string
  motor: string
  rotulo: string
  tool_chamada: string | null
  parametros: Record<string, unknown>
  classificacao: 'CORRETO' | 'PARCIAL' | 'INCORRETO' | 'RECUSA'
  trecho: string
}

interface Resultados {
  versao: string
  run_id: string
  gerado_em: string
  n_repeticoes: number
  n_perguntas: number
  motores: MotorResumo[]
  por_categoria: CategoriaResumo[]
  exemplos_qualitativos: Exemplo[]
}

// Cores por motor (paleta do projeto — index.css).
const COR_MOTOR: Record<string, string> = {
  claude: '#334155',      // slate (--verde)
  gemini: '#1e3a5f',      // navy (--ceu)
  groq_llama: '#0f766e',  // teal (--teal)
  maritaca: '#b45309',    // amber (--amarelo)
}
const COR_PADRAO = '#64748b'

const CLASSIF_CFG: Record<string, { bg: string; cor: string; borda: string }> = {
  CORRETO: { bg: '#e6f2f1', cor: '#0f766e', borda: '#9fcdc8' },
  PARCIAL: { bg: '#fff7ed', cor: '#c2410c', borda: '#fdba74' },
  INCORRETO: { bg: '#fef2f2', cor: '#b91c1c', borda: '#fca5a5' },
  RECUSA: { bg: '#eef2f7', cor: '#475569', borda: '#cbd5e1' },
}

const corDe = (m: string) => COR_MOTOR[m] ?? COR_PADRAO
const fmtData = (iso: string) => {
  try { return fmtDataHora(iso) } catch { return iso }
}

export default function BenchmarkMotores() {
  const t = useT(MSG)
  const rotuloCat = (c: string) => t(`cat_${c}` as ChaveMsg)
  const rotuloClassif = (c: string) =>
    (CLASSIFICACOES as readonly string[]).includes(c) ? t(`cl_${c}` as ChaveMsg) : c
  const [dados, setDados] = useState<Resultados | null>(null)
  const [erro, setErro] = useState('')
  const [carregando, setCarregando] = useState(true)
  const [filCategoria, setFilCategoria] = useState('todas')
  const [filConjunto, setFilConjunto] = useState('todos')

  useEffect(() => {
    // JSON estático servido pelo Vite/Cloudflare Pages (sem endpoint de backend).
    fetch('/benchmark/resultados.json', { cache: 'no-store' })
      .then(r => { if (!r.ok) throw new Error('sem dados'); return r.json() })
      .then((d: Resultados) => setDados(d))
      .catch(() => setErro('vazio'))
      .finally(() => setCarregando(false))
  }, [])

  const motores = dados?.motores ?? []

  // Melhor motor por métrica (p/ KPIs).
  const melhores = useMemo(() => {
    if (!motores.length) return null
    const menor = (k: keyof MotorResumo) =>
      [...motores].sort((a, b) => (a[k] as number) - (b[k] as number))[0]
    const maior = (k: keyof MotorResumo) =>
      [...motores].sort((a, b) => (b[k] as number) - (a[k] as number))[0]
    return {
      latencia: menor('latencia_p50_ms'),
      custo: menor('custo_usd_1k'),
      af1: maior('af1_pct'),
      consistencia: [...motores]
        .filter(m => m.consistencia != null)
        .sort((a, b) => (b.consistencia ?? 0) - (a.consistencia ?? 0))[0],
    }
  }, [motores])

  const exemplosFiltrados = useMemo(() => {
    let ex = dados?.exemplos_qualitativos ?? []
    if (filCategoria !== 'todas') {
      // mapeia prefixo do id à categoria
      const pref: Record<string, string> = { preco: 'P', licitacao: 'L', edital: 'E', geral: 'G' }
      ex = ex.filter(e => e.questao_id.startsWith(pref[filCategoria]))
    }
    return ex
  }, [dados, filCategoria])

  const categoriaData = useMemo(() => {
    const linhas = dados?.por_categoria ?? []
    const cats = filCategoria === 'todas'
      ? [...CATEGORIAS] as string[]
      : [filCategoria]
    return cats.map(cat => {
      const row: Record<string, number | string> = { categoria: cat, categoriaRotulo: t(`cat_${cat}` as ChaveMsg) }
      motores.forEach(m => {
        const r = linhas.find(l => l.motor === m.motor && l.categoria === cat)
        row[m.motor] = r ? r.af1_pct : 0
      })
      return row
    })
  }, [dados, motores, filCategoria, t])

  return (
    <div className="page">
      <h2 style={{ margin: 0 }}>{t('titulo')}</h2>

      {/* Switch global de motor + comparador ao vivo (sempre visível) */}
      <ComparadorVivo />

      {/* Dashboard agregado (corridas offline / GitHub Actions) */}
      {carregando ? (
        <div className="chart-card" style={{ textAlign: 'center', color: 'var(--texto-suave)' }}>
          {t('carregando')}
        </div>
      ) : (erro || !dados) ? (
        <div className="chart-card" style={{ textAlign: 'center', padding: 40 }}>
          <p style={{ fontSize: 16, marginBottom: 8 }}>{t('semDados')}</p>
          <p style={{ color: 'var(--texto-suave)' }}>
            {t('rodeBenchmark')}
          </p>
          <pre style={{ background: '#f1f5f9', padding: 12, borderRadius: 8, display: 'inline-block', textAlign: 'left', fontSize: 13, maxWidth: '100%', overflowX: 'auto' }}>
{`python -m benchmark.benchmark_executor --motores all --reps 3
python -m benchmark.benchmark_executor --export-frontend`}
          </pre>
        </div>
      ) : (
      <>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
        <h3 style={{ margin: 0 }}>{t('resultadosAgregados')}</h3>
        <span style={{ fontSize: 12, color: 'var(--texto-suave)' }}>
          {t('resumoRun', { reps: dados.n_repeticoes, n: dados.n_perguntas, data: fmtData(dados.gerado_em) })}
        </span>
      </div>

      {/* KPIs — melhor motor por dimensão */}
      {melhores && (
        <div className="metrics-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', marginTop: 16 }}>
          <div className="metric-card verde">
            <span className="metric-icon">⚡</span>
            <div className="metric-label">{t('menorLatencia')}</div>
            <div className="metric-value" style={{ fontSize: 20 }}>{melhores.latencia.rotulo}</div>
            <div className="metric-sub">{melhores.latencia.latencia_p50_ms} ms</div>
          </div>
          <div className="metric-card amarelo">
            <span className="metric-icon">💵</span>
            <div className="metric-label">{t('menorCusto')}</div>
            <div className="metric-value" style={{ fontSize: 20 }}>{melhores.custo.rotulo}</div>
            <div className="metric-sub">US$ {melhores.custo.custo_usd_1k.toFixed(4)}</div>
          </div>
          <div className="metric-card ceu">
            <span className="metric-icon">🎯</span>
            <div className="metric-label">{t('maiorAf1')}</div>
            <div className="metric-value" style={{ fontSize: 20 }}>{melhores.af1.rotulo}</div>
            <div className="metric-sub">{t('acertoFerramenta', { pct: melhores.af1.af1_pct })}</div>
          </div>
          <div className="metric-card terra">
            <span className="metric-icon">🔁</span>
            <div className="metric-label">{t('maiorConsistencia')}</div>
            <div className="metric-value" style={{ fontSize: 20 }}>{melhores.consistencia?.rotulo ?? '—'}</div>
            <div className="metric-sub">{melhores.consistencia?.consistencia != null ? melhores.consistencia.consistencia.toFixed(2) : '—'}</div>
          </div>
        </div>
      )}

      {/* Tabela comparativa principal (com superescritos de significância) */}
      <div className="chart-card">
        <h3>{t('comparacaoMotor')}</h3>
        <div style={{ overflowX: 'auto' }}>
          <table className="response-table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ textAlign: 'left', borderBottom: '2px solid var(--borda)' }}>
                <th style={{ padding: '8px 10px' }}>{t('colMotor')}</th>
                <th style={{ padding: '8px 10px' }}>p50 (ms)</th>
                <th style={{ padding: '8px 10px' }}>p95 (ms)</th>
                <th style={{ padding: '8px 10px' }}>{t('colCusto')}</th>
                <th style={{ padding: '8px 10px' }}>AF@1</th>
                <th style={{ padding: '8px 10px' }}>AF@2</th>
                <th style={{ padding: '8px 10px' }}>AF@3</th>
                <th style={{ padding: '8px 10px' }}>{t('colConsist')}</th>
                <th style={{ padding: '8px 10px' }}>{t('colErro')}</th>
              </tr>
            </thead>
            <tbody>
              {motores.map(m => (
                <tr key={m.motor} style={{ borderBottom: '1px solid var(--borda)', fontWeight: m.baseline ? 700 : 400 }}>
                  <td style={{ padding: '8px 10px' }}>
                    <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 3, background: corDe(m.motor), marginRight: 8 }} />
                    {m.rotulo}{m.baseline ? t('baseline') : ''}
                  </td>
                  <td style={{ padding: '8px 10px' }}>{m.latencia_p50_ms}<sup>{m.significancia?.latencia}</sup></td>
                  <td style={{ padding: '8px 10px' }}>{m.latencia_p95_ms}</td>
                  <td style={{ padding: '8px 10px' }}>{m.custo_usd_1k.toFixed(4)}</td>
                  <td style={{ padding: '8px 10px' }}>{m.af1_pct}%<sup>{m.significancia?.af1}</sup></td>
                  <td style={{ padding: '8px 10px' }}>{m.af2_pct}%</td>
                  <td style={{ padding: '8px 10px' }}>{m.af3_pct}%</td>
                  <td style={{ padding: '8px 10px' }}>{m.consistencia != null ? m.consistencia.toFixed(2) : '—'}</td>
                  <td style={{ padding: '8px 10px' }}>{m.taxa_erro_pct}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p style={{ fontSize: 11, color: 'var(--texto-suave)', marginTop: 8 }}>
          {(() => { const [antes, depois] = t('notaSignif').split('{sup}'); return <>{antes}<sup>⁰¹²³</sup>{depois}</> })()}
        </p>
      </div>

      {/* Gráficos: latência e AF@k */}
      <div className="grid-2" style={{ gap: 20 }}>
        <div className="chart-card" style={{ margin: 0 }}>
          <h3>{t('graficoLatencia')}</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={motores} margin={{ top: 4, right: 8, left: 8, bottom: 40 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e8e2d8" />
              <XAxis dataKey="rotulo" tick={{ fontSize: 10, fill: '#64748b' }} angle={-20} textAnchor="end" interval={0} />
              <YAxis tick={{ fontSize: 10, fill: '#64748b' }} />
              <Tooltip contentStyle={{ fontFamily: 'Inter', fontSize: 12, borderRadius: 10 }} />
              <Legend formatter={(v) => <span style={{ fontSize: 11 }}>{v}</span>} />
              <Bar dataKey="latencia_p50_ms" name="p50" fill="#334155" radius={[4, 4, 0, 0]} />
              <Bar dataKey="latencia_p95_ms" name="p95" fill="#94a3b8" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card" style={{ margin: 0 }}>
          <h3>{t('graficoAcuracia')}</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={motores} margin={{ top: 4, right: 8, left: 8, bottom: 40 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e8e2d8" />
              <XAxis dataKey="rotulo" tick={{ fontSize: 10, fill: '#64748b' }} angle={-20} textAnchor="end" interval={0} />
              <YAxis tick={{ fontSize: 10, fill: '#64748b' }} domain={[0, 100]} />
              <Tooltip contentStyle={{ fontFamily: 'Inter', fontSize: 12, borderRadius: 10 }} formatter={(v) => [`${v}%`, '']} />
              <Legend formatter={(v) => <span style={{ fontSize: 11 }}>{v}</span>} />
              <Bar dataKey="af1_pct" name="AF@1" fill="#0f766e" radius={[4, 4, 0, 0]} />
              <Bar dataKey="af2_pct" name="AF@2" fill="#5eaaa2" radius={[4, 4, 0, 0]} />
              <Bar dataKey="af3_pct" name="AF@3" fill="#a7cfca" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card" style={{ margin: 0 }}>
          <h3>{t('graficoCusto')}</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={motores} margin={{ top: 4, right: 8, left: 8, bottom: 40 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e8e2d8" />
              <XAxis dataKey="rotulo" tick={{ fontSize: 10, fill: '#64748b' }} angle={-20} textAnchor="end" interval={0} />
              <YAxis tick={{ fontSize: 10, fill: '#64748b' }} />
              <Tooltip contentStyle={{ fontFamily: 'Inter', fontSize: 12, borderRadius: 10 }} formatter={(v) => [`US$ ${Number(v).toFixed(4)}`, t('custo1k')]} />
              <Bar dataKey="custo_usd_1k" radius={[4, 4, 0, 0]}>
                {motores.map(m => <Cell key={m.motor} fill={corDe(m.motor)} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card" style={{ margin: 0 }}>
          <h3>{t('graficoDominio')}</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={motores} margin={{ top: 4, right: 8, left: 8, bottom: 40 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e8e2d8" />
              <XAxis dataKey="rotulo" tick={{ fontSize: 10, fill: '#64748b' }} angle={-20} textAnchor="end" interval={0} />
              <YAxis tick={{ fontSize: 10, fill: '#64748b' }} domain={[0, 100]} />
              <Tooltip contentStyle={{ fontFamily: 'Inter', fontSize: 12, borderRadius: 10 }} formatter={(v) => [`${v}%`, '']} />
              <Legend formatter={(v) => <span style={{ fontSize: 11 }}>{v}</span>} />
              <Bar dataKey="af1_conjunto_A" name={t('conjuntoA')} fill="#1e3a5f" radius={[4, 4, 0, 0]} />
              <Bar dataKey="af1_conjunto_B" name={t('conjuntoB')} fill="#b45309" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* AF@1 por categoria */}
      <div className="chart-card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
          <h3 style={{ margin: 0 }}>{t('porCategoria')}</h3>
          <select className="filter-select" style={{ fontSize: 12 }} value={filCategoria} onChange={e => setFilCategoria(e.target.value)}>
            <option value="todas">{t('todasCategorias')}</option>
            {CATEGORIAS.map(c => <option key={c} value={c}>{rotuloCat(c)}</option>)}
          </select>
        </div>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={categoriaData} margin={{ top: 12, right: 8, left: 8, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e8e2d8" />
            <XAxis dataKey="categoriaRotulo" tick={{ fontSize: 11, fill: '#64748b' }} />
            <YAxis tick={{ fontSize: 10, fill: '#64748b' }} domain={[0, 100]} />
            <Tooltip contentStyle={{ fontFamily: 'Inter', fontSize: 12, borderRadius: 10 }} formatter={(v) => [`${v}%`, '']} />
            <Legend formatter={(v) => <span style={{ fontSize: 11 }}>{motores.find(m => m.motor === v)?.rotulo ?? v}</span>} />
            {motores.map(m => (
              <Bar key={m.motor} dataKey={m.motor} name={m.motor} fill={corDe(m.motor)} radius={[4, 4, 0, 0]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Exemplos qualitativos */}
      <div className="chart-card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
          <h3 style={{ margin: 0 }}>{t('exemplos')}</h3>
          <select className="filter-select" style={{ fontSize: 12 }} value={filConjunto} onChange={e => setFilConjunto(e.target.value)}>
            <option value="todos">{t('todasClassif')}</option>
            {CLASSIFICACOES.map(c => <option key={c} value={c}>{rotuloClassif(c)}</option>)}
          </select>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
            <thead>
              <tr style={{ textAlign: 'left', borderBottom: '2px solid var(--borda)' }}>
                <th style={{ padding: '8px 10px' }}>{t('colPergunta')}</th>
                <th style={{ padding: '8px 10px' }}>{t('colMotor')}</th>
                <th style={{ padding: '8px 10px' }}>{t('colFerramenta')}</th>
                <th style={{ padding: '8px 10px' }}>{t('colParametros')}</th>
                <th style={{ padding: '8px 10px' }}>{t('colClassif')}</th>
                <th style={{ padding: '8px 10px' }}>{t('colResposta')}</th>
              </tr>
            </thead>
            <tbody>
              {exemplosFiltrados
                .filter(e => filConjunto === 'todos' || e.classificacao === filConjunto)
                .map((e, i) => {
                  const cfg = CLASSIF_CFG[e.classificacao] ?? CLASSIF_CFG.RECUSA
                  return (
                    <tr key={`${e.questao_id}-${e.motor}-${i}`} style={{ borderBottom: '1px solid var(--borda)' }}>
                      <td style={{ padding: '8px 10px', maxWidth: 200 }}>
                        <strong>{e.questao_id}</strong> {e.pergunta}
                      </td>
                      <td style={{ padding: '8px 10px' }}>{e.rotulo}</td>
                      <td style={{ padding: '8px 10px', fontFamily: 'monospace', fontSize: 11 }}>{e.tool_chamada ?? '—'}</td>
                      <td style={{ padding: '8px 10px', fontFamily: 'monospace', fontSize: 11, maxWidth: 180, wordBreak: 'break-word' }}>
                        {Object.keys(e.parametros || {}).length ? JSON.stringify(e.parametros) : '—'}
                      </td>
                      <td style={{ padding: '8px 10px' }}>
                        <span style={{ background: cfg.bg, color: cfg.cor, border: `1px solid ${cfg.borda}`, borderRadius: 6, padding: '2px 8px', fontSize: 11, fontWeight: 600 }}>
                          {rotuloClassif(e.classificacao)}
                        </span>
                      </td>
                      <td style={{ padding: '8px 10px', maxWidth: 260, color: 'var(--texto-suave)' }}>{e.trecho}</td>
                    </tr>
                  )
                })}
            </tbody>
          </table>
        </div>
      </div>
      </>
      )}
    </div>
  )
}
