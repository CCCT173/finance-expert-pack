#!/usr/bin/env python3
"""
板块轮动追踪器
功能：查询各热门板块的资金流向和涨跌，判断当前市场主线
"""
import sys
import os
import json
import urllib.request
from datetime import datetime

# Force UTF-8 encoding on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

API_PORT = int(os.environ.get("AUTH_GATEWAY_PORT", "19000"))

def call_neodata(query: str) -> dict:
    url = f"http://localhost:{API_PORT}/proxy/api"
    payload = {
        "channel": "neodata",
        "sub_channel": "qclaw",
        "query": query,
        "request_id": f"sector_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "data_type": "api",
        "se_params": {},
        "extra_params": {}
    }
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Remote-URL": "https://jprx.m.qq.com/aizone/skillserver/v1/proxy/teamrouter_neodata/query"
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def extract_sector_data(content: str) -> dict:
    """从 content 提取板块涨跌幅"""
    result = []
    for seg in content.split("；"):
        if "板块" in seg and ("涨跌幅" in seg or "%" in seg):
            result.append(seg.strip())
    return result

def main():
    now = datetime.now().strftime("%Y/%m/%d %H:%M")
    print(f"\n{'='*50}")
    print(f"🔥 板块轮动追踪 | {now}")
    print(f"{'='*50}")

    # 查询热门板块
    sectors_to_check = [
        "银行板块",
        "白酒板块", 
        "新能源板块",
        "电力设备板块",
        "电池板块",
        "半导体板块",
        "人工智能板块",
        "军工板块",
        "医药板块",
        "房地产板块",
    ]

    sector_results = []
    for sector in sectors_to_check:
        try:
            data = call_neodata(sector)
            for item in data.get("data", {}).get("apiData", {}).get("entity", []):
                for recall in item.get("apiRecall", []):
                    content = recall.get("content", "")
                    if "板块" in content and ("涨跌幅" in content or "%" in content):
                        sector_results.append({"name": sector, "content": content})
        except Exception as e:
            print(f"[WARN] 查询 {sector} 失败: {e}")

    print(f"\n📊 板块行情：")
    print(f"{'─'*40}")
    for r in sector_results:
        content = r["content"]
        # 提取板块名和涨跌幅
        name = r["name"]
        change = ""
        for seg in content.split("；"):
            if name.replace("板块", "") in seg or "板块涨" in seg:
                change = seg.strip()[:80]
                break
        print(f"  {name}: {change if change else content[:60]}")

    # 判断市场主线
    print(f"\n🎯 市场主线判断：")
    positive_sectors = []
    negative_sectors = []
    for r in sector_results:
        content = r["content"]
        try:
            for seg in content.split("；"):
                if "%" in seg:
                    num_str = seg.split("%")[0].split("涨跌幅")[-1]
                    num_str = "".join(filter(lambda x: x.isdigit() or x in ".-+", num_str))
                    pct = float(num_str) if num_str else 0
                    if pct > 0:
                        positive_sectors.append((r["name"], pct))
                    elif pct < 0:
                        negative_sectors.append((r["name"], pct))
        except:
            pass

    positive_sectors.sort(key=lambda x: x[1], reverse=True)
    negative_sectors.sort(key=lambda x: x[1])

    if positive_sectors:
        print(f"  领涨板块: {', '.join([f'{n}({p:+.2f}%)' for n, p in positive_sectors[:3]])}")
    if negative_sectors:
        print(f"  弱势板块: {', '.join([f'{n}({p:+.2f}%)' for n, p in negative_sectors[:3]])}")
    if not positive_sectors and not negative_sectors:
        print(f"  (暂无板块数据)")

    print(f"{'='*50}\n")

if __name__ == "__main__":
    try:
        main()
    except Exception as _err:
        print("执行失败（可能网关/依赖不可用）：", _err)
