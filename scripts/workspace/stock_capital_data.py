# -*- coding: utf-8 -*-
"""
stock_capital_data.py — 资金面 / 筹码 / 事件 / 研报 / 新闻 / 公告 数据维度补齐模块

移植自 a-stock-data (v3.2.2) 的直连 HTTP 端点，并与 stock-analyzer 的支撑/压力价位模型整合，
用于补齐 finance-expert-pack 在「完美世界」实盘验证中暴露的空白维度：
  资金流(120日/分钟级) / 融资融券 / 龙虎榜 / 大宗交易 / 股东户数 / 分红 / 限售解禁 /
  研报 / 个股新闻 / 全球资讯 / 巨潮公告 / 概念板块归属 / 估值(forward PE·PEG·PE消化) / 支撑压力价位

设计原则（与 finance-expert-pack 既有修复一致）：
  1. 纯 requests，不依赖 akshare / mootdx（比原 akshare 桩更稳，避免沙箱/网络差异导致的整块缺失）。
  2. 东财系接口统一走 em_get() 节流入口（串行限流 + 会话复用 + 正常 UA），避免被风控封 IP。
  3. 每个函数独立 try/except，返回结构化字典：成功含 source + 数据；失败含 error / note，**绝不抛异常崩溃**。
  4. 不强制 no_proxy（尊重系统代理），与 stock_enhanced 的 no_proxy='*' 解耦，二者可并存。

依赖：requests（已在 requirements.txt）。可选：pandas（仅 get_raw_klines 解析用，缺失时退化为纯列表）。
"""
import os
import sys
import time
import json
import random
import uuid
import urllib.request
from datetime import datetime, timedelta

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"

# ── 东财防封：全局节流 + 会话复用 ────────────────────────────────────────
EM_SESSION = None
EM_MIN_INTERVAL = float(os.environ.get("EM_MIN_INTERVAL", "1.0"))  # 两次东财请求最小间隔(秒)
_em_last_call = [0.0]


def _get_session():
    global EM_SESSION
    if EM_SESSION is None:
        import requests
        EM_SESSION = requests.Session()
        EM_SESSION.headers.update({"User-Agent": UA})
    return EM_SESSION


def em_get(url, params=None, headers=None, timeout=15, **kwargs):
    """东财统一请求入口：自动节流 + 复用 session + 默认 UA。"""
    import requests
    wait = EM_MIN_INTERVAL - (time.time() - _em_last_call[0])
    if wait > 0:
        time.sleep(wait + random.uniform(0.1, 0.5))
    try:
        return _get_session().get(url, params=params, headers=headers, timeout=timeout, **kwargs)
    finally:
        _em_last_call[0] = time.time()


def eastmoney_datacenter(report_name, columns="ALL", filter_str="", page_size=50,
                         sort_columns="", sort_types="-1"):
    """东财数据中心统一查询 — 龙虎榜/解禁/融资融券/大宗交易/股东户数/分红 共用（已内置限流）"""
    params = {
        "reportName": report_name, "columns": columns,
        "filter": filter_str, "pageNumber": "1", "pageSize": str(page_size),
        "sortColumns": sort_columns, "sortTypes": sort_types,
        "source": "WEB", "client": "WEB",
    }
    try:
        r = em_get(DATACENTER_URL, params=params, timeout=15)
        d = r.json()
        if d.get("result") and d["result"].get("data"):
            return d["result"]["data"]
    except Exception as e:
        return {"_error": str(e)}
    return []


def _secid(code):
    """6位代码 → 东财 secid"""
    pure = code[-6:] if len(code) > 6 else code
    return f"1.{pure}" if pure.startswith("6") else f"0.{pure}"


# ============================================================
# 资金面 / 筹码层
# ============================================================

def get_fund_flow_120d(code, limit=120):
    """个股资金流（日级，最近 limit 个交易日）。单位：元。
    返回 {source, rows:[{date,main_net,small_net,mid_net,large_net,super_net}], main_net_20d}"""
    pure = code[-6:] if len(code) > 6 else code
    try:
        import requests
        url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
        params = {
            "secid": _secid(pure),
            "fields1": "f1,f2,f3,f7",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
            "lmt": str(limit),
        }
        headers = {"User-Agent": UA, "Referer": "https://quote.eastmoney.com/",
                   "Origin": "https://quote.eastmoney.com"}
        r = em_get(url, params=params, headers=headers, timeout=15)
        d = r.json()
        klines = d.get("data", {}).get("klines", [])
        rows = []
        for line in klines:
            p = line.split(",")
            if len(p) >= 7:
                rows.append({
                    "date": p[0],
                    "main_net": float(p[1]) if p[1] != "-" else 0.0,
                    "small_net": float(p[2]) if p[2] != "-" else 0.0,
                    "mid_net": float(p[3]) if p[3] != "-" else 0.0,
                    "large_net": float(p[4]) if p[4] != "-" else 0.0,
                    "super_net": float(p[5]) if p[5] != "-" else 0.0,
                })
        if not rows:
            return {"source": "em_fflow_120d", "note": "未取到资金流数据", "rows": []}
        recent20 = rows[-20:]
        total20 = sum(x["main_net"] for x in recent20)
        return {"source": "em_fflow_120d", "rows": rows,
                "main_net_20d": round(total20, 2),
                "main_net_last": rows[-1]["main_net"]}
    except Exception as e:
        return {"source": "em_fflow_120d", "error": str(e)}


def get_fund_flow_minute(code):
    """个股资金流向（分钟级，当日盘中）。单位：元。"""
    pure = code[-6:] if len(code) > 6 else code
    try:
        import requests
        url = "https://push2.eastmoney.com/api/qt/stock/fflow/kline/get"
        params = {"secid": _secid(pure), "klt": "1",
                  "fields1": "f1,f2,f3,f7",
                  "fields2": "f51,f52,f53,f54,f55,f56,f57"}
        headers = {"User-Agent": UA, "Referer": "https://quote.eastmoney.com/",
                   "Origin": "https://quote.eastmoney.com"}
        r = em_get(url, params=params, headers=headers, timeout=10)
        d = r.json()
        rows = []
        for line in d.get("data", {}).get("klines", []):
            p = line.split(",")
            if len(p) >= 6:
                rows.append({"time": p[0],
                             "main_net": float(p[1]), "small_net": float(p[2]),
                             "mid_net": float(p[3]), "large_net": float(p[4]),
                             "super_net": float(p[5])})
        if not rows:
            return {"source": "em_fflow_min", "note": "未取到分钟级资金流（可能非盘中）", "rows": []}
        return {"source": "em_fflow_min", "rows": rows,
                "main_net_last": rows[-1]["main_net"]}
    except Exception as e:
        return {"source": "em_fflow_min", "error": str(e)}


def get_margin_trading(code, page_size=30):
    """融资融券明细（日级）。返回 {source, rows:[{date,rzye,rzmre,rqye,rqmcl,rzrqye}]}"""
    pure = code[-6:] if len(code) > 6 else code
    try:
        data = eastmoney_datacenter(
            "RPTA_WEB_RZRQ_GGMX", filter_str=f'(SCODE="{pure}")',
            page_size=page_size, sort_columns="DATE", sort_types="-1")
        if isinstance(data, dict) and data.get("_error"):
            return {"source": "em_margin", "error": data["_error"]}
        rows = []
        for row in data:
            rows.append({
                "date": str(row.get("DATE", ""))[:10],
                "rzye": row.get("RZYE", 0),        # 融资余额(元)
                "rzmre": row.get("RZMRE", 0),      # 融资买入额
                "rzche": row.get("RZCHE", 0),      # 融资偿还额
                "rqye": row.get("RQYE", 0),        # 融券余额(元)
                "rqmcl": row.get("RQMCL", 0),      # 融券卖出量
                "rzrqye": row.get("RZRQYE", 0),    # 两融余额合计
            })
        if not rows:
            return {"source": "em_margin", "note": "未取到融资融券数据", "rows": []}
        return {"source": "em_margin", "rows": rows, "latest": rows[0]}
    except Exception as e:
        return {"source": "em_margin", "error": str(e)}


def get_dragon_tiger(code, trade_date=None, look_back=30):
    """龙虎榜数据聚合。返回 {source, records, seats:{buy,sell}, institution}"""
    pure = code[-6:] if len(code) > 6 else code
    if trade_date is None:
        trade_date = datetime.now().strftime("%Y-%m-%d")
    try:
        start = datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=look_back)
        start_str = start.strftime("%Y-%m-%d")
        records = []
        data = eastmoney_datacenter(
            "RPT_DAILYBILLBOARD_DETAILSNEW",
            filter_str=f"(TRADE_DATE>='{start_str}')(TRADE_DATE<='{trade_date}')(SECURITY_CODE=\"{pure}\")",
            page_size=50, sort_columns="TRADE_DATE", sort_types="-1")
        if isinstance(data, dict) and data.get("_error"):
            return {"source": "em_lhb", "error": data["_error"]}
        for row in data:
            records.append({
                "date": str(row.get("TRADE_DATE", ""))[:10],
                "reason": row.get("EXPLANATION", ""),
                "net_buy_wan": round((row.get("BILLBOARD_NET_AMT") or 0) / 1e4, 1),
                "turnover": round(float(row.get("TURNOVERRATE") or 0), 2),
            })
        seats = {"buy": [], "sell": []}
        institution = {"buy_amt": 0, "sell_amt": 0, "net_amt": 0}
        if records:
            latest = records[0]["date"]
            buy_data = eastmoney_datacenter(
                "RPT_BILLBOARD_DAILYDETAILSBUY",
                filter_str=f"(TRADE_DATE='{latest}')(SECURITY_CODE=\"{pure}\")",
                page_size=10, sort_columns="BUY", sort_types="-1")
            if not isinstance(buy_data, dict):
                for row in buy_data[:5]:
                    seats["buy"].append({
                        "name": row.get("OPERATEDEPT_NAME", ""),
                        "buy_wan": round((row.get("BUY") or 0) / 1e4, 1),
                        "sell_wan": round((row.get("SELL") or 0) / 1e4, 1),
                        "net_wan": round((row.get("NET") or 0) / 1e4, 1),
                    })
            sell_data = eastmoney_datacenter(
                "RPT_BILLBOARD_DAILYDETAILSSELL",
                filter_str=f"(TRADE_DATE='{latest}')(SECURITY_CODE=\"{pure}\")",
                page_size=10, sort_columns="SELL", sort_types="-1")
            if not isinstance(sell_data, dict):
                for row in sell_data[:5]:
                    seats["sell"].append({
                        "name": row.get("OPERATEDEPT_NAME", ""),
                        "buy_wan": round((row.get("BUY") or 0) / 1e4, 1),
                        "sell_wan": round((row.get("SELL") or 0) / 1e4, 1),
                        "net_wan": round((row.get("NET") or 0) / 1e4, 1),
                    })
            for detail_data, side in [(buy_data, "buy"), (sell_data, "sell")]:
                if isinstance(detail_data, dict):
                    continue
                for row in detail_data:
                    if str(row.get("OPERATEDEPT_CODE", "")) == "0":
                        amt = (row.get("BUY") or 0) if side == "buy" else (row.get("SELL") or 0)
                        institution["buy_amt" if side == "buy" else "sell_amt"] += amt
            institution["buy_amt"] = round(institution["buy_amt"] / 1e4, 1)
            institution["sell_amt"] = round(institution["sell_amt"] / 1e4, 1)
            institution["net_amt"] = round(institution["buy_amt"] - institution["sell_amt"], 1)
        if not records:
            return {"source": "em_lhb", "note": "近%d日无龙虎榜记录" % look_back,
                    "records": [], "seats": seats, "institution": institution}
        return {"source": "em_lhb", "records": records, "seats": seats, "institution": institution}
    except Exception as e:
        return {"source": "em_lhb", "error": str(e)}


def get_block_trade(code, page_size=20):
    """大宗交易记录。返回 {source, rows:[{date,price,close,premium_pct,vol,amount,buyer,seller}]}"""
    pure = code[-6:] if len(code) > 6 else code
    try:
        data = eastmoney_datacenter(
            "RPT_DATA_BLOCKTRADE",
            filter_str=f'(SECURITY_CODE="{pure}")',
            page_size=page_size, sort_columns="TRADE_DATE", sort_types="-1")
        if isinstance(data, dict) and data.get("_error"):
            return {"source": "em_block", "error": data["_error"]}
        rows = []
        for row in data:
            close = row.get("CLOSE_PRICE") or 0
            deal = row.get("DEAL_PRICE") or 0
            prem = ((deal / close - 1) * 100) if close else 0
            rows.append({
                "date": str(row.get("TRADE_DATE", ""))[:10],
                "price": deal, "close": close,
                "premium_pct": round(prem, 2),
                "vol": row.get("DEAL_VOLUME", 0),
                "amount": row.get("DEAL_AMT", 0),
                "buyer": row.get("BUYER_NAME", ""),
                "seller": row.get("SELLER_NAME", ""),
            })
        if not rows:
            return {"source": "em_block", "note": "未取到大宗交易记录", "rows": []}
        return {"source": "em_block", "rows": rows}
    except Exception as e:
        return {"source": "em_block", "error": str(e)}


def get_holder_num_change(code, page_size=10):
    """股东户数变化（季度级）。返回 {source, rows:[{date,holder_num,change_ratio,avg_shares}]}"""
    pure = code[-6:] if len(code) > 6 else code
    try:
        data = eastmoney_datacenter(
            "RPT_HOLDERNUMLATEST",
            filter_str=f'(SECURITY_CODE="{pure}")',
            page_size=page_size, sort_columns="END_DATE", sort_types="-1")
        if isinstance(data, dict) and data.get("_error"):
            return {"source": "em_holder", "error": data["_error"]}
        rows = []
        for row in data:
            rows.append({
                "date": str(row.get("END_DATE", ""))[:10],
                "holder_num": row.get("HOLDER_NUM", 0),
                "change_ratio": row.get("HOLDER_NUM_RATIO", 0),  # 环比%
                "avg_shares": row.get("AVG_FREE_SHARES", 0),     # 户均持股
            })
        if not rows:
            return {"source": "em_holder", "note": "未取到股东户数数据", "rows": []}
        return {"source": "em_holder", "rows": rows, "latest": rows[0]}
    except Exception as e:
        return {"source": "em_holder", "error": str(e)}


def get_dividend_history(code, page_size=20):
    """分红送转历史。返回 {source, rows:[{date,bonus_rmb,transfer_ratio,bonus_ratio,plan}]}"""
    pure = code[-6:] if len(code) > 6 else code
    try:
        data = eastmoney_datacenter(
            "RPT_SHAREBONUS_DET",
            filter_str=f'(SECURITY_CODE="{pure}")',
            page_size=page_size, sort_columns="EX_DIVIDEND_DATE", sort_types="-1")
        if isinstance(data, dict) and data.get("_error"):
            return {"source": "em_div", "error": data["_error"]}
        rows = []
        for row in data:
            rows.append({
                "date": str(row.get("EX_DIVIDEND_DATE", ""))[:10],
                "bonus_rmb": row.get("PRETAX_BONUS_RMB", 0),
                "transfer_ratio": row.get("TRANSFER_RATIO", 0),
                "bonus_ratio": row.get("BONUS_RATIO", 0),
                "plan": row.get("ASSIGN_PROGRESS", ""),
            })
        if not rows:
            return {"source": "em_div", "note": "未取到分红记录", "rows": []}
        return {"source": "em_div", "rows": rows}
    except Exception as e:
        return {"source": "em_div", "error": str(e)}


def get_lockup_expiry(code, trade_date=None, forward_days=90):
    """限售解禁日历。返回 {source, history, upcoming}"""
    pure = code[-6:] if len(code) > 6 else code
    if trade_date is None:
        trade_date = datetime.now().strftime("%Y-%m-%d")
    try:
        history_data = eastmoney_datacenter(
            "RPT_LIFT_STAGE", filter_str=f'(SECURITY_CODE="{pure}")',
            page_size=15, sort_columns="FREE_DATE", sort_types="-1")
        if isinstance(history_data, dict) and history_data.get("_error"):
            return {"source": "em_lockup", "error": history_data["_error"]}
        history = [{"date": str(r.get("FREE_DATE", ""))[:10],
                    "type": r.get("LIMITED_STOCK_TYPE", ""),
                    "shares": r.get("FREE_SHARES_NUM", 0),
                    "ratio": r.get("FREE_RATIO", 0)} for r in history_data]
        end = datetime.strptime(trade_date, "%Y-%m-%d") + timedelta(days=forward_days)
        end_str = end.strftime("%Y-%m-%d")
        upcoming_data = eastmoney_datacenter(
            "RPT_LIFT_STAGE",
            filter_str=f'(SECURITY_CODE="{pure}")(FREE_DATE>=\'{trade_date}\')(FREE_DATE<=\'{end_str}\')',
            page_size=20, sort_columns="FREE_DATE", sort_types="1")
        upcoming = [{"date": str(r.get("FREE_DATE", ""))[:10],
                     "type": r.get("LIMITED_STOCK_TYPE", ""),
                     "shares": r.get("FREE_SHARES_NUM", 0),
                     "ratio": r.get("FREE_RATIO", 0)} for r in upcoming_data
                    if not isinstance(upcoming_data, dict)]
        return {"source": "em_lockup", "history": history, "upcoming": upcoming}
    except Exception as e:
        return {"source": "em_lockup", "error": str(e)}


# ============================================================
# 研报 / 新闻 / 公告 / 概念
# ============================================================

def get_research_reports(code, max_pages=3):
    """东财研报列表 + 评级。返回 {source, rows:[{date,org,title,rating,eps_cur,eps_next,info_code}]}"""
    pure = code[-6:] if len(code) > 6 else code
    try:
        import requests
        REPORT_API = "https://reportapi.eastmoney.com/report/list"
        PDF_TPL = "https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf"
        all_records = []
        for page in range(1, max_pages + 1):
            params = {
                "industryCode": "*", "pageSize": "100", "industry": "*",
                "rating": "*", "ratingChange": "*",
                "beginTime": "2000-01-01", "endTime": "2030-01-01",
                "pageNo": str(page), "fields": "", "qType": "0",
                "orgCode": "", "code": pure, "rcode": "",
                "p": str(page), "pageNum": str(page), "pageNumber": str(page),
            }
            r = em_get(REPORT_API, params=params,
                       headers={"Referer": "https://data.eastmoney.com/"}, timeout=30)
            d = r.json()
            rows = d.get("data") or []
            if not rows:
                break
            for rec in rows:
                all_records.append({
                    "date": str(rec.get("publishDate", ""))[:10],
                    "org": rec.get("orgSName", ""),
                    "title": rec.get("title", ""),
                    "rating": rec.get("emRatingName", ""),
                    "eps_cur": rec.get("predictThisYearEps"),
                    "eps_next": rec.get("predictNextYearEps"),
                    "info_code": rec.get("infoCode", ""),
                    "pdf": PDF_TPL.format(info_code=rec.get("infoCode", "")) if rec.get("infoCode") else "",
                })
            if page >= (d.get("TotalPage", 1) or 1):
                break
        if not all_records:
            return {"source": "em_report", "note": "未取到研报", "rows": []}
        return {"source": "em_report", "rows": all_records[:max_pages * 100],
                "count": len(all_records)}
    except Exception as e:
        return {"source": "em_report", "error": str(e)}


def get_stock_news(code, page_size=20):
    """东财个股新闻（JSONP）。返回 {source, rows:[{title,content,time,source,url}]}"""
    pure = code[-6:] if len(code) > 6 else code
    try:
        import requests
        cb = "jQuery_news"
        url = "https://search-api-web.eastmoney.com/search/jsonp"
        inner = json.dumps({
            "uid": "", "keyword": pure,
            "type": ["cmsArticleWebOld"], "client": "web", "clientType": "web",
            "clientVersion": "curr",
            "param": {"cmsArticleWebOld": {"searchScope": "default", "sort": "default",
                      "pageIndex": 1, "pageSize": page_size, "preTag": "", "postTag": ""}},
        }, separators=(',', ':'))
        params = {"cb": cb, "param": inner}
        headers = {"User-Agent": UA, "Referer": "https://so.eastmoney.com/"}
        r = em_get(url, params=params, headers=headers, timeout=15)
        text = r.text
        json_str = text[text.index("(") + 1: text.rindex(")")]
        d = json.loads(json_str)
        articles = d.get("result", {}).get("cmsArticleWebOld", []) or []
        rows = []
        for a in articles:
            rows.append({
                "title": _strip_tags(a.get("title", "")),
                "content": _strip_tags(a.get("content", ""))[:200],
                "time": a.get("date", ""),
                "source": a.get("mediaName", ""),
                "url": a.get("url", ""),
            })
        if not rows:
            return {"source": "em_news", "note": "未取到个股新闻", "rows": []}
        return {"source": "em_news", "rows": rows}
    except Exception as e:
        return {"source": "em_news", "error": str(e)}


def get_global_news(page_size=30):
    """东方财富全球财经资讯（7x24）。返回 {source, rows:[{title,summary,time}]}"""
    try:
        import requests
        url = "https://np-weblist.eastmoney.com/comm/web/getFastNewsList"
        params = {"client": "web", "biz": "web_724", "fastColumn": "102",
                  "sortEnd": "", "pageSize": str(page_size),
                  "req_trace": str(uuid.uuid4())}
        headers = {"User-Agent": UA, "Referer": "https://kuaixun.eastmoney.com/"}
        r = em_get(url, params=params, headers=headers, timeout=10)
        d = r.json()
        rows = []
        for item in d.get("data", {}).get("fastNewsList", []):
            rows.append({"title": item.get("title", ""),
                         "summary": item.get("summary", "")[:200],
                         "time": item.get("showTime", "")})
        if not rows:
            return {"source": "em_global", "note": "未取到全球资讯", "rows": []}
        return {"source": "em_global", "rows": rows}
    except Exception as e:
        return {"source": "em_global", "error": str(e)}


def get_announcements(code, page_size=30):
    """巨潮公告全文检索。返回 {source, rows:[{title,type,date,url}]}"""
    pure = code[-6:] if len(code) > 6 else code
    try:
        import requests
        url = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
        if pure.startswith("6"):
            org_id = f"gssh0{pure}"
        elif pure.startswith(("8", "4")):
            org_id = f"gsbj0{pure}"
        else:
            org_id = f"gssz0{pure}"
        payload = {
            "stock": f"{pure},{org_id}", "tabName": "fulltext",
            "pageSize": str(page_size), "pageNum": "1", "column": "",
            "category": "", "plate": "", "seDate": "", "searchkey": "",
            "secid": "", "sortName": "", "sortType": "", "isHLtitle": "true",
        }
        headers = {"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded",
                   "Referer": "https://www.cninfo.com.cn/new/disclosure",
                   "Origin": "https://www.cninfo.com.cn"}
        r = requests.post(url, data=payload, headers=headers, timeout=15)
        d = r.json()
        rows = []
        for item in d.get("announcements", []) or []:
            ts = item.get("announcementTime")
            date_str = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d") if isinstance(ts, (int, float)) else str(ts)[:10]
            rows.append({
                "title": item.get("announcementTitle", ""),
                "type": item.get("announcementTypeName", ""),
                "date": date_str,
                "url": f"https://www.cninfo.com.cn/new/disclosure/detail?annoId={item.get('announcementId', '')}",
            })
        if not rows:
            return {"source": "cninfo", "note": "未取到公告", "rows": []}
        return {"source": "cninfo", "rows": rows}
    except Exception as e:
        return {"source": "cninfo", "error": str(e)}


def get_concept_blocks(code):
    """百度股市通概念板块归属。返回 {source, industry, concept, region, concept_tags}"""
    pure = code[-6:] if len(code) > 6 else code
    try:
        import requests
        url = (f"https://finance.pae.baidu.com/api/getrelatedblock"
               f"?code={pure}&market=ab&typeCode=all&finClientType=pc")
        headers = {"Host": "finance.pae.baidu.com",
                   "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/117.0.0.0",
                   "Accept": "application/vnd.finance-web.v1+json",
                   "Origin": "https://gushitong.baidu.com",
                   "Referer": "https://gushitong.baidu.com/"}
        r = requests.get(url, headers=headers, timeout=10)
        d = r.json()
        if str(d.get("ResultCode", -1)) != "0":
            return {"source": "baidu_block", "note": "未取到概念板块", "concept_tags": []}
        result = {"industry": [], "concept": [], "region": [], "concept_tags": []}
        for block in d.get("Result", []):
            btype = block.get("type", "")
            for item in block.get("list", []):
                entry = {"name": item.get("name", ""),
                         "change_pct": item.get("increase", ""),
                         "desc": item.get("desc", "")}
                if "行业" in btype:
                    result["industry"].append(entry)
                elif "概念" in btype:
                    result["concept"].append(entry)
                    result["concept_tags"].append(entry["name"])
                elif "地域" in btype:
                    result["region"].append(entry)
        return {"source": "baidu_block", **result}
    except Exception as e:
        return {"source": "baidu_block", "error": str(e)}


# ============================================================
# K线原始序列（供支撑/压力计算；与 stock_enhanced.get_kline 同源但返回完整 OHLC）
# ============================================================

def get_raw_klines(code, days=120):
    """原始日K线 OHLC 列表（东财HTTP）。返回 {source, rows:[{date,open,close,high,low,volume}]}"""
    pure = code[-6:] if len(code) > 6 else code
    try:
        import requests
        url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            "secid": _secid(pure),
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": "101", "fqt": "1",
            "beg": (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d"),
            "end": "20500101",
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        }
        headers = {"User-Agent": UA, "Referer": "https://quote.eastmoney.com/"}
        r = em_get(url, params=params, headers=headers, timeout=15)
        d = r.json()
        klines = d.get("data", {}).get("klines", [])
        rows = []
        for line in klines:
            p = line.split(",")
            if len(p) >= 6:
                rows.append({
                    "date": p[0],
                    "open": float(p[1]), "close": float(p[2]),
                    "high": float(p[3]), "low": float(p[4]),
                    "volume": float(p[5]),
                })
        if not rows:
            return {"source": "em_kline", "note": "未取到K线", "rows": []}
        return {"source": "em_kline", "rows": rows[-days:]}
    except Exception as e:
        return {"source": "em_kline", "error": str(e)}


# ============================================================
# 估值公式（移植自 a-stock-data）
# ============================================================

def forward_pe(price, eps_forecast):
    """前向PE = 当前股价 / 未来年度一致预期EPS"""
    if not eps_forecast or eps_forecast <= 0:
        return None
    return round(price / eps_forecast, 2)


def pe_digestion(current_pe, cagr, target_pe=30):
    """当前PE消化到目标PE(默认30x)需要多少年。cagr = 下一年EPS/当年EPS - 1"""
    if current_pe <= target_pe:
        return 0.0
    if not cagr or cagr <= 0:
        return None
    import math
    return round(math.log(current_pe / target_pe) / math.log(1 + cagr), 1)


def calc_peg(pe, cagr):
    """PEG = 前向PE / (CAGR*100)。<1便宜, 1-1.5合理, >1.5贵"""
    if not cagr or cagr <= 0:
        return None
    return round(pe / (cagr * 100), 2)


# ============================================================
# 支撑/压力价位（整合 stock-analyzer 模型，纯计算不猜测）
# ============================================================

def support_resistance(klines, price):
    """由 K线 OHLC + 现价计算弱/强支撑与弱/强压力。
    klines: [{date,open,close,high,low,volume}]（按时间升序）
    price: 当前价
    返回 {weak_support, strong_support, weak_resist, strong_resist, ma20, ma60, basis}"""
    if not klines or price is None:
        return {"note": "K线或现价缺失，无法计算支撑压力"}
    try:
        closes = [k["close"] for k in klines if k.get("close") is not None]
        highs = [k["high"] for k in klines if k.get("high") is not None]
        lows = [k["low"] for k in klines if k.get("low") is not None]
        n = len(closes)
        ma20 = sum(closes[-20:]) / min(20, n) if n >= 1 else price
        ma60 = sum(closes[-60:]) / min(60, n) if n >= 1 else price

        r20_h, r20_l = (max(highs[-20:]), min(lows[-20:])) if len(highs) >= 20 else (max(highs), min(lows))
        r60_h, r60_l = (max(highs[-60:]), min(lows[-60:])) if len(highs) >= 60 else (max(highs), min(lows))

        # 支撑取「近期低点与均线」中更靠近现价（下方）者；压力取「近期高点与均线」中更靠近现价（上方）者
        weak_support = min(r20_l, ma20) if ma20 < price else r20_l
        strong_support = min(r60_l, ma60) if ma60 < price else r60_l
        weak_resist = max(r20_h, ma20) if ma20 > price else r20_h
        strong_resist = max(r60_h, ma60) if ma60 > price else r60_h
        return {
            "weak_support": round(weak_support, 2),
            "strong_support": round(strong_support, 2),
            "weak_resist": round(weak_resist, 2),
            "strong_resist": round(strong_resist, 2),
            "ma20": round(ma20, 2), "ma60": round(ma60, 2),
            "basis": "近期20/60日 swing + MA20/MA60",
        }
    except Exception as e:
        return {"error": str(e)}


def get_price_targets(code, price, klines=None, research=None):
    """整合支撑压力 + 分析师评级，给出买卖价位参考。
    - 支撑/压力来自 stock_capital_data.support_resistance（计算）
    - 分析师目标价：优先用研报一致预期EPS推算（price × (1 + 预期增速) 不直接给，故仅列评级与EPS预期）
    返回 {price, support_resistance, analyst:{ratings:[...], latest_rating, eps_forecast}}"""
    out = {"price": price}
    if klines:
        out["support_resistance"] = support_resistance(klines, price)
    else:
        out["support_resistance"] = {"note": "未提供K线，跳过支撑压力计算"}
    if research and isinstance(research, dict):
        rows = research.get("rows", [])
        ratings = []
        for r in rows[:10]:
            if r.get("rating"):
                ratings.append({"date": r.get("date"), "org": r.get("org"),
                                "rating": r.get("rating"),
                                "eps_cur": r.get("eps_cur"), "eps_next": r.get("eps_next")})
        if ratings:
            out["analyst"] = {"ratings": ratings,
                              "latest_rating": ratings[0]["rating"],
                              "note": "分析师目标价请以研报原文为准；本模块仅给评级与EPS预期，不臆测目标价"}
    return out


# ============================================================
# 聚合入口
# ============================================================

def enrich_capital_data(code, trade_date=None):
    """一次性补齐资金面/筹码/事件/研报/新闻/公告/概念维度。
    返回结构化字典，每个子项独立容错。"""
    pure = code[-6:] if len(code) > 6 else code
    if trade_date is None:
        trade_date = datetime.now().strftime("%Y-%m-%d")
    return {
        "code": pure,
        "fund_flow_120d": get_fund_flow_120d(pure),
        "margin": get_margin_trading(pure),
        "dragon_tiger": get_dragon_tiger(pure, trade_date),
        "block_trade": get_block_trade(pure),
        "holder_num": get_holder_num_change(pure),
        "dividend": get_dividend_history(pure),
        "lockup": get_lockup_expiry(pure, trade_date),
        "research": get_research_reports(pure),
        "news": get_stock_news(pure),
        "announcements": get_announcements(pure),
        "concept": get_concept_blocks(pure),
    }


def _strip_tags(s):
    import re
    return re.sub(r"<[^>]+>", "", s or "")


if __name__ == "__main__":
    # 自检：无网络/无依赖环境下应优雅返回 error 字典，不崩溃
    import pprint
    sample = enrich_capital_data("002624")
    pprint.pprint({k: ("<err>" if isinstance(v, dict) and v.get("error") else
                       (v.get("note") if isinstance(v, dict) else v))
                   for k, v in sample.items()})
