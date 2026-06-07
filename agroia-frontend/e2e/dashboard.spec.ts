import { test, expect } from '@playwright/test'

/**
 * E2E do redesign da Home (KPIs + agrupamento) e da coerência de dados.
 * Os testes estruturais não dependem do banco; os de dados ("!= —") aguardam
 * o carregamento real de vw_itens_agro (precisam de VITE_SUPABASE_* válidos).
 */

test.describe('Home — redesign do dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('renderiza hero, busca e os 3 grupos de serviço', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /O que você precisa hoje/ })).toBeVisible()
    await expect(page.getByPlaceholder(/Pergunte ou busque/)).toBeVisible()

    for (const titulo of ['Consultar & Analisar', 'Agir', 'Operar & Monitorar']) {
      await expect(page.getByText(titulo, { exact: true })).toBeVisible()
    }
  })

  test('mostra 4 KPIs e contagem de cards por grupo (4 / 2 / 3)', async ({ page }) => {
    await expect(page.locator('.home-kpis .metric-card')).toHaveCount(4)
    await expect(page.locator('.home-kpis .metric-card.heroi')).toHaveCount(2)

    const grids = page.locator('.hub-group .hub-grid')
    await expect(grids.nth(0).locator('.hub-card')).toHaveCount(4)
    await expect(grids.nth(1).locator('.hub-card')).toHaveCount(2)
    await expect(grids.nth(2).locator('.hub-card')).toHaveCount(3)
    await expect(page.locator('.hub-card.destaque')).toHaveCount(1)
  })

  test('navegação dos cards e da busca', async ({ page }) => {
    await page.getByRole('link', { name: /Assistente/ }).first().click()
    await expect(page).toHaveURL(/\/assistente/)
    await page.goto('/')

    await page.getByPlaceholder(/Pergunte ou busque/).fill('preço do tomate')
    await page.getByRole('button', { name: /Perguntar/ }).click()
    await expect(page).toHaveURL(/\/assistente\?q=/)
  })

  test('toggle Gestor/Produtor troca os chips', async ({ page }) => {
    await expect(page.getByRole('link', { name: /Demanda 2024/ })).toBeVisible()
    await page.getByRole('button', { name: /Produtor/ }).click()
    await expect(page.getByRole('link', { name: /Cadastrar minha produção/ })).toBeVisible()
  })

  test('responsivo: 375px sem overflow horizontal', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 800 })
    await page.goto('/')
    const overflow = await page.evaluate(() =>
      document.documentElement.scrollWidth > document.documentElement.clientWidth + 1)
    expect(overflow).toBeFalsy()
  })

  // --- Depende de dados reais (Supabase) ---
  test('@data KPIs carregam valores e coerem com a Demanda', async ({ page }) => {
    const itensKpi = page.locator('.home-kpis .metric-card', { hasText: 'Itens agrícolas' }).locator('.metric-value')
    await expect(itensKpi).not.toHaveText('—', { timeout: 15_000 })
    const itensHome = (await itensKpi.innerText()).trim()

    await page.goto('/demanda?view=resumo')
    await expect(page.locator('.demanda-toolbar')).toContainText('itens na base', { timeout: 15_000 })
    const toolbar = await page.locator('.demanda-toolbar').innerText()
    expect(toolbar).toContain(itensHome) // mesmo número em ambas as superfícies
  })
})
