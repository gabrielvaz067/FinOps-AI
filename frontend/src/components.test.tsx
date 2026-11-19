import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AnomalyTable, CashflowChart, Pagination, Status } from './components'
import { apiUrl, query, request } from './api'
import type { Anomaly } from './types'

describe('API and interface behavior', () => {
  it('uses the configured API origin without putting credentials in the client', () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://finops-api.onrender.com/')
    expect(apiUrl('/api/health')).toBe('https://finops-api.onrender.com/api/health')
    expect(apiUrl('/docs')).toBe('https://finops-api.onrender.com/docs')
    vi.unstubAllEnvs()
    expect(apiUrl('/api/health')).toBe('/api/health')
  })

  it('encodes filters and excludes empty values', () => {
    expect(query({ search: 'A & B', page: 2, status: '' })).toBe('search=A+%26+B&page=2')
  })
  it('returns the API error message without losing authorization errors', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue({
          ok: false,
          status: 401,
          json: async () => ({ detail: 'Chave inválida.' }),
        }),
    )
    await expect(request('/pipeline/run')).rejects.toThrow('Chave inválida.')
    vi.unstubAllGlobals()
  })
  it('disables pagination at boundaries and navigates forward', async () => {
    const change = vi.fn()
    render(<Pagination page={1} total={30} onChange={change} />)
    expect(screen.getByRole('button', { name: 'Anterior' })).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Próxima' }))
    expect(change).toHaveBeenCalledWith(2)
  })
  it('renders an empty result honestly', () => {
    render(<AnomalyTable items={[]} onSelect={vi.fn()} />)
    expect(screen.getByText(/Nenhum alerta corresponde/)).toBeVisible()
  })
  it('exposes error and loading states to assistive technology', () => {
    const { rerender } = render(<Status loading>Content</Status>)
    expect(screen.getByRole('status')).toHaveTextContent('Carregando')
    rerender(<Status error="API indisponível">Content</Status>)
    expect(screen.getByRole('alert')).toHaveTextContent('API indisponível')
  })
  it('offers exact chart values and supports a single day', async () => {
    render(
      <CashflowChart
        data={[{ day: '2025-10-01', count: 1, inflow_cents: 12345, outflow_cents: 0 }]}
      />,
    )
    expect(screen.getByRole('img')).toHaveAccessibleName(/Entradas e saídas/)
    await userEvent.click(screen.getByText('Consultar valores do gráfico'))
    expect(screen.getByRole('table')).toHaveTextContent('123,45')
  })
  it('keeps long names, numeric values and actions accessible', async () => {
    const select = vi.fn()
    const anomaly: Anomaly = {
      id: 1,
      account: 'Companhia Internacional de Serviços e Comércio São João & Associados',
      channel: 'Transferência',
      day: '2025-12-31',
      severity: 'critical',
      score: 0.12,
      ml_detected: true,
      rule_detected: true,
      reasons: [],
      model_version: 'test',
      evidence: {
        transaction_count: 999999,
        total_cents: 98765432100,
        max_cents: 1000,
        approval_rate: 0,
        night_rate: 1,
        duplicate_rate: 1,
        count_baseline: 1,
        max_cents_baseline: 1,
        count_ratio: 1,
        max_ratio: 1,
      },
    }
    render(<AnomalyTable items={[anomaly]} onSelect={select} />)
    expect(screen.getByText(anomaly.account)).toBeVisible()
    expect(screen.getByText('999.999 transações')).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: 'Investigar alerta 1' }))
    expect(select).toHaveBeenCalledWith(1)
  })
})
