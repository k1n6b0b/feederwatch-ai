"""Constants for FeederWatch AI integration."""

DOMAIN = "feederwatch_ai"

# Config entry keys
CONF_ADDON_URL = "addon_url"  # e.g. http://homeassistant.local:8099

# Default values
DEFAULT_ADDON_URL = "http://homeassistant.local:8099"
DEFAULT_SCAN_INTERVAL = 30  # seconds

# Coordinator update keys
DATA_COORDINATOR = "coordinator"

# Entity unique ID prefixes
SENSOR_UNIQUE_ID_PREFIX = f"{DOMAIN}_sensor"
BINARY_SENSOR_UNIQUE_ID_PREFIX = f"{DOMAIN}_binary_sensor"
IMAGE_UNIQUE_ID_PREFIX = f"{DOMAIN}_image"

# HA event type fired on every new detection
EVENT_NEW_DETECTION = f"{DOMAIN}_detection"

# Notification categories
NOTIFICATION_ID_NEW_SPECIES = f"{DOMAIN}_new_species"
