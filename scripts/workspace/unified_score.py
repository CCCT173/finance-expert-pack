#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一评分模型 (Unified Scoring Model)
==================================================================
整合 technical_analysis.py 的独立打分(-100~+100) 与 analysis-framework.md
的加权评分卡(1-10, 权重 25/25/25/15/10)，解决「两套口径不一致」问题。

设计原则
--------
1. 所有维度「可计算」，不依赖 LLM 手填；统一 0-100 量纲（越高越看多）。
2. 单一加权总分 -> 行动标签，对齐 analysis-framework 的行动语义。
3. 缺失维度自动从权重中剔除并重新归一化（不猜、不补零、标记「未取到」）。
4. 纯 pandas/numpy，无网络调用；取数由 stock_enhanced / stock_fundamentals /
   stock_capital_data 负责，本模块只做「算分」。

维度与默认权重（对齐 analysis-framework.md）：
    technical     技术面  0.25
    valuation     估值    0.25
    capital       资金面  0.25
    fundamental   基本面  0.15
    sentiment     事件    0.10
"""
import numpy as np
import pandas as pd

DEFAULT_WEIGHTS = {
    "technical": 0.25,
    "valuation": 0.25,
    "capital": 0.25,
    "fundamental": 0.15,
    "sentiment": 0.10,
}


def _clamp(x, lo=0, hi=100):
    try:
        return max(lo, min(hi, float(x)))
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------
# 1) 技术面（纯价格序列，0-100）
# --------------------------------------------------------------------------
def score_technical(close, high, low, as_vector=False):
    """由 OHLC 序列计算技术面评分。

    返回：
        as_vector=False -> (score:float|None, detail:dict)
        as_vector=True  -> (score_series:pd.Series, detail_series:dict[pd.Series])
    不足 60 根返回 None（warmup）。
    """
    close = pd.Series(close, dtype="float64").reset_index(drop=True)
    high = pd.Series(high, dtype="float64").reset_index(drop=True)
    low = pd.Series(low, dtype="float64").reset_index(drop=True)
    n = len(close)
    if n < 60:
        if as_vector:
            nan = pd.Series([np.nan] * n)
            return nan, {k: nan.copy() for k in ["ma_s", "macd_s", "kdj_s", "rsi_s", "boll_s"]}
        return None, {"error": "数据不足60根(warmup)"}

    # --- 指标序列 ---
    ma5 = close.rolling(5).mean()
    ma10 = close.rolling(10).mean()
    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()

    ema_f = close.ewm(span=12, adjust=False).mean()
    ema_s = close.ewm(span=26, adjust=False).mean()
    dif = ema_f - ema_s
    dea = dif.ewm(span=9, adjust=False).mean()
    macd = (dif - dea) * 2

    ll = low.rolling(9).min()
    hh = high.rolling(9).max()
    rsv = (close - ll) / (hh - ll + 1e-9) * 100
    K = rsv.ewm(com=2, adjust=False).mean()
    D = K.ewm(com=2, adjust=False).mean()
    J = 3 * K - 2 * D

    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    ag = gain.ewm(com=13, adjust=False).mean()
    al = loss.ewm(com=13, adjust=False).mean()
    rsi = 100 - 100 / (ag / (al + 1e-9) + 1)

    bmid = close.rolling(20).mean()
    bstd = close.rolling(20).std()
    bupper = bmid + 2 * bstd
    blower = bmid - 2 * bstd
    boll_pos = (close - blower) / (bupper - blower + 1e-9)

    # --- 子分（0-100）---
    ma_s = np.where(
        (close > ma20) & (ma20 > ma60), 90,
        np.where(close > ma20, 70,
                 np.where(close > ma5, 50,
                          np.where((close < ma20) & (ma20 < ma60), 15, 35))))
    macd_s = np.where(
        (dif > dea) & (macd > 0), 85,
        np.where(dif > dea, 65,
                 np.where((dif < dea) & (macd < 0), 25, 45)))
    kdj_s = np.where(
        (K > D) & (J > 50), 80,
        np.where(K > D, 65,
                 np.where(J < 20, 45, 50)))
    rsi_s = np.where(
        (rsi >= 50) & (rsi <= 80), 80,
        np.where(rsi > 80, 65,
                 np.where(rsi >= 40, 60, 35)))
    boll_s = np.where(
        boll_pos > 0.8, 82,
        np.where(boll_pos > 0.5, 68,
                 np.where(boll_pos > 0.2, 52, 40)))

    tech = 0.35 * ma_s + 0.25 * macd_s + 0.15 * kdj_s + 0.15 * rsi_s + 0.10 * boll_s
    tech = pd.Series(tech).clip(0, 100)

    if as_vector:
        detail = {
            "ma_s": pd.Series(ma_s, dtype="float64"),
            "macd_s": pd.Series(macd_s, dtype="float64"),
            "kdj_s": pd.Series(kdj_s, dtype="float64"),
            "rsi_s": pd.Series(rsi_s, dtype="float64"),
            "boll_s": pd.Series(boll_s, dtype="float64"),
        }
        return tech, detail

    c = float(close.iloc[-1])
    detail = {
        "ma_s": round(float(ma_s[-1]), 1),
        "macd_s": round(float(macd_s[-1]), 1),
        "kdj_s": round(float(kdj_s[-1]), 1),
        "rsi_s": round(float(rsi_s[-1]), 1),
        "boll_s": round(float(boll_s[-1]), 1),
        "price": round(c, 2),
        "ma20": round(float(ma20.iloc[-1]), 2),
        "ma60": round(float(ma60.iloc[-1]), 2) if not pd.isna(ma60.iloc[-1]) else None,
        "rsi": round(float(rsi.iloc[-1]), 1),
        "kdj_j": round(float(J.iloc[-1]), 1),
        "macd_bar": round(float(macd.iloc[-1]), 3),
        "boll_pos": round(float(boll_pos.iloc[-1]), 2),
    }
    return round(float(tech.iloc[-1]), 1), detail


# --------------------------------------------------------------------------
# 1.5) 动量（价格趋势因子，0-100；与 valuation 的反转偏向互补）
# --------------------------------------------------------------------------
def score_momentum(close, high=None, low=None, as_vector=False):
    """动量因子（0-100）：20/60/120 日收益 + MA 多头排列 + 距52周新高 proximity。
    纯价格序列，因果窗口（只用截至当日的数据）；不足 120 根返回 None（warmup）。

    子分融合：
        r120(0.4) + r60(0.3) + r20(0.3)  -> 70%
        MA5>10>20>60 多头排列            -> 15%
        close / 250日最高(距52周新高)     -> 15%
    """
    close = pd.Series(close, dtype="float64").reset_index(drop=True)
    n = len(close)
    if n < 120:
        if as_vector:
            nan = pd.Series([np.nan] * n)
            return nan, {k: nan.copy() for k in ["r20", "r60", "r120", "ma_align", "dist_high"]}
        return None, {"error": "数据不足120根(warmup)"}

    ret20 = close / close.shift(20) - 1
    ret60 = close / close.shift(60) - 1
    ret120 = close / close.shift(120) - 1
    ma5 = close.rolling(5).mean()
    ma10 = close.rolling(10).mean()
    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()
    ma_align = ((ma5 > ma10) & (ma10 > ma20) & (ma20 > ma60)).astype(float)
    dist_high = (close / close.rolling(250, min_periods=120).max()).clip(0, 1)

    def _clip(x, lo=0, hi=100):
        return np.clip(x, lo, hi)

    r20_s = _clip(50 + ret20 * 150)
    r60_s = _clip(50 + ret60 * 120)
    r120_s = _clip(50 + ret120 * 80)
    mom = (0.4 * r120_s + 0.3 * r60_s + 0.3 * r20_s) * 0.7 + ma_align * 100 * 0.15 + dist_high * 100 * 0.15
    mom = _clip(mom)

    if as_vector:
        return pd.Series(mom), {
            "r20": pd.Series(r20_s), "r60": pd.Series(r60_s), "r120": pd.Series(r120_s),
            "ma_align": pd.Series(ma_align * 100), "dist_high": pd.Series(dist_high * 100),
        }

    c = float(close.iloc[-1])
    return round(float(mom.iloc[-1]), 1), {
        "ret20_pct": round(float(ret20.iloc[-1] * 100), 1) if pd.notna(ret20.iloc[-1]) else None,
        "ret60_pct": round(float(ret60.iloc[-1] * 100), 1) if pd.notna(ret60.iloc[-1]) else None,
        "ret120_pct": round(float(ret120.iloc[-1] * 100), 1) if pd.notna(ret120.iloc[-1]) else None,
        "ma_align": bool(ma_align.iloc[-1]),
        "dist_high_pct": round(float(dist_high.iloc[-1] * 100), 1),
    }


# --------------------------------------------------------------------------
# 2) 估值（PE 历史分位，0-100；越便宜分越高）
# --------------------------------------------------------------------------
def score_valuation(pe_series, current_pe=None, window=750):
    """pe_series: 按日期升序的历史 PE（可含 NaN）；current_pe 可选（缺省取末值）。
    返回 (score:float|None, detail:dict)。
    """
    s = pd.Series(pe_series, dtype="float64").dropna()
    if len(s) < 60:
        return None, {"error": "PE样本不足60"}
    cur = float(s.iloc[-1]) if current_pe is None or pd.isna(current_pe) else float(current_pe)
    if cur <= 0:
        return 30, {"note": "盈利为负(亏损股)，估值分锁定低位", "pe_cur": cur, "pe_pct": None}
    tail = s.tail(window)
    pct = float((tail < cur).mean() * 100)  # 当前PE在历史中的分位，越低越便宜
    val = _clamp(100 - pct)
    return round(val, 1), {
        "pe_cur": round(cur, 2),
        "pe_pct": round(pct, 1),
        "pe_min": round(float(tail.min()), 2),
        "pe_max": round(float(tail.max()), 2),
    }


def valuation_series(pe_series, window=750):
    """向量化：返回与 pe_series 对齐的每日估值分位序列（NaN 直到样本充足）。"""
    s = pd.Series(pe_series, dtype="float64")
    out = pd.Series([np.nan] * len(s), index=s.index)

    def _pct(x):
        x = x[~np.isnan(x)]
        if len(x) < 60 or np.isnan(x[-1]) or x[-1] <= 0:
            return np.nan
        return (x < x[-1]).mean() * 100

    raw = s.rolling(window, min_periods=60).apply(_pct, raw=True)
    out = (100 - raw).clip(0, 100)
    return out


# --------------------------------------------------------------------------
# 3) 资金面（北向/融资/主力，0-100；数据缺失返回 None）
# --------------------------------------------------------------------------
def score_capital(north_change_pct=None, margin_change_pct=None, fund_flow_5d_pct=None):
    """各输入为近 N 日变化百分比（正=流入/增持）。缺失传 None。"""
    parts, wsum = [], 0.0
    if north_change_pct is not None:
        parts.append((_pct_to_score(north_change_pct, 5.0), 0.4)); wsum += 0.4
    if margin_change_pct is not None:
        parts.append((_pct_to_score(margin_change_pct, 8.0), 0.3)); wsum += 0.3
    if fund_flow_5d_pct is not None:
        parts.append((_pct_to_score(fund_flow_5d_pct, 3.0), 0.3)); wsum += 0.3
    if not parts:
        return None, {"error": "无资金面数据"}
    score = sum(s * w for s, w in parts) / wsum
    return round(_clamp(score), 1), {"parts": [(round(s, 1), w) for s, w in parts]}


# --------------------------------------------------------------------------
# 4) 基本面（ROE/营收/净利趋势，0-100；缺失返回 None）
# --------------------------------------------------------------------------
def score_fundamental(roe_ttm=None, rev_growth=None, profit_growth=None):
    parts, wsum = [], 0.0
    if roe_ttm is not None:
        parts.append((_roe_score(roe_ttm), 0.5)); wsum += 0.5
    if rev_growth is not None:
        parts.append((_growth_score(rev_growth), 0.25)); wsum += 0.25
    if profit_growth is not None:
        parts.append((_growth_score(profit_growth), 0.25)); wsum += 0.25
    if not parts:
        return None, {"error": "无基本面数据"}
    return round(_clamp(sum(s * w for s, w in parts) / wsum), 1), {
        "roe": roe_ttm, "rev_growth": rev_growth, "profit_growth": profit_growth
    }


# --------------------------------------------------------------------------
# 5) 事件/情绪（研报评级/新闻催化，0-100；缺失返回 None）
# --------------------------------------------------------------------------
def score_sentiment(research_rating=None, news_positivity=None):
    """research_rating: 机构评级均值映射(买入=90/增持=75/中性=50/减持=25)；
    news_positivity: -100~100 原始情绪分。缺失传 None。"""
    parts, wsum = [], 0.0
    if research_rating is not None:
        parts.append((_clamp(research_rating), 0.6)); wsum += 0.6
    if news_positivity is not None:
        parts.append((_clamp((news_positivity + 100) / 2), 0.4)); wsum += 0.4
    if not parts:
        return None, {"error": "无事件/情绪数据"}
    return round(sum(s * w for s, w in parts) / wsum, 1), {
        "research_rating": research_rating, "news_positivity": news_positivity
    }


# --------------------------------------------------------------------------
# 合成
# --------------------------------------------------------------------------
def unified_score(scores, weights=None):
    """scores: {dim: 0-100 | None}；weights: 可选覆盖。
    返回 (total:float|None, action:str|None, detail:dict)。
    缺失维度自动剔除并重新归一化。
    """
    w = weights or DEFAULT_WEIGHTS
    avail = {d: s for d, s in scores.items() if s is not None and d in w}
    if not avail:
        return None, None, {"error": "无可用维度，无法合成"}
    wsum = sum(w[d] for d in avail)
    total = sum(scores[d] * w[d] for d in avail) / wsum
    total = round(_clamp(total), 1)
    return total, _action_tag(total), {
        "available": list(avail.keys()),
        "renorm_weights": {d: round(w[d] / wsum, 3) for d in avail},
    }


def _action_tag(t):
    if t >= 70:
        return "轻仓试探（信号强）"
    if t >= 55:
        return "持有观察"
    if t >= 40:
        return "等回调"
    if t >= 25:
        return "回避至证据改善"
    return "回避"


# --- 内部小工具 ---
def _pct_to_score(pct, scale):
    """变化百分比映射到 0-100：0%->50，+scale%->100，-scale%->0（线性夹紧）。"""
    return _clamp(50 + (pct / scale) * 50)


def _roe_score(roe):
    # ROE >=15% 优, 0% 中性, <0 差
    return _clamp(50 + roe * 3)


def _growth_score(g):
    # 增速 0%->50, +30%->100, -30%->0
    return _clamp(50 + g * (50 / 30.0))


if __name__ == "__main__":
    # 自测：构造一段假数据验证不崩溃
    import numpy as np
    rng = np.random.default_rng(0)
    n = 120
    price = 10 + np.cumsum(rng.normal(0, 0.1, n))
    hi = price + 0.2
    lo = price - 0.2
    ts, td = score_technical(price, hi, lo)
    print("tech score:", ts, td)
    vs, vd = score_valuation(pd.Series(rng.normal(20, 5, n)), current_pe=18)
    print("val score:", vs, vd)
    tot, act, det = unified_score({"technical": ts, "valuation": vs})
    print("unified:", tot, act, det)
