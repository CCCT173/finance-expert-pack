import os
import requests
import sys

sys.stdout.reconfigure(encoding='utf-8')

token = ""
base = "https://api.zhituapi.com"

stocks = [
    ("002624", "完美世界"),
    ("601069", "西部黄金"),
    ("600397", "江钨装备"),
    ("000001", "平安银行（对照组）"),
    ("600519", "贵州茅台（对照组）"),
]

print("=== 智兔数服 实时行情测试 ===\n")
for code, name in stocks:
    url = f"{base}/hs/real/time/{code}?token={token}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            print(f"✅ {code} {name}")
            print(f"   当前价格: {data.get('p', 'N/A')}")
            print(f"   涨跌幅: {data.get('pc', 'N/A')}%")
            print(f"   更新时间: {data.get('t', 'N/A')}")
            print(f"   原始数据: {data}")
            print()
        else:
            print(f"❌ {code} {name}: HTTP {r.status_code}\n")
    except Exception as e:
        print(f"❌ {code} {name}: {e}\n")
