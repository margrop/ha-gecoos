"""Gecoos (集客) AC and its managed APs."""

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AcClient, ApClient, ApTracker, GecoosAuthError, GecoosError, new_session, parse_location
from .const import CONF_AP_PASSWORD, DEFAULT_INTERVAL, DOMAIN

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]
_LOGGER = logging.getLogger(__name__)


class GecoosCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self._session = new_session()
        self.ac = AcClient(self._session, entry.data[CONF_HOST],
                           entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
        self._trackers: dict[str, ApTracker] = {}
        super().__init__(
            hass,
            _LOGGER,
            name=entry.title,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_INTERVAL)
            ),
        )

    def _tracker(self, ap: dict) -> ApTracker:
        mac = ap["mac"]
        tracker = self._trackers.get(mac)
        if tracker is None or tracker.client.host != ap["ip"]:
            password = self.entry.data.get(CONF_AP_PASSWORD) or self.entry.data[CONF_PASSWORD]
            tracker = self._trackers[mac] = ApTracker(ApClient(self._session, ap["ip"], password))
        return tracker

    async def _poll_ap(self, ap: dict) -> dict | None:
        try:
            return await self._tracker(ap).poll()
        except GecoosError as exc:
            _LOGGER.debug("AP %s (%s) could not be read: %s", ap.get("name"), ap.get("ip"), exc)
            return None

    async def async_close(self) -> None:
        await self._session.close()

    async def _async_update_data(self):
        try:
            summary = await self.ac.overview()
            aplist = await self.ac.aplist()
        except GecoosAuthError as exc:
            raise ConfigEntryAuthFailed(str(exc)) from exc
        except GecoosError as exc:
            raise UpdateFailed(str(exc)) from exc

        online = [ap for ap in aplist if ap.get("online") == "yes" and ap.get("ip")]
        results = await asyncio.gather(*(self._poll_ap(ap) for ap in online))
        live = {ap["mac"]: result for ap, result in zip(online, results)}

        aps = {}
        for ap in aplist:
            room, location = parse_location(ap.get("name") or ap["mac"], ap.get("model"))
            aps[ap["mac"]] = {
                **ap,
                "room": room,
                "location": location,
                "live": live.get(ap["mac"]),
            }
        readable = [a["live"] for a in aps.values() if a["live"]]
        totals = {
            "ap_total": summary.get("apnum"),
            "ap_online": summary.get("apnum_online"),
            "ap_offline": summary.get("apnum_offline"),
            "clients_ac": summary.get("client_num"),
            "clients": sum(a["clients"] for a in readable) if readable else None,
            "download": round(sum(a["download"] or 0 for a in readable), 1)
            if any(a["download"] is not None for a in readable) else None,
            "upload": round(sum(a["upload"] or 0 for a in readable), 1)
            if any(a["upload"] is not None for a in readable) else None,
            "offline_names": [a["name"] for a in aps.values() if a.get("online") != "yes"],
        }
        return {"aps": aps, "totals": totals}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = GecoosCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_close()
        return True
    return False


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
