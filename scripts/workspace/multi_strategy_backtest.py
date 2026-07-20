#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多策略组合回测
支持多个策略等权/动态权重组合回测
"""
import sys
sys.path.append('.')
import pandas as pd
import numpy as np
from backtest_engine import BacktestEngine
from strategies import ma_trend_strategy, ma_cross_strategy, rsi_reversion_strategy, macd_strategy

def multi_strategy_backtest(code: str, name: str, strategies=None, weights=None, start_date="2021-01-01"):
    """
    多策略组合回测
    :param code: 标的代码
    :param name: 标的名称
    :param strategies: 策略函数列表
    :param weights: 策略权重
    """
    if strategies is None:
        strategies = [ma_trend_strategy, ma_cross_strategy, rsi_reversion_strategy, macd_strategy]
    if weights is None:
        weights = [0.25]*len(strategies)
    engine = BacktestEngine()
    print(f"=== {name}({code}) 多策略组合回测 ===")
    equity_list = []
    strat_results = []
    for i, (strat, w) in enumerate(zip(strategies, weights)):
        try:
            res = engine.run_single(code, name, signal_func=strat, start_date=start_date,
                                   market_filter=False, dynamic_position=False, trailing_stop=False)
            equity_list.append(res["equity_curve"] * w)
            strat_results.append(res["summary"])
            print(f"  策略{i+1}: 收益{res['summary']['total_return_pct']:+.1f}% 夏普{res['summary']['sharpe_ratio']:.2f} 权重{w*100:.0f}%")
        except Exception as e:
            print(f"  策略{i+1} 失败: {e}")
    # 合并净值
    port_eq = sum(equity_list)
    total_ret = (port_eq.iloc[-1]/port_eq.iloc[0]-1)*100
    daily_ret = port_eq.pct_change().dropna()
    sharpe = np.sqrt(252)*daily_ret.mean()/daily_ret.std() if daily_ret.std()>0 else 0
    max_dd = ((port_eq/port_eq.expanding().max()-1).min())*100
    avg_single_ret = np.mean([r["total_return_pct"] for r in strat_results])
    print(f"\n组合表现：")
    print(f"  总收益: {total_ret:+.1f}% | 单策略平均: {avg_single_ret:+.1f}%")
    print(f"  夏普比率: {sharpe:.2f} | 最大回撤: {max_dd:.1f}%")
    print(f"  相比单策略：超额{total_ret - avg_single_ret:+.1f}%，回撤降低{np.mean([r['max_drawdown_pct'] for r in strat_results]) - max_dd:.1f}%")
    return {"total_return": total_ret, "sharpe": sharpe, "max_dd": max_dd}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="多策略组合回测")
    parser.add_argument("code", type=str, help="标的代码")
    parser.add_argument("--name", type=str, default="", help="标的名称")
    args = parser.parse_args()
    multi_strategy_backtest(args.code, args.name)
