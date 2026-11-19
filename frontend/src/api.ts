import { useEffect, useState } from 'react'

export function apiUrl(path: string): string {
  const baseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/+$/, '') ?? ''
  return `${baseUrl}${path}`
}

export function query(values: Record<string, string | number | undefined>): string {
  const params = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => {
    if (value !== '' && value !== undefined) params.set(key, String(value))
  })
  return params.toString()
}

export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(`/api${path}`), options)
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)
    const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : null
    throw new Error(
      typeof detail === 'string'
        ? detail
        : `Não foi possível concluir a operação (${response.status}). Verifique os filtros e tente novamente.`,
    )
  }
  return response.json() as Promise<T>
}

export async function post<T>(path: string, key: string, body: object = {}): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Admin-Key': key },
    body: JSON.stringify(body),
  })
}

export function useApi<T>(path: string | null, revision = 0) {
  const identity = `${path}:${revision}`
  const [state, setState] = useState<{ identity: string; data?: T; error?: string }>({
    identity: '',
  })
  useEffect(() => {
    if (!path) return
    const controller = new AbortController()
    request<T>(path, { signal: controller.signal })
      .then((data) => setState({ identity, data }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted)
          setState({
            identity,
            error: error instanceof Error ? error.message : 'Erro de conexão com a API.',
          })
      })
    return () => controller.abort()
  }, [path, identity])
  return {
    data: state.identity === identity ? state.data : undefined,
    error: state.identity === identity ? state.error : undefined,
    loading: !!path && (state.identity !== identity || (!state.data && !state.error)),
  }
}
