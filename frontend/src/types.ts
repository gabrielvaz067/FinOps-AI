export type Page = 'dashboard' | 'transactions' | 'anomalies' | 'investigation' | 'automations'
export type Filters = { start: string; end: string; account_id: string; channel_id: string }
export type Option = { id: number; name: string }
export type Options = {
  accounts: Option[]
  channels: Option[]
  range: { start: string | null; end: string | null }
}
export type Health = {
  status: string
  synthetic: boolean
  gemini_available: boolean
  notification_mode: string
  public_demo: boolean
}
export type Approach = 'rules' | 'isolation_forest' | 'combined'
export type Metrics = {
  precision: number
  recall: number
  f1: number
  true_positives: number
  false_positives: number
  false_negatives: number
  true_negatives: number
}
export type Pipeline = {
  id: number
  model_version: string
  created_at: string
  train_end: string
  metrics: Record<string, Metrics>
  metadata_json: { train_buckets: number; test_buckets: number; positive_buckets: number }
}
export type Summary = {
  transaction_count: number
  inflow_cents: number
  outflow_cents: number
  net_cents: number
  approval_rate: number
  anomaly_count: number
  critical_count: number
  pipeline: Pipeline | null
}
export type SeriesPoint = {
  day: string
  count: number
  inflow_cents: number
  outflow_cents: number
}
export type ChannelTotal = { name: string; count: number; amount_cents: number }
export type Transaction = {
  id: number
  account_id: number
  channel_id: number
  account?: string
  channel?: string
  occurred_at: string
  amount_cents: number
  direction: 'inflow' | 'outflow'
  status: 'approved' | 'declined'
  payment_ref: string
}
export type Evidence = {
  transaction_count: number
  total_cents: number
  max_cents: number
  approval_rate: number
  night_rate: number
  duplicate_rate: number
  count_baseline: number
  max_cents_baseline: number
  count_ratio: number
  max_ratio: number
}
export type Anomaly = {
  id: number
  account: string
  channel: string
  day: string
  severity: 'critical' | 'high' | 'medium'
  score: number
  ml_detected: boolean
  rule_detected: boolean
  reasons: string[]
  evidence: Evidence
  model_version: string
}
export type Analysis = {
  id: number
  source: string
  model: string
  created_at: string
  fallback_reason: string | null
  content: {
    summary: string
    evidence: string[]
    hypotheses: string[]
    recommendations: string[]
    limitations: string[]
  }
}
export type AnalysisPreview = Pick<Analysis, 'source' | 'content' | 'fallback_reason'>
export type AnomalyDetail = Anomaly & { transactions: Transaction[]; analyses: Analysis[] }
export type Paginated<T> = { items: T[]; total: number; page: number; page_size: number }
export type AutomationRun = {
  id: number
  created_at: string
  mode: string
  status: string
  processed: number
  skipped: number
  failed: number
}
export type AutomationData = Paginated<AutomationRun> & {
  mode: string
  attempts: {
    id: number
    anomaly_id: number
    run_id: number
    mode: string
    status: string
    message: string
    created_at: string
  }[]
}
