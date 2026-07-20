#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTML仪表盘生成器，交互式可视化回测结果
"""
import sys
import os
import json
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px

def generate_dashboard(result, output_path: str = "index.html"):
    """生成交互式HTML仪表盘"""
    code = result["code"]
    name = result["name"]
    summary = result["summary"]
    equity = result["equity_curve"]
    trades = result["trades"]
    benchmark = result["benchmark_curve"]
    
    # 归一化净值，基准=100
    equity_norm = equity / equity.iloc[0] * 100
    benchmark_norm = benchmark / benchmark.iloc[0] * 100
    
    # 计算回撤
    rolling_max = equity_norm.expanding().max()
    drawdown = (equity_norm / rolling_max - 1) * 100
    
    # 1. 创建净值曲线图
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=equity_norm.index, y=equity_norm.values, name="策略净值", line=dict(color="red", width=2)))
    fig1.add_trace(go.Scatter(x=benchmark_norm.index, y=benchmark_norm.values, name="买入持有", line=dict(color="gray", width=2, dash="dash")))
    # 标记买卖点
    buy_trades = [t for t in trades if "买" in t["action"]]
    sell_trades = [t for t in trades if "卖" in t["action"]]
    fig1.add_trace(go.Scatter(
        x=[pd.to_datetime(t["date"]) for t in buy_trades],
        y=[equity_norm[pd.to_datetime(t["date"])] for t in buy_trades],
        mode="markers", name="买入", marker=dict(color="red", size=8, symbol="triangle-up")
    ))
    fig1.add_trace(go.Scatter(
        x=[pd.to_datetime(t["date"]) for t in sell_trades],
        y=[equity_norm[pd.to_datetime(t["date"])] for t in sell_trades],
        mode="markers", name="卖出", marker=dict(color="green", size=8, symbol="triangle-down")
    ))
    fig1.update_layout(title="净值曲线 (初始=100)", xaxis_title="日期", yaxis_title="净值", height=400, template="plotly_white")
    
    # 2. 回撤图
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=drawdown.index, y=drawdown.values, fill="tozeroy", fillcolor="rgba(255,0,0,0.2)", line=dict(color="red", width=1), name="回撤%"))
    fig2.update_layout(title="回撤曲线", xaxis_title="日期", yaxis_title="回撤%", height=250, template="plotly_white")
    
    # 3. 月度收益热力图
    monthly_ret = equity_norm.resample("ME").last().pct_change().dropna() * 100
    monthly_df = pd.DataFrame({
        "year": monthly_ret.index.year,
        "month": monthly_ret.index.month,
        "return": monthly_ret.values.round(2)
    })
    monthly_pivot = monthly_df.pivot(index="year", columns="month", values="return")
    fig3 = px.imshow(monthly_pivot, text_auto=True, color_continuous_scale="RdYlGn", aspect="auto", labels=dict(x="月份", y="年份", color="收益%"))
    fig3.update_layout(title="月度收益热力图(%)", height=300)
    
    # 4. 年度收益柱状图
    yearly_ret = equity_norm.resample("YE").last().pct_change().dropna() * 100
    yearly_bench = benchmark_norm.resample("YE").last().pct_change().dropna() * 100
    fig4 = go.Figure()
    fig4.add_trace(go.Bar(x=yearly_ret.index.year, y=yearly_ret.values, name="策略收益%", marker_color="red"))
    fig4.add_trace(go.Bar(x=yearly_bench.index.year, y=yearly_bench.values, name="持有收益%", marker_color="gray"))
    fig4.update_layout(title="年度收益对比", barmode="group", height=300, template="plotly_white")
    
    # 5. KPI指标卡片
    kpi_html = f"""
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; padding: 20px 0;">
        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center;">
            <div style="color: #6c757d; font-size: 14px;">总收益率</div>
            <div style="font-size: 24px; font-weight: bold; color: {'red' if summary['total_return_pct']>0 else 'green'};">{summary['total_return_pct']:+.2f}%</div>
        </div>
        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center;">
            <div style="color: #6c757d; font-size: 14px;">超额收益</div>
            <div style="font-size: 24px; font-weight: bold; color: {'red' if summary['excess_return_pct']>0 else 'green'};">{summary['excess_return_pct']:+.2f}%</div>
        </div>
        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center;">
            <div style="color: #6c757d; font-size: 14px;">最大回撤</div>
            <div style="font-size: 24px; font-weight: bold; color: green;">{summary['max_drawdown_pct']:.2f}%</div>
        </div>
        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center;">
            <div style="color: #6c757d; font-size: 14px;">夏普比率</div>
            <div style="font-size: 24px; font-weight: bold;">{summary['sharpe_ratio']:.2f}</div>
        </div>
        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center;">
            <div style="color: #6c757d; font-size: 14px;">胜率</div>
            <div style="font-size: 24px; font-weight: bold;">{summary['win_rate_pct']:.1f}%</div>
        </div>
        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center;">
            <div style="color: #6c757d; font-size: 14px;">盈亏比</div>
            <div style="font-size: 24px; font-weight: bold;">{summary.get('profit_loss_ratio', 0):.2f}</div>
        </div>
        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center;">
            <div style="color: #6c757d; font-size: 14px;">年化收益</div>
            <div style="font-size: 24px; font-weight: bold;">{summary['cagr_pct']:.2f}%</div>
        </div>
        <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center;">
            <div style="color: #6c757d; font-size: 14px;">交易次数</div>
            <div style="font-size: 24px; font-weight: bold;">{summary['total_trades']}</div>
        </div>
    </div>
    """
    
    # 6. 交易明细表
    trades_df = pd.DataFrame(trades)
    trades_html = trades_df.to_html(index=False, classes="table table-striped", border=0)
    
    # 合并所有图表到HTML
    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <title>{name}({code}) 回测仪表盘</title>
        <script src="https://cdn.plot.ly/plotly-2.20.0.min.js"></script>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ max-width: 1200px; margin: 0 auto; padding: 20px; font-family: "Microsoft Yahei", sans-serif; }}
            .chart {{ margin: 20px 0; }}
        </style>
    </head>
    <body>
        <h1 style="text-align: center; margin-bottom: 30px;">📊 {name}({code}) 策略回测仪表盘</h1>
        {kpi_html}
        <div class="chart">{fig1.to_html(full_html=False, include_plotlyjs=False)}</div>
        <div class="chart">{fig2.to_html(full_html=False, include_plotlyjs=False)}</div>
        <div class="chart">{fig4.to_html(full_html=False, include_plotlyjs=False)}</div>
        <div class="chart">{fig3.to_html(full_html=False, include_plotlyjs=False)}</div>
        <h3>📝 交易明细</h3>
        {trades_html}
        <div style="margin-top: 30px; padding: 15px; background: #fff3cd; border-radius: 8px;">
            <strong>⚠️ 风险提示：</strong> {summary['survivorship_bias_note']}，回测结果仅供参考，不构成任何投资建议。
        </div>
    </body>
    </html>
    """
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"✅ 仪表盘已生成：{os.path.abspath(output_path)}")
    return os.path.abspath(output_path)

if __name__ == "__main__":
    from backtest_engine import BacktestEngine
    engine = BacktestEngine()
    res = engine.run_single("002624", "完美世界", ma_period=200, start_date="2021-01-01")
    generate_dashboard(res)
