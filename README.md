# 金融投资全能工具包 · Finance Expert Pack

> 把分散的金融分析子能力整合为**单一可移植的 Skill**，导入即用。
> 覆盖 A 股 / 港股 / 美股的实时行情、技术分析、资金面、舆情、市场环境与板块策略回测。

---

## 这是什么

`finance-expert-pack` 是一个面向金融研究的 **Skill 工程包**，把 9 个原本独立的金融 Skill 与一套专家分析框架，收敛为一个目录即可分发、即可运行的技能包。它不依赖任何商业回测平台，核心回测逻辑用 **纯 Python + pandas** 实现，数据走公开源（akshare 等）并带本地缓存与断点续传。

设计目标只有一条：**让分析可复现、可溯源、不编造**。

---

## 核心特性

- **单一入口，按意图路由**：一个 Skill 内包含实时盯盘、技术分析、资金面、舆情、财经热榜、全球市场环境、自然语义金融数据搜索、热度排名、板块策略回测等能力，由 `SKILL.md` 的路由表统一分发，避免多 Skill 重复触发与文件冲突。
- **板块策略回测（重点）**：内置「过滤等权持有」规则——等权持有整篮 + 板块 ETF（缺失则回退等权指数）的 200MA 趋势过滤，跌破转现金，T+1 执行。经多板块样本外验证为当前最优简单规则；另有 `--mode quality` 实验模式做基本面截面选股（防御型倾斜）。
- **严守回测纪律**：趋势信号一律用 `t-1` 收盘判定（T+1），无未来函数；warmup 用 `min_periods=120`；成本仅含切换单边费；取数失败优雅降级并显式说明覆盖数 `M<N`。
- **多源降级，不脆断**：实时行情主源（智兔数服）缺失时相关脚本返回空并告警而非崩溃；资金面直连东财 HTTP 并带限流；财务走 akshare。
- **可溯源的分析原则**：事实 / 推断 / 猜测分层，矛盾必须呈现，缺失标记「未取到」，每条数据带来源，全程拒绝「必涨 / 精准买点 / 稳赚」式表述。
- **纯本地、可审计**：不调用任何黑盒模型服务做取数；回测脚本 `python xxx.py` 直接跑，产出 `equity.csv / trades.csv / summary.json / index.html` 一套标准产物。

---

## 目录结构

```
finance-expert-pack/
├── SKILL.md                              # 技能入口 + 能力路由表
├── _meta.json                            # 包元数据（名称/版本/依赖/作者）
├── requirements.txt                      # Python 运行依赖
├── references/                           # 分析框架、数据源、子能力说明文档
│   ├── analysis-framework.md             # 融合分析框架 v1.0
│   ├── stock-master-workflow.md          # 统一工作流（硬性规则 + 场景路由）
│   ├── data-sources.md                   # 数据源分级与降级策略
│   ├── stock-analysis-23/                # 23 通达信指标参考文档
│   └── ...
└── scripts/
    ├── run_analysis.py                   # 个股深度分析编排入口（一键 JSON）
    ├── a-share-monitor/                  # 实时行情 / 盯盘
    ├── a-share-pro/                      # 自选股管理（纯文本存储）
    ├── workspace/
    │   ├── sector_strategy.py            # 板块策略回测（过滤等权 / quality 双模式）
    │   ├── stock_capital_data.py         # 资金面 / 筹码 / 事件 / 研报补齐
    │   ├── stock_fundamentals.py         # 基本面 / 估值 / 事件取数
    │   ├── technical_analysis.py         # MACD/KDJ/RSI/BOLL/MA 指标评分
    │   ├── sentiment_scan.py             # 舆情监控与情绪打分（-10~+10）
    │   └── ...
    ├── market-environment-analysis/      # 全球市场环境 / 风险偏好
    ├── neodata-financial-search/         # 自然语义金融数据搜索
    └── stock-heat-rank-py/               # A 股实时热度 TOP50
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
# 核心包：requests / pandas / numpy / akshare / baostock / yfinance / openpyxl
```

### 2. 配置环境变量

实时行情（智兔数服）主源需要 Token；其余为可选降级源。

```powershell
$env:ZHITU_TOKEN = "你的token"        # 必填：实时行情主源
$env:TUSHARE_TOKEN = "你的token"      # 可选：a-share-pro 多源降级
```

未配置时，依赖该源的脚本会**返回空并在 stderr 告警**，其余能力不受影响。

### 3. 跑一个例子

```bash
# 个股深度分析（行情+技术+资金+基本面+估值+事件 一键 JSON）
python scripts/run_analysis.py 600519

# 板块「过滤等权持有」回测（默认，3 板块 × 全周期，产出 index_filtered_eqw.html）
python scripts/workspace/sector_strategy.py --all
python scripts/workspace/sector_strategy.py --sector 游戏 --period 全周期2021-26

# T3 实验模式：过滤等权 + 基本面截面选股（产出 index_t3_quality.html）
python scripts/workspace/sector_strategy.py --mode quality --all

# 实时行情 / 盯盘
python scripts/a-share-monitor/zhitu_monitor.py 600273 嘉化能源
```

---

## 板块策略回测说明

`scripts/workspace/sector_strategy.py` 是本包回测能力的核心。

| 模式 | 说明 | 产物 |
|------|------|------|
| `--mode filtered`（默认） | 等权持有整篮 + 板块 ETF 200MA 趋势过滤，跌破转现金 | `index_filtered_eqw.html` |
| `--mode quality` | 趋势向上区间内按 ROE / 营收增速 / 利润增速 rank-sum 复合排名选前 5 等权，月度再平衡（防御型倾斜，非默认升级） | `index_t3_quality.html` |

纪律约束（硬性）：
- 信号用 `t-1` 收盘判定，T+1 执行，**无未来函数**；
- warmup `min_periods=120`；
- 成本仅含单边切换费（偏乐观，见下方局限）；
- 取数走 akshare + 本地缓存断点续传，失败显式说明覆盖数。

---

## 真实局限（请务必阅读）

为了不误导使用者，以下局限是**真实存在**的，不是凑数：

1. **实时行情依赖外部 Token**：`ZHITU_TOKEN` 未配置时实时盯盘 / 热度排名不可用（已有降级提示，但不会凭空造数）。
2. **回测成本偏乐观**：当前仅计单边切换费，未含印花税、过户费、滑点、冲击成本；实盘摩擦会侵蚀收益。
3. **回测宇宙含生存者偏差**：成分股取自当前时点，未处理历史退市 / 更名，样本外结论需谨慎外推。
4. **资金流维度暂挂起**：逐日主力资金流因数据源接口层封锁暂不可用，T3 实验目前为纯基本面截面，质量维度不完整。
5. **23 项通达信指标仅本地实现 5 项**：MACD/KDJ/RSI/BOLL/MA 已落地；完整 M001–M023 需外部通达信环境，详见 `references/stock-analysis-23/`。
6. **A 股回测为主**：板块回测样本目前集中在 A 股板块；港股 / 美股路径存在但未经同等样本外验证。
7. **数据源稳定性风险**：akshare / 东财等公开源会随站点改版波动，偶发字段缺失或限流，脚本已做重试与降级但无法保证 100% 覆盖。

---

## 分析原则

本包继承自专家分析框架的七条铁律：

1. 数据必须来自真实来源，禁止编造数字；
2. 区分事实 / 推断 / 猜测，不确定标注「推断」或「情景」；
3. 禁止「必涨 / 精准买点 / 稳赚」，用 base / bull / bear 三情景 + 触发条件 + 失效位；
4. 矛盾必须呈现，不准和稀泥；
5. 缺失不编造，标记「未取到」；
6. 每条数据带来源；
7. 所有输出为研究参考，不构成投资建议。

---

## 免责声明

> ⚠️ 本工具包所有内容由 AI 基于公开信息整理生成，仅供参考，不构成任何投资建议或个股推荐。投资有风险，决策需谨慎。回测结果均为历史模拟，不代表未来收益。

---

## License

本仓库以 **MIT** 许可证开源，仅供研究与学习使用。
