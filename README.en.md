# GECOOS AC / AP for Home Assistant

[![hacs](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/docs/faq/custom_repositories)
[![license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

[中文](README.md) | English

Brings a GECOOS (集客) wireless AC controller and the APs it manages into Home Assistant: AP online state, client count, live download / upload throughput, CPU / memory / load, boot time, and network-wide totals.

- **Local polling**: only talks to the AC and APs on your LAN, no cloud service involved.
- **Read-only**: never changes any AC or AP setting.
- **AP discovery**: enter the AC address and account; the APs under it appear automatically, including APs added later.
- **Area suggestions**: when an AP name contains a room keyword such as "客厅" (living room) or "主卧" (master bedroom), the matching area is suggested.

> This project is not affiliated with GECOOS; see the [disclaimer](DISCLAIMER.md) (Chinese).

## How it works

| Source | Data |
|---|---|
| AC web API (`http://<AC>/api/`) | AP list, online / offline, model, firmware version, network totals |
| Each AP's own admin API (`https://<AP>/cgi-bin/api/admin/`) | Client list, load, CPU, memory, uptime, br-lan byte counters (used for throughput) |

The AC only provides client and throughput data for licensed APs, so the integration reads every online AP directly. When an AP cannot be read (for example a different password or an incompatible API), that AP keeps only the online state and location reported by the AC.

## Entities

**AC device**

| Entity | Description |
|---|---|
| APs / APs online / APs offline | Attribute `offline_aps` of "APs offline" lists the names of offline APs |
| Total clients | Sum of the APs' client counts; attribute `ac_reported_clients` is the AC's own figure |
| Total download / Total upload | Sum of the APs' throughput |

**One device per AP**

| Entity | Description |
|---|---|
| Online | As reported by the AC, so it is correct even when the AP is down; attributes include IP, MAC, model and firmware |
| Clients | Attribute `stations` lists MAC, hostname, IP, SSID, band, signal and connected time of each client |
| Download / Upload | Calculated from the br-lan byte counters, in kbit/s (shown as Mbit/s by default) |
| Load / CPU usage / Memory usage | 1-minute load average; CPU and memory usage in % |
| Location | Location parsed from the AP name; attribute `room` is the recognised room |
| Boot time | Diagnostic |

## Installation

### HACS (recommended)

1. HACS → top-right menu → "Custom repositories", enter `https://github.com/margrop/ha-gecoos`, category "Integration".
2. Search for and download "Gecoos AC (集客)", then restart Home Assistant.

### Manual

Copy `custom_components/gecoos_ac` into `custom_components/` of your Home Assistant configuration directory and restart. No extra Python packages are needed.

## Configuration

"Settings → Devices & services → Add integration", search for "Gecoos" or "集客":

| Field | Description |
|---|---|
| AC host | LAN IP or host name of the AC (without `http://`) |
| Username / Password | Login of the AC web interface; the default username is `admin` |
| AP admin password (optional) | Password of the APs' web interface (`root` account); empty means the AC password |
| Name | Name of the AC device in Home Assistant |

- **Update interval**: set it under the integration's "Configure", 30 seconds by default, 10–600 seconds allowed.
- **Password changes**: when the AC rejects the login, Home Assistant asks you to re-authenticate. Enter the new password; entities and history are kept.

### AP naming

Location and room are parsed from the AP name, for example:

| AP name | Room | Location |
|---|---|---|
| `AP59_客厅沙发_AX1800` | 客厅 (living room) | 客厅沙发 |
| `AP164儿童房_RM2100` | 儿童房 (kids' room) | 儿童房 |
| `Living Room AP` | (none) | Living Room AP |

A leading `AP<digits>` and a trailing hardware model (such as `AX1800`, `K2P`, `RM2100`) are removed. Room keywords are Chinese; when no room is recognised, the location is the original name.

## Compatibility and known limitations

- Tested only with: a GECOOS AC (web API `api/login` with salted double MD5), AP firmware `7.4_2023092700` and `8.0_2025052000`, on AX1800, K2P, RM2100 and RAX3kM hardware flashed with GECOOS firmware. Other firmware versions may use different fields; reports are welcome.
- **Throughput may be inaccurate**: it comes from the byte counters of the AP's br-lan bridge. On MT7981 hardware almost no download traffic is counted, and on the RM2100 both directions are undercounted; AX1800 and K2P were accurate in testing.
- For the poll in which an AP's counters reset after a reboot, throughput is unknown rather than a false spike.
- The APs use self-signed HTTPS certificates, so the integration **does not verify certificates** when talking to APs. The AC API is plain HTTP. Use it on a trusted LAN only.

## Privacy

The `stations` attribute of the Clients entity contains MAC addresses, host names and IPs of devices on your LAN, and is stored in the Home Assistant database. Mask them before posting logs or screenshots in an issue.

## Development

```bash
uv run --no-project --with aiohttp python tests/test_api.py
```

The tests only use sanitized offline data (`tests/fixtures.json`); no real device is needed. See [AGENTS.md](AGENTS.md) (Chinese) for contribution rules.

## License

[MIT](LICENSE)
