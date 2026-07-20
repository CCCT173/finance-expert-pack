---
slug: finance-expert-pack
name: finance-expert-pack
displayName: A股量化工具包 · Finance Expert Pack
version: 2.1.0
summary: A股量化交易工具包 | 实盘验证200MA趋势策略 | 零Token零注册 | 真实交易成本回测 | 覆盖选股/复盘/回测/告警/持仓/研报全流程 | 个人开发者开源免费工具
description: 开源免费的A股量化工具包，整合了实盘验证的200MA趋势策略、每日复盘、条件选股、信号告警、持仓跟踪、研报爬取等功能。所有数据来自公开免费API，无需注册Token。当用户提到股票分析、行情查询、盯盘、回测、选股、复盘、买卖点参考、研报爬取、可转债策略、资产配置时触发。本 skill 按用户意图自动路由到对应功能。
license: MIT
homepage: https://github.com/CCCT173/finance-expert-pack
tags:
  - finance
  - a-share
  - stock-analysis
  - quant
  - trading
  - market-data
---

# A股量化工具包 (Finance Expert Pack)

> 个人开发者开源的A股量化工具集合，所有功能实盘验证，免费使用，无任何付费门槛。
> 整合了从行情、回测、选股、复盘到研报爬取的常用功能，不用再在各个网站之间切换。

## ⚠️ 使用前说明

本包所有核心能力基于公开免费API（akshare/baostock）实现，**无需任何Token或密钥即可使用**，数据完全存本地，不上传任何云端。

部分数据源依赖可选环境变量，未配置时会自动降级，不影响核心功能：

| 变量 | 必填 | 说明 |
|------|------|------|
| `TUSHARE_TOKEN` | 可选 | Tushare Pro Token，用于多数据源降级，不填也能用 |
| `AUTH_GATEWAY_PORT` | 可选 | NeoData网关端口，默认19000，仅特定运行时需要，普通用户不用管 |
| `PROSEARCH_SCRIPT` | 可选 | 网页搜索脚本路径，普通用户不用管 |

> 首次使用请先安装依赖：`pip install -r requirements.txt`（包含akshare/baostock/pandas/numpy/requests/yfinance/openpyxl）
> 所有行情、财务、资金流数据均来自公开免费API，无需申请任何密钥即可直接使用。

## 能力路由（按用户意图自动选择）

| 用户意图 | 调用文件 | 说明 |
|---------|---------|------|
| A股实时行情/盯盘 | `scripts/a-share-monitor/zhitu_monitor.py` | 个股/指数实时行情、涨跌幅、成交量监控 |
| 自选股管理（纯文本存储） | `scripts/a-share-pro/asp_*.py` | 增删查/批量监控/绩效汇总 |
| 个股全维度分析 | `scripts/run_analysis.py <code>` | 一键获取行情+技术指标+资金面+基本面+估值+事件+支撑压力位，输出结构化JSON |
| 资金面/筹码/事件/研报数据 | `scripts/workspace/stock_capital_data.py` | 资金流/融资融券/龙虎榜/大宗交易/股东户数/分红/解禁/研报/新闻/公告 |
| 估值与买卖价位参考 | `scripts/workspace/stock_capital_data.py` | PE/PEG/PE历史分位 + 支撑压力位(MA20/MA60+近期高低点) + 分析师评级汇总 |
| 基本面财务数据 | `scripts/workspace/stock_fundamentals.py` | 5年财务报表/同业对比/PE/PB分位/事件日历 |
| 每日市场复盘报告 | `scripts/workspace/daily_review.py` | 一键生成大盘概览/板块排行/自选股表现/未来解禁财报日程结构化报告 |
| 条件选股 | `scripts/workspace/stock_screener.py` | 支持均线多头/MACD金叉/突破新高/ROE筛选，自动过滤ST/次新/低流动性个股 |
| **板块200MA过滤策略回测（实盘验证）** | `scripts/workspace/sector_strategy.py` | 等权持有板块龙头+200MA趋势过滤，真实交易成本+涨跌停/ST/次新自动过滤，结果贴近实盘；`--mode quality`为基本面优选模式 |
| 三个懒人配置策略（永久组合/三元配置/双低可转债） | `scripts/workspace/custom_strategies.py` | 均经过完整牛熊回测，适合不同风险偏好投资者 |
| 双低可转债策略回测和选券 | `scripts/workspace/convertible_bond_backtest.py` | 价格<130/溢价<30%/AA以上评级，月度轮动，回测+实时选券 |
| 信号告警推送 | `scripts/workspace/signal_alert.py` | 价格/技术信号告警，支持Server酱/PushPlus/企业微信/钉钉多渠道推送 |
| 持仓跟踪与绩效统计 | `scripts/workspace/portfolio_tracker.py` | 本地记录交易，自动计算成本/盈亏/仓位占比/胜率/盈亏比，数据完全存本地 |
| 模拟交易练习 | `scripts/workspace/simulated_trading.py` | 本地模拟A股交易，真实手续费和交易规则，适合新手练手 |
| 风控检查 | `scripts/workspace/risk_control.py` | 单票仓位/止损止盈/最大回撤/波动率自动检查，辅助风险控制 |
| 券商研报爬取 | `scripts/workspace/scraper/research_report_scraper.py` | 按个股/行业/分析师批量爬研报，含评级/目标价/盈利预测，断点续爬 |
| 公告/财报爬取 | `scripts/workspace/scraper/announcement_scraper.py` | 年报/季报/临时公告批量下载，PDF自动解析 |
| 研报/财报导出对比 | `scripts/workspace/scraper/` | 支持多格式导出，多份研报自动对比提取一致预期和风险点 |
| A股热度榜 | `scripts/stock-heat-rank-py/main.py` | 问财/雪球/东财热度TOP50聚合 |
| 通用回测引擎 | `scripts/workspace/backtest_engine.py` | 纯Python+pandas实现，支持自定义策略，真实成本计算 |
| Walk Forward滚动验证 | `scripts/workspace/walk_forward.py` | 年度滚动训练/测试，避免过拟合 |
| 交互式回测仪表盘 | `scripts/workspace/dashboard.py` | Plotly交互图表，净值曲线/回撤/月度热力图/交易明细 |
| 统一命令行入口 | `scripts/fincli.py` | `fincli backtest/screener/review/walkforward` 统一调用 |

## 核心使用原则（严格遵守）

1. 所有数据必须来自真实API，禁止编造任何数字或指标
2. 严格区分事实/推断/猜测，不确定的内容必须明确标注
3. 绝对禁止给出"必涨"、"稳赚"、"精准买点"这类确定性判断，所有分析均为研究参考
4. 所有操作建议给出上涨/中性/下跌三种情景，附触发条件和失效位
5. 数据矛盾时直接呈现矛盾点，不调和不隐瞒
6. 数据拉取失败时直接告知"未获取到数据"，绝不编造内容填充
7. 所有输出必须明确标注："本内容仅供学习研究，不构成任何投资建议，投资有风险入市需谨慎"
8. 港股美股功能未充分测试，涉及港美股的分析必须提前告知用户数据可能不准确

## 分析框架参考

- 数据源分级与降级策略：`references/data-sources.md`
- 股票分析框架（筛选→验证→三情景→事件催化）：`references/analysis-framework.md`
- 股票分析工作流（硬性规则+场景路由）：`references/stock-master-workflow.md`

## 已实现的技术指标

目前稳定支持5个最常用技术指标：
- MA（移动平均线）
- MACD（指数平滑异同移动平均线）
- RSI（相对强弱指标）
- BOLL（布林带）
- KDJ（随机指标）

其他文档中提到的更多指标需要外部通达信环境支持，本工具包未内置实现，不会返回相关结果。

## 使用示例

用户直接用自然语言提问即可，无需记忆命令，例如：
- "帮我跑一下半导体板块近3年的200MA策略回测"
- "生成今天的市场复盘报告，我的自选股是贵州茅台、宁德时代、三七互娱"
- "筛选一下最近MACD金叉、ROE大于15%的股票"
- "分析一下贵州茅台当前的估值和支撑压力位"
- "双低可转债策略最近表现怎么样，帮我选一下当前符合条件的个券"
- "设置一个提醒，三七互娱跌破18块的时候告诉我"

---
**本工具开源免费，永久无付费功能，不构成任何投资建议。**
