"""Configure the AC; the APs are found through it."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import callback

from .api import AcClient, GecoosAuthError, GecoosError, new_session
from .const import (
    CONF_AP_PASSWORD,
    DEFAULT_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_USERNAME,
    DOMAIN,
    MIN_INTERVAL,
)


async def _validate(host: str, username: str, password: str) -> dict:
    """Return form errors; empty when the AC accepts the login."""
    session = new_session()
    try:
        client = AcClient(session, host, username, password)
        await client.login()
        await client.overview()
    except GecoosAuthError:
        return {"base": "invalid_auth"}
    except GecoosError:
        return {"base": "cannot_connect"}
    finally:
        await session.close()
    return {}


class GecoosConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            errors = await _validate(host, user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
            if not errors:
                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME].strip() or DEFAULT_NAME,
                    data={
                        CONF_HOST: host,
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_AP_PASSWORD: user_input.get(CONF_AP_PASSWORD) or "",
                    },
                )
        defaults = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, vol.UNDEFINED)): str,
                    vol.Required(CONF_USERNAME, default=defaults.get(CONF_USERNAME, DEFAULT_USERNAME)): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_AP_PASSWORD): str,
                    vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            errors = await _validate(entry.data[CONF_HOST], entry.data[CONF_USERNAME], user_input[CONF_PASSWORD])
            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_AP_PASSWORD: user_input.get(CONF_AP_PASSWORD) or "",
                    },
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {vol.Required(CONF_PASSWORD): str, vol.Optional(CONF_AP_PASSWORD): str}
            ),
            errors=errors,
            description_placeholders={"title": entry.title},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return GecoosOptionsFlow()


class GecoosOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_INTERVAL)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                        vol.Coerce(int), vol.Range(min=MIN_INTERVAL, max=600)
                    )
                }
            ),
        )
