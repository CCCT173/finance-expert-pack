#!/usr/bin/env python3
"""
增强版A股行情查询工具 v2.0
基于 unified-data-sources.md 整合多维度数据

数据源优先级:
- K线: BaoStock(主) -> 东财HTTP(备) -> 腾讯HTTP(兜底)
- 实时行情: 东财HTTP(主) -> 腾讯HTTP(备)
- 资金流向: 东财HTTP
- 技术指标: 本地计算(MA/MACD/KDJ/布林带)

用法:
  python stock_enhanced.py 600066              # 默认: 行情+技术+资金
  python stock_enhanced.py 600066 000630        # 多股
  python stock_enhanced.py 600066 --all         # 全部维度
  python stock_enhanced.py 600066 --quick       # 仅实时行情
  python stock_enhanced.py 600066 --tech        # 行情+技术面
  python stock_enhanced.py 600066 --fund        # 含资金流向
  python stock_enhanced.py 600066 --north       # 含北向资金
  python stock_enhanced.py 600066 --margin      # 含融资融券
  python stock_enhanced.py 600066 --lhb         # 含龙虎榜
  python stock_enhanced.py 600066 --holder      # 含机构持仓
"""

import sys
import json
import time
import os
import traceback
from datetime import datetime, timedelta

# ---- 绕过系统代理 ----
for _k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']:
    os.environ.pop(_k, None)
os.environ['no_proxy'] = '*'
os.environ['NO_PROXY'] = '*'

import requests
# 猴子补丁: 全局禁用系统代理
_OrigMerge = requests.Session.merge_environment_settings
def _NoProxyMerge(self, url, proxies, stream, verify, cert):
    return {'proxies': {}, 'stream': stream, 'verify': verify, 'cert': cert}
requests.Session.merge_environment_settings = _NoProxyMerge

import urllib.request as urllib2

# ---- 缓存 ----
_cache = {}
CACHE_TTL = {"realtime": 60, "intraday": 300, "daily": 7200, "quarterly": 86400}

def _get_cached(key, ttl_type="intraday"):
    if key in _cache:
        data, ts = _cache[key]
        if time.time() - ts < CACHE_TTL.get(ttl_type, 300):
            return data
    return None

def _set_cached(key, data):
    _cache[key] = (data, time.time())

# ---- 工具函数 ----
def _pure_code(code):
    code = str(code).strip()
    for p in ["sh", "sz", "SH", "SZ", "bj", "BJ"]:
        if code.lower().startswith(p):
            return code[2:]
    return code

def _bs_code(code):
    """BaoStock代码: sh.600066 / sz.000630"""
    pure = _pure_code(code)
    if pure.startswith("6") or pure.startswith("9"):
        return f"sh.{pure}"
    return f"sz.{pure}"

def _em_secid(code):
    """东财secid: 1.600066 / 0.000630"""
    pure = _pure_code(code)
    if pure.startswith("6") or pure.startswith("9"):
        return f"1.{pure}"
    return f"0.{pure}"

def safe_float(val, default=None):
    try:
        if val is None or val == '-' or val == '':
            return default
        return float(val)
    except (ValueError, TypeError):
        return default


def _recent_report_dates(n=4):
    """返回最近 n 个季度末日期(YYYYMMDD)，按时间倒序。

    用于基金持仓 / 财报等需要报告期的 akshare 接口。当前季度通常尚未披露完毕，
    因此从上一季度末开始往前推，避免取到空数据（原代码写死 20251231 在未来，必空）。
    """
    today = datetime.now()
    q_end_day = {3: 31, 6: 30, 9: 30, 12: 31}
    m = today.month
    if m <= 3:
        y, m = today.year - 1, 12
    elif m <= 6:
        y, m = today.year, 3
    elif m <= 9:
        y, m = today.year, 6
    else:
        y, m = today.year, 9
    dates = []
    for _ in range(n):
        dates.append(f"{y}{m:02d}{q_end_day[m]:02d}")
        if m == 3:
            y, m = y - 1, 12
        elif m == 6:
            m = 3
        elif m == 9:
            m = 6
        else:
            m = 9
    return dates

# ---- HTTP 请求 ----
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Referer": "https://quote.eastmoney.com/",
}

def _http_get_json(url, params=None, timeout=10):
    try:
        r = requests.get(url, params=params, headers=_HEADERS, timeout=timeout, verify=False)
        return r.json()
    except Exception:
        return None

def _http_get_text(url, timeout=10, encoding='gbk'):
    try:
        req = urllib2.Request(url, headers={"User-Agent": _HEADERS["User-Agent"]})
        opener = urllib2.build_opener(urllib2.ProxyHandler({}))
        with opener.open(req, timeout=timeout) as resp:
            return resp.read().decode(encoding, errors='ignore')
    except Exception:
        return None


# =============================================
# 1. 实时行情
# =============================================
def get_realtime(code):
    pure = _pure_code(code)
    cached = _get_cached(f"rt_{pure}", "realtime")
    if cached:
        return cached

    result = {"code": pure, "update_time": datetime.now().strftime("%H:%M:%S")}

    # 主源: 东财 push2
    try:
        secid = _em_secid(code)
        data = _http_get_json(
            "https://push2.eastmoney.com/api/qt/stock/get",
            params={
                "secid": secid,
                "fields": "f43,f44,f45,f46,f47,f48,f50,f51,f52,f55,f57,f58,f60,f116,f117,f162,f167,f168,f169,f170,f171,f292",
                "ut": "fa5fd1943c7b386f172d6893dbfba10b",
            }
        )
        if data and data.get("data"):
            d = data["data"]
            result.update({
                "name": d.get("f58", ""),
                "price": safe_float(d.get("f43")) / 100 if d.get("f43") else None,
                "prev_close": safe_float(d.get("f60")) / 100 if d.get("f60") else None,
                "open": safe_float(d.get("f46")) / 100 if d.get("f46") else None,
                "high": safe_float(d.get("f44")) / 100 if d.get("f44") else None,
                "low": safe_float(d.get("f45")) / 100 if d.get("f45") else None,
                "volume": d.get("f47"),  # 手
                "amount": d.get("f48"),  # 元
                "amplitude": safe_float(d.get("f171")) / 100 if d.get("f171") else None,
                "turnover": safe_float(d.get("f168")) / 100 if d.get("f168") else None,
                "pe_ttm": safe_float(d.get("f167")) / 100 if d.get("f167") else None,
                "pb": safe_float(d.get("f162")) / 100 if d.get("f162") else None,
                "total_mv": d.get("f116"),  # 元
                "circ_mv": d.get("f117"),   # 元
                "change_pct": safe_float(d.get("f170")) / 100 if d.get("f170") else None,
                "chg_amt": safe_float(d.get("f169")) / 100 if d.get("f169") else None,
                "qty_ratio": safe_float(d.get("f50")) / 100 if d.get("f50") else None,
                "source": "em_push2",
            })
            _set_cached(f"rt_{pure}", result)
            return result
    except Exception:
        pass

    # 备源: 腾讯行情
    try:
        flag = "sh" if pure.startswith("6") or pure.startswith("9") else "sz"
        text = _http_get_text(f"http://qt.gtimg.cn/q={flag}{pure}")
        if text and "~" in text:
            parts = text.split("~")
            if len(parts) > 40:
                result.update({
                    "name": parts[1],
                    "price": safe_float(parts[3]),
                    "prev_close": safe_float(parts[4]),
                    "open": safe_float(parts[5]),
                    "volume": safe_float(parts[6]),
                    "high": safe_float(parts[33]) if len(parts) > 33 else None,
                    "low": safe_float(parts[34]) if len(parts) > 34 else None,
                    "amount": safe_float(parts[37]) if len(parts) > 37 else None,
                    "change_pct": safe_float(parts[32]) if len(parts) > 32 else None,
                    "source": "tencent_qt",
                })
                _set_cached(f"rt_{pure}", result)
                return result
    except Exception:
        pass

    result["error"] = "所有数据源均失败"
    return result


# =============================================
# 2. K线 + 技术面 (MA/MACD/KDJ/布林带)
# =============================================
def get_kline(code, days=120):
    """K线数据 - BaoStock(主) -> 东财HTTP(备)"""
    pure = _pure_code(code)
    cached = _get_cached(f"kl_{pure}", "intraday")
    if cached:
        return cached

    rows = []

    # 主源: BaoStock
    try:
        import baostock as bs
        lg = bs.login()
        start = (datetime.now() - timedelta(days=days*2)).strftime("%Y-%m-%d")
        rs = bs.query_history_k_data_plus(
            _bs_code(code),
            "date,open,high,low,close,volume,amount,turn,pctChg",
            start_date=start, adjust="2"  # 前复权
        )
        while rs.error_code == '0' and rs.next():
            row = rs.get_row_data()
            rows.append({
                "date": row[0],
                "open": safe_float(row[1]),
                "high": safe_float(row[2]),
                "low": safe_float(row[3]),
                "close": safe_float(row[4]),
                "volume": safe_float(row[5]),
                "amount": safe_float(row[6]),
                "turnover": safe_float(row[7]),
                "change_pct": safe_float(row[8]),
            })
        bs.logout()
    except Exception:
        pass

    # 备源: 东财HTTP K线
    if not rows:
        try:
            secid = _em_secid(code)
            data = _http_get_json(
                "https://push2his.eastmoney.com/api/qt/stock/kline/get",
                params={
                    "secid": secid,
                    "fields1": "f1,f2,f3,f4,f5,f6",
                    "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
                    "klt": "101", "fqt": "1",
                    "beg": (datetime.now() - timedelta(days=days*2)).strftime("%Y%m%d"),
                    "end": "20500101",
                    "ut": "fa5fd1943c7b386f172d6893dbfba10b",
                }
            )
            if data and data.get("data") and data["data"].get("klines"):
                for line in data["data"]["klines"]:
                    parts = line.split(",")
                    if len(parts) >= 6:
                        rows.append({
                            "date": parts[0],
                            "open": safe_float(parts[1]),
                            "close": safe_float(parts[2]),
                            "high": safe_float(parts[3]),
                            "low": safe_float(parts[4]),
                            "volume": safe_float(parts[5]),
                            "amount": safe_float(parts[6]) if len(parts) > 6 else None,
                            "change_pct": safe_float(parts[8]) if len(parts) > 8 else None,
                        })
        except Exception:
            pass

    # 备源2: akshare 新浪日线（东财/baostock 均不可用时兜底，覆盖面更广）
    if not rows:
        try:
            import akshare as ak
            flag = f"sz{pure}" if pure.startswith(("0", "3")) else f"sh{pure}"
            raw = ak.stock_zh_a_daily(
                symbol=flag,
                start_date=(datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d"),
                end_date="20500101",
                adjust="qfq",
            )
            if raw is not None and len(raw) > 0:
                raw = raw.sort_values("date")
                pct_col = "pct_change" if "pct_change" in raw.columns else None
                for _, r in raw.iterrows():
                    rows.append({
                        "date": str(r["date"]),
                        "open": safe_float(r["open"]),
                        "close": safe_float(r["close"]),
                        "high": safe_float(r["high"]),
                        "low": safe_float(r["low"]),
                        "volume": safe_float(r["volume"]),
                        "amount": None,
                        "change_pct": safe_float(r[pct_col]) if pct_col else None,
                    })
                _set_cached(f"kl_{pure}", {"_src": "akshare_sina"})
        except Exception:
            pass

    if not rows:
        return {"error": "K线数据获取失败"}

    # 取最近 days 天
    rows = rows[-days:]

    # 计算技术指标
    import pandas as pd
    df = pd.DataFrame(rows)
    for col in ["open", "close", "high", "low", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # MA
    for n in [5, 10, 20, 30, 60]:
        if "close" in df.columns:
            df[f"ma{n}"] = df["close"].rolling(n).mean().round(2)

    # MACD (12,26,9)
    if "close" in df.columns and len(df) > 35:
        ema12 = df["close"].ewm(span=12, adjust=False).mean()
        ema26 = df["close"].ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()
        macd_bar = 2 * (dif - dea)
        df["dif"] = dif.round(3)
        df["dea"] = dea.round(3)
        df["macd"] = macd_bar.round(3)

    # KDJ (9,3,3)
    if all(c in df.columns for c in ["close", "high", "low"]) and len(df) > 9:
        low9 = df["low"].rolling(9).min()
        high9 = df["high"].rolling(9).max()
        rsv = (df["close"] - low9) / (high9 - low9) * 100
        rsv = rsv.fillna(50)
        k = rsv.ewm(com=2, adjust=False).mean()
        d = k.ewm(com=2, adjust=False).mean()
        j = 3 * k - 2 * d
        df["k"] = k.round(2)
        df["d"] = d.round(2)
        df["j"] = j.round(2)

    # 布林带 (20,2)
    if "close" in df.columns and len(df) > 20:
        df["boll_mid"] = df["close"].rolling(20).mean().round(2)
        std20 = df["close"].rolling(20).std()
        df["boll_up"] = (df["boll_mid"] + 2 * std20).round(2)
        df["boll_dn"] = (df["boll_mid"] - 2 * std20).round(2)

    # 最近5天详情
    recent = df.tail(5)
    days_list = []
    tech_cols = ["date", "open", "close", "high", "low", "volume",
                 "ma5", "ma10", "ma20", "ma30", "ma60",
                 "dif", "dea", "macd", "k", "d", "j",
                 "boll_up", "boll_mid", "boll_dn"]
    for _, row in recent.iterrows():
        day = {}
        for col in tech_cols:
            if col in row.index and pd.notna(row[col]):
                val = row[col]
                day[col] = round(float(val), 3) if isinstance(val, float) else str(val)
        days_list.append(day)

    # 最新技术面汇总
    last = df.iloc[-1]
    summary = {}
    for key in ["close", "ma5", "ma10", "ma20", "ma30", "ma60",
                "dif", "dea", "macd", "k", "d", "j",
                "boll_up", "boll_mid", "boll_dn"]:
        if key in last.index and pd.notna(last[key]):
            summary[key] = round(float(last[key]), 3)

    # 信号判断
    if "dif" in summary and "dea" in summary:
        summary["macd_cross"] = "金叉" if summary["dif"] > summary["dea"] else "死叉"
        # 检查前一日是否即将金叉
        if len(df) > 1:
            prev = df.iloc[-2]
            if pd.notna(prev.get("dif")) and pd.notna(prev.get("dea")):
                if prev["dif"] <= prev["dea"] and summary["dif"] > summary["dea"]:
                    summary["macd_cross"] = "今日金叉✅"
                elif prev["dif"] >= prev["dea"] and summary["dif"] < summary["dea"]:
                    summary["macd_cross"] = "今日死叉⚠️"

    if "j" in summary:
        j_val = summary["j"]
        if j_val < 0:
            summary["kdj_status"] = f"极度超卖(J={j_val})🔻"
        elif j_val < 20:
            summary["kdj_status"] = f"超卖(J={j_val})"
        elif j_val > 100:
            summary["kdj_status"] = f"超买(J={j_val})🔺"
        elif j_val > 80:
            summary["kdj_status"] = f"偏高(J={j_val})"
        else:
            summary["kdj_status"] = f"中性(J={j_val})"

    if "close" in summary and "boll_dn" in summary:
        if summary["close"] <= summary["boll_dn"]:
            summary["boll_status"] = "触及下轨🔻"
        elif summary["close"] >= summary.get("boll_up", 99999):
            summary["boll_status"] = "触及上轨🔺"
        else:
            summary["boll_status"] = "中轨区间"

    if "close" in summary and "ma5" in summary:
        summary["above_ma5"] = summary["close"] > summary["ma5"]

    result = {"recent_5d": days_list, "summary": summary, "source": "baostock"}
    _set_cached(f"kl_{pure}", result)
    return result


# =============================================
# 3. 资金流向 (东财HTTP)
# =============================================
def get_fund_flow(code):
    pure = _pure_code(code)
    cached = _get_cached(f"ff_{pure}", "intraday")
    if cached:
        return cached

    result = {}
    try:
        secid = _em_secid(code)
        data = _http_get_json(
            "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get",
            params={
                "secid": secid,
                "fields1": "f1,f2,f3,f7",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
                "lmt": "10",
                "klt": "101",
                "ut": "fa5fd1943c7b386f172d6893dbfba10b",
            }
        )
        if data and data.get("data") and data["data"].get("klines"):
            days = []
            for line in data["data"]["klines"]:
                parts = line.split(",")
                if len(parts) >= 8:
                    day = {
                        "date": parts[0],
                        "main_net": safe_float(parts[1]),       # 主力净流入
                        "small_net": safe_float(parts[2]),      # 散户净流入
                        "main_pct": safe_float(parts[3]),       # 主力净占比
                        "super_net": safe_float(parts[4]) if len(parts) > 4 else None,  # 超大单
                        "big_net": safe_float(parts[5]) if len(parts) > 5 else None,    # 大单
                        "mid_net": safe_float(parts[6]) if len(parts) > 6 else None,    # 中单
                        "sml_net": safe_float(parts[7]) if len(parts) > 7 else None,    # 小单
                    }
                    days.append(day)
            result["days"] = days
            if days:
                # 5日汇总
                recent5 = days[-5:]
                result["main_net_5d"] = sum(d.get("main_net", 0) or 0 for d in recent5)
                result["main_net_today"] = days[-1].get("main_net")
                result["main_pct_today"] = days[-1].get("main_pct")
            result["source"] = "em_fflow"
        _set_cached(f"ff_{pure}", result)
    except Exception as e:
        result["error"] = str(e)
    return result


# =============================================
# 4. 北向资金
# =============================================
def get_north_flow(code):
    pure = _pure_code(code)
    cached = _get_cached(f"north_{pure}", "daily")
    if cached:
        return cached

    result = {}
    try:
        import akshare as ak
        df = ak.stock_hsgt_individual_em(symbol=pure)
        if df is not None and len(df) > 0:
            recent = df.tail(5)
            days = []
            for _, row in recent.iterrows():
                day = {
                    "date": str(row.get("日期", row.get("交易日期", ""))),
                    "hold_vol": safe_float(row.get("持股数量", 0)),
                    "hold_amt": safe_float(row.get("持股市值", 0)),
                    "chg_vol": safe_float(row.get("增减", row.get("增减数量", 0))),
                    "hold_pct": safe_float(row.get("占流通股比", 0)),
                }
                days.append(day)
            result["days"] = days
            result["source"] = "akshare_hsgt"
        _set_cached(f"north_{pure}", result)
    except Exception as e:
        result["error"] = str(e)
    return result


# =============================================
# 5. 融资融券
# =============================================
def get_margin(code):
    pure = _pure_code(code)
    cached = _get_cached(f"mg_{pure}", "daily")
    if cached:
        return cached

    result = {}
    try:
        import akshare as ak
        if pure.startswith("6"):
            df = ak.stock_margin_detail_sse(date=datetime.now().strftime("%Y%m%d"))
        else:
            df = ak.stock_margin_detail_szse(date=datetime.now().strftime("%Y%m%d"))
        if df is not None and len(df) > 0:
            row = df[df["标的证券代码"] == pure]
            if len(row) > 0:
                r = row.iloc[0]
                result = {
                    "rz_buy": safe_float(r.get("融资买入额(元)", r.get("融资买入额", 0))),
                    "rz_balance": safe_float(r.get("融资余额(元)", r.get("融资余额", 0))),
                    "rq_sell": safe_float(r.get("融券卖出量", 0)),
                    "rq_balance": safe_float(r.get("融券余额(元)", r.get("融券余额", 0))),
                    "source": "akshare_margin",
                }
        _set_cached(f"mg_{pure}", result)
    except Exception as e:
        result["error"] = str(e)
    return result


# =============================================
# 6. 龙虎榜
# =============================================
def get_lhb(code):
    pure = _pure_code(code)
    cached = _get_cached(f"lhb_{pure}", "daily")
    if cached:
        return cached

    result = {}
    try:
        import akshare as ak
        dates_df = ak.stock_lhb_stock_detail_date_em(symbol=pure)
        if dates_df is not None and len(dates_df) > 0:
            recent_dates = dates_df.head(3)
            entries = []
            for _, dr in recent_dates.iterrows():
                date_str = str(dr.iloc[0]).replace("-", "")
                try:
                    detail = ak.stock_lhb_stock_detail_em(symbol=pure, date=date_str)
                    if detail is not None and len(detail) > 0:
                        for _, row in detail.head(5).iterrows():
                            entry = {
                                "date": date_str,
                                "name": str(row.get("营业部名称", "")),
                                "buy": safe_float(row.get("买入额", 0)),
                                "sell": safe_float(row.get("卖出额", 0)),
                                "net": safe_float(row.get("净额", 0)),
                            }
                            entries.append(entry)
                except Exception:
                    pass
            result["entries"] = entries
            result["source"] = "akshare_lhb"
        else:
            result["note"] = "近30天未上榜"
        _set_cached(f"lhb_{pure}", result)
    except Exception as e:
        result["error"] = str(e)
    return result


# =============================================
# 7. 机构持仓
# =============================================
def get_holder(code):
    pure = _pure_code(code)
    cached = _get_cached(f"hold_{pure}", "quarterly")
    if cached:
        return cached

    result = {}
    try:
        import akshare as ak
        df = None
        used_date = None
        # 依次尝试最近 4 个报告期，取到第一条非空数据即用（解决写死未来日期导致永远为空的问题）
        for d in _recent_report_dates(4):
            try:
                tmp = ak.stock_report_fund_hold_detail(symbol=pure, date=d)
            except Exception:
                tmp = None
            if tmp is not None and len(tmp) > 0:
                df = tmp
                used_date = d
                break
        if df is not None and len(df) > 0:
            holders = []
            for _, row in df.head(10).iterrows():
                h = {
                    "fund": str(row.get("基金名称", "")),
                    "code": str(row.get("基金代码", "")),
                    "hold_vol": safe_float(row.get("持股数量", 0)),
                    "hold_amt": safe_float(row.get("持股市值", 0)),
                    "quarter": str(row.get("季度", used_date or "")),
                }
                holders.append(h)
            result["holders"] = holders
            result["report_date"] = used_date
            result["source"] = "akshare_fund_hold"
        else:
            result["note"] = "近 4 个报告期均未取到机构持仓数据"
        _set_cached(f"hold_{pure}", result)
    except Exception as e:
        result["error"] = str(e)
    return result


# =============================================
# 综合查询
# =============================================
# ---- NeoData 补充数据源 ----
def get_neodata(code, query_extra=""):
    """通过 NeoData Financial Search 获取补充数据（ADX/VR/AH溢价/行业对比/新闻等）
    返回解析后的结构化数据，补充 stock_enhanced 不覆盖的维度。
    """
    pure = _pure_code(code)
    # Determine SH/SZ suffix
    if pure.startswith(('6', '5', '9')):
        suffix = 'SH'
    elif pure.startswith(('0', '1', '2', '3')):
        suffix = 'SZ'
    else:
        suffix = 'BJ'
    full_code = f"{pure}.{suffix}"

    cache_key = f"neodata_{pure}"
    cached = _get_cached(cache_key, "intraday")
    if cached:
        return cached

    try:
        # 统一通过 common/gateway 访问 NeoData（网关地址可配置，不可用时优雅降级）
        _common_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "common"))
        if _common_dir not in sys.path:
            sys.path.insert(0, _common_dir)
        from gateway import query_neodata as _neo_query

        # Query 1: 实时行情 + 技术面
        q1 = f"{full_code} 实时行情 技术面 {query_extra}".strip()
        r1 = _neo_query(q1, data_type="api")

        result = {"source": "neodata", "code": full_code}

        # 网关/依赖不可用时，明确标记而非崩溃
        if r1.get("_status") == "unavailable":
            result["note"] = "NeoData 网关不可用（需在 OpenClaw/JPRX 运行时，或设置 AUTH_GATEWAY_PORT）"
            _set_cached(cache_key, result)
            return result

        # Parse apiData from r1
        if r1.get("suc") and r1.get("data", {}).get("apiData", {}).get("apiRecall"):
            for recall in r1["data"]["apiData"]["apiRecall"]:
                rtype = recall.get("type", "")
                content = recall.get("content", "")
                if "实时行情" in rtype:
                    result["neodata_realtime_text"] = content
                elif "技术" in rtype or "指标" in rtype:
                    result["neodata_technical_text"] = content
                else:
                    result[f"neodata_{rtype}"] = content

        if not result.get("neodata_realtime_text") and not result.get("neodata_technical_text"):
            result["note"] = "NeoData未返回有效数据，可能服务不可用"

        _set_cached(cache_key, result)
        return result

    except Exception as e:
        return {"source": "neodata", "code": full_code, "error": str(e)}


def _is_empty(v):
    """判断某维度结果是否为空（None / 含 error / 无数据行）"""
    if v is None:
        return True
    if not isinstance(v, dict):
        return False
    if v.get("error"):
        return True
    if v.get("note") and "未取到" in str(v.get("note", "")):
        return True
    if "rows" in v and not v["rows"]:
        return True
    return False


def query_stock(code, options=None):
    if options is None:
        options = ["realtime", "technical", "fund"]

    result = {"code": _pure_code(code), "query_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    trade_date = datetime.now().strftime("%Y-%m-%d")

    if "realtime" in options:
        result["realtime"] = get_realtime(code)
    if "technical" in options:
        result["technical"] = get_kline(code)
    # 资金面/筹码/事件维度：capital 模式走直连HTTP端口（覆盖原 akshare 桩，避免整块缺失）
    if "fund" in options and "capital" not in options:
        result["fund_flow"] = get_fund_flow(code)
    if "north" in options:
        result["north_flow"] = get_north_flow(code)
    if "margin" in options and "capital" not in options:
        result["margin"] = get_margin(code)
    if "lhb" in options and "capital" not in options:
        result["lhb"] = get_lhb(code)
    if "holder" in options and "capital" not in options:
        result["holder"] = get_holder(code)
    if "neodata" in options:
        result["neodata"] = get_neodata(code)

    if "capital" in options:
        try:
            from stock_capital_data import enrich_capital_data as _enrich
            cap = _enrich(code, trade_date)
            # 用直连源补齐 / 覆盖此前空白维度
            if _is_empty(result.get("fund_flow")):
                result["fund_flow"] = cap.get("fund_flow_120d")
            if _is_empty(result.get("margin")):
                result["margin"] = cap.get("margin")
            if _is_empty(result.get("lhb")):
                result["lhb"] = cap.get("dragon_tiger")
            if _is_empty(result.get("holder")):
                result["holder"] = cap.get("holder_num")
            result["block_trade"] = cap.get("block_trade")
            result["dividend"] = cap.get("dividend")
            result["lockup"] = cap.get("lockup")
            result["research"] = cap.get("research")
            result["news"] = cap.get("news")
            result["announcements"] = cap.get("announcements")
            result["concept"] = cap.get("concept")
            result["capital_data"] = cap
        except Exception as e:
            result["capital_data"] = {"error": str(e)}

    return result


# ---- CLI ----
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    codes = []
    options = ["realtime", "technical", "fund"]

    for arg in sys.argv[1:]:
        if arg.startswith("--"):
            opt = arg[2:]
            if opt == "all":
                options = ["realtime", "technical", "fund", "north", "margin", "lhb", "holder", "neodata", "capital"]
            elif opt == "tech":
                options = ["realtime", "technical"]
            elif opt == "quick":
                options = ["realtime"]
            elif opt not in options:
                options.append(opt)
        else:
            codes.append(arg)

    if not codes:
        print("请输入股票代码")
        sys.exit(1)

    results = []
    for code in codes:
        r = query_stock(code, options)
        results.append(r)

    print(json.dumps(results, ensure_ascii=False, indent=2))
