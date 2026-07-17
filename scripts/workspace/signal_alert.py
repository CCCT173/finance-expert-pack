#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
信号告警模块
==============
支持价格告警、技术信号告警、资金异动告警，支持多种推送渠道：
- Server酱
- PushPlus
- 企业微信机器人
- 钉钉机器人

用法:
  # 价格告警：股票突破/跌破指定价位时推送
  python signal_alert.py --price 600519:1800:above --webhook your_webhook_url
  
  # MACD金叉/死叉告警
  python signal_alert.py --macd 600519 --channel serverchan --key your_send_key
  
  # 批量监控自选股
  python signal_alert.py --watchlist 自选股.txt --channel wecom --webhook your_webhook
"""
import os
import sys
import argparse
import time
import json
import requests
import pandas as pd
from datetime import datetime
from typing import List, Dict

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from trading_utils import load_price, calc_macd, calc_ma

class AlertChannel:
    """告警通道基类"""
    def send(self, title: str, content: str) -> bool:
        raise NotImplementedError

class ServerChanChannel(AlertChannel):
    """Server酱推送"""
    def __init__(self, send_key: str):
        self.send_key = send_key
        self.url = f"https://sctapi.ftqq.com/{send_key}.send"
    
    def send(self, title: str, content: str) -> bool:
        try:
            data = {"title": title, "desp": content}
            resp = requests.post(self.url, data=data, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            print(f"Server酱推送失败: {e}")
            return False

class PushPlusChannel(AlertChannel):
    """PushPlus推送"""
    def __init__(self, token: str):
        self.token = token
        self.url = "http://www.pushplus.plus/send"
    
    def send(self, title: str, content: str) -> bool:
        try:
            data = {
                "token": self.token,
                "title": title,
                "content": content,
                "template": "markdown"
            }
            resp = requests.post(self.url, json=data, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            print(f"PushPlus推送失败: {e}")
            return False

class WeComChannel(AlertChannel):
    """企业微信机器人"""
    def __init__(self, webhook: str):
        self.webhook = webhook
    
    def send(self, title: str, content: str) -> bool:
        try:
            data = {
                "msgtype": "markdown",
                "markdown": {
                    "content": f"## {title}\n\n{content}"
                }
            }
            resp = requests.post(self.webhook, json=data, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            print(f"企业微信推送失败: {e}")
            return False

class DingTalkChannel(AlertChannel):
    """钉钉机器人"""
    def __init__(self, webhook: str):
        self.webhook = webhook
    
    def send(self, title: str, content: str) -> bool:
        try:
            data = {
                "msgtype": "markdown",
                "markdown": {
                    "title": title,
                    "text": f"## {title}\n\n{content}"
                }
            }
            resp = requests.post(self.webhook, json=data, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            print(f"钉钉推送失败: {e}")
            return False

class SignalDetector:
    """信号检测器"""
    def __init__(self):
        self.alerts = []
    
    def check_price_alert(self, code: str, target_price: float, direction: str) -> Dict:
        """价格告警：above=突破，below=跌破"""
        df = load_price(code)
        if df is None or len(df) < 2:
            return None
        
        df = df.sort_values("date")
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        close = latest["close"]
        name = code  # TODO: 自动获取名称
        
        signal = None
        if direction == "above" and prev["close"] < target_price <= close:
            signal = f"🔴 突破目标价 {target_price}，当前价 {close:.2f}"
        elif direction == "below" and prev["close"] > target_price >= close:
            signal = f"🟢 跌破目标价 {target_price}，当前价 {close:.2f}"
        
        if signal:
            return {
                "code": code,
                "name": name,
                "type": "价格告警",
                "signal": signal,
                "price": close,
                "time": str(latest["date"].date())
            }
        return None
    
    def check_macd_signal(self, code: str) -> Dict:
        """MACD金叉/死叉信号"""
        df = load_price(code)
        if df is None or len(df) < 60:
            return None
        
        df = df.sort_values("date")
        dif, dea, macd = calc_macd(df)
        
        # 金叉：DIF上穿DEA
        if dif.iloc[-2] < dea.iloc[-2] and dif.iloc[-1] > dea.iloc[-1]:
            signal = "🟢 MACD金叉"
        # 死叉：DIF下穿DEA
        elif dif.iloc[-2] > dea.iloc[-2] and dif.iloc[-1] < dea.iloc[-1]:
            signal = "🔴 MACD死叉"
        else:
            return None
        
        return {
            "code": code,
            "name": code,
            "type": "技术信号",
            "signal": signal,
            "price": round(df["close"].iloc[-1], 2),
            "time": str(df["date"].iloc[-1].date())
        }
    
    def check_ma_cross(self, code: str, short: int = 5, long: int = 20) -> Dict:
        """均线交叉信号"""
        df = load_price(code)
        if df is None or len(df) < long + 5:
            return None
        
        df = df.sort_values("date")
        ma_short = calc_ma(df, short)
        ma_long = calc_ma(df, long)
        
        # 金叉：短均线上穿长均线
        if ma_short.iloc[-2] < ma_long.iloc[-2] and ma_short.iloc[-1] > ma_long.iloc[-1]:
            signal = f"🟢 MA{short}上穿MA{long}"
        # 死叉：短均线下穿长均线
        elif ma_short.iloc[-2] > ma_long.iloc[-2] and ma_short.iloc[-1] < ma_long.iloc[-1]:
            signal = f"🔴 MA{short}下穿MA{long}"
        else:
            return None
        
        return {
            "code": code,
            "name": code,
            "type": "技术信号",
            "signal": signal,
            "price": round(df["close"].iloc[-1], 2),
            "time": str(df["date"].iloc[-1].date())
        }

def format_alert_message(alerts: List[Dict]) -> tuple:
    """格式化告警消息"""
    if not alerts:
        return None, None
    
    title = f"📈 股票信号提醒 ({len(alerts)}条)"
    content = []
    content.append(f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    for alert in alerts:
        content.append(f"### {alert['name']}({alert['code']})")
        content.append(f"- **类型**: {alert['type']}")
        content.append(f"- **信号**: {alert['signal']}")
        content.append(f"- **当前价**: {alert['price']}\n")
    
    content.append("---\n")
    content.append("> ⚠️ 信号仅供参考，不构成投资建议")
    
    return title, "\n".join(content)

def load_watchlist(path: str) -> List[str]:
    """加载自选股列表"""
    stocks = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                code = line.split()[0]
                stocks.append(code)
    return stocks

def main():
    parser = argparse.ArgumentParser(description="股票信号告警工具")
    parser.add_argument("--price", type=str, help="价格告警，格式：代码:价格:方向(above/below)，例如 600519:1800:above")
    parser.add_argument("--macd", type=str, help="MACD金叉/死叉告警，传入股票代码")
    parser.add_argument("--ma-cross", type=str, help="均线交叉告警，格式：代码:短周期:长周期，例如 600519:5:20")
    parser.add_argument("--watchlist", type=str, help="批量监控自选股文件路径，每行一个代码")
    parser.add_argument("--interval", type=int, default=60, help="监控间隔（秒），默认60秒")
    
    # 推送通道配置
    parser.add_argument("--channel", type=str, choices=["serverchan", "pushplus", "wecom", "dingtalk", "print"], 
                       default="print", help="推送通道，默认print只打印不推送")
    parser.add_argument("--key", type=str, help="Server酱SendKey或PushPlusToken")
    parser.add_argument("--webhook", type=str, help="企业微信/钉钉机器人webhook地址")
    args = parser.parse_args()
    
    # 初始化推送通道
    channel = None
    if args.channel == "serverchan" and args.key:
        channel = ServerChanChannel(args.key)
    elif args.channel == "pushplus" and args.key:
        channel = PushPlusChannel(args.key)
    elif args.channel == "wecom" and args.webhook:
        channel = WeComChannel(args.webhook)
    elif args.channel == "dingtalk" and args.webhook:
        channel = DingTalkChannel(args.webhook)
    
    detector = SignalDetector()
    
    # 单次检测模式
    if args.price or args.macd or args.ma_cross:
        alerts = []
        if args.price:
            code, price, direction = args.price.split(":")
            alert = detector.check_price_alert(code, float(price), direction)
            if alert:
                alerts.append(alert)
        if args.macd:
            alert = detector.check_macd_signal(args.macd)
            if alert:
                alerts.append(alert)
        if args.ma_cross:
            parts = args.ma_cross.split(":")
            code, short, long = parts[0], int(parts[1]), int(parts[2])
            alert = detector.check_ma_cross(code, short, long)
            if alert:
                alerts.append(alert)
        
        title, content = format_alert_message(alerts)
        if title:
            print(content)
            if channel:
                channel.send(title, content)
        else:
            print("当前无触发信号")
        return
    
    # 持续监控模式
    if args.watchlist:
        stocks = load_watchlist(args.watchlist)
        print(f"🚀 启动持续监控，共监控 {len(stocks)} 只股票，间隔 {args.interval} 秒...")
        
        last_alert_time = {}  # 防止重复告警，同一信号24小时内只推送一次
        
        while True:
            try:
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 检测信号中...")
                alerts = []
                
                for code in stocks:
                    # MACD信号
                    alert = detector.check_macd_signal(code)
                    if alert:
                        key = f"{code}_macd_{alert['time']}"
                        if key not in last_alert_time or time.time() - last_alert_time[key] > 86400:
                            alerts.append(alert)
                            last_alert_time[key] = time.time()
                    
                    # 均线交叉信号
                    alert = detector.check_ma_cross(code, 5, 20)
                    if alert:
                        key = f"{code}_ma5_20_{alert['time']}"
                        if key not in last_alert_time or time.time() - last_alert_time[key] > 86400:
                            alerts.append(alert)
                            last_alert_time[key] = time.time()
                
                if alerts:
                    title, content = format_alert_message(alerts)
                    print(content)
                    if channel:
                        channel.send(title, content)
                else:
                    print("无信号")
                
                time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\n监控停止")
                break
            except Exception as e:
                print(f"检测出错: {e}")
                time.sleep(args.interval)
        return
    
    parser.print_help()

if __name__ == "__main__":
    main()
