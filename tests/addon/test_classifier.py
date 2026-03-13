"""
Tests for classifier.py.
Uses mock interpreter and real CC0 fixture images to test the pipeline end-to-end.
"""

from __future__ import annotations

import io
import os
import sys
from unittest.mock import MagicMock

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../addon"))

from src.classifier import BirdClassifier, LabelMapper, MODEL_INPUT_SIZE

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
IMAGES_DIR = os.path.join(FIXTURES_DIR, "images")


def make_jpeg_bytes(width: int = 224, height: int = 224, color: tuple = (100, 150, 200)) -> bytes:
    """Create a minimal valid JPEG in memory."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def make_mock_interpreter(num_classes: int = 2100) -> MagicMock:
    interp = MagicMock()
    interp.get_input_details.return_value = [{
        "index": 0,
        "shape": np.array([1, MODEL_INPUT_SIZE, MODEL_INPUT_SIZE, 3]),
        "dtype": np.float32,
    }]
    scores = np.zeros(num_classes, dtype=np.float32)
    scores[42] = 0.95
    scores[7] = 0.82
    scores[100] = 0.61
    interp.get_output_details.return_value = [{"index": 1}]
    interp.get_tensor.return_value = np.expand_dims(scores, axis=0)
    return interp


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------

def test_preprocess_produces_correct_shape():
    classifier = BirdClassifier.__new__(BirdClassifier)
    image_bytes = make_jpeg_bytes()
    arr = classifier._preprocess(image_bytes)
    assert arr.shape == (1, MODEL_INPUT_SIZE, MODEL_INPUT_SIZE, 3)
    assert arr.dtype == np.float32


def test_preprocess_normalizes_to_0_1():
    classifier = BirdClassifier.__new__(BirdClassifier)
    image_bytes = make_jpeg_bytes(color=(255, 255, 255))
    arr = classifier._preprocess(image_bytes)
    assert arr.max() <= 1.0
    assert arr.min() >= 0.0


def test_preprocess_resizes_arbitrary_input():
    classifier = BirdClassifier.__new__(BirdClassifier)
    image_bytes = make_jpeg_bytes(width=640, height=480)
    arr = classifier._preprocess(image_bytes)
    assert arr.shape == (1, MODEL_INPUT_SIZE, MODEL_INPUT_SIZE, 3)


def test_preprocess_rejects_corrupt_bytes():
    classifier = BirdClassifier.__new__(BirdClassifier)
    with pytest.raises(Exception):
        classifier._preprocess(b"not an image")


# ---------------------------------------------------------------------------
# Classify sync (mocked interpreter)
# ---------------------------------------------------------------------------

def test_classify_sync_returns_top_k():
    classifier = BirdClassifier.__new__(BirdClassifier)
    classifier._interpreter = make_mock_interpreter()
    classifier._input_details = classifier._interpreter.get_input_details()
    classifier._output_details = classifier._interpreter.get_output_details()
    classifier._loaded = True

    image_bytes = make_jpeg_bytes()
    classifier._preprocess(image_bytes)
    results = classifier._classify_sync(image_bytes)

    assert len(results) <= 5
    assert results[0]["score"] >= results[-1]["score"]  # sorted descending
    assert all("score" in r and "class_index" in r for r in results)


def test_classify_sync_shape_mismatch_raises():
    classifier = BirdClassifier.__new__(BirdClassifier)
    interp = make_mock_interpreter()
    # Set wrong expected shape
    interp.get_input_details.return_value = [{
        "index": 0,
        "shape": np.array([1, 300, 300, 3]),  # wrong size
        "dtype": np.float32,
    }]
    classifier._interpreter = interp
    classifier._input_details = interp.get_input_details()
    classifier._output_details = interp.get_output_details()

    image_bytes = make_jpeg_bytes()
    with pytest.raises(ValueError, match="shape mismatch"):
        classifier._classify_sync(image_bytes)


# ---------------------------------------------------------------------------
# Async classify
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_classify_async_not_loaded_raises():
    classifier = BirdClassifier(model_path="/nonexistent/model.tflite")
    # Do not call .load()
    with pytest.raises(RuntimeError, match="not loaded"):
        await classifier.classify(make_jpeg_bytes())


@pytest.mark.asyncio
async def test_classify_async_returns_results():
    # Build classifier directly without calling load() — set up interpreter manually
    classifier = BirdClassifier.__new__(BirdClassifier)
    classifier._model_path = "/fake/model.tflite"
    classifier._num_threads = 4
    from concurrent.futures import ThreadPoolExecutor
    classifier._executor = ThreadPoolExecutor(max_workers=1)
    classifier._interpreter = make_mock_interpreter()
    classifier._input_details = classifier._interpreter.get_input_details()
    classifier._output_details = classifier._interpreter.get_output_details()
    classifier._loaded = True

    results = await classifier.classify(make_jpeg_bytes())
    assert isinstance(results, list)
    assert len(results) > 0
    assert results[0]["score"] > 0


# ---------------------------------------------------------------------------
# Label mapper
# ---------------------------------------------------------------------------

def test_label_mapper_loads_and_maps(tmp_path):
    labels_file = tmp_path / "labels.txt"
    labels_file.write_text("Poecile atricapillus\nSpinus tristis\nSitta carolinensis\n")
    mapper = LabelMapper(str(labels_file))

    assert mapper.get_scientific_name(0) == "Poecile atricapillus"
    assert mapper.get_scientific_name(1) == "Spinus tristis"
    assert mapper.get_scientific_name(99) is None


def test_label_mapper_maps_results(tmp_path):
    labels_file = tmp_path / "labels.txt"
    labels_file.write_text("Poecile atricapillus\nSpinus tristis\n")
    mapper = LabelMapper(str(labels_file))

    raw = [{"class_index": 0, "score": 0.95}, {"class_index": 1, "score": 0.82}]
    mapped = mapper.map_results(raw)
    assert mapped[0]["scientific_name"] == "Poecile atricapillus"
    assert mapped[0]["score"] == pytest.approx(0.95)
    assert mapped[1]["scientific_name"] == "Spinus tristis"


def test_label_mapper_skips_out_of_range(tmp_path):
    labels_file = tmp_path / "labels.txt"
    labels_file.write_text("Poecile atricapillus\n")
    mapper = LabelMapper(str(labels_file))

    raw = [{"class_index": 0, "score": 0.9}, {"class_index": 999, "score": 0.5}]
    mapped = mapper.map_results(raw)
    assert len(mapped) == 1


# ---------------------------------------------------------------------------
# Fixture image smoke test (uses real CC0 images if present)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.skipif(not os.path.isdir(IMAGES_DIR), reason="Fixture images not present")
async def test_pipeline_with_fixture_images():
    """
    Smoke test: preprocess real bird images → classifier input shape is correct.
    Does not require a real model — verifies the image pipeline produces valid tensors.
    """
    classifier = BirdClassifier.__new__(BirdClassifier)
    classifier._interpreter = make_mock_interpreter()
    classifier._input_details = classifier._interpreter.get_input_details()
    classifier._output_details = classifier._interpreter.get_output_details()
    classifier._loaded = True

    for fname in os.listdir(IMAGES_DIR):
        if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        path = os.path.join(IMAGES_DIR, fname)
        with open(path, "rb") as f:
            image_bytes = f.read()
        results = await classifier.classify(image_bytes)
        assert isinstance(results, list), f"Expected list for {fname}"
        assert len(results) > 0, f"Expected results for {fname}"
        assert all(0.0 <= r["score"] <= 1.0 for r in results), f"Scores out of range for {fname}"
