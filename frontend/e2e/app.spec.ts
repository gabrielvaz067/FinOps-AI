import { test, expect } from '@playwright/test'

test('dashboard, filters, pagination, investigation and automation use the live API', async ({
  page,
}, testInfo) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text())
  })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Visão geral.' })).toBeVisible()
  await expect(page.getByText('50.000 tentativas de pagamento')).toBeVisible()
  await expect(page.getByText('API conectada')).toBeAttached()
  await page.screenshot({
    path: `../artifacts/dashboard-${testInfo.project.name}.png`,
    fullPage: true,
  })
  await page.getByLabel('Conta', { exact: true }).selectOption('1')
  await expect(page.getByText('50.000 tentativas de pagamento')).not.toBeVisible()
  await page.getByRole('button', { name: 'Limpar filtros' }).click()
  await page.getByRole('link', { name: 'Transações', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Livro de movimentações' })).toBeVisible()
  await page.getByLabel('Status da transação').selectOption('declined')
  await expect(
    page.getByRole('region', { name: 'Transações', exact: true }).getByText('Recusada').first(),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Próxima' }).click()
  await expect(page.getByText(/página 2 de/)).toBeVisible()
  await page.getByLabel('Referência de pagamento').fill('DOES-NOT-EXIST')
  await page.getByRole('button', { name: 'Buscar', exact: true }).click()
  await expect(page.getByText('Nenhuma transação encontrada.', { exact: false })).toBeVisible()
  await page.getByRole('link', { name: 'Central de anomalias', exact: true }).click()
  await page.getByLabel('Prioridade', { exact: true }).selectOption('critical')
  await page
    .getByRole('button', { name: /Investigar alerta/ })
    .first()
    .click()
  await expect(page.getByRole('heading', { name: 'Evidências observadas' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Gerar análise' })).toBeDisabled()
  const adminKey = process.env.FINOPS_E2E_KEY
  if (!adminKey) throw new Error('Set FINOPS_E2E_KEY to the test server admin key.')
  await page.getByText('Acesso administrativo', { exact: false }).first().click()
  await page.getByLabel('Chave administrativa').fill(adminKey)
  await page.getByRole('button', { name: 'Gerar análise' }).click()
  await expect(page.getByText('Baseada em regras · sem IA generativa').first()).toBeVisible()
  await page.getByRole('link', { name: 'Automações', exact: true }).click()
  await page.getByRole('button', { name: 'Executar automação' }).click()
  await expect(page.getByRole('status')).toContainText('notificações processadas')
  await expect(page.getByRole('heading', { name: 'Histórico de execuções' })).toBeVisible()
  await page.getByRole('link', { name: 'Visão geral', exact: true }).click()
  const latestRun = page.getByRole('region', { name: 'Última execução da automação' })
  await expect(latestRun).toContainText('processadas')
  await expect(latestRun).toContainText('Sem envio de e-mail')
  expect(errors).toEqual([])
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
})

test('empty dates, API failure recovery, and narrow screen', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Data inicial').fill('2030-01-01')
  await expect(page.getByText('Nenhuma movimentação no período selecionado.')).toBeVisible()
  await expect(page.getByText('0 tentativas de pagamento')).toBeVisible()
  await page.getByRole('button', { name: 'Limpar filtros' }).click()
  await expect(page.getByText('50.000 tentativas de pagamento')).toBeVisible()
  await page.route('**/api/summary*', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Falha simulada no teste.' }),
    }),
  )
  await page.getByRole('button', { name: 'Atualizar', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Falha simulada no teste.')
  await page.unroute('**/api/summary*')
  await page.getByRole('button', { name: 'Recarregar página' }).click()
  await expect(page.getByText('50.000 tentativas de pagamento')).toBeVisible()
  await page.setViewportSize({ width: 320, height: 760 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
  await page.getByRole('link', { name: 'Central de anomalias', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Fila de investigação' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
})
