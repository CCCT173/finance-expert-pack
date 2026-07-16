#!/usr/bin/env python3
"""
OpenClaw / JPRX 私有运行时的统一访问层（可配置 + 优雅降级）

本 skill 的部分能力（NeoData 金融搜索、元宝/prosearch 网页搜索）原本硬编码了
私有运行时地址 `localhost:19000` 与 `E:\\QClaw\\...\\prosearch.cjs`，导致非目标
环境无法运行。本模块将所有这类访问收敛到这里：

- 网关地址可经环境变量 `AUTH_GATEWAY_PORT` / `NEODATA_GATEWAY_URL` 配置；
- prosearch 路径可经环境变量 `PROSEARCH_SCRIPT` 配置；
- 网关或 prosearch 不可用时，函数返回清晰的错误结构 / 空字符串，绝不抛异常崩溃。

所有依赖私有运行时的脚本都应 `from gateway import query_neodata, web_search_prosearch`，
而不是在各自文件里重复硬编码。
"""

import os
import sys
import json
import uuid

# ---- 可配置项（默认仍是 OpenClaw/JPRX 本地网关，但可覆盖）----
GATEWAY_URL = os.environ.get(
    "NEODATA_GATEWAY_URL",
    "http://localhost:{}/proxy/api".format(os.environ.get("AUTH_GATEWAY_PORT", "19000")),
)
PROSEARCH_SCRIPT = os.environ.get(
    "PROSEARCH_SCRIPT",
    r"E:\QClaw\resources\openclaw\config\skills\online-search\scripts\prosearch.cjs",
)
REMOTE_URL = "https://jprx.m.qq.com/aizone/skillserver/v1/proxy/teamrouter_neodata/query"


def _has_requests() -> bool:
    try:
        import requests  # noqa: F401
        return True
    except ImportError:
        return False


def query_neodata(
    query: str,
    data_type: str = "all",
    sub_channel: str = "qclaw",
    request_id: str | None = None,
) -> dict:
    """经网关查询 NeoData。

    成功时返回网关原始 JSON（含 `suc` / `data` 等字段）；
    依赖缺失或网关不可达时返回 `{"_status": "unavailable", "error": ...}`，不抛异常。
    """
    if not _has_requests():
        return {"_status": "unavailable", "error": "缺少 requests 依赖（pip install requests）"}

    payload = {
        "channel": "neodata",
        "sub_channel": sub_channel,
        "query": query,
        "request_id": request_id or uuid.uuid4().hex,
        "data_type": data_type,
        "se_params": {},
        "extra_params": {},
    }
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Remote-URL": REMOTE_URL,
    }
    try:
        import requests

        resp = requests.post(GATEWAY_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:  # 网关未启动 / 网络不通 / 鉴权失败 —— 优雅降级
        return {
            "_status": "unavailable",
            "error": f"NeoData 网关不可达（{GATEWAY_URL}）：{e}",
            "hint": "需在 OpenClaw/JPRX 运行时，或设置 AUTH_GATEWAY_PORT / NEODATA_GATEWAY_URL",
        }


def web_search_prosearch(keyword: str, freshness: str = "24h", industry: str = "news") -> str:
    """调用元宝 / prosearch 网页搜索，返回 message 文本；不可用时返回 ''（不崩溃）。"""
    if not PROSEARCH_SCRIPT or not os.path.exists(PROSEARCH_SCRIPT):
        return ""
    try:
        import subprocess

        result = subprocess.run(
            [
                "node",
                PROSEARCH_SCRIPT,
                f"--keyword={keyword}",
                f"--freshness={freshness}",
                f"--industry={industry}",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
        if result.stdout and result.stdout.strip():
            data = json.loads(result.stdout)
            return data.get("message", "") if data.get("success") else ""
    except Exception:
        return ""
    return ""


if __name__ == "__main__":
    # 简单自检：打印当前配置，便于排查环境
    print(json.dumps(
        {
            "gateway_url": GATEWAY_URL,
            "prosearch_configured": bool(PROSEARCH_SCRIPT),
            "prosearch_exists": os.path.exists(PROSEARCH_SCRIPT) if PROSEARCH_SCRIPT else False,
        },
        ensure_ascii=False,
        indent=2,
    ))
