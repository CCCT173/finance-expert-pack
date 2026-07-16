#!/usr/bin/env python3
"""
A股模拟实验 - 组合分析器
功能：查询持仓股实时数据，计算组合盈亏、风险指标，生成分析报告
"""
import sys
import os
import re
import json
import urllib.request
import urllib.error
from datetime import datetime

# Force UTF-8 encoding on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# ============ 配置区 ============
INITIAL_CAPITAL = 10000.0
PORTFOLIO = {
    "000001": {"name": "平安银行", "shares": 400, "cost": 11.14},
    "300750": {"name": "宁德时代", "shares": 10, "cost": 434.05},
}
POSITION_ALERT_THRESHOLD = 0.03   # 触发预警的涨跌幅阈值（相对成本）
INDEX_ALERT_THRESHOLD = 0.015     # 大盘异动预警阈值
API_PORT = int(os.environ.get("AUTH_GATEWAY_PORT", "19000"))
# =================================

def call_neodata(query: str) -> dict:
    """调用 neodata-financial-search API"""
    url = f"http://localhost:{API_PORT}/proxy/api"
    payload = {
        "channel": "neodata",
        "sub_channel": "qclaw",
        "query": query,
        "request_id": f"analyzer_{datetime.now().strftime('%Y%m%d%H%M%S')}",
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

def extract_price(content: str) -> dict:
    """从 API 返回的 content 中提取价格和涨跌幅"""
    result = {}
    # 提取最新价格
    for line in content.split("；"):
        if "最新价格" in line or "最新价" in line:
            try:
                price = float("".join(filter(lambda x: x.isdigit() or x == ".", line.split("最新价格")[-1].split("元")[0] if "最新价格" in line else line.split("最新价")[-1].split("元")[0])))
                result["price"] = price
            except:
                pass
        if "涨跌幅" in line and "当日" in line:
            try:
                change = float("".join(filter(lambda x: x.isdigit() or x in ".-+%%", line.split("涨跌幅")[-1].split("%")[0] if "%" in line else "0")))
                if "%" in line:
                    for seg in line.split("涨跌幅"):
                        if "%" in seg:
                            seg2 = seg.split("%")[0]
                            change = float("".join(filter(lambda x: x.isdigit() or x in ".-+", seg2)))
                            result["change_pct"] = change
                            break
            except:
                pass
    return result

def parse_stock_data(data: dict) -> dict:
    """解析股票 API 返回数据，使用正则表达式提取"""
    result = {}
    api_data = data.get("data", {}).get("apiData", {})
    # apiRecall 是 apiData 的直接子节点
    for recall in api_data.get("apiRecall", []):
        if recall.get("type") == "股票实时行情":
            content = recall.get("content", "")
            # 用正则提取关键数据
            price_match = re.search(r'最新价格[:：](\d+\.?\d*)元', content)
            change_match = re.search(r'当日涨跌幅[:：]([+-]?\d+\.?\d*)%', content)
            prev_match = re.search(r'昨日收盘价格[:：](\d+\.?\d*)元', content)
            if price_match:
                result["price"] = float(price_match.group(1))
            if change_match:
                result["change_pct"] = float(change_match.group(1))
            if prev_match:
                result["prev_close"] = float(prev_match.group(1))
            return result
    return result

def parse_index_data(data: dict) -> dict:
    """解析指数 API 返回数据"""
    result = {}
    for item in data.get("data", {}).get("apiData", {}).get("entity", []):
        for recall in item.get("apiRecall", []):
            content = recall.get("content", "")
            if "所属大盘指数" in content or "上证指数" in content or "深证成指" in content:
                for seg in content.split("；"):
                    if "上证指数" in seg and "点" in seg:
                        try:
                            pts = float("".join(filter(lambda x: x.isdigit() or x == ".", seg)))
                            chg = 0.0
                            if "%" in seg:
                                chg_str = seg.split("涨跌幅")[-1].split("%")[0]
                                chg = float("".join(filter(lambda x: x.isdigit() or x in ".-+", chg_str)))
                            result["sse"] = {"points": pts, "change_pct": chg}
                        except:
                            pass
                    if "深证成指" in seg and "点" in seg:
                        try:
                            pts = float("".join(filter(lambda x: x.isdigit() or x == ".", seg)))
                            chg = 0.0
                            if "%" in seg:
                                chg_str = seg.split("涨跌幅")[-1].split("%")[0]
                                chg = float("".join(filter(lambda x: x.isdigit() or x in ".-+", chg_str)))
                            result["szse"] = {"points": pts, "change_pct": chg}
                        except:
                            pass
    return result

def main():
    now = datetime.now().strftime("%Y/%m/%d %H:%M")
    print(f"\n{'='*50}")
    print(f"📊 组合分析报告 | {now}")
    print(f"{'='*50}")

    # 查询持仓股
    stock_prices = {}
    for code in PORTFOLIO:
        try:
            data = call_neodata(code)
            stock_prices[code] = parse_stock_data(data)
        except Exception as e:
            print(f"[ERROR] 查询 {code} 失败: {e}")
            stock_prices[code] = {}

    # 查询大盘指数
    try:
        index_data = call_neodata("上证指数")
        indices = parse_index_data(index_data)
    except Exception as e:
        print(f"[ERROR] 查询指数失败: {e}")
        indices = {}

    # 计算组合
    total_cost = sum(PORTFOLIO[c]["cost"] * PORTFOLIO[c]["shares"] for c in PORTFOLIO)
    total_value = sum(stock_prices.get(c, {}).get("price", PORTFOLIO[c]["cost"]) * PORTFOLIO[c]["shares"] for c in PORTFOLIO)
    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

    print(f"\n💼 持仓状况：")
    print(f"{'─'*40}")
    alerts = []
    for code in PORTFOLIO:
        info = stock_prices.get(code, {})
        name = PORTFOLIO[code]["name"]
        shares = PORTFOLIO[code]["shares"]
        cost = PORTFOLIO[code]["cost"]
        price = info.get("price", cost)
        pnl = (price - cost) * shares
        pnl_pct = (price - cost) / cost * 100
        print(f"  {name}({code}): {price:.2f}元 x {shares}股")
        print(f"    成本: {cost:.2f} | 浮盈亏: {pnl:+.2f}元 ({pnl_pct:+.2f}%)")

        # 检测阈值
        if abs(pnl_pct / 100) >= POSITION_ALERT_THRESHOLD:
            alerts.append(f"【持仓预警】{name} 浮盈亏 {pnl_pct:+.2f}%")

    print(f"\n📈 组合总览：")
    print(f"  总成本: {total_cost:,.2f}元")
    print(f"  总市值: {total_value:,.2f}元")
    print(f"  累计盈亏: {total_pnl:+.2f}元 ({total_pnl_pct:+.2f}%)")
    cash = INITIAL_CAPITAL - total_cost  # 简化计算（不含手续费）
    print(f"  现金: {cash:,.2f}元")
    print(f"  总资产: {total_value + cash:,.2f}元")

    # 大盘
    if "sse" in indices:
        sse = indices["sse"]
        print(f"\n📊 大盘：上证 {sse['points']:.2f}点 ({sse['change_pct']:+.2f}%)")
        if abs(sse["change_pct"] / 100) >= INDEX_ALERT_THRESHOLD:
            alerts.append(f"【大盘异动】上证指数单日 {sse['change_pct']:+.2f}%")

    if alerts:
        print(f"\n🚨 触发预警：")
        for a in alerts:
            print(f"  {a}")
    else:
        print(f"\n✅ 今日无异动警报")

    print(f"{'='*50}\n")
    return alerts

if __name__ == "__main__":
    try:
        main()
    except Exception as _err:
        print("执行失败（可能网关/依赖不可用）：", _err)
