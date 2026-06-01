import React, { useState } from "react";
import { useStore } from "../../store/useStore";
import { useEntities, useEntityDetail } from "../../hooks/useEntities";
import { getEntityColor, initials, formatDate, confidenceColor } from "../../utils/formatters";
import styles from "./EntitiesView.module.css";

export default function EntitiesView() {
  const [typeFilter, setTypeFilter] = useState("");
  const [query, setQuery]           = useState("");
  const { selectedEntityId, setSelectedEntityId, setSelectedEventId, setActiveView } = useStore();

  const { entities, loading } = useEntities({ entity_type: typeFilter || undefined, q: query || undefined });
  const { entity, events, rels, loading: detailLoading } = useEntityDetail(selectedEntityId);

  const TYPES = ["politician", "organization", "institution", "country", "topic"];

  return (
    <div className={styles.wrap}>
      {/* Entity list */}
      <div className={styles.listPanel}>
        <div className={styles.listHeader}>
          <input
            type="text"
            className={styles.search}
            placeholder="Search entities…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className={styles.typeFilters}>
            <button
              className={`${styles.typeBtn} ${!typeFilter ? styles.activeType : ""}`}
              onClick={() => setTypeFilter("")}
            >All</button>
            {TYPES.map((t) => (
              <button
                key={t}
                className={`${styles.typeBtn} ${typeFilter === t ? styles.activeType : ""}`}
                style={typeFilter === t ? { color: getEntityColor(t) } : {}}
                onClick={() => setTypeFilter(t === typeFilter ? "" : t)}
              >{t}</button>
            ))}
          </div>
        </div>

        <div className={styles.list}>
          {loading ? (
            <div className="empty-state"><div className="spinner" /></div>
          ) : entities.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">⊘</div>
              <div className="empty-label">No entities found.<br />Ingest GDELT data first.</div>
            </div>
          ) : (
            entities.map((en) => (
              <div
                key={en.id}
                className={`${styles.entityRow} ${en.id === selectedEntityId ? styles.active : ""}`}
                onClick={() => setSelectedEntityId(en.id)}
              >
                <div
                  className={styles.avatar}
                  style={{ background: getEntityColor(en.type) + "20", color: getEntityColor(en.type) }}
                >
                  {initials(en.name)}
                </div>
                <div className={styles.entityInfo}>
                  <div className={styles.entityName}>{en.name}</div>
                  <div className={styles.entityMeta}>
                    <span style={{ color: getEntityColor(en.type) }}>{en.type}</span>
                    <span>· {en.frequency} events</span>
                    {en.first_seen && <span>· since {en.first_seen?.substring(0, 7)}</span>}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Entity detail */}
      <div className={styles.detail}>
        {!selectedEntityId ? (
          <div className="empty-state">
            <div className="empty-icon">◉</div>
            <div className="empty-label">Select an entity to explore its events and relationships.</div>
          </div>
        ) : detailLoading ? (
          <div className="empty-state"><div className="spinner" /></div>
        ) : entity ? (
          <EntityDetail
            entity={entity}
            events={events}
            rels={rels}
            onEventClick={(id) => { setSelectedEventId(id); setActiveView("timeline"); }}
          />
        ) : null}
      </div>
    </div>
  );
}

function EntityDetail({ entity, events, rels, onEventClick }) {
  return (
    <div className={styles.detailInner}>
      {/* Header */}
      <div className={styles.detailHeader}>
        <div
          className={styles.bigAvatar}
          style={{ background: getEntityColor(entity.type) + "20", color: getEntityColor(entity.type) }}
        >
          {initials(entity.name)}
        </div>
        <div>
          <div className={styles.detailName}>{entity.name}</div>
          <div className={styles.detailType} style={{ color: getEntityColor(entity.type) }}>{entity.type}</div>
          <div className={styles.detailFreq}>{entity.frequency} total mentions</div>
        </div>
      </div>

      {entity.aliases?.length > 1 && (
        <div className={styles.detailSection}>
          <div className="section-label">Also known as</div>
          <div className={styles.aliases}>
            {entity.aliases.filter((a) => a !== entity.name).map((a) => (
              <span key={a} className="tag">{a}</span>
            ))}
          </div>
        </div>
      )}

      {/* Events */}
      <div className={styles.detailSection}>
        <div className="section-label">Recent Events ({events.length})</div>
        {events.slice(0, 10).map((ev) => (
          <div key={ev.id} className={styles.eventRow} onClick={() => onEventClick(ev.id)}>
            <span className={styles.evDate}>{formatDate(ev.date)}</span>
            <span className={styles.evTitle}>{ev.title || "—"}</span>
          </div>
        ))}
      </div>

      {/* Relationships */}
      <div className={styles.detailSection}>
        <div className="section-label">Observable Relationships ({rels.length})</div>
        {rels.length === 0 ? (
          <p className={styles.noRel}>No co-occurrence relationships found yet.</p>
        ) : (
          rels.slice(0, 8).map((r, i) => (
            <div key={i} className={styles.relRow}>
              <div
                className={styles.relAvatar}
                style={{ background: getEntityColor(r.entity.type) + "20", color: getEntityColor(r.entity.type) }}
              >
                {initials(r.entity.name)}
              </div>
              <div className={styles.relInfo}>
                <div className={styles.relName}>{r.entity.name}</div>
                <div className={styles.relTypeLine}>
                  <span className={styles.relTypeTag}>{r.type?.replace(/_/g, " ")}</span>
                  <span className={styles.relEv}>{r.evidence_count} events</span>
                  <span className={styles.relConf} style={{ color: confidenceColor(r.confidence) }}>
                    {Math.round(r.confidence * 100)}%
                  </span>
                </div>
                <div className="expl-box" style={{ marginTop: 4 }}>
                  <div className="expl-header">⚖ Why connected</div>
                  <div className="expl-rule">{r.explanation}</div>
                  <div className="expl-rule muted">No causal claims are made · co-occurrence only</div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      <div className={styles.detailSection}>
        <div className="disclaimer">
          <strong>Note:</strong> Relationships represent co-occurrence signals from GDELT source articles. They are observable correlations, not implied connections, affiliations, or causal links.
        </div>
      </div>
    </div>
  );
}
