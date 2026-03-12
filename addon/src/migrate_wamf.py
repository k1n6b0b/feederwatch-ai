"""
Migrate a WhosAtMyFeeder speciesid.db to FeederWatch AI schema.

WAMF → FeederWatch AI field mapping:
  detection_time   → detected_at
  display_name     → scientific_name  (WAMF stores scientific name here)
  common_name      → common_name
  score            → score (NULL when 0)
  frigate_event    → frigate_event_id
  camera_name      → camera_name
  score == 0       → category_name = 'frigate_classified'
  score > 0        → category_name = 'ai_classified'
  snapshot_path    → NULL (WAMF does not store snapshots locally)
"""

from __future__ import annotations

import logging

import aiosqlite

_LOGGER = logging.getLogger(__name__)

_SELECT = """
    SELECT detection_time, display_name, common_name, score, frigate_event, camera_name
    FROM detections
"""

_INSERT_SPECIES = """
    INSERT OR IGNORE INTO species (scientific_name, common_name)
    VALUES (?, ?)
"""

_INSERT_DETECTION = """
    INSERT OR IGNORE INTO detections
        (frigate_event_id, scientific_name, common_name, score,
         category_name, camera_name, snapshot_path, detected_at)
    VALUES (?, ?, ?, ?, ?, ?, NULL, ?)
"""


async def migrate_wamf(source_db: str, dest_db: str) -> dict[str, int]:
    """
    Import detections from a WAMF database into dest_db.
    Returns {"imported": N, "skipped": M}.
    Existing rows (duplicate frigate_event_id) are silently skipped.
    """
    imported = 0
    skipped = 0

    async with aiosqlite.connect(source_db) as src:
        src.row_factory = aiosqlite.Row
        async with aiosqlite.connect(dest_db) as dst:
            await dst.execute("PRAGMA foreign_keys=ON")

            try:
                async with src.execute(_SELECT) as cursor:
                    async for row in cursor:
                        scientific_name = row["display_name"] or ""
                        common_name = row["common_name"] or scientific_name
                        raw_score = row["score"]
                        score = float(raw_score) if raw_score else None
                        category = "ai_classified" if score else "frigate_classified"
                        camera = row["camera_name"] or "unknown"
                        frigate_event_id = row["frigate_event"] or ""
                        detected_at = row["detection_time"] or ""

                        if not scientific_name or not frigate_event_id:
                            skipped += 1
                            continue

                        await dst.execute(_INSERT_SPECIES, (scientific_name, common_name))
                        cur = await dst.execute(
                            _INSERT_DETECTION,
                            (
                                frigate_event_id,
                                scientific_name,
                                common_name,
                                score,
                                category,
                                camera,
                                detected_at,
                            ),
                        )
                        if cur.rowcount == 1:
                            imported += 1
                        else:
                            skipped += 1
            except aiosqlite.OperationalError as exc:
                raise RuntimeError(
                    f"Could not read WAMF database — is it a valid speciesid.db? ({exc})"
                ) from exc

            await dst.commit()

    _LOGGER.info("WAMF migration complete: imported=%d skipped=%d", imported, skipped)
    return {"imported": imported, "skipped": skipped}
