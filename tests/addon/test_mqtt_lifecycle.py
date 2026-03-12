"""
Tests for MQTT reconnect lifecycle in main._run_mqtt_with_reconnect.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiomqtt.exceptions import MqttConnectError  # type: ignore[import]

from src.main import _run_mqtt_with_reconnect


def _make_mqtt_client() -> MagicMock:
    client = MagicMock()
    client._running = True
    client._connected = False
    client._last_error = None
    client._error_type = None
    return client


@pytest.mark.asyncio
async def test_reconnect_loop_runs_on_startup() -> None:
    """Loop body executes even though _running starts False — we use while True."""
    client = _make_mqtt_client()
    client._running = False  # would break the old while mqtt_client._running loop

    call_count = 0

    async def mock_run() -> None:
        nonlocal call_count
        call_count += 1
        raise asyncio.CancelledError

    client.run = mock_run

    with pytest.raises(asyncio.CancelledError):
        await _run_mqtt_with_reconnect(client)

    assert call_count == 1, "run() must be called at least once regardless of _running"


@pytest.mark.asyncio
async def test_reconnect_retries_on_exception() -> None:
    """On OSError, the loop sleeps and retries; second call raises CancelledError."""
    client = _make_mqtt_client()

    calls: list[str] = []

    async def mock_run() -> None:
        calls.append("run")
        if len(calls) == 1:
            raise OSError("connection refused")
        raise asyncio.CancelledError

    client.run = mock_run

    with patch("src.main.asyncio.sleep", new=AsyncMock()):
        with pytest.raises(asyncio.CancelledError):
            await _run_mqtt_with_reconnect(client)

    assert len(calls) == 2, "run() should be called twice (first attempt + retry)"


@pytest.mark.asyncio
async def test_cancelled_error_exits_cleanly() -> None:
    """CancelledError propagates immediately without retry."""
    client = _make_mqtt_client()

    async def mock_run() -> None:
        raise asyncio.CancelledError

    client.run = mock_run

    with pytest.raises(asyncio.CancelledError):
        await _run_mqtt_with_reconnect(client)


@pytest.mark.asyncio
async def test_last_error_set_on_exception() -> None:
    """After an exception, _last_error is set to the exception message."""
    client = _make_mqtt_client()

    async def mock_run() -> None:
        raise OSError("bad host")

    client.run = mock_run

    async def mock_sleep(_: float) -> None:
        raise asyncio.CancelledError

    with patch("src.main.asyncio.sleep", new=mock_sleep):
        with pytest.raises(asyncio.CancelledError):
            await _run_mqtt_with_reconnect(client)

    assert client._last_error == "bad host"


@pytest.mark.asyncio
async def test_connected_false_after_exception() -> None:
    """_connected is not set to True by the reconnect wrapper after a failed run."""
    client = _make_mqtt_client()
    client._connected = False

    async def mock_run() -> None:
        # Simulate partial connect that never flipped _connected
        raise OSError("timeout")

    client.run = mock_run

    async def mock_sleep(_: float) -> None:
        raise asyncio.CancelledError

    with patch("src.main.asyncio.sleep", new=mock_sleep):
        with pytest.raises(asyncio.CancelledError):
            await _run_mqtt_with_reconnect(client)

    assert client._connected is False


@pytest.mark.asyncio
async def test_auth_error_sets_error_type() -> None:
    """MqttConnectError(rc=4) → error_type == 'auth', sleep called with 60."""
    client = _make_mqtt_client()

    async def mock_run() -> None:
        raise MqttConnectError(4)

    client.run = mock_run

    sleep_calls: list[float] = []

    async def mock_sleep(secs: float) -> None:
        sleep_calls.append(secs)
        raise asyncio.CancelledError

    with patch("src.main.asyncio.sleep", new=mock_sleep):
        with pytest.raises(asyncio.CancelledError):
            await _run_mqtt_with_reconnect(client)

    assert client._error_type == "auth"
    assert sleep_calls == [60]


@pytest.mark.asyncio
async def test_auth_error_rc5_sets_error_type() -> None:
    """MqttConnectError(rc=5) → error_type == 'auth'."""
    client = _make_mqtt_client()

    async def mock_run() -> None:
        raise MqttConnectError(5)

    client.run = mock_run

    async def mock_sleep(_: float) -> None:
        raise asyncio.CancelledError

    with patch("src.main.asyncio.sleep", new=mock_sleep):
        with pytest.raises(asyncio.CancelledError):
            await _run_mqtt_with_reconnect(client)

    assert client._error_type == "auth"


@pytest.mark.asyncio
async def test_connection_error_sets_error_type() -> None:
    """OSError → error_type == 'connection', normal backoff sleep called with 5."""
    client = _make_mqtt_client()

    async def mock_run() -> None:
        raise OSError("connection refused")

    client.run = mock_run

    sleep_calls: list[float] = []

    async def mock_sleep(secs: float) -> None:
        sleep_calls.append(secs)
        raise asyncio.CancelledError

    with patch("src.main.asyncio.sleep", new=mock_sleep):
        with pytest.raises(asyncio.CancelledError):
            await _run_mqtt_with_reconnect(client)

    assert client._error_type == "connection"
    assert sleep_calls == [5]


@pytest.mark.asyncio
async def test_error_type_cleared_on_clean_exit() -> None:
    """Clean run() return → error_type is None."""
    client = _make_mqtt_client()
    client._error_type = "connection"  # simulate prior error

    call_count = 0

    async def mock_run() -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return  # clean exit
        raise asyncio.CancelledError

    client.run = mock_run

    with pytest.raises(asyncio.CancelledError):
        await _run_mqtt_with_reconnect(client)

    assert client._error_type is None
