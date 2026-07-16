#!/usr/bin/env python3
"""
A-Share Pro 统一配置
集中管理所有路径和参数，避免硬编码
"""
import os

# ===========================================
# 📁 数据存储配置
# ===========================================

# 主数据目录（默认 OpenClaw 私有路径；可通过 A_SHARE_DATA_DIR 环境变量覆盖，便于脱离 OpenClaw 使用）
DATA_DIR = os.environ.get("A_SHARE_DATA_DIR", os.path.expanduser("~/.openclaw/a_share"))

# 自选股文件（code|name|cost|shares|notes）
WATCHLIST_FILE = os.path.join(DATA_DIR, "watchlist.txt")

# 交易记录文件
TRANSACTIONS_FILE = os.path.join(DATA_DIR, "transactions.txt")

# 确保目录存在
os.makedirs(DATA_DIR, exist_ok=True)

# ===========================================
# 🔌 数据源配置
# ===========================================

# 数据源优先级（按此顺序尝试）
DATA_SOURCES_PRIORITY = ["tencent", "xueqiu", "baidu", "tushare"]

# Tushare Token（从环境变量或默认值读取）
TUSHARE_TOKEN = os.environ.get("TUSHARE_TOKEN", "")

# ===========================================
# ⏱️ 网络请求配置
# ===========================================

# 请求间隔（秒），避免被反爬
REQUEST_DELAY = 1.0

# 超时时间（秒）
REQUEST_TIMEOUT = 10

# ===========================================
# 🎯 默认关注列表（可选预置）
# ===========================================

DEFAULT_WATCHLIST = [
    ("600919", "江苏银行"),
    ("600926", "杭州银行"),
    ("600025", "华能水电"),
    ("159681", "创业板 ETF"),
    ("588080", "科创 50ETF"),
]
