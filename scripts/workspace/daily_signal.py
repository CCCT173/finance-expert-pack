#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日信号生成与推送
"""
import sys
import os
import json
import requests
from datetime import datetime
import pandas as pd
from typing import List, Dict

def generate_daily_signals(watchlist: List[str], ma_period: int = 200) -> Dict:
    """生成每日交易信号"""
    from trading_utils import load_price
    signals = []
    for code in watchlist:
        try:
            df = load_price(code)
            if df is None or len(df) < ma_period +1:
                continue
            df = df.sort_values("date").reset_index(drop=True)
            ma = df["close"].rolling(ma_period).mean()
            last_close = df["close"].iloc[-1]
            last_ma = ma.iloc[-1]
            prev_ma = ma.iloc[-2]
            
            signal = "持有"
            if last_close > last_ma and prev_ma <= ma.iloc[-2]:
                signal = "买入"
            elif last_close < last_ma and prev_ma >= ma.iloc[-2]:
                signal = "卖出"
            
            signals.append({
                "code": code,
                "date": str(df["date"].iloc[-1].date()),
                "close": round(last_close, 2),
                "ma": round(last_ma, 2),
                "signal": signal
            })
        except Exception as e:
            print(f"获取{code}信号失败: {e}")
    return signals

def push_to_wechat(webhook_url: str, signals: List[Dict]):
    """推送到企业微信机器人"""
    content = "📊 今日量化策略信号\n\n"
    for s in signals:
        emoji = "🟢" if s["signal"] == "买入" else "🔴" if s["signal"] == "卖出" else "⚪"
        content += f"{emoji} {s['code']} 收盘价{s['close']} MA200={s['ma']} 信号：{s['signal']}\n"
    content += "\n⚠️ 信号仅供参考，不构成投资建议"
    
    data = {
        "msgtype": "text",
        "text": {"content": content}
    }
    requests.post(webhook_url, json=data)
    print("✅ 信号已推送到企业微信")

if __name__ == "__main__":
    # 示例：自选股信号生成
    watchlist = ["002624", "002555", "512480"]
    signals = generate_daily_signals(watchlist)
    print("今日信号：")
    for s in signals:
        print(f"  {s['code']} 收盘价{s['close']} MA{s['ma']} 信号：{s['signal']}")
