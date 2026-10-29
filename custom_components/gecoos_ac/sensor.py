from dataclasses import dataclass
from datetime import timedelta
from typing import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfDataRate
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import AcEntity, ApEntity


@dataclass(frozen=True, kw_only=True)
class GecoosSensorDescription(SensorEntityDescription):
    value: Callable[[dict], object]
    needs_live: bool = True


RATE = {
    "device_class": SensorDeviceClass.DATA_RATE,
    "state_class": SensorStateClass.MEASUREMENT,
    "native_unit_of_measurement": UnitOfDataRate.KILOBITS_PER_SECOND,
    "suggested_unit_of_measurement": UnitOfDataRate.MEGABITS_PER_SECOND,
    "suggested_display_precision": 2,
}

AP_SENSORS = [
    GecoosSensorDescription(key="clients", translation_key="clients", icon="mdi:devices",
                            state_class=SensorStateClass.MEASUREMENT,
                            value=lambda ap: ap["live"]["clients"]),
    GecoosSensorDescription(key="download", translation_key="download", icon="mdi:download",
                            value=lambda ap: ap["live"]["download"], **RATE),
    GecoosSensorDescription(key="upload", translation_key="upload", icon="mdi:upload",
                            value=lambda ap: ap["live"]["upload"], **RATE),
    GecoosSensorDescription(key="load", translation_key="load", icon="mdi:gauge",
                            state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=2,
                            value=lambda ap: ap["live"]["load"]),
    GecoosSensorDescription(key="cpu", translation_key="cpu", icon="mdi:cpu-64-bit",
                            state_class=SensorStateClass.MEASUREMENT,
                            native_unit_of_measurement=PERCENTAGE, suggested_display_precision=0,
                            value=lambda ap: ap["live"]["cpu"]),
    GecoosSensorDescription(key="memory", translation_key="memory", icon="mdi:memory",
                            state_class=SensorStateClass.MEASUREMENT,
                            native_unit_of_measurement=PERCENTAGE, suggested_display_precision=0,
                            value=lambda ap: ap["live"]["memory"]),
    GecoosSensorDescription(key="location", translation_key="location", icon="mdi:map-marker",
                            needs_live=False, value=lambda ap: ap["location"]),
    GecoosSensorDescription(key="boot", translation_key="boot", device_class=SensorDeviceClass.TIMESTAMP,
                            entity_category=EntityCategory.DIAGNOSTIC,
                            value=lambda ap: _boot_time(ap["live"]["uptime"])),
]

AC_SENSORS = [
    GecoosSensorDescription(key="ap_total", translation_key="ap_total", icon="mdi:access-point-network",
                            value=lambda t: t["ap_total"]),
    GecoosSensorDescription(key="ap_online", translation_key="ap_online", icon="mdi:access-point-check",
                            state_class=SensorStateClass.MEASUREMENT, value=lambda t: t["ap_online"]),
    GecoosSensorDescription(key="ap_offline", translation_key="ap_offline", icon="mdi:access-point-off",
                            state_class=SensorStateClass.MEASUREMENT, value=lambda t: t["ap_offline"]),
    GecoosSensorDescription(key="clients", translation_key="clients_total", icon="mdi:devices",
                            state_class=SensorStateClass.MEASUREMENT, value=lambda t: t["clients"]),
    GecoosSensorDescription(key="download", translation_key="download_total", icon="mdi:download",
                            value=lambda t: t["download"], **RATE),
    GecoosSensorDescription(key="upload", translation_key="upload_total", icon="mdi:upload",
                            value=lambda t: t["upload"], **RATE),
]


def _boot_time(uptime):
    if not uptime:
        return None
    # Round to the minute so the state does not change on every poll.
    return (dt_util.utcnow() - timedelta(seconds=int(uptime))).replace(second=0, microsecond=0)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(AcSensor(coordinator, d) for d in AC_SENSORS)
    known = set()

    def add_new():
        new = [mac for mac in coordinator.data["aps"] if mac not in known]
        known.update(new)
        async_add_entities(ApSensor(coordinator, mac, d) for mac in new for d in AP_SENSORS)

    add_new()
    entry.async_on_unload(coordinator.async_add_listener(add_new))


class AcSensor(AcEntity, SensorEntity):
    def __init__(self, coordinator, description):
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self):
        return self.entity_description.value(self.coordinator.data["totals"])

    @property
    def extra_state_attributes(self):
        totals = self.coordinator.data["totals"]
        if self.entity_description.key == "ap_offline":
            return {"offline_aps": totals["offline_names"]}
        if self.entity_description.key == "clients":
            return {"ac_reported_clients": totals["clients_ac"]}
        return None


class ApSensor(ApEntity, SensorEntity):
    def __init__(self, coordinator, mac, description):
        super().__init__(coordinator, mac, description.key)
        self.entity_description = description
        self.needs_live = description.needs_live

    @property
    def native_value(self):
        return self.entity_description.value(self.ap)

    @property
    def extra_state_attributes(self):
        key = self.entity_description.key
        if key == "clients":
            return {"stations": self.ap["live"]["stations"]}
        if key == "location":
            return {"room": self.ap["room"]}
        if key in ("download", "upload"):
            return {"source": "br-lan", "lan_speed_mbps": self.ap["live"]["lan_speed"]}
        return None
