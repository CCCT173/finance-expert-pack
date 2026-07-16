#!/usr/bin/env python3
"""
动量背离检测器
检测持仓股表现是否与所属板块/指数出现背离
如果持仓股跌了但板块在涨 = 警示信号（可能被抛售）
如果持仓股涨了但板块在跌 = 警示信号（可能是虚假繁荣）
"""
import sys
import os
import re
import json
import urllib.request
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

API_PORT = int(os.environ.get("AUTH_GATEWAY_PORT", "19000"))

# 持仓股对应的板块/指数
SECTOR_MAP = {
    "000001": {"name": "平安银行", "sector": "银行板块", "index": "沪深300银行指数"},
    "300750": {"name": "宁德时代", "sector": "新能源板块", "index": "创业板指"},
}

def call_neodata(query: str) -> dict:
    url = f"http://localhost:{API_PORT}/proxy/api"
    payload = {
        "channel": "neodata", "sub_channel": "qclaw",
        "query": query,
        "request_id": f"momentum_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "data_type": "api", "se_params": {}, "extra_params": {}
    }
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Remote-URL": "https://jprx.m.qq.com/aizone/skillserver/v1/proxy/teamrouter_neodata/query"
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def extract_change(content: str) -> float:
    """从content提取涨跌幅"""
    patterns = [
        r'当日涨跌幅[:：]?([+-]?\d+\.?\d*)%',
        r'涨跌幅[:：]?([+-]?\d+\.?\d*)%',
        r'当天涨跌幅[:：]?([+-]?\d+\.?\d*)%',
        r'近5日涨跌幅[:：]?([+-]?\d+\.?\d*)%',
    ]
    for pattern in patterns:
        m = re.search(pattern, content)
        if m:
            return float(m.group(1))
    return None

def get_stock_change(code: str) -> float:
    """获取个股当日涨跌幅"""
    try:
        data = call_neodata(code)
        recalls = data.get("data", {}).get("apiData", {}).get("apiRecall", [])
        for r in recalls:
            change = extract_change(r.get("content", ""))
            if change is not None:
                return change
    except:
        pass
    return None

def get_sector_change(sector_name: str) -> float:
    """获取板块当日涨跌幅"""
    try:
        data = call_neodata(sector_name)
        recalls = data.get("data", {}).get("apiData", {}).get("apiRecall", [])
        for r in recalls:
            change = extract_change(r.get("content", ""))
            if change is not None:
                return change
    except:
        pass
    return None

def main():
    now = datetime.now().strftime("%Y/%m/%d %H:%M")
    print(f"\n{'='*50}")
    print(f"📐 动量背离检测 | {now}")
    print(f"{'='*50}")

    alerts = []
    for code, info in SECTOR_MAP.items():
        name = info["name"]
        sector = info["sector"]

        stock_change = get_stock_change(code)
        sector_change = get_sector_change(sector)

        print(f"\n{name}({code}):")
        print(f"  个股当日: {stock_change:+.2f}%" if stock_change else "  个股当日: N/A")
        print(f"  {sector}: {sector_change:+.2f}%" if sector_change else f"  {sector}: N/A")

        if stock_change is not None and sector_change is not None:
            divergence = stock_change - sector_change
            print(f"  背离程度: {divergence:+.2f}%")

            if divergence <= -2.0:
                alerts.append(f"⚠️ {name} 弱于板块 {divergence:+.1f}%")
                print(f"  → 【警示】个股显著弱于板块！")
            elif divergence >= 2.0:
                alerts.append(f"⚡ {name} 强于板块 {divergence:+.1f}%")
                print(f"  → 【提示】个股显著强于板块")
            else:
                print(f"  → 正常联动")

    if alerts:
        print(f"\n🚨 背离告警：")
        for a in alerts:
            print(f"  {a}")
    else:
        print(f"\n✅ 无背离信号")

    print(f"{'='*50}\n")
    return alerts

if __name__ == "__main__":
    try:
        main()
    except Exception as _err:
        print("执行失败（可能网关/依赖不可用）：", _err)
