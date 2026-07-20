#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内置策略模板库
所有策略函数输入df，返回position序列（1持仓/0空仓），T+1延迟执行
"""
import pandas as pd
import numpy as np
from trading_utils import calc_ma, calc_macd, calc_rsi, calc_boll

def ma_trend_strategy(df: pd.DataFrame, ma_period: int = 200, **kwargs) -> pd.Series:
    """均线趋势策略：收盘价在MA上方持仓，否则空仓"""
    ma = calc_ma(df, ma_period)
    position = (df["close"] > ma).astype(int)
    return position.shift(1).fillna(0)

def ma_cross_strategy(df: pd.DataFrame, ma_short: int = 5, ma_long: int = 20, **kwargs) -> pd.Series:
    """双均线交叉策略：短均线上穿长均线买入，下穿卖出"""
    ma_s = calc_ma(df, ma_short)
    ma_l = calc_ma(df, ma_long)
    position = (ma_s > ma_l).astype(int)
    return position.shift(1).fillna(0)

def rsi_mean_reversion_strategy(df: pd.DataFrame, rsi_period: int = 14, 
                                oversold: int = 30, overbought: int = 70, **kwargs) -> pd.Series:
    """RSI均值回归策略：RSI超卖买入，超买卖出，适合震荡市"""
    rsi = calc_rsi(df, rsi_period)
    position = pd.Series(0, index=df.index)
    position[rsi < oversold] = 1
    position[rsi > overbought] = 0
    # 持仓直到超买
    position = position.ffill().fillna(0)
    return position.shift(1).fillna(0)

def boll_breakout_strategy(df: pd.DataFrame, window: int = 20, std_n: int = 2, **kwargs) -> pd.Series:
    """布林带突破策略：突破上轨买入，跌破下轨卖出，适合趋势行情"""
    upper, mid, lower = calc_boll(df, window, std_n)
    position = (df["close"] > upper).astype(int)
    position[df["close"] < lower] = 0
    position = position.ffill().fillna(0)
    return position.shift(1).fillna(0)

def macd_strategy(df: pd.DataFrame, **kwargs) -> pd.Series:
    """MACD策略：DIF上穿DEA买入，下穿卖出"""
    dif, dea, macd = calc_macd(df)
    position = (dif > dea).astype(int)
    return position.shift(1).fillna(0)

def dual_thrust_strategy(df: pd.DataFrame, lookback: int = 20, k1: float = 0.5, k2: float = 0.5, **kwargs) -> pd.Series:
    """Dual Thrust突破策略：基于N日高低点突破，经典日内策略适配日线"""
    hh = df["high"].rolling(lookback).max()
    hc = df["close"].rolling(lookback).max()
    lc = df["close"].rolling(lookback).min()
    ll = df["low"].rolling(lookback).min()
    range_val = pd.concat([hh - lc, hc - ll], axis=1).max(axis=1)
    buy_line = df["open"] + k1 * range_val
    sell_line = df["open"] - k2 * range_val
    position = pd.Series(0, index=df.index)
    position[df["close"] > buy_line] = 1
    position[df["close"] < sell_line] = 0
    position = position.ffill().fillna(0)
    return position.shift(1).fillna(0)

# 策略注册表
STRATEGIES = {
    "ma_trend": {
        "func": ma_trend_strategy,
        "name": "均线趋势",
        "description": "收盘价在MA上方持仓，默认200MA，适合趋势行情",
        "default_params": {"ma_period": 200}
    },
    "ma_cross": {
        "func": ma_cross_strategy,
        "name": "双均线交叉",
        "description": "短均线上穿长均线买入，默认5/20MA，适合波段",
        "default_params": {"ma_short": 5, "ma_long": 20}
    },
    "rsi_reversion": {
        "func": rsi_mean_reversion_strategy,
        "name": "RSI均值回归",
        "description": "RSI低于30买，高于70卖，适合震荡市",
        "default_params": {"rsi_period": 14, "oversold": 30, "overbought":70}
    },
    "boll_breakout": {
        "func": boll_breakout_strategy,
        "name": "布林带突破",
        "description": "突破上轨买，跌破下轨卖，适合趋势行情",
        "default_params": {"window": 20, "std_n": 2}
    },
    "macd": {
        "func": macd_strategy,
        "name": "MACD策略",
        "description": "DIF上穿DEA买，下穿卖，经典趋势指标",
        "default_params": {}
    },
    "dual_thrust": {
        "func": dual_thrust_strategy,
        "name": "Dual Thrust突破",
        "description": "基于N日高低点突破，适应性强",
        "default_params": {"lookback": 20, "k1":0.5, "k2":0.5}
    }
}

def get_strategy(name: str):
    """获取策略函数和默认参数"""
    if name not in STRATEGIES:
        raise ValueError(f"未知策略：{name}，可选策略：{list(STRATEGIES.keys())}")
    return STRATEGIES[name]["func"], STRATEGIES[name]["default_params"]

if __name__ == "__main__":
    print("内置策略库：")
    for k, v in STRATEGIES.items():
        print(f"  {k}: {v['name']} - {v['description']}")
