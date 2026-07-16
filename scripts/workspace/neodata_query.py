import requests
import json
import uuid
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

# NeoData Financial Search API —— 统一经 common/gateway 访问（地址可配置、优雅降级）
_common_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common")
if _common_dir not in sys.path:
    sys.path.insert(0, _common_dir)
from gateway import query_neodata as _gateway_query  # noqa: E402

def query_neodata(query_str, data_type="all"):
    return _gateway_query(query_str, data_type=data_type)

# Query each stock comprehensively
stocks = [
    ("完美世界 002624", "完美世界(002624)全面分析：股价、估值、财务数据、资金流向、近期新闻"),
    ("西部黄金 601069", "西部黄金(601069)全面分析：股价、估值、财务数据、资金流向、黄金走势、近期新闻"),
    ("江钨装备 600397", "江钨装备(600397)全面分析：股价、估值、财务数据、资金流向、近期新闻"),
]

for name, query in stocks:
    print(f"\n{'='*60}")
    print(f"查询: {name}")
    print(f"{'='*60}")
    result = query_neodata(query, data_type="all")
    if "error" in result:
        print(f"错误: {result['error']}")
    else:
        code = result.get("code")
        suc = result.get("suc")
        print(f"状态: code={code}, suc={suc}")
        if result.get("data"):
            api_data = result["data"].get("apiData", {})
            docs_data = result["data"].get("docData", {})
            
            # Print API data
            if api_data:
                print(f"\n--- 结构化数据 ---")
                entities = api_data.get("entity", [])
                if entities:
                    print(f"标的数量: {len(entities)}")
                    for ent in entities[:3]:
                        print(f"  {ent.get('code', 'N/A')} {ent.get('name', 'N/A')}")
                
                api_recalls = api_data.get("apiRecall", [])
                if api_recalls:
                    print(f"\nAPI数据块数量: {len(api_recalls)}")
                    for recall in api_recalls[:5]:
                        rtype = recall.get("type", "N/A")
                        rdesc = recall.get("desc", "N/A")
                        rcontent = recall.get("content", "")[:300]
                        print(f"\n  [{rtype}] {rdesc}")
                        print(f"  {rcontent[:300]}...")
            
            # Print doc data
            if docs_data:
                print(f"\n--- 文档数据 ---")
                doc_recalls = docs_data.get("docRecall", [])
                if doc_recalls:
                    print(f"文档数量: {len(doc_recalls)}")
                    for dr in doc_recalls[:3]:
                        ext_q = dr.get("extQuery", "N/A")
                        doc_list = dr.get("docList", [])
                        print(f"\n  检索词: {ext_q}, 文档数: {len(doc_list)}")
                        for doc in doc_list[:2]:
                            title = doc.get("title", "N/A")
                            print(f"    - {title[:60]}")
        else:
            print("无data字段")
            print(json.dumps(result, ensure_ascii=False, indent=2)[:500])

print("\n\n查询完成!")
