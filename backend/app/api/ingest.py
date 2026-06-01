from fastapi import APIRouter, BackgroundTasks, HTTPException
from app.services.gdelt_ingestion import GDELTIngestionService
from app.core.database import get_conn

router = APIRouter()
svc = GDELTIngestionService()


@router.post("/trigger")
async def trigger_ingestion(background_tasks: BackgroundTasks, days_back: int = 7):
    """Trigger background GDELT ingestion for the last N days."""
    background_tasks.add_task(svc.ingest_range, days_back)
    return {"status": "started", "days_back": days_back}


@router.post("/day/{date_str}")
async def ingest_day(date_str: str):
    """Ingest a specific date (YYYYMMDD)."""
    if len(date_str) != 8 or not date_str.isdigit():
        raise HTTPException(400, "date_str must be YYYYMMDD format")
    result = await svc.ingest_day(date_str)
    return result


@router.get("/log")
def ingestion_log(limit: int = 20):
    conn = get_conn()
    rows = conn.execute("""
        SELECT id, file_date, status, records_processed, error_msg,
               CAST(created_at AS VARCHAR)
        FROM ingestion_log
        ORDER BY created_at DESC
        LIMIT ?
    """, [limit]).fetchall()
    return [
        {"id":r[0],"date":str(r[1]),"status":r[2],"records":r[3],"error":r[4],"created_at":r[5]}
        for r in rows
    ]
