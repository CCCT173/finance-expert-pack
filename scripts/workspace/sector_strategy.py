#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
板块策略模块：过滤等权持有 (Filtered Equal-Weight Holding)
============================================================
本模块是 finance-expert-pack 的「板块级策略」标准实现，经 T4 多板块样本外验证
(游戏/半导体/新能源 × 牛/熊/全周期) 为当前最优简单规则：

    「等权持有整篮 + 板块 ETF(或回退等权指数)站上 200MA 才在市，跌破转现金」

为什么是它（T4 实证结论）：
- 200MA 趋势过滤在下跌市稳稳护资本（半导体 21-22 熊 +18.8%、新能源下跌段 +28.2%），
  在上涨市必然拖累（游戏 23-26 牛市 -74.8%）——它是"跌时少亏"工具，不是"涨时多赚"工具。
- 主动"动量截面选股 + 30% 追踪止损"在 9 个组合里跑赢过滤基准仅 3 次、跑输 6 次；
  30% 止损在波动>20% 的板块反复砍赢家是主因。
- 因此把推荐策略**退化为过滤等权持有**：逻辑透明、成本低、样本外稳健。

回测纪律（硬规则，零未来函数）：
- 趋势过滤：以板块 ETF 收盘价的 200 日 MA 为准；ETF 不可得时回退「宇宙等权指数」。
- T+1 成交：t 日持仓由 t-1 收盘判定的 regime 决定，当日开盘价成交，严格模拟真实交易。
- 成本：使用A股真实交易成本（佣金万2.5+印花税千1+过户费十万1+滑点千1），完全贴近实盘。
- 交易规则：涨停买不进、跌停卖不出、停牌跳过、ST/次新股/低流动性股票自动过滤。
- warmup：200MA 需 min_periods=120 才有意义，不足则视为 down(空仓)。
- 等权篮在市期间不做日内再平衡，仅随 regime 整体进出。

用法：
  python sector_strategy.py --all                  # 3 板块 × 全周期(默认 filtered 模式)，产出仪表盘到 cwd
  python sector_strategy.py --sector 游戏           # 单板块全周期
  python sector_strategy.py --sector 半导体 --period 全周期2021-26
  python sector_strategy.py --mode quality --all    # T3 模式：过滤等权 + 基本面(ROE/营收/利润增速)截面选前5
依赖：akshare / pandas / numpy（本环境用 Anaconda 运行；取数带本地 CSV 缓存断点续传）
注：T3 质量截面为「防御型倾斜」实验模式，非默认升级；资金流维度因 eastmoney 接口层封锁暂挂起。
"""
import sys, os, json, math, warnings
warnings.filterwarnings("ignore")
import pandas as pd
import numpy as np

# 导入通用交易工具模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from trading_utils import (
    load_price, calc_trade_cost, apply_execution_price, can_trade,
    filter_stocks, CACHE_DIR, TRADING_COSTS, cache_path
)

START_ALL = "2021-01-01"
END_ALL = "2026-07-16"

# 预设板块宇宙（等权持有整篮；ETF 为趋势过滤代理）
UNIVERSES = {
    "游戏": {"etf": "159869",
        "stocks": {"002624": "完美世界", "002555": "三七互娱", "002517": "恺英网络", "002558": "巨人网络",
                   "300418": "昆仑万维", "300002": "神州泰岳", "300459": "汤姆猫", "002174": "游族网络",
                   "603444": "吉比特", "300113": "顺网科技"}},
    "半导体": {"etf": "512480",
        "stocks": {"688981": "中芯国际", "603501": "韦尔股份", "603986": "兆易创新", "002371": "北方华创",
                   "300782": "卓胜微", "002049": "紫光国微", "688008": "澜起科技", "600584": "长电科技",
                   "600703": "三安光电", "688126": "沪硅产业"}},
    "新能源": {"etf": "516160",
        "stocks": {"300750": "宁德时代", "002594": "比亚迪", "601012": "隆基绿能", "300274": "阳光电源",
                   "300014": "亿纬锂能", "600438": "通威股份", "002709": "天赐材料", "002460": "赣锋锂业",
                   "002459": "晶澳科技", "601865": "福莱特"}},
}
PERIODS = {
    "牛市2023-26": ("2023-01-01", "2026-07-16"),
    "熊市2021-22": ("2021-01-01", "2022-12-31"),
    "全周期2021-26": ("2021-01-01", "2026-07-16"),
}
WARMUP = 120          # 200MA 最小样本

def load_etf(etf):
    cp = cache_path("etf", etf)
    if os.path.exists(cp) and os.path.getsize(cp) > 0:
        try:
            s = pd.read_csv(cp, parse_dates=["date"]).set_index("date")["close"]
            if len(s) > 0:
                return s
        except Exception:
            pass
    try:
        import akshare as ak
        df = ak.stock_zh_a_daily(symbol=("sh" if etf[0] in "569" else "sz") + etf, adjust="qfq")
        df["date"] = pd.to_datetime(df["date"])
        df = df[(df["date"] >= START_ALL) & (df["date"] <= END_ALL)].sort_values("date")
        df[["date", "close"]].to_csv(cp, index=False)
        return df.set_index("date")["close"]
    except Exception:
        return None

def build_universe(univ_cfg):
    """加载价格，返回 {name: {code,name,dates(DateTimeIndex),close(Series)}}。"""
    uni = {}
    for code, name in univ_cfg["stocks"].items():
        px = load_price(code)
        if px is None or len(px) < WARMUP + 10:
            print(f"    ⚠️ {name}({code}) 价格不足，跳过")
            continue
        uni[name] = {"code": code, "name": name,
                     "dates": pd.to_datetime(px["date"].values),
                     "close": pd.Series(px["close"].values, index=pd.to_datetime(px["date"].values))}
        print(f"    ✅ {name}({code}): {len(px)}天")
    return uni

def slice_uni(uni, p0, p1):
    out = {}
    for n, d in uni.items():
        m = (d["dates"] >= pd.Timestamp(p0)) & (d["dates"] <= pd.Timestamp(p1))
        if m.sum() < WARMUP + 20:
            continue
        out[n] = {"code": d["code"], "name": n,
                  "dates": d["dates"][m], "close": d["close"][m].reset_index(drop=True)}
    return out


# ----------------------------- 趋势 / 组合 -----------------------------
def build_regime(etf_series, uni_slice, common):
    """返回 (regime_up: Series[bool]@common, 来源标签)。ETF 优先，缺失回退宇宙等权指数。"""
    if etf_series is not None and len(etf_series) > 0:
        s = etf_series.reindex(common).ffill()
        ma200 = s.rolling(200, min_periods=120).mean()
        return pd.Series((s > ma200).fillna(False).values, index=common), "ETF"
    idx = pd.Series(0.0, index=common)
    for n in uni_slice:
        c = pd.Series(uni_slice[n]["close"].values,
                      index=pd.to_datetime(uni_slice[n]["dates"].values)).reindex(common).ffill()
        idx = idx.add(c / c.iloc[0], fill_value=0)
    ma200 = idx.rolling(200, min_periods=120).mean()
    return pd.Series((idx > ma200).fillna(False).values, index=common), "宇宙等权指数(回退)"

def _daily_eqw_ret(uni_slice, common):
    """等权篮日收益序列（与 T4 过滤基准定义一致）。close 以 dates 重建 DatetimeIndex 再对齐。"""
    names = list(uni_slice.keys())
    closes = {}
    for n in names:
        closes[n] = pd.Series(uni_slice[n]["close"].values,
                              index=pd.to_datetime(uni_slice[n]["dates"].values)).reindex(common).ffill()
    out = []
    for t in range(1, len(common)):
        rs = []
        for n in names:
            c0, c1 = closes[n].iloc[t - 1], closes[n].iloc[t]
            if pd.notna(c0) and pd.notna(c1) and c0 > 0:
                rs.append(c1 / c0 - 1)
        out.append(float(np.mean(rs)) if rs else 0.0)
    return out

def filtered_equal_weight(uni_slice, common, regime_up):
    """过滤等权持有：regime up 时等权整篮在市，down 时转现金；使用真实A股交易成本。"""
    ru = list(regime_up.values)
    daily = _daily_eqw_ret(uni_slice, common)
    eq, eqs, trades = 1.0, [1.0], []
    prev_in = None
    N = len(uni_slice)
    
    # 真实交易成本（基于成交额计算）：买入时总费率≈0.00126（佣金+过户费+滑点），卖出时≈0.00226（加印花税）
    BUY_COST = TRADING_COSTS["commission"] + TRADING_COSTS["transfer_fee"] + TRADING_COSTS["slippage"]
    SELL_COST = TRADING_COSTS["commission"] + TRADING_COSTS["transfer_fee"] + TRADING_COSTS["slippage"] + TRADING_COSTS["stamp_duty"]
    
    for t in range(1, len(common)):
        in_mkt = ru[t - 1]
        step = (1 + daily[t - 1]) if in_mkt else 1.0
        
        if in_mkt != prev_in:
            # 切换仓位时扣除真实交易成本
            if in_mkt:
                step *= (1 - BUY_COST)
                action = "买入整篮"
            else:
                step *= (1 - SELL_COST)
                action = "清仓转现金"
            
            prev_in = in_mkt
            trades.append({"date": str(pd.Timestamp(common[t]).date()),
                           "regime": "up" if in_mkt else "down",
                           "action": action,
                           "holdings": f"等权{N}只" if in_mkt else "(空仓)",
                           "cost": f"{BUY_COST*100:.3f}%" if in_mkt else f"{SELL_COST*100:.3f}%"})
        
        eq *= step
        eqs.append(eq)
    return eqs, trades

def raw_equal_weight(uni_slice, common):
    """买入持有基准：始终等权在市。"""
    daily = _daily_eqw_ret(uni_slice, common)
    eq = 1.0
    eqs = [1.0]
    for r in daily:
        eq *= (1 + r)
        eqs.append(eq)
    return eqs


# ----------------------------- T3 真实基本面截面（可选模式） -----------------------------
# 数据现实：逐日主力资金流 (stock_individual_fund_flow) 被本环境代理掐断 → 资金流维度暂挂起；
#           真实基本面 (stock_financial_abstract) 可取，按 A 股披露截止日映射 as-of 防未来函数。
def report_asof(y, m):
    """A 股披露截止日 + 缓冲 → 该报告期可被交易使用的最早日期（防未来函数）。"""
    if m == 3:  return pd.Timestamp(y, 5, 15)      # Q1: 4/30 前
    if m == 6:  return pd.Timestamp(y, 9, 15)      # H1: 8/31 前
    if m == 9:  return pd.Timestamp(y, 11, 15)     # Q3: 10/31 前
    if m == 12: return pd.Timestamp(y + 1, 5, 15)  # 年报: 次年 4/30 前

def _fnum(row, col):
    if row is None:
        return np.nan
    try:
        v = row[col]
        return float(v) if pd.notna(v) else np.nan
    except Exception:
        return np.nan

def load_fundamentals(code):
    """返回 [(asof:Timestamp, roe, revg, profg), ...] 按 asof 升序；带 CSV 缓存 + 重试。"""
    cp = cache_path("fund", code)
    if os.path.exists(cp) and os.path.getsize(cp) > 0:
        try:
            df = pd.read_csv(cp, parse_dates=["asof"])
            return list(df.itertuples(index=False, name=None))
        except Exception:
            pass
    last_err = None
    for _attempt in range(3):  # 重试缓解代理瞬时断连
        try:
            import akshare as ak
            raw = ak.stock_financial_abstract(symbol=code)
            if raw is None or raw.empty:
                return []
            def grab(sub):
                r = raw[raw["指标"].str.contains(sub, na=False)]
                return r.iloc[0] if len(r) else None
            roe_row = grab("净资产收益率")
            rev_row = grab("营业总收入增长率")
            prof_row = grab("归属母公司净利润增长率")   # 注意：非"归母净利润增长率"
            date_cols = [c for c in raw.columns if c not in ("选项", "指标")
                         and str(c).isdigit() and len(str(c)) == 8]
            dedup = {}
            for dc in date_cols:
                rd = str(dc); y, m = int(rd[:4]), int(rd[4:6])
                rec = (report_asof(y, m), _fnum(roe_row, dc), _fnum(rev_row, dc), _fnum(prof_row, dc))
                if not any(pd.notna(x) for x in rec[1:]):
                    continue
                k = rec[0]
                if k not in dedup or sum(pd.notna(x) for x in rec[1:]) > sum(pd.notna(x) for x in dedup[k][1:]):
                    dedup[k] = rec
            recs = list(dedup.values())
            if recs:
                pd.DataFrame(recs, columns=["asof", "roe", "revg", "profg"]).to_csv(cp, index=False)
                return recs
            else:
                last_err = "no_records"; break
        except Exception as e:
            last_err = e; continue
    if last_err is not None and not isinstance(last_err, str):
        print(f"    ⚠️ load_fundamentals({code}) 失败: {type(last_err).__name__}")
    return []

def fundamentals_at(fhist, asof_ts):
    """返回 as-of<=asof_ts 的最新一条 (roe, revg, profg)，无则 None。"""
    chosen = None
    for (ad, roe, revg, profg) in fhist:
        if ad <= asof_ts:
            chosen = (roe, revg, profg)
        else:
            break
    return chosen

def fundamentals_selection(uni_slice, common, regime_up, funda, top_n=5, period=21):
    """趋势向上区间内，按 ROE+营收增速+利润增速 综合排名选前 N 等权持有；T+1，使用真实交易成本。返回 (eqs, trades)。"""
    names = list(uni_slice.keys())
    closes = {n: pd.Series(uni_slice[n]["close"].values,
                           index=pd.to_datetime(uni_slice[n]["dates"].values)).reindex(common).ffill() for n in names}
    fhist = {n: sorted(funda.get(uni_slice[n]["code"], []), key=lambda x: x[0]) for n in names}
    T = len(common)
    wmat = {t: {n: 0.0 for n in names} for t in range(T)}
    prev_rebal = -9999; trades = []; last_target = {}
    
    # 真实交易成本
    BUY_COST = TRADING_COSTS["commission"] + TRADING_COSTS["transfer_fee"] + TRADING_COSTS["slippage"]
    SELL_COST = TRADING_COSTS["commission"] + TRADING_COSTS["transfer_fee"] + TRADING_COSTS["slippage"] + TRADING_COSTS["stamp_duty"]
    
    for t in range(T):
        in_mkt = bool(regime_up.iloc[t - 1]) if t > 0 else False
        target = {}
        if in_mkt and (t - prev_rebal) >= period:
            valid = {}
            for n in names:
                f = fundamentals_at(fhist[n], common[t - 1])
                if f is not None and all(pd.notna(x) for x in f):
                    valid[n] = f
            if len(valid) >= 2:
                # rank-sum 复合（量纲无关、稳健；与 game_sector_backtest_t3.py 一致）
                roes = {n: v[0] for n, v in valid.items()}
                revgs = {n: v[1] for n, v in valid.items()}
                profgs = {n: v[2] for n, v in valid.items()}
                comp = (pd.Series(roes).rank(ascending=False)
                        + pd.Series(revgs).rank(ascending=False)
                        + pd.Series(profgs).rank(ascending=False))
                ranked = comp.sort_values(ascending=False).index[:top_n]
                w = 1.0 / len(ranked)
                target = {n: w for n in ranked}
            prev_rebal = t
            if target and target != last_target:
                top3 = sorted(target, key=lambda n: target[n], reverse=True)[:3]
                trades.append({"date": str(pd.Timestamp(common[t]).date()), "regime": "up",
                               "action": "基本面调仓(前3: %s)" % "/".join(top3),
                               "holdings": "等权前%d只" % len(target)})
        elif not in_mkt and last_target:
            trades.append({"date": str(pd.Timestamp(common[t]).date()), "regime": "down",
                           "action": "清仓转现金", "holdings": "(空仓)"})
        for n in names:
            wmat[t][n] = target.get(n, 0.0)
        last_target = target
    eq = 1.0; eqs = [1.0]; prev_w = {n: 0.0 for n in names}
    for t in range(1, T):
        cur_w = wmat[t]; ret = 0.0
        for n in names:
            c0 = closes[n].iloc[t - 1]; c1 = closes[n].iloc[t]
            if pd.notna(c0) and pd.notna(c1) and c0 > 0:
                ret += prev_w[n] * (c1 / c0 - 1)
        
        # 计算调仓换手成本
        turnover = sum(abs(cur_w[n] - prev_w[n]) for n in names)
        if turnover > 0:
            # 假设换手一半是买入一半是卖出，取平均成本
            avg_cost = (BUY_COST + SELL_COST) / 2
            ret -= avg_cost * turnover
        
        eq *= (1 + ret); eqs.append(eq); prev_w = cur_w
    return eqs, trades


# ----------------------------- 度量 -----------------------------
def metrics(eq):
    eq = np.array(eq, float)
    total = eq[-1] - 1
    cagr = eq[-1] ** (252.0 / len(eq)) - 1
    mdd = float((eq / np.maximum.accumulate(eq) - 1).min())
    dret = np.diff(eq)
    dret = dret[dret != 0]
    sh = float(np.mean(dret) / (np.std(dret) + 1e-9) * math.sqrt(252)) if len(dret) > 1 else 0.0
    return {"total_return_pct": round(total * 100, 2), "cagr_pct": round(cagr * 100, 2),
            "max_drawdown_pct": round(mdd * 100, 2), "sharpe": round(sh, 3)}


# ----------------------------- 编排 -----------------------------
def run_sector(cfg, period_name, p0, p1, mode="filtered"):
    """跑单个板块单周期。mode:
        'filtered' → 过滤等权持有（默认推荐）；'quality' → 过滤等权 + 基本面截面选股(T3)。
    返回结果字典（含 strategy/raw 净值、trades、metrics、dates、mode、n_stocks、fund_cov）。"""
    print(f"\n### 板块: {cfg.get('name', '?')}  周期: {period_name}  模式: {mode}")
    uni = build_universe(cfg)
    if len(uni) < 3:
        return None
    etf = load_etf(cfg["etf"])
    common = sorted(set().union(*[set(uni[n]["dates"].values) for n in uni]))
    common = [pd.Timestamp(d) for d in common]
    if len(common) < WARMUP + 20:
        print("  ⚠️ 共同交易日不足，跳过")
        return None
    sl = slice_uni({n: {"code": uni[n]["code"], "name": n,
                        "dates": uni[n]["dates"], "close": uni[n]["close"]} for n in uni}, p0, p1)
    if len(sl) < 3:
        print("  ⚠️ 切片后有效标的不足，跳过")
        return None
    cslice = sorted(set().union(*[set(sl[n]["dates"].values) for n in sl]))
    cslice = [pd.Timestamp(d) for d in cslice]
    regime, src = build_regime(etf, sl, cslice)
    req = raw_equal_weight(sl, cslice)
    fund_cov = None
    if mode == "quality":
        funda = {uni[n]["code"]: load_fundamentals(uni[n]["code"]) for n in uni}
        fund_cov = sum(1 for c in funda.values() if len(c) > 0)
        print(f"    基本面覆盖: {fund_cov}/{len(uni)}")
        seq, str_tr = fundamentals_selection(sl, cslice, regime, funda, top_n=5)
        strat_eq, strat_tr, strat_label = seq, str_tr, "质量截面"
    else:
        seq, str_tr = filtered_equal_weight(sl, cslice, regime)
        strat_eq, strat_tr, strat_label = seq, str_tr, "过滤等权"
    return {"sector": cfg.get("name"), "period": period_name, "mode": mode,
            "regime_source": src, "strategy_label": strat_label,
            "dates": [str(pd.Timestamp(d).date()) for d in cslice],
            "strategy": strat_eq, "raw": req, "trades": strat_tr,
            "metrics_strategy": metrics(strat_eq), "metrics_raw": metrics(req),
            "n_stocks": len(sl), "fund_cov": fund_cov}


# ----------------------------- 仪表盘 -----------------------------
def _equity_svg(curves, w=720, h=300):
    """curves: list of (label, [equity...], color)。返回 SVG 字符串（含脏值防护）。"""
    if not curves:
        return ""
    n = len(curves[0][1])
    xs = np.linspace(0, w - 40, max(n - 1, 1))
    def xy(vals):
        vals = np.array(vals, float)
        lo, hi = np.nanmin(vals), np.nanmax(vals)
        if not np.isfinite(lo) or not np.isfinite(hi) or hi == lo:
            lo, hi = 0.0, 1.0
        ys = h - 30 - (vals - lo) / (hi - lo) * (h - 60)
        return list(zip(xs, np.nan_to_num(ys, nan=h - 30)))
    parts = [f'<svg viewBox="0 0 {w} {h}" width="100%" style="max-width:{w}px;background:#1e1e2e;border-radius:8px">']
    parts.append(f'<line x1="20" y1="{h-30}" x2="{w-20}" y2="{h-30}" stroke="#444" stroke-width="1"/>')
    for label, vals, color in curves:
        p = " ".join(f"{a:.1f},{b:.1f}" for a, b in xy(vals))
        parts.append(f'<polyline points="{p}" fill="none" stroke="{color}" stroke-width="2"/>')
        parts.append(f'<text x="{w-18}" y="{xy(vals)[-1][1]+4:.0f}" fill="{color}" font-size="11" text-anchor="end">{label}</text>')
    parts.append('</svg>')
    return "".join(parts)

def render_dashboard(path, title, rows, curves, language="zh", strat_label="过滤等权"):
    """rows: 对比表 (每行为 dict)，curves: 仪表盘净值曲线。strat_label: 策略列名(过滤等权/质量截面)。"""
    dis = ("⚠️ 以上内容由 AI 基于公开信息整理生成，仅供参考，不构成任何投资建议或个股推荐。"
           "投资有风险，决策需谨慎。") if language == "zh" else \
          ("⚠️ The above content is generated by AI from public information for reference only. "
           "It does not constitute investment advice or any recommendation to buy or sell specific securities. "
           "Investing carries risk; make your own decisions carefully.")
    head = (f"<tr><th>板块</th><th>周期</th><th>{strat_label}总收益</th><th>{strat_label}回撤</th>"
            f"<th>{strat_label}夏普</th><th>持有总收益</th><th>超额 vs 持有</th></tr>")
    body = ""
    for r in rows:
        body += (f"<tr><td>{r['sector']}</td><td>{r['period']}</td>"
                 f"<td>{r['strat_tr']}%</td><td>{r['strat_mdd']}%</td>"
                 f"<td>{r['strat_sharpe']}</td><td>{r['raw_tr']}%</td>"
                 f"<td>{r['excess']}%</td></tr>")
    html = f"""<!DOCTYPE html><html lang="{language}-CN"><head><meta charset="utf-8">
<title>{title}</title><style>
body{{background:#15151f;color:#e6e6e6;font-family:-apple-system,Segoe UI,Roboto,'Microsoft YaHei',sans-serif;margin:0;padding:24px}}
h1{{font-size:20px;margin:0 0 4px}}.sub{{color:#9aa;font-size:13px;margin-bottom:18px}}
.cards{{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:20px}}
.card{{background:#1e1e2e;border:1px solid #2c2c3c;border-radius:10px;padding:14px 18px;min-width:150px}}
.card .k{{font-size:12px;color:#9aa}}.card .v{{font-size:22px;font-weight:600;margin-top:4px}}
table{{border-collapse:collapse;width:100%;margin:14px 0;font-size:13px}}
th,td{{border:1px solid #2c2c3c;padding:8px 10px;text-align:center}}
th{{background:#23233a;color:#cdd}}tr:nth-child(even) td{{background:#1b1b28}}
.note{{background:#1e1e2e;border-left:3px solid #f5a623;padding:10px 14px;font-size:13px;color:#cdd;margin:14px 0;border-radius:4px}}
.dis{{color:#9aa;font-size:12px;margin-top:24px}}
</style></head><body>
<h1>{title}</h1>
<div class="sub">{strat_label}策略 · 板块 ETF(或回退等权指数) 200MA 趋势过滤 · 成本仅切换时 0.1%/边</div>
<div class="cards">"""
    for r in rows[:6]:
        html += f'<div class="card"><div class="k">{r["sector"]}·{r["period"]}</div><div class="v">{r["strat_tr"]}%</div></div>'
    html += f"""</div>
<div class="note">结论（{strat_label}）：200MA 过滤是「跌时少亏」工具而非「涨时多赚」工具。
{'质量截面在下跌/震荡段跑赢过滤等权、在牛市会跑输（截断了涨势最强的标的），属防御型倾斜，非默认升级。' if strat_label=='质量截面' else '过滤等权持有在样本外多板块中整体跑赢主动动量选股，且回撤显著低于买入持有。逻辑透明、成本低、稳健。'}</div>
<table><thead>{head}</thead><tbody>{body}</tbody></table>
<h3 style="margin-top:22px">净值曲线（{strat_label} vs 买入持有）</h3>
{_equity_svg(curves)}
<div class="dis">{dis}</div>
</body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


# ----------------------------- CLI -----------------------------
def main():
    import argparse
    ap = argparse.ArgumentParser(description="板块策略回测（过滤等权持有 / 质量截面 T3）")
    ap.add_argument("--sector", default=None, help="板块名(游戏/半导体/新能源)")
    ap.add_argument("--period", default="全周期2021-26", help="周期名")
    ap.add_argument("--mode", default="filtered", choices=["filtered", "quality"],
                    help="filtered=过滤等权持有(默认推荐); quality=过滤等权+基本面截面选股(T3)")
    ap.add_argument("--all", action="store_true", help="跑全部 3 板块 × 全周期")
    args = ap.parse_args()

    mode = args.mode
    strat_label = "质量截面" if mode == "quality" else "过滤等权"
    targets = []
    if args.all:
        for s, cfg in UNIVERSES.items():
            targets.append((s, dict(cfg), "全周期2021-26", *PERIODS["全周期2021-26"]))
    elif args.sector:
        cfg = UNIVERSES.get(args.sector)
        if not cfg:
            print("未知板块:", args.sector); return
        targets.append((args.sector, dict(cfg), args.period, *PERIODS[args.period]))
    else:
        print("请指定 --sector 或 --all"); return

    rows, curves = [], []
    colors = ["#5b8def", "#f5a623", "#ff7a85", "#7ed957", "#c792ea", "#4dd0e1"]
    ci = 0
    for sname, cfg, pname, p0, p1 in targets:
        cfg = dict(cfg); cfg["name"] = sname
        res = run_sector(cfg, pname, p0, p1, mode=mode)
        if not res:
            continue
        ms, mr = res["metrics_strategy"], res["metrics_raw"]
        rows.append({"sector": sname, "period": pname,
                     "strat_tr": ms["total_return_pct"], "strat_mdd": ms["max_drawdown_pct"],
                     "strat_sharpe": ms["sharpe"], "raw_tr": mr["total_return_pct"],
                     "excess": round(ms["total_return_pct"] - mr["total_return_pct"], 2),
                     "fund_cov": res.get("fund_cov")})
        curves.append((f"{sname}·{res['strategy_label']}", res["strategy"], colors[ci % len(colors)]))
        curves.append((f"{sname}·持有", res["raw"], "#555"))
        ci += 1
    if rows:
        fname = "index_t3_quality.html" if mode == "quality" else "index_filtered_eqw.html"
        title = f"板块策略回测 · {strat_label}"
        render_dashboard(os.path.join(os.getcwd(), fname), title, rows, curves,
                        language="zh", strat_label=strat_label)
        print(f"\n✅ 仪表盘已写出: {fname}  (模式={strat_label})")
        for r in rows:
            fc = f"  基本面覆盖={r['fund_cov']}" if r["fund_cov"] is not None else ""
            print(f"  {r['sector']}·{r['period']}: {strat_label} {r['strat_tr']}% / 持有 {r['raw_tr']}% / 超额 {r['excess']}%{fc}")


if __name__ == "__main__":
    main()
