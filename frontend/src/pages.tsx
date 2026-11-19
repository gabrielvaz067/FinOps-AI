import { useState } from 'react'
import { post, query, request, useApi } from './api'
import { AnomalyTable, Badge, CashflowChart, Empty, Icon, Pagination, Status } from './components'
import { compactMoney, dateLabel, money, number, percent } from './format'
import type {
  Analysis,
  AnalysisPreview,
  Anomaly,
  AnomalyDetail,
  AutomationData,
  AutomationRun,
  Approach,
  ChannelTotal,
  Paginated,
  SeriesPoint,
  Summary,
  Transaction,
} from './types'

type DataProps = { params: string; revision: number }
type SelectProps = { onSelect: (id: number) => void }

const approaches: { id: Approach; label: string; description: string }[] = [
  { id: 'rules', label: 'Regras', description: 'Maior F1 observado nesta avaliação' },
  { id: 'isolation_forest', label: 'Isolation Forest', description: 'Detecção multivariada' },
  { id: 'combined', label: 'Abordagem combinada', description: 'Maior recall observado' },
]

export function Dashboard({ params, revision, onSelect }: DataProps & SelectProps) {
  const [approach, setApproach] = useState<Approach>('rules')
  const summary = useApi<Summary>(`/summary?${params}&approach=${approach}`, revision)
  const series = useApi<SeriesPoint[]>(`/series?${params}`, revision)
  const channels = useApi<ChannelTotal[]>(`/channels?${params}`, revision)
  const alerts = useApi<Paginated<Anomaly>>(
    `/anomalies?${params}&severity=critical&page_size=5&approach=${approach}`,
    revision,
  )
  const automation = useApi<AutomationData>('/automations?page_size=1', revision)
  const latestRun = automation.data?.items[0]
  const data = summary.data
  const pipeline = data?.pipeline
  const cards = data
    ? [
        {
          label: 'Volume aprovado',
          value: compactMoney(data.inflow_cents + data.outflow_cents),
          detail: `${number(data.transaction_count)} tentativas de pagamento`,
          icon: 'wallet',
          className: 'lime',
        },
        {
          label: 'Saldo do período',
          value: compactMoney(data.net_cents),
          detail: 'Entradas menos saídas aprovadas',
          icon: 'transactions',
          className: 'blue',
        },
        {
          label: 'Taxa de aprovação',
          value: percent(data.approval_rate),
          detail: 'Sobre todas as tentativas',
          icon: 'check',
          className: 'lime',
        },
        {
          label: 'Anomalias detectadas',
          value: number(data.anomaly_count),
          detail: `${number(data.critical_count)} críticos · ${approaches.find((item) => item.id === approach)?.label}`,
          icon: 'anomalies',
          className: 'orange',
        },
      ]
    : []
  return (
    <>
      <Status loading={summary.loading} error={summary.error}>
        {data && (
          <div className="metric-grid">
            {cards.map((card) => (
              <article className="metric-card" key={card.label}>
                <div className="metric-label">
                  {card.label}
                  <span className={`metric-icon ${card.className}`}>
                    <Icon name={card.icon} size={18} />
                  </span>
                </div>
                <p className="metric-value">{card.value}</p>
                <p className="metric-detail">{card.detail}</p>
              </article>
            ))}
          </div>
        )}
      </Status>
      {pipeline && (
        <section className="panel approach-panel" aria-labelledby="approach-title">
          <div className="panel-heading">
            <div>
              <h2 id="approach-title">Comparação dos detectores</h2>
              <p>Resultados globais no teste sintético · selecione a abordagem usada nos alertas abaixo</p>
            </div>
            <span className="tag">Dados sintéticos</span>
          </div>
          <div className="approach-grid">
            {approaches.map((item) => {
              const metrics = pipeline.metrics[item.id]
              return (
                <button
                  key={item.id}
                  className={`approach-option ${approach === item.id ? 'selected' : ''}`}
                  aria-pressed={approach === item.id}
                  onClick={() => setApproach(item.id)}
                >
                  <span className="approach-name">{item.label}</span>
                  <strong>F1 {metrics.f1.toFixed(4)}</strong>
                  <span>Precisão {percent(metrics.precision)} · Recall {percent(metrics.recall)}</span>
                  <small>{item.description}</small>
                </button>
              )
            })}
          </div>
          <p className="approach-note">
            Treino: jan–ago/2025 ({number(pipeline.metadata_json.train_buckets)} grupos).
            Teste: set–dez/2025 ({number(pipeline.metadata_json.test_buckets)} grupos,
            {number(pipeline.metadata_json.positive_buckets)} positivos). Unidade: conta/canal/dia.
            As regras são o padrão pelo maior F1 observado aqui; isso não prevê desempenho em dados reais.
            Os filtros da página não recalculam estas métricas globais.
          </p>
        </section>
      )}
      <div className="dashboard-grid">
        <section className="panel chart-panel">
          <div className="panel-heading">
            <div>
              <h2>Fluxo financeiro</h2>
              <p>Movimentações aprovadas no período selecionado</p>
            </div>
            <div className="chart-legend">
              <span>
                <i className="lime-bg" />
                Entradas
              </span>
              <span>
                <i className="blue-bg" />
                Saídas
              </span>
            </div>
          </div>
          <Status loading={series.loading} error={series.error}>
            {series.data && <CashflowChart data={series.data} />}
          </Status>
        </section>
        <section className="panel channels-panel">
          <div className="panel-heading">
            <div>
              <h2>Canais de pagamento</h2>
              <p>Participação nas tentativas</p>
            </div>
            <Icon name="transactions" size={18} />
          </div>
          <Status loading={channels.loading} error={channels.error}>
            {channels.data &&
              (channels.data.length ? (
                <div className="channel-list">
                  {channels.data.map((channel, index) => {
                    const total = channels.data!.reduce((sum, item) => sum + item.count, 0)
                    return (
                      <div className="channel" key={channel.name}>
                        <div className="channel-top">
                          <span className="channel-name">
                            <span className={`channel-mark mark-${index}`}>
                              {channel.name.slice(0, 1)}
                            </span>
                            {channel.name}
                          </span>
                          <strong>{percent(channel.count / total)}</strong>
                        </div>
                        <div className="bar-track">
                          <div
                            className={`bar-fill fill-${index}`}
                            style={{ width: `${(channel.count / total) * 100}%` }}
                          />
                        </div>
                        <small>
                          {number(channel.count)} transações · {compactMoney(channel.amount_cents)}
                        </small>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <Empty>Sem dados para estes filtros.</Empty>
              ))}
          </Status>
        </section>
      </div>
      <section className="panel">
        <div className="panel-heading">
          <div className="flex items-center gap-3">
            <span className="section-icon orange">
              <Icon name="anomalies" />
            </span>
            <div>
              <h2>Prioridade na sua análise</h2>
              <p>Alertas críticos mais recentes · {approaches.find((item) => item.id === approach)?.label}</p>
            </div>
          </div>
          <a className="text-link" href="#/anomalies">
            Ver central <Icon name="arrow" size={16} />
          </a>
        </div>
        <Status loading={alerts.loading} error={alerts.error}>
          {alerts.data && <AnomalyTable items={alerts.data.items} onSelect={onSelect} />}
        </Status>
      </section>
      <section className="panel" aria-labelledby="dashboard-automation-title">
        <div className="panel-heading">
          <div>
            <h2 id="dashboard-automation-title">Última execução da automação</h2>
            <p>Resultado registrado pela API · notificações sintéticas no modo de demonstração</p>
          </div>
          <a className="text-link" href="#/automations">
            Ver histórico <Icon name="arrow" size={16} />
          </a>
        </div>
        <Status loading={automation.loading} error={automation.error}>
          {automation.data && (latestRun ? (
            <div className="dashboard-run">
              <strong>Execução #{latestRun.id}</strong>
              <span>{latestRun.status === 'completed' ? 'Concluída' : 'Falha parcial'}</span>
              <span>{number(latestRun.processed)} processadas · {number(latestRun.failed)} falhas · {number(latestRun.skipped)} ignoradas</span>
              <span className="tag">{latestRun.mode === 'simulated' ? 'Sem envio de e-mail' : 'SMTP'}</span>
            </div>
          ) : (
            <p className="dashboard-run muted">Nenhuma execução registrada. O histórico aparece após uma automação local.</p>
          ))}
        </Status>
      </section>
    </>
  )
}

export function Transactions({ params, revision }: DataProps) {
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState('')
  const [search, setSearch] = useState('')
  const [draft, setDraft] = useState('')
  const result = useApi<Paginated<Transaction>>(
    `/transactions?${params}&${query({ page, page_size: 12, status, search })}`,
    revision,
  )
  return (
    <section className="panel">
      <div className="panel-heading wrap">
        <div>
          <h2>Livro de movimentações</h2>
          <p>Valores em reais · horários sintéticos em UTC</p>
        </div>
        <form
          className="inline-form"
          onSubmit={(event) => {
            event.preventDefault()
            setPage(1)
            setSearch(draft)
          }}
        >
          <label className="sr-only" htmlFor="search-ref">
            Referência de pagamento
          </label>
          <input
            id="search-ref"
            placeholder="Buscar referência PAY-…"
            value={draft}
            maxLength={60}
            onChange={(event) => setDraft(event.target.value)}
          />
          <button type="submit">Buscar</button>
          <label className="sr-only" htmlFor="transaction-status">
            Status da transação
          </label>
          <select
            id="transaction-status"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value)
              setPage(1)
            }}
          >
            <option value="">Todos os status</option>
            <option value="approved">Aprovadas</option>
            <option value="declined">Recusadas</option>
          </select>
        </form>
      </div>
      <Status loading={result.loading} error={result.error}>
        {result.data && (
          <>
            {result.data.items.length ? (
              <div className="table-wrap" tabIndex={0} role="region" aria-label="Transações">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Referência</th>
                      <th scope="col">Conta</th>
                      <th scope="col">Data / canal</th>
                      <th scope="col">Direção</th>
                      <th scope="col">Valor</th>
                      <th scope="col">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.data.items.map((item) => (
                      <tr key={item.id}>
                        <th scope="row">
                          <span className="mono">{item.payment_ref}</span>
                          <small>TX-{item.id}</small>
                        </th>
                        <td>{item.account}</td>
                        <td>
                          {dateLabel(item.occurred_at)}
                          <small>
                            {item.occurred_at.slice(11, 16)} UTC · {item.channel}
                          </small>
                        </td>
                        <td>
                          <span className={item.direction === 'inflow' ? 'text-lime' : 'text-blue'}>
                            {item.direction === 'inflow' ? '↙ Entrada' : '↗ Saída'}
                          </span>
                        </td>
                        <td className="money-cell">{money(item.amount_cents)}</td>
                        <td>
                          <span
                            className={`badge ${item.status === 'approved' ? 'success' : 'critical'}`}
                          >
                            <span />
                            {item.status === 'approved' ? 'Aprovada' : 'Recusada'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty>Nenhuma transação encontrada. Ajuste a busca ou os filtros.</Empty>
            )}
            <Pagination page={page} total={result.data.total} pageSize={12} onChange={setPage} />
          </>
        )}
      </Status>
    </section>
  )
}

export function Anomalies({ params, revision, onSelect }: DataProps & SelectProps) {
  const [page, setPage] = useState(1)
  const [severity, setSeverity] = useState('')
  const [approach, setApproach] = useState<Approach>('rules')
  const result = useApi<Paginated<Anomaly>>(
    `/anomalies?${params}&${query({ page, page_size: 12, severity, approach })}`,
    revision,
  )
  return (
    <>
      <div className="notice">
        <Icon name="investigation" size={20} />
        <p>
          Os alertas representam grupos de uma conta e canal por dia, avaliados após o fechamento. O
          score do Isolation Forest é um sinal de desvio, não uma probabilidade de fraude.
        </p>
      </div>
      <section className="panel">
        <div className="panel-heading wrap">
          <div>
            <h2>Fila de investigação</h2>
            <p>Regras explicáveis e detecção multivariada independentes</p>
          </div>
          <div className="inline-form">
            <label>
              Prioridade
              <select
                aria-label="Prioridade"
                value={severity}
                onChange={(event) => {
                  setSeverity(event.target.value)
                  setPage(1)
                }}
              >
                <option value="">Todas</option>
                <option value="critical">Crítica</option>
                <option value="high">Alta</option>
                <option value="medium">Moderada</option>
              </select>
            </label>
            <label>
              Abordagem
              <select
                aria-label="Abordagem"
                value={approach}
                onChange={(event) => {
                  setApproach(event.target.value as Approach)
                  setPage(1)
                }}
              >
                <option value="combined">Combinada</option>
                <option value="rules">Regras</option>
                <option value="isolation_forest">Isolation Forest</option>
              </select>
            </label>
          </div>
        </div>
        <Status loading={result.loading} error={result.error}>
          {result.data && (
            <>
              <AnomalyTable items={result.data.items} onSelect={onSelect} />
              <Pagination page={page} total={result.data.total} pageSize={12} onChange={setPage} />
            </>
          )}
        </Status>
      </section>
    </>
  )
}

export function Investigation({
  params,
  revision,
  id,
  onSelect,
  adminKey,
  geminiAvailable,
  publicDemo,
}: DataProps & SelectProps & { id: number | null; adminKey: string; geminiAvailable: boolean; publicDemo: boolean }) {
  const [localRevision, setLocalRevision] = useState(0)
  const [provider, setProvider] = useState('rules')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [preview, setPreview] = useState<AnalysisPreview | null>(null)
  const alerts = useApi<Paginated<Anomaly>>(
    id ? null : `/anomalies?${params}&page_size=10`,
    revision,
  )
  const detail = useApi<AnomalyDetail>(id ? `/anomalies/${id}` : null, revision + localRevision)
  async function generate() {
    if (!id) return
    setBusy(true)
    setError('')
    try {
      if (publicDemo) {
        setPreview(await request<AnalysisPreview>(`/anomalies/${id}/analysis-preview`))
        return
      }
      await post<Analysis>(`/anomalies/${id}/investigate`, adminKey, { provider })
      setLocalRevision((value) => value + 1)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha na investigação.')
    } finally {
      setBusy(false)
    }
  }
  if (!id)
    return (
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Escolha um sinal para investigar</h2>
            <p>Abra um alerta para consultar evidências e gerar uma análise sob demanda.</p>
          </div>
        </div>
        <Status loading={alerts.loading} error={alerts.error}>
          {alerts.data && <AnomalyTable items={alerts.data.items} onSelect={onSelect} />}
        </Status>
        <div className="panel-bottom">
          <a className="text-link" href="#/anomalies">
            Explorar todos os alertas <Icon name="arrow" size={16} />
          </a>
        </div>
      </section>
    )
  const data = detail.data
  return (
    <Status loading={detail.loading} error={detail.error}>
      {data && (
        <>
          <a className="text-link back-link" href="#/anomalies">
            ← Voltar para a central
          </a>
          <div className="investigation-grid">
            <section className="panel evidence-panel">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">ALT-{String(id).padStart(4, '0')}</p>
                  <h2>{data.account}</h2>
                  <p>
                    {dateLabel(data.day)} · {data.channel}
                  </p>
                </div>
                <Badge severity={data.severity} />
              </div>
              <div className="evidence-content">
                <h3>Evidências observadas</h3>
                <ul className="reason-list">
                  {data.reasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
                <dl className="evidence-values">
                  <div>
                    <dt>Transações no grupo</dt>
                    <dd>{number(data.evidence.transaction_count)}</dd>
                  </div>
                  <div>
                    <dt>Volume em tentativas</dt>
                    <dd>{money(data.evidence.total_cents)}</dd>
                  </div>
                  <div>
                    <dt>Maior transação</dt>
                    <dd>{money(data.evidence.max_cents)}</dd>
                  </div>
                  <div>
                    <dt>Referência histórica do maior valor</dt>
                    <dd>{money(data.evidence.max_cents_baseline)}</dd>
                  </div>
                  <div>
                    <dt>Aprovação</dt>
                    <dd>{percent(data.evidence.approval_rate)}</dd>
                  </div>
                  <div>
                    <dt>Horários atípicos</dt>
                    <dd>{percent(data.evidence.night_rate)}</dd>
                  </div>
                  <div>
                    <dt>Referências repetidas</dt>
                    <dd>{percent(data.evidence.duplicate_rate)}</dd>
                  </div>
                  <div>
                    <dt>Score Isolation Forest</dt>
                    <dd>{data.score.toFixed(4)}</dd>
                  </div>
                </dl>
                <p className="muted text-xs">
                  Modelo {data.model_version}. Baselines calculados apenas no treino (jan–ago).
                </p>
              </div>
            </section>
            <section className="panel analysis-panel">
              <div className="panel-heading">
                <div className="flex items-center gap-3">
                  <span className="section-icon lime">
                    <Icon name="investigation" />
                  </span>
                  <div>
                    <h2>Análise do alerta</h2>
                    <p>Hipóteses separadas das evidências</p>
                  </div>
                </div>
              </div>
              <div className="analysis-controls">
                <label>
                  Método
                  <select value={provider} disabled={publicDemo} onChange={(event) => setProvider(event.target.value)}>
                    <option value="rules">Análise determinística · regras</option>
                    <option value="gemini" disabled={!geminiAvailable}>
                      Gemini {geminiAvailable ? '· API externa' : '· não configurado'}
                    </option>
                  </select>
                </label>
                <button className="primary" disabled={(!adminKey && !publicDemo) || busy} onClick={generate}>
                  <Icon name="investigation" size={16} />
                  {busy ? 'Analisando…' : publicDemo ? 'Ver análise por regras' : 'Gerar análise'}
                </button>
              </div>
              {publicDemo && (
                <p className="helper">Prévia sob demanda, somente leitura. Nenhuma análise é gravada ou enviada a serviços externos.</p>
              )}
              {!publicDemo && !adminKey && (
                <p className="helper">
                  Preencha o acesso administrativo acima para gerar uma análise.
                </p>
              )}
              {provider === 'gemini' && (
                <p className="helper">
                  Esta ação envia apenas as evidências agregadas ao Gemini. Use uma chave com quota
                  gratuita.
                </p>
              )}
              {error && (
                <p className="notice error" role="alert">
                  {error}
                </p>
              )}
              <div aria-live="polite">
                {preview || data.analyses.length ? (
                  <>
                    <AnalysisContent analysis={preview ?? data.analyses[0]} />
                    {!preview && <details className="history">
                      <summary>Histórico de análises ({data.analyses.length})</summary>
                      {data.analyses.slice(1).map((analysis) => (
                        <AnalysisContent key={analysis.id} analysis={analysis} />
                      ))}
                      {data.analyses.length === 1 && (
                        <p className="helper">Esta é a primeira análise deste alerta.</p>
                      )}
                    </details>}
                  </>
                ) : (
                  <Empty>
                    Nenhuma análise gerada. As evidências já estão disponíveis para revisão.
                  </Empty>
                )}
              </div>
            </section>
          </div>
          <section className="panel">
            <div className="panel-heading">
              <div>
                <h2>Transações relacionadas</h2>
                <p>Até 20 maiores valores do grupo · tentativas aprovadas e recusadas</p>
              </div>
            </div>
            <div
              className="table-wrap"
              tabIndex={0}
              role="region"
              aria-label="Transações relacionadas"
            >
              <table>
                <thead>
                  <tr>
                    <th scope="col">Referência</th>
                    <th scope="col">Horário UTC</th>
                    <th scope="col">Valor</th>
                    <th scope="col">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.transactions.map((item) => (
                    <tr key={item.id}>
                      <th scope="row" className="mono">
                        {item.payment_ref}
                      </th>
                      <td>{item.occurred_at.slice(11, 19)}</td>
                      <td>{money(item.amount_cents)}</td>
                      <td>{item.status === 'approved' ? 'Aprovada' : 'Recusada'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </Status>
  )
}

function AnalysisContent({ analysis }: { analysis: AnalysisPreview & { created_at?: string } }) {
  return (
    <article className={`analysis-content ${analysis.source === 'gemini' ? 'from-gemini' : 'from-rules'}`}>
      <div className="analysis-meta">
        <span className={`tag analysis-source ${analysis.source === 'gemini' ? 'gemini' : 'rules'}`}>
          {analysis.source === 'rules'
            ? 'Baseada em regras · sem IA generativa'
            : 'Gerada por Gemini'}
        </span>
        {analysis.created_at && <small>{dateLabel(analysis.created_at)}</small>}
      </div>
      {analysis.fallback_reason && (
        <p className="notice">
          Gemini indisponível ou resposta inválida. Foi aplicada a análise por regras.
        </p>
      )}
      <p className="analysis-summary">{analysis.content.summary}</p>
      {(
        [
          ['evidence', 'Evidências'],
          ['hypotheses', 'Hipóteses a verificar'],
          ['recommendations', 'Próximos passos'],
          ['limitations', 'Limitações'],
        ] as const
      ).map(([key, title]) => (
        <section key={key} className={key === 'limitations' ? 'limitations' : ''}>
          <h3>{title}</h3>
          <ul>
            {analysis.content[key].map((text, index) => (
              <li key={index}>{text}</li>
            ))}
          </ul>
        </section>
      ))}
    </article>
  )
}

export function Automations({ revision, adminKey, publicDemo }: { revision: number; adminKey: string; publicDemo: boolean }) {
  const [page, setPage] = useState(1)
  const [localRevision, setLocalRevision] = useState(0)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const result = useApi<AutomationData>(`/automations?page=${page}`, revision + localRevision)
  async function execute() {
    setBusy(true)
    setMessage('')
    try {
      const run = await post<AutomationRun>('/automations/run', adminKey)
      setMessage(
        `Execução #${run.id}: ${run.processed} notificações processadas, ${run.failed} falhas. Entregas anteriores não são repetidas.`,
      )
      setPage(1)
      setLocalRevision((value) => value + 1)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Erro ao executar.')
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <section className="automation-banner">
        <div className="flex items-center gap-4">
          <span className="automation-emblem">
            <Icon name="automations" size={28} />
          </span>
          <div>
            <span className="eyebrow">FLUXO DE ALERTAS CRÍTICOS</span>
            <h2>
              {result.data?.mode === 'smtp'
                ? 'Notificação por SMTP'
                : 'Simulação de notificações'}
            </h2>
            <p>
              {result.data?.mode === 'smtp'
                ? 'Envio real habilitado na configuração do servidor.'
                : 'Cada entrega é registrada. Nenhum e-mail é enviado.'}
            </p>
          </div>
        </div>
        {!publicDemo && <button className="primary" disabled={!adminKey || busy || !result.data} onClick={execute}>
          <Icon name="automations" size={17} />
          {busy ? 'Executando…' : 'Executar automação'}
        </button>}
      </section>
      {publicDemo && <p className="helper">Modo público: consulte o fluxo e o histórico sintético. A execução está disponível apenas no ambiente local.</p>}
      {!publicDemo && !adminKey && (
        <p className="helper">Preencha o acesso administrativo para executar o fluxo.</p>
      )}
      {message && (
        <div role="status" className="notice">
          {message}
        </div>
      )}
      <div className="workflow">
        <div>
          <span>01</span>
          <strong>Consultar</strong>
          <small>Até 100 alertas críticos pendentes</small>
        </div>
        <Icon name="arrow" />
        <div>
          <span>02</span>
          <strong>Deduplicar</strong>
          <small>Chave única por alerta e modo</small>
        </div>
        <Icon name="arrow" />
        <div>
          <span>03</span>
          <strong>Notificar</strong>
          <small>{result.data?.mode === 'smtp' ? 'SMTP com TLS' : 'Simulação explícita'}</small>
        </div>
        <Icon name="arrow" />
        <div>
          <span>04</span>
          <strong>Registrar</strong>
          <small>Resultado e tentativa persistidos</small>
        </div>
      </div>
      <Status loading={result.loading} error={result.error}>
        {result.data && (
          <>
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Histórico de execuções</h2>
                  <p>Falhas anteriores ao envio podem ser tentadas até três vezes.</p>
                </div>
                <span className="tag">{result.data.mode}</span>
              </div>
              {result.data.items.length ? (
                <div
                  className="table-wrap"
                  tabIndex={0}
                  role="region"
                  aria-label="Execuções de automação"
                >
                  <table>
                    <thead>
                      <tr>
                        <th scope="col">Execução</th>
                        <th scope="col">Data</th>
                        <th scope="col">Modo</th>
                        <th scope="col">Resultado</th>
                        <th scope="col">Processadas</th>
                        <th scope="col">Falhas</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.data.items.map((run) => (
                        <tr key={run.id}>
                          <th scope="row">RUN-{String(run.id).padStart(4, '0')}</th>
                          <td>
                            {dateLabel(run.created_at)}
                            <small>{run.created_at.slice(11, 19)} UTC</small>
                          </td>
                          <td>{run.mode === 'simulated' ? 'Simulado' : 'SMTP'}</td>
                          <td>
                            <span
                              className={`badge ${run.status === 'completed' ? 'success' : 'high'}`}
                            >
                              <span />
                              {run.status === 'completed'
                                ? 'Concluída'
                                : run.status === 'running'
                                  ? 'Em execução'
                                  : 'Com falhas'}
                            </span>
                          </td>
                          <td>{run.processed}</td>
                          <td>{run.failed}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <Empty>
                  {publicDemo
                    ? 'Nenhuma execução registrada nesta demonstração.'
                    : 'Nenhuma execução registrada. Execute o fluxo para simular as primeiras notificações.'}
                </Empty>
              )}
              <Pagination page={page} total={result.data.total} onChange={setPage} />
            </section>
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Últimas tentativas</h2>
                  <p>Até 50 registros recentes, com resultado auditável</p>
                </div>
              </div>
              {result.data.attempts.length ? (
                <div className="attempt-list">
                  {result.data.attempts.map((attempt) => (
                    <div key={attempt.id}>
                      <Icon
                        name={
                          attempt.status === 'simulated' || attempt.status === 'sent'
                            ? 'check'
                            : 'anomalies'
                        }
                        size={18}
                      />
                      <div>
                        <strong>
                          Alerta #{attempt.anomaly_id}{' '}
                          <span className="muted">· execução #{attempt.run_id}</span>
                        </strong>
                        <p>{attempt.message}</p>
                      </div>
                      <span className="tag">{attempt.status}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <Empty>As tentativas aparecerão aqui após a execução.</Empty>
              )}
            </section>
          </>
        )}
      </Status>
    </>
  )
}
