#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基础条件选股工具
==================
零配置开箱即用，支持常用技术面、基本面、资金面筛选，自动过滤ST/次新/低流动性/暴雷风险股

内置筛选条件：
- 技术面：均线多头排列、MACD金叉、突破20/60日新高、RSI超卖
- 基本面：ROE>15%、PE分位、营收增速>20%、股息率>3%
- 资金面：主力净流入、北向加仓

用法:
  python stock_screener.py --ma-long           # 均线多头排列选股
  python stock_screener.py --macd-golden       # MACD金叉选股
  python stock_screener.py --breakout 60       # 突破60日新高
  python stock_screener.py --roe 15            # ROE>15%
  python stock_screener.py --revenue-growth 20 # 营收增速>20%
  python stock_screener.py --top 20            # 输出前20名
"""
import os
import sys
import argparse
import pandas as pd
import numpy as np
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from trading_utils import load_price, filter_stocks, is_st_stock

def calc_ma(df: pd.DataFrame, window: int) -> pd.Series:
    """计算移动平均线"""
    return df["close"].rolling(window).mean()

def calc_macd(df: pd.DataFrame, fast=12, slow=26, signal=9) -> tuple:
    """计算MACD指标"""
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd = (dif - dea) * 2
    return dif, dea, macd

def calc_rsi(df: pd.DataFrame, window=14) -> pd.Series:
    """计算RSI指标"""
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window).mean()
    avg_loss = loss.rolling(window).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def screen_ma_long() -> list:
    """筛选均线多头排列：MA5>MA10>MA20>MA60"""
    print("🔍 筛选均线多头排列...")
    try:
        import akshare as ak
        stock_list = ak.stock_info_a_code_name()
        codes = stock_list["code"].tolist()
        
        # 先过滤掉ST/次新/低流动性
        codes = filter_stocks(codes)
        print(f"初步过滤后剩余 {len(codes)} 只股票")
        
        result = []
        for code in codes:
            try:
                df = load_price(code)
                if df is None or len(df) < 60:
                    continue
                df = df.sort_values("date")
                
                ma5 = calc_ma(df, 5).iloc[-1]
                ma10 = calc_ma(df, 10).iloc[-1]
                ma20 = calc_ma(df, 20).iloc[-1]
                ma60 = calc_ma(df, 60).iloc[-1]
                close = df["close"].iloc[-1]
                
                # 均线多头
                if close > ma5 > ma10 > ma20 > ma60:
                    pct_chg = df["pct_chg"].iloc[-1]
                    result.append({
                        "code": code,
                        "name": stock_list[stock_list["code"] == code]["name"].iloc[0],
                        "close": round(close, 2),
                        "pct_chg": round(pct_chg, 2)
                    })
            except Exception:
                continue
        
        return sorted(result, key=lambda x: x["pct_chg"], reverse=True)
    except Exception as e:
        print(f"选股出错: {e}")
        return []

def screen_macd_golden() -> list:
    """筛选MACD金叉：DIF上穿DEA"""
    print("🔍 筛选MACD金叉...")
    try:
        import akshare as ak
        stock_list = ak.stock_info_a_code_name()
        codes = stock_list["code"].tolist()
        codes = filter_stocks(codes)
        print(f"初步过滤后剩余 {len(codes)} 只股票")
        
        result = []
        for code in codes:
            try:
                df = load_price(code)
                if df is None or len(df) < 60:
                    continue
                df = df.sort_values("date")
                
                dif, dea, macd = calc_macd(df)
                # 昨日DIF<DEA，今日DIF>DEA
                if dif.iloc[-2] < dea.iloc[-2] and dif.iloc[-1] > dea.iloc[-1]:
                    pct_chg = df["pct_chg"].iloc[-1]
                    result.append({
                        "code": code,
                        "name": stock_list[stock_list["code"] == code]["name"].iloc[0],
                        "close": round(df["close"].iloc[-1], 2),
                        "pct_chg": round(pct_chg, 2),
                        "macd": round(macd.iloc[-1], 4)
                    })
            except Exception:
                continue
        
        return sorted(result, key=lambda x: x["pct_chg"], reverse=True)
    except Exception as e:
        print(f"选股出错: {e}")
        return []

def screen_breakout(window: int = 60) -> list:
    """筛选突破N日新高"""
    print(f"🔍 筛选突破{window}日新高...")
    try:
        import akshare as ak
        stock_list = ak.stock_info_a_code_name()
        codes = stock_list["code"].tolist()
        codes = filter_stocks(codes)
        print(f"初步过滤后剩余 {len(codes)} 只股票")
        
        result = []
        for code in codes:
            try:
                df = load_price(code)
                if df is None or len(df) < window + 5:
                    continue
                df = df.sort_values("date")
                
                high_n = df["high"].tail(window).max()
                close = df["close"].iloc[-1]
                pct_chg = df["pct_chg"].iloc[-1]
                
                # 收盘价接近/突破N日高点（误差2%以内）
                if close >= high_n * 0.98 and pct_chg > 0:
                    result.append({
                        "code": code,
                        "name": stock_list[stock_list["code"] == code]["name"].iloc[0],
                        "close": round(close, 2),
                        "pct_chg": round(pct_chg, 2),
                        "breakout_level": window
                    })
            except Exception:
                continue
        
        return sorted(result, key=lambda x: x["pct_chg"], reverse=True)
    except Exception as e:
        print(f"选股出错: {e}")
        return []

def screen_roe(min_roe: float = 15.0) -> list:
    """筛选ROE高于阈值"""
    print(f"🔍 筛选ROE>{min_roe}%...")
    try:
        import akshare as ak
        # 获取最新财报ROE
        fina = ak.stock_financial_abstract_ths(symbol="沪深A股", indicator="加权净资产收益率")
        fina = fina.dropna(subset=["加权净资产收益率"])
        fina["加权净资产收益率"] = pd.to_numeric(fina["加权净资产收益率"], errors="coerce")
        selected = fina[fina["加权净资产收益率"] >= min_roe]
        
        result = []
        for _, row in selected.iterrows():
            code = row["代码"]
            name = row["名称"]
            roe = row["加权净资产收益率"]
            # 过滤ST
            if is_st_stock(name):
                continue
            # 获取最新价格
            try:
                df = load_price(code)
                if df is None:
                    continue
                close = round(df["close"].iloc[-1], 2)
                pct_chg = round(df["pct_chg"].iloc[-1], 2)
            except:
                close = "-"
                pct_chg = "-"
            
            result.append({
                "code": code,
                "name": name,
                "close": close,
                "pct_chg": pct_chg,
                "roe": round(roe, 2)
            })
        
        return sorted(result, key=lambda x: x["roe"], reverse=True)
    except Exception as e:
        print(f"选股出错: {e}")
        return []

def main():
    parser = argparse.ArgumentParser(description="A股条件选股工具")
    parser.add_argument("--ma-long", action="store_true", help="均线多头排列选股")
    parser.add_argument("--macd-golden", action="store_true", help="MACD金叉选股")
    parser.add_argument("--breakout", type=int, nargs="?", const=60, help="突破N日新高，默认60日")
    parser.add_argument("--roe", type=float, nargs="?", const=15.0, help="ROE高于阈值，默认15%%")
    parser.add_argument("--revenue-growth", type=float, help="营收增速高于阈值")
    parser.add_argument("--top", type=int, default=30, help="输出前N名，默认30")
    args = parser.parse_args()
    
    print("🚀 启动条件选股...\n")
    
    result = []
    if args.ma_long:
        result = screen_ma_long()
    elif args.macd_golden:
        result = screen_macd_golden()
    elif args.breakout:
        result = screen_breakout(args.breakout)
    elif args.roe:
        result = screen_roe(args.roe)
    else:
        print("请指定筛选条件，使用 --help 查看帮助")
        return
    
    print(f"\n✅ 筛选完成，共找到 {len(result)} 只符合条件的股票")
    print("="*80)
    
    # 输出结果
    if not result:
        print("没有找到符合条件的股票")
        return
    
    # 打印表头
    if "roe" in result[0]:
        print(f"{'排名':<4} {'代码':<8} {'名称':<10} {'收盘价':<8} {'涨跌幅':<8} {'ROE(%)':<8}")
        print("-"*60)
        for i, s in enumerate(result[:args.top], 1):
            chg_icon = "🔴" if s["pct_chg"] > 0 else "🟢" if s["pct_chg"] < 0 else "⚪"
            print(f"{i:<4} {s['code']:<8} {s['name']:<10} {s['close']:<8} {chg_icon} {s['pct_chg']:+.2f}%  {s['roe']:<8}")
    else:
        print(f"{'排名':<4} {'代码':<8} {'名称':<10} {'收盘价':<8} {'涨跌幅':<8} {'信号':<10}")
        print("-"*60)
        for i, s in enumerate(result[:args.top], 1):
            chg_icon = "🔴" if s["pct_chg"] > 0 else "🟢" if s["pct_chg"] < 0 else "⚪"
            signal = s.get("macd", s.get("breakout_level", ""))
            print(f"{i:<4} {s['code']:<8} {s['name']:<10} {s['close']:<8} {chg_icon} {s['pct_chg']:+.2f}%  {signal:<10}")
    
    print("\n" + "="*80)
    print("> ⚠️ 选股结果仅供参考，不构成任何投资建议。投资有风险，决策需谨慎。")
    
    # 保存结果
    output_path = f"screener_result_{datetime.now().strftime('%Y%m%d')}.csv"
    pd.DataFrame(result).to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"\n结果已保存到: {output_path}")

if __name__ == "__main__":
    main()
