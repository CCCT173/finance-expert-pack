# 资金面 / 筹码 / 事件 / 研报 数据维度补齐（移植说明）

> 本文件记录 `scripts/workspace/stock_capital_data.py` 的来由、覆盖端点与防封规则。
> 移植自用户已安装的 `a-stock-data` (v3.2.2) 直连 HTTP 端点 + `stock-analyzer` 的支撑/压力价位模型，
> 用于补齐 finance-expert-pack 在「完美世界(002624)」实盘验证中暴露的空白维度：
> **资金流 / 融资融券 / 龙虎榜 / 大宗交易 / 股东户数 / 分红 / 限售解禁 / 研报 / 新闻 / 公告 / 概念板块 / 买卖价位**。

## 为什么直连 HTTP 而非 akshare

验证中发现原 `stock_enhanced.py` 的 `get_margin/get_lhb/get_fund_flow` 走 akshare 接口，在受限网络/代理环境下整块返回空（akshare 对上游域名有隐性依赖，失败极难排查）。`a-stock-data` 采用**直连东财/百度/巨潮 HTTP API**，零第三方数据封装依赖，URL/参数完全暴露，在本机 Anaconda 实测可用且更稳。

## 端点清单（均已实测可达性，失败时优雅降级为 error/note 字典）

| 维度 | 函数 | 数据源 | 端点/报告名 |
|------|------|--------|-------------|
| 资金流(120日) | `get_fund_flow_120d` | 东财 push2his | `api/qt/stock/fflow/daykline/get` |
| 资金流(分钟) | `get_fund_flow_minute` | 东财 push2 | `api/qt/stock/fflow/kline/get` |
| 融资融券 | `get_margin_trading` | 东财数据中心 | `RPTA_WEB_RZRQ_GGMX` |
| 龙虎榜 | `get_dragon_tiger` | 东财数据中心 | `RPT_DAILYBILLBOARD_DETAILSNEW` + 买卖席位明细 |
| 大宗交易 | `get_block_trade` | 东财数据中心 | `RPT_DATA_BLOCKTRADE` |
| 股东户数 | `get_holder_num_change` | 东财数据中心 | `RPT_HOLDERNUMLATEST` |
| 分红送转 | `get_dividend_history` | 东财数据中心 | `RPT_SHAREBONUS_DET` |
| 限售解禁 | `get_lockup_expiry` | 东财数据中心 | `RPT_LIFT_STAGE` |
| 研报 | `get_research_reports` | 东财 reportapi | `reportapi.eastmoney.com/report/list` |
| 个股新闻 | `get_stock_news` | 东财 search-api-web | `search-api-web.eastmoney.com/search/jsonp` |
| 全球资讯 | `get_global_news` | 东财 np-weblist | `np-weblist.eastmoney.com/comm/web/getFastNewsList` |
| 公告 | `get_announcements` | 巨潮 cninfo | `www.cninfo.com.cn/new/hisAnnouncement/query` |
| 概念板块 | `get_concept_blocks` | 百度股市通 | `finance.pae.baidu.com/api/getrelatedblock` |
| 原始K线 | `get_raw_klines` | 东财 push2his | `api/qt/stock/kline/get` |
| 估值 | `forward_pe` / `pe_digestion` / `calc_peg` | 计算 | 同 a-stock-data 公式 |
| 支撑压力 | `support_resistance` / `get_price_targets` | 计算 | MA20/60 + 近期 swing（整合 stock-analyzer）|

## 东财防封铁律（已内置，勿绕过）

`em_get()` 统一入口强制：
1. 串行调用（不并发），两次东财请求最小间隔 `EM_MIN_INTERVAL=1.0s`（环境变量可配，批量调到 1.5~2s）+ 随机抖动；
2. 复用 `EM_SESSION`（Keep-Alive），带正常 UA；
3. 所有 `datacenter-web.eastmoney.com` / `push2*` / `reportapi` / `search-api` / `np-weblist` 请求一律走 `em_get()`。

> 东财风控经验阈值：每秒>5次 / 单IP并发≥10 / 1分钟≥200次 → 临时封 IP（403/429/空数据）。
> 批量拉多只股票时，务必在每只之间 sleep，并调大 `EM_MIN_INTERVAL`。

## 与既有脚本的关系

- `stock_enhanced.query_stock(..., options=["capital"])` 或 `run_analysis.py` 默认开启 `capital` 维度：
  原 akshare 桩（margin/lhb/fund/holder）若返回空/报错，自动用本模块直连源覆盖；新增维度（block_trade/dividend/lockup/research/news/announcements/concept）直接挂在 `result["capital_data"]` 下。
- 本模块**不依赖** `mootdx` / `akshare`，仅依赖 `requests`（已在 `requirements.txt`），在缺 akshare 环境也能跑通资金面/筹码维度。
- 不强制 `no_proxy`，与 `stock_enhanced` 的 `no_proxy='*'` 解耦并存；在需代理的网络中本模块走系统代理，更可能成功。

## 已知边界（诚实标注）

- 北向资金：东财全系自 2024-08 后净买额字段上游断供（a-stock-data 已记录），本模块未重复实现，沿用 `stock_enhanced.get_north_flow`（akshare hsgt）。
- 分析师目标价：研报接口仅给评级与 EPS 预期，**不臆测目标价**；`get_price_targets` 仅输出支撑/压力 + 评级摘要，目标价以研报原文为准。
- 数据缺失一律标记 `error` / `note:"未取到"`，绝不编造（遵循 skill 核心原则）。
