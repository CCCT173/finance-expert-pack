# A股监控技能 - 配置参考

## 目标股票配置

默认监控自选股（可修改）：
```python
portfolio = [
    ("002624", "完美世界"),
    ("601069", "西部黄金"),
    ("600397", "江钏装备"),
]
```

指数配置：
```python
indices = [
    ("000001.SH", "上证指数"),
    ("399001.SZ", "深证成指"),
    ("399006.SZ", "创业板指"),
    ("000688.SH", "科创50"),
]
```

## Cron 任务模板

### 1. 盘前宏观扫描（8:30 工作日）
```json
{
  "name": "【盘前30分钟】全球宏观扫描",
  "schedule": {"kind": "cron", "expr": "30 8 * * 1-5", "tz": "Asia/Shanghai"},
  "sessionTarget": "isolated",
  "payload": {"kind": "agentTurn", "message": "【全球宏观盘前扫描】\n\n用 neodata-financial-search 查询外围市场..."},
  "delivery": {"mode": "announce", "channel": "qqbot", "to": "c2c:<OPENID>"}
}
```

### 2. 盘前早报（9:00 工作日）
```json
{
  "name": "【每日盘前】聚焦早报",
  "schedule": {"kind": "cron", "expr": "0 9 * * 1-5", "tz": "Asia/Shanghai"},
  "sessionTarget": "isolated",
  "payload": {"kind": "agentTurn", "message": "【每日盘前早报】\n\n查询大盘指数、聚焦标的动态..."}
}
```

### 3. 盘中异动监测（每15分钟）
```json
{
  "name": "【盘中15min】聚焦标的异动监测",
  "schedule": {"kind": "cron", "expr": "*/15 9-14 * * 1,2,3,4,5", "tz": "Asia/Shanghai"},
  "sessionTarget": "isolated",
  "payload": {"kind": "agentTurn", "message": "【盘中15分钟监测】\n\n检测异动±1.5%，触发预警..."}
}
```

### 4. 新闻追踪（每30分钟）
```json
{
  "name": "【30min】聚焦标的新闻追踪",
  "schedule": {"kind": "cron", "expr": "*/30 9-14 * * 1-5", "tz": "Asia/Shanghai"},
  "sessionTarget": "isolated",
  "payload": {"kind": "agentTurn", "message": "【聚焦标的新闻追踪】\n\n查询公告、新闻、研报..."}
}
```

### 5. 盘后报告（16:00 工作日）
```json
{
  "name": "【每日盘后】聚焦标的收盘报告",
  "schedule": {"kind": "cron", "expr": "0 16 * * 1-5", "tz": "Asia/Shanghai"},
  "sessionTarget": "isolated",
  "payload": {"kind": "agentTurn", "message": "【每日盘后报告】\n\n收盘行情、总结分析..."}
}
```

## 模拟投资实验配置

### 实验参数
```python
experiment_config = {
    "initial_capital": 10000,        # 初始资金（元）
    "target_stocks": [
        ("002624", "完美世界"),
        ("601069", "西部黄金"),
        ("600397", "江钏装备"),
    ],
    "period": "2026-05-14 ~ 2026-05-22",  # 7个交易日
    "t_plus_1": True,                # T+1规则
    "limit_up_down": 0.10,           # 涨跌停±10%
}
```

### 决策判断标准

**大盘风险判断**（用于决定是否行动）：

| 条件 | 判断 | 操作 |
|------|------|------|
| 沪指跌幅 > -1.5% | 系统性风险 | 按兵不动 |
| 创业板/科创50跌幅 > -2% | 系统性风险 | 按兵不动 |
| 指数跌破 MA20 | 技术破位 | 按兵不动 |
| 无明显风险，指数企稳 | 机会 | 建仓行动 |

**买入信号优先级**：
1. 指数在 MA20/MA60 之上（多头排列）
2. MACD 金叉（DIFF > DEA）
3. 标的跌幅小于大盘（抗跌）
4. 缩量企稳（抛压减轻）

**风控原则**：
- 单次建仓不超过 50% 仓位
- 止损设置：跌破买入价 -3% 考虑止损
- 止盈设置：达到买入价 +5% 以上考虑分批止盈

---

## 状态文件格式

### last_prices.json
```json
{
  "updated": "2026-05-14T09:30:00",
  "stocks": {
    "002624": {"name": "完美世界", "price": 16.96, "change_pct": 0.65},
    "601069": {"name": "西部黄金", "price": 33.26, "change_pct": -1.71},
    "600397": {"name": "江钏装备", "price": 15.09, "change_pct": 1.28}
  },
  "indices": {
    "上证指数": {"price": 4242.57, "change_pct": 0.67}
  }
}
```

### news_log.json
```json
{
  "last_check": "2026-05-14T09:30:00",
  "news": [
    {"time": "2026-05-14T10:00:00", "stock": "002624", "type": "公告", "summary": "..."}
  ],
  "event_log": []
}
```

### macro_scan.json
```json
{
  "generated_at": "2026-05-14T08:30:00",
  "us_market": {"sp500": 5200, "change_pct": 0.5, "nasdaq": 18000, "change_pct": 0.8},
  "a50_futures": 12500,
  "gold_price": 2350,
  "oil_price": 85,
  "usd_cny": 7.25,
  "northbound_capital_3d": 50,
  "open_bias": "偏多"
}
```
