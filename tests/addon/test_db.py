"""
Tests for db.py — all queries against in-memory SQLite.
No external dependencies required.
"""

from __future__ import annotations

import pytest
from datetime import date

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../addon"))

from src.db import (
    backfill_common_names,
    backfill_reversed_sublabels,
    delete_detection,
    detection_exists,
    get_all_species,
    get_daily_detections,
    get_daily_summary,
    get_db_size_bytes,
    get_detection_by_id,
    get_display_names,
    get_recent_detections,
    get_species_detail,
    get_total_detection_count,
    init_db,
    insert_detection,
    is_first_ever_species,
    reclassify_detection,
    upsert_species,
)

DB = ":memory:"


@pytest.fixture(autouse=True)
async def fresh_db(tmp_path):
    """Each test gets its own temp DB file (in-memory doesn't share across connections)."""
    global DB
    DB = str(tmp_path / "test.db")
    await init_db(DB)
    yield
    DB = ":memory:"


# ---------------------------------------------------------------------------
# Species
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_and_get_display_names():
    await upsert_species(DB, "Poecile atricapillus", "Black-capped Chickadee")
    await upsert_species(DB, "Spinus tristis", "American Goldfinch")

    names = await get_display_names(DB, ["Poecile atricapillus", "Spinus tristis"])
    assert names["Poecile atricapillus"] == "Black-capped Chickadee"
    assert names["Spinus tristis"] == "American Goldfinch"


@pytest.mark.asyncio
async def test_get_display_names_empty():
    names = await get_display_names(DB, [])
    assert names == {}


@pytest.mark.asyncio
async def test_get_display_names_missing():
    names = await get_display_names(DB, ["Unknown species"])
    assert names == {}


@pytest.mark.asyncio
async def test_upsert_species_updates_common_name():
    await upsert_species(DB, "Poecile atricapillus", "Old Name")
    await upsert_species(DB, "Poecile atricapillus", "Black-capped Chickadee")
    names = await get_display_names(DB, ["Poecile atricapillus"])
    assert names["Poecile atricapillus"] == "Black-capped Chickadee"


@pytest.mark.asyncio
async def test_backfill_common_names_updates_stale_rows():
    """backfill_common_names fixes rows where common_name == scientific_name."""
    # Insert species with common_name == scientific_name (pre-backfill state)
    sci = "Poecile atricapillus"
    await upsert_species(DB, sci, sci)  # common_name set to scientific_name
    await insert_detection(
        DB, "evt-backfill-1", sci, sci, score=0.9,
        category_name="ai_classified", camera_name="cam",
    )

    updated = await backfill_common_names(DB)

    # Should have updated at least the species row for this species
    assert updated >= 1
    names = await get_display_names(DB, [sci])
    assert names[sci] != sci  # common name is now different from scientific name
    assert names[sci] == "Black-capped Chickadee"


@pytest.mark.asyncio
async def test_backfill_common_names_idempotent():
    """Running backfill twice does not corrupt already-correct rows."""
    sci = "Poecile atricapillus"
    await upsert_species(DB, sci, sci)

    await backfill_common_names(DB)
    await backfill_common_names(DB)  # second run should be a no-op

    names = await get_display_names(DB, [sci])
    assert names[sci] == "Black-capped Chickadee"


@pytest.mark.asyncio
async def test_backfill_common_names_preserves_correct_rows():
    """backfill_common_names does not touch rows that already have a real common name."""
    sci = "Poecile atricapillus"
    await upsert_species(DB, sci, "Custom Name")

    await backfill_common_names(DB)

    names = await get_display_names(DB, [sci])
    assert names[sci] == "Custom Name"  # unchanged


@pytest.mark.asyncio
async def test_backfill_common_names_fixes_multiple_wrong_rows():
    """New query-first approach fixes ALL wrong rows in the DB, not just BIRD_NAMES iteration order."""
    species = [
        ("Haemorhous mexicanus", "House Finch"),
        ("Cyanocitta cristata", "Blue Jay"),
        ("Cardinalis cardinalis", "Northern Cardinal"),
    ]
    for sci, _ in species:
        await upsert_species(DB, sci, sci)  # store wrong: common_name = scientific_name

    count = await backfill_common_names(DB)

    assert count == len(species)
    names = await get_display_names(DB, [s for s, _ in species])
    for sci, expected_common in species:
        assert names[sci] == expected_common, f"{sci}: expected {expected_common!r}, got {names[sci]!r}"


@pytest.mark.asyncio
async def test_backfill_reversed_sublabels_overwrites_wrong_species_row():
    """Upsert (not INSERT OR IGNORE) corrects an existing species row with wrong common_name."""
    import aiosqlite
    # Simulate the pre-B13/B16 state:
    # AI classifier created a species row with wrong common_name (scientific == common)
    real_sci = "Haemorhous mexicanus"
    await upsert_species(DB, real_sci, real_sci)  # wrong: common = scientific

    # A Frigate sub_label detection was stored verbatim with common name as scientific_name
    wrong_sci = "House Finch"
    await upsert_species(DB, wrong_sci, wrong_sci)
    await insert_detection(
        DB, "evt-reversed-1", wrong_sci, wrong_sci, score=None,
        category_name="frigate_classified", camera_name="cam",
    )

    # Run the migration
    await backfill_reversed_sublabels(DB)

    # The target species row must now have the correct common_name, even though it
    # already existed with wrong data (INSERT OR IGNORE would have silently skipped it)
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        row = await db.execute_fetchall(
            "SELECT common_name FROM species WHERE scientific_name = ?", (real_sci,)
        )
    assert len(row) == 1
    assert row[0]["common_name"] == "House Finch"


# ---------------------------------------------------------------------------
# Detections
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_insert_and_get_detection():
    await upsert_species(DB, "Poecile atricapillus", "Black-capped Chickadee")
    det_id = await insert_detection(
        DB,
        frigate_event_id="evt_001",
        scientific_name="Poecile atricapillus",
        common_name="Black-capped Chickadee",
        score=0.96,
        category_name="ai_classified",
        camera_name="birdcam",
    )
    assert det_id > 0

    detection = await get_detection_by_id(DB, det_id)
    assert detection is not None
    assert detection["scientific_name"] == "Poecile atricapillus"
    assert detection["score"] == pytest.approx(0.96)
    assert detection["frigate_event_id"] == "evt_001"


@pytest.mark.asyncio
async def test_detection_exists():
    await upsert_species(DB, "Poecile atricapillus", "Black-capped Chickadee")
    await insert_detection(DB, "evt_dup", "Poecile atricapillus", "Black-capped Chickadee", 0.9, "ai_classified", "birdcam")
    assert await detection_exists(DB, "evt_dup") is True
    assert await detection_exists(DB, "evt_nonexistent") is False


@pytest.mark.asyncio
async def test_is_first_ever_species():
    await upsert_species(DB, "Poecile atricapillus", "Black-capped Chickadee")
    assert await is_first_ever_species(DB, "Poecile atricapillus") is True
    await insert_detection(DB, "evt_001", "Poecile atricapillus", "Black-capped Chickadee", 0.9, "ai_classified", "birdcam")
    assert await is_first_ever_species(DB, "Poecile atricapillus") is False


@pytest.mark.asyncio
async def test_delete_detection():
    await upsert_species(DB, "Poecile atricapillus", "Black-capped Chickadee")
    det_id = await insert_detection(DB, "evt_del", "Poecile atricapillus", "Black-capped Chickadee", 0.9, "ai_classified", "birdcam")
    result = await delete_detection(DB, det_id)
    assert result is not None
    assert result["deleted"] is True
    assert result["id"] == det_id
    assert await get_detection_by_id(DB, det_id) is None


@pytest.mark.asyncio
async def test_delete_detection_nonexistent():
    assert await delete_detection(DB, 99999) is None


@pytest.mark.asyncio
async def test_delete_detection_cleans_up_species():
    """When the last detection for a species is deleted, the species row is removed too."""
    await upsert_species(DB, "Poecile atricapillus", "Black-capped Chickadee")
    det_id = await insert_detection(DB, "evt_only", "Poecile atricapillus", "Black-capped Chickadee", 0.9, "ai_classified", "cam")
    result = await delete_detection(DB, det_id)
    assert result is not None
    assert result["species_deleted"] is True
    # Species row should be gone
    names = await get_display_names(DB, ["Poecile atricapillus"])
    assert names == {}


@pytest.mark.asyncio
async def test_delete_detection_keeps_species_when_others_remain():
    """Species row survives when other detections still reference it."""
    await upsert_species(DB, "Poecile atricapillus", "Black-capped Chickadee")
    det1 = await insert_detection(DB, "evt_k1", "Poecile atricapillus", "Black-capped Chickadee", 0.9, "ai_classified", "cam")
    await insert_detection(DB, "evt_k2", "Poecile atricapillus", "Black-capped Chickadee", 0.8, "ai_classified", "cam")
    result = await delete_detection(DB, det1)
    assert result is not None
    assert result["species_deleted"] is False
    # Species row must still exist
    names = await get_display_names(DB, ["Poecile atricapillus"])
    assert names["Poecile atricapillus"] == "Black-capped Chickadee"


@pytest.mark.asyncio
async def test_reclassify_detection():
    """Reclassify should update scientific_name, common_name, and set category to human_reclassified."""
    await upsert_species(DB, "Poecile atricapillus", "Black-capped Chickadee")
    det_id = await insert_detection(DB, "evt_rc", "Poecile atricapillus", "Black-capped Chickadee", 0.72, "ai_classified", "cam")
    updated = await reclassify_detection(DB, det_id, "Cyanocitta cristata", "Blue Jay")
    assert updated is not None
    assert updated["reclassified"] is True
    row = await get_detection_by_id(DB, det_id)
    assert row is not None
    assert row["scientific_name"] == "Cyanocitta cristata"
    assert row["common_name"] == "Blue Jay"
    assert row["category_name"] == "human_reclassified"
    # Score preserved (not wiped)
    assert row["score"] == pytest.approx(0.72)


@pytest.mark.asyncio
async def test_reclassify_detection_nonexistent():
    result = await reclassify_detection(DB, 99999, "Cyanocitta cristata", "Blue Jay")
    assert result is None


@pytest.mark.asyncio
async def test_reclassify_deletes_orphaned_species():
    """Reclassifying the only detection away from a species should remove that species row."""
    await upsert_species(DB, "Poecile atricapillus", "Black-capped Chickadee")
    await upsert_species(DB, "Cyanocitta cristata", "Blue Jay")
    det_id = await insert_detection(DB, "evt_orphan", "Poecile atricapillus", "Black-capped Chickadee", 0.9, "ai_classified", "cam")
    result = await reclassify_detection(DB, det_id, "Cyanocitta cristata", "Blue Jay")
    assert result is not None
    assert result["species_deleted"] is True
    # Old species should be gone
    detail = await get_species_detail(DB, "Poecile atricapillus")
    assert detail is None


@pytest.mark.asyncio
async def test_reclassify_keeps_species_with_remaining_detections():
    """Reclassifying one of two detections must NOT delete the species."""
    await upsert_species(DB, "Poecile atricapillus", "Black-capped Chickadee")
    await upsert_species(DB, "Cyanocitta cristata", "Blue Jay")
    await insert_detection(DB, "evt_keep1", "Poecile atricapillus", "Black-capped Chickadee", 0.9, "ai_classified", "cam")
    det_id2 = await insert_detection(DB, "evt_keep2", "Poecile atricapillus", "Black-capped Chickadee", 0.8, "ai_classified", "cam")
    result = await reclassify_detection(DB, det_id2, "Cyanocitta cristata", "Blue Jay")
    assert result is not None
    assert result["species_deleted"] is False
    # Original species still has one detection
    detail = await get_species_detail(DB, "Poecile atricapillus")
    assert detail is not None


@pytest.mark.asyncio
async def test_backfill_reversed_sublabels_fixes_common_as_scientific():
    """Detections where scientific_name is actually a common name get corrected."""
    # Insert a detection with Frigate sub_label stored verbatim as scientific_name
    await upsert_species(DB, "House Finch", "House Finch")
    await insert_detection(DB, "evt_hf", "House Finch", "House Finch", None, "frigate_classified", "cam")
    count = await backfill_reversed_sublabels(DB)
    assert count == 1
    # Detection should now have correct scientific name
    rows_after = await get_species_detail(DB, "Haemorhous mexicanus")
    assert rows_after is not None
    # Old wrong species row should be gone
    wrong = await get_species_detail(DB, "House Finch")
    assert wrong is None


@pytest.mark.asyncio
async def test_backfill_reversed_sublabels_idempotent():
    """Running the migration twice should not double-count or error."""
    await upsert_species(DB, "House Finch", "House Finch")
    await insert_detection(DB, "evt_idem", "House Finch", "House Finch", None, "frigate_classified", "cam")
    await backfill_reversed_sublabels(DB)
    count2 = await backfill_reversed_sublabels(DB)
    assert count2 == 0  # nothing left to fix


@pytest.mark.asyncio
async def test_best_detection_id_prefers_snapshot():
    """get_all_species best_detection_id should prefer a detection with a snapshot."""
    await upsert_species(DB, "Turdus migratorius", "American Robin")
    # Insert low-score detection WITH snapshot first
    id_with_snap = await insert_detection(
        DB, "evt_snap", "Turdus migratorius", "American Robin", 0.5, "ai_classified", "cam",
        snapshot_path="/data/snapshots/evt_snap.jpg",
    )
    # Insert high-score detection WITHOUT snapshot
    await insert_detection(
        DB, "evt_nosnap", "Turdus migratorius", "American Robin", 0.95, "ai_classified", "cam",
        snapshot_path=None,
    )
    species = await get_all_species(DB)
    assert len(species) == 1
    assert species[0]["best_detection_id"] == id_with_snap


@pytest.mark.asyncio
async def test_get_total_detection_count():
    await upsert_species(DB, "Poecile atricapillus", "Black-capped Chickadee")
    assert await get_total_detection_count(DB) == 0
    await insert_detection(DB, "evt_001", "Poecile atricapillus", "Black-capped Chickadee", 0.9, "ai_classified", "birdcam")
    await insert_detection(DB, "evt_002", "Poecile atricapillus", "Black-capped Chickadee", 0.8, "ai_classified", "birdcam")
    assert await get_total_detection_count(DB) == 2


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recent_detections_cursor_pagination():
    await upsert_species(DB, "Poecile atricapillus", "Black-capped Chickadee")
    ids = []
    for i in range(5):
        did = await insert_detection(DB, f"evt_{i:03d}", "Poecile atricapillus", "Black-capped Chickadee", 0.9, "ai_classified", "birdcam")
        ids.append(did)

    # First page
    page1 = await get_recent_detections(DB, limit=3)
    assert len(page1) == 3
    assert page1[0]["id"] == ids[-1]  # most recent first

    # Cursor page — only rows with id > after_id
    page2 = await get_recent_detections(DB, limit=10, after_id=ids[1])
    assert all(r["id"] > ids[1] for r in page2)


@pytest.mark.asyncio
async def test_limit_capped_at_100():
    await upsert_species(DB, "Poecile atricapillus", "Black-capped Chickadee")
    rows = await get_recent_detections(DB, limit=999)
    # Should not raise; DB just returns 0 rows since no detections
    assert isinstance(rows, list)


@pytest.mark.asyncio
async def test_daily_detections_offset_pagination():
    await upsert_species(DB, "Poecile atricapillus", "Black-capped Chickadee")
    for i in range(5):
        await insert_detection(DB, f"evt_d{i}", "Poecile atricapillus", "Black-capped Chickadee", 0.9, "ai_classified", "birdcam")

    page1 = await get_daily_detections(DB, date.today(), limit=3, offset=0)
    page2 = await get_daily_detections(DB, date.today(), limit=3, offset=3)
    assert len(page1) == 3
    assert len(page2) == 2
    # No overlap
    ids1 = {r["id"] for r in page1}
    ids2 = {r["id"] for r in page2}
    assert ids1.isdisjoint(ids2)


# ---------------------------------------------------------------------------
# Daily summary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_daily_summary_empty():
    summary = await get_daily_summary(DB, date.today())
    assert summary["total_detections"] == 0
    assert summary["unique_species"] == 0
    assert len(summary["hourly"]) == 24


@pytest.mark.asyncio
async def test_daily_summary_empty_peak_hour_is_none():
    """Fix 2: all-zero hourly array must not produce peak_hour=0 ("12 am")."""
    summary = await get_daily_summary(DB, date.today())
    assert summary["peak_hour"] is None, (
        "peak_hour should be None on an empty day, not 0 ('12 am')"
    )


@pytest.mark.asyncio
async def test_daily_summary_with_data():
    await upsert_species(DB, "Poecile atricapillus", "Black-capped Chickadee")
    await upsert_species(DB, "Spinus tristis", "American Goldfinch")
    await insert_detection(DB, "evt_a1", "Poecile atricapillus", "Black-capped Chickadee", 0.96, "ai_classified", "birdcam")
    await insert_detection(DB, "evt_a2", "Poecile atricapillus", "Black-capped Chickadee", 0.88, "ai_classified", "birdcam")
    await insert_detection(DB, "evt_b1", "Spinus tristis", "American Goldfinch", 0.91, "ai_classified", "birdcam")

    summary = await get_daily_summary(DB, date.today())
    assert summary["total_detections"] == 3
    assert summary["unique_species"] == 2
    assert len(summary["species"]) == 2


# ---------------------------------------------------------------------------
# Species queries
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_all_species_sort_count():
    await upsert_species(DB, "Poecile atricapillus", "Black-capped Chickadee")
    await upsert_species(DB, "Spinus tristis", "American Goldfinch")
    for i in range(3):
        await insert_detection(DB, f"evt_c{i}", "Poecile atricapillus", "Black-capped Chickadee", 0.9, "ai_classified", "birdcam")
    await insert_detection(DB, "evt_g1", "Spinus tristis", "American Goldfinch", 0.9, "ai_classified", "birdcam")

    species = await get_all_species(DB, sort="count")
    assert species[0]["scientific_name"] == "Poecile atricapillus"
    assert species[0]["total_detections"] == 3


@pytest.mark.asyncio
async def test_get_species_detail_not_found():
    detail = await get_species_detail(DB, "Nonexistent species")
    assert detail is None


@pytest.mark.asyncio
async def test_get_db_size_bytes(tmp_path):
    db_path = str(tmp_path / "size_test.db")
    await init_db(db_path)
    size = await get_db_size_bytes(db_path)
    assert size > 0


@pytest.mark.asyncio
async def test_get_db_size_bytes_missing():
    size = await get_db_size_bytes("/nonexistent/path.db")
    assert size == 0


# ---------------------------------------------------------------------------
# migrate_wamf — common name resolution
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_migrate_wamf_applies_common_names(tmp_path):
    """Imported species must get common names from BIRD_NAMES, not fall back to scientific name."""
    import aiosqlite
    from src.migrate_wamf import migrate_wamf

    # Build a minimal WAMF source DB
    src_path = str(tmp_path / "wamf.db")
    async with aiosqlite.connect(src_path) as src:
        await src.execute(
            "CREATE TABLE detections (detection_time TEXT, display_name TEXT, score REAL, frigate_event TEXT, camera_name TEXT)"
        )
        # Two species in BIRD_NAMES, one unknown
        await src.executemany(
            "INSERT INTO detections VALUES (?, ?, ?, ?, ?)",
            [
                ("2024-01-01 08:00:00", "Poecile atricapillus", 0.9, "evt-001", "birdcam"),
                ("2024-01-01 09:00:00", "Haemorhous mexicanus", 0.8, "evt-002", "birdcam"),
                ("2024-01-01 10:00:00", "Unknown species xyz", 0.7, "evt-003", "birdcam"),
            ],
        )
        await src.commit()

    dest_path = str(tmp_path / "feederwatch.db")
    from src.db import init_db
    await init_db(dest_path)

    result = await migrate_wamf(src_path, dest_path)
    assert result["imported"] == 3

    async with aiosqlite.connect(dest_path) as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall(
            "SELECT scientific_name, common_name FROM species ORDER BY scientific_name"
        )
        names = {r["scientific_name"]: r["common_name"] for r in rows}

    # Known species must have common names, not scientific names
    assert names["Poecile atricapillus"] == "Black-capped Chickadee"
    assert names["Haemorhous mexicanus"] == "House Finch"
    # Unknown species falls back to scientific name (expected)
    assert names["Unknown species xyz"] == "Unknown species xyz"


@pytest.mark.asyncio
async def test_migrate_wamf_overwrites_wrong_common_name(tmp_path):
    """If dest DB already has a species row with wrong common_name, import must correct it."""
    import aiosqlite
    from src.migrate_wamf import migrate_wamf
    from src.db import init_db

    dest_path = str(tmp_path / "feederwatch.db")
    await init_db(dest_path)

    # Pre-populate dest with a wrong common_name (simulates prior partial import)
    async with aiosqlite.connect(dest_path) as db:
        await db.execute(
            "INSERT INTO species (scientific_name, common_name) VALUES (?, ?)",
            ("Poecile atricapillus", "Poecile atricapillus"),  # wrong
        )
        await db.commit()

    src_path = str(tmp_path / "wamf.db")
    async with aiosqlite.connect(src_path) as src:
        await src.execute(
            "CREATE TABLE detections (detection_time TEXT, display_name TEXT, score REAL, frigate_event TEXT, camera_name TEXT)"
        )
        await src.execute(
            "INSERT INTO detections VALUES (?, ?, ?, ?, ?)",
            ("2024-01-01 08:00:00", "Poecile atricapillus", 0.9, "evt-001", "birdcam"),
        )
        await src.commit()

    await migrate_wamf(src_path, dest_path)

    async with aiosqlite.connect(dest_path) as db:
        db.row_factory = aiosqlite.Row
        row = await db.execute_fetchall(
            "SELECT common_name FROM species WHERE scientific_name = 'Poecile atricapillus'"
        )
    assert row[0]["common_name"] == "Black-capped Chickadee"
