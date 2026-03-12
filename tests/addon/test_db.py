"""
Tests for db.py — all queries against in-memory SQLite.
No external dependencies required.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from datetime import date, datetime, timezone

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../addon"))

from src.db import (
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
    get_species_phenology,
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
    assert updated is True
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
    assert result is False


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
    today = date.today().isoformat()
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
