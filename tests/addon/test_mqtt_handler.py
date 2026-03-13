"""
Tests for MQTT message handling logic.
Validates Pydantic model parsing, sublabel fallback, ring buffer,
and that malformed payloads never crash the handler.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../addon"))

from src.mqtt_client import FrigateEventPayload, MQTTClient, RingBufferEntry
from src.config import Config
from src.db import init_db


def make_config():
    return Config(
        frigate_url="http://frigate:5000",
        mqtt_host="localhost",
        mqtt_port=1883,
        camera_names=["birdcam"],
        classification_threshold=0.7,
    )


def make_client(tmp_path) -> tuple[MQTTClient, str]:
    db_path = str(tmp_path / "test.db")
    classifier = MagicMock()
    classifier.is_loaded = True
    classifier.classify = AsyncMock(return_value=[{"class_index": 0, "score": 0.96}])

    label_mapper = MagicMock()
    label_mapper.map_results.return_value = [
        {"scientific_name": "Poecile atricapillus", "score": 0.96}
    ]

    client = MQTTClient(
        config=make_config(),
        classifier=classifier,
        label_mapper=label_mapper,
        db_path=db_path,
    )
    return client, db_path


# ---------------------------------------------------------------------------
# Pydantic payload validation
# ---------------------------------------------------------------------------

def test_valid_frigate_event_parses():
    payload = {
        "type": "new",
        "after": {
            "camera": "birdcam",
            "label": "bird",
            "score": 0.85,
            "sub_label": None,
        },
    }
    event = FrigateEventPayload.model_validate(payload)
    assert event.type == "new"
    assert event.after.camera == "birdcam"
    assert event.after.label == "bird"


def test_invalid_payload_raises_validation_error():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        FrigateEventPayload.model_validate({"type": "new", "after": "not_a_dict"})


def test_missing_type_raises_validation_error():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        FrigateEventPayload.model_validate({"after": {"camera": "birdcam", "label": "bird"}})


def test_event_with_sub_label():
    payload = {
        "type": "update",
        "after": {
            "camera": "birdcam",
            "label": "bird",
            "sub_label": "Poecile atricapillus",
            "score": 0.6,
        },
    }
    event = FrigateEventPayload.model_validate(payload)
    assert event.after.sub_label == "Poecile atricapillus"


def test_event_with_sub_label_as_list():
    """Frigate sends sub_label as [label, score] list — must be coerced to string."""
    payload = {
        "type": "update",
        "after": {
            "camera": "birdcam",
            "label": "bird",
            "sub_label": ["Poecile atricapillus", 0.9574999999999999],
            "score": 0.85,
        },
    }
    event = FrigateEventPayload.model_validate(payload)
    assert event.after.sub_label == "Poecile atricapillus"


def test_event_with_empty_sub_label_list():
    payload = {
        "type": "update",
        "after": {
            "camera": "birdcam",
            "label": "bird",
            "sub_label": [],
            "score": 0.85,
        },
    }
    event = FrigateEventPayload.model_validate(payload)
    assert event.after.sub_label is None


# ---------------------------------------------------------------------------
# handle_message — malformed payloads never crash
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_malformed_json_does_not_crash(tmp_path):
    mqtt_client, db_path = make_client(tmp_path)
    await init_db(db_path)

    message = MagicMock()
    message.payload = b"not valid json{"
    message.topic = MagicMock()
    message.topic.__str__ = lambda self: "frigate/events"

    # Should not raise
    await mqtt_client._handle_message(message, MagicMock())
    # Ring buffer should have an error entry
    assert len(mqtt_client.ring_buffer) == 1
    assert mqtt_client.ring_buffer[0]["action"] == "error"


@pytest.mark.asyncio
async def test_non_bird_label_ignored(tmp_path):
    mqtt_client, db_path = make_client(tmp_path)
    await init_db(db_path)

    import json
    message = MagicMock()
    message.payload = json.dumps({
        "type": "new",
        "after": {"camera": "birdcam", "label": "person", "score": 0.9},
    }).encode()
    message.topic = MagicMock()
    message.topic.__str__ = lambda self: "frigate/events"

    await mqtt_client._handle_message(message, MagicMock())
    assert len(mqtt_client.ring_buffer) == 0  # silently ignored


@pytest.mark.asyncio
async def test_wrong_camera_ignored(tmp_path):
    mqtt_client, db_path = make_client(tmp_path)
    await init_db(db_path)

    import json
    message = MagicMock()
    message.payload = json.dumps({
        "type": "new",
        "after": {
            "camera": "frontdoor",  # not in camera_names
            "label": "bird",
            "score": 0.9,
            "id": "evt_ignore",
        },
    }).encode()
    message.topic = MagicMock()
    message.topic.__str__ = lambda self: "frigate/events"

    await mqtt_client._handle_message(message, MagicMock())
    assert len(mqtt_client.ring_buffer) == 0


# ---------------------------------------------------------------------------
# Sublabel fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sublabel_fallback_used_when_below_threshold(tmp_path):
    mqtt_client, db_path = make_client(tmp_path)
    await init_db(db_path)

    # Make classifier return below-threshold score
    mqtt_client._classifier.classify = AsyncMock(return_value=[{"class_index": 0, "score": 0.5}])
    mqtt_client._label_mapper.map_results.return_value = [
        {"scientific_name": "Poecile atricapillus", "score": 0.5}
    ]
    mqtt_client._classifier.is_loaded = True

    import json
    payload = {
        "type": "new",
        "after": {
            "camera": "birdcam",
            "label": "bird",
            "sub_label": "Poecile atricapillus",
            "score": 0.5,
            "id": "evt_sublabel",
        },
    }

    with patch.object(mqtt_client, "_fetch_snapshot", return_value=b"fake_image_bytes"), \
         patch.object(mqtt_client, "_save_snapshot", new=AsyncMock(return_value=None)), \
         patch.object(mqtt_client, "_publish_detection", new=AsyncMock()), \
         patch("src.mqtt_client.upsert_species", new_callable=AsyncMock), \
         patch("src.mqtt_client.insert_detection", new_callable=AsyncMock, return_value=1), \
         patch("src.mqtt_client.is_first_ever_species", new_callable=AsyncMock, return_value=False), \
         patch("src.mqtt_client.detection_exists", new_callable=AsyncMock, return_value=False), \
         patch("src.db.get_display_names", new_callable=AsyncMock, return_value={"Poecile atricapillus": "Black-capped Chickadee"}):

        message = MagicMock()
        message.payload = json.dumps(payload).encode()
        message.topic = MagicMock()
        message.topic.__str__ = lambda self: "frigate/events"

        await mqtt_client._handle_message(message, MagicMock())

    ring = mqtt_client.ring_buffer
    assert len(ring) == 1
    assert ring[0]["action"] == "saved_frigate"


# ---------------------------------------------------------------------------
# Ring buffer
# ---------------------------------------------------------------------------

def test_snapshot_id_allows_frigate_format():
    """Frigate event IDs contain dots, e.g. 1773407461.534049-3st0ju — must not be rejected."""
    import re
    # Pattern copied from mqtt_client._save_snapshot
    pattern = re.compile(r'^[a-zA-Z0-9_\-\.]+$')
    assert pattern.match("1773407461.534049-3st0ju"), "Dot-containing Frigate ID must be allowed"
    assert not pattern.match("../etc/passwd"), "Path traversal must be rejected"
    assert not pattern.match("event id with spaces"), "Spaces must be rejected"


# ---------------------------------------------------------------------------
# MQTT in-memory deduplication (B12)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dedup_event_done_blocks_reprocess(tmp_path):
    """Once an event is saved, subsequent updates must be silently skipped."""
    mqtt_client, db_path = make_client(tmp_path)
    await init_db(db_path)

    mqtt_client._event_done.add("evt_dedup")

    import json
    payload = {
        "type": "update",
        "after": {
            "camera": "birdcam",
            "label": "bird",
            "score": 0.9,
            "id": "evt_dedup",
        },
    }
    message = MagicMock()
    message.payload = json.dumps(payload).encode()

    with patch("src.mqtt_client.detection_exists", new_callable=AsyncMock, return_value=False):
        await mqtt_client._handle_message(message, MagicMock())

    assert len(mqtt_client.ring_buffer) == 0  # skipped without classifying


@pytest.mark.asyncio
async def test_dedup_no_sublabel_set_on_below_threshold(tmp_path):
    """Below-threshold result with no sub_label adds event to _event_no_sublabel."""
    mqtt_client, db_path = make_client(tmp_path)
    await init_db(db_path)

    mqtt_client._classifier.classify = AsyncMock(return_value=[{"class_index": 0, "score": 0.4}])
    mqtt_client._label_mapper.map_results.return_value = [
        {"scientific_name": "Poecile atricapillus", "score": 0.4}
    ]

    import json
    payload = {
        "type": "new",
        "after": {
            "camera": "birdcam",
            "label": "bird",
            "sub_label": None,
            "score": 0.4,
            "id": "evt_below",
        },
    }
    message = MagicMock()
    message.payload = json.dumps(payload).encode()

    with patch.object(mqtt_client, "_fetch_snapshot", return_value=b"fake"), \
         patch("src.mqtt_client.detection_exists", new_callable=AsyncMock, return_value=False):
        await mqtt_client._handle_message(message, MagicMock())

    assert "evt_below" in mqtt_client._event_no_sublabel
    assert "evt_below" not in mqtt_client._event_done


@pytest.mark.asyncio
async def test_dedup_no_sublabel_skips_repeat_without_sublabel(tmp_path):
    """Second update with no sub_label for same event must be skipped."""
    mqtt_client, db_path = make_client(tmp_path)
    await init_db(db_path)

    mqtt_client._event_no_sublabel.add("evt_repeat")

    import json
    payload = {
        "type": "update",
        "after": {
            "camera": "birdcam",
            "label": "bird",
            "sub_label": None,
            "score": 0.4,
            "id": "evt_repeat",
        },
    }
    message = MagicMock()
    message.payload = json.dumps(payload).encode()

    with patch("src.mqtt_client.detection_exists", new_callable=AsyncMock, return_value=False):
        await mqtt_client._handle_message(message, MagicMock())

    assert len(mqtt_client.ring_buffer) == 0  # skipped


@pytest.mark.asyncio
async def test_dedup_allows_retry_when_sublabel_appears(tmp_path):
    """When sub_label appears for an event previously tried without one, process it."""
    mqtt_client, db_path = make_client(tmp_path)
    await init_db(db_path)

    # Previously tried without sub_label
    mqtt_client._event_no_sublabel.add("evt_sublabel_late")

    mqtt_client._classifier.classify = AsyncMock(return_value=[{"class_index": 0, "score": 0.4}])
    mqtt_client._label_mapper.map_results.return_value = [
        {"scientific_name": "Poecile atricapillus", "score": 0.4}
    ]

    import json
    payload = {
        "type": "update",
        "after": {
            "camera": "birdcam",
            "label": "bird",
            "sub_label": ["House Finch", 0.9],
            "score": 0.4,
            "id": "evt_sublabel_late",
        },
    }
    message = MagicMock()
    message.payload = json.dumps(payload).encode()

    with patch.object(mqtt_client, "_fetch_snapshot", return_value=b"fake"), \
         patch.object(mqtt_client, "_save_snapshot", new=AsyncMock(return_value=None)), \
         patch.object(mqtt_client, "_publish_detection", new=AsyncMock()), \
         patch("src.mqtt_client.upsert_species", new_callable=AsyncMock), \
         patch("src.mqtt_client.insert_detection", new_callable=AsyncMock, return_value=1), \
         patch("src.mqtt_client.is_first_ever_species", new_callable=AsyncMock, return_value=False), \
         patch("src.mqtt_client.detection_exists", new_callable=AsyncMock, return_value=False):
        await mqtt_client._handle_message(message, MagicMock())

    # Should have been processed (sub_label unblocked it)
    assert len(mqtt_client.ring_buffer) == 1
    assert mqtt_client.ring_buffer[0]["action"] == "saved_frigate"
    assert "evt_sublabel_late" in mqtt_client._event_done


@pytest.mark.asyncio
async def test_dedup_end_event_clears_sets(tmp_path):
    """End event must remove the event from both dedup sets."""
    mqtt_client, db_path = make_client(tmp_path)
    await init_db(db_path)

    mqtt_client._event_done.add("evt_end")
    mqtt_client._event_no_sublabel.add("evt_end")

    import json
    payload = {"type": "end", "before": {"id": "evt_end"}}
    message = MagicMock()
    message.payload = json.dumps(payload).encode()

    await mqtt_client._handle_message(message, MagicMock())

    assert "evt_end" not in mqtt_client._event_done
    assert "evt_end" not in mqtt_client._event_no_sublabel


# ---------------------------------------------------------------------------
# Frigate sub_label reverse lookup (B13)
# ---------------------------------------------------------------------------

def test_reverse_lookup_common_to_scientific():
    """get_scientific_name returns the scientific name for a known common name."""
    from src.bird_names import get_scientific_name
    assert get_scientific_name("House Finch") == "Haemorhous mexicanus"
    assert get_scientific_name("American Robin") == "Turdus migratorius"
    assert get_scientific_name("Unknown Species XYZ") is None


def test_reverse_lookup_values_are_valid_scientific_names():
    """Every value in COMMON_TO_SCIENTIFIC must be a key in BIRD_NAMES."""
    from src.bird_names import BIRD_NAMES, COMMON_TO_SCIENTIFIC
    for common, sci in COMMON_TO_SCIENTIFIC.items():
        assert sci in BIRD_NAMES, f"{sci} from reverse lookup not in BIRD_NAMES"


@pytest.mark.asyncio
async def test_sublabel_common_name_stored_as_scientific(tmp_path):
    """Frigate sub_label 'House Finch' must be stored as 'Haemorhous mexicanus'."""
    mqtt_client, db_path = make_client(tmp_path)
    await init_db(db_path)

    # Below threshold so AI classification fails — falls back to sub_label
    mqtt_client._classifier.classify = AsyncMock(return_value=[{"class_index": 0, "score": 0.4}])
    mqtt_client._label_mapper.map_results.return_value = [
        {"scientific_name": "Poecile atricapillus", "score": 0.4}
    ]

    saved_args: dict = {}

    async def mock_insert(**kwargs):
        saved_args.update(kwargs)
        return 1

    import json
    payload = {
        "type": "new",
        "after": {
            "camera": "birdcam",
            "label": "bird",
            "sub_label": ["House Finch", 0.9],
            "score": 0.4,
            "id": "evt_hf",
        },
    }
    message = MagicMock()
    message.payload = json.dumps(payload).encode()

    with patch.object(mqtt_client, "_fetch_snapshot", return_value=b"fake"), \
         patch.object(mqtt_client, "_save_snapshot", new=AsyncMock(return_value=None)), \
         patch.object(mqtt_client, "_publish_detection", new=AsyncMock()), \
         patch("src.mqtt_client.upsert_species", new_callable=AsyncMock), \
         patch("src.mqtt_client.insert_detection", new_callable=AsyncMock, side_effect=mock_insert), \
         patch("src.mqtt_client.is_first_ever_species", new_callable=AsyncMock, return_value=False), \
         patch("src.mqtt_client.detection_exists", new_callable=AsyncMock, return_value=False):
        await mqtt_client._handle_message(message, MagicMock())

    assert saved_args.get("scientific_name") == "Haemorhous mexicanus"
    assert saved_args.get("category_name") == "frigate_classified"


def test_ring_buffer_max_size():
    from collections import deque
    from src.mqtt_client import RING_BUFFER_SIZE

    client = MagicMock(spec=MQTTClient)
    client._ring_buffer = deque(maxlen=RING_BUFFER_SIZE)
    client._config = MagicMock()
    client._config.classification_threshold = 0.7

    # Fill beyond capacity
    for i in range(RING_BUFFER_SIZE + 10):
        client._ring_buffer.append(
            RingBufferEntry(
                timestamp="2024-01-01T00:00:00Z",
                camera="birdcam",
                frigate_event_id=f"evt_{i}",
                our_score=0.5,
                threshold=0.7,
                action="below_threshold",
                raw_payload={},
            )
        )

    assert len(client._ring_buffer) == RING_BUFFER_SIZE
