import { useState, useEffect } from 'react'
import { api } from '../utils/api'

export function useGraph({ minConfidence = 0.4, limitNodes = 60, limitEdges = 120 } = {}) {
  const [graph,   setGraph]   = useState(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)

  useEffect(() => {
    setLoading(true)
    api.getGraph({ min_confidence: minConfidence, limit_nodes: limitNodes, limit_edges: limitEdges })
      .then(setGraph)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [minConfidence, limitNodes, limitEdges])

  return { graph, loading, error }
}
