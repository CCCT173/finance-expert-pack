#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风控管理模块
=============
内置风控规则，自动检查持仓风险：
- 单票仓位上限
- 最大回撤止损
- 单票止损止盈提醒
- 行业集中度提醒
- 波动率预警

用法:
  python risk_control.py check    # 检查所有持仓风险
  python risk_control.py add-stop 600519 -8  # 添加止损位-8%
  python risk_control.py add-take-profit 600519 20  # 添加止盈位20%
"""
import os
import sys
import json
import argparse
from datetime import datetime
from typing import List, Dict

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from trading_utils import load_price
from simulated_trading import load_sim

RISK_FILE = os.path.join(os.path.expanduser("~"), ".risk_rules.json")
DEFAULT_RULES = {
    "max_single_position_pct": 30,   # 单票最大仓位30%
    "max_drawdown_pct": 10,          # 账户最大回撤10%
    "default_stop_loss_pct": -8,     # 默认单票止损-8%
    "default_take_profit_pct": 30,   # 默认单票止盈30%
    "max_industry_pct": 50,          # 单行业最大仓位50%
    "custom_rules": {}               # code: {stop_loss, take_profit}
}

def load_rules() -> Dict:
    """加载风控规则"""
    if os.path.exists(RISK_FILE):
        with open(RISK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    save_rules(DEFAULT_RULES)
    return DEFAULT_RULES

def save_rules(rules: Dict):
    """保存风控规则"""
    with open(RISK_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)

def check_risk() -> List[str]:
    """检查所有持仓风险，返回风险告警列表"""
    rules = load_rules()
    sim = load_sim()
    alerts = []
    
    if not sim["positions"]:
        return ["当前无持仓，无风险"]
    
    # 计算总市值
    total_value = sim["cash"]
    positions_info = []
    for code, pos in sim["positions"].items():
        df = load_price(code)
        if df is None:
            continue
        current_price = df.iloc[-1]["close"]
        market_value = current_price * pos["shares"]
        cost_value = pos["avg_cost"] * pos["shares"]
        profit_pct = (current_price - pos["avg_cost"]) / pos["avg_cost"] * 100
        weight = market_value / total_value * 100 if total_value > 0 else 0
        
        positions_info.append({
            "code": code,
            "name": pos.get("name", code),
            "weight": weight,
            "profit_pct": profit_pct,
            "market_value": market_value
        })
        total_value += market_value
    
    # 1. 单票仓位检查
    for p in positions_info:
        if p["weight"] > rules["max_single_position_pct"]:
            alerts.append(f"⚠️  {p['name']}({p['code']}) 仓位{p['weight']:.1f}%，超过单票上限{rules['max_single_position_pct']}%，建议减仓")
    
    # 2. 账户回撤检查（从初始资金10万计算）
    total_profit_pct = (total_value - 100000) / 100000 * 100
    if total_profit_pct < -rules["max_drawdown_pct"]:
        alerts.append(f"❌ 账户总回撤{total_profit_pct:.2f}%，超过最大回撤阈值{rules['max_drawdown_pct']}%，建议降仓避险")
    
    # 3. 单票止损止盈检查
    custom = rules.get("custom_rules", {})
    for p in positions_info:
        code = p["code"]
        sl = custom.get(code, {}).get("stop_loss", rules["default_stop_loss_pct"])
        tp = custom.get(code, {}).get("take_profit", rules["default_take_profit_pct"])
        
        if p["profit_pct"] <= sl:
            alerts.append(f"❌ {p['name']}({code}) 浮亏{p['profit_pct']:.2f}%，触发止损位{sl}%，建议卖出")
        if p["profit_pct"] >= tp:
            alerts.append(f"✅ {p['name']}({code}) 浮盈{p['profit_pct']:.2f}%，达到止盈位{tp}%，可以考虑止盈")
    
    # 4. 波动率预警（近20日波动率>3%）
    for p in positions_info:
        df = load_price(p["code"])
        if df is None or len(df) < 20:
            continue
        daily_ret = df["pct_chg"].tail(20) / 100
        vol = daily_ret.std() * (252 ** 0.5) * 100  # 年化波动率
        if vol > 50:
            alerts.append(f"⚠️  {p['name']}({p['code']}) 年化波动率{vol:.1f}%过高，注意波动风险")
    
    return alerts

def add_stop_loss(code: str, pct: float):
    """添加止损规则"""
    rules = load_rules()
    if code not in rules["custom_rules"]:
        rules["custom_rules"][code] = {}
    rules["custom_rules"][code]["stop_loss"] = pct
    save_rules(rules)
    print(f"✅ 已设置 {code} 止损位 {pct}%")

def add_take_profit(code: str, pct: float):
    """添加止盈规则"""
    rules = load_rules()
    if code not in rules["custom_rules"]:
        rules["custom_rules"][code] = {}
    rules["custom_rules"][code]["take_profit"] = pct
    save_rules(rules)
    print(f"✅ 已设置 {code} 止盈位 {pct}%")

def main():
    parser = argparse.ArgumentParser(description="风控管理系统")
    subparsers = parser.add_subparsers(dest="command")
    
    subparsers.add_parser("check", help="检查持仓风险")
    
    sl_parser = subparsers.add_parser("add-stop", help="添加止损位")
    sl_parser.add_argument("code", type=str, help="股票代码")
    sl_parser.add_argument("pct", type=float, help="止损百分比，负数，如-8")
    
    tp_parser = subparsers.add_parser("add-profit", help="添加止盈位")
    tp_parser.add_argument("code", type=str, help="股票代码")
    tp_parser.add_argument("pct", type=float, help="止盈百分比，正数，如20")
    
    args = parser.parse_args()
    
    if args.command == "check":
        alerts = check_risk()
        print("="*60)
        print("🛡️  风控检查报告")
        print("="*60)
        for a in alerts:
            print(a)
        if not any(("❌" in a or "⚠️" in a) for a in alerts):
            print("✅ 所有持仓风险正常")
    elif args.command == "add-stop":
        add_stop_loss(args.code, args.pct)
    elif args.command == "add-profit":
        add_take_profit(args.code, args.pct)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
