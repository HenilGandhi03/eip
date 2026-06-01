import { useRef } from 'react'
import { useStore } from '../../store/useStore'
import styles from './TopBar.module.css'

const NAV = [
  { id: 'timeline', label: 'Timeline' },
  { id: 'graph',    label: 'Graph' },
  { id: 'entities', label: 'Entities' },
  { id: 'ingest',   label: 'Ingest' },
]

export default function TopBar() {
  const { activeView, setActiveView, filters, setFilter } = useStore()
  const inputRef = useRef()

  return (
    <header className={styles.bar}>
      <div className={styles.logo}>EI<span>/</span>PLATFORM</div>

      <nav className={styles.nav}>
        {NAV.map((n) => (
          <button
            key={n.id}
            className={`${styles.navBtn} ${activeView === n.id ? styles.active : ''}`}
            onClick={() => setActiveView(n.id)}
          >{n.label}</button>
        ))}
      </nav>

      <div className={styles.right}>
        <div className={styles.searchWrap}>
          <span className={styles.searchIcon}>⌕</span>
          <input
            ref={inputRef}
            type="text"
            placeholder="Search events, entities, topics…"
            value={filters.query}
            onChange={(e) => setFilter('query', e.target.value)}
            className={styles.searchInput}
          />
          {filters.query && (
            <button className={styles.clearBtn} onClick={() => { setFilter('query', ''); inputRef.current?.focus() }}>✕</button>
          )}
        </div>
        <div className={styles.statusDot} title="GDELT data source" />
        <span className={styles.statusLabel}>GDELT LIVE</span>
      </div>
    </header>
  )
}
