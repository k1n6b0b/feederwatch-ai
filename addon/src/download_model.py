"""
Download model.tflite and labels.txt on first startup.

Model: Google AIY Vision Classifier Birds V1 (MobileNetV2, 224x224, 965 classes)
       Sourced from WhosAtMyFeeder repo (same model, committed directly there)
Labels: Google AIY Birds V1 labelmap CSV → converted to plain text (one name per line)

Run: python3 /app/src/download_model.py
Exit 0: files are in place (downloaded or already present)
Exit 1: one or more files could not be obtained
"""

from __future__ import annotations

import csv
import io
import logging
import os
import sys
import urllib.error
import urllib.request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    stream=sys.stdout,
)
_LOGGER = logging.getLogger("download_model")

# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

MODEL_URL = (
    "https://raw.githubusercontent.com/mmcc-xx/WhosAtMyFeeder/master/model.tflite"
)
MODEL_DEST = "/data/model.tflite"

LABELS_CSV_URL = (
    "https://www.gstatic.com/aihub/tfhub/labelmaps/aiy_birds_V1_labelmap.csv"
)
LABELS_DEST = "/data/labels.txt"

TIMEOUT = 120  # seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_bytes(url: str) -> bytes:
    _LOGGER.info("Downloading %s", url)
    req = urllib.request.Request(url, headers={"User-Agent": "feederwatch-ai/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read()
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error fetching {url}: {exc.reason}") from exc
    except Exception as exc:
        raise RuntimeError(f"Failed to fetch {url}: {exc}") from exc


def _write_atomic(dest: str, data: bytes) -> None:
    tmp = dest + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, dest)
    _LOGGER.info("Saved %s (%d bytes)", dest, os.path.getsize(dest))


def _download_model() -> None:
    data = _fetch_bytes(MODEL_URL)
    _write_atomic(MODEL_DEST, data)


def _download_labels() -> None:
    """Fetch the CSV labelmap and convert to plain-text labels.txt.

    CSV format:  id,name   (header row + 965 entries, ids 0–964)
    Output format: one scientific name per line, line N = class index N.
    Index 964 is the background class (filtered at inference time).
    """
    raw = _fetch_bytes(LABELS_CSV_URL).decode("utf-8")
    reader = csv.DictReader(io.StringIO(raw))
    entries: dict[int, str] = {}
    for row in reader:
        entries[int(row["id"])] = row["name"]

    if not entries:
        raise RuntimeError("Labels CSV was empty or unparseable")

    lines = [entries[i] for i in sorted(entries)]
    _write_atomic(LABELS_DEST, "\n".join(lines).encode("utf-8"))
    _LOGGER.info("Labels converted: %d classes", len(lines))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    all_ok = True

    if os.path.exists(MODEL_DEST):
        _LOGGER.info("Model already present, skipping: %s", MODEL_DEST)
    else:
        try:
            _download_model()
        except Exception as exc:
            _LOGGER.error("Failed to download model: %s", exc)
            all_ok = False

    if os.path.exists(LABELS_DEST):
        _LOGGER.info("Labels already present, skipping: %s", LABELS_DEST)
    else:
        try:
            _download_labels()
        except Exception as exc:
            _LOGGER.error("Failed to download labels: %s", exc)
            all_ok = False

    if not all_ok:
        _LOGGER.error(
            "Model files unavailable. Place model.tflite and labels.txt in "
            "/data/ to enable classification, or check network connectivity."
        )
        return 1

    _LOGGER.info("All model files ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
