"""
GDELT Data Ingestion Pipeline
Downloads and processes daily GDELT ZIP files from data.gdeltproject.org

GDELT Event Codebook v2.0:
  https://www.gdeltproject.org/data/documentation/GDELT-Event_Codebook-V2.0.pdf
"""
import logging
import re
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Iterator
from uuid import uuid4

import httpx
import pandas as pd

from app.core.config import settings
from app.core.database import get_conn
from app.services.entity_resolver import EntityResolver
from app.services.relationship_builder import RelationshipBuilder

logger = logging.getLogger(__name__)

# All 58 GDELT 2.0 columns in order
GDELT_COLS = [
    "GlobalEventID","Day","MonthYear","Year","FractionDate",
    "Actor1Code","Actor1Name","Actor1CountryCode","Actor1KnownGroupCode",
    "Actor1EthnicCode","Actor1Religion1Code","Actor1Religion2Code",
    "Actor1Type1Code","Actor1Type2Code","Actor1Type3Code",
    "Actor2Code","Actor2Name","Actor2CountryCode","Actor2KnownGroupCode",
    "Actor2EthnicCode","Actor2Religion1Code","Actor2Religion2Code",
    "Actor2Type1Code","Actor2Type2Code","Actor2Type3Code",
    "IsRootEvent","EventCode","EventBaseCode","EventRootCode",
    "QuadClass","GoldsteinScale","NumMentions","NumSources","NumArticles",
    "AvgTone",
    "Actor1Geo_Type","Actor1Geo_FullName","Actor1Geo_CountryCode",
    "Actor1Geo_ADM1Code","Actor1Geo_ADM2Code","Actor1Geo_Lat","Actor1Geo_Long","Actor1Geo_FeatureID",
    "Actor2Geo_Type","Actor2Geo_FullName","Actor2Geo_CountryCode",
    "Actor2Geo_ADM1Code","Actor2Geo_ADM2Code","Actor2Geo_Lat","Actor2Geo_Long","Actor2Geo_FeatureID",
    "ActionGeo_Type","ActionGeo_FullName","ActionGeo_CountryCode",
    "ActionGeo_ADM1Code","ActionGeo_ADM2Code","ActionGeo_Lat","ActionGeo_Long","ActionGeo_FeatureID",
    "DATEADDED","SOURCEURL",
]

CAMEO_CATEGORIES = {
    "01": "VERBAL_COOPERATION",        "02": "MATERIAL_COOPERATION",
    "03": "PROVIDE_AID",               "04": "CONSULT",
    "05": "DIPLOMATIC_COOPERATION",    "06": "ENGAGE_IN_NEGOTIATION",
    "07": "PROVIDE_STATEMENT",         "08": "APPEAL",
    "09": "INVESTIGATE",               "10": "DEMAND",
    "11": "DISAPPROVE",                "12": "REJECT",
    "13": "THREATEN",                  "14": "PROTEST",
    "15": "EXHIBIT_MILITARY_POSTURE",  "16": "REDUCE_RELATIONS",
    "17": "COERCE",                    "18": "ASSAULT",
    "19": "FIGHT",                     "20": "USE_UNCONVENTIONAL_MASS_VIOLENCE",
}


def _s(val, fallback="") -> str:
    """Safe string — never returns None/nan."""
    if val is None or (isinstance(val, float) and val != val):
        return fallback
    return str(val).strip()


def _f(val) -> float | None:
    try:
        v = float(val)
        return None if v != v else v   # nan → None
    except (TypeError, ValueError):
        return None


def _i(val, fallback=0) -> int:
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return fallback


class GDELTIngestionService:
    def __init__(self):
        self.raw_dir = Path(settings.DATA_RAW_DIR)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.entity_resolver = EntityResolver()
        self.rel_builder     = RelationshipBuilder()

    # ── Discovery ─────────────────────────────────────────────────────────────

    async def get_available_dates(self, days_back: int = 30) -> list[str]:
        """
        Scrape the GDELT index page for available export file dates.
        The index page lists links like: 20240115.export.CSV.zip
        """
        logger.info(f"Fetching GDELT index: {settings.GDELT_INDEX_URL}")
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
                resp = await c.get(settings.GDELT_INDEX_URL)
                resp.raise_for_status()

            # The index page is plain HTML — dates appear in href attributes
            # Pattern: href="20240115.export.CSV.zip"
            dates = re.findall(r'(\d{8})\.export\.CSV\.zip', resp.text)
            dates = sorted(set(dates))

            if not dates:
                logger.error(
                    "No dates found in GDELT index. "
                    "Response preview: " + resp.text[:200]
                )
                return []

            logger.info(f"Found {len(dates)} available dates. Latest 3: {dates[-3:]}")
            return dates[-days_back:]

        except httpx.TimeoutException:
            logger.error("Timeout fetching GDELT index. Check internet connectivity.")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch GDELT index: {e}")
            return []

    # ── Download ──────────────────────────────────────────────────────────────

    async def download_day(self, date_str: str) -> Path | None:
        """Download and cache a GDELT daily ZIP. Returns path or None on failure."""
        url  = f"{settings.GDELT_BASE_URL}/{date_str}.export.CSV.zip"
        dest = self.raw_dir / f"{date_str}.export.CSV.zip"

        if dest.exists() and dest.stat().st_size > 2_000:
            logger.info(f"[{date_str}] Cache hit ({dest.stat().st_size/1024:.0f} KB)")
            return dest

        logger.info(f"[{date_str}] Downloading {url}")
        try:
            async with httpx.AsyncClient(timeout=180, follow_redirects=True) as c:
                resp = await c.get(url)

            if resp.status_code == 404:
                logger.warning(f"[{date_str}] 404 — file not yet available on GDELT servers")
                return None
            if resp.status_code == 403:
                logger.error(
                    f"[{date_str}] 403 Forbidden. "
                    "data.gdeltproject.org may be blocked by your network or firewall. "
                    "Use POST /api/ingest/seed to load sample data instead."
                )
                return None
            resp.raise_for_status()

            size_kb = len(resp.content) / 1024
            if size_kb < 2:
                logger.error(
                    f"[{date_str}] Response only {size_kb:.1f} KB — "
                    "likely blocked. Content: " + resp.text[:100]
                )
                return None

            dest.write_bytes(resp.content)
            logger.info(f"[{date_str}] Saved {size_kb:.0f} KB → {dest.name}")
            return dest

        except httpx.TimeoutException:
            logger.error(f"[{date_str}] Download timed out after 180s")
            return None
        except Exception as e:
            logger.error(f"[{date_str}] Download error: {e}")
            return None

    # ── Parse ─────────────────────────────────────────────────────────────────

    def parse_zip(self, zip_path: Path) -> Iterator[pd.DataFrame]:
        """Stream-parse GDELT ZIP → DataFrame chunks."""
        with zipfile.ZipFile(zip_path) as zf:
            csv_name = next((n for n in zf.namelist() if n.upper().endswith(".CSV")), None)
            if not csv_name:
                logger.error(f"No CSV inside {zip_path.name}")
                return
            with zf.open(csv_name) as f:
                for chunk in pd.read_csv(
                    f, sep="\t", header=None,
                    names=GDELT_COLS, dtype=str,
                    chunksize=settings.BATCH_SIZE,
                    on_bad_lines="skip",
                ):
                    yield chunk

    def filter_events(self, df: pd.DataFrame) -> pd.DataFrame:
        """Keep only rows relevant to FOCUS_COUNTRIES."""
        if not settings.FOCUS_COUNTRIES:
            return df
        mask = (
            df["Actor1CountryCode"].isin(settings.FOCUS_COUNTRIES) |
            df["Actor2CountryCode"].isin(settings.FOCUS_COUNTRIES) |
            df["ActionGeo_CountryCode"].isin(settings.FOCUS_COUNTRIES)
        )
        return df[mask].copy()

    def transform_row(self, row: pd.Series) -> dict | None:
        """Convert one GDELT row to our event schema dict."""
        try:
            raw_date = _s(row.get("Day"))
            if len(raw_date) != 8 or not raw_date.isdigit():
                return None
            ev_date = date(int(raw_date[:4]), int(raw_date[4:6]), int(raw_date[6:8]))

            cameo_root = _s(row.get("EventRootCode"))[:2]
            category   = CAMEO_CATEGORIES.get(cameo_root, "OTHER")

            a1 = _s(row.get("Actor1Name")).title()
            a2 = _s(row.get("Actor2Name")).title()
            loc = _s(row.get("ActionGeo_FullName"))
            loc_short = loc.split(",")[0] if loc else ""
            title = (
                f"{a1} — {category.replace('_',' ').title()} — {a2} in {loc_short}"
                if a1 and a2 and loc_short else
                f"{a1 or 'Unknown'} — {category.replace('_',' ').title()}"
                + (f" in {loc_short}" if loc_short else "")
            )

            return {
                "id":           _s(row.get("GlobalEventID")) or str(uuid4()),
                "date":         ev_date,
                "year":         ev_date.year,
                "month":        ev_date.month,
                "day":          ev_date.day,
                "title":        title[:300],
                "summary":      None,
                "category":     category,
                "cameo_code":   _s(row.get("EventCode")),
                "goldstein":    _f(row.get("GoldsteinScale")),
                "tone":         _f(row.get("AvgTone")),
                "country_a":    _s(row.get("Actor1CountryCode")) or None,
                "country_b":    _s(row.get("Actor2CountryCode")) or None,
                "location":     loc or None,
                "lat":          _f(row.get("ActionGeo_Lat")),
                "lon":          _f(row.get("ActionGeo_Long")),
                "num_mentions": _i(row.get("NumMentions")),
                "num_sources":  _i(row.get("NumSources")),
                "num_articles": _i(row.get("NumArticles")),
                "source_url":   _s(row.get("SOURCEURL")) or None,
            }
        except Exception as e:
            logger.debug(f"Transform error: {e}")
            return None

    # ── Store ─────────────────────────────────────────────────────────────────

    def store_events(self, events: list[dict]) -> int:
        """
        Bulk-insert events into DuckDB.
        DuckDB syntax: ON CONFLICT DO NOTHING (not INSERT OR IGNORE).
        """
        if not events:
            return 0
        conn = get_conn()

        # Register as a temp view and INSERT SELECT — fastest for DuckDB
        df = pd.DataFrame(events)

        # Ensure column types are correct for DuckDB
        df["date"] = pd.to_datetime(df["date"]).dt.date

        conn.register("_staging", df)
        try:
            conn.execute("""
                INSERT INTO events
                    (id, date, year, month, day, title, summary, category, cameo_code,
                     goldstein, tone, country_a, country_b, location, lat, lon,
                     num_mentions, num_sources, num_articles, source_url)
                SELECT
                    id, date, year, month, day, title, summary, category, cameo_code,
                    goldstein, tone, country_a, country_b, location, lat, lon,
                    num_mentions, num_sources, num_articles, source_url
                FROM _staging
                ON CONFLICT (id) DO NOTHING
            """)
            return len(events)
        except Exception as e:
            logger.error(f"Bulk insert failed ({e}), falling back to row-by-row")
            stored = 0
            for ev in events:
                try:
                    conn.execute("""
                        INSERT INTO events
                            (id,date,year,month,day,title,summary,category,cameo_code,
                             goldstein,tone,country_a,country_b,location,lat,lon,
                             num_mentions,num_sources,num_articles,source_url)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT (id) DO NOTHING
                    """, [
                        ev["id"], ev["date"], ev["year"], ev["month"], ev["day"],
                        ev["title"], ev["summary"], ev["category"], ev["cameo_code"],
                        ev["goldstein"], ev["tone"], ev["country_a"], ev["country_b"],
                        ev["location"], ev["lat"], ev["lon"],
                        ev["num_mentions"], ev["num_sources"], ev["num_articles"],
                        ev["source_url"],
                    ])
                    stored += 1
                except Exception:
                    pass
            return stored
        finally:
            try:
                conn.unregister("_staging")
            except Exception:
                pass

    # ── Full pipeline ─────────────────────────────────────────────────────────

    async def ingest_day(self, date_str: str) -> dict:
        """Download → parse → filter → store → entity resolve → build relationships."""
        log_id = str(uuid4())
        conn   = get_conn()

        file_date = datetime.strptime(date_str, "%Y%m%d").date()
        conn.execute("""
            INSERT INTO ingestion_log (id, file_date, file_url, status)
            VALUES (?, ?, ?, 'pending')
            ON CONFLICT (id) DO NOTHING
        """, [log_id, file_date, f"{settings.GDELT_BASE_URL}/{date_str}.export.CSV.zip"])

        try:
            zip_path = await self.download_day(date_str)
            if not zip_path:
                msg = (
                    f"Download failed for {date_str}. "
                    f"Possible causes: (1) data.gdeltproject.org is blocked by your network, "
                    f"(2) date has no GDELT file yet, (3) timeout. "
                    f"Quick fix: POST /api/ingest/seed loads 13 built-in India 2024 events instantly."
                )
                conn.execute(
                    "UPDATE ingestion_log SET status='error', error_msg=? WHERE id=?",
                    [msg, log_id]
                )
                return {"date": date_str, "status": "error", "error": msg}

            total_stored = 0
            total_raw    = 0
            total_filtered = 0

            for chunk in self.parse_zip(zip_path):
                total_raw += len(chunk)
                filtered = self.filter_events(chunk)
                total_filtered += len(filtered)

                if filtered.empty:
                    continue

                records = [self.transform_row(row) for _, row in filtered.iterrows()]
                records = [r for r in records if r is not None]
                stored  = self.store_events(records)
                total_stored += stored

            logger.info(
                f"[{date_str}] raw={total_raw} filtered={total_filtered} stored={total_stored}"
            )

            if total_stored > 0:
                await self.entity_resolver.resolve_from_db(date_str)
                await self.rel_builder.build_from_db(date_str)
            else:
                logger.warning(
                    f"[{date_str}] 0 events stored. "
                    f"Filtered {total_filtered} rows but none passed transform. "
                    f"Check FOCUS_COUNTRIES={settings.FOCUS_COUNTRIES}"
                )

            conn.execute(
                "UPDATE ingestion_log SET status='success', records_processed=? WHERE id=?",
                [total_stored, log_id]
            )
            return {"date": date_str, "status": "success", "records": total_stored,
                    "raw_rows": total_raw, "filtered_rows": total_filtered}

        except Exception as e:
            logger.exception(f"[{date_str}] Ingestion failed")
            conn.execute(
                "UPDATE ingestion_log SET status='error', error_msg=? WHERE id=?",
                [str(e), log_id]
            )
            return {"date": date_str, "status": "error", "error": str(e)}

    async def ingest_range(self, days_back: int = 7) -> list[dict]:
        """Ingest the last N available days from GDELT."""
        dates = await self.get_available_dates(days_back)
        if not dates:
            logger.error(
                "No GDELT dates discoverable. "
                "Check internet access to data.gdeltproject.org"
            )
            return [{"status": "error", "error": "GDELT index unreachable"}]

        logger.info(f"Ingesting {len(dates)} dates: {dates[0]} → {dates[-1]}")
        results = []
        for d in dates:
            result = await self.ingest_day(d)
            results.append(result)
        return results
