import React, { useState, useEffect } from "react";
import { api } from "../../utils/api";
import styles from "./IngestView.module.css";

export default function IngestView() {
  const [log,       setLog]       = useState([]);
  const [stats,     setStats]     = useState(null);
  const [daysBack,  setDaysBack]  = useState(7);
  const [singleDay, setSingleDay] = useState("");
  const [loading,   setLoading]   = useState(false);
  const [message,   setMessage]   = useState(null);

  function fetchLog() {
    api.getIngestLog().then(setLog).catch(() => {});
    api.getEventStats().then(setStats).catch(() => {});
  }
  useEffect(() => { fetchLog(); }, []);

  async function handleTrigger() {
    setLoading(true);
    setMessage(null);
    try {
      const r = await api.triggerIngest(daysBack);
      setMessage({ type: "ok", text: `Ingestion started for last ${daysBack} days. Runs in background.` });
      setTimeout(fetchLog, 3000);
    } catch (e) {
      setMessage({ type: "err", text: e.message });
    } finally {
      setLoading(false);
    }
  }

  async function handleIngestDay() {
    if (!singleDay) return;
    const dateStr = singleDay.replace(/-/g, "");
    setLoading(true);
    setMessage(null);
    try {
      const r = await api.ingestDay(dateStr);
      setMessage({ type: "ok", text: `Ingested ${r.records} records for ${r.date}.` });
      fetchLog();
    } catch (e) {
      setMessage({ type: "err", text: e.message });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.inner}>
        <h1 className={styles.heading}>GDELT Data Ingestion</h1>
        <p className={styles.sub}>
          Downloads and processes daily GDELT event ZIP files from{" "}
          <a href="http://data.gdeltproject.org/events/index.html" target="_blank" rel="noopener noreferrer">
            data.gdeltproject.org
          </a>
          . Events are filtered for configured focus countries (default: India).
        </p>

        {/* Stats */}
        {stats && (
          <div className={styles.statsGrid}>
            <StatCard label="Total Events"    value={stats.total_events?.toLocaleString()} />
            <StatCard label="Date Range"      value={`${stats.date_range?.from} → ${stats.date_range?.to}`} />
            <StatCard label="Categories"      value={stats.categories} />
            <StatCard label="Total Mentions"  value={stats.total_mentions?.toLocaleString()} />
          </div>
        )}

        {/* Trigger bulk */}
        <div className={styles.card}>
          <div className={styles.cardTitle}>Bulk Ingest (last N days)</div>
          <p className={styles.cardDesc}>
            Fetches the last N days of GDELT data. Runs as a background task.
            Large ranges (30+ days) may take several minutes.
          </p>
          <div className={styles.row}>
            <label className={styles.fieldLabel}>Days back:</label>
            <input
              type="number"
              min={1} max={90}
              value={daysBack}
              onChange={(e) => setDaysBack(Number(e.target.value))}
              className={styles.numInput}
            />
            <button className={styles.btn} onClick={handleTrigger} disabled={loading}>
              {loading ? <><div className="spinner" style={{ width:12,height:12 }} /> Running…</> : "▶ Start Ingestion"}
            </button>
          </div>
        </div>

        {/* Single day */}
        <div className={styles.card}>
          <div className={styles.cardTitle}>Single Day Ingest</div>
          <p className={styles.cardDesc}>Ingest a specific date. Runs synchronously and returns result immediately.</p>
          <div className={styles.row}>
            <input
              type="date"
              value={singleDay}
              onChange={(e) => setSingleDay(e.target.value)}
              className={styles.dateInput}
              style={{ colorScheme: "dark" }}
            />
            <button className={styles.btn} onClick={handleIngestDay} disabled={loading || !singleDay}>
              {loading ? "Running…" : "▶ Ingest Day"}
            </button>
          </div>
        </div>

        {message && (
          <div className={`${styles.message} ${message.type === "ok" ? styles.msgOk : styles.msgErr}`}>
            {message.text}
          </div>
        )}

        {/* Log */}
        <div className={styles.card}>
          <div className={styles.cardTitleRow}>
            <span className={styles.cardTitle}>Ingestion Log</span>
            <button className={styles.refreshBtn} onClick={fetchLog}>↻ Refresh</button>
          </div>
          {log.length === 0 ? (
            <p className={styles.noLog}>No ingestion runs yet.</p>
          ) : (
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Date</th><th>Status</th><th>Records</th><th>Time</th><th>Error</th>
                </tr>
              </thead>
              <tbody>
                {log.map((row) => (
                  <tr key={row.id}>
                    <td className={styles.mono}>{row.date}</td>
                    <td>
                      <span className={`badge ${row.status === "success" ? "badge-ok" : row.status === "pending" ? "badge-warn" : "badge-error"}`}>
                        {row.status}
                      </span>
                    </td>
                    <td className={styles.mono}>{row.records?.toLocaleString()}</td>
                    <td className={styles.mono}>{row.created_at?.substring(0, 19)}</td>
                    <td className={styles.errorCell}>{row.error || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* GDELT notes */}
        <div className={styles.card}>
          <div className={styles.cardTitle}>Data Source Notes</div>
          <ul className={styles.notesList}>
            <li>GDELT uses the <strong>CAMEO</strong> coding system for event types.</li>
            <li>Events filtered for <code>ActionGeo_CountryCode = IND</code> (configurable in <code>config.py</code>).</li>
            <li>Tone scores range from negative (conflict/negative) to positive (cooperation).</li>
            <li>Goldstein scale: <code>-10</code> (most destabilising) to <code>+10</code> (most cooperative).</li>
            <li>Entity resolution maps variant names to canonical forms (e.g., "PM Modi" → "Narendra Modi").</li>
            <li>Relationships are co-occurrence signals only — <strong>no causal claims</strong> are ever made.</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value }) {
  return (
    <div className={styles.statCard}>
      <div className={styles.statVal}>{value ?? "—"}</div>
      <div className={styles.statKey}>{label}</div>
    </div>
  );
}
