#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股每日一键复盘脚本
====================
零配置开箱即用，自动获取当日大盘、板块、个股、事件等数据，输出结构化复盘报告

用法:
  python daily_review.py                 # 生成最新交易日复盘报告
  python daily_review.py --watchlist 自选股.txt   # 指定自选股列表文件
  python daily_review.py --date 2026-07-16        # 指定日期复盘
"""
import os
import sys
import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 导入通用工具
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from trading_utils import load_price, is_trade_date

def get_market_overview(date: str = None) -> dict:
    """获取大盘概览数据"""
    print("📊 正在获取大盘数据...")
    try:
        import akshare as ak
        
        # 三大指数
        indices = {
            "上证指数": "sh000001",
            "深证成指": "sz399001",
            "创业板指": "sz399006"
        }
        
        result = {}
        for name, code in indices.items():
            df = ak.stock_zh_index_daily(symbol=code)
            df = df.sort_values("date")
            if date:
                df = df[df["date"] == date]
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            pct = (latest["close"] - prev["close"]) / prev["close"] * 100
            result[name] = {
                "close": round(latest["close"], 2),
                "pct_chg": round(pct, 2),
                "volume": latest["volume"],
                "amount": latest.get("amount", 0)
            }
        
        # 涨跌家数
        stock_zh_a_spot = ak.stock_zh_a_spot_em()
        up = len(stock_zh_a_spot[stock_zh_a_spot["涨跌幅"] > 0])
        down = len(stock_zh_a_spot[stock_zh_a_spot["涨跌幅"] < 0])
        flat = len(stock_zh_a_spot[stock_zh_a_spot["涨跌幅"] == 0])
        limit_up = len(stock_zh_a_spot[stock_zh_a_spot["涨跌幅"] >= 9.8])
        limit_down = len(stock_zh_a_spot[stock_zh_a_spot["涨跌幅"] <= -9.8])
        
        result["market_stats"] = {
            "up": up,
            "down": down,
            "flat": flat,
            "limit_up": limit_up,
            "limit_down": limit_down
        }
        
        # 北向资金
        try:
            north = ak.stock_hsgt_north_net_flow_in_em()
            north_latest = north.iloc[-1]
            result["north_flow"] = round(north_latest["value"] / 1e8, 2)  # 单位：亿元
        except Exception:
            result["north_flow"] = "无数据"
        
        return result
    except Exception as e:
        print(f"获取大盘数据出错: {e}")
        return {}

def get_sector_ranks() -> dict:
    """获取板块涨幅榜/跌幅榜"""
    print("🏭 正在获取板块数据...")
    try:
        import akshare as ak
        df = ak.stock_board_industry_name_em()
        
        # 涨幅前10
        top10 = df.sort_values("涨跌幅", ascending=False).head(10)[["板块名称", "涨跌幅", "总市值"]].to_dict("records")
        # 跌幅前10
        bottom10 = df.sort_values("涨跌幅", ascending=True).head(10)[["板块名称", "涨跌幅", "总市值"]].to_dict("records")
        
        return {
            "top10": top10,
            "bottom10": bottom10
        }
    except Exception as e:
        print(f"获取板块数据出错: {e}")
        return {"top10": [], "bottom10": []}

def get_watchlist_performance(watchlist_path: str = None) -> list:
    """获取自选股当日表现"""
    print("📈 正在获取自选股表现...")
    stocks = []
    
    # 默认自选股示例
    if not watchlist_path or not os.path.exists(watchlist_path):
        # 默认空
        return []
    
    with open(watchlist_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split()
                code = parts[0]
                name = parts[1] if len(parts) > 1 else code
                stocks.append({"code": code, "name": name})
    
    result = []
    for stock in stocks:
        try:
            df = load_price(stock["code"])
            if df is None or len(df) < 2:
                continue
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            pct = (latest["close"] - prev["close"]) / prev["close"] * 100
            
            # 简单信号检测
            signal = []
            ma5 = df["close"].tail(5).mean()
            ma20 = df["close"].tail(20).mean()
            if latest["close"] > ma5 > ma20:
                signal.append("均线多头")
            if pct > 5:
                signal.append("大涨")
            if pct < -5:
                signal.append("大跌")
            if latest["close"] > df["close"].tail(60).max() * 0.98:
                signal.append("接近新高")
                
            result.append({
                "code": stock["code"],
                "name": stock["name"],
                "close": round(latest["close"], 2),
                "pct_chg": round(pct, 2),
                "signal": "/".join(signal) if signal else "-"
            })
        except Exception as e:
            print(f"获取 {stock['code']} 数据出错: {e}")
    
    return sorted(result, key=lambda x: x["pct_chg"], reverse=True)

def get_upcoming_events(date: str = None) -> dict:
    """获取未来一周事件：解禁、财报等"""
    print("📅 正在获取未来事件...")
    events = {
        "lockup": [],
        "earnings": [],
        "dividend": []
    }
    
    try:
        import akshare as ak
        # 限售解禁
        end_date = (datetime.now() + timedelta(days=7)).strftime("%Y%m%d")
        start_date = datetime.now().strftime("%Y%m%d")
        try:
            lockup = ak.stock_restricted_release_summary_em(start_date=start_date, end_date=end_date)
            events["lockup"] = lockup.head(10).to_dict("records")
        except Exception:
            pass
        
        # 财报披露计划
        try:
            report_date = ak.stock_report_disclosure_date_em(date=datetime.now().strftime("%Y%m%d"))
            events["earnings"] = report_date.head(10).to_dict("records")
        except Exception:
            pass
        
        return events
    except Exception as e:
        print(f"获取事件出错: {e}")
        return events

def generate_report(market: dict, sectors: dict, watchlist: list, events: dict, date: str) -> str:
    """生成Markdown格式复盘报告"""
    report = []
    report.append(f"# A股每日复盘 - {date}\n")
    
    # 大盘概览
    report.append("## 📊 大盘概览\n")
    report.append("| 指数 | 收盘价 | 涨跌幅 |\n|------|--------|--------|")
    for name, data in market.items():
        if name in ["market_stats", "north_flow"]:
            continue
        chg_icon = "🔴" if data["pct_chg"] > 0 else "🟢" if data["pct_chg"] < 0 else "⚪"
        report.append(f"| {name} | {data['close']} | {chg_icon} {data['pct_chg']:+.2f}% |")
    
    report.append("")
    if "market_stats" in market:
        stats = market["market_stats"]
        report.append(f"**涨跌分布**：上涨 {stats['up']} 家 / 下跌 {stats['down']} 家 / 平盘 {stats['flat']} 家")
        report.append(f"**涨跌停**：涨停 {stats['limit_up']} 家 / 跌停 {stats['limit_down']} 家")
    if "north_flow" in market:
        flow_icon = "✅" if market["north_flow"] > 0 else "❌" if isinstance(market["north_flow"], (int, float)) else ""
        report.append(f"**北向资金**：{flow_icon} 净流入 {market['north_flow']} 亿元")
    
    report.append("\n---\n")
    
    # 板块排行
    report.append("## 🏭 板块排行\n")
    report.append("### 涨幅前10\n")
    report.append("| 板块 | 涨跌幅 |\n|------|--------|")
    for b in sectors.get("top10", []):
        report.append(f"| {b['板块名称']} | {b['涨跌幅']:+.2f}% |")
    
    report.append("\n### 跌幅前10\n")
    report.append("| 板块 | 涨跌幅 |\n|------|--------|")
    for b in sectors.get("bottom10", []):
        report.append(f"| {b['板块名称']} | {b['涨跌幅']:+.2f}% |")
    
    report.append("\n---\n")
    
    # 自选股表现
    if watchlist:
        report.append("## 📈 自选股表现\n")
        report.append("| 代码 | 名称 | 收盘价 | 涨跌幅 | 信号 |\n|------|------|--------|--------|------|")
        for s in watchlist:
            chg_icon = "🔴" if s["pct_chg"] > 0 else "🟢" if s["pct_chg"] < 0 else "⚪"
            report.append(f"| {s['code']} | {s['name']} | {s['close']} | {chg_icon} {s['pct_chg']:+.2f}% | {s['signal']} |")
        report.append("\n---\n")
    
    # 未来事件
    report.append("## 📅 未来一周事件提醒\n")
    if events.get("lockup"):
        report.append("### 限售解禁\n")
        report.append("| 代码 | 名称 | 解禁日期 | 解禁市值(亿) |\n|------|------|----------|--------------|")
        for e in events["lockup"]:
            report.append(f"| {e.get('股票代码', '')} | {e.get('股票名称', '')} | {e.get('解禁日期', '')} | {round(e.get('解禁市值', 0)/1e8, 2)} |")
    
    if events.get("earnings"):
        report.append("\n### 财报披露\n")
        report.append("| 代码 | 名称 | 披露日期 | 报告期 |\n|------|------|----------|--------|")
        for e in events["earnings"]:
            report.append(f"| {e.get('代码', '')} | {e.get('名称', '')} | {e.get('披露日期', '')} | {e.get('报告期', '')} |")
    
    report.append("\n---\n")
    report.append("> ⚠️ 本报告基于公开信息自动生成，仅供参考，不构成任何投资建议。投资有风险，决策需谨慎。")
    
    return "\n".join(report)

def main():
    parser = argparse.ArgumentParser(description="A股每日一键复盘")
    parser.add_argument("--watchlist", type=str, help="自选股列表文件路径，每行格式：代码 名称")
    parser.add_argument("--date", type=str, help="指定复盘日期，格式YYYY-MM-DD，默认最新交易日")
    parser.add_argument("--output", type=str, default=None, help="输出报告文件路径，默认daily_review_YYYYMMDD.md")
    args = parser.parse_args()
    
    # 日期处理
    if args.date:
        date = args.date
    else:
        date = datetime.now().strftime("%Y-%m-%d")
        # 如果当天不是交易日，往前找
        while not is_trade_date(date.replace("-", "")):
            date = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    
    print(f"🚀 生成 {date} A股复盘报告...\n")
    
    # 获取数据
    market = get_market_overview(date.replace("-", ""))
    sectors = get_sector_ranks()
    watchlist = get_watchlist_performance(args.watchlist)
    events = get_upcoming_events(date)
    
    # 生成报告
    report = generate_report(market, sectors, watchlist, events, date)
    
    # 保存报告
    if args.output:
        output_path = args.output
    else:
        output_path = f"daily_review_{date.replace('-', '')}.md"
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"\n✅ 复盘报告已生成: {output_path}")
    print("\n" + "="*50)
    print(report)

if __name__ == "__main__":
    main()
