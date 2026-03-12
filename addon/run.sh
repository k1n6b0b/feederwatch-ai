#!/usr/bin/with-contenv bashio
# FeederWatch AI Add-on entrypoint

set -e

bashio::log.info "Starting FeederWatch AI v0.1.0"

# Download model on first startup if missing
if [ ! -f /data/model.tflite ]; then
  bashio::log.info "Model not found — downloading from GitHub release..."
  python3 /app/src/download_model.py || bashio::log.warning "Model download failed — classification disabled"
fi

# HA Supervisor writes /data/options.json — config.py reads it automatically
exec python -m src.main
