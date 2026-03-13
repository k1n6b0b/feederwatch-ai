"""
Configuration loader for FeederWatch AI Add-on.

Production: reads /data/options.json (injected by HA Supervisor).
Development: reads path from FEEDERWATCH_CONFIG env var.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from urllib.parse import urlparse

_LOGGER = logging.getLogger(__name__)

_OPTIONS_PATH = "/data/options.json"


@dataclass
class Config:
    frigate_api_url: str
    mqtt_host: str
    mqtt_port: int = 1883
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_use_tls: bool = False
    camera_names: list[str] = field(default_factory=list)
    classification_threshold: float = 0.7
    model_path: str = "/data/model.tflite"  # not user-configurable; fixed at install time
    store_snapshots: bool = True
    max_snapshot_storage_mb: int = 500
    bird_present_timeout_minutes: int = 5
    frigate_topic: str = "frigate"
    frigate_clips_ui_url: str | None = None
    mqtt_publish_topic: str = "feederwatch_ai"

    def masked_password(self) -> str | None:
        return "***" if self.mqtt_password else None


def load_config() -> Config:
    env_path = os.environ.get("FEEDERWATCH_CONFIG")
    path = env_path or _OPTIONS_PATH

    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Config file not found at {path}. "
            "Set FEEDERWATCH_CONFIG env var for local development."
        )

    with open(path) as f:
        if path.endswith(".json"):
            data = json.load(f)
        else:
            import yaml  # only needed for dev
            data = yaml.safe_load(f)

    # Support old key name (frigate_url) for backward compatibility with existing installs
    raw_api_url = (data.get("frigate_api_url") or data.get("frigate_url", "")).rstrip("/")
    parsed = urlparse(raw_api_url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"frigate_api_url must use http or https scheme, got: {parsed.scheme!r}"
        )

    # Support old key name (frigate_ui_url) for backward compatibility
    raw_clips_ui_url = (
        data.get("frigate_clips_ui_url") or data.get("frigate_ui_url") or None
    )

    cfg = Config(
        frigate_api_url=raw_api_url,
        mqtt_host=data["mqtt_host"],
        mqtt_port=int(data.get("mqtt_port", 1883)),
        mqtt_username=data.get("mqtt_username") or None,
        mqtt_password=data.get("mqtt_password") or None,
        mqtt_use_tls=bool(data.get("mqtt_use_tls", False)),
        camera_names=[n.lower() for n in data.get("camera_names", [])],
        classification_threshold=float(data.get("classification_threshold", 0.7)),
        model_path="/data/model.tflite",
        store_snapshots=bool(data.get("store_snapshots", True)),
        max_snapshot_storage_mb=int(data.get("max_snapshot_storage_mb", 500)),
        bird_present_timeout_minutes=int(data.get("bird_present_timeout_minutes", 5)),
        frigate_topic=data.get("frigate_topic", "frigate"),
        frigate_clips_ui_url=raw_clips_ui_url,
        mqtt_publish_topic=data.get("mqtt_publish_topic") or "feederwatch_ai",
    )

    _LOGGER.info(
        "Config loaded: frigate=%s mqtt=%s:%s user=%s tls=%s cameras=%s threshold=%s",
        cfg.frigate_api_url,
        cfg.mqtt_host,
        cfg.mqtt_port,
        cfg.mqtt_username or "(anonymous)",
        cfg.mqtt_use_tls,
        cfg.camera_names,
        cfg.classification_threshold,
    )
    return cfg
