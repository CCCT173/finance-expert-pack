# 统一数据源清单

> 整合自三个 skill 仓库的所有数据获取来源：
> - **FlyPig23/stock-analysis-library**（stock-deep-analyzer / capital-rotation-stock-analysis / serenity-stock-research / us-political-stock-signal-analysis / ai-supply-chain-bottleneck-hunter）
> - **HzahcyK/stock-fund-radar**
> - **mingli30119/stock-analysis**（stock-analysis-enhanced）

---

## 一、数据源分级规则

| 优先级 | 含义 | 说明 |
|--------|------|------|
| A 主源 | 官方 API / akshare 主接口 | 最稳定 |
| B 备源 | akshare 备用接口 或 直连 HTTP | 东财/新浪/腾讯 |
| C 兜底 | Web search + AI 解析 | 最后防线 |
| D 缺失 | 标记"数据缺失"，不渲染 | 禁止编造 |

---

## 二、按数据类型分类

### 1. 股票基础信息（名称/行业/市值/PE/PB/价格）

| 字段 | A 主源 | B 备源 | C 兜底 |
|------|--------|--------|--------|
| 股票简称 | `akshare.stock_individual_basic_info_xq(symbol)` | `akshare.stock_info_a_code_name()` | web search |
| 行业 | `stock_individual_basic_info_xq` -> `affiliate_industry` | `stock_board_industry_cons_em` 反查 | 同花顺 F10 |
| 市值 | `stock_individual_spot_xq` -> `总市值` | `stock_individual_info_em` -> `总市值` | 东财 push2 JSON |
| 最新价 | `stock_individual_spot_xq` -> `现价` | 东财 `push2.eastmoney.com/api/qt/stock/get` | 腾讯 `qt.gtimg.cn` |
| 涨跌幅 | `stock_individual_spot_xq` -> `涨幅` | 同上 | 同上 |
| PE(TTM) | `stock_individual_spot_xq` -> `市盈率(TTM)` | `stock_a_indicator_lg` | 百度股市通 `stock_zh_valuation_baidu` |
| PB | `stock_individual_spot_xq` -> `市净率` | `stock_a_indicator_lg` | 百度股市通 |
| 港股基础 | `stock_individual_basic_info_hk_xq` + `stock_hk_company_profile_em` + `stock_hk_security_profile_em` | `stock_hk_spot_em` | 腾讯港股 `qt.gtimg.cn/q=hk{code}` |
| 美股基础 | `yfinance.Ticker(code).info` | `stock_us_hist` | Yahoo Chart v8 HTTP |

### 2. K 线行情

**A股 6 路 fallback 链：**

| 优先级 | 数据源 | 接口 |
|--------|--------|------|
| 1 | akshare 东财 | `akshare.stock_zh_a_hist(symbol, period='daily', adjust='qfq')` |
| 2 | akshare 新浪 | `akshare.stock_zh_a_daily(symbol, start_date, adjust='qfq')` |
| 3 | BaoStock | `baostock.query_history_k_data_plus(bs_code, fields, start_date, frequency='d')` |
| 4 | 东财直连 HTTP | `push2his.eastmoney.com/api/qt/stock/kline/get` |
| 5 | 新浪直连 HTTP | `money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData` |
| 6 | 腾讯直连 HTTP | `web.ifzq.gtimg.cn/appstock/app/fqkline/get` |
| 7 | tushare / efinance | providers chain（需 TOKEN） |

**港股 K 线 fallback：**

| 优先级 | 数据源 | 接口 |
|--------|--------|------|
| 1 | akshare 东财 | `akshare.stock_hk_hist(symbol, period, adjust)` |
| 2 | akshare 新浪 | `akshare.stock_hk_daily(symbol, adjust)` |
| 3 | yfinance | `yfinance.Ticker(code).history(start, interval='1d')` |
| 4 | Yahoo Chart v8 HTTP | `query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d` |

**美股 K 线 fallback：**

| 优先级 | 数据源 | 接口 |
|--------|--------|------|
| 1 | yfinance | `yfinance.Ticker(code).history(period='2y')` |
| 2 | akshare | `akshare.stock_us_hist(symbol, period='daily')` |
| 3 | Yahoo Chart v8 HTTP | 同上 |
| 4 | Stooq HTTP | `stooq.com/q/d/l/?s={code}.us&i=d` |

### 3. 财报数据

| 字段 | A 主源 | 备注 |
|------|--------|------|
| 5年ROE | `stock_financial_analysis_indicator(symbol)` -> `加权净资产收益率(%)` | 取最近5年年末值 |
| 5年营收 | `stock_financial_abstract(symbol)` -> `营业总收入` | 单位换算到亿 |
| 5年净利 | `stock_financial_abstract` -> `归属母公司所有者的净利润` | 同上 |
| 流动比率/资产负债率 | `stock_financial_analysis_indicator` | |
| 现金流 | `stock_cash_flow_sheet_by_report_em` | |
| 三大报表 | `stock_financial_report_sina(stock, symbol='资产负债表/利润表/现金流量表')` | |
| 同花顺指标 | `stock_financial_abstract_ths(symbol, indicator='按报告期')` | |
| 港股财报 | `stock_hk_financial_abstract` | |
| 美股财报 | `yfinance.Ticker.financials` + `.balance_sheet` + `.cashflow` | |

### 4. 资金面

| 字段 | A 主源 |
|------|--------|
| 北向资金 | `stock_hsgt_individual_em(stock=code)` tail 20 |
| 融资融券(沪) | `stock_margin_detail_sse(date)` filter by code |
| 融资融券(深) | `stock_margin_detail_szse(date)` filter by code |
| 股东户数 | `stock_zh_a_gdhs(symbol=code)` |
| 主力资金 | `stock_individual_fund_flow(stock, market)` |
| 大宗交易 | `stock_dzjy_mrtj(start_date, end_date)` filter |
| 限售解禁 | `stock_restricted_release_queue_sina(symbol)` / `stock_restricted_release_detail_em(start, end)` |
| 机构持仓 | `stock_report_fund_hold_detail(symbol, date)` 近8季聚合 |
| 基金持仓 | 同上，type 过滤"公募/QFII/社保" |

### 5. 龙虎榜

| 字段 | A 主源 |
|------|--------|
| 上榜日期 | `stock_lhb_stock_detail_date_em(symbol=code)` |
| 席位明细 | `stock_lhb_stock_detail_em(symbol=code, date=YYYYMMDD)` |
| 游资识别 | `lib/seat_db::match_seats_in_lhb()` |
| 板块龙虎 | `stock_lhb_stock_statistic_em(symbol='近一月')` |
| 全市场龙虎 | `stock_lhb_detail_em(start_date, end_date)` |

### 6. 研报与评级

| 字段 | A 主源 |
|------|--------|
| 研报列表 | `stock_research_report_em(symbol)` |
| 机构评级 | `stock_institute_recommend(symbol='股票综合评级')` |

### 7. 估值

| 字段 | A 主源 |
|------|--------|
| PE/PB历史 | `stock_a_indicator_lg(symbol)` |
| 行业PE均值 | `stock_board_industry_cons_em(industry)` 的 `市盈率-动态` 均值 |
| DCF | 自算 `simple_dcf(fcf, growth, wacc)` |
| 百度估值 | `stock_zh_valuation_baidu(symbol, indicator, period)` |
| 港股估值排名 | `stock_hk_valuation_comparison_em(symbol)` / `stock_hk_growth_comparison_em` / `stock_hk_scale_comparison_em` |

### 8. 同行对比

| 字段 | A 主源 |
|------|--------|
| 行业成分 | `stock_board_industry_cons_em(industry_name)` |
| 概念板块 | `stock_board_concept_name_em()` / `stock_board_concept_cons_em(concept)` |
| 相似股 | 同行业 + 概念板块交集 + 60日收益率 pearson 相关 > 0.8 |

### 9. 上下游 / 主营构成

| 字段 | A 主源 |
|------|--------|
| 主营构成 | `stock_zygc_em(symbol)` -> `分产品/分地区` |
| 客户集中度 | cninfo 年报附注 "前五大客户" |
| 供应商集中度 | cninfo 年报附注 "前五大供应商" |

### 10. 治理

| 字段 | A 主源 |
|------|--------|
| 质押 | `stock_gpzy_pledge_ratio_em()` filter |
| 增减持 | `stock_ggcg_em(symbol='近一年')` |
| ST/违规 | `stock_zh_a_st_em()` |
| 高管持股(沪) | `stock_share_hold_change_sse(symbol)` |
| 高管持股(深) | `stock_share_hold_change_szse(symbol)` |

### 11. 事件 / 新闻 / 公告

| 字段 | A 主源 |
|------|--------|
| 个股新闻 | `stock_news_em(symbol)` |
| 财联社电报 | `stock_telegraph_cls` |
| 公告 | `stock_notice_report(symbol, date)` |
| 业绩预告 | `stock_yjyg_em(date)` filter by code |
| 业绩快报 | `stock_yjkb_em(date)` filter by code |
| 东财公告JSON | `np-anotice-stock.eastmoney.com/api/security/ann` |
| 港股公告 | `www1.hkexnews.hk/search/titlesearch.xhtml` |

### 12. 舆情 / 热度

| 字段 | A 主源 |
|------|--------|
| 雪球热度 | `stock_hot_rank_detail_em(symbol)` |
| 股吧 | `guba.eastmoney.com/list,{code}.html` |

### 13. 分红 / 股本

| 字段 | A 主源 |
|------|--------|
| 历史分红 | `stock_history_dividend_detail(symbol, indicator='分红')` |
| 历史送转 | `stock_history_dividend_detail(symbol, indicator='配股')` |
| 股本结构 | `stock_zh_a_gbjg_em(symbol)` |
| 十大股东 | `stock_gdfx_top_10_em(symbol, date)` |
| 十大流通股东 | `stock_gdfx_free_top_10_em(symbol, date)` |
| 股东户数变动 | `stock_zh_a_gdhs_detail_em(symbol)` |

### 14. 基金数据

| 字段 | A 主源 |
|------|--------|
| 基金持仓明细 | `stock_report_fund_hold_detail(symbol, date)` |
| 基金经理 | `fund_em_manager_thsi(fund_code)` / `fund_manager_em()` |
| 基金净值 | `fund_open_fund_info_em(symbol=fund_code, indicator='累计净值走势')` |
| 基金评级 | `fund_em_rating` / `fund_em_rank_detail` |
| 基金详情 | `fund.eastmoney.com/{fund_code}.html` |

---

## 三、HTTP 直连数据源（无需 akshare）

### Tier 1 - HTTP 主源

| ID | 名称 | URL | 市场 | 覆盖维度 | 健康度 |
|----|------|-----|------|----------|--------|
| em_push2 | 东方财富 push2 | `push2.eastmoney.com/api/qt/stock/get` | A/H/U | 基础/K线/估值/资金 | 常被拦截 |
| em_quote | 东方财富 quote | `quote.eastmoney.com/` | A/H/U | 基础/K线 | 稳定 |
| em_data | 东方财富 data | `data.eastmoney.com/` | A | 同行/行业/治理/资金/龙虎/事件/研报 | 稳定 |
| xq_api | 雪球 akshare | `stock.xueqiu.com/` | A/H | 基础/财报/K线/事件/舆情 | 稳定 |
| tencent_qt | 腾讯行情 | `qt.gtimg.cn/` | A/H/U | 基础/K线 | 稳定 |
| sina_quote | 新浪财经 | `finance.sina.com.cn/` | A/H/U | 基础/K线/事件 | 不稳定 |
| cninfo | 巨潮资讯 | `cninfo.com.cn/` | A | 事件/行业/财报 | 稳定 |
| hkexnews | 港交所披露易 | `hkexnews.hk/` | H | 事件/治理 | 稳定 |
| aastocks | AASTOCKS | `aastocks.com/` | H | 基础/同行/资金/事件 | 不稳定 |
| cls | 财联社 | `cls.cn/` | A/H/U | 事件/宏观 | 稳定 |
| yicai | 第一财经 | `yicai.com/` | A/H | 事件/宏观/行业 | 稳定 |
| wallstreetcn | 华尔街见闻 | `wallstreetcn.com/` | A/H/U | 宏观/舆情 | 不稳定 |
| cfi | 中财网 | `cfi.cn/` | A | 基础/财报/事件 | 稳定 |
| hexun | 和讯网 | `stock.hexun.com/` | A | 研报/事件 | 稳定 |
| 163money | 网易财经 | `money.163.com/` | A/U | 基础/事件 | 稳定 |
| jrj | 金融界 | `stock.jrj.com.cn/` | A | 事件/行业 | 稳定 |
| investing | Investing.com | `investing.com/` | U | 宏观/期货 | 稳定 |
| mx_api | 东方财富妙想 | `mkapi2.dfcfs.com/finskillshub/` | A/H/U | 基础/财报/事件 | 稳定(需Key) |
| baostock | BaoStock | `baostock.com/` | A | K线 | 稳定 |
| yfinance | Yahoo Finance | `finance.yahoo.com/` | U/H | 基础/财报/K线 | 稳定 |
| yahoo_chart_v8 | Yahoo Chart v8 | `query1.finance.yahoo.com/v8/finance/chart/` | U/H | K线 | 稳定 |
| tencent_hk_quote | 腾讯港股 | `qt.gtimg.cn/q=hk{code}` | H | 基础 | 稳定 |
| jin10_flash | 金十数据 | `jin10.com/flash_newest.js` | A/H/U | 宏观/政策/事件/舆情 | 稳定 |
| em_kuaixun | 东财快讯 | `newsapi.eastmoney.com/kuaixun/v1/getlist_102_ajaxResult_50_1_.html` | A/H/U | 事件/舆情 | 稳定 |
| em_stock_ann | 东财公告 | `np-anotice-stock.eastmoney.com/api/security/ann` | A | 事件 | 稳定 |
| qh99_inventory | 99期货网 | `99qh.com/` | A | 原材料/期货 | 稳定 |
| ths_news_today | 同花顺快讯 | `news.10jqka.com.cn/today_list/` | A/H | 事件/舆情 | 稳定 |

### 加密货币源（宏观情绪参考）

| ID | 名称 | URL | 备注 |
|----|------|-----|------|
| coingecko_simple | CoinGecko Simple Price | `api.coingecko.com/api/v3/simple/price` | BTC/ETH 实时价 |
| coingecko_markets | CoinGecko Markets | `api.coingecko.com/api/v3/coins/markets` | Top 100 行情 |
| okx_spot | OKX 现货 | `okx.com/api/v5/market/tickers?instType=SPOT` | 国内可访问 |
| kucoin_stats | KuCoin 24h | `api.kucoin.com/api/v1/market/stats` | 备用 |
| kraken_trades | Kraken 成交 | `api.kraken.com/0/public/Trades` | 合规美金所 |
| gemini_ticker | Gemini 行情 | `api.gemini.com/v2/ticker/btcusd` | 合规美金所 |
| coinlore_tickers | CoinLore 全量 | `api.coinlore.net/api/tickers/` | 无分页限制 |
| geckoterminal | GeckoTerminal DEX | `api.geckoterminal.com/api/v2/networks` | 链上资金流 |

### Tier 2 - Playwright / 浏览器源

| ID | 名称 | URL | 市场 | 覆盖维度 |
|----|------|-----|------|----------|
| iwencai | 问财 | `iwencai.com/` | A | 同行/产业链/行业 |
| ths_f10 | 同花顺 F10 | `stockpage.10jqka.com.cn/` | A/H | 基础/同行/产业链/治理/护城河 |
| xueqiu_f10 | 雪球 F10 | `xueqiu.com/` | A/H/U | 治理/事件/舆情 |
| legulegu | 乐咕乐股 | `legulegu.com/` | A | 估值/行业 |
| stockstar | 证券之星 | `stock.stockstar.com/` | A | 研报/事件 |
| futu | 富途牛牛 | `futunn.com/` | H/U | 基础/财报/舆情 |
| yuncaijing | 云财经 | `yuncaijing.com/` | A | 龙虎榜 |
| guba_em_list | 东财股吧 | `guba.eastmoney.com/list,{code}.html` | A/H | 舆情/杀猪盘/比赛 |
| jisilu | 集思录 | `jisilu.cn/` | A | 舆情/可转债 |
| fx678 | 汇通财经 | `fx678.com/` | A/U | 宏观/原材料/期货 |
| cmc | CompaniesMarketCap | `companiesmarketcap.com/` | H/U | 市值/估值 |

### Tier 3 - 官方披露源

| ID | 名称 | URL | 覆盖维度 |
|----|------|-----|----------|
| sse | 上交所 | `sse.com.cn/` | 事件/治理 |
| szse | 深交所 | `szse.cn/` | 事件/治理 |
| csrc | 证监会 | `csrc.gov.cn/` | 政策 |
| gov_cn | 国务院 | `gov.cn/zhengce/` | 政策/宏观 |
| miit | 工信部 | `miit.gov.cn/` | 政策/行业 |
| ndrc | 发改委 | `ndrc.gov.cn/` | 政策/宏观 |
| samr | 市场监管总局 | `samr.gov.cn/` | 政策 |
| shfe | 上期所 | `shfe.com.cn/` | 原材料/期货 |
| dce | 大商所 | `dce.com.cn/` | 原材料/期货 |
| czce | 郑商所 | `czce.com.cn/` | 原材料/期货 |
| ine | 能源中心 | `ine.cn/` | 原材料/期货 |
| 100ppi | 生意社 | `100ppi.com/` | 现货价格 |
| cnstock | 中国证券网 | `cnstock.com/` | 事件/研报/舆情/政策 |
| cs_cn | 中证网 | `cs.com.cn/` | 事件/政策/舆情 |
| stcn | 证券时报 | `stcn.com/` | 事件/舆情/政策 |
| nbd | 每经网 | `nbd.com.cn/` | 事件/舆情/杀猪盘/护城河 |
| pbc | 央行 | `pbc.gov.cn/` | 宏观/政策 |
| safe | 外管局 | `safe.gov.cn/` | 宏观/政策 |
| stats_gov | 国家统计局 | `stats.gov.cn/` | 宏观/行业 |
| chinamoney | 中国货币网 | `chinamoney.com.cn/` | 宏观/资金 |
| chinabond | 中国债券网 | `yield.chinabond.com.cn/` | 宏观/估值(WACC锚) |
| cfachina | 期货业协会 | `cfachina.org/` | 期货/政策 |

---

## 四、美国政治交易信号专用源

### 国会交易

| 来源 | URL | 用途 |
|------|-----|------|
| Capitol Trades | `capitoltrades.com` | 快速 ticker/member 搜索、近期申报 |
| Quiver Quant | `quiverquant.com/congresstrading` | ticker/议员级别聚合 |
| Unusual Whales | `unusualwhales.com/politics` | 委员会/情境仪表盘、异常集群检测 |
| House Clerk PTR | 众议院书记官公开披露 PDF | 一手源 |
| Senate eFD | 参议院电子财务披露 | 一手源 |

### 行政分支

| 来源 | URL | 用途 |
|------|-----|------|
| Open Cabinet | `open-cabinet.org` | 行政官员 OGE Form 278-T 交易报告 |
| TrumpTrades | `trumpstrades.com` | Trump OGE 披露可视化 |
| Trump Tracker | `trumptracker.org` | Trump 政府仪表盘、最新交易、持仓 |
| OGE 公开披露 | 美国政府道德办公室 | 一手源 |

### 验证注意事项

- 公开披露有延迟；交易日期不等于申报日期
- 金额通常是范围而非精确值
- 部分记录为家庭账户/信托/RSU/合规性出售
- ETF/基金/债券记录不应描述为普通股买入
- 不暗示违法；使用"潜在利益冲突"/"角色-行业重叠"/"政策信息优势"

---

## 五、stock-fund-radar 每日快照数据清单

### 必须采集的数据组

| 数据组 | 内容 | 首选源 |
|--------|------|--------|
| 地缘/事件风险 | 冲突/制裁/贸易/外交/峰会/央行/行业大会 | 官方政府/外交部/白宫/欧盟/NATO/UN/OPEC/Fed/ECB |
| 海外市场 | 标普/纳指/道指/罗素2000/美10Y/美元指数/USD-CNH/金/铜/油/VIX/亚股 | 交易所数据 > 市场数据终端 |
| A股盘面 | 上证/沪深300/创业板/科创50/A50/成交额/涨跌比/涨停跌停/北向南向 | 交易所数据 |
| 主力资金 | 板块/概念主力/大单/ETF份额/活跃基金线索/大宗 | 东财 data 子域 |
| 技术面 | 日/周K线/MA5/10/20/60/成交量/MACD/KDJ/RSI/支撑阻力/相对强度 | 交易所数据 |
| ETF技术 | 日/盘中K线/换手/溢价折价/量变/是否确认板块走势 | 交易所数据 |
| 政策/宏观 | 最新政策/央行操作/财政/地产/消费/科技支持/宏观日历 | 国务院/PBOC/CSRC/NDRC |
| 财报/估值 | 最新季报/年报/营收利润趋势/毛利率/现金流/库存/订单/估值/拥挤 | 交易所披露/公司年报 |
| 日历 | 财报/分红/指数再平衡/央行会议/行业会议/产品发布/商品库存 | 交易所/行业日历 |

### 新鲜度规则

- 盘中决策需要盘中数据（有条件时）
- 重大地缘/政策/峰会事件应刷新，即使行情数据刚拉过
- 同会话内数据仍新鲜时可复用，仅在用户要求/市场显著变动/时间戳过时时刷新
- 数据点跨站不一致时，说明用了哪个以及原因
- 数据类别不可用时标记"未取到"，不猜测
- 基金用最新披露持仓和最新可用业绩数据，不暗示持仓是实时的

---

## 六、缓存 TTL 规则

| 数据类型 | TTL | 举例 |
|----------|-----|------|
| 实时行情 | 60s | 价格、涨跌幅、市值 |
| 盘中数据 | 5min | K线、筹码分布、主力资金、雪球热度 |
| 小时级 | 1h | 个股新闻 |
| 日度聚合 | 2h | 龙虎榜、北向、融资融券 |
| 季度低频 | 24h | 财报、研报、历史估值、机构持仓、分红 |
| 几乎不变 | 7d | 行业分类、股票简称 |

强刷：`STOCK_NO_CACHE=1` 环境变量绕过全部缓存。

---

## 七、数据质量约定

1. **每条数据必须带 source 字段**：告诉前端这条数据来自哪个接口
2. **fallback=True 标记**：用 web search 兜底时必须标记
3. **缺失不编造**：找不到数据时字段置 null，viz 自动跳过
4. **akshare 版本锁定**：`akshare>=1.14.0`
5. **接口失败重试 3 次后才走 fallback 链**

---

## 八、已知问题

- `stock_report_fund_hold_detail` 返回格式不稳定，不同季度字段名可能变化
- cninfo 年报附注（客户/供应商集中度）没有结构化 API，只能 PDF 解析，暂时依赖 web search
- 港股/美股的基金持仓数据源比 A 股弱
- 雪球 cookie 6 小时过期，无刷新机制
- 淘股吧对爬虫有 WAF，高频访问会被封，建议单次查询 + 缓存 24h
- 东财 push2 在 2026 常被反爬拦截，建议走 MX API 或雪球 akshare 代抓
- 新浪 hq.sinajs.cn 老接口 2026 返 403
