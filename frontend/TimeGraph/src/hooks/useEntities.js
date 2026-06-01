import { useState, useEffect } from 'react'
import { api } from '../utils/api'

export function useEntities(params = {}) {
  const [entities, setEntities] = useState([])
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState(null)

  useEffect(() => {
    setLoading(true)
    api.getEntities({ limit: 100, ...params })
      .then(setEntities)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [params.entity_type, params.q])

  return { entities, loading, error }
}

export function useEntityDetail(entityId) {
  const [entity,  setEntity]  = useState(null)
  const [events,  setEvents]  = useState([])
  const [rels,    setRels]    = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!entityId) return
    setLoading(true)
    Promise.all([
      api.getEntity(entityId),
      api.getEntityEvents(entityId),
      api.getEntityRels(entityId),
    ])
      .then(([ent, evs, rs]) => { setEntity(ent); setEvents(evs); setRels(rs) })
      .finally(() => setLoading(false))
  }, [entityId])

  return { entity, events, rels, loading }
}
