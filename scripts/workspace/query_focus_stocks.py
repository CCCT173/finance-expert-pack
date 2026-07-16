import os
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

# 统一经 common/gateway 访问 NeoData / 元宝搜索（地址可配置、优雅降级，不再硬编码私有运行时）
_COMMON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common")
if _COMMON not in sys.path:
    sys.path.insert(0, _COMMON)
from gateway import query_neodata as call, web_search_prosearch as web_search

FOCUS_STOCKS = {
    "002624": {"name": "完美世界", "market": "SZ", "sector": "游戏板块"},
    "601069": {"name": "西部黄金", "market": "SH", "sector": "黄金板块"},
    "600397": {"name": "江钨装备", "market": "SH", "sector": "稀有金属板块"},
}

def extract(content, pattern):
    m = re.search(pattern, content)
    return float(m.group(1)) if m else None

print("=" * 60)
print(f"  🎯 聚焦标的深度分析 | {datetime.now().strftime('%Y/%m/%d %H:%M')}")
print("=" * 60)

for code, info in FOCUS_STOCKS.items():
    name = info["name"]
    market = info["market"]
    sector = info["sector"]
    print(f"\n{'─' * 55}")
    print(f"  {name} ({code}.{market}) | {sector}")

    # 1. 行情
    d = call(f'{name}({code}.{market})')
    recalls = d.get('data',{}).get('apiData',{}).get('apiRecall',[])
    price = change = pe = pb = div_yield = None
    for r in recalls:
        c = r.get('content','')
        if price is None: price = extract(c, r'(?:最新价格|当前价格)[:：]?(\d+\.?\d*)')
        if change is None: change = extract(c, r'(?:当日涨跌幅|当天涨跌幅)[:：]?([+-]?\d+\.?\d*)%?')
        if pe is None: pe = extract(c, r'市盈率[:：]?(\d+\.?\d*)')
        if pb is None: pb = extract(c, r'市净率[:：]?(\d+\.?\d*)')
        if div_yield is None: div_yield = extract(c, r'股息率[:：]?(\d+\.?\d*)%?')
    ch_str = f'{change:+.2f}%' if change is not None else 'N/A'
    pe_str = f'{pe:.2f}' if pe is not None else 'N/A'
    pb_str = f'{pb:.2f}' if pb is not None else 'N/A'
    div_str = f'{div_yield:.2f}%' if div_yield is not None else 'N/A'
    print(f"\n  📊 行情:")
    print(f"    价格: {price} | 今日: {ch_str} | PE: {pe_str} | PB: {pb_str} | 股息率: {div_str}")

    # 2. 公告/事件
    d2 = call(f'{name} 公告')
    recalls2 = d2.get('data',{}).get('apiData',{}).get('apiRecall',[])
    shown = 0
    for r in recalls2:
        c = r.get('content','')[:300]
        if c and shown < 2:
            print(f"\n  📋 公告: {c}")
            shown += 1

    # 3. 研报
    d3 = call(f'{name} 券商 研报 机构评级')
    recalls3 = d3.get('data',{}).get('apiData',{}).get('apiRecall',[])
    for r in recalls3:
        c = r.get('content','')
        if c and '目标价' in c:
            target = re.search(r'目标价[为:：]?\s*(\d+\.?\d*)元', c)
            rating = re.search(r'(买入|增持|中性|减持|卖出)', c)
            if target or rating:
                parts = []
                if target: parts.append(f"目标价:{target.group(1)}元")
                if rating: parts.append(f"评级:{rating.group(1)}")
                print(f"\n  📝 研报: {' | '.join(parts)}")
            break

    # 4. 新闻
    result = web_search(f"{name} 今日", freshness="24h")
    if result and "未找到" not in result:
        lines = [l.strip() for l in result.split("\n") if l.strip().startswith("**")]
        if lines:
            print(f"\n  📰 今日新闻:")
            for line in lines[:2]:
                print(f"    {line}")

    # 5. 板块对比
    sector_d = call(sector)
    sector_recalls = sector_d.get('data',{}).get('apiData',{}).get('apiRecall',[])
    sector_change = None
    for r in sector_recalls:
        c = r.get('content','')
        sector_change = extract(c, r'(?:当日涨跌幅|涨跌幅)[:：]?([+-]?\d+\.?\d*)%?')
        if sector_change is not None: break
    if sector_change is not None and change is not None:
        div = change - sector_change
        div_str = f"{div:+.2f}%"
        if div <= -1.5: flag = "⚠️ 弱于板块"
        elif div >= 1.5: flag = "⚡ 强于板块"
        else: flag = "✓ 正常"
        print(f"\n  🔍 板块对比: 个股 {ch_str} | {sector} {sector_change:+.2f}% | 背离 {div_str} {flag}")

print(f"\n{'=' * 60}")
print("  ✅ 聚焦标的分析完成")
print(f"{'=' * 60}\n")
