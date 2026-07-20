#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动回测报告生成器，跑完回测自动生成Markdown/PDF报告
"""
import os
from datetime import datetime
import pandas as pd

def generate_report(result, output_path: str = None) -> str:
    """生成Markdown格式回测报告"""
    code = result["code"]
    name = result["name"]
    s = result["summary"]
    trades = result["trades"]
    
    if output_path is None:
        output_path = f"{code}_backtest_report.md"
    
    # 生成交易统计
    trades_df = pd.DataFrame(trades)
    win_trades = trades_df[trades_df["profit"]>0] if len(trades_df)>0 else pd.DataFrame()
    lose_trades = trades_df[trades_df["profit"]<=0] if len(trades_df)>0 else pd.DataFrame()
    
    md_content = f"""# {name}({code}) 策略回测报告
生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 核心绩效指标
| 指标 | 数值 |
|------|------|
| 总收益率 | {s['total_return_pct']:+.2f}% |
| 买入持有收益率 | {s['buy_hold_return_pct']:+.2f}% |
| 超额收益率 | {s['excess_return_pct']:+.2f}% |
| 年化收益率(CAGR) | {s['cagr_pct']:+.2f}% |
| 最大回撤 | {s['max_drawdown_pct']:.2f}% |
| 最大回撤 | {s.get('max_drawdown_pct',0):.2f}% |
| 夏普比率 | {s['sharpe_ratio']:.2f} |
| 索提诺比率 | {s['sortino_ratio']:.2f} |
| 卡玛比率 | {s['calmar_ratio']:.2f} |
| 胜率 | {s['win_rate_pct']:.1f}% |
| 盈亏比 | {s['profit_loss_ratio']:.2f} |
| 总交易次数 | {s['total_trades']}次 |
| 总手续费 | {s['total_commission']:.2f}元 |

## 年度收益表现
| 年份 | 策略收益% |
|------|-----------|
"""
    for year, ret in s["yearly_returns"].items():
        md_content += f"| {year[:4]} | {ret:+.2f}% |\n"
    
    md_content += f"""
## 策略说明
- 策略逻辑：200MA趋势跟踪，收盘价在200日均线上方持有，跌破空仓
- 交易成本：佣金万2.5 + 印花税千1（卖出） + 过户费十万1 + 滑点千1，{'ETF免印花税' if s['is_etf'] else ''}
- 风控：默认8%止损
- {s['survivorship_bias_note']}

## 风险提示
⚠️ 本报告为历史回测结果，不代表未来收益，不构成任何投资建议，投资有风险，入市需谨慎。
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"✅ 回测报告已生成：{os.path.abspath(output_path)}")
    return output_path

if __name__ == "__main__":
    from backtest_engine import BacktestEngine
    engine = BacktestEngine()
    res = engine.run_single("002624", "完美世界", ma_period=200, start_date="2021-01-01")
    generate_report(res)
