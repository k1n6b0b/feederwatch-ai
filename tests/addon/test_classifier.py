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


def make_mock_interpreter(num_classes: int = 2100, quantized_output: bool = False) -> MagicMock:
    interp = MagicMock()
    interp.get_input_details.return_value = [{
        "index": 0,
        "shape": np.array([1, MODEL_INPUT_SIZE, MODEL_INPUT_SIZE, 3]),
        "dtype": np.uint8,  # AiY Birds V1 model uses uint8 input
    }]
    if quantized_output:
        # Simulate uint8 output with AiY Birds V1 quantization (scale=1/256, zero_point=0)
        # score 0.95 → uint8 = round(0.95 / 0.00390625) = 243
        raw = np.zeros(num_classes, dtype=np.uint8)
        raw[42] = 243  # ≈ 0.949
        raw[7] = 210   # ≈ 0.820
        raw[100] = 156 # ≈ 0.609
        output_detail = {
            "index": 1,
            "dtype": np.uint8,
            "quantization_parameters": {
                "scales": np.array([0.00390625], dtype=np.float32),
                "zero_points": np.array([0], dtype=np.int32),
            },
        }
    else:
        raw = np.zeros(num_classes, dtype=np.float32)
        raw[42] = 0.95
        raw[7] = 0.82
        raw[100] = 0.61
        output_detail = {
            "index": 1,
            "dtype": np.float32,
            "quantization_parameters": {
                "scales": np.array([], dtype=np.float32),
                "zero_points": np.array([], dtype=np.int32),
            },
        }
    interp.get_output_details.return_value = [output_detail]
    interp.get_tensor.return_value = np.expand_dims(raw, axis=0)
    return interp


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------

def test_preprocess_produces_correct_shape():
    classifier = BirdClassifier.__new__(BirdClassifier)
    image_bytes = make_jpeg_bytes()
    arr = classifier._preprocess(image_bytes)
    assert arr.shape == (1, MODEL_INPUT_SIZE, MODEL_INPUT_SIZE, 3)
    assert arr.dtype == np.uint8  # AiY Birds V1 expects uint8, not float32


def test_preprocess_uint8_range():
    """Values must be in [0, 255] — AiY Birds V1 model input is uint8."""
    classifier = BirdClassifier.__new__(BirdClassifier)
    image_bytes = make_jpeg_bytes(color=(255, 255, 255))
    arr = classifier._preprocess(image_bytes)
    assert arr.dtype == np.uint8
    assert int(arr.max()) <= 255
    assert int(arr.min()) >= 0


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


def test_classify_sync_dequantizes_uint8_output():
    """Quantized uint8 output must be dequantized to float scores in [0, 1]."""
    classifier = BirdClassifier.__new__(BirdClassifier)
    classifier._interpreter = make_mock_interpreter(quantized_output=True)
    classifier._input_details = classifier._interpreter.get_input_details()
    classifier._output_details = classifier._interpreter.get_output_details()
    classifier._loaded = True

    results = classifier._classify_sync(make_jpeg_bytes())
    assert len(results) > 0
    for r in results:
        assert 0.0 <= r["score"] <= 1.0, f"Dequantized score {r['score']} out of [0,1]"
    assert results[0]["class_index"] == 42
    assert results[0]["score"] == pytest.approx(243 * 0.00390625, abs=0.01)


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
