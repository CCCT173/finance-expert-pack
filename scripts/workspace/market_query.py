import requests
import os
import json
import uuid
import sys

sys.stdout.reconfigure(encoding='utf-8')

NEO_API = f"http://localhost:{os.environ.get('AUTH_GATEWAY_PORT', '19000')}/proxy/api"
HEADERS = {
    "Remote-URL": "https://jprx.m.qq.com/aizone/skillserver/v1/proxy/teamrouter_neodata/query",
    "Content-Type": "application/json"
}

def query(q):
    payload = {"channel":"neodata","sub_channel":"qclaw","query":q,"request_id":str(uuid.uuid4()),"data_type":"api"}
    r = requests.post(NEO_API, json=payload, headers=HEADERS, timeout=30)
    return r.json()

queries = [
    "上证指数 深证成指 今日行情 2026年5月",
    "黄金价格 国际金价 今日 2026年5月",
    "人民币兑美元 汇率 今日",
]

for q in queries:
    print(f"\n=== {q} ===")
    result = query(q)
    api_data = result.get("data", {}).get("apiData", {})
    for block in api_data.get("apiRecall", [])[:2]:
        btype = block.get("type", "N/A")
        bcontent = block.get("content", "")[:400]
        print(f"[{btype}] {bcontent}\n")
