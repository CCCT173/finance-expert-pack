# Finance Expert Pack

> A single, portable **Skill** that consolidates fragmented financial-analysis capabilities into one drop-in package.
> Covers real-time quotes, technical analysis, capital flows, sentiment, market environment, and sector-strategy backtesting for **A-shares / HK stocks / US stocks**.

---

## What is this

`finance-expert-pack` is a **Skill engineering bundle** for financial research. It converges 9 previously independent financial Skills plus an expert analysis framework into one directory that can be distributed and run as-is. It depends on no commercial backtesting platform — the core backtest logic is implemented in **pure Python + pandas**, and data comes from public sources (akshare, etc.) with local caching and resumable fetching.

One design goal only: **make analysis reproducible, traceable, and free of fabrication.**

---

## Core features

- **Single entry point, intent-based routing**: one Skill covers real-time monitoring, technical analysis, capital flows, sentiment, finance hot lists, global market environment, natural-language financial data search, heat ranking, and sector-strategy backtesting. A routing table in `SKILL.md` dispatches uniformly, avoiding duplicate triggers and file conflicts across multiple Skills.
- **Sector-strategy backtest (flagship)**: built-in "filtered equal-weight hold" rule — equal-weight the whole basket plus a 200MA trend filter on the sector ETF (falls back to an equal-weight index if missing); drop to cash below the MA, executed T+1. Validated out-of-sample across multiple sectors as the best current simple rule. A `--mode quality` experimental mode does fundamental cross-sectional selection (defensive tilt).
- **Strict backtest discipline**: trend signals are always judged on `t-1` close (T+1), with no look-ahead; warmup uses `min_periods=120`; cost counts only one-sided switching fees; on fetch failure it degrades gracefully and explicitly reports coverage `M<N`.
- **Multi-source degradation, no hard crashes**: when the primary real-time quote source (Zhitu) is missing, relevant scripts return empty with a warning instead of crashing; capital-flow hits Eastmoney HTTP directly with rate limiting; fundamentals go through akshare.
- **Traceable analysis principles**: facts / inferences / guesses are layered; contradictions must be shown; missing data is tagged "not fetched"; every data point carries a source; the package refuses "must rise / precise entry / guaranteed profit" phrasing throughout.
- **Pure local, auditable**: no black-box model service is called for data fetching; backtest scripts run directly via `python xxx.py` and produce a standard set of artifacts: `equity.csv / trades.csv / summary.json / index.html`.

---

## Directory structure

```
finance-expert-pack/
├── SKILL.md                              # Skill entry + capability routing table
├── _meta.json                            # Package metadata (name / version / deps / author)
├── requirements.txt                      # Python runtime dependencies
├── references/                           # Analysis frameworks, data sources, sub-skill docs
│   ├── analysis-framework.md             # Fusion analysis framework v1.0
│   ├── stock-master-workflow.md          # Unified workflow (hard rules + scenario routing)
│   ├── data-sources.md                   # Data-source tiers and degradation strategy
│   ├── stock-analysis-23/                # 23 Tonghuashun (TDX) indicator reference docs
│   └── ...
└── scripts/
    ├── run_analysis.py                   # Individual-stock deep-analysis orchestrator (one-shot JSON)
    ├── a-share-monitor/                  # Real-time quotes / monitoring
    ├── a-share-pro/                      # Watchlist management (plain-text storage)
    ├── workspace/
    │   ├── sector_strategy.py            # Sector-strategy backtest (filtered eqw / quality dual-mode)
    │   ├── stock_capital_data.py         # Capital flows / chip / events / research-report fill-in
    │   ├── stock_fundamentals.py         # Fundamentals / valuation / event data
    │   ├── technical_analysis.py         # MACD/KDJ/RSI/BOLL/MA indicator scoring
    │   ├── sentiment_scan.py             # Sentiment monitoring and scoring (-10~+10)
    │   └── ...
    ├── market-environment-analysis/      # Global market environment / risk appetite
    ├── neodata-financial-search/         # Natural-language financial data search
    └── stock-heat-rank-py/               # A-share real-time heat TOP50
```

---

## Quick start

### 1. Install dependencies

```bash
pip install -r requirements.txt
# Core packages: requests / pandas / numpy / akshare / baostock / yfinance / openpyxl
```

### 2. Configure environment variables

The primary real-time quote source (Zhitu) needs a Token; the rest are optional degradation sources.

```powershell
$env:ZHITU_TOKEN = "your-token"        # Required: primary real-time quote source
$env:TUSHARE_TOKEN = "your-token"      # Optional: a-share-pro multi-source fallback
```

When not configured, scripts depending on that source will **return empty with a stderr warning**; other capabilities are unaffected.

### 3. Run an example

```bash
# Individual-stock deep analysis (quotes + technical + capital + fundamentals + valuation + events, one-shot JSON)
python scripts/run_analysis.py 600519

# Sector "filtered equal-weight hold" backtest (default; 3 sectors x full period; produces index_filtered_eqw.html)
python scripts/workspace/sector_strategy.py --all
python scripts/workspace/sector_strategy.py --sector 游戏 --period 全周期2021-26

# T3 experimental mode: filtered eqw + fundamental cross-sectional selection (produces index_t3_quality.html)
python scripts/workspace/sector_strategy.py --mode quality --all

# Real-time quotes / monitoring
python scripts/a-share-monitor/zhitu_monitor.py 600273 嘉化能源
```

---

## Sector-strategy backtest

`scripts/workspace/sector_strategy.py` is the core of this package's backtest capability.

| Mode | Description | Artifacts |
|------|-------------|-----------|
| `--mode filtered` (default) | Equal-weight the whole basket + 200MA trend filter on the sector ETF; drop to cash below the MA | `index_filtered_eqw.html` |
| `--mode quality` | Within an upward-trend regime, rank by ROE / revenue-growth / profit-growth (rank-sum composite) and equal-weight the top 5, rebalanced monthly (defensive tilt, **not** a default upgrade) | `index_t3_quality.html` |

Hard discipline constraints:
- Signals judged on `t-1` close, executed T+1 — **no look-ahead**;
- warmup `min_periods=120`;
- cost counts only one-sided switching fees (optimistic — see Limitations below);
- data via akshare + local cache with resume; failures explicitly report coverage.

---

## Real limitations (please read)

To avoid misleading users, the following limitations are **genuinely present**, not padding:

1. **Real-time quotes depend on an external Token**: without `ZHITU_TOKEN`, real-time monitoring / heat ranking is unavailable (degradation warnings exist, but no numbers are fabricated).
2. **Backtest cost is optimistic**: currently only one-sided switching fees are counted — no stamp duty, transfer fee, slippage, or impact cost; real-world friction will erode returns.
3. **Backtest universe has survivorship bias**: constituents are taken as of the current date; historical delistings / renamings are not handled, so out-of-sample conclusions should be extrapolated with caution.
4. **Capital-flow dimension is suspended**: daily main-force capital flow is temporarily unavailable due to a data-source interface block, so the T3 experiment is currently pure-fundamental cross-section — the quality dimension is incomplete.
5. **Only 5 of 23 TDX indicators are implemented locally**: MACD/KDJ/RSI/BOLL/MA are done; the full M001–M023 needs an external TDX environment — see `references/stock-analysis-23/`.
6. **A-share backtest is primary**: sector-backtest samples are currently concentrated in A-share sectors; HK / US paths exist but lack equivalent out-of-sample validation.
7. **Data-source stability risk**: public sources like akshare / Eastmoney fluctuate with site redesigns, occasionally dropping fields or rate-limiting; scripts retry and degrade but cannot guarantee 100% coverage.

---

## Analysis principles

This package inherits seven iron rules from the expert analysis framework:

1. Data must come from real sources; fabricating numbers is forbidden;
2. Distinguish fact / inference / guess, and label uncertainty as "inference" or "scenario";
3. Forbid "must rise / precise entry / guaranteed profit"; use base / bull / bear three-scenario framing with trigger conditions and invalidation levels;
4. Contradictions must be presented, not smoothed over;
5. Missing data is not fabricated, but tagged "not fetched";
6. Every data point carries a source;
7. All output is for research reference only and does not constitute investment advice.

---

## Disclaimer

> ⚠️ All content in this toolkit is compiled from public information for reference only. It does not constitute any investment advice or specific stock recommendation. Investing carries risk; make your own decisions carefully. Backtest results are historical simulations and do not represent future returns.

---

## License

This repository is open-sourced under the **MIT** License, for research and study purposes only.
