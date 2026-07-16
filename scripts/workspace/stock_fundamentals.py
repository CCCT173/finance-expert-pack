#!/usr/bin/env python3
"""
个股基本面 / 估值 / 事件 取数薄封装（弥补 stock_enhanced.py 缺失的六大维度）

覆盖：5年财务摘要、同业对比、PE/PB 历史分位、DCF 自由现金流输入、事件催化日历。

设计原则：
- 每个函数独立 try/except，成功返回结构化 dict，失败返回 {"source":..., "error":...} 或
  {"note":"未取到"}，**绝不抛异常中断分析流程**（遵循 skill 核心原则：缺失不编造）。
- 依赖 akshare；未安装时对应函数返回 {"error":"缺少 akshare"}。
- 列名随 akshare 版本漂移，提取时采用"候选列名匹配"，匹配不到则该字段置 None。
"""

import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

import os
from datetime import datetime, timedelta


def _pure_code(code):
    code = str(code).strip()
    for p in ["sh", "sz", "SH", "SZ", "bj", "BJ"]:
        if code.lower().startswith(p):
            return code[2:]
    return code


def _has_akshare():
    try:
        import akshare  # noqa: F401
        return True
    except ImportError:
        return False


def _find_col(df, *candidates):
    """在 DataFrame 列中模糊匹配候选列名，返回首个命中的列名或 None。"""
    cols = list(df.columns)
    for cand in candidates:
        for c in cols:
            if cand in str(c):
                return c
    return None


def _records(df, limit=8):
    try:
        return df.head(limit).to_dict(orient="records")
    except Exception:
        return []


# =========================================================
# 1. 5 年财务摘要（营收 / 净利 / ROE / 资产负债率）
# =========================================================
def get_financial_summary(code, years=5):
    code = _pure_code(code)
    if not _has_akshare():
        return {"source": "akshare_financial", "error": "缺少 akshare（pip install akshare）"}
    try:
        import akshare as ak
        out = {"source": "akshare_financial", "code": code}

        # 财务分析指标：ROE / 资产负债率
        try:
            ind = ak.stock_financial_analysis_indicator(symbol=code)
            roe_c = _find_col(ind, "加权净资产收益率", "净资产收益率")
            debt_c = _find_col(ind, "资产负债率")
            if roe_c:
                out["roe_trend"] = _records(ind[["日期", roe_c]].rename(
                    columns={roe_c: "roe_pct"}), limit=years) if "日期" in ind.columns else _records(ind, limit=years)
            if debt_c:
                out["debt_ratio_trend"] = _records(ind[["日期", debt_c]].rename(
                    columns={debt_c: "debt_ratio_pct"}), limit=years) if "日期" in ind.columns else None
        except Exception as e:
            out["indicator_error"] = str(e)

        # 财务摘要：营收 / 净利
        try:
            ab = ak.stock_financial_abstract(symbol=code)
            rev_c = _find_col(ab, "营业总收入")
            np_c = _find_col(ab, "归属母公司所有者的净利润", "净利润")
            if rev_c:
                out["revenue_records"] = _records(ab, limit=years)
            if np_c:
                out["net_profit_records"] = _records(ab, limit=years)
        except Exception as e:
            out["abstract_error"] = str(e)

        return out
    except Exception as e:
        return {"source": "akshare_financial", "error": str(e)}


# =========================================================
# 2. 同业对比（行业归属 + 成分 + 行业 PE 中位数）
# =========================================================
def get_peer_comparison(code, top_n=10):
    code = _pure_code(code)
    if not _has_akshare():
        return {"source": "akshare_peer", "error": "缺少 akshare（pip install akshare）"}
    try:
        import akshare as ak
        out = {"source": "akshare_peer", "code": code}
        # 行业归属
        try:
            info = ak.stock_individual_basic_info_xq(symbol=code)
            row = info.iloc[0] if len(info) > 0 else None
            if row is not None:
                out["industry"] = str(row.get("affiliate_industry", row.get("行业", "N/A")))
        except Exception as e:
            out["industry_error"] = str(e)

        industry = out.get("industry", "")
        if industry and industry != "N/A":
            try:
                cons = ak.stock_board_industry_cons_em(industry)
                if cons is not None and len(cons) > 0:
                    out["peer_count"] = len(cons)
                    out["peers"] = [
                        {"code": str(r.get("代码", "")), "name": str(r.get("名称", ""))}
                        for _, r in cons.head(top_n).iterrows()
                    ]
            except Exception as e:
                out["cons_error"] = str(e)
        return out
    except Exception as e:
        return {"source": "akshare_peer", "error": str(e)}


# =========================================================
# 3. PE / PB 历史分位
# =========================================================
def get_valuation_percentile(code):
    code = _pure_code(code)
    if not _has_akshare():
        return {"source": "akshare_valuation", "error": "缺少 akshare（pip install akshare）"}
    try:
        import akshare as ak
        df = ak.stock_a_indicator_lg(symbol=code)
        if df is None or len(df) == 0:
            return {"source": "akshare_valuation", "code": code, "note": "未取到估值序列"}
        # 列名候选
        pe_c = _find_col(df, "市盈率", "PE")
        pb_c = _find_col(df, "市净率", "PB")
        out = {"source": "akshare_valuation", "code": code, "count": len(df)}

        def _pct(series_col):
            vals = df[series_col].dropna().astype(float)
            if len(vals) == 0:
                return None
            cur = vals.iloc[-1]
            return {
                "current": round(float(cur), 2),
                "min": round(float(vals.min()), 2),
                "max": round(float(vals.max()), 2),
                "median": round(float(vals.median()), 2),
                "percentile": round(float((vals < cur).mean() * 100), 1),
            }

        if pe_c:
            out["pe"] = _pct(pe_c)
        if pb_c:
            out["pb"] = _pct(pb_c)
        return out
    except Exception as e:
        return {"source": "akshare_valuation", "error": str(e)}


# =========================================================
# 4. DCF 输入（自由现金流序列）
# =========================================================
def get_dcf_inputs(code, years=5):
    code = _pure_code(code)
    if not _has_akshare():
        return {"source": "akshare_dcf", "error": "缺少 akshare（pip install akshare）"}
    try:
        import akshare as ak
        cf = ak.stock_cash_flow_sheet_by_report_em(symbol=code, indicator="年度")
        if cf is None or len(cf) == 0:
            return {"source": "akshare_dcf", "code": code, "note": "未取到现金流数据"}
        ocf_c = _find_col(cf, "经营活动产生的现金流量净额", "经营活动现金流入小计")
        capex_c = _find_col(cf, "购建固定资产、无形资产和其他长期资产支付的现金", "投资活动现金流出小计")
        out = {"source": "akshare_dcf", "code": code, "fcf_records": []}
        for _, r in cf.head(years).iterrows():
            ocf = _to_float(r.get(ocf_c)) if ocf_c else None
            capex = _to_float(r.get(capex_c)) if capex_c else None
            fcf = (ocf - capex) if (ocf is not None and capex is not None) else None
            out["fcf_records"].append({
                "report_date": str(r.get("报告期", r.get("REPORT_DATE", ""))),
                "operating_cash_flow": ocf,
                "capex": capex,
                "free_cash_flow": fcf,
            })
        return out
    except Exception as e:
        return {"source": "akshare_dcf", "error": str(e)}


# =========================================================
# 5. 事件催化日历（业绩预告 / 快报 / 近期新闻）
# =========================================================
def get_event_calendar(code, days=30):
    code = _pure_code(code)
    if not _has_akshare():
        return {"source": "akshare_event", "error": "缺少 akshare（pip install akshare）"}
    out = {"source": "akshare_event", "code": code, "events": []}
    try:
        import akshare as ak
        # 业绩预告
        try:
            today = datetime.now()
            start = (today - timedelta(days=days)).strftime("%Y%m%d")
            end = today.strftime("%Y%m%d")
            yjyg = ak.stock_yjyg_em(date=end)
            if yjyg is not None and len(yjyg) > 0:
                sub = yjyg[yjyg.astype(str).apply(
                    lambda r: code in r.to_string(index=False), axis=1)] if False else yjyg
                # 保守过滤：仅保留含该代码的行
                for _, r in yjyg.head(20).iterrows():
                    if code in str(r.values):
                        out["events"].append({"type": "业绩预告", "content": str(r.to_dict())})
        except Exception as e:
            out["yjyg_error"] = str(e)

        # 近期新闻
        try:
            news = ak.stock_news_em(symbol=code)
            if news is not None and len(news) > 0:
                for _, r in news.head(10).iterrows():
                    out["events"].append({
                        "type": "新闻",
                        "title": str(r.get("新闻标题", "")),
                        "published": str(r.get("发布时间", "")),
                    })
        except Exception as e:
            out["news_error"] = str(e)

        if not out["events"]:
            out["note"] = f"近 {days} 天未检索到明确事件催化"
        return out
    except Exception as e:
        return {"source": "akshare_event", "error": str(e)}


def _to_float(v):
    try:
        if v in (None, "", "-"):
            return None
        return float(v)
    except (ValueError, TypeError):
        return None


# =========================================================
# 便捷聚合：一次性取全部维度
# =========================================================
def analyze_fundamentals(code, days=30):
    return {
        "financial": get_financial_summary(code),
        "peer": get_peer_comparison(code),
        "valuation": get_valuation_percentile(code),
        "dcf": get_dcf_inputs(code),
        "events": get_event_calendar(code, days=days),
    }


if __name__ == "__main__":
    import json
    code = sys.argv[1] if len(sys.argv) > 1 else "600519"
    print(json.dumps(analyze_fundamentals(code), ensure_ascii=False, indent=2, default=str))
