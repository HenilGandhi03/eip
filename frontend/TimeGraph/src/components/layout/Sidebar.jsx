import { useState } from 'react'
import { useStore } from '../../store/useStore'
import { useEntities } from '../../hooks/useEntities'
import { CATEGORY_META, getEntityColor, initials } from '../../utils/formatters'
import styles from './Sidebar.module.css'

const CATS = ['ELECTIONS','POLITICS','ECONOMY','PROTEST','CONFLICT','LEGAL','DIPLOMACY','CLIMATE','RELIGION']

const COUNTRIES = [
  { code: 'IND', label: 'India' },
  { code: 'CHN', label: 'China' },
  { code: 'PAK', label: 'Pakistan' },
  { code: 'USA', label: 'United States' },
]

export default function Sidebar() {
  const { filters, toggleCategory, setFilter, setActiveView, setSelectedEntityId } = useStore()
  const { entities } = useEntities()

  return (
    <aside className={styles.sidebar}>
      {/* Categories */}
      <section className={styles.section}>
        <div className={styles.label}>Category</div>
        {CATS.map((id) => {
          const meta = CATEGORY_META[id] || { label: id, color: '#666' }
          const active = filters.categories.includes(id)
          return (
            <div key={id} className={`${styles.row} ${active ? styles.active : ''}`} onClick={() => toggleCategory(id)}>
              <span className={styles.dot} style={{ background: meta.color }} />
              <span className={`${styles.rowLabel} ${active ? styles.activeLabel : ''}`}>{meta.label}</span>
            </div>
          )
        })}
        {filters.categories.length > 0 && (
          <button className={styles.clearAll} onClick={() => setFilter('categories', [])}>Clear filters</button>
        )}
      </section>

      {/* Date range */}
      <section className={styles.section}>
        <div className={styles.label}>Date Range</div>
        <div className={styles.dateRow}>
          <input type="date" className={styles.dateInput} value={filters.startDate || ''} onChange={(e) => setFilter('startDate', e.target.value || null)} />
          <span className={styles.dateSep}>→</span>
          <input type="date" className={styles.dateInput} value={filters.endDate || ''}   onChange={(e) => setFilter('endDate',   e.target.value || null)} />
        </div>
      </section>

      {/* Countries */}
      <section className={styles.section}>
        <div className={styles.label}>Country</div>
        {COUNTRIES.map(({ code, label }) => {
          const active = filters.countries.includes(code)
          return (
            <div key={code} className={`${styles.row} ${active ? styles.active : ''}`}
              onClick={() => {
                const next = active ? filters.countries.filter(c => c !== code) : [...filters.countries, code]
                setFilter('countries', next)
              }}>
              <span className={styles.dot} style={{ background: 'var(--green)' }} />
              <span className={`${styles.rowLabel} ${active ? styles.activeLabel : ''}`}>{label}</span>
              <span className={styles.code}>{code}</span>
            </div>
          )
        })}
      </section>

      {/* Entities */}
      <section className={`${styles.section} ${styles.entitySection}`}>
        <div className={styles.label}>Top Entities</div>
        <div className={styles.entityScroll}>
          {entities.length === 0 ? (
            <div className={styles.noEntities}>Ingest GDELT data to populate entities.</div>
          ) : entities.slice(0, 20).map((en) => (
            <div key={en.id} className={styles.entityRow}
              onClick={() => { setSelectedEntityId(en.id); setActiveView('entities') }}>
              <div className={styles.avatar} style={{ background: getEntityColor(en.type) + '20', color: getEntityColor(en.type) }}>
                {initials(en.name)}
              </div>
              <div className={styles.entityName}>{en.name}</div>
              <div className={styles.entityCount}>{en.frequency}</div>
            </div>
          ))}
        </div>
      </section>
    </aside>
  )
}
