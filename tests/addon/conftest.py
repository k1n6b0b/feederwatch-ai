import pytest
import sys
import os

# Required for pytest-asyncio auto mode
pytest_plugins = ["pytest_asyncio"]

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../addon"))


@pytest.fixture(autouse=True)
def reset_api_discovery_cache():
    """Reset module-level discovery cache between tests to prevent cross-test contamination."""
    import src.api as api_module
    api_module._discovery_cache = None
    api_module._discovery_cache_time = 0.0
    yield
    api_module._discovery_cache = None
    api_module._discovery_cache_time = 0.0
