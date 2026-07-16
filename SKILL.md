---
name: finance-expert-pack
description: 金融投资全能工具包（A股/港股/美股）。整合实时行情盯盘、技术分析（MACD/KDJ/RSI/布林/筹码）、资金流向、舆情监控、财经热榜、全球市场环境、自然语义金融数据搜索、23通达信指标多维度评分、A股热度TOP50。当用户提到股票分析、行情查询、盯盘、涨跌扫描、涨停板、市场技术面、主力资金、舆情情绪、财经资讯、市场环境、选股策略、买卖点判断时触发。本 skill 是多个金融子能力的统一入口，按意图路由到对应 references/scripts。
---

# 金融投资全能工具包 (Finance Expert Pack)

> 把分散的金融 skill 与专家分析框架整合为**单一可移植 skill**，导入即用。
> 包含：你的专家分析框架 + 9 个金融 skill 的能力集合。

## ⚠️ 使用前必须配置的环境变量

本包的实时行情（智兔数服）与部分数据源依赖以下环境变量。**未配置时相关脚本会优雅降级或返回空，而非崩溃**，但核心能力需要：

| 变量 | 必填 | 说明 |
|------|------|------|
| `ZHITU_TOKEN` | **必填** | 智兔数服实时行情主源鉴权 Token。申请见其官网；未配置时 `zhitu_monitor.py` 返回空并在 stderr 告警。 |
| `TUSHARE_TOKEN` | 可选 | Tushare Pro Token（a-share-pro 多源降级用）。 |
| `AUTH_GATEWAY_PORT` | 可选 | NeoData 网关端口，默认 `19000`，仅 OpenClaw/JPRX 运行时需要；未配置时 neodata / 新闻雷达等返回"网关不可用"。 |
| `PROSEARCH_SCRIPT` | 可选 | 元宝 / prosearch 网页搜索脚本路径，默认 QClaw 内置路径；未配置时网页新闻分支返回空。 |
| `A_SHARE_DATA_DIR` | 可选 | a-share-pro 数据存储目录，默认 `~/.openclaw/a_share`。 |

> 依赖安装：首次使用请 `pip install -r requirements.txt`（akshare / baostock / pandas / numpy / requests / yfinance / openpyxl）。

配置方式（Windows PowerShell 当前会话）：
```powershell
$env:ZHITU_TOKEN = "你的token"
$env:TUSHARE_TOKEN = "你的token"   # 可选
```

## 能力路由（按用户意图选择）

| 用户意图 | 调用文件 | 说明 |
|---------|---------|------|
| A股实时行情/盯盘/涨停股池 | `scripts/a-share-monitor/zhitu_monitor.py` | 个股/指数/涨停/综合监控 |
| 自选股管理（纯文本存储） | `scripts/a-share-pro/asp_*.py` | 增删查/监控/绩效汇总 |
| 个股深度分析买卖建议 | `references/stock-master-workflow.md` + `references/analysis-framework.md` | 陷阱检测+三情景+23策略 |
| 个股深度分析(编排入口) | `scripts/run_analysis.py <code>` | 一键取行情+技术+资金+基本面+估值+事件+**资金面/筹码/研报/价位**，输出 JSON |
| 资金面/筹码/事件/研报补齐 | `scripts/workspace/stock_capital_data.py` | 资金流120日/分钟级·融资融券·龙虎榜·大宗·股东户数·分红·解禁·研报·新闻·公告·概念板块（直连东财HTTP，抗封限流） |
| 估值与买卖价位 | `scripts/workspace/stock_capital_data.py` | forward PE / PEG / PE消化 + 支撑压力位(MA20/60+近期swing) + 分析师评级（整合 stock-analyzer 模型） |
| 基本面/估值/事件取数 | `scripts/workspace/stock_fundamentals.py` | 5年财务/同业对比/PE·PB分位/DCF输入/事件日历(akshare) |
| 中国公司投资分析 | `references/china-stock-analysis/china-stocks.md` | A股/港股买卖建议与趋势 |
| 每日财经热榜/投资资讯 | `references/daily-finance.md` | 平台联网能力 或 私有运行时(news_radar.py) 两条路径 |
| 全球市场环境/风险偏好 | `scripts/market-environment-analysis/market_utils.py` + `references/market-environment-analysis/` | 美股/欧股/亚股/外汇/商品 |
| 自然语义金融数据搜索 | `scripts/neodata-financial-search/neodata_query.py` | 财报/资金流/研报/板块 |
| 舆情监控与情绪打分 | `scripts/news-sentiment-scan/sentiment_scan.py` | 公告/新闻/研报/社媒 -10~+10 |
| 技术面指标评分(参考) | `references/stock-analysis-23/完整技能文档.md` + `scripts/workspace/technical_analysis.py` | 已实现 MACD/KDJ/RSI/BOLL/MA 共5项；完整 M001-M023 需外部通达信环境，详见文档 |
| A股实时热度TOP50 | `scripts/stock-heat-rank-py/main.py` | 问财/雪球/东财聚合 |
| **板块策略回测 / 过滤等权持有（推荐默认）** | `scripts/workspace/sector_strategy.py` | 等权持有整篮 + 板块ETF(或回退等权指数) 200MA 趋势过滤（默认）；`--mode quality` 为 T3 实验：过滤等权 + 基本面(ROE/营收/利润增速)截面选前5。经 T4 多板块样本外验证为当前最优简单规则；资金流维度因 eastmoney 接口封锁暂挂起 |

## 数据分析总纲

- 数据源分级与降级策略：`references/data-sources.md`
- 融合分析框架 v1.0（筛选→验证→三情景→事件催化）：`references/analysis-framework.md`
- 股票分析统一工作流（硬性规则+场景路由）：`references/stock-master-workflow.md`

## 核心原则（继承自 stock-master）

1. 数据必须来自真实来源，禁止编造数字
2. 区分事实/推断/猜测，不确定标注"推断"或"情景"
3. 禁止"必涨/精准买点/稳赚"，用 base/bull/bear 三情景 + 触发条件 + 失效位
4. 矛盾必须呈现，不准和稀泥
5. 缺失不编造，标记"未取到"
6. 每条数据带来源
7. 不构成投资建议，所有输出为研究参考

## 使用说明

- 脚本均为独立 Python 文件，按需调用，例如：
  ```powershell
  # 首次安装依赖
  pip install -r requirements.txt

  # 个股深度分析（编排入口：行情+技术+资金+基本面+估值+事件 一键 JSON）
  python scripts/run_analysis.py 600519

  # 板块「过滤等权持有」策略回测（默认，3 板块 × 全周期，产出 index_filtered_eqw.html 仪表盘）
  python scripts/workspace/sector_strategy.py --all
  python scripts/workspace/sector_strategy.py --sector 游戏 --period 全周期2021-26
  # T3 实验模式：过滤等权 + 基本面截面选股（产出 index_t3_quality.html）
  python scripts/workspace/sector_strategy.py --mode quality --all

  # 实时行情 / 盯盘
  python scripts/a-share-monitor/zhitu_monitor.py 600273 嘉化能源
  python scripts/stock-heat-rank-py/main.py
  ```
- 各子能力详细用法见对应 `references/` 与原始 skill 文档。
- 本 skill 与原 9 个独立金融 skill 功能等价，整合后避免重复触发与文件冲突。
