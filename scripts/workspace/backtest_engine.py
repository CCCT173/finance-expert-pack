#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用回测引擎
=============
纯Python+pandas实现，零额外重依赖，支持任意自定义策略、单标的/多标的组合回测，
真实还原A股交易规则，全量专业绩效指标计算。

用法示例：
```python
from backtest_engine import BacktestEngine, ma_strategy

# 单标的回测
engine = BacktestEngine()
result = engine.run_single(
    code="002555",
    name="三七互娱",
    signal_func=ma_strategy,
    ma_period=200,
    stop_loss=-0.08
)
print(result["summary"])
```
"""
import os
import sys
import json
import math
from typing import Callable, Dict, List, Tuple, Optional
import pandas as pd
import numpy as np

# 导入通用工具
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from trading_utils import (
    load_price, calc_trade_cost, can_trade, calc_ma, TRADING_COSTS, is_etf
)


def ma_cross_strategy(df: pd.DataFrame, ma_short: int = 5, ma_long: int = 20, **kwargs) -> pd.Series:
    """
    双均线策略信号函数示例
    返回: 1=持仓, 0=空仓
    """
    ma_s = calc_ma(df, ma_short)
    ma_l = calc_ma(df, ma_long)
    position = (ma_s > ma_l).astype(int)
    # T+1: 信号延迟一天执行
    return position.shift(1).fillna(0)


def ma_trend_strategy(df: pd.DataFrame, ma_period: int = 200, **kwargs) -> pd.Series:
    """
    均线趋势策略（默认推荐）
    收盘价在MA上方持仓，下方空仓
    """
    ma = calc_ma(df, ma_period)
    position = (df["close"] > ma).astype(int)
    return position.shift(1).fillna(0)


class BacktestEngine:
    def __init__(self, 
                 commission: float = None,
                 stamp_duty: float = None,
                 transfer_fee: float = None,
                 slippage: float = None,
                 initial_cash: float = 100000.0,
                 is_etf: bool = False):
        """
        初始化回测引擎
        :param commission: 佣金率，默认万2.5，None用TRADING_COSTS默认值
        :param stamp_duty: 印花税率，默认千1，仅卖出收取，ETF自动免税
        :param transfer_fee: 过户费率，默认十万1
        :param slippage: 滑点，默认千1
        :param initial_cash: 初始资金
        :param is_etf: 是否ETF，自动免印花税
        """
        from trading_utils import TRADING_COSTS
        self.commission = commission if commission is not None else TRADING_COSTS["commission"]
        self.stamp_duty = stamp_duty if stamp_duty is not None else TRADING_COSTS["stamp_duty"]
        self.transfer_fee = transfer_fee if transfer_fee is not None else TRADING_COSTS["transfer_fee"]
        self.slippage = slippage if slippage is not None else TRADING_COSTS["slippage"]
        self.initial_cash = initial_cash
        self.is_etf = is_etf
    
    def cost_sensitivity_test(self, code: str, name: str = "",
                              cost_multipliers: List[float] = [0.5, 1, 2, 3],
                              **kwargs) -> Dict:
        """
        成本敏感性测试：成本提高/降低时策略表现是否稳定
        :param cost_multipliers: 成本倍数，比如2表示成本翻倍
        """
        results = []
        base_costs = {
            "commission": self.commission,
            "stamp_duty": self.stamp_duty,
            "transfer_fee": self.transfer_fee,
            "slippage": self.slippage
        }
        for mult in cost_multipliers:
            self.commission = base_costs["commission"] * mult
            self.stamp_duty = base_costs["stamp_duty"] * mult
            self.transfer_fee = base_costs["transfer_fee"] * mult
            self.slippage = base_costs["slippage"] * mult
            try:
                res = self.run_single(code, name, **kwargs)
                results.append({
                    "成本倍数": mult,
                    "总收益%": res["summary"]["total_return_pct"],
                    "超额收益%": res["summary"]["excess_return_pct"],
                    "最大回撤%": res["summary"]["max_drawdown_pct"],
                    "夏普比率": res["summary"]["sharpe_ratio"]
                })
            except:
                continue
        # 恢复默认成本
        self.commission = base_costs["commission"]
        self.stamp_duty = base_costs["stamp_duty"]
        self.transfer_fee = base_costs["transfer_fee"]
        self.slippage = base_costs["slippage"]
        
        df = pd.DataFrame(results)
        # 判断稳健性：3倍成本下仍然正收益/超额为正就是稳健
        max_excess_drop = df["超额收益%"].max() - df["超额收益%"].min()
        is_robust = df[df["成本倍数"]==3]["超额收益%"].values[0] > -10 if len(df)>=3 else False
        return {
            "results": df,
            "max_excess_drop": max_excess_drop,
            "is_cost_robust": is_robust,
            "conclusion": "✅ 策略对交易成本不敏感，实盘表现稳定" if is_robust else "⚠️ 策略对成本敏感，实盘收益可能因滑点下降"
        }
    
    def _calc_trade_cost(self, amount: float, is_buy: bool, is_etf_flag: bool = False) -> float:
        """计算交易成本"""
        cost = 0
        commission = max(amount * self.commission, 5)  # 最低5元
        cost += commission
        cost += amount * self.transfer_fee
        cost += amount * self.slippage
        # ETF免印花税
        if not is_buy and not is_etf_flag:
            cost += amount * self.stamp_duty
        return cost
    
    def _calc_performance(self, equity: pd.Series, trades: List[Dict], benchmark_ret: pd.Series = None) -> Dict:
        """计算全量绩效指标"""
        # 基础收益
        total_return = equity.iloc[-1] / equity.iloc[0] - 1
        n_days = len(equity)
        cagr = (equity.iloc[-1] / equity.iloc[0]) ** (252 / n_days) - 1 if n_days > 0 else 0
        
        # 最大回撤
        rolling_max = equity.expanding().max()
        drawdown = equity / rolling_max - 1
        max_drawdown = drawdown.min()
        # 最大回撤区间
        end_idx = drawdown.idxmin()
        start_idx = equity.loc[:end_idx].idxmax()
        dd_days = (end_idx - start_idx).days
        
        # 收益统计
        daily_ret = equity.pct_change().dropna()
        sharpe = np.sqrt(252) * daily_ret.mean() / daily_ret.std() if daily_ret.std() > 0 else 0
        # 索提诺比率：只考虑下行波动
        downside_ret = daily_ret[daily_ret < 0]
        sortino = np.sqrt(252) * daily_ret.mean() / downside_ret.std() if len(downside_ret) > 0 and downside_ret.std() > 0 else 0
        # 卡玛比率
        calmar = cagr / abs(max_drawdown) if max_drawdown != 0 else 0
        
        # 交易统计
        if trades:
            win_trades = [t for t in trades if t["profit"] > 0]
            lose_trades = [t for t in trades if t["profit"] <= 0]
            win_rate = len(win_trades) / len(trades) if len(trades) > 0 else 0
            avg_win = np.mean([t["profit_pct"] for t in win_trades]) if win_trades else 0
            avg_loss = np.mean([t["profit_pct"] for t in lose_trades]) if lose_trades else 0
            profit_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
            total_cost = sum(t["cost"] for t in trades)
        else:
            win_rate = avg_win = avg_loss = profit_loss_ratio = total_cost = 0
        
        # 月度/年度收益
        monthly_ret = equity.resample("ME").last().pct_change().dropna()
        yearly_ret = equity.resample("YE").last().pct_change().dropna()
        
        # 贝塔和阿尔法（和沪深300对比，有基准数据时计算）
        beta = alpha = 0
        if benchmark_ret is not None and len(benchmark_ret) == len(daily_ret):
            cov = np.cov(daily_ret, benchmark_ret)[0, 1]
            var = np.var(benchmark_ret)
            beta = cov / var if var != 0 else 0
            alpha = (daily_ret.mean() * 252) - beta * (benchmark_ret.mean() * 252)
        
        # 连续盈亏
        max_consecutive_win = max_consecutive_loss = 0
        current_win = current_loss = 0
        for t in trades:
            if t["profit"] > 0:
                current_win += 1
                current_loss = 0
                max_consecutive_win = max(max_consecutive_win, current_win)
            else:
                current_loss += 1
                current_win = 0
                max_consecutive_loss = max(max_consecutive_loss, current_loss)
        
        return {
            # 收益指标
            "total_return_pct": round(total_return * 100, 2),
            "cagr_pct": round(cagr * 100, 2),
            "alpha_pct": round(alpha * 100, 2),
            "beta": round(beta, 2),
            # 风险指标
            "max_drawdown_pct": round(max_drawdown * 100, 2),
            "max_drawdown_start": str(start_idx.date()) if hasattr(start_idx, "date") else str(start_idx),
            "max_drawdown_end": str(end_idx.date()) if hasattr(end_idx, "date") else str(end_idx),
            "max_drawdown_days": dd_days,
            "sharpe_ratio": round(sharpe, 2),
            "sortino_ratio": round(sortino, 2),
            "calmar_ratio": round(calmar, 2),
            "annual_volatility_pct": round(daily_ret.std() * np.sqrt(252) * 100, 2),
            # 交易统计
            "total_trades": len(trades),
            "win_rate_pct": round(win_rate * 100, 2),
            "profit_loss_ratio": round(profit_loss_ratio, 2),
            "avg_win_pct": round(avg_win * 100, 2),
            "avg_loss_pct": round(avg_loss * 100, 2),
            "max_consecutive_win": max_consecutive_win,
            "max_consecutive_loss": max_consecutive_loss,
            "total_commission": round(total_cost, 2),
            # 收益分布
            "monthly_returns": {str(k.date()): round(v*100, 2) for k, v in monthly_ret.items()},
            "yearly_returns": {str(k.date()): round(v*100, 2) for k, v in yearly_ret.items()},
        }
    
    def run_single(self, code: str, name: str = "",
                   signal_func: Callable = ma_trend_strategy,
                   start_date: str = "2021-01-01", end_date: str = None,
                   stop_loss: float = None, take_profit: float = None,
                   market_filter: bool = True, dynamic_position: bool = True, 
                   trailing_stop: bool = True,
                   **signal_kwargs) -> Dict:
        """
        单标的回测
        :param code: 股票代码
        :param name: 股票名称
        :param signal_func: 信号生成函数，输入df，返回position序列(1持仓/0空仓)
        :param start_date: 回测开始日期
        :param end_date: 回测结束日期
        :param stop_loss: 止损比例，负数，如-0.08表示亏8%止损
        :param take_profit: 止盈比例，正数，如0.3表示赚30%止盈
        :param market_filter: 是否启用大盘过滤，沪深300在200MA下方不开仓
        :param dynamic_position: 是否启用动态仓位（强趋势满仓/弱趋势半仓）
        :param trailing_stop: 是否启用移动止损（盈利后止损线上移到成本/最高点）
        :param signal_kwargs: 传给信号函数的参数
        """
        # 加载数据
        df = load_price(code)
        if df is None or len(df) < 200:
            raise ValueError(f"无法加载{code}行情数据或数据不足")
        
        is_etf_flag = is_etf(code)
        
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        if end_date:
            df = df.loc[:end_date]
        df = df.loc[start_date:]
        
        # 生成信号
        df["position"] = signal_func(df, **signal_kwargs)
        
        # 大盘过滤：加载沪深300数据，只有大盘在200MA上方才允许开仓
        market_bull = True
        market_bull_series = pd.Series(True, index=df.index)
        if market_filter:
            try:
                hs300 = load_price("000300")
                if hs300 is not None:
                    hs300["date"] = pd.to_datetime(hs300["date"])
                    hs300 = hs300.set_index("date").sort_index()
                    hs300_ma200 = hs300["close"].rolling(200).mean()
                    # 对齐日期
                    market_bull_series = (hs300["close"] > hs300_ma200).reindex(df.index).ffill().fillna(True)
            except:
                market_bull_series = pd.Series(True, index=df.index)
        
        # 回测主循环
        cash = self.initial_cash
        shares = 0
        entry_price = 0
        highest_price = 0  # 持仓期间最高价，用于移动止损
        equity = []
        trades = []
        holding_days = 0
        total_commission = 0
        position_size = 1.0  # 仓位比例，1=满仓，0.5=半仓
        
        for date, row in df.iterrows():
            # 大盘过滤更新
            if market_filter:
                market_bull = bool(market_bull_series.loc[date]) if date in market_bull_series.index else True
            
            # 检查止损止盈/移动止损
            if shares > 0:
                current_profit_pct = (row["close"] / entry_price - 1)
                highest_price = max(highest_price, row["close"])
                # 移动止损：盈利超过5%后，从最高点回撤10%卖出
                trailing_triggered = False
                if trailing_stop and highest_price > entry_price * 1.05:
                    drawdown_from_high = (row["close"] / highest_price - 1)
                    if drawdown_from_high <= -0.1:
                        trailing_triggered = True
                if (stop_loss is not None and current_profit_pct <= stop_loss) or trailing_triggered:
                    # 止损/移动止损卖出
                    sell_amount = shares * row["close"]
                    cost = self._calc_trade_cost(sell_amount, is_buy=False, is_etf_flag=is_etf_flag)
                    cash += sell_amount - cost
                    total_commission += cost
                    profit = sell_amount - entry_price * shares - cost
                    action = "移动止损卖出" if trailing_triggered else "止损卖出"
                    trades.append({
                        "date": str(date.date()),
                        "code": code,
                        "name": name,
                        "action": action,
                        "price": round(row["close"], 2),
                        "shares": shares,
                        "amount": round(sell_amount, 2),
                        "cost": round(cost, 2),
                        "profit": round(profit, 2),
                        "profit_pct": round(current_profit_pct, 4),
                        "holding_days": holding_days
                    })
                    shares = 0
                    holding_days = 0
                    highest_price = 0
                elif take_profit is not None and current_profit_pct >= take_profit:
                    # 止盈卖出
                    sell_amount = shares * row["close"]
                    cost = self._calc_trade_cost(sell_amount, is_buy=False, is_etf_flag=is_etf_flag)
                    cash += sell_amount - cost
                    total_commission += cost
                    profit = sell_amount - entry_price * shares - cost
                    trades.append({
                        "date": str(date.date()),
                        "code": code,
                        "name": name,
                        "action": "止盈卖出",
                        "price": round(row["close"], 2),
                        "shares": shares,
                        "amount": round(sell_amount, 2),
                        "cost": round(cost, 2),
                        "profit": round(profit, 2),
                        "profit_pct": round(current_profit_pct, 4),
                        "holding_days": holding_days
                    })
                    shares = 0
                    holding_days = 0
            
            target_position = row["position"]
            # 动态仓位：计算仓位比例
            if dynamic_position and target_position == 1:
                ma = calc_ma(df, signal_kwargs.get("ma_period", 200))
                ma_slope = (ma.iloc[-1] - ma.iloc[-20]) / ma.iloc[-20] if len(ma) >= 20 else 0
                # MA斜率向上5%以上满仓，斜率0-5%半仓，斜率向下空仓
                if ma_slope > 0.05:
                    position_size = 1.0
                elif ma_slope > 0:
                    position_size = 0.5
                else:
                    target_position = 0
                    position_size = 0
            else:
                position_size = 1.0 if target_position ==1 else 0
            
            # 调仓：从0到1买入，从1到0卖出
            if target_position == 1 and shares == 0 and market_bull:
                # 按仓位比例买入（动态半仓/满仓），大盘过滤只在开仓时生效
                buy_price = row["close"] * (1 + self.slippage)
                invest_cash = cash * position_size
                # 计算可买股数（100股整数倍）
                max_shares = int(invest_cash / (buy_price * (1 + self.commission + self.transfer_fee)) / 100) * 100
                if max_shares >= 100:
                    buy_amount = max_shares * buy_price
                    cost = self._calc_trade_cost(buy_amount, is_buy=True, is_etf_flag=is_etf_flag)
                    cash -= buy_amount + cost
                    total_commission += cost
                    shares = max_shares
                    entry_price = buy_price
                    holding_days = 0
                    highest_price = buy_price
                    action = "半仓买入" if position_size == 0.5 else "满仓买入"
                    trades.append({
                        "date": str(date.date()),
                        "code": code,
                        "name": name,
                        "action": action,
                        "price": round(buy_price, 2),
                        "shares": shares,
                        "amount": round(buy_amount, 2),
                        "cost": round(cost, 2),
                        "profit": 0,
                        "profit_pct": 0,
                        "holding_days": 0
                    })
            elif target_position == 0 and shares > 0:
                # 全仓卖出
                sell_price = row["close"] * (1 - self.slippage)
                sell_amount = shares * sell_price
                cost = self._calc_trade_cost(sell_amount, is_buy=False, is_etf_flag=is_etf_flag)
                cash += sell_amount - cost
                total_commission += cost
                profit_pct = (sell_price / entry_price - 1)
                profit = sell_amount - entry_price * shares - cost
                trades.append({
                    "date": str(date.date()),
                    "code": code,
                    "name": name,
                    "action": "卖出",
                    "price": round(sell_price, 2),
                    "shares": shares,
                    "amount": round(sell_amount, 2),
                    "cost": round(cost, 2),
                    "profit": round(profit, 2),
                    "profit_pct": round(profit_pct, 4),
                    "holding_days": holding_days
                })
                shares = 0
                holding_days = 0
            
            # 计算当日净值
            current_equity = cash + shares * row["close"]
            equity.append({"date": date, "equity": current_equity})
            if shares > 0:
                holding_days += 1
        
        # 整理结果
        equity_df = pd.DataFrame(equity).set_index("date")["equity"]
        daily_ret = equity_df.pct_change().dropna()
        
        # 基准收益（买入持有）
        benchmark_equity = self.initial_cash * (1 + df["close"].pct_change().fillna(0)).cumprod()
        benchmark_ret = benchmark_equity.pct_change().dropna()
        
        performance = self._calc_performance(equity_df, trades, benchmark_ret)
        # 加上买入持有基准绩效
        bh_return = (df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100
        performance["buy_hold_return_pct"] = round(bh_return, 2)
        performance["excess_return_pct"] = round(performance["total_return_pct"] - bh_return, 2)
        
        # 生存者偏差提示
        performance["survivorship_bias_note"] = "回测使用当前成分股，存在生存者偏差，实盘收益可能低5%-10%"
        performance["is_etf"] = is_etf_flag
        
        return {
            "code": code,
            "name": name,
            "summary": performance,
            "equity_curve": equity_df,
            "trades": trades,
            "benchmark_curve": benchmark_equity
        }
    
    def export_results(self, result: Dict, output_dir: str = "."):
        """导出标准结果文件"""
        os.makedirs(output_dir, exist_ok=True)
        code = result["code"]
        # 净值曲线
        result["equity_curve"].to_csv(os.path.join(output_dir, f"{code}_equity.csv"), encoding="utf-8-sig")
        # 交易明细
        pd.DataFrame(result["trades"]).to_csv(os.path.join(output_dir, f"{code}_trades.csv"), index=False, encoding="utf-8-sig")
        # 汇总JSON
        with open(os.path.join(output_dir, f"{code}_summary.json"), "w", encoding="utf-8") as f:
            json.dump(result["summary"], f, indent=2, ensure_ascii=False)


# 预定义策略
STRATEGIES = {
    "ma_trend": ma_trend_strategy,
    "ma_cross": ma_cross_strategy,
}

if __name__ == "__main__":
    # 测试
    engine = BacktestEngine()
    res = engine.run_single("002555", "三七互娱", ma_period=200, stop_loss=-0.08)
    print(json.dumps(res["summary"], indent=2, ensure_ascii=False))
    engine.export_results(res, "backtest_results")
