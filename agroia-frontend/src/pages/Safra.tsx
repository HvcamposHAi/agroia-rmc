import { useEffect, useMemo, useState } from 'react'
import { CalendarRange, CircleAlert, Landmark, Truck } from 'lucide-react'
import PageHeader from '../components/PageHeader'
import { useUrlState } from '../lib/useUrlState'
import { defineMessages, useT, useI18n, fmtBRL, fmtNum, fmtData } from '../i18n'
import {
  getSafraSazonal, getSafraComparar, getCatalogoProhort, faixaSazonal, diferencaPct,
  rotuloProduto, rotuloCeasa, dataIso,
} from '../lib/pauta'
import type { SafraSazonal, SafraComparar, FaixaSazonal } from '../lib/pauta'

const MSG = defineMessages({
  pt: {
    titulo: 'Planejamento de safra',
    subtitulo: 'Quando a colheita costuma valer mais e em qual CEASA o produto está mais caro agora.',
    fonte: 'Fonte: PROHORT/CONAB, preços de atacado das CEASAs',
    produto: 'Produto',
    ceasa: 'CEASA do calendário',
    carregando: 'Carregando…',
    erro: 'Não foi possível carregar os dados agora. Tente novamente em instantes.',
    semDados: 'Não há cotações deste produto na CEASA {c} para montar o calendário. Escolha outra CEASA.',
    quandoTitulo: 'Quando a colheita vale mais',
    quandoSub: 'Preço de cada mês comparado com a média do mesmo ano, em {c}. Resumo de {n} anos ({de} a {ate}), em {u}.',
    acima: '{p}% acima da média',
    abaixo: '{p}% abaixo da média',
    naMedia: 'perto da média',
    semDado: 'sem dado',
    anos: '{n} anos',
    poucoConfiavel: 'pouco confiável',
    legendaAlta: 'Mês mais caro (vale mais colher)',
    legendaBaixa: 'Mês mais barato',
    legendaConfianca: 'Meses com menos de 3 anos de dados são pouco confiáveis.',
    plantio: 'Para virar data de plantio, o calendário precisa do ciclo de cada cultura na região (IDR-Paraná). Por enquanto a página mostra só a colheita.',
    ondeTitulo: 'Onde vender agora',
    ondeSub: 'Mediana dos últimos 30 dias em cada CEASA, em {u}.',
    colCeasa: 'CEASA',
    colMediana: 'Mediana (30 dias)',
    colDif: 'Diferença para Curitiba',
    colCotacoes: 'Cotações',
    colUltima: 'Última cotação',
    referencia: 'referência',
    excluidas: 'Fora da comparação (sem cotação nos últimos 15 dias ou vendido em outra unidade):',
    frete: 'Diferença bruta de preço: não desconta frete, perdas nem custo de acesso ao box da CEASA de destino. Curitiba–Cascavel tem cerca de 500 km.',
    rodape: 'Material de apoio ao planejamento. Não é promessa de preço: o mercado pode fugir do padrão de anos anteriores.',
    consultado: 'Consultado em {d}',
  },
  en: {
    titulo: 'Harvest planning',
    subtitulo: 'When the harvest usually pays more, and which wholesale market (CEASA) pays the most right now.',
    fonte: 'Source: PROHORT/CONAB, wholesale prices at the CEASAs',
    produto: 'Product',
    ceasa: 'CEASA for the calendar',
    carregando: 'Loading…',
    erro: "Couldn't load the data right now. Please try again in a moment.",
    semDados: 'There are no quotes for this product at CEASA {c} to build the calendar. Choose another CEASA.',
    quandoTitulo: 'When the harvest pays more',
    quandoSub: 'Each month’s price compared with the same year’s average, at {c}. Summary of {n} years ({de} to {ate}), in {u}.',
    acima: '{p}% above average',
    abaixo: '{p}% below average',
    naMedia: 'close to average',
    semDado: 'no data',
    anos: '{n} years',
    poucoConfiavel: 'low confidence',
    legendaAlta: 'Most expensive month (best to harvest)',
    legendaBaixa: 'Cheapest month',
    legendaConfianca: 'Months with fewer than 3 years of data have low confidence.',
    plantio: 'Turning this into planting dates needs each crop’s cycle in the region (IDR-Paraná). For now the page shows the harvest only.',
    ondeTitulo: 'Where to sell now',
    ondeSub: 'Median of the last 30 days at each CEASA, in {u}.',
    colCeasa: 'CEASA',
    colMediana: 'Median (30 days)',
    colDif: 'Difference to Curitiba',
    colCotacoes: 'Quotes',
    colUltima: 'Last quote',
    referencia: 'reference',
    excluidas: 'Left out (no quote in the last 15 days, or sold in another unit):',
    frete: 'Gross price difference: it does not deduct freight, losses or the cost of selling at the destination CEASA. Curitiba–Cascavel is about 500 km.',
    rodape: 'Planning aid. Not a price promise: the market can depart from past years’ pattern.',
    consultado: 'Retrieved on {d}',
  },
  es: {
    titulo: 'Planificación de cosecha',
    subtitulo: 'Cuándo la cosecha suele valer más y en qué CEASA el producto está más caro ahora.',
    fonte: 'Fuente: PROHORT/CONAB, precios mayoristas de las CEASAs',
    produto: 'Producto',
    ceasa: 'CEASA del calendario',
    carregando: 'Cargando…',
    erro: 'No fue posible cargar los datos ahora. Inténtelo de nuevo en unos instantes.',
    semDados: 'No hay cotizaciones de este producto en la CEASA {c} para armar el calendario. Elija otra CEASA.',
    quandoTitulo: 'Cuándo la cosecha vale más',
    quandoSub: 'Precio de cada mes comparado con el promedio del mismo año, en {c}. Resumen de {n} años ({de} a {ate}), en {u}.',
    acima: '{p}% por encima del promedio',
    abaixo: '{p}% por debajo del promedio',
    naMedia: 'cerca del promedio',
    semDado: 'sin datos',
    anos: '{n} años',
    poucoConfiavel: 'poco confiable',
    legendaAlta: 'Mes más caro (conviene cosechar)',
    legendaBaixa: 'Mes más barato',
    legendaConfianca: 'Los meses con menos de 3 años de datos son poco confiables.',
    plantio: 'Para convertirlo en fechas de siembra se necesita el ciclo de cada cultivo en la región (IDR-Paraná). Por ahora la página muestra solo la cosecha.',
    ondeTitulo: 'Dónde vender ahora',
    ondeSub: 'Mediana de los últimos 30 días en cada CEASA, en {u}.',
    colCeasa: 'CEASA',
    colMediana: 'Mediana (30 días)',
    colDif: 'Diferencia con Curitiba',
    colCotacoes: 'Cotizaciones',
    colUltima: 'Última cotización',
    referencia: 'referencia',
    excluidas: 'Fuera de la comparación (sin cotización en los últimos 15 días o vendido en otra unidad):',
    frete: 'Diferencia bruta de precio: no descuenta flete, pérdidas ni el costo de acceso al box de la CEASA de destino. Curitiba–Cascavel tiene unos 500 km.',
    rodape: 'Material de apoyo a la planificación. No es una promesa de precio: el mercado puede apartarse del patrón de años anteriores.',
    consultado: 'Consultado el {d}',
  },
})

/** 404/422 = não há dado para essa combinação (não adianta tentar de novo); resto = falha. */
type Falha = null | 'sem_dados' | 'falha'
function classificarFalha(r: PromiseSettledResult<unknown>): Falha {
  if (r.status === 'fulfilled') return null
  const status = (r.reason as { response?: { status?: number } })?.response?.status
  return status === 404 || status === 422 ? 'sem_dados' : 'falha'
}

const COR_FAIXA: Record<FaixaSazonal, { fundo: string; borda: string }> = {
  alta: { fundo: 'var(--ok-fundo)', borda: 'var(--ok-borda)' },
  baixa: { fundo: 'var(--erro-fundo)', borda: 'var(--erro-borda)' },
  normal: { fundo: 'var(--superficie)', borda: 'var(--borda)' },
  sem_dado: { fundo: 'var(--cinza-claro)', borda: 'var(--borda)' },
}

export default function Safra() {
  const t = useT(MSG)
  const { locale } = useI18n()
  const [produto, setProduto] = useUrlState('produto', 'couve-flor')
  const [ceasa, setCeasa] = useUrlState('ceasa', 'CURITIBA')
  const [catalogo, setCatalogo] = useState<{ produtos: string[]; ceasas: string[] }>({ produtos: [], ceasas: [] })
  // Resultado guardado com a chave da consulta: "carregando" = resultado de outra chave
  // (evita setState síncrono dentro do efeito).
  const chave = `${produto}|${ceasa}`
  const [res, setRes] = useState<{
    chave: string; sazonal: SafraSazonal | null; comparar: SafraComparar | null
    falhaSazonal: Falha; falhaComparar: Falha
  } | null>(null)

  useEffect(() => { getCatalogoProhort().then(setCatalogo) }, [])

  useEffect(() => {
    let vivo = true
    // allSettled: se só o calendário falhar, a comparação continua aparecendo (achado B11)
    Promise.allSettled([getSafraSazonal(produto, ceasa), getSafraComparar(produto)])
      .then(([s, c]) => {
        if (!vivo) return
        setRes({
          chave,
          sazonal: s.status === 'fulfilled' ? s.value : null,
          comparar: c.status === 'fulfilled' ? c.value : null,
          falhaSazonal: classificarFalha(s), falhaComparar: classificarFalha(c),
        })
      })
    return () => { vivo = false }
  }, [chave, produto, ceasa])

  const carregando = res?.chave !== chave
  const sazonal = carregando ? null : res?.sazonal ?? null
  const comparar = carregando ? null : res?.comparar ?? null
  const semDados = !carregando && res?.falhaSazonal === 'sem_dados'
  const erro = !carregando && (res?.falhaSazonal === 'falha' || res?.falhaComparar === 'falha')

  const nomeMes = (m: number) =>
    new Date(2026, m - 1, 1).toLocaleString(locale, { month: 'long' })

  const anosResumo = useMemo(
    () => (sazonal ? Math.max(...sazonal.meses.map((m) => m.anos)) : 0),
    [sazonal],
  )
  const refCuritiba = comparar?.ranking.find((r) => r.ceasa === 'CURITIBA')?.mediana

  return (
    <div className="page">
      <PageHeader
        eyebrow={<><CalendarRange size={13} aria-hidden /> AgroIA-RMC</>}
        title={t('titulo')}
        subtitle={t('subtitulo')}
        source={t('fonte')}
      />

      <div className="filters-bar" style={{ marginBottom: 20 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600, fontSize: 13 }}>
          {t('produto')}
          <select className="filter-select" value={produto} onChange={(e) => setProduto(e.target.value)}>
            {(catalogo.produtos.length ? catalogo.produtos : [produto]).map((p) => (
              <option key={p} value={p}>{rotuloProduto(p)}</option>
            ))}
          </select>
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600, fontSize: 13 }}>
          {t('ceasa')}
          <select className="filter-select" value={ceasa} onChange={(e) => setCeasa(e.target.value)}>
            {(catalogo.ceasas.length ? catalogo.ceasas : [ceasa]).map((c) => (
              <option key={c} value={c}>{rotuloCeasa(c)}</option>
            ))}
          </select>
        </label>
      </div>

      {carregando && (
        <div role="status" style={{ textAlign: 'center', padding: 40 }}>
          <span className="spinner" style={{ width: 32, height: 32, borderWidth: 3 }} />
          <p style={{ marginTop: 12, color: 'var(--texto-suave)', fontWeight: 600 }}>{t('carregando')}</p>
        </div>
      )}

      {!carregando && erro && (
        <div className="aviso-box erro"><CircleAlert size={17} aria-hidden /> <span>{t('erro')}</span></div>
      )}

      {semDados && (
        <div className="aviso-box aviso" style={{ marginBottom: 20 }}>
          <CircleAlert size={17} aria-hidden /> <span>{t('semDados', { c: rotuloCeasa(ceasa) })}</span>
        </div>
      )}

      {!carregando && sazonal && (
        <section className="chart-card" style={{ marginBottom: 20 }}>
          <h3 style={{ margin: '0 0 4px' }}>{t('quandoTitulo')}</h3>
          <p style={{ margin: '0 0 14px', color: 'var(--texto-suave)', fontSize: 13 }}>
            {t('quandoSub', {
              c: rotuloCeasa(sazonal.ceasa), n: anosResumo, u: sazonal.unidade,
              de: fmtData(dataIso(sazonal.periodo.inicio)), ate: fmtData(dataIso(sazonal.periodo.fim)),
            })}
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 10 }}>
            {sazonal.meses.map((m) => {
              const faixa = faixaSazonal(m.indice)
              const pct = m.indice === null ? null : Math.round(Math.abs(m.indice - 1) * 100)
              return (
                <div
                  key={m.mes}
                  data-testid="calendario-mes"
                  data-faixa={faixa}
                  style={{
                    background: COR_FAIXA[faixa].fundo, border: `1px solid ${COR_FAIXA[faixa].borda}`,
                    borderRadius: 'var(--raio)', padding: '10px 12px', opacity: m.confiavel ? 1 : 0.75,
                  }}
                >
                  <div style={{ fontWeight: 700, textTransform: 'capitalize' }}>{nomeMes(m.mes)}</div>
                  <div style={{ fontSize: 13, marginTop: 2 }}>
                    {faixa === 'sem_dado' ? t('semDado')
                      : faixa === 'alta' ? t('acima', { p: pct ?? 0 })
                      : faixa === 'baixa' ? t('abaixo', { p: pct ?? 0 })
                      : t('naMedia')}
                  </div>
                  <div style={{ fontSize: 11.5, color: 'var(--texto-suave)', marginTop: 4 }}>
                    {t('anos', { n: m.anos })}
                    {!m.confiavel && m.anos > 0 && <> · <span className="badge aviso">{t('poucoConfiavel')}</span></>}
                  </div>
                </div>
              )
            })}
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, marginTop: 12, fontSize: 12, color: 'var(--texto-suave)' }}>
            <span><span className="badge ok">■</span> {t('legendaAlta')}</span>
            <span><span className="badge erro">■</span> {t('legendaBaixa')}</span>
            <span>{t('legendaConfianca')}</span>
          </div>
          <p style={{ margin: '12px 0 0', fontSize: 12.5, color: 'var(--texto-suave)' }}>{t('plantio')}</p>
        </section>
      )}

      {!carregando && comparar && (
        <section className="chart-card" style={{ marginBottom: 20 }}>
          <h3 style={{ margin: '0 0 4px', display: 'flex', alignItems: 'center', gap: 8 }}>
            <Landmark size={18} aria-hidden /> {t('ondeTitulo')}
          </h3>
          <p style={{ margin: '0 0 12px', color: 'var(--texto-suave)', fontSize: 13 }}>
            {t('ondeSub', { u: comparar.unidade })}
          </p>
          <div className="data-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t('colCeasa')}</th>
                  <th style={{ textAlign: 'right' }}>{t('colMediana')}</th>
                  <th style={{ textAlign: 'right' }}>{t('colDif')}</th>
                  <th style={{ textAlign: 'right' }}>{t('colCotacoes')}</th>
                  <th>{t('colUltima')}</th>
                </tr>
              </thead>
              <tbody>
                {comparar.ranking.map((r) => {
                  const dif = r.ceasa === 'CURITIBA' ? null : diferencaPct(r.mediana, refCuritiba)
                  return (
                    <tr key={r.ceasa} data-testid="comparar-ceasa" style={r.ceasa === 'CURITIBA' ? { fontWeight: 700 } : undefined}>
                      <td>{rotuloCeasa(r.ceasa)}</td>
                      <td style={{ textAlign: 'right' }}>{fmtBRL(r.mediana)}/{comparar.unidade}</td>
                      <td style={{ textAlign: 'right' }}>
                        {r.ceasa === 'CURITIBA' ? t('referencia')
                          : dif === null ? '—'
                          : `${dif > 0 ? '+' : ''}${fmtNum(dif, { maximumFractionDigits: 0 })}%`}
                      </td>
                      <td style={{ textAlign: 'right' }}>{fmtNum(r.cotacoes)}</td>
                      <td>{fmtData(dataIso(r.ultima_data))}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          {comparar.excluidas.length > 0 && (
            <p style={{ margin: '10px 0 0', fontSize: 12.5, color: 'var(--texto-suave)' }}>
              <strong>{t('excluidas')}</strong>{' '}
              {comparar.excluidas.map((e) => rotuloCeasa(e.ceasa)).join(', ')}
            </p>
          )}
          <div className="aviso-box aviso" data-testid="aviso-frete" style={{ marginTop: 12 }}>
            <Truck size={17} aria-hidden /> <span>{t('frete')}</span>
          </div>
        </section>
      )}

      {!carregando && (sazonal || comparar) && (
        <p style={{ fontSize: 12, color: 'var(--texto-suave)' }}>
          {t('rodape')}{' '}
          {sazonal && t('consultado', { d: new Date(sazonal.consultado_em).toLocaleString(locale) })}
        </p>
      )}
    </div>
  )
}
