#!/bin/bash
# FeederWatch AI Add-on entrypoint

set -e

echo "[INFO] Starting FeederWatch AI v0.1.2"

# Download model on first startup if missing
if [ ! -f /data/model.tflite ]; then
  echo "[INFO] Model not found — downloading from GitHub release..."
  python3 /app/src/download_model.py || echo "[WARNING] Model download failed — classification disabled"
fi

# HA Supervisor writes /data/options.json — config.py reads it automatically
exec python -m src.main
