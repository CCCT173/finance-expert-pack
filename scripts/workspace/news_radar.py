#!/usr/bin/env python3
"""
新闻雷达 - Web + API 双通道新闻监测
结合 neodata API（结构化数据）和元宝搜索（互联网实时新闻）
发现持仓股重大事件、宏观政策、市场热点
"""
import sys
import os
import re
import json
import subprocess
import urllib.request
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# 统一经 common/gateway 访问（地址可配置、优雅降级，不再硬编码私有运行时）
_COMMON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common")
if _COMMON not in sys.path:
    sys.path.insert(0, _COMMON)
from gateway import query_neodata as call_neodata, web_search_prosearch as web_search

def extract_change(content: str) -> float:
    m = re.search(r'(?:当日涨跌幅|当天涨跌幅|涨跌幅)[:：]?([+-]?\d+\.?\d*)%', content)
    return float(m.group(1)) if m else None

def main():
    now = datetime.now().strftime("%Y/%m/%d %H:%M")
    print(f"\n{'='*50}")
    print(f"📰 新闻雷达 | {now}")
    print(f"{'='*50}")

    stocks = [
        ("002624", "完美世界", "完美世界 股价"),
        ("601069", "西部黄金", "西部黄金 股价"),
        ("600397", "江钨装备", "江钨装备 股价"),
    ]

    all_findings = []

    # === 1. 结构化数据：查询 API 公告 ===
    print("\n[结构化数据 - 公告/研报]")
    for code, name, _ in stocks:
        try:
            # 公告
            gonggao_data = call_neodata(f"{name} 公告")
            recalls = gonggao_data.get("data", {}).get("apiData", {}).get("apiRecall", [])
            for r in recalls:
                content = r.get("content", "")[:300]
                if content:
                    print(f"\n  【{name} 公告】")
                    print(f"  {content}")
                    all_findings.append({"type": "公告", "stock": name, "content": content})
        except Exception as e:
            print(f"  [{name}] 公告查询失败: {e}")

        try:
            # 研报
            yanbao_data = call_neodata(f"{name} 券商 研报")
            recalls = yanbao_data.get("data", {}).get("apiData", {}).get("apiRecall", [])
            for r in recalls:
                content = r.get("content", "")[:300]
                if content:
                    print(f"\n  【{name} 研报】")
                    print(f"  {content}")
                    all_findings.append({"type": "研报", "stock": name, "content": content})
        except Exception as e:
            print(f"  [{name}] 研报查询失败: {e}")

    # === 2. 实时新闻：元宝搜索 ===
    print("\n\n[实时新闻 - 元宝搜索]")

    # 搜索持仓股相关新闻
    for code, name, keyword in stocks:
        print(f"\n  [{name}] 搜索中...")
        result = web_search(keyword, freshness="24h")
        if result.get("success"):
            msg = result.get("message", "")
            if "未找到" in msg or not msg.strip():
                print(f"  → 无相关新闻")
            else:
                # 提取前3条
                lines = msg.split("\n")
                shown = 0
                for line in lines:
                    if line.strip() and shown < 3:
                        print(f"  {line.strip()}")
                        all_findings.append({"type": "新闻", "stock": name, "content": line.strip()})
                        shown += 1
        else:
            print(f"  → 搜索失败: {result.get('message', 'unknown')}")

    # === 3. 市场快讯 ===
    print("\n\n[市场快讯]")
    result = web_search("A股 今日 股市 快讯", freshness="24h")
    if result.get("success"):
        msg = result.get("message", "")
        if "未找到" not in msg and msg.strip():
            lines = msg.split("\n")
            shown = 0
            for line in lines:
                if line.strip() and shown < 5:
                    print(f"  {line.strip()}")
                    shown += 1

    # === 4. 宏观政策 ===
    print("\n\n[宏观政策]")
    result = web_search("中国 宏观 政策 今日", freshness="72h")
    if result.get("success"):
        msg = result.get("message", "")
        if "未找到" not in msg and msg.strip():
            lines = msg.split("\n")
            shown = 0
            for line in lines:
                if line.strip() and shown < 3:
                    print(f"  {line.strip()}")
                    shown += 1

    print(f"\n{'='*50}")
    # 汇总
    if all_findings:
        print(f"\n共发现 {len(all_findings)} 条重要信息:")
        for f in all_findings:
            print(f"  [{f['type']}] {f['stock']}: {f['content'][:80]}...")
    else:
        print("\n✅ 无重大发现")
    print(f"{'='*50}\n")

    return all_findings

if __name__ == "__main__":
    main()
