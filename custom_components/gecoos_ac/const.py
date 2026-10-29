DOMAIN = "gecoos_ac"

CONF_AP_PASSWORD = "ap_password"
DEFAULT_USERNAME = "admin"
DEFAULT_NAME = "集客 AC"
DEFAULT_INTERVAL = 30
MIN_INTERVAL = 10

# Room keywords looked for in AP names; the longest match wins, so "主卧" beats "卧室" in "主卧室".
ROOMS = [
    "儿童房", "老人房", "衣帽间", "储物间", "卫生间", "洗手间", "洗手台", "会议室", "办公室",
    "主卧", "次卧", "客卧", "卧室", "客房", "客厅", "厨房", "餐厅", "书房", "走廊", "玄关",
    "阳台", "车库", "花园", "庭院",
]
# Hardware names often appended to AP names (e.g. "AP59_客厅沙发_AX1800"); stripped from the location.
MODEL_SUFFIXES = ["AX1800", "AX3000", "K2P", "RM2100", "RAX3kM", "CR660x", "CR8806", "WR3000"]
