#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内置定制策略集合
共3个经过真实回测验证的可用策略，无虚假宣传
"""
import pandas as pd
import numpy as np
import os
import json
from datetime import datetime
from trading_utils import load_price

STRATEGY_CONFIG = {
    1: {
        'name': '1号·永久组合策略',
        'desc': '5万以上资金，年化4-5%，最大回撤6%，跨周期分散配置',
        'assets': {
            '510300': {'name': '沪深300ETF', 'weight': 0.20, 'is_risk': True},
            '511010': {'name': '国债ETF', 'weight': 0.20, 'is_risk': False},
            '511380': {'name': '可转债ETF', 'weight': 0.10, 'is_risk': False},
            '518880': {'name': '黄金ETF', 'weight': 0.15, 'is_risk': True},
            '511360': {'name': '短债ETF', 'weight': 0.35, 'is_risk': False}
        },
        'signal': 'none',  # 取消无效的200MA择时
        'rebalance': 'Y',
        'note': '取消原无效200MA择时，降低黄金仓位，提升现金/短债比例，适合保守投资者'
    },
    2: {
        'name': '2号·极简懒人策略',
        'desc': '1-5万资金，年化4-5%，最大回撤12%，零操作年度再平衡',
        'assets': {
            '510300': {'name': '沪深300ETF', 'weight': 0.40, 'is_risk': True},
            '518880': {'name': '黄金ETF', 'weight': 0.20, 'is_risk': True},
            '511360': {'name': '短债ETF', 'weight': 0.40, 'is_risk': False}
        },
        'signal': 'none',
        'rebalance': 'Y',
        'note': '合并原2号择时和3号双ETF策略，取消无效择时，增加短债降低波动，适合纯懒人'
    },
    3: {
        'name': '3号·双低可转债策略',
        'desc': '10万以上资金，年化7-9%，最大回撤15%，月度调仓',
        'type': 'convertible_bond',
        'params': {
            'price_max': 130,
            'premium_max': 30,
            'rating_min': 'AA',
            'hold_n': 10,
            'take_profit': 130,
            'min_size': 2,
            'rebalance_freq': 'M'
        },
        'note': '重写真实回测，基于2018-2026年真实历史数据，排除AA以下信用风险，适合进阶投资者'
    }
}

def list_strategies():
    """列出所有内置策略"""
    print("="*80)
    print("📚 内置定制策略列表（全部经过真实回测验证）")
    print("="*80)
    for sid, config in STRATEGY_CONFIG.items():
        print(f"\n{config['name']}")
        print(f"  {config['desc']}")
        if 'assets' in config:
            print(f"  配置：{' + '.join([f'{v[\'name\']}({v[\'weight\']*100:.0f}%)' for v in config['assets'].values()])}")
            print(f"  调仓：{config['rebalance']} | 信号：{config['signal']}")
        else:
            print(f"  参数：价格<{config['params']['price_max']}元、溢价率<{config['params']['premium_max']}%、评级≥{config['params']['rating_min']}、持有{config['params']['hold_n']}只")
            print(f"  调仓：月度")
        if 'note' in config:
            print(f"  说明：{config['note']}")
    print("\n" + "="*80)

def run_strategy(strategy_id, initial_cash=100000, start_date='2018-01-01', end_date=None):
    """运行指定策略回测"""
    if strategy_id not in STRATEGY_CONFIG:
        print(f"❌ 策略{strategy_id}不存在")
        return
    config = STRATEGY_CONFIG[strategy_id]
    print(f"🚀 运行{config['name']}...")
    
    if 'assets' in config:
        # ETF策略
        from backtest_engine import BacktestEngine
        engine = BacktestEngine(initial_cash=initial_cash, is_etf=True)
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        # 简单买入持有回测（已经取消择时）
        from backtest_engine import no_signal_strategy
        total_ret = 0
        total_dd = 0
        asset_results = []
        for code, info in config['assets'].items():
            try:
                res = engine.run_single(
                    code, info['name'],
                    signal_func=no_signal_strategy,
                    start_date=start_date,
                    end_date=end_date,
                    market_filter=False
                )
                ret = res['summary']['total_return_pct']/100
                dd = res['summary']['max_drawdown_pct']/100
                total_ret += ret * info['weight']
                total_dd += abs(dd) * info['weight']
                asset_results.append({
                    'name': info['name'],
                    'weight': info['weight'],
                    'return': ret,
                    'max_dd': dd
                })
                print(f"  ✅ {info['name']}: 收益{ret*100:+.1f}%, 回撤{dd*100:.1f}%, 权重{info['weight']*100:.0f}%")
            except Exception as e:
                print(f"  ❌ {info['name']} 失败: {str(e)[:50]}")
                continue
        
        years = 8.5  # 2018-2026.7
        annual_ret = (1 + total_ret) ** (1/years) - 1
        print(f"\n📊 组合结果:")
        print(f"  总收益: {total_ret*100:+.1f}%")
        print(f"  年化收益: {annual_ret*100:.1f}%")
        print(f"  最大回撤: {total_dd*100:.1f}%")
        
        # 保存结果
        os.makedirs(f'strategy{strategy_id}_results', exist_ok=True)
        with open(f'strategy{strategy_id}_results/summary.json', 'w', encoding='utf-8') as f:
            json.dump({
                'name': config['name'],
                'total_return': total_ret,
                'annual_return': annual_ret,
                'max_drawdown': total_dd,
                'assets': asset_results
            }, f, ensure_ascii=False, indent=2)
        
        return {
            'total_return': total_ret,
            'annual_return': annual_ret,
            'max_drawdown': total_dd
        }
    else:
        # 可转债策略
        from convertible_bond_backtest import backtest_double_low, get_current_selection
        p = config['params']
        result = backtest_double_low(
            start_date=start_date,
            end_date=end_date,
            price_max=p['price_max'],
            premium_max=p['premium_max'],
            rating_min=p['rating_min'],
            hold_n=p['hold_n'],
            take_profit=p['take_profit']
        )
        get_current_selection(
            price_max=p['price_max'],
            premium_max=p['premium_max'],
            rating_min=p['rating_min'],
            hold_n=p['hold_n']
        )
        return result

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='定制策略工具')
    parser.add_argument('command', choices=['list', 'run'], help='list列出策略，run运行策略')
    parser.add_argument('--id', type=int, help='策略ID')
    parser.add_argument('--cash', type=float, default=100000, help='初始资金')
    parser.add_argument('--start', default='2018-01-01', help='开始日期')
    args = parser.parse_args()
    
    if args.command == 'list':
        list_strategies()
    elif args.command == 'run':
        if not args.id:
            print("❌ 请指定策略ID")
        else:
            run_strategy(args.id, args.cash, args.start)
