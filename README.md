# 集客（GECOOS）AC / AP Home Assistant 集成

[![hacs](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/docs/faq/custom_repositories)
[![license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

把集客无线 AC 和它管理的 AP 接入 Home Assistant：AP 在线状态、终端数、实时上下行速率、CPU / 内存 / 负载、开机时间，以及全网汇总。

- **本地轮询**：只访问局域网里的 AC 和 AP，不经过任何云服务。
- **只读**：不修改 AC 或 AP 的任何配置。
- **自动发现 AP**：只需填写 AC 的地址和账号，AC 下的 AP 会自动出现，新增 AP 也会自动添加。
- **自动分区**：AP 名称里带“客厅”“主卧”等房间关键词时，会自动建议对应的区域。

> 本项目与集客官方无关，详见 [免责声明](DISCLAIMER.md)。

## 工作方式

| 数据来源 | 提供的数据 |
|---|---|
| AC 的 Web 接口（`http://<AC>/api/`） | AP 列表、在线 / 离线、型号、固件版本、全网汇总 |
| 每台 AP 自己的管理接口（`https://<AP>/cgi-bin/api/admin/`） | 终端列表、负载、CPU、内存、开机时间、br-lan 字节计数（用来算速率） |

AC 只会给已授权的 AP 提供终端和速率数据，所以集成会直接去读每台在线 AP 的接口。读不到某台 AP 时（比如密码不同或接口不兼容），这台 AP 只保留 AC 提供的在线状态和位置。

## 实体

**AC 设备**

| 实体 | 说明 |
|---|---|
| AP 总数 / 在线 AP / 离线 AP | 离线 AP 的属性 `offline_aps` 列出离线 AP 的名称 |
| 终端总数 | 各 AP 终端数之和；属性 `ac_reported_clients` 是 AC 自己统计的数字 |
| 总下载 / 总上传 | 各 AP 速率之和 |

**每台 AP 一个设备**

| 实体 | 说明 |
|---|---|
| 在线 | 由 AC 判断，AP 宕机时也能正确显示；属性里有 IP、MAC、型号、固件版本 |
| 终端数 | 属性 `stations` 列出每个终端的 MAC、主机名、IP、SSID、频段、信号强度和连接时长 |
| 下载 / 上传 | 根据 br-lan 字节计数计算，单位 kbit/s（界面默认显示 Mbit/s） |
| 负载 / CPU / 内存 | 1 分钟平均负载；CPU 和内存使用率（%） |
| 位置 | 从 AP 名称解析出来的位置，属性 `room` 是识别出的房间 |
| 开机时间 | 诊断实体 |

## 安装

### HACS（推荐）

1. HACS → 右上角菜单 →「自定义存储库」，地址填 `https://github.com/margrop/ha-gecoos`，类别选「Integration」。
2. 搜索并下载「Gecoos AC (集客)」，然后重启 Home Assistant。

### 手动安装

把 `custom_components/gecoos_ac` 复制到 Home Assistant 配置目录下的 `custom_components/`，然后重启。不需要额外的 Python 依赖。

## 配置

「设置 → 设备与服务 → 添加集成」，搜索「Gecoos」或「集客」：

| 字段 | 说明 |
|---|---|
| AC 地址 | AC 的局域网 IP 或主机名（不带 `http://`） |
| 用户名 / 密码 | AC 管理页面的登录账号，默认用户名是 `admin` |
| AP 管理密码（可选） | 登录 AP 管理页面（`root` 账号）的密码；留空时使用 AC 的密码 |
| 名称 | AC 设备在 Home Assistant 里的名字 |

- **刷新间隔**：在集成的「配置」里设置，默认 30 秒，范围 10–600 秒。
- **密码变更**：AC 拒绝登录时，Home Assistant 会提示「重新认证」，输入新密码即可，实体和历史数据都会保留。

### AP 命名建议

位置和房间是从 AP 名称里解析的，例如：

| AP 名称 | 房间 | 位置 |
|---|---|---|
| `AP59_客厅沙发_AX1800` | 客厅 | 客厅沙发 |
| `AP164儿童房_RM2100` | 儿童房 | 儿童房 |
| `Living Room AP` | （无） | Living Room AP |

开头的 `AP<数字>` 和结尾的硬件型号（如 `AX1800`、`K2P`、`RM2100`）会被去掉。识别不出房间时，位置就是原名称。

## 兼容性与已知限制

- 目前只在以下环境实测过：集客 AC（Web 接口 `api/login` 加盐双 MD5 登录），AP 固件 `7.4_2023092700` 和 `8.0_2025052000`，硬件包括刷了集客固件的 AX1800、K2P、RM2100、RAX3kM。其他固件版本的字段可能不同，欢迎提 issue 反馈。
- **速率不一定准确**：速率来自 AP 上 br-lan 网桥的字节计数。实测在 MT7981 机型上几乎统计不到下行流量，在 RM2100 上两个方向都会少算；AX1800、K2P 上比较准确。
- AP 重启导致计数清零的那一次轮询，速率显示为未知，不会算出一个异常的峰值。
- AP 使用自签名 HTTPS 证书，所以集成访问 AP 时**不校验证书**。AC 接口是 HTTP。请只在可信的局域网里使用。

## 隐私

终端数实体的 `stations` 属性包含局域网设备的 MAC、主机名和 IP，会写进 Home Assistant 的数据库。在 issue 里贴日志或截图前请先打码。

## 开发

```bash
uv run --no-project --with aiohttp python tests/test_api.py
```

测试只用打码后的离线数据（`tests/fixtures.json`），不需要真实设备。更多约定见 [AGENTS.md](AGENTS.md)。

## 许可证

[MIT](LICENSE)

---

## English

Home Assistant integration for GECOOS (集客) wireless AC controllers and the APs they manage: AP online state, client count and list, throughput, CPU / memory / load and uptime, plus network-wide totals. Local polling only, read-only. Configure the AC address and admin account; APs are discovered through the AC and read directly over their own admin API (self-signed HTTPS, certificate not verified). Install through HACS as a custom repository. Not affiliated with GECOOS.
