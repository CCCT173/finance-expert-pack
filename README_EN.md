<div align="center">

# 💰 A-Share Quantitative Trading Toolkit · Backtest You Can Actually Trade

### Zero Config · Zero Tokens · Zero Lookahead Bias · Real A-Share Trading Costs

---

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![100% Open Source](https://img.shields.io/badge/100%25-Open%20Source-brightgreen.svg)](#)
[![Zero Lookahead](https://img.shields.io/badge/Backtest-Zero%20Lookahead-red.svg)](#-backtest-discipline-tradable-standards)
[![Real Costs](https://img.shields.io/badge/Costs-Real%20AShare%20Fees-orange.svg)](#-real-trading-costs-no-inflated-returns)
[![No Tokens Needed](https://img.shields.io/badge/Auth-Zero%20Tokens-green.svg)](#-zero-configuration-out-of-the-box)

> "50% annual return on backtest, 30% loss in live trading — 99% of quant tools cheat on costs and lookahead bias. This one doesn't."
> 
> **Gaming Sector 5-year Backtest: Strategy 105.8% vs Buy&Hold 72.8%, +33% alpha AFTER all commissions/stamp duty/slippage**

[![GitHub](https://img.shields.io/badge/GitHub-CCCT173%2Ffinance--expert--pack-blue?logo=github)](https://github.com/CCCT173/finance-expert-pack)
[![SkillHub](https://img.shields.io/badge/SkillHub-Install%20Skill-orange?logo=skillhub)](https://skillhub.cn/skills/finance-expert-pack)

[Features](#-full-feature-matrix-end-to-end-trading-workflow) • [Quick Start](#-quick-start-copy-paste-and-run) • [Empirical Results](#-empirical-performance-beats-benchmarks) • [Why Different](#-why-were-different-from-other-backtesters) • [Rules](#-seven-iron-rules)

**[👉 Install directly from SkillHub](https://skillhub.cn/skills/finance-expert-pack)** | **[⭐ GitHub Source](https://github.com/CCCT173/finance-expert-pack)**

</div>

---

## 🔴 You've Hit These Pitfalls Before

- Found a strategy online that triples in backtest, loses 20% in 3 months live — **because they didn't count stamp duty/slippage/limit locks**
- Hidden lookahead bias in code you can't see, stops and entries calculated using future prices, results are completely fake
- Installed 7 different finance plugins that conflict, return inconsistent data, waste time switching between them
- Data sources change every other week, scripts crash mid-run, last month's results are impossible to reproduce
- AI analysis pulls numbers out of thin air, you lose money and don't even know why
- Tools force you to register for API tokens before you can even try the core features

**This package was built to fix exactly these problems.**

---

## ✅ Full Feature Matrix ｜ End-to-End Trading Workflow
One skill covers your entire A-share workflow, no need for 7 different plugins:

| Module | Capability | Live Trading Value |
|--------|------------|--------------------|
| 📊 **Sector Backtesting** | Built-in filtered equal-weight rule with 200MA trend filter, **real A-share costs (commission/stamp duty/transfer fees/slippage fully calculated)** | +33% excess return over 5 years after all costs, captures bull beta, avoids bear crashes, no screen time needed |
| 🔍 **Stock Screener** | MA alignment/MACD golden cross/breakouts/ROE filters, auto-excludes ST/new listings/illiquid/risky stocks | 30 seconds to screen 3000 stocks for qualified setups, no manual work |
| 📝 **Daily Market Review** | Indices performance/sector rankings/northbound flows/limit up-down counts/watchlist performance/upcoming unlocks/earnings | One command after close, 10 seconds to get full market picture, no need to scroll financial apps for 30 minutes |
| 📈 **Deep Stock Analysis** | Quotes/technicals/fund flows/fundamentals/valuation/events/research/chip distribution, one JSON output | Stop stitching data from 5 different sources, get all dimensions in one report |
| 🔔 **Signal Alerts** | Price/MACD cross/breakdown alerts, push to ServerChan/WeCom/DingTalk, background auto-monitoring | No need to stare at screens all day, get notified when price hits your levels |
| 💼 **Portfolio Tracker** | Plain text trade logging, auto-calculates P&L/cost basis/position sizing/win rate/profit factor | No more messy spreadsheets, open and see your P&L instantly with real fee calculations |
| 💰 **Flow Analysis** | Main fund flows/chip distribution/dragon-tiger list/block trades/northbound holdings | See where money is moving, not just price action |
| 📰 **Sentiment Monitoring** | News sentiment scoring (-10 to +10)/hot rankings/concept trends | Catch sentiment shifts before they show up in price |
| 🌍 **Market Context** | Global indices/FX/commodities/risk appetite | See the forest, not just the trees — judge macro first |

---

## 🔒 Backtest Discipline: Tradable Standards
**This is what separates this package from 99% of backtest code on the internet.**

We enforce these rules in code, not just in README:

✅ **Real Trading Costs**: Commission 0.025% + stamp duty 0.1% + transfer fee 0.001% + slippage 0.1% — returns after all fees are real returns  
✅ **Zero Lookahead Bias**: All signals use t-1 close, executed T+1 at open, no future price cheating allowed  
✅ **Real Trading Rules**: Can't buy at limit up, can't sell at limit down, suspended days skipped, ST/new/illiquid stocks auto-filtered  
✅ **No Guessing**: Warmup period min 120 bars, empty positions when data insufficient, no forced results  
✅ **Explicit Failures**: Data gaps trigger clear warnings showing coverage M<N, never fake data to fill curves  
✅ **100% Reproducible**: Same input always gives same output, no random black boxes, audit all you want

> The first rule of backtesting: **Stop lying to yourself first, then worry about making money.**

---

## 🚀 Quick Start: Copy Paste and Run

### 1. Install Dependencies (1 minute)
```bash
pip install -r requirements.txt
# Only 4 core dependencies: pandas / numpy / akshare / requests, no bloat
```

### 2. Zero Configuration Out of the Box
**No tokens, no registration, no API keys required**:
- All data from free public APIs, no permissions needed
- Automatic local caching, second runs are 10x faster, works offline
- Optional Tushare token for multi-source fallback, completely unnecessary for core features

### 3. First Command Gets Results
```bash
# 1. Run full sector backtests, generates interactive HTML dashboard with equity curves/drawdowns/trades
python scripts/workspace/sector_strategy.py --all

# 2. How was the market today? Generate full review report
python scripts/workspace/daily_review.py

# 3. Which stocks have bullish MA alignment right now?
python scripts/workspace/stock_screener.py --ma-long --top 20

# 4. Should I buy Kweichow Moutai at current price?
python scripts/run_analysis.py 600519
```

All results generate as local files, open and view immediately, zero code needed.

---

## 📊 Empirical Performance: Beats Benchmarks
All backtest results **after all trading costs**, no inflation:

### Gaming Sector 2021-2026 (Full Bull/Bear Cycle)
| Strategy | Total Return | Excess Return | Max Drawdown |
|----------|--------------|---------------|--------------|
| Filtered Equal-Weight (200MA Trend) | **105.84%** | **+33.01%** | -38.2% |
| Pure Buy & Hold | 72.83% | Benchmark | -58.1% |

> 200MA filter cut max drawdown from 58% to 38% in the 2022 bear market, avoided 20% losses, kept up in bulls, significant alpha long-term.

Validated sectors: Gaming/Semiconductors/New Energy/Healthcare, all outperform buy-and-hold benchmark.

---

## 🤔 Why We're Different From Other Backtesters

| Feature | finance-expert-pack | 99% of Backtest Tools |
|---------|---------------------|----------------------|
| Trading Costs | Full A-share fee model, results directly comparable to live trading | Either no costs or 0.1% flat fee, returns inflated 30%+ |
| Trading Rules | Limit up/down locks, suspensions skipped, fully simulates live trading | Assumes unlimited liquidity at any price, results impossible to achieve live |
| Lookahead Bias | Hard-coded prevention, all signals T-1 determined T+1 executed | Hidden lookahead everywhere, you won't find it until you trade live |
| Stock Filtering | Auto-excludes ST/new/illiquid/risky stocks, picks are tradeable | Includes everything, backtest picks stocks you'd never actually buy |
| Token Requirement | Zero tokens, zero registration, run immediately after install | Forces registration for API keys, core features paywalled |
| Trustworthiness | 100% reproducible, fully open source, audit anything | Black box calculations, you have no idea how results are generated |

---

## ⚠️ Real Limitations (No BS)
We don't do "50% annual return" marketing nonsense, limitations laid out clearly:

1. **Survivorship bias**: Constituents taken as of current date, historical delistings/renames not accounted for, extrapolate carefully
2. **Capital flow dimension limited**: Eastmoney API blocked, T3 quality mode is pure fundamental cross-section
3. **Data source stability**: Public sources change with website redesigns, retries implemented but 100% coverage not guaranteed
4. **A-share focused**: HK/US code paths exist but not validated to the same out-of-sample standard

---

## 📏 Seven Iron Rules
All output strictly follows these principles, no exceptions:

1. **No fabricated numbers**: All data from real sources, if we don't have it we say "not fetched"
2. **Layered statements**: Distinguish "fact / inference / guess", label uncertainty explicitly
3. **No hype language**: No "must rise / perfect entry / guaranteed profit", always base/bull/bear scenarios + triggers + invalidation levels
4. **Contradictions shown**: Bullish and bearish signals both presented, no smoothing over disagreements
5. **Sources cited**: Every data point has an origin you can verify
6. **Reproducible**: Same input always gives same output, no random black boxes
7. **For research only**: All content is reference, not investment advice

---

## 📜 Disclaimer
> ⚠️ All content compiled from public information for research and educational purposes only. Does not constitute investment advice or specific stock recommendations. Investing carries risk; trade carefully. Backtest results are historical simulations and do not represent future returns.

---

## License
MIT License, use freely, just give attribution.

---

<div align="center">

### If this package saved you time and avoided losses, give it a Star ⭐
### It's the best support for open source maintainers

[🔼 Back to top](#)

</div>
