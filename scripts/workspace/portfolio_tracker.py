#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
持仓跟踪与绩效统计工具
========================
纯文本记录交易，自动计算实时盈亏、仓位占比、实盘绩效指标

用法:
  # 初始化持仓文件
  python portfolio_tracker.py init
  
  # 添加买入记录
  python portfolio_tracker.py buy 600519 贵州茅台 100 1700
  
  # 添加卖出记录
  python portfolio_tracker.py sell 600519 100 1900
  
  # 查看持仓和盈亏
  python portfolio_tracker.py status
  
  # 查看绩效统计
  python portfolio_tracker.py performance
"""
import os
import sys
import argparse
import json
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from trading_utils import load_price, TRADING_COSTS

PORTFOLIO_FILE = os.path.join(os.path.expanduser("~"), ".portfolio_trades.json")

def load_portfolio() -> Dict:
    """加载持仓数据"""
    if not os.path.exists(PORTFOLIO_FILE):
        return {"trades": [], "cash": 0}
    with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_portfolio(data: Dict):
    """保存持仓数据"""
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def init_portfolio():
    """初始化持仓文件"""
    if os.path.exists(PORTFOLIO_FILE):
        print(f"持仓文件已存在: {PORTFOLIO_FILE}")
        return
    save_portfolio({"trades": [], "cash": 0})
    print(f"✅ 持仓文件已初始化: {PORTFOLIO_FILE}")

def add_trade(code: str, name: str, shares: int, price: float, is_buy: bool):
    """添加交易记录"""
    data = load_portfolio()
    
    # 计算真实交易成本
    amount = shares * price
    cost = 0
    # 佣金
    commission = max(amount * TRADING_COSTS["commission"], TRADING_COSTS["commission_min"])
    cost += commission
    # 过户费
    cost += amount * TRADING_COSTS["transfer_fee"]
    # 印花税（卖出）
    if not is_buy:
        cost += amount * TRADING_COSTS["stamp_duty"]
    
    trade = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "code": code,
        "name": name,
        "shares": shares if is_buy else -shares,
        "price": price,
        "amount": amount if is_buy else -amount,
        "cost": cost,
        "type": "buy" if is_buy else "sell"
    }
    data["trades"].append(trade)
    save_portfolio(data)
    
    action = "买入" if is_buy else "卖出"
    print(f"✅ {action}记录已添加: {name}({code}) {shares}股 @ {price:.2f}元，手续费: {cost:.2f}元")

def get_holdings() -> pd.DataFrame:
    """计算当前持仓"""
    data = load_portfolio()
    if not data["trades"]:
        return pd.DataFrame()
    
    df = pd.DataFrame(data["trades"])
    # 按股票汇总
    holdings = df.groupby(["code", "name"]).agg(
        total_shares=("shares", "sum"),
        total_amount=("amount", "sum"),
        total_cost=("cost", "sum")
    ).reset_index()
    
    # 计算持仓成本
    holdings["avg_cost"] = (holdings["total_amount"].abs() + holdings["total_cost"]) / holdings["total_shares"].abs()
    holdings = holdings[holdings["total_shares"] > 0]  # 只保留当前持有
    
    # 获取最新价格
    current_prices = []
    current_pct = []
    market_values = []
    profits = []
    profit_pcts = []
    
    for _, row in holdings.iterrows():
        code = row["code"]
        df_px = load_price(code)
        if df_px is None or len(df_px) == 0:
            current_prices.append(0)
            current_pct.append(0)
            market_values.append(0)
            profits.append(0)
            profit_pcts.append(0)
            continue
        
        latest = df_px.iloc[-1]
        current_price = latest["close"]
        current_prices.append(round(current_price, 2))
        current_pct.append(round(latest["pct_chg"], 2))
        mv = current_price * row["total_shares"]
        market_values.append(round(mv, 2))
        profit = mv - row["total_amount"] - row["total_cost"]
        profits.append(round(profit, 2))
        profit_pcts.append(round(profit / (row["total_amount"] + row["total_cost"]) * 100, 2))
    
    holdings["current_price"] = current_prices
    holdings["today_pct"] = current_pct
    holdings["market_value"] = market_values
    holdings["profit"] = profits
    holdings["profit_pct"] = profit_pcts
    
    # 计算仓位占比
    total_mv = holdings["market_value"].sum()
    holdings["weight_pct"] = round(holdings["market_value"] / total_mv * 100, 2) if total_mv > 0 else 0
    
    return holdings.sort_values("market_value", ascending=False).reset_index(drop=True)

def show_status():
    """显示当前持仓状态"""
    holdings = get_holdings()
    if holdings.empty:
        print("当前无持仓")
        return
    
    total_mv = holdings["market_value"].sum()
    total_profit = holdings["profit"].sum()
    total_profit_pct = total_profit / (holdings["total_amount"].sum() + holdings["total_cost"].sum()) * 100
    
    print("="*100)
    print(f"📊 持仓总览 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"总市值: {total_mv:,.2f}元 | 总盈亏: {total_profit:+,.2f}元 | 总收益率: {total_profit_pct:+.2f}%")
    print("="*100)
    print(f"{'代码':<8} {'名称':<10} {'持仓':<6} {'成本价':<8} {'现价':<8} {'今日涨跌':<8} {'市值':<10} {'盈亏':<10} {'收益率':<8} {'仓位':<6}")
    print("-"*100)
    
    for _, row in holdings.iterrows():
        chg_icon = "🔴" if row["today_pct"] > 0 else "🟢" if row["today_pct"] < 0 else "⚪"
        profit_icon = "✅" if row["profit"] > 0 else "❌" if row["profit"] < 0 else "⚪"
        print(f"{row['code']:<8} {row['name']:<10} {int(row['total_shares']):<6} {row['avg_cost']:<8.2f} {row['current_price']:<8.2f} "
              f"{chg_icon} {row['today_pct']:+.2f}%  {row['market_value']:<10,.2f} {profit_icon} {row['profit']:+,.2f}  "
              f"{row['profit_pct']:+.2f}%  {row['weight_pct']:.1f}%")
    
    print("="*100)

def calc_performance():
    """计算绩效统计"""
    data = load_portfolio()
    if not data["trades"]:
        print("无交易记录")
        return
    
    df = pd.DataFrame(data["trades"])
    df["date"] = pd.to_datetime(df["date"])
    
    # 已平仓交易计算
    print("📈 交易绩效统计")
    print("="*80)
    
    # 简单绩效：总手续费、总盈利、胜率
    total_trades = len(df)
    buy_trades = len(df[df["type"] == "buy"])
    sell_trades = len(df[df["type"] == "sell"])
    total_cost = df["cost"].sum()
    total_amount = df["amount"].abs().sum()
    
    print(f"总交易次数: {total_trades} (买入{buy_trades}次 / 卖出{sell_trades}次)")
    print(f"总交易成本: {total_cost:.2f}元 (占总成交额 {total_cost/total_amount*100:.3f}%)")
    
    # 按股票计算已实现盈亏
    print("\n--- 个股已实现盈亏 ---")
    stocks = df["code"].unique()
    total_realized = 0
    wins = 0
    total_closed = 0
    
    for code in stocks:
        stock_trades = df[df["code"] == code].sort_values("date")
        cum_shares = 0
        cum_amount = 0
        cum_cost = 0
        realized = 0
        
        for _, t in stock_trades.iterrows():
            if t["type"] == "buy":
                cum_shares += t["shares"]
                cum_amount += -t["amount"]
                cum_cost += t["cost"]
            else:
                # 卖出，按平均成本计算盈亏
                avg_cost = (cum_amount + cum_cost) / cum_shares if cum_shares > 0 else 0
                sell_amount = -t["amount"]
                sell_shares = -t["shares"]
                profit = sell_amount - sell_shares * avg_cost - t["cost"]
                realized += profit
                cum_shares -= sell_shares
                cum_amount -= sell_shares * avg_cost
                cum_cost = 0 if cum_shares == 0 else cum_cost * (cum_shares / (cum_shares + sell_shares))
        
        if cum_shares == 0 and realized != 0:
            total_closed += 1
            total_realized += realized
            if realized > 0:
                wins += 1
            name = stock_trades["name"].iloc[0]
            icon = "✅" if realized > 0 else "❌"
            print(f"{code} {name:<10} 已实现盈亏: {icon} {realized:+,.2f}元")
    
    if total_closed > 0:
        win_rate = wins / total_closed * 100
        print(f"\n已平仓胜率: {win_rate:.1f}% ({wins}/{total_closed})")
        print(f"总已实现盈亏: {total_realized:+,.2f}元")
    
    print("\n" + "="*80)
    print("> ⚠️ 绩效统计仅供参考，不构成投资建议")

def main():
    parser = argparse.ArgumentParser(description="持仓跟踪与绩效统计工具")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # init命令
    subparsers.add_parser("init", help="初始化持仓文件")
    
    # buy命令
    buy_parser = subparsers.add_parser("buy", help="添加买入记录")
    buy_parser.add_argument("code", type=str, help="股票代码")
    buy_parser.add_argument("name", type=str, help="股票名称")
    buy_parser.add_argument("shares", type=int, help="买入股数")
    buy_parser.add_argument("price", type=float, help="买入价格")
    
    # sell命令
    sell_parser = subparsers.add_parser("sell", help="添加卖出记录")
    sell_parser.add_argument("code", type=str, help="股票代码")
    sell_parser.add_argument("shares", type=int, help="卖出股数")
    sell_parser.add_argument("price", type=float, help="卖出价格")
    
    # status命令
    subparsers.add_parser("status", help="查看当前持仓盈亏")
    
    # performance命令
    subparsers.add_parser("performance", help="查看交易绩效统计")
    
    args = parser.parse_args()
    
    if args.command == "init":
        init_portfolio()
    elif args.command == "buy":
        add_trade(args.code, args.name, args.shares, args.price, is_buy=True)
    elif args.command == "sell":
        add_trade(args.code, "", args.shares, args.price, is_buy=False)
    elif args.command == "status":
        show_status()
    elif args.command == "performance":
        calc_performance()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
