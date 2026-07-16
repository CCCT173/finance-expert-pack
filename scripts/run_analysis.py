#!/usr/bin/env python3
"""
个股深度分析编排入口（run_analysis.py）

串联四层能力并输出统一 JSON，供 LLM 直接消费，减少人工路由误差：
  - stock_enhanced.query_stock         ：实时行情 / 技术面 / 资金流 / 北向 / 融资 / 龙虎榜 / 机构持仓 / neodata
  - stock_fundamentals.analyze_fundamentals ：5年财务 / 同业对比 / 估值分位 / DCF输入 / 事件日历
  - stock_capital_data.enrich_capital_data  ：资金流120日 / 融资融券 / 龙虎榜 / 大宗 / 股东户数 / 分红 /
                                              解禁 / 研报 / 新闻 / 公告 / 概念板块（直连东财HTTP，比 akshare 桩更稳）
  - 估值与买卖价位（support_resistance + get_price_targets）：支撑/压力 + 分析师评级（整合 stock-analyzer 模型）

用法：
  python run_analysis.py 600519
  python run_analysis.py 600519 --all          # 额外触发 neodata 补充源
  python run_analysis.py 600519 000001 300750  # 多股

输出为 JSON（单股为对象，多股为数组），各维度缺失时以 error/note 字段标记，绝不整体崩溃。
"""
import sys
import os
import json

_HERE = os.path.dirname(os.path.abspath(__file__))
_WS = os.path.join(_HERE, "workspace")
for _p in (_WS, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from stock_enhanced import query_stock                # noqa: E402
from stock_fundamentals import analyze_fundamentals   # noqa: E402


def _safe_price(result):
    """从实时行情或基本面中提取现价"""
    rt = result.get("realtime") or {}
    if isinstance(rt, dict):
        p = rt.get("price") or rt.get("current_price")
        if p:
            return float(p)
    fu = result.get("fundamentals") or {}
    if isinstance(fu, dict):
        pe = fu.get("valuation_percentile") or {}
        if isinstance(pe, dict) and pe.get("price"):
            return float(pe["price"])
    return None


def build_pricing(result):
    """估值 + 支撑压力 + 买卖价位参考（整合 stock-analyzer 模型，纯计算不臆测）"""
    code = result.get("code")
    price = _safe_price(result)
    if not code or price is None:
        return {"note": "缺少现价，跳过价位计算"}
    try:
        from stock_capital_data import get_raw_klines, get_price_targets
        kl = get_raw_klines(code, days=120)
        klines = kl.get("rows") if isinstance(kl, dict) else None
        research = (result.get("capital_data") or {}).get("research")
        return get_price_targets(code, price, klines=klines, research=research)
    except Exception as e:
        return {"error": str(e)}


def run(code, options):
    result = query_stock(code, options)
    # 基本面 / 估值 / 事件（各自独立容错）
    try:
        result["fundamentals"] = analyze_fundamentals(code)
    except Exception as e:
        result["fundamentals"] = {"error": str(e)}
    # 估值与买卖价位（支撑压力 + 分析师评级）
    try:
        result["pricing"] = build_pricing(result)
    except Exception as e:
        result["pricing"] = {"error": str(e)}
    return result


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return
    codes = [a for a in args if not a.startswith("--")]
    all_flag = "--all" in args
    # capital 维度默认开启（补齐此前空白）；--all 再叠加 neodata
    options = (["realtime", "technical", "fund", "north", "margin", "lhb", "holder",
                "capital", "neodata"]
               if all_flag else
               ["realtime", "technical", "fund", "north", "margin", "lhb", "holder", "capital"])

    out = [run(c, options) for c in codes]
    payload = out if len(out) > 1 else out[0]
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
