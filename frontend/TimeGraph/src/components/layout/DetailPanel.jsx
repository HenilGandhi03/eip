import { useEffect, useState } from 'react'
import { useStore } from '../../store/useStore'
import { api } from '../../utils/api'
import { getCatMeta, toneLabel, confidenceColor, formatDate } from '../../utils/formatters'
import styles from './DetailPanel.module.css'

export default function DetailPanel() {
  const { selectedEventId, setSelectedEventId } = useStore()
  const [event,   setEvent]   = useState(null)
  const [related, setRelated] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!selectedEventId) { setEvent(null); setRelated([]); return }
    setLoading(true)
    Promise.all([api.getEvent(selectedEventId), api.getRelated(selectedEventId)])
      .then(([ev, rel]) => { setEvent(ev); setRelated(rel) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [selectedEventId])

  if (!selectedEventId) return (
    <aside className={styles.panel}>
      <div className={styles.header}><div className={styles.headerTitle}>Event Detail</div><div className={styles.headerSub}>Select an event to explore context</div></div>
      <div className="empty-state"><div className="empty-icon">◎</div><div className="empty-label">Click any event in the timeline<br />to explore relationships and context.</div></div>
    </aside>
  )

  if (loading || !event) return (
    <aside className={styles.panel}>
      <div className={styles.header}><div className={styles.headerTitle}>Loading…</div></div>
      <div className="empty-state"><div className="spinner" /></div>
    </aside>
  )

  const cat = getCatMeta(event.category)
  const confScore = Math.min(95, 40 + (event.num_sources || 0) * 1.5)

  return (
    <aside className={styles.panel}>
      <div className={styles.header}>
        <div className={styles.catBadge} style={{ background: cat.color + '18', color: cat.color }}>{cat.label}</div>
        <div className={styles.headerTitle}>{event.title || 'Untitled Event'}</div>
        <div className={styles.headerMeta}>
          <span>{formatDate(event.date)}</span>
          {event.location && <span>· {event.location}</span>}
        </div>
      </div>

      <div className={styles.scroll}>
        {event.summary && (
          <section className={styles.section}>
            <div className="section-label">Summary</div>
            <p className={styles.summary}>{event.summary}</p>
          </section>
        )}

        <section className={styles.section}>
          <div className="section-label">GDELT Signals</div>
          <div className={styles.metrics}>
            <Metric label="Tone"     value={toneLabel(event.tone)}  color={event.tone < -3 ? 'var(--red)' : event.tone > 2 ? 'var(--green)' : undefined} />
            <Metric label="Goldstein" value={event.goldstein != null ? event.goldstein.toFixed(1) : '—'} />
            <Metric label="Sources"  value={event.num_sources ?? '—'} />
            <Metric label="Articles" value={event.num_articles ?? '—'} />
            <Metric label="Mentions" value={event.num_mentions?.toLocaleString() ?? '—'} />
            <Metric label="Country"  value={event.country_a ?? '—'} />
          </div>
        </section>

        <section className={styles.section}>
          <div className="section-label">Data Confidence</div>
          <div className={styles.confRow}>
            <div className="conf-bar"><div className="conf-fill" style={{ width: `${confScore}%`, background: confidenceColor(confScore / 100) }} /></div>
            <span className="badge badge-ok">{Math.round(confScore)}%</span>
          </div>
          <div className={styles.confNote}>Based on source count and mention spread</div>
        </section>

        {event.source_url && (
          <section className={styles.section}>
            <div className="section-label">Primary Source</div>
            <a className={styles.sourceLink} href={event.source_url} target="_blank" rel="noopener noreferrer">
              <span>↗</span>
              <span className={styles.sourceDomain}>{(() => { try { return new URL(event.source_url).hostname } catch { return event.source_url } })()}</span>
              <span className={styles.gdeltTag}>GDELT</span>
            </a>
          </section>
        )}

        <div className="sep" />

        <section className={styles.section}>
          <div className="section-label">Observable Relationships ({related.length})</div>
          {related.length === 0
            ? <p className={styles.noRel}>No strong relationships detected in current dataset.</p>
            : related.map((r, i) => <RelatedCard key={i} rel={r} onSelect={setSelectedEventId} />)
          }
        </section>

        <section className={styles.section}>
          <div className="disclaimer">
            <strong>Transparency:</strong> All relationships are based on observable co-occurrence signals from GDELT data — shared entities, topics, locations, and temporal proximity. Time proximity is <em>never</em> treated as causality.
          </div>
        </section>
      </div>
    </aside>
  )
}

function Metric({ label, value, color }) {
  return (
    <div className={styles.metric}>
      <div className={styles.metricVal} style={color ? { color } : undefined}>{value}</div>
      <div className={styles.metricKey}>{label}</div>
    </div>
  )
}

function RelatedCard({ rel, onSelect }) {
  return (
    <div className={styles.relCard} onClick={() => onSelect(rel.event.id)}>
      <div className={styles.relTop}>
        <span className={styles.relType}>{rel.relationship_type?.replace(/_/g, ' ')}</span>
        <span className={styles.relConf} style={{ color: confidenceColor(rel.confidence) }}>{Math.round((rel.confidence || 0) * 100)}%</span>
      </div>
      <div className={styles.relTitle}>{rel.event.title || '—'}</div>
      <div className={styles.relMeta}>
        <span>{formatDate(rel.event.date)}</span>
        {rel.days_apart != null && <span>· {rel.days_apart}d apart</span>}
      </div>
      {rel.explanation && (
        <div className="expl-box">
          <div className="expl-header">⚖ Why connected</div>
          {rel.explanation.replace('Connected because: ', '').split(';').map((part, i) => (
            <div key={i} className={`expl-rule${part.toLowerCase().includes('no causal') ? ' muted' : ''}`}>{part.trim()}</div>
          ))}
        </div>
      )}
    </div>
  )
}
