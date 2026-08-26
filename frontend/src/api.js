const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`)
  return res.json()
}

export const api = {
  health: () => request('/health'),
  dashboard: () => request('/dashboard'),
  chat: (message) =>
    request('/chat', { method: 'POST', body: JSON.stringify({ message }) }),
  resetChat: () => request('/chat/reset', { method: 'POST' }),
}
