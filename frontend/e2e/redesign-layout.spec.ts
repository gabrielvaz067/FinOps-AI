import { expect, test } from '@playwright/test'

test('five pages fit desktop, tablet and phone viewports with live synthetic data', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Viewport matrix runs in the desktop browser context')
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text())
  })

  const routes = ['dashboard', 'transactions', 'anomalies', 'investigation/175', 'automations']
  for (const width of [1440, 1366, 768, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : width === 1366 ? 768 : 900 })
    for (const route of routes) {
      await page.goto(`/#/${route}`)
      await expect(page.locator('.loading')).toHaveCount(0)
      await expect(page.getByText('API conectada')).toBeAttached()
      await expect(page.locator('nav a[aria-current="page"]')).toBeVisible()
      await expect(page.getByRole('alert')).toHaveCount(0)
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
      expect(overflow, `${route} at ${width}px has page-level horizontal overflow`).toBeLessThanOrEqual(1)
      if (width === 390 && route === 'dashboard') {
        const chart = page.getByRole('region', { name: 'Gráfico de fluxo financeiro' })
        expect(await chart.evaluate((element) => element.scrollWidth > element.clientWidth)).toBe(true)
      }
      if (width === 390) {
        await page.screenshot({ path: `../artifacts/redesign-${route.replace('/', '-')}-390.png`, fullPage: true })
      }
    }
  }
  expect(errors).toEqual([])
})
