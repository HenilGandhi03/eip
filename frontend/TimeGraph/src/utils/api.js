const BASE = import.meta.env.VITE_API_URL || '/api'

async function apiFetch(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`API ${res.status}: ${body}`)
  }
  return res.json()
}

export const api = {
  getEvents:       (params) => apiFetch(`/events?${new URLSearchParams(params)}`),
  getEvent:        (id)     => apiFetch(`/events/${id}`),
  getRelated:      (id, n=8)=> apiFetch(`/events/${id}/related?limit=${n}`),
  getEventStats:   ()       => apiFetch('/events/stats/summary'),

  getEntities:     (params) => apiFetch(`/entities?${new URLSearchParams(params)}`),
  getEntity:       (id)     => apiFetch(`/entities/${id}`),
  getEntityEvents: (id)     => apiFetch(`/entities/${id}/events`),
  getEntityRels:   (id)     => apiFetch(`/entities/${id}/relationships`),

  getGraph:        (params) => apiFetch(`/relationships/graph?${new URLSearchParams(params)}`),

  triggerIngest:   (days=7) => apiFetch(`/ingest/trigger?days_back=${days}`, { method: 'POST' }),
  ingestDay:       (date)   => apiFetch(`/ingest/day/${date}`, { method: 'POST' }),
  getIngestLog:    ()       => apiFetch('/ingest/log'),
}
