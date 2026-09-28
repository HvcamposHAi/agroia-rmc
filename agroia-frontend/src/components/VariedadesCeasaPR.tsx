import { useEffect, useMemo, useState } from 'react'
import type { CSSProperties } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { supabase } from '../lib/supabaseClient'
import { useUrlState } from '../lib/useUrlState'
import { defineMessages, useI18n, useT, fmtBRL as fmtBRLi, fmtData as fmtDataI } from '../i18n'

const MSG = defineMessages({
  pt: {
    titulo: 'Preços por variedade — CEASA/PR · {p}',
    intro: 'O preço muda conforme a variedade e a classificação. Escolha uma para ver só ela e a evolução.',
    ariaUnidade: 'Unidade CEASA/PR',
    ariaVariedade: 'Variedade',
    todas: 'Todas as variedades ({n})',
    variedade: 'Variedade',
    embalagem: 'Embalagem',
    ultimoPreco: 'Último preço',
    media30: 'Média 30d',
    minMax30: 'Mín–Máx 30d',
    data: 'Data',
    mostrarTodas: 'Mostrar todas',
    verSo: 'Ver só esta variedade',
    comum: '(comum)',
    evolucao: 'Evolução · {r} ({u}, 6 meses)',
    rsEmbalagem: 'R$/embalagem',
    rsEmb: 'R$/emb.',
    dataLabel: 'Data: {d}',
    rodape: 'Preço mais comum do dia no atacado, por embalagem; R$/kg calculado pelo peso da embalagem. Fonte: CEASA/PR.',
  },
  en: {
    titulo: 'Prices by variety — CEASA/PR · {p}',
    intro: 'Prices vary by variety and grade. Pick one to see only it and its trend.',
    ariaUnidade: 'CEASA/PR unit',
    ariaVariedade: 'Variety',
    todas: 'All varieties ({n})',
    variedade: 'Variety',
    embalagem: 'Package',
    ultimoPreco: 'Last price',
    media30: '30d average',
    minMax30: 'Min–Max 30d',
    data: 'Date',
    mostrarTodas: 'Show all',
    verSo: 'Show only this variety',
    comum: '(common)',
    evolucao: 'Trend · {r} ({u}, 6 months)',
    rsEmbalagem: 'R$/package',
    rsEmb: 'R$/pkg.',
    dataLabel: 'Date: {d}',
    rodape: 'Most common wholesale price of the day, per package; R$/kg calculated from the package weight. Source: CEASA/PR.',
  },
  es: {
    titulo: 'Precios por variedad — CEASA/PR · {p}',
    intro: 'El precio cambia según la variedad y la clasificación. Elige una para ver solo esa y su evolución.',
    ariaUnidade: 'Unidad CEASA/PR',
    ariaVariedade: 'Variedad',
    todas: 'Todas las variedades ({n})',
    variedade: 'Variedad',
    embalagem: 'Embalaje',
    ultimoPreco: 'Último precio',
    media30: 'Promedio 30d',
    minMax30: 'Mín–Máx 30d',
    data: 'Fecha',
    mostrarTodas: 'Mostrar todas',
    verSo: 'Ver solo esta variedad',
    comum: '(común)',
    evolucao: 'Evolución · {r} ({u}, 6 meses)',
    rsEmbalagem: 'R$/embalaje',
    rsEmb: 'R$/emb.',
    dataLabel: 'Fecha: {d}',
    rodape: 'Precio mayorista más común del día, por embalaje; R$/kg calculado por el peso del embalaje. Fuente: CEASA/PR.',
  },
})

// Cotação da CEASA/PR por VARIEDADE (tabela ceasa_pr_cotacoes, coletor chat/ceasa_pr_collector.py).
// O PROHORT só tem o produto genérico ("tangerina"); aqui aparecem Ponkan, Murkote, Montenegrina...

interface Variedade {
  unidade: string
  produto: string
  variedade: string | null
  embalagem: string | null
  descricao: string
  peso_kg: number | null
  ultima_data: string
  ultimo_preco: number | null
  ultimo_preco_kg: number | null
  media_30d: number | null
  min_30d: number | null
  max_30d: number | null
  media_kg_30d: number | null
  cotacoes_30d: number
}

interface Ponto { data_coleta: string; preco: number; preco_kg: number | null }

const UNIDADES_PR = [
  { value: 'CURITIBA',      label: 'Curitiba' },
  { value: 'MARINGA',       label: 'Maringá' },
  { value: 'LONDRINA',      label: 'Londrina' },
  { value: 'FOZ DO IGUACU', label: 'Foz do Iguaçu' },
  { value: 'CASCAVEL',      label: 'Cascavel' },
]

// Série única → cor de marca dos gráficos; estilo do tooltip comum às páginas.
const TOOLTIP_STYLE: CSSProperties = { border: '1px solid var(--borda)', borderRadius: 10 }

const fmtBRL = (v: number | null | undefined) =>
  v == null ? '—' : fmtBRLi(v, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const fmtData = (d: string) => fmtDataI(new Date(d.slice(0, 10) + 'T00:00:00'), { day: '2-digit', month: '2-digit' })
const capitalizar = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

/** "Maçã Fuji" → "maca" — mesma normalização do coletor (1ª palavra, sem acento). */
function produtoBase(termo: string): string {
  return termo.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim().split(/\s+/)[0] ?? ''
}

export default function VariedadesCeasaPR({ produto, unidadeInicial }: { produto: string; unidadeInicial: string }) {
  const { locale } = useI18n()
  const t = useT(MSG)
  const base = produtoBase(produto)
  const [unidade, setUnidade] = useState(
    UNIDADES_PR.some((u) => u.value === unidadeInicial) ? unidadeInicial : 'CURITIBA',
  )
  const [variedade, setVariedade] = useUrlState('variedade')   // = descricao (variedade + embalagem)
  // Resultados guardados com a chave da consulta: evita exibir dado de outro produto/unidade
  // sem precisar zerar estado dentro do efeito.
  const chave = `${base}|${unidade}`
  const [resultado, setResultado] = useState<{ chave: string; linhas: Variedade[] } | null>(null)
  const [serieRes, setSerieRes] = useState<{ chave: string; pontos: Ponto[] } | null>(null)
  const linhas = resultado?.chave === chave ? resultado.linhas : null

  useEffect(() => {
    if (!base) return
    let ativo = true
    supabase.from('v_ceasa_pr_variedades').select('*')
      .eq('produto', base).eq('unidade', unidade)
      .then(({ data, error }) => {
        if (!ativo) return
        // tabela ainda não criada / erro → painel some (não atrapalha a página)
        setResultado({ chave: `${base}|${unidade}`, linhas: error ? [] : ((data ?? []) as Variedade[]) })
      })
    return () => { ativo = false }
  }, [base, unidade])

  // Mais recentes primeiro; dentro da mesma data, ordem alfabética da variedade.
  const ordenadas = useMemo(() => [...(linhas ?? [])].sort((a, b) =>
    b.ultima_data.localeCompare(a.ultima_data) || a.descricao.localeCompare(b.descricao, locale),
  ), [linhas, locale])
  const selecionada = ordenadas.find((l) => l.descricao === variedade) ?? null
  const visiveis = selecionada ? [selecionada] : ordenadas

  const chaveSerie = selecionada ? `${unidade}|${selecionada.descricao}` : ''
  const serie = serieRes && serieRes.chave === chaveSerie ? serieRes.pontos : []

  useEffect(() => {
    if (!selecionada) return
    let ativo = true
    const desde = new Date(Date.now() - 180 * 86400000).toISOString().slice(0, 10)
    supabase.from('ceasa_pr_cotacoes').select('data_coleta, preco, preco_kg')
      .eq('unidade', unidade).eq('descricao', selecionada.descricao).gte('data_coleta', desde)
      .order('data_coleta', { ascending: true })
      .then(({ data }) => {
        if (ativo) setSerieRes({ chave: `${unidade}|${selecionada.descricao}`, pontos: (data ?? []) as Ponto[] })
      })
    return () => { ativo = false }
  }, [selecionada, unidade])

  if (!base || linhas === null || linhas.length === 0) return null

  const porKg = selecionada?.peso_kg != null
  const rotulo = (l: Variedade) => `${capitalizar(l.variedade ?? l.produto)} · ${l.embalagem ?? ''}`

  return (
    <div className="chart-card" style={{ marginBottom: 20, padding: '18px 20px' }}>
      <h3 style={{ margin: '0 0 4px' }}>{t('titulo', { p: capitalizar(base) })}</h3>
      <p style={{ fontSize: 12, color: 'var(--texto-suave)', margin: '0 0 12px' }}>
        {t('intro')}
      </p>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 14 }}>
        <select className="filter-select" value={unidade} onChange={(e) => setUnidade(e.target.value)} aria-label={t('ariaUnidade')}>
          {UNIDADES_PR.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
        </select>
        <select className="filter-select" value={selecionada ? variedade : ''} onChange={(e) => setVariedade(e.target.value)} aria-label={t('ariaVariedade')}>
          <option value="">{t('todas', { n: ordenadas.length })}</option>
          {ordenadas.map((l) => <option key={l.descricao} value={l.descricao}>{rotulo(l)}</option>)}
        </select>
      </div>

      <div className="data-table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>{t('variedade')}</th>
              <th>{t('embalagem')}</th>
              <th>{t('ultimoPreco')}</th>
              <th>R$/kg</th>
              <th>{t('media30')}</th>
              <th>{t('minMax30')}</th>
              <th>{t('data')}</th>
            </tr>
          </thead>
          <tbody>
            {visiveis.map((l) => (
              <tr
                key={l.descricao}
                onClick={() => setVariedade(selecionada ? '' : l.descricao)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setVariedade(selecionada ? '' : l.descricao) }
                }}
                tabIndex={0}
                className={`clicavel${selecionada ? ' selecionada' : ''}`}
                title={selecionada ? t('mostrarTodas') : t('verSo')}
              >
                <td className="forte">{capitalizar(l.variedade ?? t('comum'))}</td>
                <td>{l.embalagem ?? '—'}</td>
                <td>{fmtBRL(l.ultimo_preco)}</td>
                <td className="forte">{fmtBRL(l.ultimo_preco_kg)}</td>
                <td>{fmtBRL(l.media_30d)}</td>
                <td>{fmtBRL(l.min_30d)} – {fmtBRL(l.max_30d)}</td>
                <td>{fmtData(l.ultima_data)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selecionada && serie.length > 1 && (
        <div style={{ marginTop: 16 }}>
          <p style={{ fontSize: 13, fontWeight: 700, margin: '0 0 6px' }}>
            {t('evolucao', { r: rotulo(selecionada), u: porKg ? 'R$/kg' : t('rsEmbalagem') })}
          </p>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={serie}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grade)" />
              <XAxis dataKey="data_coleta" tickFormatter={fmtData} tick={{ fontSize: 11, fill: 'var(--chart-eixo)' }} />
              <YAxis tick={{ fontSize: 11, fill: 'var(--chart-eixo)' }} tickFormatter={(v: number) => `R$${v}`} />
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                formatter={(value) => [fmtBRL(Number(value)), porKg ? 'R$/kg' : t('rsEmb')]}
                labelFormatter={(label) => t('dataLabel', { d: fmtData(String(label)) })}
              />
              <Line type="monotone" dataKey={porKg ? 'preco_kg' : 'preco'} stroke="var(--chart-marca)" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <p style={{ fontSize: 11, color: 'var(--texto-suave)', margin: '10px 0 0', lineHeight: 1.5 }}>
        {t('rodape')}
      </p>
    </div>
  )
}

