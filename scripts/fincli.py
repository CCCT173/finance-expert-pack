#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fincli 统一命令行入口
用法:
  fincli backtest <code> [--ma 200] [--stoploss -0.08] [--start 2021-01-01]
  fincli screener [--ma-long|--macd-golden|--roe 15] [--top 20]
  fincli review [--watchlist watchlist.txt]
  fincli walkforward <code>
"""
import sys
import os
import argparse

sys.path.append(os.path.join(os.path.dirname(__file__), "workspace"))

def main():
    parser = argparse.ArgumentParser(description="finance-expert-pack 量化工具命令行")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # backtest 回测命令
    bt_parser = subparsers.add_parser("backtest", help="回测单只标的")
    bt_parser.add_argument("code", type=str, help="股票/ETF代码")
    bt_parser.add_argument("--name", type=str, default="", help="标的名称")
    bt_parser.add_argument("--ma", type=int, default=200, help="MA周期，默认200")
    bt_parser.add_argument("--stoploss", type=float, default=-0.08, help="止损比例，默认-0.08即8%止损")
    bt_parser.add_argument("--takeprofit", type=float, default=None, help="止盈比例")
    bt_parser.add_argument("--start", type=str, default="2021-01-01", help="开始日期")
    bt_parser.add_argument("--end", type=str, default=None, help="结束日期")
    
    # screener 选股命令
    scr_parser = subparsers.add_parser("screener", help="条件选股")
    scr_parser.add_argument("--ma-long", action="store_true", help="均线多头排列")
    scr_parser.add_argument("--macd-golden", action="store_true", help="MACD金叉")
    scr_parser.add_argument("--breakout", type=int, default=None, help="N日新高")
    scr_parser.add_argument("--roe", type=float, default=None, help="ROE高于阈值")
    scr_parser.add_argument("--top", type=int, default=20, help="输出前N个")
    
    # review 复盘命令
    rv_parser = subparsers.add_parser("review", help="每日复盘")
    rv_parser.add_argument("--watchlist", type=str, default=None, help="自选股文件路径")
    rv_parser.add_argument("--date", type=str, default=None, help="复盘日期")
    
    # walkforward 滚动验证命令
    wf_parser = subparsers.add_parser("walkforward", help="Walk Forward滚动验证")
    wf_parser.add_argument("code", type=str, help="标的代码")
    wf_parser.add_argument("--name", type=str, default="", help="标的名称")
    
    # sector 板块回测命令
    sec_parser = subparsers.add_parser("sector", help="板块批量回测")
    sec_parser.add_argument("sector", type=str, help="板块名称：游戏/半导体/新能源/医药/消费")
    sec_parser.add_argument("--ma", type=int, default=200, help="MA周期")
    sec_parser.add_argument("--start", type=str, default="2021-01-01", help="开始日期")
    
    args = parser.parse_args()
    
    if args.command == "backtest":
        from backtest_engine import BacktestEngine
        engine = BacktestEngine()
        res = engine.run_single(args.code, args.name, ma_period=args.ma, 
                              stop_loss=args.stoploss, take_profit=args.takeprofit,
                              start_date=args.start, end_date=args.end)
        s = res["summary"]
        print(f"\n📊 {args.name}({args.code}) {args.ma}MA策略回测结果")
        print("="*60)
        print(f"策略收益: {s['total_return_pct']:+.2f}% | 持有收益: {s['buy_hold_return_pct']:+.2f}% | 超额: {s['excess_return_pct']:+.2f}%")
        print(f"最大回撤: {s['max_drawdown_pct']:.2f}% | 夏普: {s['sharpe_ratio']:.2f} | 胜率: {s['win_rate_pct']:.1f}%")
        print(f"交易次数: {s['total_trades']}次 | 总手续费: {s['total_commission']:.2f}元")
        if s["is_etf"]:
            print("ℹ️  ETF自动免印花税")
        print(f"⚠️  {s['survivorship_bias_note']}")
        engine.export_results(res, ".")
        print(f"\n✅ 结果已导出到当前目录")
    
    elif args.command == "screener":
        from stock_screener import screen_ma_long, screen_macd_golden
        print("\n🔍 正在选股...")
        if args.ma_long:
            res = screen_ma_long()
        elif args.macd_golden:
            res = screen_macd_golden()
        else:
            print("请指定筛选条件：--ma-long/--macd-golden/--breakout N/--roe N")
            return
        res = sorted(res, key=lambda x: x["pct_chg"], reverse=True)[:args.top]
        print(f"\n选出{len(res)}只股票：")
        print(f"{'代码':<8} {'名称':<10} {'现价':<8} {'涨跌幅%':<8}")
        print("-"*40)
        for s in res:
            print(f"{s['code']:<8} {s['name']:<10} {s['close']:<8.2f} {s['pct_chg']:<+8.2f}")
    
    elif args.command == "review":
        from daily_review import generate_review
        report = generate_review(watchlist_path=args.watchlist, date=args.date)
        print(report)
    
    elif args.command == "walkforward":
        from walk_forward import walk_forward_test
        walk_forward_test(args.code, args.name)
    elif args.command == "sector":
        sys.path.append(os.path.join(os.path.dirname(__file__), "workspace"))
        from sector_backtest import backtest_sector
        backtest_sector(args.sector, args.ma, args.start)
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
