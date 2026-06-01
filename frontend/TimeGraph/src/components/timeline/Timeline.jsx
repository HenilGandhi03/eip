import { useMemo } from 'react'
import { useStore } from '../../store/useStore'
import { useEvents } from '../../hooks/useEvents'
import { getCatMeta, toneLabel, formatDate } from '../../utils/formatters'
import styles from './Timeline.module.css'

export default function Timeline() {
  const { filters, selectedEventId, setSelectedEventId } = useStore()
  const { events, loading, error } = useEvents(filters)

  const grouped = useMemo(() => {
    const sorted = [...events].sort((a, b) => (a.date || '').localeCompare(b.date || ''))
    const map = new Map()
    sorted.forEach((ev) => {
      const key = ev.date?.substring(0, 7) || 'unknown'
      if (!map.has(key)) map.set(key, [])
      map.get(key).push(ev)
    })
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b))
  }, [events])

  if (loading) return <div className={styles.center}><div className="spinner" /><span className={styles.loadingLabel}>Loading events…</span></div>

  if (error) return (
    <div className={styles.center}>
      <div className={styles.errorBox}>
        <strong>Backend not reachable</strong><br />{error}<br />
        <code>cd backend && uvicorn app.main:app --reload</code>
        <br /><br />
        <small>Or run the seed script first:<br /><code>python scripts/seed_sample_data.py</code></small>
      </div>
    </div>
  )

  if (events.length === 0) return (
    <div className="empty-state">
      <div className="empty-icon">⏱</div>
      <div className="empty-label">No events found.<br />Try the <strong>Ingest</strong> tab to load GDELT data,<br />or seed sample data from the backend.</div>
    </div>
  )

  return (
    <div className={styles.wrap}>
      <div className={styles.statsBar}>
        <span className="mono text3">{events.length} events</span>
        {filters.categories.length > 0 && <span className="badge badge-info">{filters.categories.join(', ')}</span>}
        {filters.query && <span className="badge badge-warn">"{filters.query}"</span>}
      </div>

      <div className={styles.axis}>
        <div className={styles.line} />
        {grouped.map(([month, evs]) => (
          <div key={month}>
            <MonthLabel month={month} count={evs.length} />
            {evs.map((ev) => (
              <EventCard key={ev.id} event={ev}
                selected={ev.id === selectedEventId}
                onClick={() => setSelectedEventId(ev.id === selectedEventId ? null : ev.id)}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

function MonthLabel({ month, count }) {
  const [year, m] = month.split('-')
  const name = new Date(parseInt(year), parseInt(m) - 1, 1).toLocaleString('en-IN', { month: 'long' })
  return (
    <div className={styles.monthRow}>
      <div className={styles.monthDot} />
      <span className={styles.monthLabel}>{name} {year}</span>
      <span className={styles.monthCount}>{count}</span>
    </div>
  )
}

function EventCard({ event, selected, onClick }) {
  const cat   = getCatMeta(event.category)
  const tone  = event.tone ?? 0
  const toneStyle = tone < -3 ? styles.toneNeg : tone > 2 ? styles.tonePos : styles.toneNeu

  return (
    <div className={`${styles.card} ${selected ? styles.selected : ''}`} onClick={onClick}>
      <div className={styles.cardMarker} style={{ background: selected ? cat.color : cat.color + '50', borderColor: cat.color }} />
      <div className={styles.cardTop}>
        <span className={styles.catTag} style={{ background: cat.color + '18', color: cat.color }}>{cat.label}</span>
        <span className={styles.title}>{event.title || '(no title)'}</span>
      </div>
      <div className={styles.meta}>
        <span className={styles.date}>{formatDate(event.date)}</span>
        {event.location && <span className={styles.loc}>📍 {event.location}</span>}
        <span className={`${styles.tone} ${toneStyle}`}>TONE {toneLabel(event.tone)}</span>
        <span className={styles.sources}>{event.num_sources ?? 0} src</span>
        <span className={styles.country}>{event.country_a}</span>
      </div>
      {event.summary && <p className={styles.summary}>{event.summary}</p>}
      {selected && <div className={styles.selectedBar} />}
    </div>
  )
}
