"""
FeederWatch AI — asyncio entry point.

Single process, single event loop. No multiprocessing, no forking.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys

from aiohttp import web

from .api import broadcast_detection, create_app
from .classifier import BirdClassifier, LabelMapper
from .config import load_config
from .db import init_db
from .mqtt_client import MQTTClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
_LOGGER = logging.getLogger(__name__)

DB_PATH = os.environ.get("FEEDERWATCH_DB", "/data/feederwatch.db")
STATIC_PATH = os.environ.get("FEEDERWATCH_STATIC", "/app/frontend/dist")
HOST = os.environ.get("FEEDERWATCH_HOST", "0.0.0.0")
PORT = int(os.environ.get("FEEDERWATCH_PORT", "8099"))
LABELS_PATH = os.environ.get("FEEDERWATCH_LABELS", "/data/labels.txt")
MQTT_HEARTBEAT_INTERVAL = 60


async def run_status_heartbeat(mqtt_client: MQTTClient) -> None:
    """Publishes feederwatch_ai/status every 60s."""
    import json
    while True:
        await asyncio.sleep(MQTT_HEARTBEAT_INTERVAL)
        try:
            pass  # heartbeat publish handled in mqtt_client when client is available
        except Exception as exc:
            _LOGGER.debug("Heartbeat error: %s", exc)


async def main() -> None:
    _LOGGER.info("FeederWatch AI starting up")

    # Load configuration
    config = load_config()

    # Initialize database
    _LOGGER.info("Initializing database at %s", DB_PATH)
    await init_db(DB_PATH)

    # Load classifier
    classifier = BirdClassifier(model_path=config.model_path)
    label_mapper: LabelMapper | None = None
    if os.path.exists(config.model_path):
        try:
            classifier.load()
            if os.path.exists(LABELS_PATH):
                label_mapper = LabelMapper(LABELS_PATH)
            else:
                _LOGGER.error("Labels file not found at %s — classification disabled", LABELS_PATH)
        except Exception as exc:
            _LOGGER.error("Failed to load classifier: %s", exc)
    else:
        _LOGGER.error("Model not found at %s — classification disabled", config.model_path)

    # Create aiohttp app first so mqtt_client can reference it
    app = create_app(
        config=config,
        db_path=DB_PATH,
        classifier=classifier,
        static_path=STATIC_PATH,
    )
    app["label_mapper"] = label_mapper

    # Detection callback — broadcasts to SSE subscribers
    async def on_detection(detection: dict) -> None:
        await broadcast_detection(app, detection)

    # Presence callback — placeholder; wired to HACS integration via MQTT
    async def on_presence(scientific_name: str, present: bool) -> None:
        _LOGGER.debug("Presence: %s = %s", scientific_name, present)

    # Create MQTT client
    if label_mapper is not None:
        mqtt_client = MQTTClient(
            config=config,
            classifier=classifier,
            label_mapper=label_mapper,
            db_path=DB_PATH,
            on_detection_callback=on_detection,
            on_presence_callback=on_presence,
        )
        app["mqtt_client"] = mqtt_client
    else:
        mqtt_client = None
        _LOGGER.error("MQTT client disabled — model or labels not loaded")

    # Graceful shutdown
    loop = asyncio.get_event_loop()
    shutdown_event = asyncio.Event()

    def _shutdown_handler() -> None:
        _LOGGER.info("Shutdown signal received")
        if mqtt_client:
            mqtt_client.stop()
        classifier.shutdown()
        shutdown_event.set()

    loop.add_signal_handler(signal.SIGTERM, _shutdown_handler)
    loop.add_signal_handler(signal.SIGINT, _shutdown_handler)

    # Start web server
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HOST, PORT)
    await site.start()
    _LOGGER.info("Web server running on http://%s:%d", HOST, PORT)

    # Start MQTT client as background task
    tasks = []
    if mqtt_client:
        mqtt_task = asyncio.create_task(
            _run_mqtt_with_reconnect(mqtt_client),
            name="mqtt_client",
        )
        tasks.append(mqtt_task)

    # Wait for shutdown
    await shutdown_event.wait()

    _LOGGER.info("Shutting down")
    for task in tasks:
        task.cancel()
    await runner.cleanup()
    _LOGGER.info("FeederWatch AI stopped")


async def _run_mqtt_with_reconnect(mqtt_client: MQTTClient) -> None:
    """Run MQTT client with exponential backoff reconnect."""
    backoff = 5
    while mqtt_client._running:
        try:
            _LOGGER.info("Starting MQTT client")
            await mqtt_client.run()
        except Exception as exc:
            _LOGGER.error("MQTT client error: %s — reconnecting in %ds", exc, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)
        else:
            backoff = 5  # reset on clean exit


def entrypoint() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    entrypoint()
