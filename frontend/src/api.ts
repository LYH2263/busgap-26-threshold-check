export class ApiError extends Error {
  status: number
  payload: any
  constructor(status: number, payload: any, text: string) {
    super(typeof payload?.detail === 'object' ? payload.detail.message || text : text)
    this.status = status
    this.payload = payload
  }
}

export async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch('/api' + path, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text()
    let payload: any = null
    try { payload = text ? JSON.parse(text) : null } catch { payload = null }
    throw new ApiError(res.status, payload, text || res.statusText)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}
