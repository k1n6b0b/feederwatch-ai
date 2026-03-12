"""
Bird classifier using ai-edge-litert (Google's successor to tflite_support).
Runs synchronous inference in a dedicated ThreadPoolExecutor — never blocks the event loop.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np

_LOGGER = logging.getLogger(__name__)

# iNaturalist model input size
MODEL_INPUT_SIZE = 224
TOP_K = 5


class BirdClassifier:
    def __init__(self, model_path: str, num_threads: int = 4) -> None:
        self._model_path = model_path
        self._num_threads = num_threads
        self._interpreter: Any = None
        self._input_details: list[dict] = []
        self._output_details: list[dict] = []
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="classifier")
        self._loaded = False

    def load(self) -> None:
        """Load model synchronously at startup. Call once before serving requests."""
        try:
            from ai_edge_litert.interpreter import Interpreter  # type: ignore[import]
            self._interpreter = Interpreter(
                model_path=self._model_path,
                num_threads=self._num_threads,
            )
            self._interpreter.allocate_tensors()
            self._input_details = self._interpreter.get_input_details()
            self._output_details = self._interpreter.get_output_details()
            self._loaded = True
            _LOGGER.info(
                "Model loaded: %s  input_size=%d",
                self._model_path,
                MODEL_INPUT_SIZE,
            )
        except Exception as exc:
            _LOGGER.error("Failed to load model: %s", exc)
            self._loaded = False
            raise

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    async def classify(self, image_bytes: bytes) -> list[dict[str, Any]]:
        """
        Classify bird image. Returns list of {scientific_name, score} sorted descending.
        Runs sync inference in executor — safe to await from the event loop.
        """
        if not self._loaded:
            raise RuntimeError("Classifier not loaded")
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, self._classify_sync, image_bytes
        )

    def _classify_sync(self, image_bytes: bytes) -> list[dict[str, Any]]:
        """Synchronous classification — runs in ThreadPoolExecutor only."""
        image_array = self._preprocess(image_bytes)
        input_detail = self._input_details[0]

        # Validate input shape
        expected_shape = input_detail["shape"]  # [1, 224, 224, 3]
        if image_array.shape != tuple(expected_shape):
            raise ValueError(
                f"Input shape mismatch: expected {tuple(expected_shape)}, "
                f"got {image_array.shape}"
            )

        self._interpreter.set_tensor(input_detail["index"], image_array)
        self._interpreter.invoke()

        output = self._interpreter.get_tensor(self._output_details[0]["index"])
        scores = output[0]  # shape: [num_classes]

        # Top-K results
        top_indices = np.argsort(scores)[::-1][:TOP_K]
        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score <= 0:
                break
            results.append({
                "class_index": int(idx),
                "score": round(score, 4),
            })
        return results

    def _preprocess(self, image_bytes: bytes) -> np.ndarray:
        """Decode JPEG/PNG bytes → normalized float32 tensor [1, 224, 224, 3]."""
        from PIL import Image  # type: ignore[import]
        import io

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img = img.resize((MODEL_INPUT_SIZE, MODEL_INPUT_SIZE), Image.LANCZOS)
        arr = np.array(img, dtype=np.float32)
        arr = arr / 255.0  # normalize to [0, 1]
        return np.expand_dims(arr, axis=0)  # [1, 224, 224, 3]

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)
        _LOGGER.info("Classifier executor shut down")


class LabelMapper:
    """Maps class indices from the iNaturalist model to scientific names."""

    def __init__(self, labels_path: str) -> None:
        self._labels: list[str] = []
        self._load(labels_path)

    def _load(self, path: str) -> None:
        with open(path) as f:
            self._labels = [line.strip() for line in f if line.strip()]
        _LOGGER.info("Loaded %d labels from %s", len(self._labels), path)

    def get_scientific_name(self, class_index: int) -> str | None:
        if 0 <= class_index < len(self._labels):
            return self._labels[class_index]
        return None

    def map_results(self, raw_results: list[dict]) -> list[dict[str, Any]]:
        """Attach scientific_name to raw classifier output."""
        mapped = []
        for r in raw_results:
            sci_name = self.get_scientific_name(r["class_index"])
            if sci_name:
                mapped.append({"scientific_name": sci_name, "score": r["score"]})
        return mapped
