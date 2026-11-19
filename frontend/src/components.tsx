import type { ReactNode } from 'react'
import { compactMoney, dateLabel, number, severityLabels } from './format'
import type { Anomaly, SeriesPoint } from './types'

export function Icon({ name, size = 20 }: { name: string; size?: number }) {
  const paths: Record<string, ReactNode> = {
    dashboard: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
        <rect x="14" y="14" width="7" height="7" rx="1.5" />
      </>
    ),
    transactions: (
      <>
        <path d="M4 7h16m-4-4 4 4-4 4M20 17H4m4-4-4 4 4 4" />
      </>
    ),
    anomalies: (
      <>
        <path d="m12 3 10 17H2L12 3Z" />
        <path d="M12 9v4m0 3v1" />
      </>
    ),
    investigation: (
      <>
        <path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z" />
      </>
    ),
    automations: (
      <>
        <path d="m13 2-9 12h7l-1 8 10-13h-8l1-7Z" />
      </>
    ),
    arrow: (
      <>
        <path d="M5 12h14m-5-5 5 5-5 5" />
      </>
    ),
    refresh: (
      <>
        <path d="M20 7v5h-5M4 17v-5h5M6 6a8 8 0 0 1 13 3M5 15a8 8 0 0 0 13 3" />
      </>
    ),
    wallet: (
      <>
        <rect x="3" y="5" width="18" height="15" rx="3" />
        <path d="M21 11h-6v5h6M5 5V3h12" />
      </>
    ),
    check: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="m8 12 3 3 5-6" />
      </>
    ),
    lock: (
      <>
        <rect x="5" y="10" width="14" height="11" rx="2" />
        <path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2" />
      </>
    ),
  }
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] ?? paths.dashboard}
    </svg>
  )
}

export function Status({
  error,
  loading,
  children,
}: {
  error?: string
  loading?: boolean
  children: ReactNode
}) {
  if (error)
    return (
      <div className="notice error" role="alert">
        <Icon name="anomalies" />
        <div>
          <strong>Não foi possível carregar</strong>
          <p>{error}</p>
          <button className="text-button" onClick={() => window.location.reload()}>
            Recarregar página
          </button>
        </div>
      </div>
    )
  if (loading)
    return (
      <div className="loading" role="status">
        <span className="status-dot" />
        Carregando dados da API…
      </div>
    )
  return children
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="empty">
      <Icon name="check" size={28} />
      <p>{children}</p>
    </div>
  )
}

export function Badge({ severity }: { severity: Anomaly['severity'] }) {
  return (
    <span className={`badge ${severity}`}>
      <span />
      {severityLabels[severity]}
    </span>
  )
}

export function Pagination({
  page,
  total,
  pageSize = 25,
  onChange,
}: {
  page: number
  total: number
  pageSize?: number
  onChange: (page: number) => void
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  return (
    <div className="pagination">
      <span>
        {number(total)} registros · página {page} de {pages}
      </span>
      <div className="flex gap-2">
        <button disabled={page <= 1} onClick={() => onChange(page - 1)}>
          Anterior
        </button>
        <button disabled={page >= pages} onClick={() => onChange(page + 1)}>
          Próxima
        </button>
      </div>
    </div>
  )
}

export function CashflowChart({ data }: { data: SeriesPoint[] }) {
  const monthly = data.length > 45
  const groups = new Map<string, { inflow: number; outflow: number }>()
  data.forEach((point) => {
    const key = monthly ? point.day.slice(0, 7) : point.day
    const group = groups.get(key) ?? { inflow: 0, outflow: 0 }
    group.inflow += point.inflow_cents
    group.outflow += point.outflow_cents
    groups.set(key, group)
  })
  const points = [...groups.entries()].sort(([a], [b]) => a.localeCompare(b))
  if (!points.length) return <Empty>Nenhuma movimentação no período selecionado.</Empty>
  const max = Math.max(1, ...points.flatMap(([, value]) => [value.inflow, value.outflow])) * 1.12
  const x = (index: number) => 78 + (index / Math.max(1, points.length - 1)) * 740
  const y = (value: number) => 224 - (value / max) * 188
  const line = (field: 'inflow' | 'outflow') =>
    points
      .map(
        ([, point], index) =>
          `${index ? 'L' : 'M'} ${x(index).toFixed(1)} ${y(point[field]).toFixed(1)}`,
      )
      .join(' ')
  const label = (key: string) =>
    new Intl.DateTimeFormat(
      'pt-BR',
      monthly
        ? { month: 'short', timeZone: 'UTC' }
        : { day: '2-digit', month: '2-digit', timeZone: 'UTC' },
    ).format(new Date(`${key}${monthly ? '-01' : ''}T12:00:00Z`))
  return (
    <>
      <svg
        className="cashflow-chart"
        viewBox="0 0 850 270"
        role="img"
        aria-label={`Entradas e saídas aprovadas por ${monthly ? 'mês' : 'dia'}. Valores exatos disponíveis na tabela abaixo.`}
      >
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => (
          <g key={ratio}>
            <line
              x1="78"
              y1={y(max * ratio)}
              x2="824"
              y2={y(max * ratio)}
              stroke="#2c322b"
              strokeDasharray="3 5"
            />
            <text x="65" y={y(max * ratio) + 4} textAnchor="end">
              {compactMoney(max * ratio)}
            </text>
          </g>
        ))}
        <path
          d={`${line('inflow')} L ${x(points.length - 1)} 224 L 78 224 Z`}
          fill="#c4ef6e"
          fillOpacity=".045"
        />
        <path
          d={line('inflow')}
          fill="none"
          stroke="#c4ef6e"
          strokeWidth="2.5"
          strokeLinejoin="round"
        />
        <path
          d={line('outflow')}
          fill="none"
          stroke="#839cce"
          strokeWidth="2"
          strokeLinejoin="round"
        />
        {points.map(([key, point], index) => (
          <g key={key}>
            <circle cx={x(index)} cy={y(point.inflow)} r="3" fill="#c4ef6e">
              <title>
                {label(key)}: entrada {compactMoney(point.inflow)}, saída{' '}
                {compactMoney(point.outflow)}
              </title>
            </circle>
            {(index % Math.ceil(points.length / 12) === 0 || index === points.length - 1) && (
              <text x={x(index)} y="253" textAnchor="middle">
                {label(key)}
              </text>
            )}
          </g>
        ))}
      </svg>
      <details className="chart-data">
        <summary>Consultar valores do gráfico</summary>
        <div
          className="table-wrap"
          tabIndex={0}
          role="region"
          aria-label="Valores do fluxo financeiro"
        >
          <table>
            <thead>
              <tr>
                <th scope="col">Período</th>
                <th scope="col">Entradas</th>
                <th scope="col">Saídas</th>
              </tr>
            </thead>
            <tbody>
              {points.map(([key, point]) => (
                <tr key={key}>
                  <th scope="row">{monthly ? key : dateLabel(key)}</th>
                  <td>
                    {(point.inflow / 100).toLocaleString('pt-BR', {
                      style: 'currency',
                      currency: 'BRL',
                    })}
                  </td>
                  <td>
                    {(point.outflow / 100).toLocaleString('pt-BR', {
                      style: 'currency',
                      currency: 'BRL',
                    })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  )
}

export function AnomalyTable({
  items,
  onSelect,
}: {
  items: Anomaly[]
  onSelect: (id: number) => void
}) {
  if (!items.length) return <Empty>Nenhum alerta corresponde aos filtros selecionados.</Empty>
  return (
    <div className="table-wrap" tabIndex={0} role="region" aria-label="Lista de anomalias">
      <table>
        <thead>
          <tr>
            <th scope="col">Alerta / conta</th>
            <th scope="col">Data e canal</th>
            <th scope="col">Prioridade</th>
            <th scope="col">Detecção</th>
            <th scope="col">Grupo analisado</th>
            <th scope="col">
              <span className="sr-only">Ação</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <th scope="row">
                <span className="row-id">ALT-{String(item.id).padStart(4, '0')}</span>
                <strong>{item.account}</strong>
              </th>
              <td>
                {dateLabel(item.day)}
                <small>{item.channel}</small>
              </td>
              <td>
                <Badge severity={item.severity} />
              </td>
              <td>
                {item.ml_detected && <span className="tag">ML</span>}{' '}
                {item.rule_detected && <span className="tag">Regras</span>}
                <small>score IF {item.score.toFixed(3)}</small>
              </td>
              <td>
                {number(item.evidence.transaction_count)} transações
                <small>{compactMoney(item.evidence.total_cents)} em tentativas</small>
              </td>
              <td>
                <button
                  className="icon-button"
                  title={`Investigar alerta ${item.id}`}
                  aria-label={`Investigar alerta ${item.id}`}
                  onClick={() => onSelect(item.id)}
                >
                  <Icon name="arrow" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
