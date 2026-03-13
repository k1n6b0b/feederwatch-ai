"""
Database layer for FeederWatch AI.

Schema v1 — compatible with WhosAtMyFeeder schema for migration.
All queries are async via aiosqlite. Context managers only — no connection leaks.
"""

from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any

import aiosqlite

_LOGGER = logging.getLogger(__name__)

SCHEMA_VERSION = 1

CREATE_META = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
"""

CREATE_SPECIES = """
CREATE TABLE IF NOT EXISTS species (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scientific_name TEXT NOT NULL UNIQUE,
    common_name     TEXT NOT NULL,
    family          TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
)
"""

CREATE_DETECTIONS = """
CREATE TABLE IF NOT EXISTS detections (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    frigate_event_id   TEXT NOT NULL UNIQUE,
    scientific_name    TEXT NOT NULL,
    common_name        TEXT NOT NULL,
    score              REAL,
    category_name      TEXT NOT NULL DEFAULT 'ai_classified',
    camera_name        TEXT NOT NULL,
    snapshot_path      TEXT,
    detected_at        TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (scientific_name) REFERENCES species(scientific_name)
)
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_detections_detected_at ON detections(detected_at)",
    "CREATE INDEX IF NOT EXISTS idx_detections_scientific_name ON detections(scientific_name)",
    "CREATE INDEX IF NOT EXISTS idx_detections_camera ON detections(camera_name)",
    "CREATE INDEX IF NOT EXISTS idx_detections_frigate_event ON detections(frigate_event_id)",
]


async def init_db(db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True) if os.path.dirname(db_path) else None
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")

        current_version = await _get_version(db)
        if current_version == 0:
            await _apply_schema_v1(db)
            await _set_version(db, 1)
            _LOGGER.info("Database initialized at schema v1")
        elif current_version < SCHEMA_VERSION:
            await _migrate(db, current_version)
        else:
            _LOGGER.debug("Database schema up to date (v%d)", current_version)

        await db.commit()


async def _get_version(db: aiosqlite.Connection) -> int:
    row = await db.execute_fetchall("PRAGMA user_version")
    return row[0][0] if row else 0


async def _set_version(db: aiosqlite.Connection, version: int) -> None:
    await db.execute(f"PRAGMA user_version = {version}")


async def _apply_schema_v1(db: aiosqlite.Connection) -> None:
    await db.execute(CREATE_META)
    await db.execute(CREATE_SPECIES)
    await db.execute(CREATE_DETECTIONS)
    for idx in CREATE_INDEXES:
        await db.execute(idx)


async def _migrate(db: aiosqlite.Connection, from_version: int) -> None:
    _LOGGER.info("Migrating database from v%d to v%d", from_version, SCHEMA_VERSION)
    # Future migrations added here as elif from_version == N blocks


# ---------------------------------------------------------------------------
# Species queries
# ---------------------------------------------------------------------------

async def upsert_species(db_path: str, scientific_name: str, common_name: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO species (scientific_name, common_name)
            VALUES (?, ?)
            ON CONFLICT(scientific_name) DO UPDATE SET common_name = excluded.common_name
            """,
            (scientific_name, common_name),
        )
        await db.commit()


async def get_display_names(db_path: str, scientific_names: list[str]) -> dict[str, str]:
    """Batch lookup: scientific_name → common_name. No N+1."""
    if not scientific_names:
        return {}
    placeholders = ",".join("?" * len(scientific_names))
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            f"SELECT scientific_name, common_name FROM species WHERE scientific_name IN ({placeholders})",
            scientific_names,
        )
    return {row["scientific_name"]: row["common_name"] for row in rows}


async def get_all_species(
    db_path: str,
    sort: str = "count",
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    order = {
        "count": "total_detections DESC",
        "recent": "last_seen DESC",
        "alpha": "common_name ASC",
        "first": "first_seen ASC",
    }.get(sort, "total_detections DESC")

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            f"""
            SELECT
                s.scientific_name,
                s.common_name,
                COUNT(d.id)        AS total_detections,
                MIN(d.detected_at) AS first_seen,
                MAX(d.detected_at) AS last_seen,
                MAX(d.score)       AS best_score,
                d.snapshot_path    AS best_snapshot_path,
                (
                    SELECT id FROM detections
                    WHERE scientific_name = s.scientific_name
                    ORDER BY score DESC NULLS LAST
                    LIMIT 1
                ) AS best_detection_id
            FROM species s
            LEFT JOIN detections d ON s.scientific_name = d.scientific_name
            GROUP BY s.scientific_name
            ORDER BY {order}
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
    return [dict(row) for row in rows]


async def get_species_detail(db_path: str, scientific_name: str) -> dict[str, Any] | None:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """
            SELECT
                s.scientific_name,
                s.common_name,
                COUNT(d.id)                                    AS total_detections,
                MIN(d.detected_at)                             AS first_seen,
                MAX(d.detected_at)                             AS last_seen,
                MAX(d.score)                                   AS best_score,
                (
                    SELECT id FROM detections
                    WHERE scientific_name = s.scientific_name
                    ORDER BY score DESC NULLS LAST
                    LIMIT 1
                ) AS best_detection_id,
                json_group_array(
                    json_object(
                        'hour', CAST(strftime('%H', d.detected_at) AS INTEGER),
                        'count', 1
                    )
                ) AS hourly_raw
            FROM species s
            LEFT JOIN detections d ON s.scientific_name = d.scientific_name
            WHERE s.scientific_name = ?
            GROUP BY s.scientific_name
            """,
            (scientific_name,),
        )
    if not rows:
        return None
    row = dict(rows[0])
    # Aggregate hourly counts
    import json as _json
    hourly_raw = _json.loads(row.pop("hourly_raw", "[]"))
    hourly: dict[int, int] = {}
    for entry in hourly_raw:
        h = entry["hour"]
        hourly[h] = hourly.get(h, 0) + 1
    row["hourly_activity"] = [{"hour": h, "count": hourly.get(h, 0)} for h in range(24)]
    return row


async def get_species_phenology(db_path: str, scientific_name: str) -> list[dict[str, Any]]:
    """First and last detection per calendar year for phenology chart."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """
            SELECT
                strftime('%Y', detected_at)           AS year,
                MIN(strftime('%j', detected_at))      AS first_day_of_year,
                MAX(strftime('%j', detected_at))      AS last_day_of_year,
                MIN(detected_at)                      AS first_seen,
                MAX(detected_at)                      AS last_seen,
                COUNT(*)                              AS total
            FROM detections
            WHERE scientific_name = ?
            GROUP BY year
            ORDER BY year
            """,
            (scientific_name,),
        )
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Detection queries
# ---------------------------------------------------------------------------

async def insert_detection(
    db_path: str,
    frigate_event_id: str,
    scientific_name: str,
    common_name: str,
    score: float | None,
    category_name: str,
    camera_name: str,
    snapshot_path: str | None = None,
) -> int:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            INSERT INTO detections
                (frigate_event_id, scientific_name, common_name, score,
                 category_name, camera_name, snapshot_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (frigate_event_id, scientific_name, common_name, score,
             category_name, camera_name, snapshot_path),
        )
        await db.commit()
        return cursor.lastrowid


async def get_recent_detections(
    db_path: str,
    limit: int = 20,
    after_id: int | None = None,
) -> list[dict[str, Any]]:
    """Cursor-based pagination for the live feed."""
    limit = min(limit, 100)
    params: list[Any] = []
    where = ""
    if after_id is not None:
        where = "WHERE d.id > ?"
        params.append(after_id)
    params.append(limit)

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            f"""
            SELECT
                d.id, d.frigate_event_id, d.scientific_name, d.common_name,
                d.score, d.category_name, d.camera_name,
                d.snapshot_path, d.detected_at
            FROM detections d
            {where}
            ORDER BY d.id DESC
            LIMIT ?
            """,
            params,
        )
    return [dict(row) for row in rows]


async def get_daily_detections(
    db_path: str,
    target_date: date,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    limit = min(limit, 100)
    date_str = target_date.isoformat()
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """
            SELECT
                d.id, d.frigate_event_id, d.scientific_name, d.common_name,
                d.score, d.category_name, d.camera_name,
                d.snapshot_path, d.detected_at
            FROM detections d
            WHERE date(d.detected_at) = ?
            ORDER BY d.detected_at DESC
            LIMIT ? OFFSET ?
            """,
            (date_str, limit, offset),
        )
    return [dict(row) for row in rows]


async def get_daily_summary(db_path: str, target_date: date) -> dict[str, Any]:
    """Hourly counts + per-species table for the Daily page."""
    date_str = target_date.isoformat()
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        hourly_rows = await db.execute_fetchall(
            """
            SELECT
                CAST(strftime('%H', detected_at) AS INTEGER) AS hour,
                COUNT(*) AS count
            FROM detections
            WHERE date(detected_at) = ?
            GROUP BY hour
            ORDER BY hour
            """,
            (date_str,),
        )

        species_rows = await db.execute_fetchall(
            """
            SELECT
                scientific_name,
                common_name,
                COUNT(*)        AS count,
                MIN(detected_at) AS first_seen,
                MAX(detected_at) AS last_seen,
                MAX(score)      AS best_score,
                category_name
            FROM detections
            WHERE date(detected_at) = ?
            GROUP BY scientific_name
            ORDER BY count DESC
            """,
            (date_str,),
        )

        total_row = await db.execute_fetchall(
            "SELECT COUNT(*) AS total FROM detections WHERE date(detected_at) = ?",
            (date_str,),
        )

    hourly: dict[int, int] = {row["hour"]: row["count"] for row in hourly_rows}
    hourly_full = [{"hour": h, "count": hourly.get(h, 0)} for h in range(24)]
    total_count = total_row[0]["total"] if total_row else 0
    if total_count == 0:
        peak_hour = {"hour": None}
    else:
        peak_hour = max(hourly_full, key=lambda x: x["count"], default={"hour": None})

    species_list = [dict(row) for row in species_rows]

    # Mark first-ever detections
    first_ever = await _get_first_ever_dates(db_path, [s["scientific_name"] for s in species_list])
    for s in species_list:
        s["is_first_ever"] = first_ever.get(s["scientific_name"], "") == date_str

    return {
        "date": date_str,
        "total_detections": total_row[0]["total"] if total_row else 0,
        "unique_species": len(species_list),
        "peak_hour": peak_hour.get("hour"),
        "hourly": hourly_full,
        "species": species_list,
    }


async def _get_first_ever_dates(db_path: str, scientific_names: list[str]) -> dict[str, str]:
    if not scientific_names:
        return {}
    placeholders = ",".join("?" * len(scientific_names))
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            f"""
            SELECT scientific_name, date(MIN(detected_at)) AS first_date
            FROM detections
            WHERE scientific_name IN ({placeholders})
            GROUP BY scientific_name
            """,
            scientific_names,
        )
    return {row["scientific_name"]: row["first_date"] for row in rows}


async def detection_exists(db_path: str, frigate_event_id: str) -> bool:
    async with aiosqlite.connect(db_path) as db:
        rows = await db.execute_fetchall(
            "SELECT 1 FROM detections WHERE frigate_event_id = ? LIMIT 1",
            (frigate_event_id,),
        )
    return len(rows) > 0


async def delete_detection(db_path: str, detection_id: int) -> dict | None:
    """Delete a detection. Returns result dict or None if not found.

    Auto-removes the species row when no detections remain for that species.
    """
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        # Fetch the scientific_name before deleting
        rows = await db.execute_fetchall(
            "SELECT scientific_name FROM detections WHERE id = ?", (detection_id,)
        )
        if not rows:
            return None
        scientific_name: str = rows[0]["scientific_name"]

        await db.execute("DELETE FROM detections WHERE id = ?", (detection_id,))

        # Check if species has any remaining detections
        count_rows = await db.execute_fetchall(
            "SELECT COUNT(*) AS n FROM detections WHERE scientific_name = ?",
            (scientific_name,),
        )
        remaining = count_rows[0]["n"] if count_rows else 0
        species_deleted = False
        if remaining == 0:
            await db.execute(
                "DELETE FROM species WHERE scientific_name = ?", (scientific_name,)
            )
            species_deleted = True

        await db.commit()
    return {"deleted": True, "id": detection_id, "species_deleted": species_deleted}


async def reclassify_detection(
    db_path: str,
    detection_id: int,
    scientific_name: str,
    common_name: str,
) -> bool:
    """Update detection classification. Preserves original score for audit."""
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            UPDATE detections
            SET scientific_name = ?, common_name = ?, category_name = 'human_reclassified'
            WHERE id = ?
            """,
            (scientific_name, common_name, detection_id),
        )
        await db.commit()
    return cursor.rowcount > 0


async def get_detection_by_id(db_path: str, detection_id: int) -> dict[str, Any] | None:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            "SELECT * FROM detections WHERE id = ?", (detection_id,)
        )
    return dict(rows[0]) if rows else None


async def get_total_detection_count(db_path: str) -> int:
    async with aiosqlite.connect(db_path) as db:
        rows = await db.execute_fetchall("SELECT COUNT(*) AS n FROM detections")
    return rows[0][0] if rows else 0


async def get_db_size_bytes(db_path: str) -> int:
    try:
        return os.path.getsize(db_path)
    except OSError:
        return 0


async def is_first_ever_species(db_path: str, scientific_name: str) -> bool:
    async with aiosqlite.connect(db_path) as db:
        rows = await db.execute_fetchall(
            "SELECT COUNT(*) AS n FROM detections WHERE scientific_name = ?",
            (scientific_name,),
        )
    return (rows[0][0] if rows else 0) == 0


async def get_weekly_heatmap(db_path: str, days: int = 28) -> list[dict[str, Any]]:
    """Day-of-week × hour-of-day counts for the last `days` days.

    Returns [{day: 0–6 (Sun–Sat), hour: 0–23, count: N}].
    """
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """
            SELECT
                CAST(strftime('%w', detected_at) AS INTEGER) AS day,
                CAST(strftime('%H', detected_at) AS INTEGER) AS hour,
                COUNT(*) AS count
            FROM detections
            WHERE detected_at >= datetime('now', ?)
            GROUP BY day, hour
            ORDER BY day, hour
            """,
            (f"-{days} days",),
        )
    return [dict(row) for row in rows]


async def get_species_detections(
    db_path: str,
    scientific_name: str,
    limit: int = 20,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Paginated detections for a species (for photo grid in SpeciesDetail)."""
    limit = min(limit, 100)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """
            SELECT
                id, frigate_event_id, scientific_name, common_name,
                score, category_name, camera_name, snapshot_path, detected_at
            FROM detections
            WHERE scientific_name = ?
            ORDER BY detected_at DESC
            LIMIT ? OFFSET ?
            """,
            (scientific_name, limit, offset),
        )
    return [dict(row) for row in rows]


async def get_seasonal_activity(db_path: str) -> list[dict[str, Any]]:
    """Unique species count and total detections per ISO week for the last 52 weeks.

    Returns [{week: 'YYYY-WW', species: N, detections: N}].
    """
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            """
            SELECT
                strftime('%Y-%W', detected_at)   AS week,
                COUNT(DISTINCT scientific_name)  AS species,
                COUNT(*)                         AS detections
            FROM detections
            WHERE detected_at >= datetime('now', '-52 weeks')
            GROUP BY week
            ORDER BY week
            """
        )
    return [dict(row) for row in rows]
