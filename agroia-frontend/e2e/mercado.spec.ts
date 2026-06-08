import { test, expect } from '@playwright/test'
import { recortarJanela, agregarJanela, labelPeriodo, PERIODOS } from '../src/lib/janelaPreco'
import type { PontoSerie } from '../src/lib/janelaPreco'

/**
 * Mercado — filtro de período (Hoje / Última semana / N dias / Personalizado).
 *
 * Testes PONTUAIS (lógica pura, sem navegador) das funções de janela, e testes
 * E2E estruturais do seletor. Os de dados ("@data") exigem VITE_SUPABASE_* válidos.
 */

// ── Teste pontual: lógica de janela (puro, determinístico) ────────────────────
test.describe('janelaPreco — unidade', () => {
  // Série fixa de 5 dias (asc). preco_min/medio/max por dia.
  const serie: PontoSerie[] = [
    { data_coleta: '2026-06-01', preco_min: 2.0, preco_medio: 2.5, preco_max: 3.0, unidade: 'KG' },
    { data_coleta: '2026-06-02', preco_min: 2.1, preco_medio: 2.6, preco_max: 3.1, unidade: 'KG' },
    { data_coleta: '2026-06-05', preco_min: 1.8, preco_medio: 2.4, preco_max: 2.9, unidade: 'KG' }, // lacuna 03-04
    { data_coleta: '2026-06-07', preco_min: 2.2, preco_medio: 2.7, preco_max: 3.3, unidade: 'KG' },
    { data_coleta: '2026-06-08', preco_min: 2.3, preco_medio: 2.8, preco_max: 3.4, unidade: 'KG' }, // maxData
  ]

  test('"hoje" devolve só o último dia disponível', () => {
    const j = recortarJanela(serie, 'hoje', '', '')
    expect(j).toHaveLength(1)
    expect(j[0].data_coleta).toBe('2026-06-08')
  })

  test('"7" (última semana) ancora na última data e filtra por data (não por contagem)', () => {
    // cutoff = 2026-06-08 - 6d = 2026-06-02 → inclui 02,05,07,08 (não 01)
    const j = recortarJanela(serie, '7', '', '')
    expect(j.map((p) => p.data_coleta)).toEqual(['2026-06-02', '2026-06-05', '2026-06-07', '2026-06-08'])
  })

  test('agregarJanela: min/médio/máx corretos', () => {
    const a = agregarJanela(serie)
    expect(a.n).toBe(5)
    expect(a.min).toBeCloseTo(1.8, 5)              // menor preco_min
    expect(a.max).toBeCloseTo(3.4, 5)              // maior preco_max
    expect(a.media).toBeCloseTo((2.5 + 2.6 + 2.4 + 2.7 + 2.8) / 5, 5)
    expect(a.unidade).toBe('KG')
  })

  test('monotonicidade min ≤ médio ≤ máx em toda janela', () => {
    for (const p of PERIODOS.map((x) => x.value)) {
      const a = agregarJanela(recortarJanela(serie, p, '', ''))
      if (a.n > 0) {
        expect(a.min as number).toBeLessThanOrEqual(a.media as number)
        expect(a.media as number).toBeLessThanOrEqual(a.max as number)
      }
    }
  })

  test('custom: faixa filtra; datas invertidas são normalizadas; fora-da-faixa → n=0', () => {
    expect(recortarJanela(serie, 'custom', '2026-06-02', '2026-06-05').map((p) => p.data_coleta))
      .toEqual(['2026-06-02', '2026-06-05'])
    // invertido (de > ate) → mesmo resultado
    expect(recortarJanela(serie, 'custom', '2026-06-05', '2026-06-02').map((p) => p.data_coleta))
      .toEqual(['2026-06-02', '2026-06-05'])
    // faixa vazia → série inteira
    expect(recortarJanela(serie, 'custom', '', '')).toHaveLength(5)
    // fora da faixa → vazio
    expect(agregarJanela(recortarJanela(serie, 'custom', '2030-01-01', '2030-12-31')).n).toBe(0)
  })

  test('série vazia → n=0 e tudo null', () => {
    const a = agregarJanela(recortarJanela([], '30', '', ''))
    expect(a).toMatchObject({ n: 0, min: null, media: null, max: null })
  })

  test('labelPeriodo: rótulos fixos e faixa custom', () => {
    expect(labelPeriodo('hoje', '', '', serie)).toBe('Hoje')
    expect(labelPeriodo('7', '', '', serie)).toBe('Última semana')
    expect(labelPeriodo('custom', '2026-06-02', '2026-06-05', serie)).toBe('02/06–05/06')
    expect(labelPeriodo('custom', '', '', serie)).toBe('01/06–08/06') // limites da série
  })
})

// ── E2E estrutural do seletor (navegador, sem depender de banco) ──────────────
test.describe('Mercado — seletor de período (UI)', () => {
  test('o seletor oferece Hoje, Última semana e Período personalizado', async ({ page }) => {
    await page.goto('/mercado')
    const select = page.locator('.filters-bar select.filter-select')
    await expect(select).toBeVisible()
    const opts = await select.locator('option').allInnerTexts()
    for (const esperado of ['Hoje', 'Última semana', '30 dias', '24 meses', 'Período personalizado']) {
      expect(opts).toContain(esperado)
    }
  })

  test('escolher "Período personalizado" revela 2 inputs de data e persiste na URL', async ({ page }) => {
    await page.goto('/mercado')
    const select = page.locator('.filters-bar select.filter-select')
    await expect(page.locator('.filters-bar input[type="date"]')).toHaveCount(0)
    await select.selectOption('custom')
    await expect(page.locator('.filters-bar input[type="date"]')).toHaveCount(2)
    await expect(page).toHaveURL(/periodo=custom/)
    // recarrega → estado restaurado da URL
    await page.reload()
    await expect(page.locator('.filters-bar input[type="date"]')).toHaveCount(2)
  })
})
