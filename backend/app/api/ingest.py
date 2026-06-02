from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from app.services.gdelt_ingestion import GDELTIngestionService
from app.core.database import get_conn

router = APIRouter()
svc    = GDELTIngestionService()

# In-process run state (single-server MVP; use Redis for multi-worker prod)
_state: dict = {"running": False, "message": "idle", "last_result": None}


async def _run(days_back: int):
    _state["running"] = True
    _state["message"] = f"Fetching GDELT index…"
    try:
        results = await svc.ingest_range(days_back)
        ok    = sum(1 for r in results if r.get("status") == "success")
        total = sum(r.get("records", 0) for r in results if r.get("status") == "success")
        _state["message"]     = f"Done. {ok}/{len(results)} days OK, {total} events stored."
        _state["last_result"] = results
    except Exception as e:
        _state["message"] = f"ERROR: {e}"
    finally:
        _state["running"] = False


@router.post("/trigger")
async def trigger_ingestion(background_tasks: BackgroundTasks, days_back: int = 7):
    """
    Start background GDELT ingestion.
    Poll GET /api/ingest/status to track progress.
    Use days_back=1 for the latest day only (fastest).
    """
    if _state["running"]:
        return {"status": "already_running", "message": _state["message"]}
    background_tasks.add_task(_run, days_back)
    return {
        "status":   "started",
        "days_back": days_back,
        "tip":       "Poll GET /api/ingest/status — or use POST /api/ingest/seed for instant sample data.",
    }


@router.get("/status")
def ingest_status():
    """Real-time ingestion progress."""
    conn = get_conn()
    try:
        total_events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM ingestion_log WHERE status='pending'").fetchone()[0]
        success = conn.execute("SELECT COUNT(*) FROM ingestion_log WHERE status='success'").fetchone()[0]
        errors  = conn.execute("SELECT COUNT(*) FROM ingestion_log WHERE status='error'").fetchone()[0]
        last_err = conn.execute(
            "SELECT error_msg FROM ingestion_log WHERE status='error' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    except Exception:
        total_events = pending = success = errors = 0
        last_err = None

    return {
        "running":         _state["running"],
        "message":         _state["message"],
        "total_events_db": total_events,
        "log_summary":     {"pending": pending, "success": success, "errors": errors},
        "last_error":      last_err[0] if last_err else None,
        "last_result":     _state["last_result"],
    }


@router.post("/day/{date_str}")
async def ingest_day(date_str: str):
    """
    Synchronously ingest one specific date (YYYYMMDD).
    Blocks until complete and returns the result.
    Good for debugging specific dates.
    """
    if len(date_str) != 8 or not date_str.isdigit():
        raise HTTPException(400, "date_str must be YYYYMMDD, e.g. 20240604")
    result = await svc.ingest_day(date_str)
    return result


@router.post("/seed")
async def seed_sample_data():
    """
    Instantly load 13 real India 2024 events WITHOUT downloading anything.
    Use this when GDELT download is unavailable (firewall, slow network, etc.).
    """
    import sys, os, subprocess
    script = os.path.join(
        os.path.dirname(__file__), "../../../scripts/seed_sample_data.py"
    )
    if not os.path.exists(script):
        raise HTTPException(404, f"Seed script not found at {script}")

    result = subprocess.run([sys.executable, script], capture_output=True, text=True)
    if result.returncode != 0:
        raise HTTPException(500, f"Seed failed:\n{result.stderr[-1000:]}")

    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    return {
        "status":       "seeded",
        "total_events": count,
        "output":       result.stdout,
    }


@router.get("/log")
def ingestion_log(limit: int = Query(30, le=100)):
    conn = get_conn()
    rows = conn.execute("""
        SELECT id, CAST(file_date AS VARCHAR), status,
               records_processed, error_msg,
               CAST(created_at AS VARCHAR)
        FROM ingestion_log
        ORDER BY created_at DESC
        LIMIT ?
    """, [limit]).fetchall()
    return [
        {
            "id":       r[0], "date":    r[1], "status":  r[2],
            "records":  r[3], "error":   r[4], "created": r[5],
        }
        for r in rows
    ]
