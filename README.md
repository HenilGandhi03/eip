# Event Intelligence Platform

> Contextual intelligence through structured timelines and verified relationships.

A GDELT-powered platform for exploring world events through timelines, entity relationships, and transparent contextual intelligence.

## Core Philosophy

This is a **context exploration engine**, not a truth machine. It helps you:
- Explore event timelines chronologically
- Discover which entities co-occur across events
- Understand surrounding context for any event
- Analyze recurring patterns in global events

**Every relationship is explained. No causal claims are made.**

---

## Architecture

```
┌─────────────────┐    ┌──────────────────────────────┐
│  React Frontend │────│       FastAPI Backend        │
│  D3.js Graph    │    │  ┌────────────────────────┐  │
│  Timeline UI    │    │  │  GDELT Ingestion        │  │
└─────────────────┘    │  │  Entity Resolver        │  │
                       │  │  Relationship Builder   │  │
                       │  └────────────────────────┘  │
                       │  ┌────────────────────────┐  │
                       │  │  DuckDB (MVP)           │  │
                       │  │  → PostgreSQL (prod)    │  │
                       │  │  → Neo4j (graph)        │  │
                       │  └────────────────────────┘  │
                       └──────────────────────────────┘
                                    │
                       ┌────────────▼───────────┐
                       │  GDELT Project          │
                       │  data.gdeltproject.org  │
                       └────────────────────────┘
```

## Quick Start

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Start the API server
uvicorn app.main:app --reload --port 8000
```

### 2. Ingest GDELT Data

```bash
# Trigger ingestion for last 7 days (India-focused by default)
curl -X POST "http://localhost:8000/api/ingest/trigger?days_back=7"

# Or ingest a specific date
curl -X POST "http://localhost:8000/api/ingest/day/20240604"

# Check ingestion log
curl "http://localhost:8000/api/ingest/log"
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### 4. Docker (all-in-one)

```bash
docker compose up
```

---

## GDELT Data Sources

| Source | URL | Used For |
|--------|-----|---------|
| Events Database | `data.gdeltproject.org/events/` | Event records, actors, locations, tone |
| GKG | `data.gdeltproject.org/gkg/` | Themes, persons, organizations, sentiment |
| Index | `data.gdeltproject.org/events/index.html` | File discovery |

GDELT event data uses the **CAMEO coding system** for event types.
See: [CAMEO Codebook](http://eventdata.parusanalytics.com/cameo.dir/CAMEO.Manual.1.1b3.pdf)

## Configuration

Copy `.env.example` to `.env`:

```env
# Focus countries (CAMEO 3-letter codes)
FOCUS_COUNTRIES=["IND"]

# Optional: Claude AI for event summarization
ANTHROPIC_API_KEY=sk-ant-...

# Database
DATABASE_URL=data/processed/eip.duckdb
```

## API Reference

| Endpoint | Description |
|----------|-------------|
| `GET /api/events` | List events with filters (date, category, country, query) |
| `GET /api/events/{id}` | Single event details |
| `GET /api/events/{id}/related` | Related events (with explainability) |
| `GET /api/events/stats/summary` | Dashboard statistics |
| `GET /api/entities` | List entities |
| `GET /api/entities/{id}/relationships` | Entity relationships (transparent) |
| `GET /api/relationships/graph` | Graph data for D3 visualization |
| `POST /api/ingest/trigger` | Start background GDELT ingestion |
| `GET /api/ingest/log` | Ingestion status log |

## Relationship Transparency

Every relationship in this system includes:

```json
{
  "type": "co_mention",
  "evidence_count": 12,
  "confidence": 0.72,
  "explanation": "Connected because: shared countries: IND; same event category: ELECTIONS",
  "is_causal": false,
  "is_speculative": false,
  "basis": "Co-occurrence and shared context signals from GDELT data only"
}
```

**What we never infer:**
- X caused Y (temporal proximity ≠ causality)
- Hidden coordination (co-occurrence ≠ conspiracy)
- Intent or motivation

## Extending to Production

| Component | MVP | Production |
|-----------|-----|------------|
| Database | DuckDB | PostgreSQL + TimescaleDB |
| Graph | In-memory D3 | Neo4j |
| Search | SQL LIKE | OpenSearch / Meilisearch |
| Entity Resolution | Rule-based | spaCy NER + Claude |
| GKG Integration | Planned | Full GKG pipeline |

## License

MIT. Data from [GDELT Project](https://www.gdeltproject.org/) — open data, free to use.
