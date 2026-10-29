# AGENTS.md

本文件写给在这个仓库里工作的 AI 编程助手和人类贡献者。

## 项目概况

- Home Assistant 自定义集成，domain 为 `gecoos_ac`，代码在 `custom_components/gecoos_ac/`。
- 本地轮询集客（GECOOS）AC 和它管理的 AP，**只读**。

| 文件 | 作用 |
|---|---|
| `api.py` | `AcClient`（AC 的 Web 接口，会话 Cookie，加盐双 MD5 登录）、`ApClient`（AP 的管理接口，`sysauth` 令牌）、`ApTracker`（把计数器换算成速率和 CPU 使用率）、`parse_location`。不依赖 Home Assistant，可以单独测试 |
| `__init__.py` | `DataUpdateCoordinator`：先读 AC，再并发读取每台在线 AP。`GecoosAuthError` 会转成 `ConfigEntryAuthFailed`（触发重新认证）；单台 AP 读取失败不影响其他 AP |
| `config_flow.py` | 添加 AC、重新认证（更新密码）、刷新间隔选项 |
| `entity.py`、`sensor.py`、`binary_sensor.py` | 实体。AP 设备以 MAC 作为标识；新出现的 AP 会自动添加实体 |
| `const.py` | 房间关键词 `ROOMS`、常见硬件型号后缀 `MODEL_SUFFIXES` |
| `strings.json`、`translations/` | 界面文案。`en.json` 必须和 `strings.json` 完全一致，`zh-Hans.json` 键名要一一对应 |
| `brand/` | 集成图标，HACS 校验要求必须有 |

## 硬性规则

1. **只读。** 不要添加任何修改 AC 或 AP 配置的调用，比如重启、改 SSID、踢终端、升级固件。
2. **不要提交真实数据。** 包括真实的 IP、MAC、主机名、SSID、密码，以及抓到的接口原始响应。测试数据一律使用 `tests/fixtures.json` 这种打码后的值：MAC 用 `02:00:00:00:xx:xx`，IP 用 `192.0.2.0/24`（RFC 5737 文档专用网段）。SSID 表的键可能是由真实 SSID 计算出的哈希，也要替换掉。
3. **不要把凭证写进日志。** 日志里可以出现 AP 名称、IP 和错误信息，不能出现密码、令牌或 Cookie。
4. **兼容旧数据。** 实体的 `unique_id`（AC 用 `<entry_id>_<key>`，AP 用 `<MAC>_<key>`）和设备标识不能改，否则用户的历史数据和仪表盘会失效。`parse_location` 的改动要保证 `tests/test_api.py` 里已有的用例结果不变。
5. **不增加第三方依赖。** 只用 Home Assistant 自带的 `aiohttp`，`manifest.json` 的 `requirements` 保持为空。
6. **TLS。** AP 使用自签名证书，只对本集成自己的会话关闭证书校验，不要改用 Home Assistant 的共享会话。
7. **频率。** 默认每 30 秒轮询一次，最小 10 秒。不要再调低，AP 的 CPU 很弱。

## 测试

```bash
uv run --no-project --with aiohttp python tests/test_api.py
```

测试必须通过。CI（`.github/workflows/validate.yml`）还会跑 hassfest 和 HACS 校验。

新增解析逻辑时，在 `tests/fixtures.json` 里补充打码后的数据，并在 `tests/test_api.py` 里加用例。

## 敏感信息检查

提交前在仓库根目录执行，除了 `192.0.2.x` 和 `02:00:00:00:xx:xx` 这类文档专用地址，不应该有其他命中：

```bash
git grep -nE '192\.168\.|(^|[^0-9.])10\.[0-9]+\.[0-9]+\.[0-9]+|172\.(1[6-9]|2[0-9]|3[01])\.' -- . ':!AGENTS.md'
git grep -niE '([0-9a-f]{2}:){5}[0-9a-f]{2}' | grep -viE '02:00:00:00'
```

## 发版

1. 修改 `custom_components/gecoos_ac/manifest.json` 里的 `version`，并在 `CHANGELOG.md` 里写明改动。
2. 确认 CI 通过后，打标签 `vX.Y.Z` 并创建 GitHub Release。

## 风格

- 和现有代码保持一致：注释少而准，函数短，不加多余的抽象。
- 面向用户的文案要同时更新英文和简体中文。
- `strings.json` 里不能直接写 URL（hassfest 会报错），要用 `{占位符}`，并在代码里通过 `description_placeholders` 传入。
- 图标不要换成集客的商标或标志。
