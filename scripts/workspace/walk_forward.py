#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Walk Forward 滚动验证
模拟实盘动态调参：前N年训练选最优参数，下一年测试，逐年滚动
"""
import sys
import pandas as pd
import numpy as np
from typing import List, Dict
from backtest_engine import BacktestEngine, ma_trend_strategy

def walk_forward_test(code: str, name: str = "",
                     param_range: List[int] = None,
                     train_years: int = 5,
                     start_year: int = 2016,
                     end_year: int = 2026) -> Dict:
    """
    Walk Forward滚动验证
    :param code: 标的代码
    :param name: 标的名称
    :param param_range: MA参数测试范围
    :param train_years: 训练期年数
    :param start_year: 起始年份
    :param end_year: 结束年份
    """
    if param_range is None:
        param_range = [100, 150, 180, 200, 220, 250]
    
    engine = BacktestEngine()
    results = []
    robust_years = 0
    total_excess = 0
    
    print(f"=== Walk Forward滚动验证：{name}({code}) ===")
    print(f"训练期：{train_years}年 | 参数范围：{param_range}\n")
    
    for test_year in range(start_year + train_years, end_year + 1):
        # 训练期：前train_years年
        train_start = f"{test_year - train_years}-01-01"
        train_end = f"{test_year - 1}-12-31"
        # 测试期：当年
        test_start = f"{test_year}-01-01"
        test_end = f"{test_year}-12-31"
        
        # 在训练期找最优MA参数
        best_param = 200
        best_return = -np.inf
        for ma in param_range:
            try:
                res = engine.run_single(code, name, ma_period=ma, start_date=train_start, end_date=train_end)
                if res["summary"]["total_return_pct"] > best_return:
                    best_return = res["summary"]["total_return_pct"]
                    best_param = ma
            except:
                continue
        
        # 用最优参数跑测试期
        try:
            test_res = engine.run_single(code, name, ma_period=best_param, start_date=test_start, end_date=test_end)
            strategy_ret = test_res["summary"]["total_return_pct"]
            bh_ret = test_res["summary"]["buy_hold_return_pct"]
            excess = strategy_ret - bh_ret
            total_excess += excess
            if excess > 0:
                robust_years += 1
            
            results.append({
                "年份": test_year,
                "最优MA": best_param,
                "训练期收益%": round(best_return, 1),
                "测试期策略收益%": round(strategy_ret, 1),
                "测试期持有收益%": round(bh_ret, 1),
                "超额收益%": round(excess, 1)
            })
            print(f"📅 {test_year}年: 最优MA{best_param} | 策略{strategy_ret:+.1f}% | 持有{bh_ret:+.1f}% | 超额{excess:+.1f}%")
        except Exception as e:
            print(f"❌ {test_year}年测试失败: {e}")
            continue
    
    df = pd.DataFrame(results)
    win_rate = robust_years / len(results) * 100 if results else 0
    avg_excess = total_excess / len(results) if results else 0
    
    # 稳健性评分
    robustness_score = 0
    if win_rate >= 70 and avg_excess > 10:
        robustness_score = 100
        conclusion = "✅ 策略非常稳健，不同年份和参数下都能跑赢，未来大概率有效"
    elif win_rate >= 60 and avg_excess > 0:
        robustness_score = 70
        conclusion = "⚠️  策略比较稳健，大部分年份跑赢，可以实盘使用"
    elif win_rate >= 50:
        robustness_score = 50
        conclusion = "⚠️  策略表现一般，部分年份跑输，谨慎使用"
    else:
        robustness_score = 30
        conclusion = "❌ 策略稳健性差，过拟合风险高，不建议实盘"
    
    print("\n" + "="*70)
    print(f"📊 滚动验证结果汇总：")
    print("-"*70)
    print(df.to_string(index=False))
    print("-"*70)
    print(f"✅ 跑赢年份: {robust_years}/{len(results)} ({win_rate:.0f}%)")
    print(f"📈 平均年度超额收益: {avg_excess:+.1f}%")
    print(f"🛡️  稳健性评分: {robustness_score}/100")
    print(f"💡 结论: {conclusion}")
    print("="*70)
    
    return {
        "results": df,
        "win_rate": win_rate,
        "avg_excess": avg_excess,
        "robustness_score": robustness_score,
        "conclusion": conclusion
    }

if __name__ == "__main__":
    # 测试完美世界
    walk_forward_test("002624", "完美世界")
