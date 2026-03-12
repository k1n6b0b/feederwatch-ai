"""Config flow for FeederWatch AI."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import CONF_ADDON_URL, DEFAULT_ADDON_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def _test_connection(hass, url: str) -> bool:
    """Probe /api/v1/status — returns True if the add-on is reachable."""
    session = async_create_clientsession(hass)
    try:
        async with session.get(
            f"{url.rstrip('/')}/api/v1/status", timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            return resp.status == 200
    except Exception:
        return False


class FeederWatchAIFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for FeederWatch AI."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_ADDON_URL].rstrip("/")

            # Prevent duplicate entries for the same add-on URL
            await self.async_set_unique_id(url)
            self._abort_if_unique_id_configured()

            if not await _test_connection(self.hass, url):
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"FeederWatch AI ({url})",
                    data={CONF_ADDON_URL: url},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ADDON_URL,
                        default=(user_input or {}).get(CONF_ADDON_URL, DEFAULT_ADDON_URL),
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_ADDON_URL].rstrip("/")
            if not await _test_connection(self.hass, url):
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    title=f"FeederWatch AI ({url})",
                    data={CONF_ADDON_URL: url},
                )

        current_url = self._get_reconfigure_entry().data.get(CONF_ADDON_URL, DEFAULT_ADDON_URL)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDON_URL, default=current_url): str}
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> FeederWatchAIOptionsFlow:
        return FeederWatchAIOptionsFlow()


class FeederWatchAIOptionsFlow(config_entries.OptionsFlow):
    """Options flow — push notification target."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "notify_service",
                        default=self.config_entry.options.get("notify_service", ""),
                    ): str,
                    vol.Optional(
                        "notify_new_species_only",
                        default=self.config_entry.options.get("notify_new_species_only", False),
                    ): bool,
                }
            ),
            description_placeholders={
                "notify_hint": "e.g. notify.mobile_app_my_phone — leave blank to disable push notifications"
            },
        )
