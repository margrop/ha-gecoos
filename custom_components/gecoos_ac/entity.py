from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo, format_mac
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


def ac_device(coordinator) -> DeviceInfo:
    host = coordinator.entry.data[CONF_HOST]
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.entry.entry_id)},
        name=coordinator.entry.title,
        manufacturer="集客 Gecoos",
        model="AC",
        configuration_url=f"http://{host}/",
    )


class AcEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_device_info = ac_device(coordinator)


class ApEntity(CoordinatorEntity):
    """An entity of one AP; the AP itself is identified by its MAC."""

    _attr_has_entity_name = True
    needs_live = True

    def __init__(self, coordinator, mac: str, key: str) -> None:
        super().__init__(coordinator)
        self.mac = mac
        ap = coordinator.data["aps"][mac]
        self._attr_unique_id = f"{mac}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            connections={(CONNECTION_NETWORK_MAC, format_mac(mac))},
            name=ap.get("name") or mac,
            manufacturer="集客 Gecoos",
            model=ap.get("model"),
            sw_version=ap.get("version"),
            suggested_area=ap.get("room"),
            configuration_url=f"https://{ap['ip']}/" if ap.get("ip") else None,
        )

    @property
    def ap(self) -> dict | None:
        return self.coordinator.data["aps"].get(self.mac)

    @property
    def available(self) -> bool:
        if not super().available or self.ap is None:
            return False
        return not self.needs_live or self.ap["live"] is not None
