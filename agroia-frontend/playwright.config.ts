import { defineConfig, devices } from '@playwright/test'

/**
 * E2E do frontend AgroIA-RMC.
 * Sobe o dev server do Vite (porta 5173) e roda os specs em e2e/.
 *
 *   npm i -D @playwright/test && npx playwright install chromium
 *   npm run test:e2e
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: true,
    timeout: 120_000,
  },
})
