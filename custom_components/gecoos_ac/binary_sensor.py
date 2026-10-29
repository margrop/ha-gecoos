from datetime import datetime, timezone

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .const import DOMAIN
from .entity import ApEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    known = set()

    def add_new():
        new = [mac for mac in coordinator.data["aps"] if mac not in known]
        known.update(new)
        async_add_entities(ApOnline(coordinator, mac) for mac in new)

    add_new()
    entry.async_on_unload(coordinator.async_add_listener(add_new))


class ApOnline(ApEntity, BinarySensorEntity):
    """Online state as reported by the AC, so it works while the AP is down."""

    _attr_translation_key = "online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    needs_live = False

    def __init__(self, coordinator, mac):
        super().__init__(coordinator, mac, "online")

    @property
    def is_on(self):
        return self.ap.get("online") == "yes"

    @property
    def extra_state_attributes(self):
        ap = self.ap
        report = ap.get("reporttime")
        return {
            "ip": ap.get("ip"),
            "mac": self.mac,
            "model": ap.get("model"),
            "firmware": ap.get("version"),
            "room": ap.get("room"),
            "location": ap.get("location"),
            "template": ap.get("template"),
            "last_report": datetime.fromtimestamp(report, timezone.utc).isoformat() if report else None,
            "direct_api": ap["live"] is not None,
        }
