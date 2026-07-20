# -*- coding: utf-8 -*-
"""
HTTP 公共基础设施 v3.0 — 零外部依赖纯标准库实现
所有 scraper 模块共用，消除重复代码。

v3.0: requests → urllib 标准库，零 pip 依赖即可运行核心爬虫功能。
      optional: scrapling/playwright 用户可选安装用于动态渲染。

兼容接口（与旧 requests 版完全一致）：
  http_get(), http_post(), fetch_text(), http_get_json(),
  download_file(), get_session(), rate_limit(), clear_cache()

v2.2 遗留 API（保留）：
  DEFAULT_UA, DEFAULT_HEADERS, DEFAULT_TIMEOUT, DOWNLOAD_TIMEOUT,
  sanitize_filename(), LRUCache
"""
from __future__ import annotations

import os
import re
import time
import json
import random
import logging
import hashlib
import threading
import urllib.request
import urllib.error
import urllib.parse
from collections import OrderedDict
from pathlib import Path
from typing import Optional, Dict, Any, Union
from http.cookiejar import CookieJar

# ─── 日志 ────────────────────────────────────────────────────────────────────
log = logging.getLogger("http_utils")

# ─── 常量 ────────────────────────────────────────────────────────────────────

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)

DEFAULT_HEADERS: Dict[str, str] = {
    "User-Agent": DEFAULT_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

DEFAULT_TIMEOUT = 30
DOWNLOAD_TIMEOUT = 60
MAX_RETRIES = 3
RETRY_BACKOFF = 1.5
RATE_LIMIT_DELAY = 2.0
JITTER_FACTOR = 0.3

# ─── StdlibResponse ───────────────────────────────────────────────────────────

class HTTPError(urllib.error.HTTPError):
    """requests 风格的 HTTPError（兼容 raise_for_status 用法）"""
    def __init__(self, code: int, msg: str, hdrs: Dict, fp: Any, url: str = ""):
        super().__init__(url or "?", code, msg, hdrs, fp)
        self.code = code  # urllib.error.HTTPError uses .code internally
        self._url = url or "?"

    @property
    def status_code(self) -> int:
        return self.code

    @property
    def url(self) -> str:
        return self._url


class StdlibResponse:
    """
    urllib.response 包装器，对标 requests.Response 接口。
    让调用方无感切换到 urllib。
    """
    __slots__ = ('_url', '_code', '_headers', '_data', '_encoding')

    def __init__(self, url: str, code: int, headers: Dict[str, str], data: bytes, encoding: str = "utf-8"):
        self._url = url
        self._code = code
        self._headers = headers
        self._data = data
        self._encoding = encoding

    @property
    def url(self) -> str:
        return self._url

    @property
    def code(self) -> int:
        return self._code

    @property
    def status_code(self) -> int:
        return self._code

    @property
    def headers(self) -> Dict[str, str]:
        return self._headers

    @property
    def content(self) -> bytes:
        return self._data

    @property
    def text(self) -> str:
        return self._data.decode(self._encoding, errors="replace")

    def json(self) -> Any:
        return json.loads(self._data)

    def raise_for_status(self):
        if self._code >= 400:
            raise HTTPError(
                self._code,
                urllib.error.HTTPError.code.__doc__ or "",
                self._headers,
                None,
                self._url
            )

    def __repr__(self):
        return f"<StdlibResponse [{self._code}]>"


# ─── StdlibSession ───────────────────────────────────────────────────────────

class StdlibSession:
    """
    对标 requests.Session 的标准库实现。
    内部使用 urllib.request.OpenerDirector + CookieJar。
    """
    def __init__(self, headers: Optional[Dict[str, str]] = None):
        self.headers = {**DEFAULT_HEADERS, **(headers or {})}
        self.cookies = CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies)
        )

    def _build_request(self, url: str, headers: Dict, data: Optional[bytes]) -> urllib.request.Request:
        merged = {**self.headers, **headers}
        return urllib.request.Request(url, data=data, headers=merged, method="GET" if data is None else "POST")

    def _do_open(self, request: urllib.request.Request,
                 timeout: int,
                 response_cls: type = StdlibResponse) -> StdlibResponse:
        """执行请求并返回 StdlibResponse"""
        try:
            raw = self._opener.open(request, timeout=timeout)
            code = raw.getcode()
            # urllib 返回的是 email.message.Message 或类似对象
            hdrs = dict(raw.headers) if hasattr(raw.headers, '__iter__') else {}
            data = raw.read()
            url = request.full_url
            raw.close()

            # 编码检测
            encoding = self._detect_encoding(code, hdrs, data)
            return StdlibResponse(url, code, hdrs, data, encoding)

        except urllib.error.HTTPError as e:
            # 读取错误响应体（某些服务器在 4xx/5xx 时仍返回内容）
            code = e.code
            hdrs = dict(e.headers) if hasattr(e.headers, '__iter__') else {}
            data = b""
            try:
                if e.fp:
                    data = e.fp.read()
                    e.fp.close()
            except Exception:
                pass
            url = e.url or request.full_url
            encoding = self._detect_encoding(code, hdrs, data)
            return StdlibResponse(url, code, hdrs, data, encoding)

    def _detect_encoding(self, code: int, hdrs: Dict, data: bytes) -> str:
        """推断响应编码"""
        ct = hdrs.get("Content-Type", "")
        # 从 charset= 取编码
        m = re.search(r'charset=([^\s;]+)', ct, re.IGNORECASE)
        if m:
            return m.group(1).strip('"\'')
        # 尝试 apparent_encoding 替代方案：按优先级试探
        for enc in ("utf-8", "gbk", "gb2312", "gb18030", "latin-1"):
            try:
                data.decode(enc)
                return enc
            except (UnicodeDecodeError, LookupError):
                continue
        return "utf-8"

    def get(self, url: str,
            headers: Optional[Dict[str, str]] = None,
            timeout: int = DEFAULT_TIMEOUT,
            **kwargs) -> StdlibResponse:
        """HTTP GET"""
        req = self._build_request(url, headers or {}, None)
        return self._do_open(req, timeout)

    def post(self, url: str,
             data: Optional[Any] = None,
             json_body: Optional[Dict] = None,
             headers: Optional[Dict[str, str]] = None,
             timeout: int = DEFAULT_TIMEOUT,
             **kwargs) -> StdlibResponse:
        """HTTP POST — data 或 json_body 二选一"""
        if json_body is not None:
            body_bytes = json.dumps(json_body).encode("utf-8")
            h = {"Content-Type": "application/json; charset=utf-8"}
            if headers:
                h = {**headers, **h}
            headers = h
        elif data is not None:
            if isinstance(data, str):
                body_bytes = data.encode("utf-8")
            elif isinstance(data, dict):
                body_bytes = urllib.parse.urlencode(data).encode("utf-8")
            else:
                body_bytes = data
        else:
            body_bytes = None
        req = self._build_request(url, headers or {}, body_bytes)
        return self._do_open(req, timeout)

    def request(self, method: str, url: str,
                headers: Optional[Dict[str, str]] = None,
                data: Optional[Any] = None,
                timeout: int = DEFAULT_TIMEOUT,
                **kwargs) -> StdlibResponse:
        """通用 request"""
        if method.upper() == "POST":
            return self.post(url, data=data, headers=headers, timeout=timeout, **kwargs)
        return self.get(url, headers=headers, timeout=timeout, **kwargs)


# ─── 全局会话 ────────────────────────────────────────────────────────────────

_shared_session: Optional[StdlibSession] = None
_shared_mobile_session: Optional[StdlibSession] = None


def get_session(headers: Optional[Dict[str, str]] = None,
                reuse: bool = True,
                mobile: bool = False) -> StdlibSession:
    global _shared_session, _shared_mobile_session

    if mobile:
        if reuse and _shared_mobile_session is not None and headers is None:
            return _shared_mobile_session
        session = StdlibSession({**DEFAULT_HEADERS, "User-Agent": MOBILE_UA, **(headers or {})})
        if reuse and headers is None:
            _shared_mobile_session = session
        return session

    if reuse and _shared_session is not None and headers is None:
        return _shared_session

    session = StdlibSession({**DEFAULT_HEADERS, **(headers or {})})
    if reuse and headers is None:
        _shared_session = session
    return session


# ─── LRU 缓存 ────────────────────────────────────────────────────────────────

class LRUCache:
    def __init__(self, max_size: int = 128, ttl: float = 3600):
        self.max_size = max_size
        self.ttl = ttl
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

    def _key(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()[:16]

    def get(self, url: str) -> Optional[StdlibResponse]:
        key = self._key(url)
        with self._lock:
            if key in self._cache:
                entry_time, resp = self._cache[key]
                if time.time() - entry_time < self.ttl:
                    self._cache.move_to_end(key)
                    return resp
                del self._cache[key]
        return None

    def set(self, url: str, resp: StdlibResponse):
        key = self._key(url)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            else:
                if len(self._cache) >= self.max_size:
                    self._cache.popitem(last=False)
                self._cache[key] = (time.time(), resp)

    def clear(self):
        with self._lock:
            self._cache.clear()

    def __len__(self):
        return len(self._cache)


_response_cache = LRUCache(max_size=256, ttl=1800)


# ─── 按域名限流 ──────────────────────────────────────────────────────────────

_DOMAIN_RATE_LIMITS: Dict[str, float] = {
    "eastmoney.com": 1.0,
    "10jqka.com.cn": 2.0,
    "sina.com.cn": 1.5,
    "163.com": 1.5,
    "xueqiu.com": 3.0,
    "cls.cn": 2.0,
    "jisilu.cn": 3.0,
    "wallstreetcn.com": 2.0,
    "sse.com.cn": 3.0,
    "szse.cn": 3.0,
    "stats.gov.cn": 2.0,
    "pbc.gov.cn": 2.0,
    "default": RATE_LIMIT_DELAY,
}

_domain_last_request: Dict[str, float] = {}
_domain_lock = threading.Lock()


def _extract_domain(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return "unknown"


def rate_limit(delay: float = RATE_LIMIT_DELAY, url: str = ""):
    global _domain_last_request
    wait_time = 0
    with _domain_lock:
        now = time.time()
        if url:
            domain = _extract_domain(url)
            # 查找匹配域名配置
            domain_delay = RATE_LIMIT_DELAY
            for d, v in _DOMAIN_RATE_LIMITS.items():
                if d in domain and d != "default":
                    domain_delay = v
                    break
            else:
                domain_delay = _DOMAIN_RATE_LIMITS.get("default", RATE_LIMIT_DELAY)
            last_time = _domain_last_request.get(domain, 0)
            elapsed = now - last_time
            if elapsed < domain_delay:
                wait_time = domain_delay - elapsed
            _domain_last_request[domain] = now + wait_time
            if len(_domain_last_request) > 100:
                expired = [d for d, t in _domain_last_request.items() if now - t > 3600]
                for d in expired:
                    del _domain_last_request[d]
    if wait_time > 0:
        time.sleep(wait_time)


# ─── 重试抖动 ────────────────────────────────────────────────────────────────

def _jitter(base: float, factor: float = JITTER_FACTOR) -> float:
    return base * (1 + random.uniform(-factor, factor))


# ─── HTTP GET ────────────────────────────────────────────────────────────────

def http_get(url: str,
             headers: Optional[Dict[str, str]] = None,
             timeout: int = DEFAULT_TIMEOUT,
             retries: int = MAX_RETRIES,
             rate_limit_delay: float = 0,
             session: Optional[StdlibSession] = None,
             use_cache: bool = True,
             **kwargs) -> Optional[StdlibResponse]:
    if use_cache:
        cached = _response_cache.get(url)
        if cached is not None:
            log.debug(f"Cache hit: {url[:80]}")
            return cached

    rate_limit(rate_limit_delay, url)
    s = session or get_session()
    merged = {**DEFAULT_HEADERS, **(headers or {})}

    for attempt in range(retries):
        try:
            resp = s.get(url, headers=merged, timeout=timeout, **kwargs)
            if resp.code >= 400:
                wait = _jitter(RETRY_BACKOFF ** (attempt + 1))
                log.warning(f"HTTP {resp.code} on {url[:80]}, retry {attempt+1}/{retries} in {wait:.1f}s")
                time.sleep(wait)
                continue
            if use_cache:
                _response_cache.set(url, resp)
            return resp
        except Exception as e:
            wait = _jitter(RETRY_BACKOFF ** (attempt + 1))
            log.warning(f"Request failed on {url[:80]}: {e}, retry {attempt+1}/{retries} in {wait:.1f}s")
            time.sleep(wait)
    log.error(f"All {retries} retries exhausted for {url[:80]}")
    return None


def http_get_json(url: str,
                  timeout: int = DEFAULT_TIMEOUT,
                  session: Optional[StdlibSession] = None,
                  **kwargs) -> Optional[Dict]:
    resp = http_get(url, timeout=timeout, session=session,
                    headers={"Accept": "application/json, */*"}, **kwargs)
    if resp is not None:
        try:
            return resp.json()
        except Exception as e:
            log.warning(f"JSON parse failed for {url[:80]}: {e}")
    return None


# ─── HTTP POST ──────────────────────────────────────────────────────────────

def http_post(url: str,
              data: Optional[Any] = None,
              json_body: Optional[Dict] = None,
              headers: Optional[Dict[str, str]] = None,
              timeout: int = DEFAULT_TIMEOUT,
              retries: int = MAX_RETRIES,
              rate_limit_delay: float = 0,
              session: Optional[StdlibSession] = None,
              use_cache: bool = False,
              **kwargs) -> Optional[StdlibResponse]:
    cache_key = url if use_cache else None
    rate_limit(rate_limit_delay, url)
    s = session or get_session()
    merged = {**DEFAULT_HEADERS, **(headers or {})}

    for attempt in range(retries):
        try:
            resp = s.post(url, data=data, json_body=json_body,
                          headers=merged, timeout=timeout, **kwargs)
            if resp.code >= 400:
                wait = _jitter(RETRY_BACKOFF ** (attempt + 1))
                log.warning(f"HTTP {resp.code} on POST {url[:80]}, retry {attempt+1}/{retries} in {wait:.1f}s")
                time.sleep(wait)
                continue
            if use_cache and cache_key:
                _response_cache.set(cache_key, resp)
            return resp
        except Exception as e:
            wait = _jitter(RETRY_BACKOFF ** (attempt + 1))
            log.warning(f"POST failed on {url[:80]}: {e}, retry {attempt+1}/{retries} in {wait:.1f}s")
            time.sleep(wait)
    log.error(f"All {retries} retries exhausted for POST {url[:80]}")
    return None


# ─── 便捷函数 ───────────────────────────────────────────────────────────────

def fetch_text(url: str,
               headers: Optional[Dict[str, str]] = None,
               timeout: int = DEFAULT_TIMEOUT,
               retries: int = MAX_RETRIES,
               use_cache: bool = True,
               **kwargs) -> Optional[str]:
    resp = http_get(url, headers=headers, timeout=timeout,
                    retries=retries, use_cache=use_cache, **kwargs)
    return resp.text if resp is not None else None


def clear_cache() -> int:
    _response_cache.clear()
    return len(_response_cache)


# ─── 文件下载 ────────────────────────────────────────────────────────────────

def download_file(url: str,
                  save_dir: str = ".",
                  filename: Optional[str] = None,
                  headers: Optional[Dict[str, str]] = None,
                  timeout: int = DOWNLOAD_TIMEOUT,
                  session: Optional[StdlibSession] = None) -> Optional[str]:
    s = session or get_session()
    merged = {**DEFAULT_HEADERS, **(headers or {})}
    try:
        resp = s.get(url, headers=merged, timeout=timeout)
        # 解析文件名
        if not filename:
            filename = _extract_filename(resp, url)
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, filename)
        with open(save_path, 'wb') as f:
            f.write(resp.content)
        log.info(f"Downloaded: {save_path}")
        return save_path
    except Exception as e:
        log.error(f"Download failed from {url[:80]}: {e}")
        return None


def _extract_filename(resp: StdlibResponse, url: str) -> str:
    cd = resp.headers.get("Content-Disposition", "")
    if cd:
        m = re.search(r"filename\*=UTF-8''(.+?)(?:;|$)", cd, re.IGNORECASE)
        if m:
            return urllib.parse.unquote(m.group(1).strip())
        m = re.search(r'filename=["\']?([^"\';]+)', cd)
        if m:
            return m.group(1).strip()
    path = urllib.parse.urlparse(url).path
    name = os.path.basename(path)
    if name and '.' in name:
        return urllib.parse.unquote(name)
    return f"download_{int(time.time())}"


def sanitize_filename(name: str, max_len: int = 100) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    name = re.sub(r'\s+', ' ', name).strip()
    if len(name) > max_len:
        name = name[:max_len]
    # If the name is empty or only underscores after sanitization, use a default
    if not name or not name.strip('_'):
        return "unnamed"
    return name
