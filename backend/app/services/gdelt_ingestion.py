"""
GDELT Data Ingestion Pipeline
Downloads and processes daily GDELT ZIP files.

GDELT Event Database columns (2.0 format — 58 columns):
  https://www.gdeltproject.org/data/documentation/GDELT-Event_Codebook-V2.0.pdf

GDELT GKG columns:
  https://www.gdeltproject.org/data/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf
"""
import asyncio
import hashlib
import io
import logging
import os
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterator
from uuid import uuid4

import httpx
import pandas as pd
from bs4 import BeautifulSoup

from app.core.config import settings
from app.core.database import get_conn
from app.services.entity_resolver import EntityResolver
from app.services.relationship_builder import RelationshipBuilder

logger = logging.getLogger(__name__)

# GDELT 2.0 event column names (58 columns)
GDELT_EVENT_COLUMNS = [
    "GlobalEventID","Day","MonthYear","Year","FractionDate",
    "Actor1Code","Actor1Name","Actor1CountryCode","Actor1KnownGroupCode",
    "Actor1EthnicCode","Actor1Religion1Code","Actor1Religion2Code",
    "Actor1Type1Code","Actor1Type2Code","Actor1Type3Code",
    "Actor2Code","Actor2Name","Actor2CountryCode","Actor2KnownGroupCode",
    "Actor2EthnicCode","Actor2Religion1Code","Actor2Religion2Code",
    "Actor2Type1Code","Actor2Type2Code","Actor2Type3Code",
    "IsRootEvent","EventCode","EventBaseCode","EventRootCode",
    "QuadClass","GoldsteinScale","NumMentions","NumSources","NumArticles",
    "AvgTone","Actor1Geo_Type","Actor1Geo_FullName","Actor1Geo_CountryCode",
    "Actor1Geo_ADM1Code","Actor1Geo_ADM2Code","Actor1Geo_Lat","Actor1Geo_Long",
    "Actor1Geo_FeatureID","Actor2Geo_Type","Actor2Geo_FullName",
    "Actor2Geo_CountryCode","Actor2Geo_ADM1Code","Actor2Geo_ADM2Code",
    "Actor2Geo_Lat","Actor2Geo_Long","Actor2Geo_FeatureID",
    "ActionGeo_Type","ActionGeo_FullName","ActionGeo_CountryCode",
    "ActionGeo_ADM1Code","ActionGeo_ADM2Code","ActionGeo_Lat","ActionGeo_Long",
    "ActionGeo_FeatureID","DATEADDED","SOURCEURL",
]

# CAMEO event code labels (simplified)
CAMEO_CATEGORIES = {
    "01": "VERBAL_COOPERATION",  "02": "MATERIAL_COOPERATION",
    "03": "PROVIDE_AID",         "04": "CONSULT",
    "05": "DIPLOMATIC_COOPERATION", "06": "ENGAGE_IN_NEGOTIATION",
    "07": "PROVIDE_STATEMENT",   "08": "APPEAL",
    "09": "INVESTIGATE",         "10": "DEMAND",
    "11": "DISAPPROVE",          "12": "REJECT",
    "13": "THREATEN",            "14": "PROTEST",
    "15": "EXHIBIT_MILITARY_POSTURE", "16": "REDUCE_RELATIONS",
    "17": "COERCE",              "18": "ASSAULT",
    "19": "FIGHT",               "20": "USE_UNCONVENTIONAL_MASS_VIOLENCE",
}


class GDELTIngestionService:
    def __init__(self):
        self.raw_dir = Path(settings.DATA_RAW_DIR)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.entity_resolver = EntityResolver()
        self.relationship_builder = RelationshipBuilder()

    # ── Discovery ─────────────────────────────────────────────────────────────

    async def get_available_dates(self, days_back: int = 30) -> list[str]:
        """Scrape GDELT index to find available file dates."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(settings.GDELT_INDEX_URL)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        dates = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if href.endswith(".export.CSV.zip"):
                # e.g. 20240115.export.CSV.zip
                file_date = href.split(".")[0]
                if len(file_date) == 8 and file_date.isdigit():
                    dates.append(file_date)
        return sorted(dates)[-days_back:]

    # ── Download ──────────────────────────────────────────────────────────────

    async def download_day(self, date_str: str) -> Path | None:
        """Download and cache a GDELT daily ZIP. Returns local path."""
        url = f"{settings.GDELT_BASE_URL}/{date_str}.export.CSV.zip"
        dest = self.raw_dir / f"{date_str}.export.CSV.zip"

        if dest.exists():
            logger.info(f"[{date_str}] Using cached file.")
            return dest

        logger.info(f"[{date_str}] Downloading {url}")
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                dest.write_bytes(resp.content)
                logger.info(f"[{date_str}] Downloaded {len(resp.content)/1024:.0f} KB")
                return dest
            except httpx.HTTPStatusError as e:
                logger.warning(f"[{date_str}] HTTP {e.response.status_code} — skipping")
                return None

    # ── Parse ─────────────────────────────────────────────────────────────────

    def parse_zip(self, zip_path: Path) -> Iterator[pd.DataFrame]:
        """Stream-parse a GDELT ZIP into DataFrame chunks."""
        with zipfile.ZipFile(zip_path) as zf:
            csv_name = next(n for n in zf.namelist() if n.endswith(".CSV"))
            with zf.open(csv_name) as f:
                for chunk in pd.read_csv(
                    f,
                    sep="\t",
                    header=None,
                    names=GDELT_EVENT_COLUMNS,
                    dtype=str,
                    chunksize=settings.BATCH_SIZE,
                    on_bad_lines="skip",
                ):
                    yield chunk

    def filter_events(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply focus filters: keep events relevant to configured countries."""
        if not settings.FOCUS_COUNTRIES:
            return df
        mask = (
            df["Actor1CountryCode"].isin(settings.FOCUS_COUNTRIES) |
            df["Actor2CountryCode"].isin(settings.FOCUS_COUNTRIES) |
            df["ActionGeo_CountryCode"].isin(settings.FOCUS_COUNTRIES)
        )
        return df[mask].copy()

    def transform_event(self, row: dict) -> dict | None:
        """Transform a raw GDELT row into our schema."""
        try:
            raw_date = str(row.get("Day", ""))
            if len(raw_date) != 8:
                return None
            event_date = date(int(raw_date[:4]), int(raw_date[4:6]), int(raw_date[6:8]))

            cameo_root = str(row.get("EventRootCode", "00"))[:2]
            category = CAMEO_CATEGORIES.get(cameo_root, "OTHER")

            goldstein = float(row.get("GoldsteinScale") or 0)
            tone = float(row.get("AvgTone") or 0)

            return {
                "id": str(row.get("GlobalEventID", uuid4())),
                "date": event_date,
                "year": event_date.year,
                "month": event_date.month,
                "day": event_date.day,
                "category": category,
                "cameo_code": str(row.get("EventCode", "")),
                "goldstein": goldstein,
                "tone": tone,
                "country_a": str(row.get("Actor1CountryCode", "") or ""),
                "country_b": str(row.get("Actor2CountryCode", "") or ""),
                "location": str(row.get("ActionGeo_FullName", "") or ""),
                "lat": self._safe_float(row.get("ActionGeo_Lat")),
                "lon": self._safe_float(row.get("ActionGeo_Long")),
                "num_mentions": int(row.get("NumMentions") or 0),
                "num_sources": int(row.get("NumSources") or 0),
                "num_articles": int(row.get("NumArticles") or 0),
                "source_url": str(row.get("SOURCEURL", "") or ""),
                "title": self._generate_title(row),
                "summary": None,  # Filled by AI summarization service if enabled
            }
        except Exception as e:
            logger.debug(f"Transform error: {e}")
            return None

    def _safe_float(self, val) -> float | None:
        try:
            return float(val) if val and str(val).strip() else None
        except (ValueError, TypeError):
            return None

    def _generate_title(self, row: dict) -> str:
        a1 = str(row.get("Actor1Name", "") or "").title() or "Actor"
        a2 = str(row.get("Actor2Name", "") or "").title()
        cat = CAMEO_CATEGORIES.get(str(row.get("EventRootCode", ""))[:2], "Event")
        loc = str(row.get("ActionGeo_FullName", "") or "")
        loc_str = f" in {loc}" if loc else ""
        if a2:
            return f"{a1} — {cat.replace('_',' ').title()} — {a2}{loc_str}"
        return f"{a1} — {cat.replace('_',' ').title()}{loc_str}"

    # ── Store ─────────────────────────────────────────────────────────────────

    def store_events(self, events: list[dict]) -> int:
        if not events:
            return 0
        conn = get_conn()
        df = pd.DataFrame(events)
        conn.execute("""
            INSERT OR IGNORE INTO events
            SELECT * FROM df
        """)
        return len(events)

    # ── Full pipeline ─────────────────────────────────────────────────────────

    async def ingest_day(self, date_str: str) -> dict:
        """Full pipeline for one day: download → parse → filter → store → resolve entities."""
        log_id = str(uuid4())
        conn = get_conn()
        conn.execute("""
            INSERT INTO ingestion_log (id, file_date, file_url, status)
            VALUES (?, ?, ?, 'pending')
        """, [log_id, date_str, f"{settings.GDELT_BASE_URL}/{date_str}.export.CSV.zip"])

        try:
            zip_path = await self.download_day(date_str)
            if not zip_path:
                raise FileNotFoundError(f"Could not download {date_str}")

            total_stored = 0
            for chunk in self.parse_zip(zip_path):
                filtered = self.filter_events(chunk)
                events = [self.transform_event(r) for _, r in filtered.iterrows()]
                events = [e for e in events if e is not None]
                total_stored += self.store_events(events)

            # Run entity extraction and relationship building
            await self.entity_resolver.resolve_from_db(date_str)
            await self.relationship_builder.build_from_db(date_str)

            conn.execute("""
                UPDATE ingestion_log
                SET status='success', records_processed=?
                WHERE id=?
            """, [total_stored, log_id])

            logger.info(f"[{date_str}] Stored {total_stored} events.")
            return {"date": date_str, "status": "success", "records": total_stored}

        except Exception as e:
            conn.execute("""
                UPDATE ingestion_log SET status='error', error_msg=? WHERE id=?
            """, [str(e), log_id])
            logger.error(f"[{date_str}] Ingestion failed: {e}")
            raise

    async def ingest_range(self, days_back: int = 7):
        """Ingest the last N days of GDELT data."""
        dates = await self.get_available_dates(days_back)
        results = []
        for d in dates:
            try:
                result = await self.ingest_day(d)
                results.append(result)
            except Exception as e:
                results.append({"date": d, "status": "error", "error": str(e)})
        return results
