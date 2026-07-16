#!/usr/bin/env python3
"""
三只聚焦标的的技术分析脚本
使用 akshare 获取 K 线数据，计算 MACD/KDJ/RSI/布林带 等核心指标
基于 stock-analysis-23 技能的 23 指标体系（简化版）
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

FOCUS = {
    "002624": ("完美世界", "sz"),
    "601069": ("西部黄金", "sh"),
    "600397": ("江钨装备", "sh"),
}

def get_stock_data(code, market, days=60):
    """获取日线数据"""
    try:
        if market == "sz":
            sym = f"sz{code}"
        else:
            sym = f"sh{code}"
        # 使用 stock_zh_a_daily（不走 East Money API）
        df = ak.stock_zh_a_daily(symbol=sym, adjust="qfq")
        df.columns = [c.strip() for c in df.columns]
        # 统一列名
        col_map = {}
        for c in df.columns:
            cl = c.lower()
            if "日期" in c: col_map[c] = "date"
            elif "开盘" in c or "open" in cl: col_map[c] = "open"
            elif "收盘" in c or "close" in cl: col_map[c] = "close"
            elif "最高" in c or "high" in cl: col_map[c] = "high"
            elif "最低" in c or "low" in cl: col_map[c] = "low"
            elif "成交量" in c or "vol" in cl: col_map[c] = "volume"
            elif "成交额" in c: col_map[c] = "amount"
        df = df.rename(columns=col_map)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        # 只取最近 days 天
        cutoff = datetime.now() - timedelta(days=days)
        df = df[df["date"] >= cutoff]
        return df
    except Exception as e:
        return None

def calc_MACD(close, fast=12, slow=26, signal=9):
    """MACD指标"""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd = (dif - dea) * 2
    return dif, dea, macd

def calc_KDJ(high, low, close, N=9, M1=3, M2=3):
    """KDJ指标"""
    lowest_low = low.rolling(N).min()
    highest_high = high.rolling(N).max()
    rsv = (close - lowest_low) / (highest_high - lowest_low + 1e-9) * 100
    K = rsv.ewm(com=M1-1, adjust=False).mean()
    D = K.ewm(com=M2-1, adjust=False).mean()
    J = 3 * K - 2 * D
    return K, D, J

def calc_RSI(close, N=14):
    """RSI指标"""
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    avg_gain = gain.ewm(com=N-1, adjust=False).mean()
    avg_loss = loss.ewm(com=N-1, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    rsi = 100 - 100 / (rs + 1)
    return rsi

def calc_BOLL(close, N=20, K=2):
    """布林带"""
    mid = close.rolling(N).mean()
    std = close.rolling(N).std()
    upper = mid + K * std
    lower = mid - K * std
    position = (close - lower) / (upper - lower + 1e-9)  # 价格在布林带中的位置 0~1
    return upper, mid, lower, position

def calc_MA(close, periods=[5, 10, 20, 60]):
    """均线"""
    ma = {}
    for p in periods:
        ma[p] = close.rolling(p).mean()
    return ma

def analyze_stock(name, code, market):
    """完整技术分析"""
    df = get_stock_data(code, market, days=90)
    if df is None or len(df) < 20:
        print(f"\n  ⚠️  {name}({code}): 数据获取失败")
        return

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    # 计算指标
    dif, dea, macd = calc_MACD(close)
    K, D, J = calc_KDJ(high, low, close)
    rsi = calc_RSI(close)
    upper, mid, lower, boll_pos = calc_BOLL(close)
    ma = calc_MA(close)

    latest = len(df) - 1
    c = close.iloc[latest]
    v = volume.iloc[latest] / 10000  # 万手

    # 信号判断
    signals = {}

    # MACD信号
    if latest >= 1:
        macd_prev = macd.iloc[latest-1]
        macd_curr = macd.iloc[latest]
        dif_curr = dif.iloc[latest]
        dif_prev = dif.iloc[latest-1]
        dea_prev = dea.iloc[latest-1]
        if dif_curr > dea.iloc[latest] and dif_prev <= dea_prev:
            signals["MACD"] = ("金叉", +1)
        elif dif_curr < dea.iloc[latest] and dif_prev >= dea.iloc[latest-1]:
            signals["MACD"] = ("死叉", -1)
        elif macd_curr > 0:
            signals["MACD"] = ("多头", +0.5)
        else:
            signals["MACD"] = ("空头", -0.5)

    # KDJ信号
    k_curr = K.iloc[latest]
    d_curr = D.iloc[latest]
    j_curr = J.iloc[latest]
    if k_curr > d_curr and K.iloc[latest-1] <= D.iloc[latest-1]:
        signals["KDJ"] = ("金叉", +1)
    elif k_curr < d_curr and K.iloc[latest-1] >= D.iloc[latest-1]:
        signals["KDJ"] = ("死叉", -1)
    elif j_curr > 80:
        signals["KDJ"] = ("超买", -0.5)
    elif j_curr < 20:
        signals["KDJ"] = ("超卖", +0.5)
    else:
        signals["KDJ"] = ("中性", 0)

    # RSI信号
    rsi_curr = rsi.iloc[latest]
    if rsi_curr > 70:
        signals["RSI"] = ("超买", -1)
    elif rsi_curr < 30:
        signals["RSI"] = ("超卖", +1)
    elif rsi_curr > 50:
        signals["RSI"] = ("偏多", +0.5)
    else:
        signals["RSI"] = ("偏空", -0.5)

    # 布林带信号
    boll_curr = boll_pos.iloc[latest]
    if c > upper.iloc[latest]:
        signals["BOLL"] = ("突破上轨", +1)
    elif c < lower.iloc[latest]:
        signals["BOLL"] = ("跌破下轨", -1)
    elif boll_curr > 0.8:
        signals["BOLL"] = ("上轨附近", +0.5)
    elif boll_curr < 0.2:
        signals["BOLL"] = ("下轨附近", +0.5)
    else:
        signals["BOLL"] = ("中轨附近", 0)

    # 均线信号
    ma_signals = []
    if ma[5].iloc[latest] > ma[10].iloc[latest] > ma[20].iloc[latest]:
        ma_signals.append(("多头排列", +2))
    elif ma[5].iloc[latest] < ma[10].iloc[latest] < ma[20].iloc[latest]:
        ma_signals.append(("空头排列", -2))
    if c > ma[5].iloc[latest]:
        ma_signals.append(("站上5日线", +1))
    if c > ma[20].iloc[latest]:
        ma_signals.append(("站上20日线", +1))
    if c < ma[20].iloc[latest]:
        ma_signals.append(("跌破20日线", -1))

    # 综合评分
    score = 0
    for s in signals.values():
        score += s[1]
    for _, s in ma_signals:
        score += s

    # 归一化到 -100~+100
    total_score = max(-100, min(100, score * 12))

    # 成交量变化
    vol_ma5 = volume.iloc[-5:].mean()
    vol_today = volume.iloc[latest]
    vol_ratio = vol_today / vol_ma5 if vol_ma5 > 0 else 1

    # 趋势判断
    ma20_slope = (ma[20].iloc[latest] - ma[20].iloc[max(0, latest-5)]) / ma[20].iloc[max(0, latest-5)] * 100

    dea_curr = dea.iloc[latest]
    return {
        "name": name, "code": code,
        "close": c,
        "volume": v,
        "vol_ratio": vol_ratio,
        "signals": signals,
        "ma_signals": ma_signals,
        "score": total_score,
        "rsi": rsi_curr,
        "kdj_k": k_curr, "kdj_d": d_curr, "kdj_j": j_curr,
        "macd_dif": dif_curr, "macd_dea": dea_curr,
        "macd_bar": macd.iloc[latest],
        "boll_upper": upper.iloc[latest], "boll_mid": mid.iloc[latest], "boll_lower": lower.iloc[latest],
        "ma5": ma[5].iloc[latest], "ma10": ma[10].iloc[latest], "ma20": ma[20].iloc[latest], "ma60": ma[60].iloc[latest] if len(ma[60]) > latest else None,
        "ma20_slope": ma20_slope,
    }

def _code_to_market(code):
    """根据 6 位代码判断 sh/sz 市场（用于命令行传入任意代码时自动选择）。"""
    pure = str(code).strip().lstrip("shszSHSZ")
    if pure.startswith(("6", "5", "9")):
        return "sh"
    return "sz"


def main():
    # 支持命令行传入任意代码：python technical_analysis.py 600519 000001 300750
    # 未传参则分析默认三只聚焦标的（FOCUS）。
    # 注：本脚本技术面评分(score*12 → -100~+100)为独立短线打分，与
    # analysis-framework 的加权评分卡(25/25/25/15/10)口径不同，二者不可直接相加。
    cli_codes = [a for a in sys.argv[1:] if not a.startswith("-")]
    if cli_codes:
        targets = {c.strip().lstrip("shszSHSZ"): (c, _code_to_market(c)) for c in cli_codes}
        title = "自定义标的"
    else:
        targets = {code: (name, m) for code, (name, m) in FOCUS.items()}
        title = "三只聚焦标的"

    print(f"\n{'='*60}")
    print(f"  📊 技术分析 | {title} | {datetime.now().strftime('%Y/%m/%d %H:%M')}")
    print(f"{'='*60}")

    results = {}
    for code, (name, market) in targets.items():
        r = analyze_stock(name, code, market)
        if r:
            results[code] = r

    for code, r in results.items():
        score = r["score"]
        if score >= 60: rating = "🟢 强势"
        elif score >= 30: rating = "🟡 偏强"
        elif score >= -30: rating = "⚪ 中性"
        elif score >= -60: rating = "🟠 偏弱"
        else: rating = "🔴 弱势"

        print(f"\n{'─'*55}")
        print(f"  {r['name']}({code})")
        print(f"  价格: {r['close']:.2f} | 成交量: {r['volume']:.1f}万手", end="")
        if r['vol_ratio'] > 1.5: print(f" | 量能放大 {r['vol_ratio']:.1f}x ⚠️")
        elif r['vol_ratio'] < 0.7: print(f" | 量能萎缩 {r['vol_ratio']:.1f}x")
        else: print()

        print(f"\n  📈 均线状态:")
        ma60_str = f"{r['ma60']:.2f}" if r['ma60'] else "N/A"
        print(f"    MA5={r['ma5']:.2f} | MA10={r['ma10']:.2f} | MA20={r['ma20']:.2f} | MA60={ma60_str}")
        slope = r['ma20_slope']
        slope_str = "↗" if slope > 0.5 else "↘" if slope < -0.5 else "→"
        print(f"    MA20斜率: {slope:.2f}% {slope_str}")
        if r['ma_signals']:
            for sig, _ in r['ma_signals']:
                print(f"    ✅ {sig}")
        else:
            print(f"    ○ 均线无明显信号")

        print(f"\n  ⚡ 核心指标信号:")
        for ind, (sig, _) in r["signals"].items():
            print(f"    {ind}: {sig}")

        print(f"\n  📊 技术指标读数:")
        print(f"    MACD: DIF={r['macd_dif']:.3f} DEA={r['macd_dea']:.3f} BAR={r['macd_bar']:.3f}")
        print(f"    KDJ: K={r['kdj_k']:.1f} D={r['kdj_d']:.1f} J={r['kdj_j']:.1f}")
        print(f"    RSI(14): {r['rsi']:.1f}")
        print(f"    BOLL: 上={r['boll_upper']:.2f} 中={r['boll_mid']:.2f} 下={r['boll_lower']:.2f}")

        print(f"\n  💯 综合技术评分: {score:.0f}/100 【{rating}】")

        # 简明建议
        if score >= 60:
            rec = "技术面偏强，均线多头，MACD/KDJ共振向上"
        elif score >= 30:
            rec = "技术面偏好，短线有望继续反弹"
        elif score >= -30:
            rec = "技术面中性，方向不明，观望为主"
        elif score >= -60:
            rec = "技术面偏弱，注意下行风险"
        else:
            rec = "技术面弱势，趋势向下，严控风险"
        print(f"  💡 建议: {rec}")

    print(f"\n{'='*60}")
    print(f"  ✅ 技术分析完成")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
