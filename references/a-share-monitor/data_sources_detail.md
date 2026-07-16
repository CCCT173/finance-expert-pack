# A股监控数据源明细（智兔数服 zhitu_monitor）

> 本文件为 `scripts/a-share-monitor/zhitu_monitor.py` 的数据源说明。原文件因编码损坏（GBK 误读为 UTF-8）不可读，此处以 UTF-8 重写。
> 鉴权：环境变量 `ZHITU_TOKEN`（必填），缺失时接口返回空并在 stderr 给出告警。

## 一、接口清单

| 能力 | 接口路径 | 说明 |
|------|----------|------|
| 个股实时行情 | `GET /hs/real/time/{code}?token=` | 价格、涨跌幅、换手率、成交额、PE |
| 指数实时行情 | `GET /hz/real/ssjy/{code}?token=` | 如上证 `000001.SH` |
| 指数 MA 均线 | `GET /hz/history/ma/{code}/{period}?token=&limit=` | period: d/w/m，默认 limit=5 |
| 指数 MACD | `GET /hz/history/macd/{code}/{period}?token=&limit=` | 同上 |
| 涨停股池 | `GET /hs/pool/ztgc/{trade_date}?token=` | trade_date 格式 `YYYY-MM-DD` |

- BASE：`https://api.zhituapi.com`
- 返回非 200 或空时函数返回 `None`，由调用方降级（如实时行情回退到东财/腾讯）。

## 二、降级与健壮性

- `get_last_trading_day()` / `get_zt_pool()` 已处理周末、节假日，自动回退到上一交易日。
- 盘中（15:00 前）涨停池默认取上一交易日；15:00 后取当日。
- 所有请求超时 10s，异常静默返回 `None`，不抛出。

## 三、与其他数据源的关系

- 实时监控主源为智兔数服；若 `ZHITU_TOKEN` 未配置，应改用 `stock_enhanced.get_realtime`（东财 push2 → 腾讯兜底）。
- 指数技术面（MA/MACD）由智兔提供；个股技术面由 `stock_enhanced.get_kline` 本地计算（BaoStock/东财）。

## 四、已知限制

- 智兔为第三方付费 API，稳定性与配额取决于账户。
- 实时行情类接口在市场极端行情或停牌时可能返回异常结构，消费端需做字段判空。
