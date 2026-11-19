export const number = (value: number) => new Intl.NumberFormat('pt-BR').format(value)
export const money = (cents: number) =>
  new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    maximumFractionDigits: 2,
  }).format(cents / 100)
export const compactMoney = (cents: number) =>
  new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(cents / 100)
export const percent = (value: number) =>
  new Intl.NumberFormat('pt-BR', { style: 'percent', maximumFractionDigits: 1 }).format(value)
export const dateLabel = (value: string) =>
  new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(value.length === 10 ? `${value}T12:00:00Z` : `${value.replace(/Z$/, '')}Z`))
export const severityLabels = { critical: 'Crítica', high: 'Alta', medium: 'Moderada' }
