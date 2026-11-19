import { expect, test } from '@playwright/test'

test.skip(process.env.PUBLIC_DEMO !== 'true', 'Executado apenas com PUBLIC_DEMO=true')

test('cinco telas funcionam em modo público sem ações administrativas', async ({ page, request }, testInfo) => {
  const errors: string[] = []
  const noHorizontalOverflow = async () =>
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text())
  })

  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Visão geral.' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Comparação dos detectores' })).toBeVisible()
  await expect(page.getByText('F1 0.8574')).toBeVisible()
  await expect(page.getByText('Dados sintéticos', { exact: true })).toBeVisible()
  await expect(page.getByText('Acesso administrativo')).toHaveCount(0)
  await noHorizontalOverflow()
  await page.screenshot({ path: `../artifacts/public-dashboard-${testInfo.project.name}.png`, fullPage: true })

  await page.getByRole('button', { name: /Isolation Forest.*F1/ }).click()
  await expect(page.getByRole('button', { name: /Isolation Forest.*F1/ })).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('link', { name: 'Transações', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Livro de movimentações' })).toBeVisible()
  await noHorizontalOverflow()
  await page.screenshot({ path: `../artifacts/public-transactions-${testInfo.project.name}.png`, fullPage: true })

  await page.getByRole('link', { name: 'Central de anomalias', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Fila de investigação' })).toBeVisible()
  await noHorizontalOverflow()
  await page.screenshot({ path: `../artifacts/public-anomalies-${testInfo.project.name}.png`, fullPage: true })
  await page.getByRole('button', { name: /Investigar alerta/ }).first().click()
  await expect(page.getByRole('heading', { name: 'Evidências observadas' })).toBeVisible()
  await page.getByRole('button', { name: 'Ver análise por regras' }).click()
  await expect(page.getByText('Baseada em regras · sem IA generativa').first()).toBeVisible()
  await noHorizontalOverflow()
  await page.screenshot({ path: `../artifacts/public-investigation-${testInfo.project.name}.png`, fullPage: true })

  await page.getByRole('link', { name: 'Automações', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Histórico de execuções' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Executar automação' })).toHaveCount(0)
  await noHorizontalOverflow()
  await page.screenshot({ path: `../artifacts/public-automations-${testInfo.project.name}.png`, fullPage: true })

  const root = 'http://127.0.0.1:8001'
  expect((await request.get(`${root}/api/health`)).ok()).toBe(true)
  const paths = (await (await request.get(`${root}/openapi.json`)).json()).paths
  expect(paths['/api/automations/pending']).toBeUndefined()
  expect(paths['/api/automations/run']).toBeUndefined()
  expect(paths['/api/pipeline/run']).toBeUndefined()
  expect([404, 405]).toContain((await request.post(`${root}/api/automations/run`)).status())
  expect([404, 405]).toContain((await request.post(`${root}/api/pipeline/run`)).status())
  expect(errors).toEqual([])
})
