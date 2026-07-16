import os
"""
智兔数服集成监控模块
功能：实时行情 + 指数技术面 + 涨停股池监控
"""
import requests
import json
import sys
from datetime import datetime, date
from typing import Optional

sys.stdout.reconfigure(encoding='utf-8')

# 鉴权 Token 来自环境变量 ZHITU_TOKEN（必填）。未配置时所有接口将返回 None，
# 但不会崩溃；下方会在调用前给出明确告警，方便排查。
TOKEN = os.environ.get("ZHITU_TOKEN", "")
BASE = "https://api.zhituapi.com"

if not TOKEN:
    print("⚠️ 警告：环境变量 ZHITU_TOKEN 未设置，智兔数服接口将无法鉴权（返回空）。"
          "请在运行前配置：set ZHITU_TOKEN=你的token", file=sys.stderr)

# ===================== 核心接口 =====================

def get_stock_realtime(code: str) -> Optional[dict]:
    """获取股票实时行情（使用6位代码，无后缀）"""
    url = f"{BASE}/hs/real/time/{code}?token={TOKEN}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None


def get_index_realtime(code: str) -> Optional[dict]:
    """获取指数实时行情（如000001.SH）"""
    url = f"{BASE}/hz/real/ssjy/{code}?token={TOKEN}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None


def get_index_ma(code: str, period: str = "d", limit: int = 5) -> Optional[list]:
    """获取指数MA均线（如000001.SH/d）"""
    url = f"{BASE}/hz/history/ma/{code}/{period}?token={TOKEN}&limit={limit}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None


def get_index_macd(code: str, period: str = "d", limit: int = 5) -> Optional[list]:
    """获取指数MACD（如000001.SH/d）"""
    url = f"{BASE}/hz/history/macd/{code}/{period}?token={TOKEN}&limit={limit}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None


def get_last_trading_day() -> str:
    """获取最近交易日（兼容节假日）"""
    today = date.today()
    # 简单逻辑：如果是周一到周五，看今天是否有数据，否则回退一天
    weekday = today.weekday()  # 0=周一, 6=周日
    if weekday == 6:  # 周日
        return (today - __import__('datetime').timedelta(days=2)).strftime("%Y-%m-%d")
    elif weekday == 0:  # 周一
        return (today - __import__('datetime').timedelta(days=3)).strftime("%Y-%m-%d")
    else:
        return today.strftime("%Y-%m-%d")


def get_zt_pool(trade_date: str = None) -> Optional[list]:
    """获取涨停股池（格式：YYYY-MM-DD）"""
    if trade_date is None:
        # 盘前自动用上一个交易日
        now = datetime.now()
        if now.hour < 15:  # 下午3点前，用上一个交易日
            weekday = date.today().weekday()
            if weekday == 0:  # 周一
                trade_date = (date.today() - __import__('datetime').timedelta(days=3)).strftime("%Y-%m-%d")
            elif weekday == 6:  # 周日
                trade_date = (date.today() - __import__('datetime').timedelta(days=2)).strftime("%Y-%m-%d")
            else:
                trade_date = (date.today() - __import__('datetime').timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            trade_date = date.today().strftime("%Y-%m-%d")
    url = f"{BASE}/hs/pool/ztgc/{trade_date}?token={TOKEN}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None


# ===================== 格式化输出 =====================

def fmt_stock(data: dict, code: str, name: str = "") -> str:
    """格式化股票行情"""
    if not data:
        return f"❌ {code} 获取失败"
    p = data.get("p", "N/A")
    pc = data.get("pc", 0)
    trend = "🔴" if pc < 0 else "🟢"
    ud = data.get("ud", 0)
    tr = data.get("tr", 0)  # 换手率
    cje = data.get("cje", 0)  # 成交额
    cje_str = f"{cje/1e8:.2f}亿" if cje > 0 else "N/A"
    pe = data.get("pe", "N/A")
    return (f"{trend} {code} {name}\n"
            f"   价格: {p} | 涨跌: {ud:+.2f} ({pc:+.2f}%)\n"
            f"   换手率: {tr:.2f}% | 成交额: {cje_str} | PE: {pe}")


def fmt_index(data: dict, code: str, name: str = "") -> str:
    """格式化指数行情"""
    if not data:
        return f"❌ 指数 {code} 获取失败"
    p = data.get("p", 0)
    pc = data.get("pc", 0)
    o = data.get("o", 0)
    h = data.get("h", 0)
    l = data.get("l", 0)
    cje = data.get("cje", 0)
    cje_str = f"{cje/1e8:.2f}亿" if cje > 0 else "N/A"
    trend = "🔴" if pc < 0 else "🟢"
    return (f"{trend} {name} ({code})\n"
            f"   最新: {p} ({pc:+.2f}%) | 开盘: {o} | 最高: {h} | 最低: {l}\n"
            f"   成交额: {cje_str}")


def fmt_ma(ma_list: list, name: str = "上证指数") -> str:
    """格式化MA均线"""
    if not ma_list:
        return f"❌ {name} MA获取失败"
    latest = ma_list[-1]
    t = latest.get("t", "")
    ma_keys = ["ma3", "ma5", "ma10", "ma20", "ma60"]
    ma_str = " | ".join([f"MA{k[2:]}={latest.get(k, 0):.2f}" for k in ma_keys if latest.get(k) is not None])
    return f"📊 {name} MA（{t[:10]}）\n   {ma_str}"


def fmt_macd(macd_list: list, name: str = "上证指数") -> str:
    """格式化MACD"""
    if not macd_list:
        return f"❌ {name} MACD获取失败"
    latest = macd_list[-1]
    t = latest.get("t", "")
    diff = latest.get("diff", 0)
    dea = latest.get("dea", 0)
    macd = latest.get("macd", 0)
    signal = "🟢多头" if macd > 0 else "🔴空头"
    return (f"📊 {name} MACD（{t[:10]}）\n"
            f"   {signal} | DIFF={diff:.3f} | DEA={dea:.3f} | MACD={macd:.3f}")


def fmt_zt_pool(pool: list, my_codes: list = None) -> str:
    """格式化涨停股池"""
    if not pool:
        return "❌ 涨停股池获取失败"
    total = len(pool)
    # 统计
    fbt_times = {}
    for s in pool:
        fbt = s.get("fbt", "")
        if fbt:
            fbt_times[fbt[:2]] = fbt_times.get(fbt[:2], 0) + 1
    early_count = sum(v for k, v in fbt_times.items() if int(k) <= 9)
    mid_count = sum(v for k, v in fbt_times.items() if 9 < int(k) <= 10)
    late_count = sum(v for k, v in fbt_times.items() if int(k) > 10)

    lines = [f"🔥 涨停股池（{total}只）"]
    lines.append(f"   早盘封板(9:xx): {early_count}只 | 盘中(10:xx): {mid_count}只 | 午盘(>10:xx): {late_count}只")

    if my_codes:
        lines.append(f"\n   📌 自选股涨停状态：")
        found = False
        for s in pool:
            dm = s.get("dm", "").replace("sz", "").replace("sh", "").upper()
            for mc in my_codes:
                if mc in dm or dm in mc:
                    lines.append(f"   🔥 {s.get('dm')} {s.get('mc')} 涨停！")
                    found = True
        if not found:
            lines.append(f"   自选股今日未涨停 ✅")

    # 最早封板的前3只
    lines.append(f"\n   最早封板（前3只）：")
    for s in pool[:3]:
        lines.append(f"   🏆 {s.get('fbt')} {s.get('dm')} {s.get('mc')} 成交额{s.get('cje',0)/1e8:.1f}亿")

    return "\n".join(lines)


# ===================== 主监控函数 =====================

def monitor_portfolio(codes_names: list, index_codes: list = None, my_codes: list = None):
    """
    综合盯盘输出
    codes_names: [(code, name), ...]
    index_codes: [("000001.SH", "上证指数"), ("399006.SZ", "创业板"), ...]
    """
    print(f"\n{'='*50}")
    print(f"【智兔数服 综合监控】{datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*50}")

    # 1. 个股实时
    print("\n## 📈 个股实时行情")
    for code, name in codes_names:
        data = get_stock_realtime(code)
        print(fmt_stock(data, code, name))

    # 2. 指数实时
    if index_codes:
        print("\n## 📊 指数实时")
        for code, name in index_codes:
            data = get_index_realtime(code)
            print(fmt_index(data, code, name))

    # 3. 指数技术面（默认用上证）
    if index_codes:
        idx_code = index_codes[0][0] if index_codes else "000001.SH"
        idx_name = index_codes[0][1] if index_codes else "上证指数"
        print(f"\n## 📉 {idx_name} 技术面")
        ma_data = get_index_ma(idx_code, "d", 3)
        macd_data = get_index_macd(idx_code, "d", 3)
        if ma_data:
            print(fmt_ma(ma_data, idx_name))
        if macd_data:
            print(fmt_macd(macd_data, idx_name))

    # 4. 涨停股池
    print(f"\n## 🔥 涨停股池")
    zt_data = get_zt_pool()
    print(fmt_zt_pool(zt_data, my_codes))

    print(f"\n{'='*50}")


# ===================== 单票查询快捷函数 =====================

def quick_look(code: str, name: str = ""):
    """快速查询单只股票"""
    data = get_stock_realtime(code)
    print(fmt_stock(data, code, name))
    # 也检查是否涨停
    zt_data = get_zt_pool()
    if zt_data:
        for s in zt_data:
            dm = s.get("dm", "").replace("sz", "").replace("sh", "").upper()
            if code.upper() in dm or dm in code.upper():
                print(f"\n🔥 {s.get('dm')} {s.get('mc')} 今日涨停！")
                print(f"   首次封板: {s.get('fbt')} | 最后封板: {s.get('lbt')}")
                print(f"   成交额: {s.get('cje',0)/1e8:.2f}亿 | 换手率: {s.get('hs',0):.2f}%")
                print(f"   连板数: {s.get('lbc', 0)} | 炸板次数: {s.get('zbc', 0)}")


# ===================== 入口 =====================

if __name__ == "__main__":
    # 默认监控自选股
    portfolio = [
        ("002624", "完美世界"),
        ("601069", "西部黄金"),
        ("600397", "江钨装备"),
        ("000001", "平安银行"),
    ]
    indices = [
        ("000001.SH", "上证指数"),
        ("399001.SH", "深证成指"),
        ("399006.SZ", "创业板指"),
        ("000688.SH", "科创50"),
    ]
    my_codes = [c for c, _ in portfolio]

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "zt":
            # 涨停股池
            dt = sys.argv[2] if len(sys.argv) > 2 else None
            result = get_zt_pool(dt)
            print(fmt_zt_pool(result, my_codes))
        elif cmd == "index":
            # 指数技术面
            idx = sys.argv[2] if len(sys.argv) > 2 else "000001.SH"
            name = sys.argv[3] if len(sys.argv) > 3 else "指数"
            ma = get_index_ma(idx, "d", 5)
            macd = get_index_macd(idx, "d", 5)
            print(fmt_ma(ma, name))
            print(fmt_macd(macd, name))
        elif len(sys.argv) > 2:
            quick_look(sys.argv[1], sys.argv[2])
        else:
            quick_look(cmd)
    else:
        monitor_portfolio(portfolio, indices, my_codes)
