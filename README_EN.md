<div align="center">

# finance-expert-pack · A-Share Quantitative Trading Toolkit
Python-based A-share quant toolkit, backtests with real trading costs, zero configuration, no API tokens required, works out of the box.

---

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![Zero Lookahead](https://img.shields.io/badge/Backtest-No%20Future%20Functions-red.svg)](#backtest-discipline)
[![Real Costs](https://img.shields.io/badge/Costs-Real%20AShare%20Fees-orange.svg)](#cost-model)
[![No Tokens](https://img.shields.io/badge/Setup-Zero%20Config-green.svg)](#quick-start)

**[GitHub Source](https://github.com/CCCT173/finance-expert-pack)** | **[Install via SkillHub](https://skillhub.cn/skills/finance-expert-pack)**

Gaming sector 2021-2026 backtest: 200MA trend strategy returned 105.8% vs 72.8% buy-and-hold, +33% alpha after commissions, stamp duty and slippage.

</div>

---

## Why this exists
Every quant trader has run into these problems:
- Backtest code you find online either hides lookahead bias or ignores trading costs, shows 200% return but loses money live
- Installed 10 different finance plugins that return inconsistent data and trigger duplicate actions
- Data sources change every few months, scripts crash mid-run, old results become impossible to reproduce
- Every tool forces you to register for API keys before you can even test anything

This package fixes those issues. All code is open source, backtest rules are hard-coded so you can audit them, uses only public APIs, no registration required, runs immediately after installing dependencies.

---

## Features
No marketing fluff, just tools that work for live trading:

| Module | Description |
|--------|-------------|
| 📊 Sector Backtesting | Built-in 200MA filtered equal-weight strategy, calculates real commissions/stamp duty/slippage, auto-handles limit locks, suspended stocks and ST/new share filtering |
| 🔍 Stock Screener | Screens for bullish MA alignment, MACD golden cross, new highs, ROE thresholds, auto-excludes ST/new/illiquid stocks |
| 📝 Daily Market Review | One command generates index performance, sector rankings, northbound flows, limit up/down counts, watchlist performance, upcoming unlocks/earnings |
| 📈 Stock Analysis | Quotes, technicals, fund flows, fundamentals, valuation, events, research, chip distribution in one JSON output |
| 🔔 Signal Alerts | Price alerts, MACD crosses, breakdown notifications via ServerChan/WeCom/DingTalk, can run in background to monitor watchlists |
| 💼 Portfolio Tracker | Plain text trade logging, auto-calculates P&L, cost basis, position sizing, win rate, no spreadsheet needed |
| 💰 Flow Analysis | Main fund flows, chip distribution, dragon-tiger list, block trades, northbound holdings |
| 📰 Sentiment Monitoring | News sentiment scoring, trending topics, concept heat |

---

## Backtest Discipline
This is what separates this code from 99% of backtest scripts online, rules are enforced in code, not just in README:
- All signals calculated on t-1 close, executed at t+1 open, zero lookahead bias guaranteed
- Full cost model: 0.025% commission, 0.1% stamp duty on sells, 0.001% transfer fee, 0.1% slippage, matches live trading almost exactly
- Real trading rules: can't buy at limit up, can't sell at limit down, suspended days skipped, no assumption of unlimited liquidity
- Auto-excludes ST/*ST stocks, IPOs under 60 days old, stocks with average daily turnover under 50M CNY
- 120-day warmup period, empty positions when data insufficient, no forced results
- Explicit warnings on data gaps, never fills fake data to make curves look good
- 100% reproducible: same input always gives same output

---

## Quick Start
### 1. Install dependencies
```bash
pip install -r requirements.txt
# Only 4 core dependencies: pandas / numpy / akshare / requests, no bloat
```

### 2. Zero configuration
All data comes from free public APIs, no registration or API keys required. Optional Tushare token available as a fallback data source, completely unnecessary for core functionality.

### 3. First run examples
```bash
# Full sector backtests, generates interactive HTML dashboard with equity curves, drawdowns and trade logs
python scripts/workspace/sector_strategy.py --all

# Generate today's market review
python scripts/workspace/daily_review.py

# Screen for stocks with bullish MA alignment, top 20 results
python scripts/workspace/stock_screener.py --ma-long --top 20

# Individual stock analysis
python scripts/run_analysis.py 600519
```

---

## Strategy Details
Default strategy is 200MA filtered equal-weight: hold equal-weight sector constituents when sector index is above 200MA, move to cash when it drops below, buy back when it crosses back above.
- Simple rule, no overcomplicated factors
- Outperformed buy-and-hold across gaming, semiconductors, new energy and healthcare sectors 2021-2026
- Designed to reduce downside in bear markets, not outperform in bulls: cut max drawdown from 58% to 38% in 2022 bear market, avoided 20% loss
- Experimental quality mode available: in uptrends, selects top 5 stocks by ROE/revenue growth/profit growth rank-sum for lower volatility.

All backtest results are net of all trading costs, directly comparable to live trading performance.

---

## Limitations
No bullshit, just facts:
1. Backtest universe uses current constituents, survivorship bias exists, historical delistings/renames not processed, don't over-extrapolate results
2. Eastmoney blocked the daily fund flow API, so T3 quality mode currently only uses fundamental data, fund flow dimension is incomplete
3. Public data sources occasionally change interfaces or rate limit, retries and fallbacks implemented but 100% uptime not guaranteed
4. Focused on A-shares, HK/US code paths exist but not thoroughly validated
5. Slippage model is fixed at 0.1%, large orders will experience higher market impact not accounted for

---

## Seven Ground Rules
All output follows these principles, no exceptions:
1. Never fabricate data, explicitly mark missing values as "not available"
2. Clearly separate facts, inferences, and assumptions
3. Never use "guaranteed return", "sure win" language, always provide base/bull/bear scenarios with trigger conditions
4. Show both bullish and bearish signals, no cherry-picking
5. Cite all data sources so you can verify independently
6. Same input always produces same output, no random black boxes
7. All content is for research purposes only, not investment advice.

---

## License
MIT, use freely, just give attribution.

---

<div align="center">

If this saved you time, feel free to star the repo⭐. PRs and issues welcome.

</div>
