# -*- coding: utf-8 -*-
"""
cn-financial-scraper
中国大陆金融数据爬取与分析综合工具 v2.2
"""

# 禁止运行时生成 .pyc/__pycache__
import sys as _sys
_sys.dont_write_bytecode = True

from .scraper import FinancialPageScraper, scrape_financial_product, save_to_cache
from .web_parser import (
    PageOperator, WebOperation,
    FundParser, ETFParser, StockParser, FOFParser, AdvisorPortfolioParser,
    parse_financial_product, parse_product_from_html, format_product_summary
)
from .institution_scraper import (
    InstitutionLoader, InstitutionScraper, UniversalScraper,
    list_all_institutions, search_institution, get_institution_summary
)
from .institution_updater import (
    InstitutionUpdater, QuarterlyUpdater
)
from .announcement_scraper import (
    Announcement, PageStructure, PageStructureScanner,
    AnnouncementSearcher, PDFDownloader, AnnouncementManager
)
from .document_parser import (
    parse_document, parse_pdf, parse_docx, parse_xlsx, parse_txt,
    extract_financial_numbers, extract_key_info
)
from .document_analyzer import (
    DocumentAnalyzer, classify_document, extract_metadata,
    extract_financial_indicators, extract_risk_factors, extract_glossary
)
from .analyzer import (
    calculate_risk_metrics, analyze_investment_style,
    analyze_product, generate_portfolio_replication, suggest_alternatives
)
from .company_report_scraper import (
    CompanyReport, EastMoneyReportAPI, ReportDownloader,
    CompanyReportManager, get_stock_financial_report
)
from .news_scraper import (
    NewsArticle, EastMoneyNewsAPI, NewsAggregator, NewsDownloader,
    format_news_report
)
from .visualization_reporter import (
    ASCIIChart, ReportFormatter, ASCIIReportExporter,
    generate_analysis_report
)
from .realtime_monitor import (
    PageSnapshot, ChangeEvent,
    RealtimePageMonitor, AnnouncementMonitor, MarketNewsMonitor
)
from .full_institution_crawler import (
    FullInstitutionCrawler
)
from .adaptive_parser_v2 import (
    AdaptivePageParser,
    parse_institutions, parse_products, parse_page
)
from .scrapable_registry import (
    ScrapableRegistry,
)
from .name_scraper import (
    InstitutionNameScraper, AntiCrawlFetcher,
    scrape_institution, scrape_institution_by_name, scrape_institution_by_url,
    format_scraping_result,
    FOREIGN_INSTITUTION_TRANSLATIONS, is_foreign_institution
)
from .research_report_scraper import (
    BrokerReport, BrokerReportStats,
    EastMoneyBrokerReportAPI, BrokerReportDownloader, BrokerReportManager
)
from .comprehensive_report_scraper import (
    ReportSummary, ComprehensiveDownloader, ComprehensiveReportManager
)
from .report_indexer import (
    ReportIndex, ScanProgress, StockIndexDatabase, StockIndexer
)
from .report_exporter import (
    ExportedReport, DataOrganizer, AnalysisEngine,
    PPTExporter, WordExporter, ExcelExporter, PDFExporter, ComprehensiveExporter
)

# 批量爬虫
from .batch_institution_crawler import BatchInstitutionCrawler, StockBatchCrawler

# 数据验证
from .data_validator import run_full_validation, validate_institution_registry, validate_all_list_files

# 新增数据源爬虫 (v3.0)
from .sina_scraper import get_realtime_quote, get_stock_brief
from .cls_scraper import get_telegraph, get_hot_articles, search_articles
from .jisilu_scraper import get_convertible_bonds, get_bond_detail, search_bonds
from .wallstreetcn_scraper import get_live_news, get_articles
from .exchange_scraper import get_ipo_calendar, get_listed_companies, search_announcements

__all__ = [
    # 基础爬虫
    'FinancialPageScraper',
    'scrape_financial_product',
    'save_to_cache',

    # 网页解析
    'PageOperator',
    'WebOperation',
    'FundParser',
    'ETFParser',
    'StockParser',
    'FOFParser',
    'AdvisorPortfolioParser',
    'parse_financial_product',
    'parse_product_from_html',
    'format_product_summary',

    # 机构爬虫
    'InstitutionLoader',
    'InstitutionScraper',
    'UniversalScraper',
    'list_all_institutions',
    'search_institution',
    'get_institution_summary',

    # 机构更新器
    'InstitutionUpdater',
    'QuarterlyUpdater',

    # 公告爬虫
    'Announcement',
    'PageStructure',
    'PageStructureScanner',
    'AnnouncementSearcher',
    'PDFDownloader',
    'AnnouncementManager',

    # 文档解析
    'parse_document',
    'parse_pdf',
    'parse_docx',
    'parse_xlsx',
    'parse_txt',
    'extract_financial_numbers',
    'extract_key_info',

    # 文档分析整理
    'DocumentAnalyzer',
    'classify_document',
    'extract_metadata',
    'extract_financial_indicators',
    'extract_risk_factors',
    'extract_glossary',

    # 分析
    'calculate_risk_metrics',
    'analyze_investment_style',
    'analyze_product',
    'generate_portfolio_replication',
    'suggest_alternatives',

    # 公司报告
    'CompanyReport',
    'EastMoneyReportAPI',
    'ReportDownloader',
    'CompanyReportManager',
    'get_stock_financial_report',

    # 新闻爬虫
    'NewsArticle',
    'EastMoneyNewsAPI',
    'NewsAggregator',
    'NewsDownloader',
    'format_news_report',

    # 可视化报告
    'ASCIIChart',
    'ReportFormatter',
    'ASCIIReportExporter',
    'generate_analysis_report',

    # 实时监控
    'PageSnapshot',
    'ChangeEvent',
    'RealtimePageMonitor',
    'AnnouncementMonitor',
    'MarketNewsMonitor',

    # 机构名爬虫
    'InstitutionNameScraper',
    'AntiCrawlFetcher',
    'scrape_institution',
    'scrape_institution_by_name',
    'scrape_institution_by_url',
    'format_scraping_result',
    'FOREIGN_INSTITUTION_TRANSLATIONS',
    'is_foreign_institution',
    'ScrapableRegistry',

    # 券商研报
    'BrokerReport',
    'BrokerReportStats',
    'EastMoneyBrokerReportAPI',
    'BrokerReportDownloader',
    'BrokerReportManager',

    # 综合报告爬虫
    'ReportSummary',
    'ComprehensiveDownloader',
    'ComprehensiveReportManager',

    # 全量索引器
    'ReportIndex',
    'ScanProgress',
    'StockIndexDatabase',
    'StockIndexer',

    # 报告导出器
    'ExportedReport',
    'DataOrganizer',
    'AnalysisEngine',
    'PPTExporter',
    'WordExporter',
    'ExcelExporter',
    'PDFExporter',
    'ComprehensiveExporter',

    # 批量爬虫
    'BatchInstitutionCrawler',
    'StockBatchCrawler',

    # 数据验证
    'run_full_validation',
    'validate_institution_registry',
    'validate_all_list_files',

    # 新增数据源 (v3.0)
    'get_realtime_quote',
    'get_stock_brief',
    'get_telegraph',
    'get_hot_articles',
    'search_articles',
    'get_convertible_bonds',
    'get_bond_detail',
    'search_bonds',
    'get_live_news',
    'get_articles',
    'get_ipo_calendar',
    'get_listed_companies',
]

__version__ = '3.1.0'