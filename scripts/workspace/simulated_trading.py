#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模拟交易模块
=============
本地模拟A股交易，支持市价/限价/条件单，自动计算盈亏、手续费、持仓，配套风控规则

用法:
  python simulated_trading.py buy 600519 100 1700    # 市价买入100股贵州茅台
  python simulated_trading.py sell 600519 100 1900   # 市价卖出
  python simulated_trading.py status                 # 查看持仓和盈亏
  python simulated_trading.py history                # 查看交易历史
"""
import os
import sys
import json
import argparse
from datetime import datetime
from typing import List, Dict

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from trading_utils import load_price, calc_trade_cost, TRADING_COSTS

SIM_FILE = os.path.join(os.path.expanduser("~"), ".sim_trading.json")

def load_sim() -> Dict:
    """加载模拟账户数据"""
    default = {
        "cash": 100000.0,  # 默认初始资金10万
        "positions": {},   # code: {shares, avg_cost, name}
        "trades": [],      # 交易历史
        "pending_orders": []  # 待成交条件单
    }
    if os.path.exists(SIM_FILE):
        with open(SIM_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    save_sim(default)
    return default

def save_sim(data: Dict):
    """保存模拟账户数据"""
    with open(SIM_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def place_order(code: str, name: str, shares: int, price: float, is_buy: bool, order_type: str = "market") -> Dict:
    """下单交易"""
    data = load_sim()
    
    df = load_price(code)
    if df is None:
        return {"success": False, "msg": f"无法获取 {code} 行情"}
    
    latest = df.iloc[-1]
    current_price = latest["close"]
    
    # 模拟成交价
    if order_type == "market":
        exec_price = current_price
    else:  # limit
        if is_buy and price > current_price:
            exec_price = current_price  # 限价买，当前价低于限价直接成交
        elif not is_buy and price < current_price:
            exec_price = current_price  # 限价卖，当前价高于限价直接成交
        else:
            # 条件单加入待成交列表
            order = {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "code": code,
                "name": name,
                "shares": shares if is_buy else -shares,
                "price": price,
                "type": "limit",
                "is_buy": is_buy
            }
            data["pending_orders"].append(order)
            save_sim(data)
            return {"success": True, "msg": f"限价单已挂单，待价格触发成交"}
    
    # 计算金额和手续费
    amount = exec_price * shares
    cost = calc_trade_cost(amount, is_buy)
    total = amount + cost if is_buy else amount - cost
    
    # 检查资金/持仓
    if is_buy and total > data["cash"]:
        return {"success": False, "msg": f"资金不足，需要 {total:.2f}，可用 {data['cash']:.2f}"}
    if not is_buy:
        pos = data["positions"].get(code, {})
        if pos.get("shares", 0) < shares:
            return {"success": False, "msg": f"持仓不足，持有 {pos.get('shares', 0)} 股"}
    
    # 更新资金和持仓
    if is_buy:
        data["cash"] -= total
        if code in data["positions"]:
            old = data["positions"][code]
            total_shares = old["shares"] + shares
            total_cost = old["avg_cost"] * old["shares"] + exec_price * shares
            data["positions"][code]["shares"] = total_shares
            data["positions"][code]["avg_cost"] = total_cost / total_shares
            if name:
                data["positions"][code]["name"] = name
        else:
            data["positions"][code] = {
                "shares": shares,
                "avg_cost": exec_price,
                "name": name
            }
    else:
        data["cash"] += total
        data["positions"][code]["shares"] -= shares
        if data["positions"][code]["shares"] == 0:
            del data["positions"][code]
    
    # 记录交易
    trade = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "code": code,
        "name": name,
        "shares": shares if is_buy else -shares,
        "price": round(exec_price, 2),
        "amount": round(amount, 2),
        "cost": round(cost, 2),
        "type": "buy" if is_buy else "sell"
    }
    data["trades"].append(trade)
    save_sim(data)
    
    return {"success": True, "msg": f"{'买入' if is_buy else '卖出'}成功：{shares}股 {name}({code})，成交价{exec_price:.2f}，手续费{cost:.2f}元"}

def check_pending_orders():
    """检查待成交条件单"""
    data = load_sim()
    if not data["pending_orders"]:
        return
    
    remaining = []
    for order in data["pending_orders"]:
        code = order["code"]
        df = load_price(code)
        if df is None:
            remaining.append(order)
            continue
        latest = df.iloc[-1]["close"]
        # 检查触发条件
        triggered = False
        if order["is_buy"] and latest <= order["price"]:
            triggered = True
        elif not order["is_buy"] and latest >= order["price"]:
            triggered = True
        
        if triggered:
            result = place_order(code, order["name"], abs(order["shares"]), order["price"], order["is_buy"], "market")
            print(f"条件单成交：{result['msg']}")
        else:
            remaining.append(order)
    
    data["pending_orders"] = remaining
    save_sim(data)

def show_status():
    """显示账户状态和持仓"""
    data = load_sim()
    check_pending_orders()
    data = load_sim()
    
    total_value = data["cash"]
    total_cost = 0
    positions = []
    
    print("="*80)
    print(f"📊 模拟交易账户  |  可用资金：{data['cash']:,.2f}元")
    print("-"*80)
    print(f"{'代码':<8} {'名称':<10} {'持仓':<6} {'成本价':<8} {'现价':<8} {'市值':<10} {'盈亏':<10} {'收益率':<8}")
    print("-"*80)
    
    for code, pos in data["positions"].items():
        df = load_price(code)
        if df is None:
            continue
        current = df.iloc[-1]["close"]
        market_value = current * pos["shares"]
        cost_value = pos["avg_cost"] * pos["shares"]
        profit = market_value - cost_value
        profit_pct = profit / cost_value * 100
        
        total_value += market_value
        total_cost += cost_value
        
        print(f"{code:<8} {pos.get('name', code):<10} {pos['shares']:<6} {pos['avg_cost']:<8.2f} {current:<8.2f} {market_value:<10,.2f} "
              f"{'✅' if profit>=0 else '❌'} {profit:+,.2f}  {profit_pct:+.2f}%")
        positions.append({
            "code": code,
            "name": pos.get("name", code),
            "profit_pct": profit_pct
        })
    
    print("-"*80)
    total_profit = total_value - 100000  # 初始资金10万
    total_pct = total_profit / 100000 * 100
    print(f"💵 账户总资产：{total_value:,.2f}元 | 总盈亏：{'✅' if total_profit>=0 else '❌'} {total_profit:+,.2f}元 | 收益率：{total_pct:+.2f}%")
    
    # 风控检查
    print("\n⚠️ 风控检查：")
    if positions:
        max_pct = max(p["profit_pct"] for p in positions)
        min_pct = min(p["profit_pct"] for p in positions)
        # 单票仓位预警
        for code, pos in data["positions"].items():
            df = load_price(code)
            mv = df.iloc[-1]["close"] * pos["shares"]
            weight = mv / total_value * 100
            if weight > 30:
                print(f"  ⚠️  {pos.get('name', code)} 仓位{weight:.1f}%超过30%单票上限")
        if min_pct < -8:
            print(f"  ❌ 持仓最大浮亏{min_pct:.2f}%，建议止损")
        if total_pct < -10:
            print(f"  ❌ 账户总回撤超过10%，建议降低仓位")
    print("="*80)
    
    if data["pending_orders"]:
        print(f"\n📝 待成交条件单：{len(data['pending_orders'])}个")
        for o in data["pending_orders"]:
            print(f"  {o['type']} {o['name']}({o['code']}) {abs(o['shares'])}股 @ {o['price']:.2f}")

def main():
    parser = argparse.ArgumentParser(description="A股模拟交易系统")
    subparsers = parser.add_subparsers(dest="command")
    
    # 买入命令
    buy_parser = subparsers.add_parser("buy", help="买入股票")
    buy_parser.add_argument("code", type=str, help="股票代码")
    buy_parser.add_argument("shares", type=int, help="股数")
    buy_parser.add_argument("price", type=float, nargs="?", default=0, help="限价单价格，0为市价单")
    buy_parser.add_argument("--name", type=str, default="", help="股票名称")
    
    # 卖出命令
    sell_parser = subparsers.add_parser("sell", help="卖出股票")
    sell_parser.add_argument("code", type=str, help="股票代码")
    sell_parser.add_argument("shares", type=int, help="股数")
    sell_parser.add_argument("price", type=float, nargs="?", default=0, help="限价单价格，0为市价单")
    
    # 状态命令
    subparsers.add_parser("status", help="查看持仓和账户状态")
    
    args = parser.parse_args()
    
    if args.command == "buy":
        order_type = "limit" if args.price > 0 else "market"
        result = place_order(args.code, args.name, args.shares, args.price, is_buy=True, order_type=order_type)
        print(result["msg"])
    elif args.command == "sell":
        order_type = "limit" if args.price > 0 else "market"
        result = place_order(args.code, "", args.shares, args.price, is_buy=False, order_type=order_type)
        print(result["msg"])
    elif args.command == "status":
        show_status()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
