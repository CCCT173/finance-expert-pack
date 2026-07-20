#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
板块批量回测，使用通用回测引擎
"""
import sys
sys.path.append('.')
import pandas as pd
from backtest_engine import BacktestEngine

# 板块成分股预设
SECTORS = {
    "游戏": ["002624", "002555", "002517", "002558", "300418"],
    "半导体": ["688981", "002371", "600584", "002049", "603986"],
    "新能源": ["300750", "002594", "601012", "002460", "300274"],
    "医药": ["600276", "300760", "000661", "300015", "603259"],
    "消费": ["600519", "000858", "002304", "600887", "000333"],
}

def backtest_sector(sector_name: str, ma_period=200, start_date="2021-01-01"):
    engine = BacktestEngine()
    codes = SECTORS.get(sector_name, [])
    if not codes:
        print(f"未知板块：{sector_name}，可选：{list(SECTORS.keys())}")
        return
    results = []
    equity_list = []
    print(f"=== {sector_name}板块回测 ===")
    for code in codes:
        try:
            res = engine.run_single(code, "", ma_period=ma_period, start_date=start_date,
                                   market_filter=False, dynamic_position=False, trailing_stop=False)
            results.append(res["summary"])
            equity_list.append(res["equity_curve"]/len(codes))
            print(f"  {code}: 策略{res['summary']['total_return_pct']:+.1f}% 持有{res['summary']['buy_hold_return_pct']:+.1f}%")
        except Exception as e:
            print(f"  {code} 失败: {e}")
            continue
    port_eq = sum(equity_list)
    total_ret = (port_eq.iloc[-1]/port_eq.iloc[0]-1)*100
    avg_bh = sum(r["buy_hold_return_pct"] for r in results)/len(results)
    avg_excess = sum(r["excess_return_pct"] for r in results)/len(results)
    max_dd = ((port_eq/port_eq.expanding().max()-1).min())*100
    print(f"\n板块平均：策略{total_ret:+.1f}% 持有{avg_bh:+.1f}% 超额{avg_excess:+.1f}% 最大回撤{max_dd:.1f}%")
    return {"total_return": total_ret, "avg_bh": avg_bh, "avg_excess": avg_excess, "max_dd": max_dd}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="板块回测工具")
    parser.add_argument("sector", type=str, help="板块名称")
    parser.add_argument("--ma", type=int, default=200, help="MA周期")
    parser.add_argument("--start", type=str, default="2021-01-01", help="开始日期")
    args = parser.parse_args()
    backtest_sector(args.sector, args.ma, args.start)
