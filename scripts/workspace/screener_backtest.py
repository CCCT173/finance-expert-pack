#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
选股结果回测与参数稳健性测试
"""
import sys
sys.path.append('.')
import pandas as pd
import numpy as np
from backtest_engine import BacktestEngine
from stock_screener import screen_ma_long

def backtest_screener_results(screener_func, top_n=10, ma_period=200, start_date="2021-01-01"):
    """
    回测选股结果，等权持有
    """
    engine = BacktestEngine()
    print(f"=== 选股策略回测：{screener_func.__name__} 前{top_n}只 ===")
    # 获取选股结果
    stocks = screener_func()
    stocks = sorted(stocks, key=lambda x: x["pct_chg"], reverse=True)[:top_n]
    results = []
    equity_list = []
    for s in stocks:
        try:
            res = engine.run_single(s["code"], s["name"], ma_period=ma_period, start_date=start_date,
                                   market_filter=False, dynamic_position=False, trailing_stop=False)
            results.append(res)
            equity_list.append(res["equity_curve"]/top_n)
            print(f"  ✅ {s['name']}({s['code']}): 策略{res['summary']['total_return_pct']:+.1f}% 持有{res['summary']['buy_hold_return_pct']:+.1f}%")
        except Exception as e:
            print(f"  ❌ {s['name']}: {e}")
    port_eq = sum(equity_list)
    total_ret = (port_eq.iloc[-1]/port_eq.iloc[0]-1)*100
    avg_bh = np.mean([r["summary"]["buy_hold_return_pct"] for r in results])
    avg_excess = np.mean([r["summary"]["excess_return_pct"] for r in results])
    max_dd = ((port_eq/port_eq.expanding().max()-1).min())*100
    print(f"\n选股组合表现：策略{total_ret:+.1f}% 持有{avg_bh:+.1f}% 超额{avg_excess:+.1f}% 最大回撤{max_dd:.1f}%")
    return {"total_return": total_ret, "avg_bh": avg_bh, "avg_excess": avg_excess, "max_dd": max_dd}

def parameter_robustness_test(code: str, name: str, param_range=None, start_date="2021-01-01"):
    """
    参数稳健性测试：测试不同MA周期下的策略表现
    """
    if param_range is None:
        param_range = [100, 150, 180, 200, 220, 250]
    engine = BacktestEngine()
    print(f"\n=== {name}({code}) 参数稳健性测试 ===")
    results = []
    for ma in param_range:
        try:
            res = engine.run_single(code, name, ma_period=ma, start_date=start_date,
                                   market_filter=False, dynamic_position=False, trailing_stop=False)
            results.append({
                "MA周期": ma,
                "策略收益%": res["summary"]["total_return_pct"],
                "持有收益%": res["summary"]["buy_hold_return_pct"],
                "超额收益%": res["summary"]["excess_return_pct"],
                "最大回撤%": res["summary"]["max_drawdown_pct"],
                "夏普比率": res["summary"]["sharpe_ratio"],
                "交易次数": res["summary"]["total_trades"]
            })
            print(f"  MA{ma:>3}: 策略{res['summary']['total_return_pct']:+7.1f}% 超额{res['summary']['excess_return_pct']:+7.1f}% 夏普{res['summary']['sharpe_ratio']:.2f}")
        except Exception as e:
            print(f"  MA{ma}: 失败 {e}")
    df = pd.DataFrame(results)
    excess_range = df["超额收益%"].max() - df["超额收益%"].min()
    all_win = (df["超额收益%"]>0).all()
    print(f"\n参数稳健性：{'✅ 稳健' if all_win and excess_range < 50 else '⚠️ 一般' if excess_range < 80 else '❌ 不稳健'}")
    print(f"  超额收益差：{excess_range:.1f}%，所有参数都跑赢：{all_win}")
    return df, all_win, excess_range

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="选股回测与参数稳健性")
    parser.add_argument("--screener", action="store_true", help="运行选股回测")
    parser.add_argument("--robust", type=str, help="参数稳健性测试，输入代码")
    parser.add_argument("--name", type=str, default="", help="标的名称")
    args = parser.parse_args()
    if args.screener:
        backtest_screener_results(screen_ma_long)
    if args.robust:
        parameter_robustness_test(args.robust, args.name)
