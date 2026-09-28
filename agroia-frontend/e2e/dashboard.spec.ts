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

  test('renderiza hero, busca, aviso de IA e os grupos de serviço (Prefeitura)', async ({ page }) => {
    await expect(page.getByRole('heading', { level: 1, name: /Agricultura familiar e compras públicas/ })).toBeVisible()
    await expect(page.getByPlaceholder(/Pergunte em linguagem natural/)).toBeVisible()
    await expect(page.getByText(/Respostas geradas por IA/).first()).toBeVisible()

    for (const titulo of ['Analisar a demanda', 'Gestão e qualidade', 'Sobre os dados e a IA']) {
      await expect(page.getByRole('heading', { name: titulo })).toBeVisible()
    }
  })

  test('mostra 4 KPIs e contagem de cards por grupo (5 / 3)', async ({ page }) => {
    await expect(page.locator('.home-kpis .metric-card')).toHaveCount(4)
    await expect(page.locator('.home-kpis .metric-card.heroi')).toHaveCount(2)

    const grids = page.locator('.hub-group .hub-grid')
    await expect(grids.nth(0).locator('.hub-card')).toHaveCount(5)
    await expect(grids.nth(1).locator('.hub-card')).toHaveCount(3)
    await expect(page.locator('.hub-card.destaque')).toHaveCount(1)
  })

  test('navegação dos cards e da busca', async ({ page }) => {
    await page.locator('.hub-card', { hasText: 'Assistente' }).first().click()
    await expect(page).toHaveURL(/\/assistente/)
    await page.goto('/')

    await page.getByPlaceholder(/Pergunte em linguagem natural/).fill('preço do tomate')
    await page.getByRole('button', { name: /Perguntar/ }).click()
    await expect(page).toHaveURL(/\/assistente\?q=/)
  })

  test('perfil Prefeitura/Cooperativas troca atalhos e serviços', async ({ page }) => {
    await expect(page.getByRole('link', { name: /Demanda de 2025/ })).toBeVisible()
    await page.getByRole('button', { name: /Cooperativas e produtores/ }).click()
    await expect(page.getByRole('link', { name: /Cadastrar minha produção/ })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Vender para a prefeitura' })).toBeVisible()
  })

  test('rota antiga /ofertas leva ao Assistente', async ({ page }) => {
    await page.goto('/ofertas')
    await expect(page).toHaveURL(/\/assistente/)
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
