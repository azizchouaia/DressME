import { useAuthStore } from '../stores/authStore'

const API_BASE = import.meta.env.VITE_API_URL ?? '/api/v1'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  body?: unknown
  form?: FormData
}

function describeError(status: number, payload: unknown): string {
  if (payload && typeof payload === 'object' && 'detail' in payload) {
    const { detail } = payload as { detail: unknown }
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: string; loc?: unknown[] }
      const field = first.loc?.at(-1)
      return field ? `${String(field)}: ${first.msg ?? 'invalid'}` : (first.msg ?? 'Invalid input')
    }
  }
  if (status >= 500) return 'The server had a problem. Please try again.'
  return `Request failed (${status})`
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {}
  const token = useAuthStore.getState().token
  if (token) headers.Authorization = `Bearer ${token}`

  let body: BodyInit | undefined
  if (options.form) {
    body = options.form
  } else if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }

  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: options.method ?? 'GET',
      headers,
      body,
    })
  } catch {
    throw new ApiError(0, 'Cannot reach the server. Check that the backend is running.')
  }

  if (response.status === 401 && token) {
    useAuthStore.getState().logout()
  }
  if (response.status === 204) return undefined as T

  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(response.status, describeError(response.status, payload))
  return payload as T
}
