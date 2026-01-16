#!/usr/bin/env python3
"""
RSS/Atom 解析与规范化模块

功能：
- 解析 RSS 2.0、Atom 1.0 格式
- 规范化条目为 ArticleItem
- URL 规范化（去除追踪参数、解析相对 URL）
- 时间标准化为 ISO 8601
"""

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse, urlunparse, parse_qs, urlencode

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

# 需要去除的追踪参数
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "source", "fbclid", "gclid", "msclkid", "dclid",
    "_ga", "_gl", "mc_eid", "mc_cid"
}


@dataclass
class ArticleItem:
    """解析后的文章条目"""
    title: str
    url: str
    source_id: str
    source_name: str = ""
    title_raw: str = ""
    published_at: Optional[str] = None
    summary: str = ""
    summary_raw: str = ""
    topic: str = "other"
    tags: List[str] = field(default_factory=list)
    mentions: List[Dict] = field(default_factory=list)
    score: float = 0.0
    flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)


def normalize_url(url: str, base_url: Optional[str] = None) -> str:
    """
    规范化 URL

    - 解析相对 URL
    - 去除追踪参数
    - 统一协议为 https

    Args:
        url: 待规范化的 URL
        base_url: 基础 URL（用于解析相对路径）

    Returns:
        规范化后的 URL
    """
    if not url:
        return ""

    # 解析相对 URL
    if base_url and not url.startswith(("http://", "https://")):
        url = urljoin(base_url, url)

    # 解析 URL
    parsed = urlparse(url)

    # 统一协议为 https
    scheme = "https" if parsed.scheme in ("http", "https", "") else parsed.scheme

    # 去除追踪参数
    if parsed.query:
        params = parse_qs(parsed.query, keep_blank_values=True)
        filtered_params = {
            k: v for k, v in params.items()
            if k.lower() not in TRACKING_PARAMS
        }
        query = urlencode(filtered_params, doseq=True)
    else:
        query = ""

    # 重建 URL
    return urlunparse((
        scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        query,
        ""  # 去除 fragment
    ))


def parse_datetime(date_str: Optional[str]) -> Optional[str]:
    """
    解析日期时间字符串为 ISO 8601 格式

    支持多种常见格式：
    - RFC 822: Mon, 15 Jan 2026 09:00:00 GMT
    - RFC 3339: 2026-01-15T09:00:00Z
    - ISO 8601: 2026-01-15T09:00:00+08:00

    Args:
        date_str: 日期时间字符串

    Returns:
        ISO 8601 格式字符串，无法解析时返回 None
    """
    if not date_str:
        return None

    date_str = date_str.strip()

    # 常见日期格式
    formats = [
        # RFC 3339 / ISO 8601
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S",
        # RFC 822
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%d %b %Y %H:%M:%S %z",
        "%d %b %Y %H:%M:%S %Z",
        # 其他常见格式
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]

    # 预处理：处理 GMT/UTC 时区
    date_str_clean = date_str.replace("GMT", "+0000").replace("UTC", "+0000")
    # 处理 +00:00 格式
    date_str_clean = re.sub(r"([+-]\d{2}):(\d{2})$", r"\1\2", date_str_clean)

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str_clean, fmt)
            # 确保有时区信息
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ZoneInfo("UTC"))
            return dt.isoformat()
        except ValueError:
            continue

    return None


def strip_html(text: str) -> str:
    """去除 HTML 标签并解码实体"""
    if not text:
        return ""
    # 去除 HTML 标签
    text = re.sub(r"<[^>]+>", " ", text)
    # 解码 HTML 实体
    text = html.unescape(text)
    # 清理空白
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_text(element: Optional[ET.Element], default: str = "") -> str:
    """安全提取元素文本"""
    if element is None:
        return default
    if element.text:
        return element.text.strip()
    # 处理 CDATA
    all_text = "".join(element.itertext())
    return all_text.strip() if all_text else default


class FeedParser:
    """Feed 解析器"""

    # XML 命名空间
    NAMESPACES = {
        "atom": "http://www.w3.org/2005/Atom",
        "dc": "http://purl.org/dc/elements/1.1/",
        "content": "http://purl.org/rss/1.0/modules/content/",
        "media": "http://search.yahoo.com/mrss/",
    }

    def __init__(self, source_id: str, source_name: str = ""):
        """
        初始化解析器

        Args:
            source_id: 信源 ID
            source_name: 信源显示名称
        """
        self.source_id = source_id
        self.source_name = source_name or source_id

    def parse(self, content: str, feed_url: str = "") -> Tuple[List[ArticleItem], Optional[str]]:
        """
        解析 feed 内容

        Args:
            content: XML 内容字符串
            feed_url: feed URL（用于解析相对链接）

        Returns:
            (文章列表, 错误信息)
            解析成功时错误信息为 None
        """
        if not content:
            return [], "内容为空"

        try:
            # 清理可能的 BOM
            content = content.lstrip("\ufeff")
            root = ET.fromstring(content)
        except ET.ParseError as e:
            return [], f"XML 解析错误: {e}"

        # 检测 feed 类型
        tag = root.tag.lower()
        if "feed" in tag:
            return self._parse_atom(root, feed_url), None
        elif "rss" in tag or "rdf" in tag:
            return self._parse_rss(root, feed_url), None
        else:
            # 尝试查找 channel 元素（RSS）
            channel = root.find("channel")
            if channel is not None:
                return self._parse_rss(root, feed_url), None
            return [], f"未知的 feed 格式: {root.tag}"

    def _parse_rss(self, root: ET.Element, feed_url: str) -> List[ArticleItem]:
        """解析 RSS 2.0 格式"""
        items = []
        channel = root.find("channel")
        if channel is None:
            channel = root

        for item in channel.findall("item"):
            article = self._parse_rss_item(item, feed_url)
            if article:
                items.append(article)

        return items

    def _parse_rss_item(self, item: ET.Element, feed_url: str) -> Optional[ArticleItem]:
        """解析单个 RSS item"""
        # 标题
        title = extract_text(item.find("title"))
        if not title:
            return None

        # 链接
        link = extract_text(item.find("link"))
        # 备选：guid
        if not link:
            guid = item.find("guid")
            if guid is not None and guid.get("isPermaLink", "true").lower() == "true":
                link = extract_text(guid)

        if not link:
            return None

        link = normalize_url(link, feed_url)

        # 发布时间
        pub_date = extract_text(item.find("pubDate"))
        if not pub_date:
            # 尝试 dc:date
            pub_date = extract_text(item.find("dc:date", self.NAMESPACES))
        published_at = parse_datetime(pub_date)

        # 摘要
        description = extract_text(item.find("description"))
        # 尝试 content:encoded
        content_encoded = item.find("content:encoded", self.NAMESPACES)
        if content_encoded is not None:
            full_content = extract_text(content_encoded)
            if len(full_content) > len(description):
                description = full_content

        summary_raw = description
        summary = strip_html(description)
        # 限制摘要长度
        if len(summary) > 500:
            summary = summary[:500] + "..."

        # 标签/分类
        tags = []
        for category in item.findall("category"):
            cat_text = extract_text(category)
            if cat_text:
                tags.append(cat_text)

        # 构建 flags
        flags = []
        if not published_at:
            flags.append("date_unknown")

        return ArticleItem(
            title=title,
            title_raw=title,
            url=link,
            source_id=self.source_id,
            source_name=self.source_name,
            published_at=published_at,
            summary=summary,
            summary_raw=summary_raw,
            tags=tags[:5],  # 限制标签数量
            flags=flags
        )

    def _parse_atom(self, root: ET.Element, feed_url: str) -> List[ArticleItem]:
        """解析 Atom 1.0 格式"""
        items = []
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        # 尝试带命名空间和不带命名空间
        entries = root.findall("atom:entry", ns)
        if not entries:
            entries = root.findall("entry")
        if not entries:
            entries = root.findall("{http://www.w3.org/2005/Atom}entry")

        for entry in entries:
            article = self._parse_atom_entry(entry, feed_url, ns)
            if article:
                items.append(article)

        return items

    def _parse_atom_entry(self, entry: ET.Element, feed_url: str, ns: Dict) -> Optional[ArticleItem]:
        """解析单个 Atom entry"""
        # 标题
        title_elem = entry.find("atom:title", ns)
        if title_elem is None:
            title_elem = entry.find("title")
        if title_elem is None:
            title_elem = entry.find("{http://www.w3.org/2005/Atom}title")
        title = extract_text(title_elem)
        if not title:
            return None

        # 链接 - 优先选择 alternate 类型
        link = ""
        for link_elem in entry.findall("atom:link", ns) + entry.findall("link") + entry.findall("{http://www.w3.org/2005/Atom}link"):
            rel = link_elem.get("rel", "alternate")
            if rel == "alternate":
                link = link_elem.get("href", "")
                break
            elif not link:
                link = link_elem.get("href", "")

        if not link:
            return None

        link = normalize_url(link, feed_url)

        # 发布时间
        pub_elem = entry.find("atom:published", ns)
        if pub_elem is None:
            pub_elem = entry.find("published")
        if pub_elem is None:
            pub_elem = entry.find("{http://www.w3.org/2005/Atom}published")
        updated_elem = entry.find("atom:updated", ns)
        if updated_elem is None:
            updated_elem = entry.find("updated")
        if updated_elem is None:
            updated_elem = entry.find("{http://www.w3.org/2005/Atom}updated")
        pub_date = extract_text(pub_elem) or extract_text(updated_elem)
        published_at = parse_datetime(pub_date)

        # 摘要
        summary_elem = entry.find("atom:summary", ns)
        if summary_elem is None:
            summary_elem = entry.find("summary")
        if summary_elem is None:
            summary_elem = entry.find("{http://www.w3.org/2005/Atom}summary")
        content_elem = entry.find("atom:content", ns)
        if content_elem is None:
            content_elem = entry.find("content")
        if content_elem is None:
            content_elem = entry.find("{http://www.w3.org/2005/Atom}content")

        description = extract_text(summary_elem)
        if content_elem is not None:
            content_text = extract_text(content_elem)
            if len(content_text) > len(description):
                description = content_text

        summary_raw = description
        summary = strip_html(description)
        if len(summary) > 500:
            summary = summary[:500] + "..."

        # 标签
        tags = []
        for cat in entry.findall("atom:category", ns) + entry.findall("category") + entry.findall("{http://www.w3.org/2005/Atom}category"):
            term = cat.get("term")
            if term:
                tags.append(term)

        # flags
        flags = []
        if not published_at:
            flags.append("date_unknown")

        return ArticleItem(
            title=title,
            title_raw=title,
            url=link,
            source_id=self.source_id,
            source_name=self.source_name,
            published_at=published_at,
            summary=summary,
            summary_raw=summary_raw,
            tags=tags[:5],
            flags=flags
        )


def parse_feed(content: str, source_id: str, source_name: str = "", feed_url: str = "") -> Tuple[List[ArticleItem], Optional[str]]:
    """
    便捷函数：解析 feed 内容

    Args:
        content: XML 内容
        source_id: 信源 ID
        source_name: 信源名称
        feed_url: feed URL

    Returns:
        (文章列表, 错误信息)
    """
    parser = FeedParser(source_id, source_name)
    return parser.parse(content, feed_url)


# ============ 自测试 ============
def _run_self_tests():
    """运行内置自测试"""
    import sys

    errors = []

    # 测试 1: URL 规范化 - 去除追踪参数
    try:
        url = normalize_url("https://example.com/article?id=123&utm_source=twitter&ref=homepage")
        assert "utm_source" not in url, f"应去除 utm_source: {url}"
        assert "ref=" not in url, f"应去除 ref: {url}"
        assert "id=123" in url, f"应保留 id: {url}"
        print("✓ 测试1: URL 规范化（去除追踪参数）通过")
    except Exception as e:
        errors.append(f"测试1失败: {e}")
        print(f"✗ 测试1: {e}")

    # 测试 2: URL 规范化 - 相对 URL
    try:
        url = normalize_url("/article/123", "https://example.com/feed")
        assert url == "https://example.com/article/123", f"相对 URL 解析错误: {url}"
        print("✓ 测试2: URL 规范化（相对 URL）通过")
    except Exception as e:
        errors.append(f"测试2失败: {e}")
        print(f"✗ 测试2: {e}")

    # 测试 3: 日期解析 - RFC 822
    try:
        dt = parse_datetime("Mon, 15 Jan 2026 09:00:00 +0000")
        assert dt is not None, "应能解析 RFC 822 格式"
        assert "2026-01-15" in dt, f"日期解析错误: {dt}"
        print("✓ 测试3: 日期解析（RFC 822）通过")
    except Exception as e:
        errors.append(f"测试3失败: {e}")
        print(f"✗ 测试3: {e}")

    # 测试 4: 日期解析 - ISO 8601
    try:
        dt = parse_datetime("2026-01-15T09:00:00+08:00")
        assert dt is not None, "应能解析 ISO 8601 格式"
        assert "2026-01-15" in dt, f"日期解析错误: {dt}"
        print("✓ 测试4: 日期解析（ISO 8601）通过")
    except Exception as e:
        errors.append(f"测试4失败: {e}")
        print(f"✗ 测试4: {e}")

    # 测试 5: HTML 清理
    try:
        text = strip_html("<p>Hello <strong>world</strong>!</p>")
        assert text == "Hello world !", f"HTML 清理错误: {text}"
        print("✓ 测试5: HTML 清理通过")
    except Exception as e:
        errors.append(f"测试5失败: {e}")
        print(f"✗ 测试5: {e}")

    # 测试 6: RSS 解析
    try:
        rss_content = """<?xml version="1.0"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>测试标题</title>
                    <link>https://example.com/article/1</link>
                    <pubDate>Mon, 15 Jan 2026 09:00:00 +0000</pubDate>
                    <description>这是摘要内容</description>
                </item>
            </channel>
        </rss>"""
        items, error = parse_feed(rss_content, "test", "测试信源")
        assert error is None, f"解析应成功: {error}"
        assert len(items) == 1, f"应有 1 个条目: {len(items)}"
        assert items[0].title == "测试标题"
        assert items[0].source_id == "test"
        print("✓ 测试6: RSS 解析通过")
    except Exception as e:
        errors.append(f"测试6失败: {e}")
        print(f"✗ 测试6: {e}")

    # 测试 7: Atom 解析
    try:
        atom_content = """<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <entry>
                <title>Atom 测试</title>
                <link href="https://example.com/article/2" rel="alternate"/>
                <published>2026-01-15T10:00:00Z</published>
                <summary>Atom 摘要</summary>
            </entry>
        </feed>"""
        items, error = parse_feed(atom_content, "test_atom", "Atom 测试")
        assert error is None, f"解析应成功: {error}"
        assert len(items) == 1, f"应有 1 个条目: {len(items)}"
        assert items[0].title == "Atom 测试"
        print("✓ 测试7: Atom 解析通过")
    except Exception as e:
        errors.append(f"测试7失败: {e}")
        print(f"✗ 测试7: {e}")

    # 测试 8: ArticleItem 数据结构
    try:
        item = ArticleItem(
            title="测试",
            url="https://example.com/test",
            source_id="test"
        )
        d = item.to_dict()
        assert d["title"] == "测试"
        assert d["url"] == "https://example.com/test"
        assert d["topic"] == "other"  # 默认值
        print("✓ 测试8: ArticleItem 数据结构通过")
    except Exception as e:
        errors.append(f"测试8失败: {e}")
        print(f"✗ 测试8: {e}")

    # 汇总
    print()
    if errors:
        print(f"自测试完成，{len(errors)} 个失败:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("✓ 所有自测试通过")
        sys.exit(0)


if __name__ == "__main__":
    _run_self_tests()
