import { expect, test } from '@playwright/test'

test.use({ viewport: { width: 1440, height: 900 } })
test.skip(process.env.PUBLIC_DEMO !== 'true', 'Capturas geradas apenas com a demonstração pública')

test('capturas completas das cinco páginas com dados sintéticos carregados', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Capturas documentadas apenas no projeto desktop')
  let browserErrors = 0
  page.on('pageerror', () => browserErrors++)
  page.on('console', (message) => {
    if (message.type() === 'error') browserErrors++
  })

  const ready = async () => {
    await expect(page.locator('.loading')).toHaveCount(0)
    await expect(page.getByRole('alert')).toHaveCount(0)
    await expect(page.getByText('Demonstração pública · dados sintéticos · somente leitura')).toBeVisible()
    await expect(page.getByText('Acesso administrativo')).toHaveCount(0)
    await page.evaluate(async () => {
      await document.fonts.ready
    })
  }
  const capture = async (name: string) => {
    await ready()
    await page.screenshot({ path: `../docs/images/${name}`, fullPage: true, animations: 'disabled' })
  }

  await page.goto('/#/dashboard')
  await expect(page.locator('.metric-card')).toHaveCount(4)
  await expect(page.locator('.chart-panel svg[aria-label*="Entradas e saídas"]')).toBeVisible()
  await expect(page.locator('.channel-list .channel')).toHaveCount(4)
  await expect(page.getByRole('region', { name: 'Lista de anomalias' }).locator('tbody tr').first()).toBeVisible()
  await expect(page.locator('.dashboard-run')).toBeVisible()
  await capture('01-dashboard.png')

  await page.getByRole('link', { name: 'Transações', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Transações' }).locator('tbody tr')).toHaveCount(12)
  await capture('02-transacoes.png')

  await page.getByRole('link', { name: 'Central de anomalias', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Lista de anomalias' }).locator('tbody tr')).toHaveCount(12)
  await capture('03-anomalias.png')

  await page.getByRole('button', { name: /Investigar alerta/ }).first().click()
  await expect(page.getByRole('heading', { name: 'Evidências observadas' })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Transações relacionadas' }).locator('tbody tr').first()).toBeVisible()
  await page.getByRole('button', { name: 'Ver análise por regras' }).click()
  await expect(page.getByText('Baseada em regras · sem IA generativa').first()).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Limitações' })).toBeVisible()
  await capture('04-investigacao-ia.png')

  await page.getByRole('link', { name: 'Automações', exact: true }).click()
  await expect(page.locator('.automation-banner')).toContainText('Simulação de notificações')
  await expect(page.getByRole('heading', { name: 'Histórico de execuções' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Últimas tentativas' })).toBeVisible()
  await expect(
    page.getByRole('region', { name: 'Execuções de automação' })
      .or(page.getByText('Nenhuma execução registrada nesta demonstração.'))
      .first(),
  ).toBeVisible()
  await capture('05-automacoes.png')

  expect(browserErrors).toBe(0)
})
