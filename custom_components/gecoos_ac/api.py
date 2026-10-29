"""Clients for the Gecoos AC web API and the per-AP admin API."""

import asyncio
import hashlib
import re
import time
from dataclasses import dataclass, field

import aiohttp

from .const import MODEL_SUFFIXES, ROOMS

TIMEOUT = aiohttp.ClientTimeout(total=10)


def new_session() -> aiohttp.ClientSession:
    """A private session: the AC keeps its login in a cookie on an IP host,
    which needs an unsafe cookie jar, and the APs use self-signed HTTPS."""
    return aiohttp.ClientSession(
        cookie_jar=aiohttp.CookieJar(unsafe=True),
        connector=aiohttp.TCPConnector(ssl=False),
    )


class GecoosError(Exception):
    """The device answered with an error or could not be reached."""


class GecoosAuthError(GecoosError):
    """The credentials were rejected."""


def _md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def parse_location(name: str, model: str = "") -> tuple[str | None, str]:
    """Split names such as "AP59_客厅沙发_AX1800" into ("客厅", "客厅沙发").

    Names without a known room keep the room unset and the location as written."""
    room = next((r for r in sorted(ROOMS, key=len, reverse=True) if r in name), None)
    rest = re.sub(r"^AP\d+_?", "", name)
    suffixes = "|".join(re.escape(s) for s in [*MODEL_SUFFIXES, model] if s)
    rest = re.sub(r"[_\s-]?(" + suffixes + r")$", "", rest, flags=re.I)
    return room, rest.strip("_- ") or name


class AcClient:
    """Session-cookie client for the AC (salted double MD5 login)."""

    def __init__(self, session: aiohttp.ClientSession, host: str, username: str, password: str) -> None:
        self._session = session
        self._base = f"http://{host}/api/"
        self._username = username
        self._password = password
        self._logged_in = False

    async def _json(self, method: str, path: str, **kwargs) -> dict:
        try:
            async with self._session.request(method, self._base + path, timeout=TIMEOUT, **kwargs) as resp:
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            raise GecoosError(f"AC {path}: {exc}") from exc

    async def login(self) -> None:
        salt = await self._json("GET", "login")
        if str(salt.get("ret")) != "1":
            raise GecoosError("AC did not return a login challenge")
        result = await self._json("POST", "login", data={
            "loginid": self._username,
            "passwd": _md5(_md5(self._password) + salt["msg"]),
        })
        if str(result.get("ret")) != "1":
            raise GecoosAuthError(result.get("msg") or "login rejected")
        self._logged_in = True

    async def call(self, method: str, module: str, data: dict) -> dict:
        for attempt in range(2):
            if not self._logged_in:
                await self.login()
            if method == "GET":
                result = await self._json("GET", module, params=data)
            else:
                result = await self._json("POST", module, data=data)
            if str(result.get("ret")) == "1":
                return result
            # An expired session answers ret=0 with "请重新登陆"; log in once more.
            self._logged_in = False
        raise GecoosError(f"AC {module}/{data.get('action')}: {result.get('msg')}")

    async def overview(self) -> dict:
        return await self.call("GET", "apmgr", {"action": "apstatview"})

    async def aplist(self) -> list[dict]:
        result = await self.call("POST", "apmgr", {"action": "apsearch", "pagenum": 1, "numperpage": 1000})
        return result.get("aplist") or []


class ApClient:
    """Token client for an AP's own admin API (HTTPS, self-signed)."""

    def __init__(self, session: aiohttp.ClientSession, host: str, password: str) -> None:
        self._session = session
        self.host = host
        self._base = f"https://{host}/cgi-bin/api/admin/"
        self._password = password
        self._token: str | None = None

    async def _json(self, method: str, path: str, **kwargs) -> dict:
        headers = {"sysauth": self._token} if self._token else {}
        try:
            async with self._session.request(method, self._base + path, headers=headers,
                                             timeout=TIMEOUT, ssl=False, **kwargs) as resp:
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            raise GecoosError(f"AP {path}: {exc}") from exc

    async def login(self) -> None:
        self._token = None
        random = await self._json("POST", "getrandom")
        result = await self._json("POST", "sysauth", data={
            "username": "root",
            "password": _md5(random.get("random", "") + self._password),
        })
        if result.get("ret") != 1 or not result.get("token"):
            raise GecoosAuthError(result.get("msg") or "AP login rejected")
        self._token = result["token"]

    async def get(self, path: str) -> dict:
        for attempt in range(2):
            if not self._token:
                await self.login()
            result = await self._json("GET", path)
            # Some answers (status/overview) carry no "ret"; -99 means the token expired.
            if result.get("ret", 1) == 1:
                return result
            if result.get("ret") != -99:
                break
            self._token = None
        raise GecoosError(f"AP {path}: {result.get('msg')}")


@dataclass
class _Counters:
    at: float
    rx: int
    tx: int
    cpu_busy: int
    cpu_total: int


@dataclass
class ApTracker:
    """Keeps the previous counters of one AP to turn them into rates."""

    client: ApClient
    last: _Counters | None = None
    clients: list[dict] = field(default_factory=list)

    async def poll(self) -> dict:
        overview = await self.client.get("status/overview")
        try:
            wireless = await self.client.get("network/wireless_status")
        except GecoosError:
            wireless = {}
        now = time.monotonic()
        lan = overview.get("lan") or {}
        cpu = (overview.get("cputable") or {}).get("cpu") or {}
        values = {k: int(v) for k, v in cpu.items() if str(v).isdigit()}
        total = sum(values.values())
        current = _Counters(now, int(lan.get("rx_bytes") or 0), int(lan.get("tx_bytes") or 0),
                            total - values.get("idle", 0) - values.get("iowait", 0), total)

        data = {"download": None, "upload": None, "cpu": None}
        previous, self.last = self.last, current
        if previous and current.at > previous.at:
            seconds = current.at - previous.at
            rx, tx = current.rx - previous.rx, current.tx - previous.tx
            # Counters reset on reboot; skip that interval rather than report a spike.
            if rx >= 0 and tx >= 0:
                # br-lan rx is traffic coming from the wired side, i.e. client download.
                data["download"] = round(rx * 8 / seconds / 1000, 1)
                data["upload"] = round(tx * 8 / seconds / 1000, 1)
            if current.cpu_total > previous.cpu_total:
                data["cpu"] = round(100 * (current.cpu_busy - previous.cpu_busy)
                                    / (current.cpu_total - previous.cpu_total), 1)

        details = {}
        for ssid in (wireless.get("ssid_table") or {}).values():
            for radio in (ssid.get("radio") or {}).values():
                for mac, info in radio.items():
                    if isinstance(info, dict):
                        details[mac.upper()] = info
        stations = {}
        for net in (overview.get("wifinets") or {}).values():
            for mac, info in (net.get("assoclist") or {}).items():
                extra = details.get(mac.upper(), {})
                stations[mac.upper()] = {
                    "mac": mac.upper(),
                    "hostname": extra.get("hostname") or "",
                    "ip": extra.get("ip") or "",
                    "ssid": net.get("ssid"),
                    "band": extra.get("alias") or net.get("alias") or "",
                    "signal": info.get("signal"),
                    "connected_seconds": info.get("assoctime"),
                }
        memtotal = overview.get("memtotal") or 0
        memfree = sum(overview.get(k) or 0 for k in ("memfree", "membuffers", "memcached"))
        loadavg = overview.get("loadavg") or [None]
        data.update({
            "clients": len(stations),
            "stations": sorted(stations.values(), key=lambda s: (s["ssid"] or "", s["hostname"])),
            "load": round(loadavg[0], 2) if loadavg[0] is not None else None,
            "memory": round(100 * (memtotal - memfree) / memtotal, 1) if memtotal else None,
            "uptime": overview.get("uptime"),
            "lan_speed": lan.get("speed"),
            "ac_status": overview.get("ac_status"),
        })
        return data
