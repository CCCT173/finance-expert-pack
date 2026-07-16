#!/usr/bin/env python3
"""
市场综合情报中心
一键生成持仓股完整情报报告
= 行情 + 资金 + 消息 + 板块 + 宏观 + 动量背离
"""
import sys
import os
import re
import json
import subprocess
import urllib.request
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# 统一经 common/gateway 访问（地址可配置、优雅降级，不再硬编码私有运行时）
_COMMON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common")
if _COMMON not in sys.path:
    sys.path.insert(0, _COMMON)
from gateway import query_neodata as call_neodata, web_search_prosearch as web_search

PORTFOLIO = {
    "002624": {"name": "完美世界", "shares": 0, "cost": 0},
    "601069": {"name": "西部黄金", "shares": 0, "cost": 0},
    "600397": {"name": "江钨装备", "shares": 0, "cost": 0},
}

MACRO_QUERIES = {
    "上证指数": "上证指数",
    "S&P500": "美国标普500指数",
    "Nasdaq": "纳斯达克综合指数",
    "黄金": "黄金价格 今日",
    "原油": "WTI原油期货价格",
    "A50": "A50期货指数",
    "USD_CNY": "美元兑人民币汇率 USD CNY",
}

SECTOR_MAP = {
    "002624": {"name": "完美世界", "sector": "游戏板块"},
    "601069": {"name": "西部黄金", "sector": "黄金板块"},
    "600397": {"name": "江钨装备", "sector": "稀有金属板块"},
}

def extract(content: str, pattern: str) -> float:
    m = re.search(pattern, content)
    return float(m.group(1)) if m else None

def get_price_info(query: str) -> dict:
    data = call_neodata(query)
    recalls = data.get("data", {}).get("apiData", {}).get("apiRecall", [])
    for r in recalls:
        c = r.get("content", "")
        return {
            "price": extract(c, r'最新价格[:：]?(\d+\.?\d*)') or extract(c, r'价格[:：]?(\d+\.?\d*)'),
            "change_pct": extract(c, r'当日涨跌幅[:：]?([+-]?\d+\.?\d*)%') or extract(c, r'涨跌幅[:：]?([+-]?\d+\.?\d*)%'),
            "content": c[:200]
        }
    return {}

def main():
    now = datetime.now().strftime("%Y/%m/%d %H:%M")
    sep = "=" * 55
    print(f"\n{sep}")
    print(f"  🧠 市场综合情报中心 | {now}")
    print(f"{sep}")

    # === 1. 持仓行情 ===
    print(f"\n【持仓实时行情】")
    portfolio_data = {}
    total_cost = 0
    total_value = 0
    for code, info in PORTFOLIO.items():
        d = get_price_info(f"{info['name']}({code})")
        price = d.get("price", info["cost"])
        change = d.get("change_pct", 0)
        value = price * info["shares"]
        cost = info["cost"] * info["shares"]
        pnl = value - cost
        portfolio_data[code] = {"price": price, "change_pct": change, "value": value, "pnl": pnl}
        total_cost += cost
        total_value += value
        sign = "+" if pnl >= 0 else ""
        print(f"  {info['name']}({code}): {price}元 x {info['shares']}股")
        print(f"    今日: {change:+.2f}% | 市值: {value:,.2f}元 | 盈亏: {sign}{pnl:,.2f}元")

    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0
    sign = "+" if total_pnl >= 0 else ""
    print(f"\n  组合总市值: {total_value:,.2f}元 | 累计盈亏: {sign}{total_pnl:,.2f}元({sign}{total_pnl_pct:.2f}%)")

    # === 2. 宏观环境 ===
    print(f"\n{sep}")
    print(f"【外围宏观环境】")
    for key, query in MACRO_QUERIES.items():
        d = get_price_info(query)
        if d.get("price") or d.get("change_pct"):
            ch = f"{d['change_pct']:+.2f}%" if d.get("change_pct") is not None else "N/A"
            print(f"  {key}: {'{:.2f}'.format(d['price']) if d.get('price') else 'N/A'} ({ch})")

    # === 3. 板块对比 ===
    print(f"\n{sep}")
    print(f"【动量背离检测】")
    for code, info in SECTOR_MAP.items():
        stock_change = portfolio_data.get(code, {}).get("change_pct", 0)
        sector_d = get_price_info(info["sector"])
        sector_change = sector_d.get("change_pct", 0)
        divergence = (stock_change or 0) - (sector_change or 0)
        div_str = f"{divergence:+.2f}%"
        if divergence <= -2:
            alert = "⚠️ 警示：弱于板块"
        elif divergence >= 2:
            alert = "⚡ 提示：强于板块"
        else:
            alert = "✓ 正常"
        print(f"  {info['name']}: 个股 {stock_change:+.2f}% | 板块 {sector_change:+.2f}% | 背离 {div_str} {alert}")

    # === 4. 新闻速报 ===
    print(f"\n{sep}")
    print(f"【重要公告】")
    for code, info in PORTFOLIO.items():
        d = call_neodata(f"{info['name']} 公告")
        recalls = d.get("data", {}).get("apiData", {}).get("apiRecall", [])
        shown = 0
        for r in recalls:
            c = r.get("content", "")
            if c and shown < 2:
                print(f"\n  ▶ {info['name']}:")
                print(f"    {c[:250]}")
                shown += 1

    # === 5. 研报评级 ===
    print(f"\n{sep}")
    print(f"【机构研报】")
    for code, info in PORTFOLIO.items():
        d = call_neodata(f"{info['name']} 券商研报 机构评级")
        recalls = d.get("data", {}).get("apiData", {}).get("apiRecall", [])
        for r in recalls:
            c = r.get("content", "")
            if c and "目标价" in c:
                # 提取目标价
                target = re.search(r'目标价[为:]?\s*(\d+\.?\d*)元', c)
                rating = re.search(r'(买入|增持|中性|减持|卖出)', c)
                if target or rating:
                    parts = []
                    if target: parts.append(f"目标价: {target.group(1)}元")
                    if rating: parts.append(f"评级: {rating.group(1)}")
                    print(f"  {info['name']}: {' | '.join(parts)}")
                    print(f"    {c[:200]}")
                break

    # === 6. 实时新闻（网页搜索）===
    print(f"\n{sep}")
    print(f"【实时新闻速递】")
    news_found = False
    for code, info in PORTFOLIO.items():
        result = web_search(f"{info['name']} 今日", freshness="24h")
        if result and "未找到" not in result:
            lines = [l for l in result.split("\n") if l.strip() and l.startswith("**")]
            if lines:
                print(f"\n  ▶ {info['name']}:")
                for line in lines[:2]:
                    print(f"    {line.strip()}")
                news_found = True
    if not news_found:
        print(f"  今日无重大相关新闻")

    print(f"\n{sep}")
    print(f"  ✅ 情报汇总完成 | {now}")
    print(f"{sep}\n")

if __name__ == "__main__":
    main()
