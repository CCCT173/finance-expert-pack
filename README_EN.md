# finance-expert-pack · A-Share Quant Toolkit

<div align="center">

**Open-source, free A-share quantitative toolkit for individual investors | Zero config | No API tokens | Live-tested strategies**

[👉 One-click install for AI Agents (SkillHub)](https://www.skillhub.cn/skills/finance-expert-pack) | [👉 GitHub Source Code](https://github.com/CCCT173/finance-expert-pack)

---

</div>

## 🎯 Two ways to use, beginners choose the first one

### Option 1: Install as a Skill for your AI assistant (Recommended, no commands needed)
Install directly from [SkillHub](https://www.skillhub.cn/skills/finance-expert-pack) to your WorkBuddy/CodeBuddy/OpenClaw or any Skill-compatible AI assistant. **No need to memorize commands, no need to read code — just tell your AI what you want in plain English**, for example:
- "Run a backtest for the 200MA strategy on the semiconductor sector over the past 3 years"
- "Generate today's market review report, my watchlist is Kweichow Moutai, CATL, Sanqi Interactive"
- "Screen stocks with recent MACD golden cross and ROE above 15%"
- "Show me the current valuation and support/resistance levels for Kweichow Moutai"
- "How has the dual-low convertible bond strategy performed recently? Run a backtest for me"

The AI will automatically call the tools and give you results directly, you don't need to care about the underlying implementation at all.

### Option 2: Run Python scripts directly (for developers)
All data comes from free public APIs (akshare/baostock), no account registration, no paid tokens, no membership required, install dependencies and run directly:
```bash
pip install -r requirements.txt
python scripts/workspace/sector_strategy.py --all
```

---

## Preface

### Why free and open source?

People often ask me why I don't sell this toolkit since it works in live trading. Truth be told:
- I have a full-time job that pays well enough, I don't need to make money from this
- When I first started investing, I stepped on so many pitfalls: paid thousands for useless trading software, joined paid signal groups, got scammed by so-called "gurus" — I know how hard it is for retail investors in this market
- I wrote these scripts for my own daily use anyway, open sourcing them costs me nothing, and if they help other people navigating the same mess, that's worth more than charging membership fees
- Open source means more people can find bugs, suggest improvements, and make the strategies better — better than me working on it alone

**Promise: This project will stay free and open source forever. No paywalls, no ads, no paid signal groups to scalp you. Use it freely.**

---

Let me be clear upfront: this is not some "AI trading holy grail", and there are no "3x per year" guaranteed strategies — we all know what those things are worth.

This toolkit is essentially a collection of scripts that automates the manual work I do every day: market reviews, stock screening, backtesting, monitoring, research report scraping, etc. It saves me from jumping between Eastmoney, Tonghuashun and other websites all day long.

I use the 200MA filter strategy in my own live trading. From 2021 to now (5.5 years), it has returned about 12% annualized with 28% max drawdown, outperforming buy-and-hold sector ETFs by over 20% in bear markets. The best part is it trades very infrequently, only 1-2 times per year, so you don't need to stare at the screen all day — perfect for people with full-time jobs.

**This toolkit is for you if:**
- You want to backtest strategies but don't want to deal with complex platforms like JoinQuant or RiceQuant
- You regularly monitor the market, do reviews, look up data, or find research reports, and are tired of switching between dozens of websites
- You're sick of pop-up ads and VIP membership upsells in trading apps
- It's even better if you know some Python, but if you don't, just install it as a Skill and use natural language

**This might not be for you if:**
- You're looking for "sure win picks" or "guaranteed profits" (there are none here, no shortcuts in investing)
- You do high-frequency trading or institutional-grade quant (this is built for retail investors, it won't meet professional performance requirements)

---

## Core Features (ordered by usage frequency)

### 1. 200MA Filter Sector Strategy (most mature, live-tested by me)

The logic is extremely simple, no secrets:
- Equal-weight 10 leading stocks in the sector
- Go fully long when the sector ETF closes above its 200-day moving average
- Sell everything and hold cash when it breaks below the 200MA
- Rebalance back to equal weight once per year

This "dumb" approach works surprisingly well in trending markets. Across 3 sectors over 5.5 years (2021.1 to 2026.7), average performance:
- 12.7% annualized return
- 28.3% max drawdown
- 34.3% excess return over buy-and-hold, 22% less loss during the 2022 bear market
- Only 1-2 trades per year, total fees under 0.5% annually, very low transaction costs

If you prefer lower volatility, use the quality mode: when in an uptrend, it selects the top 5 stocks by ROE, revenue growth, and profit growth for better fundamentals and lower volatility, higher Sharpe ratio — ideal for risk-averse investors.

### 2. Three Lazy Portfolios Tested Across Full Bull/Bear Cycles

These three have all been backtested across at least one full market cycle, require almost no maintenance, perfect for working people:

| Strategy | Suitable Capital | Historical Performance (2018-present) | Best For |
|----------|------------------|----------------------------------------|----------|
| Permanent Portfolio | ¥50k+ (~$7k) | 4-5% annualized, 6% max drawdown | Risk-averse investors who don't want volatility, just better than savings accounts |
| Lazy 3-Asset Portfolio | ¥10k-50k (~$1.4k-7k) | 4-5% annualized, 12% max drawdown | Total beginners who don't want to spend any time researching, set it and forget it |
| Dual-Low Convertible Bonds | ¥100k+ (~$14k) | 7-9% annualized, 15% max drawdown | Investors who want higher returns than fixed income and can handle modest volatility |

💡 Tip for new investors: Start with the Permanent Portfolio or Lazy 3-Asset to get comfortable, don't jump straight into stock picking.

There are also 6 basic strategy templates included: MA crossover, dual MA, RSI mean reversion, Bollinger Band breakout, MACD, Dual Thrust. The backtesting framework is correct, but they haven't been optimized for recent market conditions — feel free to tune parameters yourself if you want to experiment.

### 3. Why you can trust these backtest results

I've stepped on too many backtesting pitfalls when I started, and I know exactly what "backtests like a champ, live trades like a chump" means. These rules are hardcoded into the engine, you can't turn them off, specifically to avoid self-deception:
- ✅ **Zero look-ahead bias**: Signals are calculated on t-1 close, executed on t+1 open, no future data is ever used
- ✅ **Realistic transaction costs**: Commission 0.025%, stamp tax 0.1% (sell only), transfer fee 0.001%, plus 0.1% slippage — total 0.4% round-trip, almost exactly what you pay in live trading
- ✅ **Real trading rules**: Can't buy at limit up, can't sell at limit down, suspended stocks are skipped, strict T+1 enforcement — no impossible fills like "buying the entire position at the limit up price"
- ✅ **Junk stock filter**: ST/*ST stocks, IPOs less than 60 days old, stocks with average daily volume below ¥50M are automatically excluded, so you won't end up with illiquid positions you can't exit
- ✅ **Hold cash when data is insufficient**: The 200MA needs 120 trading days of data; if there isn't enough, hold cash instead of forcing a result
- ✅ **Fully reproducible**: Same inputs always produce the same outputs, no randomness, no black boxes — you'll get exactly the same results running it as I do

If you want to verify a strategy isn't overfit, use the Walk Forward Validation feature: it trains parameters on a rolling annual window and tests on the next year, which is the most reliable way to avoid curve-fitting.

### 4. One-click daily market review (I run this every day after close)

No need to spend half an hour browsing websites, the AI automatically generates a structured review report including:
- Three major index returns, advance/decline ratio, limit up/down counts, northbound capital flows — see how the market is doing at a glance
- Top 10 sectors by gain/loss, see today's hot themes
- Performance of your watchlist stocks and signal alerts, no need to check each one individually
- Upcoming unlocks and earnings reports for the next week, avoid landmines in advance

Just tell your AI "Generate today's market review, my watchlist is [your stocks]" and it does the rest automatically.

### 5. Stock screening (no more writing Tongdaxin formulas)

Looking for stocks with specific setups? No need to write complex formulas in Tongdaxin, just tell the AI what you want in plain language, for example:
- "Find the top 20 stocks with bullish MA alignment"
- "Screen for stocks with MACD golden cross and 3 consecutive years of ROE above 15%"
- "Find stocks breaking out to 60-day highs, exclude ST stocks and IPOs"

⚠️ Important reminder: Stocks from the screener are not buy recommendations. They're just a narrowed-down list — always do your own fundamental research. Tools save you screening time, they don't make decisions for you.

### 6. Signal alerts (monitor the market while at work)

No time to stare at the screen at work? Set up signals to push to your WeChat automatically, get notified only when something happens:
- Price alerts, e.g. "Let me know if Moutai drops below ¥1700"
- Technical signal alerts, e.g. "Notify me when Sanqi Interactive has a MACD golden cross"
- Batch monitoring for your entire watchlist, push on buy/sell signals
- Supports ServerChan, PushPlus, WeCom Work, DingTalk — same signal only pushes once every 24 hours, no spamming.

### 7. Portfolio tracking and paper trading (beginners should start here)

All data is stored locally on your computer, nothing is uploaded to any cloud, full privacy:
- Record trades, automatically calculate average cost, floating P&L, position weighting
- Track win rate, profit factor and other performance metrics, see if you can beat the strategy
- Paper trading works exactly like live trading rules — beginners should paper trade for 1-3 months before using real money to validate strategies.

### 8. Full-dimension stock analysis (stop jumping between websites)

Just say the stock name or ticker, the AI automatically pulls all the data you need, no more switching between F10, research sites, fund flow sites:
- Latest quotes, volume, turnover
- Common technical indicators: MA/MACD/RSI/KDJ/Bollinger Bands
- Main capital flows, northbound holdings, dragon-tiger list, block trades
- 5 years of financials, PE/PB historical percentiles, ROE/revenue/profit growth
- Recent announcements, dividends, lockup expirations, analyst ratings
- Support and resistance levels (MA20/MA60 + recent swing points)
- Bull/base/bear scenario action plans with trigger levels

⚠️ Important: This only provides objective data and scenario analysis, it will never say "this stock will definitely go up". You make the final decision, you bear the profits and losses.

### 9. Research report and announcement scraping (the ultimate research tool)

No need to search everywhere for research reports when studying a company, just tell the AI:
- "Find me all broker reports for Kweichow Moutai from the last 6 months, include target prices and ratings"
- "Download CATL's 2025 annual report and Q1 quarterly report"
- "Compare consensus expectations and disagreements across brokers on the gaming sector"

Supports batch scraping by stock, industry, or analyst, resume on interruption, export to PDF/Word/Excel/Markdown, auto categorized and archived, no manual downloading and organizing needed.

---

## Other useful tools

- **Real-time market monitor**: CLI real-time quotes, price changes, volume — no need to run memory-heavy trading apps, perfect for discreet monitoring at work
- **A-share heat rank**: Aggregates top 50 trending stocks from Wencai, Xueqiu, Eastmoney, quickly see what the market is talking about
- **Risk control check**: Automatically checks position risks: single position size too large, stop loss/profit hit, account drawdown too high — helps you keep discipline
- **Cost sensitivity test**: Automatically tests strategy performance with double/triple transaction costs, see how robust the strategy is in adverse conditions

---

## Things to know upfront (pitfalls I've already stepped on for you)

These are known limitations I'm telling you about in advance, so you know what to expect:

1. **Survivorship bias exists**: Sector backtests use current constituents, not including delisted stocks, so backtest returns are about 5-10% higher than live trading — this is a limitation of free public data, just discount results a bit.
2. **HK/US stock support is limited**: The APIs exist, but I mostly trade A-shares, so HK/US functionality hasn't been well tested, use with caution for non-A-share markets.
3. **Historical fund flow data is spotty**: Eastmoney APIs have rate limits, so very old main capital flow data might not pull successfully, recent data works fine.
4. **Slippage is higher for large accounts**: Default slippage is 0.1%; if your account is over ¥1M, actual slippage will be higher, so live returns will be somewhat lower than backtests.
5. **Data sources occasionally fail**: These are free APIs after all, if akshare changes their API or rate limits you, data pulls might fail — retries are built in, just try again later if it happens.
6. **Not all technical indicators are implemented**: I only implemented the 5 most used ones (MACD/KDJ/RSI/Bollinger/MA), the rest I don't use so I didn't build them.

---

## Frequently asked questions

**Q: Will you upload my trading data? Is my privacy safe?**
A: 100% no. All data is stored locally as JSON and CSV files on your own computer, there's no upload logic in the code anywhere — feel free to audit the code yourself, it's fully open source with no black boxes.

**Q: Is this free? Will you ever start charging?**
A: Completely free, MIT licensed, for personal and commercial use. I have a full-time job, I'm not going to make money off this.

**Q: Will the strategies stop working in the future?**
A: Of course they will. No strategy works forever. The 200MA is a trend following strategy, it gets whipsawed a lot in ranging markets, but since it trades so infrequently, losses are minimal when it does. I re-backtest all strategies every year, and if they break I'll update the code — Star the GitHub repo to get notified.

**Q: Can I modify the strategies myself? What if I break something?**
A: Absolutely. The code is straightforward, well commented, just edit `scripts/workspace/strategies.py` to add indicators or change logic, the backtest engine is already built for you. If you break something, just pull the code again to reset.

**Q: What if I find a bug? Or want to add a feature?**
A: Feel free to open an Issue on GitHub, I'll fix it when I can. This isn't my full-time job though, so I might be slow to respond during busy work weeks. If you add a useful feature yourself, PRs are welcome!

---

## CLI Reference (for developers who run scripts directly)

All common commands are listed here so you don't have to dig through code:

### Backtesting
```bash
# Full sector full period 200MA backtest, generates interactive dashboard
python scripts/workspace/sector_strategy.py --all

# Specific sector and time period
python scripts/workspace/sector_strategy.py --sector Gaming --period Bear2021-22

# Quality stock selection mode
python scripts/workspace/sector_strategy.py --mode quality --all

# List all built-in portfolio strategies
python scripts/workspace/custom_strategies.py list

# Run specific strategy (id: 1=Permanent Portfolio 2=Lazy 3-Asset 3=Dual-low CB)
python scripts/workspace/custom_strategies.py run --id 3

# Walk Forward validation to avoid overfitting
python scripts/workspace/walk_forward.py
```

### Screening & Monitoring
```bash
# Top 20 bullish MA alignment stocks
python scripts/workspace/stock_screener.py --ma-long --top 20

# MACD golden cross + ROE > 15%
python scripts/workspace/stock_screener.py --macd-golden --roe 15

# Top 30 stocks breaking 60-day highs
python scripts/workspace/stock_screener.py --breakout 60 --top 30

# Real-time quote monitor
python scripts/a-share-monitor/zhitu_monitor.py 600519 KweichowMoutai

# A-share heat rank TOP 50
python scripts/stock-heat-rank-py/main.py
```

### Reviews & Analysis
```bash
# Latest trading day review
python scripts/workspace/daily_review.py

# Specific date review
python scripts/workspace/daily_review.py --date 2026-07-18

# Review with watchlist
python scripts/workspace/daily_review.py --watchlist watchlist.txt

# Full dimension stock analysis
python scripts/run_analysis.py 600519
```

### Alerts
```bash
# Price drop alert (push to ServerChan WeChat)
python scripts/workspace/signal_alert.py --price 600519:1700:below --channel serverchan --key YOUR_SENDKEY

# MACD golden cross alert (push to WeCom)
python scripts/workspace/signal_alert.py --macd 600519 --channel wecom --webhook YOUR_WEBHOOK

# Background watchlist monitoring (push to DingTalk)
python scripts/workspace/signal_alert.py --watchlist watchlist.txt --interval 60 --channel dingtalk --webhook YOUR_WEBHOOK
```

### Portfolio & Trading
```bash
# Record buy
python scripts/workspace/portfolio_tracker.py buy 600519 KweichowMoutai 100 1700

# Record sell
python scripts/workspace/portfolio_tracker.py sell 600519 50 1900

# View positions
python scripts/workspace/portfolio_tracker.py status

# View performance
python scripts/workspace/portfolio_tracker.py performance

# Paper trading
python scripts/workspace/simulated_trading.py buy 002555 SanqiInteractive 100 18

# Risk control check
python scripts/workspace/risk_control.py check
```

### Unified CLI entry point (no need to remember script paths)
```bash
python scripts/fincli.py backtest    # Backtesting
python scripts/fincli.py screener    # Screening
python scripts/fincli.py review      # Market review
python scripts/fincli.py walkforward # Walk forward validation
```

---

## A few final words

Tools are just tools. Don't blindly trust any strategy, don't blindly trust anyone's code — including mine.

I built this originally just to save myself time, after using it for years I figured I'd open source it to help other people. If it helps you, that makes me happy.

Investing returns come from your own cognition — other people's strategies are just reference. You make your own decisions, you take your own profits and losses.

If you find it useful, a Star on GitHub is the best support you can give me.

---

## License

MIT licensed, use it however you want, just don't repackage it to sell and scam people.
