import urllib
import os.request, json, re, sys

sys.stdout.reconfigure(encoding='utf-8')

API_PORT = int(os.environ.get("AUTH_GATEWAY_PORT", "19000"))

def call(q):
    url = f'http://localhost:{API_PORT}/proxy/api'
    p = {'channel':'neodata','sub_channel':'qclaw','query':q,'request_id':'focus','data_type':'api','se_params':{},'extra_params':{}}
    h = {'Content-Type':'application/json; charset=utf-8','Remote-URL':'https://jprx.m.qq.com/aizone/skillserver/v1/proxy/teamrouter_neodata/query'}
    req = urllib.request.Request(url, data=json.dumps(p, ensure_ascii=False).encode('utf-8'), headers=h, method='POST')
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8'))

def extract(content, pattern):
    m = re.search(pattern, content)
    return float(m.group(1)) if m else None

stocks = [
    ('002624', '完美世界', 'SZ'),
    ('601069', '西部黄金', 'SH'),
    ('600397', '江钨装备', 'SH'),
]

for code, name, market in stocks:
    query = f'{name}({code}.{market})'
    d = call(query)
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
    print(f'{name}({code}.{market}) | 价格:{price} | 涨跌:{ch_str} | PE:{pe_str} | PB:{pb_str} | 股息率:{div_str}')
