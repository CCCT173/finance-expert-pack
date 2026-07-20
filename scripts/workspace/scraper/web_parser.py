# -*- coding: utf-8 -*-
"""
网页操作与金融产品解析模块
支持动态网页交互、元素操作、金融产品深度解析
"""

from __future__ import annotations

import json
import re
import time
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Callable, TYPE_CHECKING
from dataclasses import dataclass, field

# Scrapling导入
try:
    from scrapling.fetchers import StealthyFetcher, DynamicFetcher
    from scrapling.parser import Selector, Element
    SCRAPLING_AVAILABLE = True
except ImportError:
    SCRAPLING_AVAILABLE = False
    if TYPE_CHECKING:
        Selector = Any  # type: ignore
        Element = Any   # type: ignore
    SCRAPLING_AVAILABLE = False

# Playwright导入（用于复杂交互）
try:
    from playwright.sync_api import sync_playwright, Page, Locator
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

SKILL_DATA_DIR = Path(__file__).parent.parent / "data"

# ==================== 预编译正则（性能优化，避免每次解析重复编译） ====================

# 金融数字提取
_RE_NUMBER = re.compile(r'(\d+\.?\d*)')
_RE_SIGNED_NUMBER = re.compile(r'([+-]?\d+\.?\d*)')
_RE_PERCENTAGE = re.compile(r'(\d+\.?\d*)\s*%')
_RE_FUND_CODE = re.compile(r'(\d{6})')
_RE_STOCK_CODE = re.compile(r'(?:s[hz]|sh|sz)\s*\.?\s*(\d{6})', re.IGNORECASE)
_RE_DATE = re.compile(r'(\d{4}-\d{2}-\d{2})')

# 金融指标提取
_RE_PE = re.compile(r'市盈率[（(]?PE[）)]?\s*[：:]\s*(\d+\.?\d*)')
_RE_PB = re.compile(r'市净率[（(]?PB[）)]?\s*[：:]\s*(\d+\.?\d*)')
_RE_SHARPE = re.compile(r'夏普比率[（(]?Sharpe[）)]?\s*[：:]\s*([+-]?\d+\.?\d*)')
_RE_MAXDD = re.compile(r'最大回撤\s*[：:]\s*([+-]?\d+\.?\d*)\s*%?')
_RE_VOLATILITY = re.compile(r'波动率\s*[：:]\s*(\d+\.?\d*)\s*%?')

# 基金指标
_RE_FUND_NAV = re.compile(r'(?:单位)?净值[：:]\s*(\d+\.\d+)')
_RE_FUND_ACCU_NAV = re.compile(r'累计净值[：:]\s*(\d+\.\d+)')
_RE_FUND_SCALE = re.compile(r'基金规模[：:]\s*([\d.]+)\s*亿')
_RE_FUND_MANAGER = re.compile(r'基金经理[：:]\s*([^\s，,]+)')
_RE_FUND_COMPANY = re.compile(r'基金公司[：:]\s*([^\s，,]+)')
_RE_FUND_ESTABLISH = re.compile(r'成立日期[：:]\s*(\d{4}-\d{2}-\d{2})')

# 收益提取
_RE_RETURN_PATTERNS = [
    (re.compile(r'近1月[收益收益率]*[：:]\s*([+-]?\d+\.?\d*)\s*%?'), 'return_1m'),
    (re.compile(r'近3月[收益收益率]*[：:]\s*([+-]?\d+\.?\d*)\s*%?'), 'return_3m'),
    (re.compile(r'近6月[收益收益率]*[：:]\s*([+-]?\d+\.?\d*)\s*%?'), 'return_6m'),
    (re.compile(r'近1年[收益收益率]*[：:]\s*([+-]?\d+\.?\d*)\s*%?'), 'return_1y'),
    (re.compile(r'近3年[收益收益率]*[：:]\s*([+-]?\d+\.?\d*)\s*%?'), 'return_3y'),
    (re.compile(r'今年来[收益收益率]*[：:]\s*([+-]?\d+\.?\d*)\s*%?'), 'return_ytd'),
    (re.compile(r'成立来[收益收益率]*[：:]\s*([+-]?\d+\.?\d*)\s*%?'), 'return_since_inception'),
]

# HTML 标签清理
_RE_HTML_TAG = re.compile(r'<[^>]+>')
_RE_HTML_SCRIPT = re.compile(r'<script[^>]*>.*?</script>', re.DOTALL | re.IGNORECASE)
_RE_HTML_STYLE = re.compile(r'<style[^>]*>.*?</style>', re.DOTALL | re.IGNORECASE)
_RE_MULTI_SPACE = re.compile(r'\s+')

# ==================== 解析工具函数 ====================

def _safe_css_first(page, selectors, default=""):
    """安全获取第一个匹配的 CSS 选择器文本"""
    if not hasattr(page, 'css_first'):
        return default
    for sel in ([selectors] if isinstance(selectors, str) else selectors):
        try:
            el = page.css_first(sel)
            if el and el.text():
                return el.text().strip()
        except Exception:
            continue
    return default


def _safe_re_search(page, pattern, group=1, default=None):
    """安全执行正则搜索，提取分组"""
    try:
        if hasattr(page, 're_search'):
            match = page.re_search(pattern)
        else:
            match = re.search(pattern, str(page))
        if match:
            if group == 0:
                return match.group(0)
            return match.group(group) if match.groups() else match.group(0)
    except Exception:
        pass
    return default


def _clean_html(html: str) -> str:
    """清理 HTML 标签，提取纯文本"""
    text = _RE_HTML_SCRIPT.sub(' ', html)
    text = _RE_HTML_STYLE.sub(' ', text)
    text = _RE_HTML_TAG.sub(' ', text)
    text = _RE_MULTI_SPACE.sub(' ', text)
    return text.strip()


def _parse_percentage(text: str) -> float:
    """从文本解析百分比值"""
    match = _RE_SIGNED_NUMBER.search(text)
    return float(match.group(1)) if match else 0.0


def _match_first(text: str, patterns: list) -> str:
    """用多个正则模式匹配文本，返回第一个成功的"""
    for pattern in patterns:
        match = re.search(pattern, text) if isinstance(pattern, str) else pattern.search(text)
        if match:
            return match.group(1) if match.groups() else match.group(0)
    return ""


@dataclass
class WebOperation:
    """网页操作描述"""
    op_type: str  # click, scroll, wait, fill, select, hover
    selector: str
    value: Optional[str] = None
    timeout: int = 10000
    wait_for: Optional[str] = None  # networkidle, domcontentloaded, load


class PageOperator:
    """页面操作器 - 支持复杂网页交互"""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._initialized = False

    def _ensure_playwright(self):
        """确保Playwright可用"""
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright未安装，请运行: pip install playwright && playwright install")

    def start(self):
        """启动浏览器"""
        self._ensure_playwright()
        if self.browser is None:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=self.headless)
            self.context = self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            self.page = self.context.new_page()
            self._initialized = True
        return self

    def stop(self):
        """关闭浏览器"""
        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        self._initialized = False

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.stop()

    def goto(self, url: str, wait: str = "networkidle") -> 'PageOperator':
        """导航到URL"""
        if not self._initialized:
            self.start()
        self.page.goto(url, wait_until=wait, timeout=30000)
        return self

    def click(self, selector: str, timeout: int = 10000) -> 'PageOperator':
        """点击元素"""
        self.page.click(selector, timeout=timeout)
        time.sleep(0.5)
        return self

    def fill(self, selector: str, value: str) -> 'PageOperator':
        """填写表单"""
        self.page.fill(selector, value)
        return self

    def select(self, selector: str, value: str) -> 'PageOperator':
        """选择下拉选项"""
        self.page.select_option(selector, value)
        return self

    def hover(self, selector: str) -> 'PageOperator':
        """悬停"""
        self.page.hover(selector)
        return self

    def scroll(self, direction: str = "down", amount: int = 500) -> 'PageOperator':
        """滚动页面"""
        if direction == "down":
            self.page.evaluate(f"window.scrollBy(0, {amount})")
        else:
            self.page.evaluate(f"window.scrollBy(0, -{amount})")
        time.sleep(0.3)
        return self

    def wait(self, seconds: float = 1) -> 'PageOperator':
        """等待"""
        time.sleep(seconds)
        return self

    def wait_for_selector(self, selector: str, timeout: int = 10000) -> 'PageOperator':
        """等待元素出现"""
        self.page.wait_for_selector(selector, timeout=timeout)
        return self

    def wait_for_navigation(self, timeout: int = 30000) -> 'PageOperator':
        """等待导航完成"""
        self.page.wait_for_load_state("networkidle", timeout=timeout)
        return self

    def execute_script(self, script: str) -> Any:
        """执行JavaScript"""
        return self.page.evaluate(script)

    def get_html(self) -> str:
        """获取页面HTML"""
        return self.page.content()

    def get_text(self, selector: str) -> str:
        """获取元素文本"""
        return self.page.locator(selector).text_content() or ""

    def get_attribute(self, selector: str, attr: str) -> str:
        """获取元素属性"""
        return self.page.locator(selector).get_attribute(attr) or ""

    def screenshot(self, path: str):
        """截图"""
        self.page.screenshot(path=path)

    def run_operations(self, operations: List[WebOperation]) -> 'PageOperator':
        """批量执行操作"""
        for op in operations:
            if op.op_type == "click":
                self.click(op.selector, op.timeout)
            elif op.op_type == "fill":
                self.fill(op.selector, op.value or "")
            elif op.op_type == "scroll":
                self.scroll("down", int(op.value or 500))
            elif op.op_type == "wait":
                self.wait(float(op.value or 1))
            elif op.op_type == "hover":
                self.hover(op.selector)
            elif op.op_type == "select":
                self.select(op.selector, op.value or "")
            elif op.op_type == "goto":
                self.goto(op.value or "")
            elif op.op_type == "wait_for":
                self.wait_for_selector(op.selector, op.timeout)

            if op.wait_for == "navigation":
                self.wait_for_navigation()

        return self


class FundParser:
    """基金产品解析器"""

    # 天天基金页面选择器
    TiantianSelectors = {
        "name": [".fundName", ".fund-title h1", "h1.fundName", "[class*='fund-name']"],
        "code": [".fundCode", ".fundcode", "#fundCode", "[class*='fund-code']"],
        "type": [".fundType", ".type", "#fundType", "[class*='fund-type']"],
        "company": [".company", ".management", "[class*='company']"],
        "manager": [".manager a", ".基金经理 a", "#manager a", "[class*='manager'] a"],
        "nav": [".nav", "#nav", "[class*='nav']"],
        "nav_change": [".navChange", ".nav_change", "[class*='change']"],
        "accu_nav": [".accuNav", "#accuNav", "[class*='accu']"],
        "establish_date": [".establishDate", "#establishDate", "[class*='establish']"],
        "scale": [".scale", "#scale", "[class*='scale']"],
        "risk_level": [".risk", "#risk", "[class*='risk']"],
    }

    # 东方财富选择器
    EastmoneySelectors = {
        "name": [".title", ".fund-name", "h1", "[class*='name']"],
        "code": [".code", "#fundCode", "[class*='code']"],
        "type": [".type", "[class*='type']"],
        "nav": ["#nav", ".nav", "[class*='nav']"],
        "features": ["[class*='feature']", ".tags", ".label"],
    }

    @staticmethod
    def parse_tiantian_fund(page: Union[Selector, str], url: str = "") -> Dict[str, Any]:
        """解析天天基金页面"""
        result = {
            "source": "tiantian",
            "product_name": "",
            "product_code": "",
            "product_type": "",
            "company": "",
            "manager": "",
            "risk_level": "",
            "nav": {},
            "fees": {},
            "holdings": {"stocks": [], "bonds": [], "top_industry": ""},
            "historical_nav": {},
            "risk_metrics": {},
            "basic_info": {},
            "raw_data": {}
        }

        try:
            if isinstance(page, str):
                # 如果是HTML字符串，用正则解析
                return FundParser._parse_fund_html(page, result)
            else:
                # 使用Scrapling Selector解析
                return FundParser._parse_fund_selector(page, result)
        except Exception as e:
            result["error"] = str(e)

        return result

    @staticmethod
    def _parse_fund_selector(page: Selector, result: Dict) -> Dict[str, Any]:
        """使用Selector解析基金"""
        # 尝试多个选择器
        for sel in FundParser.TiantianSelectors.get("name", []):
            try:
                el = page.css_first(sel)
                if el:
                    result["product_name"] = el.text().strip()
                    break
            except:
                continue

        # 基金代码
        for sel in FundParser.TiantianSelectors.get("code", []):
            try:
                el = page.css_first(sel)
                if el:
                    result["product_code"] = el.text().strip()
                    break
            except:
                continue

        # 净值信息
        for sel in FundParser.TiantianSelectors.get("nav", []):
            try:
                el = page.css_first(sel)
                if el:
                    text = el.text()
                    nav_match = re.search(r'(\d+\.\d+)', text)
                    if nav_match:
                        result["nav"]["current"] = float(nav_match.group(1))
                    break
            except:
                continue

        # 提取基本信息块
        info_patterns = [
            (r'基金规模[：:]\s*([\d.]+\s*亿元)', 'scale'),
            (r'成立日期[：:]\s*(\d{4}-\d{2}-\d{2})', 'establish_date'),
            (r'基金经理[：:]\s*([^\s，,]+)', 'manager'),
            (r'基金公司[：:]\s*([^\s，,]+)', 'company'),
        ]

        full_text = page.re_search(r'[一-龥]+[：:][^<>\n]+')
        if full_text:
            for pattern, key in info_patterns:
                match = re.search(pattern, full_text)
                if match:
                    result["basic_info"][key] = match.group(1).strip()

        return result

    @staticmethod
    def _parse_fund_html(html: str, result: Dict) -> Dict[str, Any]:
        """使用正则解析HTML"""
        # 基金名称
        name_match = re.search(r'class="fundName"[^>]*>([^<]+)', html)
        if not name_match:
            name_match = re.search(r'<h1[^>]*>([^<]+)', html)
        if name_match:
            result["product_name"] = name_match.group(1).strip()

        # 基金代码
        code_match = re.search(r'class="fundCode"[^>]*>([^<]+)', html)
        if code_match:
            result["product_code"] = code_match.group(1).strip()

        # 净值
        nav_match = re.search(r'<td[^>]*class="[^"]*nav[^"]*"[^>]*>.*?(\d+\.\d+)', html, re.DOTALL)
        if nav_match:
            result["nav"]["current"] = float(nav_match.group(1))

        return result


class ETFParser:
    """ETF产品解析器"""

    @staticmethod
    def parse_etf_page(page: Union[Selector, str], url: str = "") -> Dict[str, Any]:
        """解析ETF详情页面"""
        result = {
            "source": "etf",
            "source_url": url,
            "scrape_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "product_name": "",
            "product_code": "",
            "product_type": "ETF",
            "exchange": "",
            "跟踪指数": "",
            "nav": {},
            "premium": {},  # 溢价率、折价率
            "holdings": {
                "stocks": [],
                "top_10_weight": 0
            },
            "tracking_index": "",
            "fund_attributes": {},
            "risk_metrics": {}
        }

        try:
            if isinstance(page, Selector):
                result = ETFParser._parse_etf_selector(page, result)
            else:
                result = ETFParser._parse_etf_html(page, result)
        except Exception as e:
            result["error"] = str(e)

        return result

    @staticmethod
    def _parse_etf_selector(page: Selector, result: Dict) -> Dict[str, Any]:
        """Selector解析ETF"""
        # ETF名称
        for sel in ["h1", ".fund-name", "[class*='name']", ".title"]:
            try:
                el = page.css_first(sel)
                if el:
                    result["product_name"] = el.text().strip()
                    break
            except:
                continue

        # ETF代码
        code_patterns = [
            r'(\d{6})',
            r'代码[：:]\s*(\d{6})',
            r'512[0-9]{3}',  # 上交所ETF
            r'159[0-9]{3}',  # 深交所ETF
        ]
        for pat in code_patterns:
            match = page.re_search(pat)
            if match:
                result["product_code"] = match.group(1) if match.groups() else match.group(0)
                break

        # 交易所
        if result["product_code"]:
            if result["product_code"].startswith("5"):
                result["exchange"] = "上交所"
            elif result["product_code"].startswith("1") or result["product_code"].startswith("15"):
                result["exchange"] = "深交所"

        # 净值数据
        nav_sel = page.re_search(r'单位净值[：:]\s*(\d+\.\d+)')
        if nav_sel:
            result["nav"]["unit"] = float(nav_sel.group(1))

        accu_nav_sel = page.re_search(r'累计净值[：:]\s*(\d+\.\d+)')
        if accu_nav_sel:
            result["nav"]["accumulated"] = float(accu_nav_sel.group(1))

        # 溢价率/折价率
        premium_sel = page.re_search(r'溢价率[：:]\s*([+-]?\d+\.?\d*)%')
        if premium_sel:
            result["premium"]["premium_rate"] = float(premium_sel.group(1))

        discount_sel = page.re_search(r'折价率[：:]\s*([+-]?\d+\.?\d*)%')
        if discount_sel:
            result["premium"]["discount_rate"] = float(discount_sel.group(1))

        # 跟踪指数
        index_sel = page.re_search(r'跟踪指数[：:]\s*([^\s\n，,]+[^\n，,]*)')
        if index_sel:
            result["tracking_index"] = index_sel.group(1).strip()

        return result

    @staticmethod
    def _parse_etf_html(html: str, result: Dict) -> Dict[str, Any]:
        """正则解析ETF HTML"""
        # 名称
        name_match = re.search(r'<h1[^>]*>([^<]+)', html)
        if name_match:
            result["product_name"] = name_match.group(1).strip()

        # 代码
        code_match = re.search(r'(\d{6})', html)
        if code_match:
            result["product_code"] = code_match.group(1)

        # 净值
        nav_match = re.search(r'单位净值[^\d]*(\d+\.\d+)', html)
        if nav_match:
            result["nav"]["unit"] = float(nav_match.group(1))

        return result


class StockParser:
    """股票产品解析器"""

    @staticmethod
    def parse_stock_page(page: Union[Selector, str], url: str = "") -> Dict[str, Any]:
        """解析股票详情页面"""
        result = {
            "source": "stock",
            "source_url": url,
            "scrape_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "stock_name": "",
            "stock_code": "",
            "exchange": "",
            "price": {},
            "indicators": {},
            "financials": {},
            "main_indicators": {},  # 主要财务指标
            "dividend": {},  # 分红配送
            "holders": {}  # 股东情况
        }

        try:
            if isinstance(page, Selector):
                result = StockParser._parse_stock_selector(page, result)
            else:
                result = StockParser._parse_stock_html(page, result)
        except Exception as e:
            result["error"] = str(e)

        return result

    @staticmethod
    def _parse_stock_selector(page: Selector, result: Dict) -> Dict[str, Any]:
        """Selector解析股票"""
        # 股票名称
        for sel in ["h1", ".stock-name", "[class*='name']", ".title"]:
            try:
                el = page.css_first(sel)
                if el:
                    result["stock_name"] = el.text().strip()
                    break
            except:
                continue

        # 价格信息
        price_patterns = [
            (r'现价[：:]\s*(\d+\.?\d*)', 'current'),
            (r'今开[：:]\s*(\d+\.?\d*)', 'open'),
            (r'最高[：:]\s*(\d+\.?\d*)', 'high'),
            (r'最低[：:]\s*(\d+\.?\d*)', 'low'),
            (r'成交量[：:]\s*([\d.]+\s*[万千手]+)', 'volume'),
            (r'成交额[：:]\s*([\d.]+\s*[万元]+)', 'amount'),
        ]

        text_content = page.re_search(r'[\d.]+')
        if text_content:
            for pattern, key in price_patterns:
                match = page.re_search(pattern)
                if match:
                    try:
                        result["price"][key] = float(re.search(r'[\d.]+', match.group(0)).group())
                    except:
                        pass

        # 市盈率、市净率
        pe_match = page.re_search(r'市盈率[（(]PE[）)][：:]\s*(\d+\.?\d*)')
        if pe_match:
            result["indicators"]["pe"] = float(pe_match.group(1))

        pb_match = page.re_search(r'市净率[（(]PB[）)][：:]\s*(\d+\.?\d*)')
        if pb_match:
            result["indicators"]["pb"] = float(pb_match.group(1))

        # 总市值、流通市值
        mktcap_match = page.re_search(r'总市值[：:]\s*([\d.]+\s*[万亿亿]?)')
        if mktcap_match:
            result["financials"]["market_cap"] = mktcap_match.group(1).strip()

        return result

    @staticmethod
    def _parse_stock_html(html: str, result: Dict) -> Dict[str, Any]:
        """正则解析股票HTML"""
        # 名称
        name_match = re.search(r'<h1[^>]*>([^<]+)', html)
        if name_match:
            result["stock_name"] = name_match.group(1).strip()

        # 价格
        price_match = re.search(r'"price"\s*:\s*"?(\d+\.?\d*)"?', html)
        if price_match:
            result["price"]["current"] = float(price_match.group(1))

        return result


class InsurerParser:
    """保险公司解析器（万能险、年金险等）"""

    @staticmethod
    def parse_insurance_page(page: Union[Selector, str], url: str = "") -> Dict[str, Any]:
        """解析保险产品页面"""
        result = {
            "source": "insurance",
            "source_url": url,
            "scrape_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "product_name": "",
            "product_code": "",
            "insurance_type": "",  # 万能险、年金险、健康险
            "company": "",
            "coverage_years": 0,
            "payment_years": [],
            "min_premium": 0,
            "Guaranteed_rate": 0,  # 保证利率
            "historical_rate": 0,  # 历史利率/结算利率
            "protection": {},  # 保障内容
            "cash_value": {},  # 现金价值
            "surrender_period": 0,  # 犹豫期/退保期间
            "risk_warnings": []
        }

        try:
            if isinstance(page, Selector):
                result = InsurerParser._parse_insurance_selector(page, result)
            else:
                result = InsurerParser._parse_insurance_html(page, result)
        except Exception as e:
            result["error"] = str(e)

        return result

    @staticmethod
    def _parse_insurance_selector(page: Selector, result: Dict) -> Dict[str, Any]:
        """Selector解析保险"""
        # 产品名称
        for sel in ["h1", ".product-name", "[class*='name']", ".title"]:
            try:
                el = page.css_first(sel)
                if el:
                    result["product_name"] = el.text().strip()
                    break
            except:
                continue

        # 保证利率
        rate_patterns = [
            (r'保证利率[：:]\s*(\d+\.?\d*)%?', 'Guaranteed_rate'),
            (r'历史结算利率[：:]\s*(\d+\.?\d*)%?', 'historical_rate'),
            (r'预期收益率[：:]\s*(\d+\.?\d*)%?', 'expected_return'),
        ]
        for pat, key in rate_patterns:
            match = page.re_search(pat)
            if match:
                try:
                    result[key] = float(re.search(r'\d+\.?\d*', match.group(0)).group())
                except:
                    pass

        # 保障期限
        coverage_match = page.re_search(r'保障期限[：:]\s*(\d+)\s*年')
        if coverage_match:
            result["coverage_years"] = int(coverage_match.group(1))

        # 保费
        premium_match = page.re_search(r'最低保费[：:]\s*([\d,]+)\s*元')
        if premium_match:
            result["min_premium"] = int(premium_match.group(1).replace(',', ''))

        return result

    @staticmethod
    def _parse_insurance_html(html: str, result: Dict) -> Dict[str, Any]:
        """正则解析保险HTML"""
        name_match = re.search(r'<h1[^>]*>([^<]+)', html)
        if name_match:
            result["product_name"] = name_match.group(1).strip()

        return result


class AdvisorPortfolioParser:
    """投资顾问组合方案解析器（基金组合、主理人组合）"""

    @staticmethod
    def parse_advisor_portfolio(url: str, page: Union[Selector, str] = None,
                                platform: str = "auto") -> Dict[str, Any]:
        """
        解析投资顾问组合页面

        支持平台:
        - 天天基金"基金组合"（顾工组合）
        - 且慢"长期主义"等组合
        - 蛋卷基金组合
        - 支付宝"投顾管家"
        - 微信"基金组合"
        """
        result = {
            "source": "advisor_portfolio",
            "source_url": url,
            "platform": platform,
            "scrape_time": time.strftime("%Y-%m-%d %H:%M:%S"),

            # 组合基本信息
            "portfolio_name": "",
            "portfolio_id": "",
            "advisor_name": "",  # 主理人/顾问
            "advisor_title": "",  # 顾问头衔
            "company": "",  # 所属机构
            "creation_date": "",
            "track_record_years": 0,

            # 组合特征
            "strategy_type": "",  # 稳健、平衡、进取
            "suitable_investor": "",  # 适合投资者类型
            "investment_horizon": "",  # 建议投资期限
            "risk_level": "",  # 风险等级
            "max_drawdown_control": "",  # 最大回撤控制目标

            # 业绩指标
            "cumulative_return": 0,  # 累计收益率
            "annualized_return": 0,  # 年化收益率
            "ytd_return": 0,  # 今年来收益
            "performance": {},  # 各周期收益

            # 组合配置 - 核心
            "allocations": [],  # 配置列表
            "allocation_summary": {  # 配置汇总
                "stocks": 0,
                "bonds": 0,
                "funds": 0,
                "cash": 0,
                "other": 0
            },
            "holdings": {
                "stocks": [],   # 穿透后股票持仓
                "funds": [],    # 基金持仓
                "bonds": []     # 债券持仓
            },
            "positions": [],  # 持仓明细（含权重）

            # 调仓记录
            "rebalance_records": [],
            "last_rebalance_date": "",

            # 跟投信息
            "follow_amount": 0,  # 最低跟投金额
            "follow_count": 0,  # 跟投人数
            "management_fee": 0,  # 打理费

            # 风险指标
            "risk_metrics": {
                "sharpe_ratio": 0,
                "max_drawdown": 0,
                "volatility": 0,
                "calmar_ratio": 0
            },

            # 分析建议
            "style_analysis": "",  # 风格分析
            "recommendation": ""  # 配置建议
        }

        try:
            if page is None and url:
                # 需要先爬取
                if SCRAPLING_AVAILABLE:
                    fetcher = StealthyFetcher()
                    page = fetcher.fetch(url, headless=True)
                else:
                    result["error"] = "需要安装scrapling才能爬取"
                    return result

            if isinstance(page, Selector):
                result = AdvisorPortfolioParser._parse_portfolio_selector(page, result)
            else:
                result = AdvisorPortfolioParser._parse_portfolio_html(page, result)

            # 自动检测平台
            if platform == "auto":
                url_lower = url.lower()
                if 'easmart' in url_lower or '1234567' in url_lower:
                    result["platform"] = "天天基金组合"
                elif 'qieman' in url_lower:
                    result["platform"] = "且慢"
                elif 'danjuan' in url_lower:
                    result["platform"] = "蛋卷基金"
                elif 'zhipu' in url_lower:
                    result["platform"] = "支付宝投顾"

        except Exception as e:
            result["error"] = str(e)

        return result

    @staticmethod
    def _parse_portfolio_selector(page: Selector, result: Dict) -> Dict[str, Any]:
        """Selector解析投资顾问组合"""

        # 组合名称
        for sel in ["h1", ".portfolio-name", "[class*='name']", ".title",
                    ".strategy-name", "[class*='portfolio']"]:
            try:
                el = page.css_first(sel)
                if el:
                    result["portfolio_name"] = el.text().strip()
                    break
            except:
                continue

        # 主理人/顾问
        for sel in [".advisor", ".manager", "[class*='advisor']", ". Strategist",
                   "[class*='manager']", ".owner"]:
            try:
                el = page.css_first(sel)
                if el:
                    result["advisor_name"] = el.text().strip()
                    break
            except:
                continue

        # 策略类型（稳健/平衡/进取）
        for sel in [".strategy", "[class*='strategy']", ".type", ".level"]:
            try:
                el = page.css_first(sel)
                if el:
                    text = el.text().strip()
                    if text:
                        result["strategy_type"] = text
                    break
            except:
                continue

        # 业绩数据提取
        # 累计收益
        cum_match = page.re_search(r'累计收益[：:]*\s*([+-]?\d+\.?\d*)%?')
        if cum_match:
            result["cumulative_return"] = float(cum_match.group(1))

        # 年化收益
        annual_match = page.re_search(r'年化收益[：:]*\s*([+-]?\d+\.?\d*)%?')
        if annual_match:
            result["annualized_return"] = float(annual_match.group(1))

        # 今年来
        ytd_match = page.re_search(r'今年来[：:]*\s*([+-]?\d+\.?\d*)%?')
        if ytd_match:
            result["ytd_return"] = float(ytd_match.group(1))

        # 各周期收益
        period_patterns = [
            (r'近1月[：:]*\s*([+-]?\d+\.?\d*)%?', '1month'),
            (r'近3月[：:]*\s*([+-]?\d+\.?\d*)%?', '3month'),
            (r'近6月[：:]*\s*([+-]?\d+\.?\d*)%?', '6month'),
            (r'近1年[：:]*\s*([+-]?\d+\.?\d*)%?', '1year'),
            (r'近3年[：:]*\s*([+-]?\d+\.?\d*)%?', '3year'),
        ]
        for pattern, key in period_patterns:
            match = page.re_search(pattern)
            if match:
                result["performance"][key] = float(match.group(1))

        # ============ 持仓配置解析（核心） ============
        positions = []

        # 尝试提取持仓表格
        table_selectors = [
            ".positions-table tr",
            ".holdings-table tr",
            ".allocation-table tr",
            ".portfolio-holdings tr",
            "[class*='position'] tr",
            "table[class*='position'] tr"
        ]

        for sel in table_selectors:
            try:
                rows = page.css(sel)
                if rows and len(rows) > 1:
                    for row in rows[1:]:  # 跳过表头
                        cells = row.css("td, th")
                        if len(cells) >= 2:
                            item = {
                                "name": "",
                                "code": "",
                                "weight": 0,
                                "change": "",  # 调仓变化
                                "type": ""     # stock/fund/bond
                            }

                            for i, cell in enumerate(cells):
                                cell_text = cell.text().strip()
                                if i == 0:
                                    # 名称列
                                    item["name"] = cell_text
                                    # 尝试提取代码
                                    code_match = re.search(r'(\d{6})', cell_text)
                                    if code_match:
                                        item["code"] = code_match.group(1)
                                elif i == 1:
                                    # 权重列
                                    w_match = re.search(r'(\d+\.?\d*)%?', cell_text)
                                    if w_match:
                                        item["weight"] = float(w_match.group(1))
                                    # 判断类型
                                    if 'ETF' in cell_text or '指数' in cell_text:
                                        item["type"] = "etf"
                                    elif re.search(r'\d{6}', cell_text):
                                        item["type"] = "stock"
                                    else:
                                        item["type"] = "fund"

                            if item["name"]:
                                positions.append(item)
                    break
            except:
                continue

        result["positions"] = positions

        # 计算配置汇总
        stocks_weight = 0
        bonds_weight = 0
        funds_weight = 0

        for p in positions:
            w = p.get("weight", 0)
            t = p.get("type", "")
            if t == "stock":
                stocks_weight += w
            elif t in ("fund", "etf"):
                funds_weight += w
            else:
                funds_weight += w  # 默认归为基金

        result["allocation_summary"] = {
            "stocks": stocks_weight,
            "bonds": bonds_weight,
            "funds": funds_weight,
            "cash": 100 - stocks_weight - bonds_weight - funds_weight,
            "other": 0
        }

        # 穿透后股票持仓（如果是基金组合，需要穿透到股票）
        # 简化处理：根据基金类型估算
        if funds_weight > 50:
            result["holdings"]["funds"] = positions
            # 估算穿透股票
            # 股票型基金按95%计, 混合型按70%计, 债券型按5%计
            estimated_stock = funds_weight * 0.5  # 简化估算
            stocks_weight += estimated_stock
            result["holdings"]["stocks"] = [{
                "name": "穿透估算股票持仓",
                "estimated_weight": estimated_stock,
                "note": "由基金持仓穿透估算"
            }]
        else:
            result["holdings"]["funds"] = positions

        # 风险指标
        sharpe_match = page.re_search(r'夏普比率[：:]*\s*([+-]?\d+\.?\d*)')
        if sharpe_match:
            result["risk_metrics"]["sharpe_ratio"] = float(sharpe_match.group(1))

        maxdd_match = page.re_search(r'最大回撤[：:]*\s*([+-]?\d+\.?\d*)%?')
        if maxdd_match:
            result["risk_metrics"]["max_drawdown"] = float(maxdd_match.group(1))

        # 适合投资者
        investor_match = page.re_search(r'适合[人群类型]*[：:]*\s*([^\n，,]+)')
        if investor_match:
            result["suitable_investor"] = investor_match.group(1).strip()

        # 建议持有期
        horizon_match = page.re_search(r'建议持有[期]*[：:]*\s*(\d+)\s*[年个月天]+')
        if horizon_match:
            result["investment_horizon"] = horizon_match.group(0)

        # 跟投信息
        follow_match = page.re_search(r'跟投[人数金额]*[：:]*\s*([\d,]+)')
        if follow_match:
            result["follow_count"] = int(follow_match.group(1).replace(',', ''))

        return result

    @staticmethod
    def _parse_portfolio_html(html: str, result: Dict) -> Dict[str, Any]:
        """正则解析组合HTML"""
        # 组合名称
        name_match = re.search(r'<h1[^>]*>([^<]+)', html)
        if name_match:
            result["portfolio_name"] = name_match.group(1).strip()

        # 主理人
        advisor_match = re.search(r'主理人[：:]*\s*([^\s<]+)', html)
        if advisor_match:
            result["advisor_name"] = advisor_match.group(1).strip()

        # 累计收益
        cum_match = re.search(r'累计收益[：:]*\s*([+-]?\d+\.?\d*)%?', html)
        if cum_match:
            result["cumulative_return"] = float(cum_match.group(1))

        # 持仓表格
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
        positions = []
        for row in rows[1:]:  # 跳过表头
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            if len(cells) >= 2:
                name_cell = re.sub(r'<[^>]+>', '', cells[0]).strip()
                weight_cell = re.sub(r'<[^>]+>', '', cells[1]).strip()

                weight_match = re.search(r'(\d+\.?\d*)%?', weight_cell)
                weight = float(weight_match.group(1)) if weight_match else 0

                code_match = re.search(r'(\d{6})', name_cell)

                positions.append({
                    "name": re.sub(r'\d{6}', '', name_cell).strip(),
                    "code": code_match.group(1) if code_match else "",
                    "weight": weight
                })

        result["positions"] = positions

        return result

    @staticmethod
    def format_portfolio_analysis(portfolio: Dict[str, Any]) -> str:
        """格式化投资顾问组合分析报告"""
        if "error" in portfolio:
            return f"解析错误: {portfolio['error']}"

        name = portfolio.get("portfolio_name", "未知组合")
        advisor = portfolio.get("advisor_name", "未知主理人")
        platform = portfolio.get("platform", "")
        strategy = portfolio.get("strategy_type", "")

        report = f"""
【投资顾问组合分析】

■ 基本信息
组合名称: {name}
主理人: {advisor}
平台: {platform}
策略类型: {strategy if strategy else '未识别'}
"""

        # 业绩表现
        perf = portfolio.get("performance", {})
        cum_return = portfolio.get("cumulative_return", 0)
        annual_return = portfolio.get("annualized_return", 0)

        if cum_return or annual_return:
            report += "\n■ 业绩表现\n"
            if cum_return:
                report += f"累计收益: {cum_return:+.2f}%\n"
            if annual_return:
                report += f"年化收益: {annual_return:+.2f}%\n"

            if perf:
                report += "各周期表现:\n"
                for period, value in list(perf.items())[:6]:
                    report += f"  近{period}: {value:+.2f}%\n"

        # 资产配置
        report += "\n■ 资产配置\n"
        summary = portfolio.get("allocation_summary", {})
        if summary:
            stocks = summary.get("stocks", 0)
            bonds = summary.get("bonds", 0)
            funds = summary.get("funds", 0)
            cash = summary.get("cash", 0)

            bar_len = 25
            total = stocks + bonds + funds + cash
            if total > 0:
                stocks_bar = int(stocks / 100 * bar_len)
                bonds_bar = int(bonds / 100 * bar_len)
                funds_bar = int(funds / 100 * bar_len)
                cash_bar = int(cash / 100 * bar_len)

                report += f"股票:   {stocks:5.1f}% | {'▓' * stocks_bar}{'░' * (bar_len - stocks_bar)}\n"
                report += f"债券:   {bonds:5.1f}% | {'▓' * bonds_bar}{'░' * (bar_len - bonds_bar)}\n"
                report += f"基金:   {funds:5.1f}% | {'▓' * funds_bar}{'░' * (bar_len - funds_bar)}\n"
                report += f"现金:   {cash:5.1f}% | {'▓' * cash_bar}{'░' * (bar_len - cash_bar)}\n"

        # 持仓明细
        positions = portfolio.get("positions", [])
        if positions:
            report += f"\n■ 持仓明细 (共{len(positions)}只)\n"
            report += f"{'名称':<20} {'代码':<8} {'权重':>8}\n"
            report += "-" * 40 + "\n"
            for p in positions[:15]:
                name = (p.get("name", "") or "")[:18]
                code = p.get("code", "") or "-"
                weight = p.get("weight", 0)
                report += f"{name:<20} {code:<8} {weight:>7.2f}%\n"

            if len(positions) > 15:
                report += f"... 还有{len(positions) - 15}只\n"

        # 风险指标
        risk = portfolio.get("risk_metrics", {})
        if risk:
            report += "\n■ 风险指标\n"
            if risk.get("sharpe_ratio"):
                report += f"夏普比率: {risk['sharpe_ratio']:.2f}\n"
            if risk.get("max_drawdown"):
                report += f"最大回撤: {risk['max_drawdown']:.2f}%\n"
            if risk.get("volatility"):
                report += f"波动率: {risk['volatility']:.2f}%\n"

        # 适合投资者
        suitable = portfolio.get("suitable_investor", "")
        horizon = portfolio.get("investment_horizon", "")
        if suitable or horizon:
            report += "\n■ 适合人群\n"
            if suitable:
                report += f"{suitable}\n"
            if horizon:
                report += f"建议持有: {horizon}\n"

        # 投资建议
        report += "\n■ 配置建议\n"
        if strategy:
            if "稳健" in strategy or "保守" in strategy:
                report += "该组合为稳健型，适合风险偏好较低的投资者，可作为养老或教育金规划。\n"
            elif "进取" in strategy or "积极" in strategy:
                report += "该组合为进取型，适合风险承受能力强的投资者，建议定投并长期持有。\n"
            else:
                report += "该组合为均衡型，适合大多数投资者，可作为核心配置。\n"

        return report


class FOFParser:
    """FOF（基金中基金）产品解析器"""

    @staticmethod
    def parse_fof_page(page: Union[Selector, str], url: str = "") -> Dict[str, Any]:
        """解析FOF产品页面 - 提取底层基金配置"""
        result = {
            "source": "fof",
            "source_url": url,
            "scrape_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "product_name": "",
            "product_code": "",
            "product_type": "FOF",
            "company": "",
            "manager": "",
            "fof_category": "",  # 养老FOF、普通FOF
            "investment_style": "",  # 目标日期、目标风险、均衡型

            # FOF特有字段
            "asset_allocation": {  # 资产配置比例
                "stocks": 0,  # 股票比例
                "bonds": 0,    # 债券比例
                "funds": 0,    # 基金比例（自家产品）
                "cash": 0,     # 现金
                "other": 0     # 其他
            },
            "underlying_funds": [],  # 底层基金持仓
            "external_funds": [],    # 外部基金（非自家）
            "internal_funds": [],    # 内部基金（自家产品）
            "holdings": {
                "stocks": [],  # 直接股票持仓（如果有）
                "bonds": [],   # 直接债券持仓（如果有）
                "funds": []    # 基金持仓
            },
            "top_10_holdings_weight": 0,  # 前十持仓集中度
            "rebalance_history": [],  # 调仓历史
            "fee_structure": {},  # FOF费率（双层收费）
            "risk_metrics": {},
            "performance": {}
        }

        try:
            if isinstance(page, Selector):
                result = FOFParser._parse_fof_selector(page, result)
            else:
                result = FOFParser._parse_fof_html(page, result)
        except Exception as e:
            result["error"] = str(e)

        return result

    @staticmethod
    def _parse_fof_selector(page: Selector, result: Dict) -> Dict[str, Any]:
        """使用Selector解析FOF"""
        # 产品名称
        for sel in ["h1", ".fund-name", "[class*='name']", ".title", ".fof-name"]:
            try:
                el = page.css_first(sel)
                if el:
                    result["product_name"] = el.text().strip()
                    break
            except:
                continue

        # 基金代码
        code_match = page.re_search(r'(\d{6})')
        if code_match:
            result["product_code"] = code_match.group(1)

        # 资产配置比例 - 关键解析
        # 格式1: 股票 20%、债券 60%、基金 15%、现金 5%
        # 格式2: 权益类 20%、固收类 75%、其他 5%
        allocation_patterns = [
            r'股票[仓位]*[：:]*\s*(\d+\.?\d*)\s*%',
            r'权益类[：:]*\s*(\d+\.?\d*)\s*%',
            r'股票仓位[：:]*\s*(\d+\.?\d*)\s*%',
            r'投资于基金[：:]*\s*(\d+\.?\d*)\s*%',
            r'基金投资比例[：:]*\s*(\d+\.?\d*)\s*%',
        ]
        for pat in allocation_patterns:
            match = page.re_search(pat)
            if match:
                result["asset_allocation"]["stocks"] = float(match.group(1))
                break

        # 债券配置
        bond_patterns = [
            r'债券[仓位]*[：:]*\s*(\d+\.?\d*)\s*%',
            r'固收类[：:]*\s*(\d+\.?\d*)\s*%',
        ]
        for pat in bond_patterns:
            match = page.re_search(pat)
            if match:
                result["asset_allocation"]["bonds"] = float(match.group(1))
                break

        # 现金配置
        cash_match = page.re_search(r'现金[：:]*\s*(\d+\.?\d*)\s*%')
        if cash_match:
            result["asset_allocation"]["cash"] = float(cash_match.group(1))

        # ============ 底层基金持仓解析（核心功能） ============
        # FOF的精髓是提取其持有的底层基金

        # 尝试提取基金持仓表格
        # 天天基金的FOF持仓通常在"基金持仓"或"持仓明细"tab下
        fund_holdings = []

        # 尝试CSS选择器
        holding_selectors = [
            ".holdings-table tr",  # 持仓表格行
            ".fund-holdings tr",
            "[class*='holding'] tr",
            ".positions tr",
            "table[class*='fund'] tr",
            ".fof-holdings tr"
        ]

        for sel in holding_selectors:
            try:
                rows = page.css(sel)
                if rows and len(rows) > 1:
                    # 解析持仓行
                    for row in rows[1:]:  # 跳过表头
                        cells = row.css("td, th")
                        if len(cells) >= 2:
                            fund_name = ""
                            fund_code = ""
                            weight = 0
                            change = ""

                            for i, cell in enumerate(cells):
                                cell_text = cell.text().strip()
                                # 第一列通常是基金名称或代码
                                if i == 0:
                                    # 尝试提取基金代码 (6位数字)
                                    code_in_cell = re.search(r'(\d{6})', cell_text)
                                    if code_in_cell:
                                        fund_code = code_in_cell.group(1)
                                    fund_name = re.sub(r'\d{6}', '', cell_text).strip()
                                elif i == 1:
                                    # 第二列通常是持仓比例
                                    w_match = re.search(r'(\d+\.?\d*)%?', cell_text)
                                    if w_match:
                                        weight = float(w_match.group(1))
                                    elif re.search(r'\d', cell_text):
                                        try:
                                            weight = float(re.search(r'[\d.]+', cell_text).group())
                                        except:
                                            pass

                            if fund_name or fund_code:
                                fund_holdings.append({
                                    "name": fund_name,
                                    "code": fund_code,
                                    "weight": weight,
                                    "change": change
                                })
                    break
            except:
                continue

        result["underlying_funds"] = fund_holdings

        # 区分内部基金和外部基金（通过名称匹配或平台判断）
        internal_companies = ["易方达", "华夏", "嘉实", "南方", "广发", "博时",
                             "招商", "工银", "建信", "富国", "鹏华", "汇添富",
                             "中欧", "兴全", "景林", "高毅", "淡水泉", "明汯"]

        internal_funds = []
        external_funds = []

        for f in fund_holdings:
            is_internal = any(co in f.get("name", "") for co in internal_companies)
            if is_internal:
                internal_funds.append(f)
            else:
                external_funds.append(f)

        result["internal_funds"] = internal_funds
        result["external_funds"] = external_funds

        # 计算前十持仓集中度
        if fund_holdings:
            top_10 = sum(f.get("weight", 0) for f in fund_holdings[:10])
            result["top_10_holdings_weight"] = top_10

        # FOF分类
        name_text = result.get("product_name", "")
        if "养老" in name_text or "目标日期" in name_text:
            result["fof_category"] = "养老FOF"
            result["investment_style"] = "目标日期"
        elif "目标风险" in name_text:
            result["fof_category"] = "普通FOF"
            result["investment_style"] = "目标风险"
        else:
            result["fof_category"] = "普通FOF"

        # FOF特有费率（通常有双重收费）
        fee_match = page.re_search(r'基金管理费[：:]\s*(\d+\.?\d*)%?')
        if fee_match:
            result["fee_structure"]["management_fee"] = float(fee_match.group(1))

        return result

    @staticmethod
    def _parse_fof_html(html: str, result: Dict) -> Dict[str, Any]:
        """正则解析FOF HTML"""
        # 名称
        name_match = re.search(r'<h1[^>]*>([^<]+)', html)
        if name_match:
            result["product_name"] = name_match.group(1).strip()

        # 代码
        code_match = re.search(r'(\d{6})', html)
        if code_match:
            result["product_code"] = code_match.group(1)

        # 资产配置比例
        alloc_match = re.search(r'股票[：:]*\s*(\d+\.?\d*)%?', html)
        if alloc_match:
            result["asset_allocation"]["stocks"] = float(alloc_match.group(1))

        # 底层基金持仓 - 通过正则提取表格
        # 匹配基金持仓行: 基金名称 持仓比例
        fund_rows = re.findall(r'<tr[^>]*>.*?<td[^>]*>([^<]*(?:\d{6})?[^<]*)</td>.*?<td[^>]*>(\d+\.?\d*)%?</td>', html, re.DOTALL)
        funds = []
        for name_cell, weight_cell in fund_rows:
            fund_name = re.sub(r'\d{6}', '', name_cell).strip()
            fund_code = re.search(r'(\d{6})', name_cell)
            try:
                weight = float(re.search(r'(\d+\.?\d*)', weight_cell).group(1))
            except:
                weight = 0

            if fund_name:
                funds.append({
                    "name": fund_name,
                    "code": fund_code.group(1) if fund_code else "",
                    "weight": weight
                })

        result["underlying_funds"] = funds

        return result

    @staticmethod
    def extract_asset_allocation(text: str) -> Dict[str, float]:
        """从文本提取资产配置比例"""
        allocation = {"stocks": 0, "bonds": 0, "funds": 0, "cash": 0, "other": 0}

        # 股票/权益类
        stock_match = re.search(r'股票[仓位]*[：:]*\s*(\d+\.?\d*)\s*%', text)
        if stock_match:
            allocation["stocks"] = float(stock_match.group(1))
        else:
            equity_match = re.search(r'权益类[：:]*\s*(\d+\.?\d*)\s*%', text)
            if equity_match:
                allocation["stocks"] = float(equity_match.group(1))

        # 债券/固收类
        bond_match = re.search(r'债券[仓位]*[：:]*\s*(\d+\.?\d*)\s*%', text)
        if bond_match:
            allocation["bonds"] = float(bond_match.group(1))
        else:
            fixed_match = re.search(r'固收类[：:]*\s*(\d+\.?\d*)\s*%', text)
            if fixed_match:
                allocation["bonds"] = float(fixed_match.group(1))

        # 现金
        cash_match = re.search(r'现金[：:]*\s*(\d+\.?\d*)\s*%', text)
        if cash_match:
            allocation["cash"] = float(cash_match.group(1))

        # 基金
        fund_match = re.search(r'基金[：:]*\s*(\d+\.?\d*)\s*%', text)
        if fund_match:
            allocation["funds"] = float(fund_match.group(1))

        return allocation

    @staticmethod
    def format_fof_analysis(fof_info: Dict[str, Any]) -> str:
        """格式化FOF分析报告"""
        if "error" in fof_info:
            return f"解析错误: {fof_info['error']}"

        name = fof_info.get("product_name", "未知")
        code = fof_info.get("product_code", "")
        category = fof_info.get("fof_category", "FOF")
        style = fof_info.get("investment_style", "")

        report = f"""
【{category}产品分析】

■ 基本信息
名称: {name}
代码: {code}
类型: {category}
风格: {style if style else '未识别'}

■ 资产配置比例
"""
        alloc = fof_info.get("asset_allocation", {})
        if alloc:
            stocks = alloc.get("stocks", 0)
            bonds = alloc.get("bonds", 0)
            funds = alloc.get("funds", 0)
            cash = alloc.get("cash", 0)

            # 可视化
            total = stocks + bonds + funds + cash
            if total > 0:
                bar_len = 30
                stocks_bar = int(stocks / 100 * bar_len)
                bonds_bar = int(bonds / 100 * bar_len)
                funds_bar = int(funds / 100 * bar_len)
                cash_bar = int(cash / 100 * bar_len)

                report += f"股票/权益: {stocks:5.1f}% | {'█' * stocks_bar}{'░' * (bar_len - stocks_bar)}\n"
                report += f"债券/固收: {bonds:5.1f}% | {'█' * bonds_bar}{'░' * (bar_len - bonds_bar)}\n"
                report += f"基金:       {funds:5.1f}% | {'█' * funds_bar}{'░' * (bar_len - funds_bar)}\n"
                report += f"现金:       {cash:5.1f}% | {'█' * cash_bar}{'░' * (bar_len - cash_bar)}\n"

        report += f"""
■ 底层基金持仓 (共{len(fof_info.get('underlying_funds', []))}只)
"""
        underlying = fof_info.get("underlying_funds", [])
        if underlying:
            # 内部vs外部分类
            internal = fof_info.get("internal_funds", [])
            external = fof_info.get("external_funds", [])

            if internal:
                report += f"\n自家产品 ({len(internal)}只):\n"
                for f in internal[:5]:
                    report += f"  {f.get('name', '')}({f.get('code', '')}) - {f.get('weight', 0):.2f}%\n"

            if external:
                report += f"\n外部基金 ({len(external)}只):\n"
                for f in external[:10]:
                    report += f"  {f.get('name', '')}({f.get('code', '')}) - {f.get('weight', 0):.2f}%\n"

            top10_weight = fof_info.get("top_10_holdings_weight", 0)
            report += f"\n前十持仓集中度: {top10_weight:.1f}%\n"
        else:
            report += "暂无可用持仓数据\n"

        # 收益表现
        perf = fof_info.get("performance", {})
        if perf:
            report += "\n■ 收益表现\n"
            for period, value in list(perf.items())[:5]:
                report += f"  {period}: {value}%\n"

        return report


class BondParser:
    """债券产品解析器"""

    @staticmethod
    def parse_bond_page(page: Union[Selector, str], url: str = "") -> Dict[str, Any]:
        """解析债券产品页面"""
        result = {
            "source": "bond",
            "source_url": url,
            "scrape_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "product_name": "",
            "product_code": "",
            "bond_type": "",  # 国债、企业债、可转债
            "par_value": 100,
            "coupon_rate": 0,  # 票面利率
            "issue_price": 0,
            "maturity_date": "",
            "term_to_maturity": 0,  # 剩余期限
            "rating": "",  # 信用评级
            "yield_to_maturity": 0,  # 到期收益率
            "clean_price": 0,  # 净价
            "dirty_price": 0,  # 全价
            "accrued_interest": 0,  # 应计利息
            "conversion_price": 0,  # 转股价（可转债）
            "conversion_ratio": 0,  # 转股比例（可转债）
        }

        try:
            if isinstance(page, Selector):
                result = BondParser._parse_bond_selector(page, result)
            else:
                result = BondParser._parse_bond_html(page, result)
        except Exception as e:
            result["error"] = str(e)

        return result

    @staticmethod
    def _parse_bond_selector(page: Selector, result: Dict) -> Dict[str, Any]:
        """Selector解析债券"""
        for sel in ["h1", ".bond-name", "[class*='name']", ".title"]:
            try:
                el = page.css_first(sel)
                if el:
                    result["product_name"] = el.text().strip()
                    break
            except:
                continue

        # 票面利率
        coupon_match = page.re_search(r'票面利率[：:]\s*(\d+\.?\d*)%?')
        if coupon_match:
            result["coupon_rate"] = float(coupon_match.group(1))

        # 到期收益率
        ytm_match = page.re_search(r'到期收益率[：:]\s*(\d+\.?\d*)%?')
        if ytm_match:
            result["yield_to_maturity"] = float(ytm_match.group(1))

        return result

    @staticmethod
    def _parse_bond_html(html: str, result: Dict) -> Dict[str, Any]:
        """正则解析债券HTML"""
        name_match = re.search(r'<h1[^>]*>([^<]+)', html)
        if name_match:
            result["product_name"] = name_match.group(1).strip()

        return result


# ============ 统一解析入口 ============

def parse_financial_product(url: str, product_type: str = "auto",
                            use_dynamic: bool = False,
                            operations: List[WebOperation] = None) -> Dict[str, Any]:
    """
    统一金融产品解析入口

    Args:
        url: 产品URL
        product_type: 产品类型 ("fund", "etf", "stock", "bond", "insurance", "p2p", "fof", "advisor", "auto")
        use_dynamic: 是否使用动态渲染
        operations: 页面操作列表（用于登录、点击等）

    Returns:
        产品信息字典
    """
    result = {"source_url": url, "scrape_time": time.strftime("%Y-%m-%d %H:%M:%S")}

    # 自动检测类型
    if product_type == "auto":
        url_lower = url.lower()
        if 'fof' in url_lower or 'FOF' in url:
            product_type = "fof"
        elif 'portfolio' in url_lower or '组合' in url:
            product_type = "advisor"
        elif 'fund.eastmoney' in url_lower or 'tiantian' in url_lower or '/fund/' in url_lower:
            product_type = "fund"
        elif 'etf.' in url_lower or 'quotes.etf' in url_lower or '512' in url_lower or '159' in url_lower:
            product_type = "etf"
        elif 'stock.eastmoney' in url_lower or 'quotes.stock' in url_lower or '10jqka' in url_lower:
            product_type = "stock"
        elif 'bond.' in url_lower or 'cbond' in url_lower:
            product_type = "bond"
        elif 'insurance' in url_lower or 'baodan' in url_lower:
            product_type = "insurance"
        else:
            product_type = "fund"  # 默认

    # 使用Playwright进行复杂操作
    if operations and PLAYWRIGHT_AVAILABLE:
        with PageOperator() as op:
            op.goto(url)
            op.run_operations(operations)
            html = op.get_html()

            if product_type == "fund":
                return FundParser.parse_tiantian_fund(html, url)
            elif product_type == "etf":
                return ETFParser.parse_etf_page(html, url)
            elif product_type == "stock":
                return StockParser.parse_stock_page(html, url)
            elif product_type == "bond":
                return BondParser.parse_bond_page(html, url)
            elif product_type == "fof":
                return FOFParser.parse_fof_page(html, url)
            elif product_type == "advisor":
                return AdvisorPortfolioParser.parse_advisor_portfolio(url, html)

    # 使用Scrapling
    if SCRAPLING_AVAILABLE:
        fetcher = StealthyFetcher() if not use_dynamic else DynamicFetcher()
        try:
            page = fetcher.fetch(url, headless=True,
                                solve_cloudflare=True if not use_dynamic else False)
        except Exception as e:
            result["error"] = f"爬取失败: {e}"
            return result

        if product_type == "fund":
            return FundParser.parse_tiantian_fund(page, url)
        elif product_type == "etf":
            return ETFParser.parse_etf_page(page, url)
        elif product_type == "stock":
            return StockParser.parse_stock_page(page, url)
        elif product_type == "bond":
            return BondParser.parse_bond_page(page, url)
        elif product_type == "fof":
            return FOFParser.parse_fof_page(page, url)
        elif product_type == "advisor":
            return AdvisorPortfolioParser.parse_advisor_portfolio(url, page)

    result["error"] = "无可用爬取引擎，请安装 scrapling 或 playwright"
    return result


def parse_product_from_html(html: str, product_type: str, url: str = "") -> Dict[str, Any]:
    """
    从HTML内容解析金融产品

    Args:
        html: HTML内容
        product_type: 产品类型
        url: 原始URL（可选）

    Returns:
        产品信息
    """
    if product_type == "fund":
        return FundParser.parse_tiantian_fund(html, url)
    elif product_type == "etf":
        return ETFParser.parse_etf_page(html, url)
    elif product_type == "stock":
        return StockParser.parse_stock_page(html, url)
    elif product_type == "bond":
        return BondParser.parse_bond_page(html, url)
    elif product_type == "fof":
        return FOFParser.parse_fof_page(html, url)
    elif product_type == "advisor":
        return AdvisorPortfolioParser.parse_advisor_portfolio(url, html)
    else:
        return {"error": f"不支持的产品类型: {product_type}"}


def extract_financial_metrics(text: str) -> Dict[str, Any]:
    """
    从文本中提取金融指标

    Args:
        text: 文本内容

    Returns:
        金融指标字典
    """
    metrics = {}

    # 收益率
    return_patterns = [
        (r'近1月[收益收益率]*[：:]*\s*([+-]?\d+\.?\d*)%?', 'return_1m'),
        (r'近3月[收益收益率]*[：:]*\s*([+-]?\d+\.?\d*)%?', 'return_3m'),
        (r'近6月[收益收益率]*[：:]*\s*([+-]?\d+\.?\d*)%?', 'return_6m'),
        (r'近1年[收益收益率]*[：:]*\s*([+-]?\d+\.?\d*)%?', 'return_1y'),
        (r'近3年[收益收益率]*[：:]*\s*([+-]?\d+\.?\d*)%?', 'return_3y'),
        (r'今年来[收益收益率]*[：:]*\s*([+-]?\d+\.?\d*)%?', 'return_ytd'),
    ]

    for pattern, key in return_patterns:
        match = re.search(pattern, text)
        if match:
            try:
                metrics[key] = float(match.group(1))
            except (ValueError, TypeError):
                pass

    # 风险指标
    risk_patterns = [
        (r'夏普比率[（(]Sharpe[）)][：:]*\s*([+-]?\d+\.?\d*)', 'sharpe_ratio'),
        (r'最大回撤[：:]*\s*([+-]?\d+\.?\d*)%?', 'max_drawdown'),
        (r'波动率[：:]*\s*(\d+\.?\d*)%?', 'volatility'),
        (r'卡玛比率[：:]*\s*([+-]?\d+\.?\d*)', 'calmar_ratio'),
    ]

    for pattern, key in risk_patterns:
        match = re.search(pattern, text)
        if match:
            try:
                metrics[key] = float(re.search(r'[+-]?\d+\.?\d*', match.group(0)).group())
            except:
                pass

    # 估值指标
    val_patterns = [
        (r'市盈率[（(]PE[）)][：:]*\s*(\d+\.?\d*)', 'pe'),
        (r'市净率[（(]PB[）)][：:]*\s*(\d+\.?\d*)', 'pb'),
        (r'市销率[（(]PS[）)][：:]*\s*(\d+\.?\d*)', 'ps'),
        (r'股息率[：:]*\s*(\d+\.?\d*)%?', 'dividend_yield'),
    ]

    for pattern, key in val_patterns:
        match = re.search(pattern, text)
        if match:
            try:
                metrics[key] = float(re.search(r'\d+\.?\d*', match.group(0)).group())
            except:
                pass

    return metrics


def format_product_summary(product_info: Dict[str, Any]) -> str:
    """
    格式化产品信息为可读摘要

    Args:
        product_info: 产品信息字典

    Returns:
        格式化摘要文本
    """
    if "error" in product_info:
        return f"解析错误: {product_info['error']}"

    source = product_info.get("source", "unknown")
    summary = f"【{source.upper()} 产品解析结果】\n\n"

    # 基本信息
    name = product_info.get("product_name") or product_info.get("stock_name", "") or \
           product_info.get("portfolio_name", "未知")
    code = product_info.get("product_code") or product_info.get("stock_code", "")

    summary += f"名称: {name}\n"
    if code:
        summary += f"代码: {code}\n"

    ptype = product_info.get("product_type") or product_info.get("insurance_type", "") or \
            product_info.get("fof_category", "")
    if ptype:
        summary += f"类型: {ptype}\n"

    company = product_info.get("company") or product_info.get("platform", "")
    if company:
        summary += f"机构: {company}\n"

    # 净值/价格
    nav = product_info.get("nav", {})
    price = product_info.get("price", {})
    if nav:
        if "current" in nav:
            summary += f"\n单位净值: {nav['current']}\n"
        elif "unit" in nav:
            summary += f"\n单位净值: {nav['unit']}\n"
        if "accumulated" in nav:
            summary += f"累计净值: {nav['accumulated']}\n"

    if price:
        if "current" in price:
            summary += f"\n现价: {price['current']}\n"

    # 收益率
    hist = product_info.get("historical_nav", {})
    perf = product_info.get("performance", {})
    cum_return = product_info.get("cumulative_return", 0)

    if hist:
        summary += "\n历史收益:\n"
        for period, value in list(hist.items())[:5]:
            summary += f"  近{period}: {value}%\n"
    elif perf:
        summary += "\n收益表现:\n"
        for period, value in list(perf.items())[:5]:
            summary += f"  {period}: {value}%\n"
    elif cum_return:
        summary += f"\n累计收益: {cum_return:+.2f}%\n"

    # FOF特有 - 资产配置
    asset_alloc = product_info.get("asset_allocation", {})
    if asset_alloc:
        summary += "\n资产配置:\n"
        for k, v in asset_alloc.items():
            if v > 0:
                summary += f"  {k}: {v}%\n"

    # 投资顾问组合 - 配置汇总
    alloc_summary = product_info.get("allocation_summary", {})
    if alloc_summary:
        summary += "\n配置比例:\n"
        for k, v in alloc_summary.items():
            if v > 0:
                summary += f"  {k}: {v}%\n"

    # 风险指标
    metrics = product_info.get("risk_metrics", {})
    if metrics:
        summary += "\n风险指标:\n"
        for k, v in list(metrics.items())[:5]:
            summary += f"  {k}: {v}\n"

    # 持仓
    holdings = product_info.get("holdings", {})
    positions = product_info.get("positions", [])
    underlying = product_info.get("underlying_funds", [])

    if holdings.get("stocks"):
        summary += "\n重仓股:\n"
        for s in holdings["stocks"][:5]:
            summary += f"  {s.get('name', '')}({s.get('code', '')}) - {s.get('weight', 0)}%\n"
    elif underlying:
        summary += "\n底层基金持仓:\n"
        for f in underlying[:10]:
            summary += f"  {f.get('name', '')}({f.get('code', '')}) - {f.get('weight', 0):.2f}%\n"
    elif positions:
        summary += f"\n持仓明细 (共{len(positions)}只):\n"
        for p in positions[:10]:
            summary += f"  {p.get('name', '')}({p.get('code', '')}) - {p.get('weight', 0):.2f}%\n"

    return summary


# ============ CLI入口 ============

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python web_parser.py <URL> [产品类型]")
        print("  python web_parser.py --html <HTML文件> [产品类型]")
        print("\n产品类型: fund, etf, stock, bond, insurance, auto")
        print("示例:")
        print("  python web_parser.py https://fund.eastmoney.com/000001.html fund")
        print("  python web_parser.py --html page.html fund")
        sys.exit(1)

    if sys.argv[1] == "--html":
        # 从HTML文件解析
        html_file = sys.argv[2]
        product_type = sys.argv[3] if len(sys.argv) > 3 else "fund"

        with open(html_file, 'r', encoding='utf-8') as f:
            html = f.read()

        result = parse_product_from_html(html, product_type)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        url = sys.argv[1]
        product_type = sys.argv[2] if len(sys.argv) > 2 else "auto"

        print(f"正在解析: {url}")
        print(f"产品类型: {product_type}")

        result = parse_financial_product(url, product_type)
        print("\n" + format_product_summary(result))