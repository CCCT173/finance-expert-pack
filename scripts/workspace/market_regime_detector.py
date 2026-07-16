#!/usr/bin/env python3
"""
市场状态探测器
功能：综合判断当前市场处于哪种状态（牛市/熊市/震荡/复苏/过热/衰退）
参考：均线多头排列、涨跌幅、成交量、板块表现
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
        "request_id": f"regime_{datetime.now().strftime('%Y%m%d%H%M%S')}",
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

def extract_index_info(content: str) -> dict:
    """提取指数的关键信息"""
    result = {}
    for seg in content.split("；"):
        if "上证指数" in seg and "点" in seg:
            result["sse_change_5d"] = 0
            result["sse_change_20d"] = 0
            for keyword, key in [("5日涨跌幅", "sse_change_5d"), ("20日涨跌幅", "sse_change_20d")]:
                if keyword in seg:
                    try:
                        num_str = seg.split(keyword)[-1].replace("%", "").strip()
                        num_str = "".join(filter(lambda x: x.isdigit() or x in ".-+", num_str))
                        result[key] = float(num_str)
                    except:
                        pass
        if "深证成指" in seg and "5日涨跌幅" in seg:
            try:
                num_str = seg.split("5日涨跌幅")[-1].replace("%", "").strip()
                result["szse_change_5d"] = float("".join(filter(lambda x: x.isdigit() or x in ".-+", num_str)))
            except:
                pass
    return result

def classify_regime(data: dict) -> tuple:
    """
    判断市场状态
    返回: (状态名称, 状态描述, 建议策略)
    """
    sse_5d = data.get("sse_change_5d", 0)
    sse_20d = data.get("sse_change_20d", 0)
    szse_5d = data.get("szse_change_5d", 0)

    # 简单判断逻辑
    if sse_20d > 10 and sse_5d > 3:
        return ("🔥 过热阶段", "市场快速上涨，动能强劲但风险积累", "注意仓位控制，可适度止盈")
    elif sse_20d > 5 and sse_5d > 0:
        return ("📈 牛市阶段", "中期上升趋势确立，逢低做多", "顺势持有，可适当加仓")
    elif sse_5d < -3 and sse_20d < 0:
        return ("😱 熊市阶段", "下跌趋势明显，控制风险", "轻仓或空仓观望，等待企稳信号")
    elif sse_5d < 0 and sse_20d > 0:
        return ("🔄 震荡整理", "短期回调，中期趋势未破", "高抛低吸，控制仓位")
    elif sse_5d > 0 and sse_20d < 0:
        return ("🌱 反弹修复", "超跌反弹，轻仓试探", "快进快出，设好止损")
    elif abs(sse_5d) < 1 and abs(sse_20d) < 3:
        return ("⚖️ 横盘整理", "方向不明，观望为主", "控制仓位，减少操作")
    else:
        return ("❓ 模糊状态", "信号不明确", "谨慎操作，等待确认")

def main():
    now = datetime.now().strftime("%Y/%m/%d %H:%M")
    print(f"\n{'='*50}")
    print(f"🌡️ 市场状态探测 | {now}")
    print(f"{'='*50}")

    try:
        data = call_neodata("上证指数")
        index_info = {}
        for item in data.get("data", {}).get("apiData", {}).get("entity", []):
            for recall in item.get("apiRecall", []):
                content = recall.get("content", "")
                if "指数" in content:
                    info = extract_index_info(content)
                    index_info.update(info)

        print(f"\n📊 技术指标：")
        print(f"  上证5日涨跌: {index_info.get('sse_change_5d', 0):+.2f}%")
        print(f"  上证20日涨跌: {index_info.get('sse_change_20d', 0):+.2f}%")
        print(f"  深证5日涨跌: {index_info.get('szse_change_5d', 0):+.2f}%")

        regime, desc, strategy = classify_regime(index_info)
        print(f"\n🎯 市场状态: {regime}")
        print(f"  状态解读: {desc}")
        print(f"  策略建议: {strategy}")

    except Exception as e:
        print(f"[ERROR] {e}")

    print(f"{'='*50}\n")

if __name__ == "__main__":
    try:
        main()
    except Exception as _err:
        print("执行失败（可能网关/依赖不可用）：", _err)
