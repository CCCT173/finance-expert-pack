#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易通用工具模块
================
统一回测交易规则、成本计算、数据缓存、股票过滤等公共功能
所有回测/实盘模块统一调用，保证规则一致
"""
import os
import json
import time
import pandas as pd
import numpy as np
import requests
import socket
from datetime import datetime, timedelta
from functools import lru_cache

socket.setdefaulttimeout(15)
requests.adapters.DEFAULT_RETRIES = 2

# -------------------------- 全局配置 --------------------------
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# A股真实交易成本（2026年标准）
TRADING_COSTS = {
    "commission": 0.00025,      # 佣金万2.5，买卖双边
    "commission_min": 5,        # 单笔最低佣金5元
    "stamp_duty": 0.001,        # 印花税千1，仅卖出收
    "transfer_fee": 0.00001,    # 过户费十万分之1，买卖双边
    "slippage": 0.001,          # 滑点千1，买卖双边
}

# 股票过滤规则
FILTER_RULES = {
    "min_list_days": 60,               # 上市满60天
    "min_avg_amount": 50_000_000,      # 日均成交额>5000万
    "exclude_st": True,                # 排除ST/*ST
    "exclude_delisting": True,         # 排除退市整理股
    "exclude_suspended": True,         # 排除停牌股
}

# -------------------------- 数据缓存系统 --------------------------
def cache_path(prefix: str, code: str) -> str:
    """获取缓存文件路径"""
    return os.path.join(CACHE_DIR, f"{prefix}_{code}.csv")

def is_cache_valid(path: str, days: int = 7) -> bool:
    """检查缓存是否在有效期内"""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return False
    mtime = datetime.fromtimestamp(os.path.getmtime(path))
    return datetime.now() - mtime < timedelta(days=days)

@lru_cache(maxsize=128)
def load_price(code: str, adjust: str = "qfq", use_cache: bool = True) -> pd.DataFrame:
    """
    加载股票日线数据，带本地缓存
    缓存有效期：7天
    返回列: date, open, high, low, close, volume, amount, pct_chg
    """
    cp = cache_path("px", code)
    need_cols = ["date", "open", "high", "low", "close", "volume", "amount"]
    
    # 读取缓存
    if use_cache and is_cache_valid(cp, days=7):
        try:
            df = pd.read_csv(cp, parse_dates=["date"])
            if set(need_cols).issubset(df.columns) and len(df) > 0:
                df = df.sort_values("date").reset_index(drop=True)
                df["pct_chg"] = df["close"].pct_change() * 100
                return df
        except Exception:
            pass
    
    # 从akshare拉取
    sym = ("sh" if code[0] in "569" else "sz") + code
    for _ in range(2):
        try:
            import akshare as ak
            df = ak.stock_zh_a_daily(symbol=sym, adjust=adjust)
            df = df.rename(columns={c: c.lower().strip() for c in df.columns})
            if not set(need_cols).issubset(df.columns):
                return None
            
            df["date"] = pd.to_datetime(df["date"])
            df = df[need_cols].sort_values("date").reset_index(drop=True)
            df["pct_chg"] = df["close"].pct_change() * 100
            
            # 存缓存
            df.to_csv(cp, index=False, encoding="utf-8")
            return df
        except Exception as e:
            time.sleep(1)
    return None

# -------------------------- 交易成本计算 --------------------------
def calc_trade_cost(amount: float, is_buy: bool) -> float:
    """
    计算真实交易成本
    :param amount: 成交金额（元）
    :param is_buy: True=买入, False=卖出
    :return: 成本金额（元）
    """
    cost = 0
    # 佣金
    commission = max(amount * TRADING_COSTS["commission"], TRADING_COSTS["commission_min"])
    cost += commission
    # 过户费
    cost += amount * TRADING_COSTS["transfer_fee"]
    # 滑点
    cost += amount * TRADING_COSTS["slippage"]
    # 印花税（仅卖出）
    if not is_buy:
        cost += amount * TRADING_COSTS["stamp_duty"]
    
    return cost

def apply_execution_price(price: float, is_buy: bool, slippage_bps: float = None) -> float:
    """
    计算实际成交价格（滑点模拟）
    :param price: 目标价格
    :param is_buy: 买入价加滑点，卖出价减滑点
    :param slippage_bps: 自定义滑点（基点），None用默认值
    :return: 实际成交价
    """
    if slippage_bps is None:
        slippage_bps = TRADING_COSTS["slippage"] * 10000  # 转换为基点
    if is_buy:
        return price * (1 + slippage_bps / 10000)
    else:
        return price * (1 - slippage_bps / 10000)

# -------------------------- 交易规则检查 --------------------------
def can_trade(df_row: pd.Series, is_buy: bool) -> bool:
    """
    检查当日是否可以交易
    :param df_row: 当日行情数据
    :param is_buy: 买入/卖出
    :return: True=可以交易, False=不可成交
    """
    close = df_row["close"]
    open_p = df_row["open"]
    high = df_row["high"]
    low = df_row["low"]
    pct = df_row.get("pct_chg", 0)
    
    # 涨跌停判断
    limit_up = close >= open_p * 1.098  # 涨停（ST是5%，后面过滤ST了）
    limit_down = close <= open_p * 0.902
    
    if is_buy and limit_up:
        return False  # 涨停买不进
    if not is_buy and limit_down:
        return False  # 跌停卖不出
    if high == low:
        return False  # 一字板停牌/涨跌停，不可成交
    return True

# -------------------------- 股票过滤 --------------------------
def is_st_stock(name: str) -> bool:
    """判断是否ST/*ST股票"""
    name = name.upper()
    return "ST" in name or "*ST" in name or "退" in name

def filter_stocks(code_list: list, date: str = None) -> list:
    """
    过滤不符合要求的股票
    :param code_list: 股票代码列表
    :param date: 过滤基准日期，None为最新日期
    :return: 过滤后的股票代码列表
    """
    filtered = []
    try:
        import akshare as ak
        # 获取股票基本信息
        stock_info = ak.stock_info_a_code_name()
        name_map = dict(zip(stock_info["code"], stock_info["name"]))
        
        for code in code_list:
            name = name_map.get(code, "")
            if FILTER_RULES["exclude_st"] and is_st_stock(name):
                continue
            
            # 加载行情检查流动性
            df = load_price(code)
            if df is None or len(df) < FILTER_RULES["min_list_days"]:
                continue
            
            # 检查上市天数
            df = df.sort_values("date")
            if len(df) < FILTER_RULES["min_list_days"]:
                continue
            
            # 检查日均成交额（最近20日）
            recent = df.tail(20)
            avg_amount = recent["amount"].mean()
            if avg_amount < FILTER_RULES["min_avg_amount"]:
                continue
            
            # 检查停牌
            if date:
                if pd.to_datetime(date) not in df["date"].values:
                    continue
            
            filtered.append(code)
    except Exception as e:
        print(f"股票过滤出错: {e}")
        return code_list  # 出错时返回原列表
    
    return filtered

# -------------------------- 交易日历 --------------------------
@lru_cache(maxsize=1)
def get_trade_dates(start: str, end: str) -> list:
    """获取A股交易日历"""
    try:
        import akshare as ak
        df = ak.tool_trade_date_hist_sina()
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        mask = (df["trade_date"] >= start) & (df["trade_date"] <= end)
        return df[mask]["trade_date"].dt.strftime("%Y-%m-%d").tolist()
    except Exception:
        # 降级：生成工作日
        dates = pd.date_range(start=start, end=end, freq="B")
        return dates.strftime("%Y-%m-%d").tolist()

def is_trade_date(date: str) -> bool:
    """判断是否为交易日"""
    return date in get_trade_dates("2020-01-01", "2030-12-31")

# -------------------------- 技术指标计算 --------------------------
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
