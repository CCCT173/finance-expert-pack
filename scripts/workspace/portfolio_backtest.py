#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多策略/多标的组合回测
"""
import sys
import pandas as pd
import numpy as np
from typing import List, Dict
from backtest_engine import BacktestEngine

def portfolio_backtest(holdings: List[Dict], weight_equal: bool = True) -> Dict:
    """
    多标的组合回测
    :param holdings: [{"code":"xxx", "name":"xxx", "weight":0.25}]
    :param weight_equal: True为等权，False用holdings里的weight
    """
    engine = BacktestEngine()
    equity_list = []
    weights = []
    total_return = 0
    total_bh_return = 0
    
    print("="*70)
    print("多标的组合回测")
    print("="*70)
    
    for h in holdings:
        code = h["code"]
        name = h["name"]
        try:
            res = engine.run_single(code, name, ma_period=h.get("ma_period", 200), 
                                   stop_loss=h.get("stop_loss", -0.08), start_date=h.get("start", "2021-01-01"))
            equity_list.append(res["equity_curve"])
            weight = 1/len(holdings) if weight_equal else h.get("weight", 1/len(holdings))
            weights.append(weight)
            total_return += res["summary"]["total_return_pct"] * weight
            total_bh_return += res["summary"]["buy_hold_return_pct"] * weight
            print(f"✅ {name:<10} 策略{res['summary']['total_return_pct']:+6.1f}% 持有{res['summary']['buy_hold_return_pct']:+6.1f}% 权重{weight*100:.0f}%")
        except Exception as e:
            print(f"❌ {name} 失败: {e}")
            continue
    
    # 合并净值曲线，对齐日期
    portfolio_equity = pd.DataFrame({i: e for i, e in enumerate(equity_list)}).sum(axis=1, skipna=True)
    total_return_pct = (portfolio_equity.iloc[-1] / portfolio_equity.iloc[0] - 1)*100
    rolling_max = portfolio_equity.expanding().max()
    max_dd = (portfolio_equity/rolling_max -1).min()*100
    daily_ret = portfolio_equity.pct_change().dropna()
    sharpe = np.sqrt(252)*daily_ret.mean()/daily_ret.std() if daily_ret.std()>0 else 0
    
    print("\n" + "-"*70)
    print(f"📊 组合表现：")
    print(f"  策略总收益: {total_return_pct:+.2f}%")
    print(f"  持有总收益: {total_bh_return:+.2f}%")
    print(f"  超额收益: {total_return_pct - total_bh_return:+.2f}%")
    print(f"  最大回撤: {max_dd:.2f}%")
    print(f"  夏普比率: {sharpe:.2f}")
    print("="*70)
    
    return {
        "portfolio_equity": portfolio_equity,
        "total_return_pct": total_return_pct,
        "total_bh_return_pct": total_bh_return,
        "excess_return_pct": total_return_pct - total_bh_return,
        "max_drawdown_pct": max_dd,
        "sharpe_ratio": sharpe
    }

if __name__ == "__main__":
    # 测试4个行业ETF等权组合
    holdings = [
        {"code": "512480", "name": "半导体ETF"},
        {"code": "159869", "name": "游戏ETF"},
        {"code": "516160", "name": "新能源ETF"},
        {"code": "512010", "name": "医药ETF"},
    ]
    portfolio_backtest(holdings)
