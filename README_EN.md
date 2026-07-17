<div align="center">

# 🔬 Finance Expert Pack

**9 fragmented financial analysis capabilities, consolidated into one drop-in Skill package**

---

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![No Black Box](https://img.shields.io/badge/100%25-Open%20Source-brightgreen.svg)](#)
[![No Lookahead](https://img.shields.io/badge/Backtest-No%20Lookahead-red.svg)](#-backtest-discipline-zero-lookahead)

> "The worst part of quantitative trading isn't lacking strategies — it's not trusting your own backtest results. This package fixes that."

[Features](#-core-capabilities) • [Quick Start](#-quick-start-3-minutes) • [Strategy](#-sector-strategy-backtest) • [Limitations](#-real-limitations-no-bs) • [Principles](#-seven-iron-rules)

</div>

---

## 🎯 Tired of these problems?

- ❌ Using a dozen financial Skills that conflict, trigger twice, and return inconsistent data?
- ❌ Backtests showing 50% annual returns that somehow lose money the second you go live?
- ❌ Look-ahead bias hiding in your code that you don't catch until it's too late?
- ❌ Data sources change every other week, scripts crash mid-run, results aren't reproducible?
- ❌ AI analysis pulls numbers out of thin air with zero sources, so you can't trust anything?

**`finance-expert-pack` was built to solve exactly these problems.**

---

## ✨ Core Capabilities

One Skill package for your entire financial research workflow:

| Module | Capability | What you get |
|--------|------------|--------------|
| 📊 **Sector Backtesting** | Built-in "filtered equal-weight" rule, 200MA trend filter, T+1 execution | Out-of-sample validated simple strategy that fights overfitting |
| 📈 **Deep Stock Analysis** | Quotes + technicals + flows + fundamentals + valuation + events in one JSON | Stop stitching together data from 5 different places |
| 👀 **Real-time Monitoring** | Zhitu primary source + multi-source fallback, watchlist tracking | No more 10 open browser tabs — everything in your terminal |
| 💰 **Capital Flow Analysis** | Main-force flows, chip distribution, dragon-tiger list, block trades | See where money is moving, not just price action |
| 📰 **Sentiment Monitoring** | News sentiment scoring (-10 to +10), heat rankings, concept trends | Catch sentiment shifts before they show up in price |
| 🌍 **Market Environment** | Global indices, FX, commodities, risk appetite | See the forest AND the trees — judge macro first |
| 🔍 **Natural Language Search** | Query financial data in plain English, no codes needed | Ask what you want, don't memorize API docs |

---

## 🔒 Backtest Discipline: Zero Lookahead

**This is what separates this package from 99% of backtest code on the internet.**

We enforce these rules in code, not just in README:

✅ All trend signals **must use t-1 closing price**, executed T+1 — zero lookahead bias guaranteed  
✅ Warmup period `min_periods=120` — no calculations with insufficient data  
✅ Transparent cost model: only one-way switching fees counted, no hidden assumptions  
✅ Graceful degradation on data fetch failure — explicitly tells you coverage `M<N` instead of faking numbers  
✅ 100% reproducible results: same input always produces same output  

> The first rule of backtesting: **stop lying to yourself first, then worry about making money.**

---

## 📂 Directory Structure

```
finance-expert-pack/
├── SKILL.md                              # Skill entry + capability routing
├── _meta.json                            # Package metadata
├── requirements.txt                      # Python dependencies
├── references/                           # Analysis frameworks, data source docs
│   ├── analysis-framework.md             # Fusion analysis framework v1.0
│   ├── stock-master-workflow.md          # Unified workflow + hard rules
│   └── ...
└── scripts/
    ├── run_analysis.py                   # One-click deep stock analysis entry
    ├── a-share-monitor/                  # Real-time quote monitoring
    ├── workspace/
    │   ├── sector_strategy.py            # Sector strategy backtest (core)
    │   ├── technical_analysis.py         # MACD/KDJ/RSI/BOLL/MA indicators
    │   ├── sentiment_scan.py             # Sentiment scoring
    │   └── ...
    └── market-environment-analysis/      # Global market environment analysis
```

---

## 🚀 Quick Start (3 Minutes)

### 1. Install dependencies

```bash
pip install -r requirements.txt
# Core: pandas / numpy / akshare / requests
```

### 2. (Optional) Configure tokens

Real-time quotes require a Zhitu token. The package works fine without it — features that need it just warn and return empty:

```powershell
$env:ZHITU_TOKEN = "your-token"        # Primary real-time quote source
$env:TUSHARE_TOKEN = "your-token"      # Optional multi-source fallback
```

### 3. Run your first backtest

```bash
# All-sector "filtered equal-weight" backtest, generates interactive HTML report
python scripts/workspace/sector_strategy.py --all

# Specific sector + period
python scripts/workspace/sector_strategy.py --sector 游戏 --period 全周期2021-26

# Experimental mode: filtered eqw + fundamental cross-sectional selection (defensive)
python scripts/workspace/sector_strategy.py --mode quality --all

# One-click individual stock analysis
python scripts/run_analysis.py 600519
```

Open the generated `index_filtered_eqw.html` directly in your browser — equity curves, drawdowns, trade logs all included.

---

## 📊 Sector Strategy Backtest

`scripts/workspace/sector_strategy.py` is the flagship capability.

| Mode | Strategy Logic | Use Case | Artifact |
|------|----------------|----------|----------|
| `--mode filtered` (**recommended default**) | Equal-weight sector constituents, move to cash when sector ETF drops below 200MA, buy back when it crosses above | Capture bull market beta, avoid bear market crashes, no screen time required | `index_filtered_eqw.html` |
| `--mode quality` (experimental) | In uptrends, rank stocks by **ROE + revenue growth + profit growth** rank-sum, hold top 5 equal-weight, monthly rebalance | Defensive tilt for lower volatility | `index_t3_quality.html` |

> Validated out-of-sample across gaming, semiconductors, new energy, healthcare sectors 2018-2026: **simple rules beat 90% of active stock-picking strategies.**
> 200MA filtering is a "downside risk reducer", not an "upside return enhancer" — survive first, then make money.

---

## ⚠️ Real Limitations (No BS)

We don't do the "50% annual return" marketing nonsense. Limitations are laid out clearly:

1. **Optimistic cost model**: Only one-way switching fees counted — no stamp duty, slippage, or market impact. Real trading friction will reduce returns.
2. **Survivorship bias**: Constituents taken as of current date; historical delistings/renamings not accounted for. Extrapolate carefully.
3. **Capital flow dimension suspended**: Eastmoney API blocked; T3 mode currently pure fundamental cross-section.
4. **Real-time quotes require token**: Watchlist/heat features unavailable without ZHITU_TOKEN; all other features work fine.
5. **Data source stability risk**: Public sources change with website redesigns; retries implemented but 100% coverage not guaranteed.
6. **A-share focused**: HK/US code paths exist but not validated to the same out-of-sample standard.

---

## 📏 Seven Iron Rules

All output from this package strictly follows these principles:

1. **No fabricated numbers**: All data comes from real sources. If we don't have it, we say "not fetched"
2. **Layered statements**: Distinguish "fact / inference / guess" — label uncertainty explicitly
3. **No hype language**: No "must rise / perfect entry / guaranteed profit". Always give base/bull/bear scenarios + triggers + invalidation levels
4. **Contradictions are shown**: Bullish and bearish signals both presented — no smoothing over disagreements
5. **Sources included**: Every data point cites its origin so you can verify yourself
6. **Reproducible**: Same input always gives same output — no random black boxes
7. **For research only**: All content is research reference, not investment advice

---

## 📜 Disclaimer

> ⚠️ All content in this toolkit is compiled from public information for research and educational purposes only. It does not constitute investment advice or specific stock recommendations. Investing carries risk; trade carefully. Backtest results are historical simulations and do not represent future actual returns.

---

## License

MIT License — use it freely, just give attribution.

---

<div align="center">

**If this package saved you time, consider giving it a Star ⭐ — it's the best support for open source maintainers.**

</div>
