#!/usr/bin/env python3
"""
全球宏观扫描器
查询外围市场数据，为A股开盘提供外部环境参考
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

QUERIES = {
    "S&P500": "美国标普500指数",
    "Nasdaq": "纳斯达克指数",
    "Gold": "黄金价格",
    "Oil": "WTI原油",
    "USD_CNY": "美元兑人民币",
    "A50": "A50期货",
}

def call_neodata(query: str) -> dict:
    url = f"http://localhost:{API_PORT}/proxy/api"
    payload = {
        "channel": "neodata", "sub_channel": "qclaw",
        "query": query,
        "request_id": f"macro_{datetime.now().strftime('%Y%m%d%H%M%S')}",
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

def extract_price_info(data: dict) -> dict:
    """从API响应中提取价格和涨跌幅"""
    result = {}
    for item in data.get("data", {}).get("apiData", {}).get("apiRecall", []):
        content = item.get("content", "")
        # 提取价格
        price_match = re.search(r'(?:最新价格|当前价格|价格|点位)[:：](\d+\.?\d*)', content)
        if price_match:
            result["price"] = float(price_match.group(1))
        # 提取涨跌幅
        change_match = re.search(r'(?:涨跌幅|涨跌)[:：]?([+-]?\d+\.?\d*)%', content)
        if change_match:
            result["change_pct"] = float(change_match.group(1))
        # 提取时间
        time_match = re.search(r'(\d{4}[-/]\d{2}[-/]\d{2}[T\s]\d{2}:\d{2})', content)
        if time_match:
            result["time"] = time_match.group(1)
        if result:
            return result
    return result

def extract_single(data: dict) -> dict:
    """简洁提取"""
    result = {}
    recalls = data.get("data", {}).get("apiData", {}).get("apiRecall", [])
    for recall in recalls:
        content = recall.get("content", "")
        pm = re.search(r'价格[:：](\d+\.?\d*)', content)
        if pm and "price" not in result:
            result["price"] = float(pm.group(1))
        cm = re.search(r'涨跌幅[:：]?([+-]?\d+\.?\d*)%', content)
        if cm and "change_pct" not in result:
            result["change_pct"] = float(cm.group(1))
    return result

def main():
    now = datetime.now().strftime("%Y/%m/%d %H:%M")
    print(f"\n{'='*50}")
    print(f"🌐 全球宏观盘前扫描 | {now}")
    print(f"{'='*50}")

    results = {}
    for key, query in QUERIES.items():
        try:
            data = call_neodata(query)
            info = extract_single(data)
            results[key] = info
            print(f"[{key}] price={info.get('price','N/A')}, change={info.get('change_pct','N/A')}%")
        except Exception as e:
            results[key] = {}
            print(f"[{key}] ERROR: {e}")

    # 北向资金
    print("\n[北向资金查询...]")
    try:
        north_data = call_neodata("北向资金 沪深股通")
        recalls = north_data.get("data", {}).get("apiData", {}).get("apiRecall", [])
        for recall in recalls:
            content = recall.get("content", "")
            if "北向" in content or "股通" in content or "净买入" in content:
                print(f"[北向] {content[:200]}")
                break
    except Exception as e:
        print(f"[北向] ERROR: {e}")

    print(f"\n{'='*50}")
    # 综合判断
    print("\n[开盘方向判断]")
    changes = []
    for key in ["S&P500", "Nasdaq", "A50"]:
        if key in results and "change_pct" in results[key]:
            changes.append((key, results[key]["change_pct"]))

    if changes:
        avg = sum(c for _, c in changes) / len(changes)
        if avg > 1:
            direction = "偏多"
        elif avg < -1:
            direction = "偏空"
        else:
            direction = "震荡"
        print(f"  外围平均涨跌: {avg:+.2f}% → A股开盘方向: {direction}")
    print(f"{'='*50}\n")

if __name__ == "__main__":
    try:
        main()
    except Exception as _err:
        print("执行失败（可能网关/依赖不可用）：", _err)
