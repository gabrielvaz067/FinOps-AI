import { useEffect, useRef, useState } from 'react'
import { apiUrl, post, query, useApi } from './api'
import { Icon, Status } from './components'
import { Dashboard, Transactions, Anomalies, Investigation, Automations } from './pages'
import type { Filters, Health, Options, Page } from './types'

const pages: { id: Page; label: string; eyebrow: string; subtitle: string }[] = [
  {
    id: 'dashboard',
    label: 'Visão geral',
    eyebrow: 'MONITORAMENTO FINANCEIRO',
    subtitle: 'Uma visão clara dos movimentos. Atenção ao que foge do padrão.',
  },
  {
    id: 'transactions',
    label: 'Transações',
    eyebrow: 'EXPLORAR MOVIMENTAÇÕES',
    subtitle: 'Rastreie entradas, saídas e tentativas de pagamento.',
  },
  {
    id: 'anomalies',
    label: 'Central de anomalias',
    eyebrow: 'SINAIS QUE MERECEM ATENÇÃO',
    subtitle: 'Evidências de comportamento atípico, com contexto e prioridade.',
  },
  {
    id: 'investigation',
    label: 'Investigação com IA',
    eyebrow: 'DO SINAL À INVESTIGAÇÃO',
    subtitle: 'Entenda as evidências e documente os próximos passos.',
  },
  {
    id: 'automations',
    label: 'Automações',
    eyebrow: 'OPERAÇÃO E RASTREABILIDADE',
    subtitle: 'Alertas críticos, entregas deduplicadas e histórico de execução.',
  },
]
function currentRoute(): { page: Page; id: number | null } {
  const [name, id] = window.location.hash.replace(/^#\/?/, '').split('/')
  return {
    page: pages.some((page) => page.id === name) ? (name as Page) : 'dashboard',
    id: id && /^\d+$/.test(id) ? Number(id) : null,
  }
}

export default function App() {
  const [route, setRoute] = useState(currentRoute)
  const [filters, setFilters] = useState<Filters>({
    start: '',
    end: '',
    account_id: '',
    channel_id: '',
  })
  const [revision, setRevision] = useState(0)
  const [adminKey, setAdminKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const heading = useRef<HTMLHeadingElement>(null)
  const options = useApi<Options>('/options')
  const health = useApi<Health>('/health')
  useEffect(() => {
    const navigate = () => {
      setRoute(currentRoute())
      setMessage('')
      requestAnimationFrame(() => heading.current?.focus())
    }
    window.addEventListener('hashchange', navigate)
    return () => window.removeEventListener('hashchange', navigate)
  }, [])
  const active = pages.find((page) => page.id === route.page)!
  const selectAnomaly = (id: number) => {
    window.location.hash = `/investigation/${id}`
  }
  const update = (key: keyof Filters, value: string) =>
    setFilters((previous) => ({ ...previous, [key]: value }))
  const params = query(filters)
  async function pipeline() {
    setBusy(true)
    setMessage('')
    try {
      await post('/pipeline/run', adminKey)
      setRevision((value) => value + 1)
      setMessage('Pipeline concluído. Resultados desta versão disponíveis, sem duplicações.')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Falha ao executar pipeline.')
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Pular para o conteúdo
      </a>
      <aside className="sidebar">
        <a href="#/dashboard" className="brand" aria-label="FinOps AI, início">
          <span className="brand-symbol">
            f<span>.</span>
          </span>
          <span>
            finops<span className="brand-ai">AI</span>
          </span>
        </a>
        <div className="workspace">
          <span className="workspace-avatar">S</span>
          <div>
            <strong>Sandbox financeiro</strong>
            <small>Ambiente de demonstração</small>
          </div>
          <span className="status-dot" />
        </div>
        <p className="nav-label">WORKSPACE</p>
        <nav aria-label="Navegação principal">
          {pages.map((page) => (
            <a
              key={page.id}
              href={`#/${page.id}`}
              aria-label={page.label}
              title={page.label}
              aria-current={route.page === page.id ? 'page' : undefined}
              className={route.page === page.id ? 'nav-item active' : 'nav-item'}
            >
              <Icon name={page.id} />
              <span>{page.label}</span>
              {route.page === page.id && <span className="active-mark" />}
            </a>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sandbox-note">
            <Icon name="lock" size={18} />
            <strong>Dados sintéticos. Sempre.</strong>
            <p>Um laboratório para explorar sinais, sem movimentar dinheiro real.</p>
          </div>
          <a className="docs-link" href={apiUrl('/docs')} target="_blank" rel="noreferrer">
            Documentação da API <Icon name="arrow" size={16} />
          </a>
          <div className="sidebar-footer">
            <span className="status-dot" />
            {health.data?.public_demo ? 'Demonstração pública' : 'Execução local'}<span>v1.0</span>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div>
            <span className="muted">Workspace</span>
            <span className="breadcrumb-slash">/</span>
            <span>{active.label}</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="demo-badge">DEMO</span>
            <span className="topbar-status">
              <span className={`status-dot ${health.data ? '' : 'offline'}`} />
              {health.data ? 'API conectada' : health.error ? 'API indisponível' : 'Conectando'}
            </span>
            <span className="avatar" aria-label={health.data?.public_demo ? 'Ambiente público' : 'Ambiente local'}>
              SF
            </span>
          </div>
        </header>
        <main id="main">
          <div className="page-heading">
            <div>
              <p className="eyebrow">{active.eyebrow}</p>
              <h1 tabIndex={-1} ref={heading}>
                {active.label}
                <span className="heading-dot">.</span>
              </h1>
              <p className="subtitle">{active.subtitle}</p>
            </div>
            <button onClick={() => setRevision((value) => value + 1)} className="refresh-button">
              <Icon name="refresh" size={17} />
              Atualizar
            </button>
          </div>
          {health.data?.public_demo && (
            <p className="public-demo-note">Demonstração pública · dados sintéticos · somente leitura</p>
          )}
          {health.data && !health.data.public_demo && <details className="admin-access">
            <summary>
              <Icon name="lock" size={14} /> Acesso administrativo{' '}
              <span>
                {adminKey ? 'Chave preenchida nesta sessão' : 'Necessário para executar ações'}
              </span>
            </summary>
            <div className="admin-controls">
              <label>
                Chave administrativa
                <input
                  type="password"
                  value={adminKey}
                  autoComplete="off"
                  placeholder="FINOPS_ADMIN_KEY do seu .env"
                  onChange={(event) => setAdminKey(event.target.value)}
                />
              </label>
              <button disabled={!adminKey || busy} onClick={pipeline}>
                {busy ? 'Executando…' : 'Executar pipeline'}
              </button>
              <p>A chave permanece apenas na memória desta aba.</p>
            </div>
          </details>}
          {message && (
            <div className="notice" role="status">
              {message}
            </div>
          )}
          {route.page !== 'automations' && (
            <div className="filterbar" role="group" aria-label="Filtros globais">
              <label>
                De
                <input
                  aria-label="Data inicial"
                  type="date"
                  value={filters.start}
                  onChange={(event) => update('start', event.target.value)}
                />
              </label>
              <label>
                Até
                <input
                  aria-label="Data final"
                  type="date"
                  value={filters.end}
                  onChange={(event) => update('end', event.target.value)}
                />
              </label>
              <label>
                Conta
                <select
                  aria-label="Conta"
                  value={filters.account_id}
                  onChange={(event) => update('account_id', event.target.value)}
                >
                  <option value="">Todas as contas</option>
                  {options.data?.accounts.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Canal
                <select
                  aria-label="Canal"
                  value={filters.channel_id}
                  onChange={(event) => update('channel_id', event.target.value)}
                >
                  <option value="">Todos os canais</option>
                  {options.data?.channels.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
              <button
                className="text-button clear-filters"
                onClick={() => setFilters({ start: '', end: '', account_id: '', channel_id: '' })}
              >
                Limpar filtros
              </button>
            </div>
          )}
          <Status error={options.error} loading={options.loading}>
            {route.page === 'dashboard' && (
              <Dashboard params={params} revision={revision} onSelect={selectAnomaly} />
            )}
            {route.page === 'transactions' && (
              <Transactions key={params} params={params} revision={revision} />
            )}
            {route.page === 'anomalies' && (
              <Anomalies
                key={params}
                params={params}
                revision={revision}
                onSelect={selectAnomaly}
              />
            )}
            {route.page === 'investigation' && (
              <Investigation
                key={`${params}:${route.id}`}
                params={params}
                revision={revision}
                id={route.id}
                onSelect={selectAnomaly}
                adminKey={adminKey}
                geminiAvailable={health.data?.gemini_available ?? false}
                publicDemo={health.data?.public_demo ?? false}
              />
            )}
            {route.page === 'automations' && (
              <Automations revision={revision} adminKey={adminKey} publicDemo={health.data?.public_demo ?? false} />
            )}
          </Status>
          <footer className="main-footer">
            <span>
              FinOps AI <span className="muted">/</span> Laboratório de inteligência financeira
            </span>
            <span>Anomalia é um sinal para investigar, não uma conclusão de fraude.</span>
          </footer>
        </main>
      </div>
    </div>
  )
}
