"""Offline tests of gecoos_ac/api.py with a mocked transport (no Home Assistant, no network)."""
import asyncio
import copy
import hashlib
import json
import pathlib
import sys
import types

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _load import load  # noqa: E402

api = load(HERE.parent / "custom_components/gecoos_ac")
F = json.loads((HERE / "fixtures.json").read_text())


def md5(text):
    return hashlib.md5(text.encode()).hexdigest()


def raises(exc, coro):
    try:
        asyncio.run(coro)
    except exc:
        return
    raise AssertionError(f"did not raise {exc.__name__}")


# --- parse_location -------------------------------------------------------------------------
CASES = {
    ("AP59_客厅沙发_AX1800", "AX1800MI"): ("客厅", "客厅沙发"),
    ("AP164儿童房_RM2100", "AP246ND"): ("儿童房", "儿童房"),
    ("AP134_次卧书桌RAX3kM", "AP250MD"): ("次卧", "次卧书桌"),
    ("主卧室吸顶", "AP250MD"): ("主卧", "主卧室吸顶"),
    ("Living Room AP", "AP246ND"): (None, "Living Room AP"),
    ("APartment", ""): (None, "APartment"),
    ("书房-AP250MD", "AP250MD"): ("书房", "书房"),
}
for (name, model), expected in CASES.items():
    assert api.parse_location(name, model) == expected, (name, api.parse_location(name, model))


# --- AC client ------------------------------------------------------------------------------
class FakeAc(api.AcClient):
    def __init__(self, answers):
        super().__init__(None, "192.0.2.1", "admin", "secret")
        self.answers, self.calls = answers, []

    async def _json(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        return self.answers.pop(0)


ac = FakeAc([{"ret": 1, "msg": "SALT"}, {"ret": 1}, F["ac_overview"]])
assert asyncio.run(ac.overview())["apnum"] == 3
assert ac.calls[1][2]["data"] == {"loginid": "admin", "passwd": md5(md5("secret") + "SALT")}

# An expired session (ret=0) logs in again once and retries.
ac = FakeAc([{"ret": 1, "msg": "S"}, {"ret": 1}, {"ret": 0, "msg": "请重新登陆"},
             {"ret": 1, "msg": "S2"}, {"ret": 1}, F["ac_aplist"]])
assert len(asyncio.run(ac.aplist())) == 3
assert [c[1] for c in ac.calls] == ["login", "login", "apmgr", "login", "login", "apmgr"]

raises(api.GecoosAuthError, FakeAc([{"ret": 1, "msg": "S"}, {"ret": 0, "msg": "密码错误"}]).login())
raises(api.GecoosError, FakeAc([{"ret": 0}]).login())


# --- AP client ------------------------------------------------------------------------------
class FakeAp(api.ApClient):
    def __init__(self, answers):
        super().__init__(None, "192.0.2.11", "secret")
        self.answers, self.calls = answers, []

    async def _json(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs, self._token))
        answer = self.answers.pop(0)
        return answer(path) if callable(answer) else answer


ap = FakeAp([{"random": "R"}, {"ret": 1, "token": "T1"}, {"ret": -99}, {"random": "R2"},
             {"ret": 1, "token": "T2"}, {"ret": 1, "x": 1}])
assert asyncio.run(ap.get("status/load_status")) == {"ret": 1, "x": 1}
assert ap.calls[1][2]["data"] == {"username": "root", "password": md5("R" + "secret")}
assert ap.calls[-1][3] == "T2"
raises(api.GecoosAuthError, FakeAp([{"random": "R"}, {"ret": 0, "msg": "bad"}]).login())


# --- ApTracker: rates, CPU, stations, counter reset ------------------------------------------
def answers_for(overview):
    return lambda path: overview if path == "status/overview" else F["ap_wireless"]


first = copy.deepcopy(F["ap_overview"])
second = copy.deepcopy(first)
second["lan"]["rx_bytes"] += 3_750_000   # 30 Mbit in 1 s
second["lan"]["tx_bytes"] += 125_000     # 1 Mbit in 1 s
cpu = second["cputable"]["cpu"]
cpu["user"] = str(int(cpu["user"]) + 300)
cpu["idle"] = int(cpu["idle"]) + 700

clock = iter([100.0, 101.0, 102.0])
# Replace only the clock api.py sees; asyncio keeps the real one.
api.time = types.SimpleNamespace(monotonic=lambda: next(clock))
tracker = api.ApTracker(FakeAp([{"random": "R"}, {"ret": 1, "token": "T"}] + [answers_for(first)] * 2))
data = asyncio.run(tracker.poll())
assert data["download"] is None and data["upload"] is None and data["cpu"] is None
assert data["clients"] == 3
named = {s["mac"]: s for s in data["stations"]}
assert named["02:00:00:00:00:04"]["hostname"] == "device-04" and named["02:00:00:00:00:04"]["ip"] == "192.0.2.104"
assert named["02:00:00:00:00:06"]["band"] == "2.4G"
assert 0 < data["memory"] < 100 and data["load"] == 0.03

tracker.client.answers += [answers_for(second)] * 2
data = asyncio.run(tracker.poll())
assert data["download"] == 30000.0 and data["upload"] == 1000.0, data
assert data["cpu"] == 30.0, data["cpu"]

# Counters reset after a reboot: that interval is skipped instead of reporting a spike.
tracker.client.answers += [answers_for(first)] * 2
data = asyncio.run(tracker.poll())
assert data["download"] is None and data["upload"] is None

# The wireless status call is optional; stations still come from the overview.
tracker.client.answers += [answers_for(first), {"ret": 0, "msg": "unsupported"}]
api.time = types.SimpleNamespace(monotonic=lambda: 200.0)
data = asyncio.run(tracker.poll())
assert data["clients"] == 3 and all(s["hostname"] == "" for s in data["stations"])

print("gecoos api ok")
