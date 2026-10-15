import { test, expect, type Page } from '@playwright/test'
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

/**
 * Pauta do Sacolão (/pauta) e Planejamento de safra (/safra) — plano v3, T-E6 e T-E7.
 *
 * Os testes das páginas novas ficam IGNORADOS até src/pages/Pauta.tsx e
 * src/pages/Safra.tsx existirem (etapa E8). O de não impacto (T-E7) roda já.
 * Os de dados ("@data") exigem VITE_SUPABASE_* e VITE_API_URL válidos.
 *
 * Contrato de marcação (data-testid) que E8 deve respeitar:
 *   pauta-linha, fonte-preco, exportar-xlsx, projecao-faixa, margem-erro,
 *   calendario-mes, aviso-frete, comparar-ceasa
 */

const existe = (rel: string) => existsSync(fileURLToPath(new URL(rel, import.meta.url)))
const TEM_PAUTA = existe('../src/pages/Pauta.tsx')
const TEM_SAFRA = existe('../src/pages/Safra.tsx')

/** Coleta erros de console e de página durante o teste. */
function vigiarConsole(page: Page): string[] {
  const erros: string[] = []
  page.on('console', (m) => { if (m.type() === 'error') erros.push(m.text()) })
  page.on('pageerror', (e) => erros.push(e.message))
  return erros
}

const PROMESSA = /previs[aã]o garantida|garantimos|com certeza|guaranteed|garantizad/i

// ── T-E6 · página /pauta ─────────────────────────────────────────────────────
test.describe('Pauta do Sacolão (/pauta)', () => {
  test.skip(!TEM_PAUTA, 'E8 pendente: src/pages/Pauta.tsx não existe')

  test('@data 43 linhas, cada preço com fonte, e exportação', async ({ page }) => {
    const erros = vigiarConsole(page)
    await page.goto('/pauta')
    const linhas = page.locator('[data-testid="pauta-linha"]')
    await expect(linhas).toHaveCount(43, { timeout: 20_000 })
    const n = await linhas.count()
    for (let i = 0; i < n; i++) {
      const linha = linhas.nth(i)
      // preço ausente aparece como "sem fonte" com motivo — nunca célula vazia
      await expect(linha.locator('[data-testid="fonte-preco"]')).not.toHaveText('')
    }
    const download = page.waitForEvent('download')
    await page.locator('[data-testid="exportar-xlsx"]').click()
    expect((await download).suggestedFilename()).toMatch(/\.xlsx$/)
    expect(erros).toEqual([])
  })

  test('@data projeção mostra faixa e margem de erro, sem promessa de acerto', async ({ page }) => {
    await page.goto('/pauta')
    const faixa = page.locator('[data-testid="projecao-faixa"]').first()
    // série sem modelo publicado mostra o motivo no lugar da faixa
    if (await faixa.count() === 0) {
      await expect(page.getByText(/sem proje[cç][aã]o/i).first()).toBeVisible()
      return
    }
    await expect(faixa).toContainText(/R\$\s?\d/)
    await expect(page.locator('[data-testid="margem-erro"]').first()).toBeVisible()
    expect(await page.locator('main').innerText()).not.toMatch(PROMESSA)
  })
})

// ── T-E6 · página /safra ─────────────────────────────────────────────────────
test.describe('Planejamento de safra (/safra)', () => {
  test.skip(!TEM_SAFRA, 'E8 pendente: src/pages/Safra.tsx não existe')

  test('@data calendário de 12 meses e comparação com aviso de frete', async ({ page }) => {
    const erros = vigiarConsole(page)
    await page.goto('/safra')
    await expect(page.locator('[data-testid="calendario-mes"]')).toHaveCount(12, { timeout: 20_000 })
    await expect(page.locator('[data-testid="comparar-ceasa"]').first()).toBeVisible()
    await expect(page.locator('[data-testid="aviso-frete"]')).toContainText(/frete/i)
    expect(erros).toEqual([])
  })

  test('textos nos 3 idiomas (pt/en/es)', async ({ page }) => {
    for (const idioma of ['pt', 'en', 'es']) {
      await page.addInitScript((i) => localStorage.setItem('agroia_idioma', i), idioma)
      await page.goto('/safra')
      await expect(page.locator('h1').first()).not.toBeEmpty()
    }
  })
})

// ── T-E7 · não impacto: páginas existentes seguem abrindo sem erro ───────────
const PAGINAS_EXISTENTES = ['/', '/mercado']

test.describe('Não impacto nas páginas existentes', () => {
  for (const rota of PAGINAS_EXISTENTES) {
    test(`${rota} abre sem erro de página`, async ({ page }) => {
      const erros: string[] = []
      page.on('pageerror', (e) => erros.push(e.message))
      const resp = await page.goto(rota)
      expect(resp?.ok()).toBeTruthy()
      await expect(page.locator('#root')).not.toBeEmpty()
      expect(erros).toEqual([])
    })
  }
})
