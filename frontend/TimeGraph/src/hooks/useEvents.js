import { useState, useEffect } from 'react'
import { api } from '../utils/api'

export function useEvents(filters = {}) {
  const [events,  setEvents]  = useState([])
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)

  useEffect(() => {
    const params = { limit: 500 }
    if (filters.categories?.length) params.category   = filters.categories[0]
    if (filters.countries?.length)  params.country    = filters.countries[0]
    if (filters.startDate)          params.start_date = filters.startDate
    if (filters.endDate)            params.end_date   = filters.endDate
    if (filters.query)              params.q          = filters.query

    setLoading(true)
    api.getEvents(params)
      .then(setEvents)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [
    filters.categories?.join(','),
    filters.countries?.join(','),
    filters.startDate,
    filters.endDate,
    filters.query,
  ])

  return { events, loading, error }
}

export function useEventDetail(eventId) {
  const [event,   setEvent]   = useState(null)
  const [related, setRelated] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!eventId) { setEvent(null); setRelated([]); return }
    setLoading(true)
    Promise.all([api.getEvent(eventId), api.getRelated(eventId)])
      .then(([ev, rel]) => { setEvent(ev); setRelated(rel) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [eventId])

  return { event, related, loading }
}

export function useEventStats() {
  const [stats, setStats] = useState(null)
  useEffect(() => {
    api.getEventStats().then(setStats).catch(() => {})
  }, [])
  return { stats }
}
