<div align="center">

# finance-expert-pack · A股量化交易工具包
Python写的A股量化工具集，回测用真实交易成本，零配置不用Token，直接跑。

---

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![Zero Lookahead](https://img.shields.io/badge/Backtest-No%20Future%20Functions-red.svg)](#backtest-discipline)
[![Real Costs](https://img.shields.io/badge/Costs-Real%20A--Share%20Fees-orange.svg)](#cost-model)
[![No Tokens](https://img.shields.io/badge/Setup-Zero%20Config-green.svg)](#quick-start)

**[GitHub 源码](https://github.com/CCCT173/finance-expert-pack)** | **[SkillHub 安装](https://skillhub.cn/skills/finance-expert-pack)**

游戏板块2021-2026回测：200MA趋势策略收益105.8%，同期买入持有72.8%，扣除佣金/印花税/滑点后超额33%。

</div>

---

## 为什么做这个
做量化的人都遇到过这些问题：
- 网上找的回测代码，要么藏着未来函数，要么根本没算交易成本，回测翻倍实盘亏30%
- 装了一堆金融插件，数据对不上，还经常冲突重复触发
- 数据源三天两头改接口，脚本跑一半崩了，之前的结果再也复现不出来
- 很多工具上来就要注册拿Token，核心功能还要付费

这个包就是为了解决这些问题，所有代码开源，回测规则写死，结果自己能审，用公开API不用注册，装完依赖直接跑。

---

## 功能清单
都是实盘能用的功能，没有花架子：

| 模块 | 说明 |
|------|------|
| 📊 板块策略回测 | 内置200MA过滤等权策略，真实计算佣金/印花税/滑点，自动过滤ST/次新/涨跌停不可成交情况 |
| 🔍 条件选股 | 均线多头、MACD金叉、突破新高、ROE筛选，自动排除ST/次新/低流动性股票 |
| 📝 每日复盘 | 一键生成大盘涨跌、板块排行、北向资金、涨跌停统计、自选股表现、未来解禁/财报提醒 |
| 📈 个股分析 | 行情、技术面、资金面、基本面、估值、事件、研报、筹码，一键输出JSON |
| 🔔 信号提醒 | 价格提醒、金叉死叉、破位信号，支持Server酱/企业微信/钉钉推送，后台可以挂着监控自选股 |
| 💼 持仓跟踪 | 纯文本记录交易，自动算盈亏、成本价、仓位占比、胜率，不用自己记Excel |
| 💰 资金面分析 | 主力资金流、筹码分布、龙虎榜、大宗交易、北向持仓 |
| 📰 舆情监控 | 新闻情绪打分、热搜榜、概念热度 |

---

## Backtest Discipline 回测规则
这部分是和网上其他回测代码最大的区别，所有规则都写死在代码里，不是嘴上说说：
- 信号用t-1收盘价计算，T+1开盘成交，绝对没有未来函数
- 成本完整计算：佣金万2.5 + 印花税千1（卖出收） + 过户费十万1 + 滑点千1，和实盘几乎一致
- 交易规则还原：涨停买不进、跌停卖不出、停牌跳过交易，不假设随时能成交
- 自动过滤ST/*ST、上市不满60天次新股、日均成交额低于5000万的低流动性股票
- warmup期120个交易日，数据不够就空仓，不凑结果
- 数据拉取失败直接告警，不偷偷补假数据
- 同样输入永远得到同样结果，100%可复现

---

## Quick Start 快速开始
### 1. 安装依赖
```bash
pip install -r requirements.txt
# 核心依赖只有pandas/numpy/akshare/requests，没有其他乱七八糟的包
```

### 2. 不用配置任何Token
所有数据都走公开免费API，不需要注册，不用申请密钥，装完直接跑。可选配Tushare Token做多源降级，不配完全不影响使用。

### 3. 跑第一个例子
```bash
# 全板块策略回测，生成可交互HTML报告，包含净值曲线、回撤、交易记录
python scripts/workspace/sector_strategy.py --all

# 今天市场怎么样？生成每日复盘报告
python scripts/workspace/daily_review.py

# 找均线多头排列的股票，输出前20个
python scripts/workspace/stock_screener.py --ma-long --top 20

# 分析个股
python scripts/run_analysis.py 600519
```

---

## 策略说明
默认推荐200MA过滤等权策略：板块成分股等权持有，板块指数跌破200MA就空仓，站上再买回来。
- 逻辑很简单，不用搞复杂因子
- 2021-2026游戏、半导体、新能源、医药四个板块回测全部跑赢买入持有
- 作用是熊市少跌，不是牛市多赚——2022年熊市最大回撤从58%降到38%，少亏20个点
- 另外有实验性质的quality模式，趋势向上时按ROE/营收增速/利润增速选前5只等权，波动更小。

目前所有回测都已经扣除了全部交易成本，结果直接对标实盘。

---

## Limitations 已知局限
不吹牛逼，有问题直接说：
1. 回测成分股是当前时点的，有生存者偏差，历史退市/更名没有处理，结论不要过度外推
2. 主力资金流接口被东财封了，目前T3质量模式只用基本面数据，资金面维度暂缺
3. 公开数据源偶尔会改版或者限流，已经做了重试降级，但不能保证100%可用
4. 现在主要做A股，港股美股路径有但是没做过充分验证
5. 回测没算冲击成本，资金量特别大的话滑点会比默认的千1高

---

## 七条原则
所有输出都遵守这些规则：
1. 没有的数据就说没拿到，绝不编数字
2. 分清楚哪些是事实，哪些是推断，哪些是猜测
3. 永远不说"必涨"、"稳赚"，任何判断都给上涨/中性/下跌三种情景和触发条件
4. 多空矛盾的信号都列出来，不偏不倚
5. 所有数据带来源，你可以自己去查
6. 同样输入永远出同样结果，没有随机黑盒
7. 所有内容都是研究参考，不构成投资建议。

---

## License
MIT，随便用，注明出处就行。

---

<div align="center">

如果这个包帮你省了时间，欢迎点个Star⭐，有问题提PR或者Issue都行。

</div>
