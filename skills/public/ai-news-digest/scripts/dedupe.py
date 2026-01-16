#!/usr/bin/env python3
"""
去重与合并模块

功能：
- 基于规范化 URL 的主去重
- 可选的标题相似度 + 时间接近度二次去重
- 合并重复项的多信源提及
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse, urlunparse

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

# 导入 ArticleItem（如果在同一包中）
try:
    from parse_feeds import ArticleItem
except ImportError:
    from dataclasses import dataclass as dc

    @dataclass
    class ArticleItem:
        """文章条目的简化版本（独立运行时使用）"""
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


def normalize_url_for_dedupe(url: str) -> str:
    """
    规范化 URL 用于去重

    - 移除 www. 前缀
    - 统一为小写
    - 移除尾部斜杠
    - 移除 fragment
    """
    if not url:
        return ""

    parsed = urlparse(url.lower())

    # 移除 www. 前缀
    netloc = parsed.netloc
    if netloc.startswith("www."):
        netloc = netloc[4:]

    # 移除尾部斜杠
    path = parsed.path.rstrip("/")

    return urlunparse((
        parsed.scheme,
        netloc,
        path,
        parsed.params,
        parsed.query,
        ""  # 移除 fragment
    ))


def normalize_title(title: str) -> str:
    """
    规范化标题用于相似度比较

    - 转小写
    - 移除标点符号
    - 移除多余空白
    """
    if not title:
        return ""

    # 转小写
    title = title.lower()
    # 移除标点（保留中文字符）
    title = re.sub(r"[^\w\s\u4e00-\u9fff]", " ", title)
    # 移除多余空白
    title = re.sub(r"\s+", " ", title).strip()

    return title


def calculate_title_similarity(title1: str, title2: str) -> float:
    """
    计算两个标题的相似度（简化版 Jaccard 相似度）

    Returns:
        相似度 0.0 - 1.0
    """
    norm1 = normalize_title(title1)
    norm2 = normalize_title(title2)

    if not norm1 or not norm2:
        return 0.0

    # 分词（对中文按字符，对英文按单词）
    def tokenize(text: str) -> Set[str]:
        tokens = set()
        # 英文单词
        tokens.update(re.findall(r"[a-z]+", text))
        # 中文字符
        tokens.update(re.findall(r"[\u4e00-\u9fff]", text))
        return tokens

    tokens1 = tokenize(norm1)
    tokens2 = tokenize(norm2)

    if not tokens1 or not tokens2:
        return 0.0

    # Jaccard 相似度
    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)

    return intersection / union if union > 0 else 0.0


def are_times_close(time1: Optional[str], time2: Optional[str], hours: int = 24) -> bool:
    """
    判断两个时间是否接近

    Args:
        time1: ISO 8601 时间字符串
        time2: ISO 8601 时间字符串
        hours: 最大时间差（小时）

    Returns:
        是否在指定时间范围内
    """
    if not time1 or not time2:
        # 如果有一个时间未知，默认认为可能接近
        return True

    try:
        dt1 = datetime.fromisoformat(time1.replace("Z", "+00:00"))
        dt2 = datetime.fromisoformat(time2.replace("Z", "+00:00"))
        diff = abs((dt1 - dt2).total_seconds())
        return diff <= hours * 3600
    except (ValueError, AttributeError):
        return True


class Deduplicator:
    """去重器"""

    def __init__(
        self,
        enable_title_similarity: bool = False,
        title_similarity_threshold: float = 0.8,
        time_proximity_hours: int = 24
    ):
        """
        初始化去重器

        Args:
            enable_title_similarity: 是否启用标题相似度去重
            title_similarity_threshold: 标题相似度阈值（0.0-1.0）
            time_proximity_hours: 时间接近度阈值（小时）
        """
        self.enable_title_similarity = enable_title_similarity
        self.title_similarity_threshold = title_similarity_threshold
        self.time_proximity_hours = time_proximity_hours

    def dedupe(self, items: List[ArticleItem]) -> List[ArticleItem]:
        """
        对文章列表去重

        Args:
            items: 文章列表

        Returns:
            去重后的文章列表（带 mentions 合并）
        """
        if not items:
            return []

        # 第一轮：基于 URL 去重
        url_map: Dict[str, ArticleItem] = {}
        url_key_map: Dict[str, str] = {}  # 原始 URL -> 规范化 URL

        for item in items:
            norm_url = normalize_url_for_dedupe(item.url)

            if norm_url in url_map:
                # 合并到已有条目
                existing = url_map[norm_url]
                existing.mentions.append({
                    "source_id": item.source_id,
                    "source_name": item.source_name,
                    "url": item.url
                })
                # 如果新条目有更好的信息，更新
                if not existing.published_at and item.published_at:
                    existing.published_at = item.published_at
                if not existing.summary and item.summary:
                    existing.summary = item.summary
                    existing.summary_raw = item.summary_raw
            else:
                url_map[norm_url] = item
                url_key_map[item.url] = norm_url

        # 获取第一轮结果
        deduped = list(url_map.values())

        # 第二轮：可选的标题相似度去重
        if self.enable_title_similarity and len(deduped) > 1:
            deduped = self._dedupe_by_title_similarity(deduped)

        return deduped

    def _dedupe_by_title_similarity(self, items: List[ArticleItem]) -> List[ArticleItem]:
        """
        基于标题相似度的二次去重

        Args:
            items: 第一轮去重后的文章列表

        Returns:
            二次去重后的列表
        """
        if len(items) <= 1:
            return items

        # 标记已被合并的条目
        merged_indices: Set[int] = set()
        result: List[ArticleItem] = []

        for i, item in enumerate(items):
            if i in merged_indices:
                continue

            # 查找相似的条目
            for j in range(i + 1, len(items)):
                if j in merged_indices:
                    continue

                other = items[j]

                # 检查标题相似度
                similarity = calculate_title_similarity(item.title, other.title)
                if similarity < self.title_similarity_threshold:
                    continue

                # 检查时间接近度
                if not are_times_close(item.published_at, other.published_at, self.time_proximity_hours):
                    continue

                # 合并
                item.mentions.append({
                    "source_id": other.source_id,
                    "source_name": other.source_name,
                    "url": other.url
                })
                # 合并 other 的 mentions
                item.mentions.extend(other.mentions)

                # 更新信息
                if not item.published_at and other.published_at:
                    item.published_at = other.published_at
                if not item.summary and other.summary:
                    item.summary = other.summary
                    item.summary_raw = other.summary_raw

                merged_indices.add(j)

            result.append(item)

        return result


def dedupe_articles(
    items: List[ArticleItem],
    enable_title_similarity: bool = False,
    title_similarity_threshold: float = 0.8,
    time_proximity_hours: int = 24
) -> List[ArticleItem]:
    """
    便捷函数：对文章列表去重

    Args:
        items: 文章列表
        enable_title_similarity: 是否启用标题相似度去重
        title_similarity_threshold: 标题相似度阈值
        time_proximity_hours: 时间接近度阈值

    Returns:
        去重后的文章列表
    """
    deduper = Deduplicator(
        enable_title_similarity=enable_title_similarity,
        title_similarity_threshold=title_similarity_threshold,
        time_proximity_hours=time_proximity_hours
    )
    return deduper.dedupe(items)


# ============ 自测试 ============
def _run_self_tests():
    """运行内置自测试"""
    import sys
    from dataclasses import dataclass, field

    errors = []

    # 测试 1: URL 规范化
    try:
        url1 = normalize_url_for_dedupe("https://www.example.com/article/123/")
        url2 = normalize_url_for_dedupe("https://example.com/article/123")
        assert url1 == url2, f"URL 规范化应该相同: {url1} vs {url2}"
        print("✓ 测试1: URL 规范化通过")
    except Exception as e:
        errors.append(f"测试1失败: {e}")
        print(f"✗ 测试1: {e}")

    # 测试 2: 标题规范化
    try:
        title = normalize_title("Hello, World! 你好世界")
        assert "hello" in title
        assert "world" in title
        assert "你好世界" in title
        print("✓ 测试2: 标题规范化通过")
    except Exception as e:
        errors.append(f"测试2失败: {e}")
        print(f"✗ 测试2: {e}")

    # 测试 3: 标题相似度
    try:
        sim1 = calculate_title_similarity("OpenAI 发布 GPT-5", "OpenAI 发布了 GPT-5 模型")
        assert sim1 > 0.5, f"相似标题应有高相似度: {sim1}"

        sim2 = calculate_title_similarity("OpenAI 发布 GPT-5", "谷歌发布 Gemini 2")
        assert sim2 < 0.5, f"不同标题应有低相似度: {sim2}"
        print("✓ 测试3: 标题相似度计算通过")
    except Exception as e:
        errors.append(f"测试3失败: {e}")
        print(f"✗ 测试3: {e}")

    # 测试 4: 时间接近度
    try:
        assert are_times_close("2026-01-16T10:00:00+08:00", "2026-01-16T12:00:00+08:00", hours=24)
        assert not are_times_close("2026-01-16T10:00:00+08:00", "2026-01-20T10:00:00+08:00", hours=24)
        print("✓ 测试4: 时间接近度判断通过")
    except Exception as e:
        errors.append(f"测试4失败: {e}")
        print(f"✗ 测试4: {e}")

    # 测试 5: URL 去重
    try:
        @dataclass
        class TestItem:
            title: str
            url: str
            source_id: str
            source_name: str = ""
            title_raw: str = ""
            published_at: Optional[str] = None
            summary: str = ""
            summary_raw: str = ""
            topic: str = "other"
            tags: List = field(default_factory=list)
            mentions: List = field(default_factory=list)
            score: float = 0.0
            flags: List = field(default_factory=list)

        items = [
            TestItem(title="测试文章", url="https://example.com/test", source_id="source1", source_name="信源1"),
            TestItem(title="测试文章", url="https://www.example.com/test/", source_id="source2", source_name="信源2"),
        ]

        result = dedupe_articles(items)
        assert len(result) == 1, f"应去重为 1 条: {len(result)}"
        assert len(result[0].mentions) == 1, f"应有 1 个 mention: {len(result[0].mentions)}"
        print("✓ 测试5: URL 去重通过")
    except Exception as e:
        errors.append(f"测试5失败: {e}")
        print(f"✗ 测试5: {e}")

    # 测试 6: 标题相似度去重
    try:
        items = [
            TestItem(title="OpenAI 发布 GPT-5", url="https://source1.com/a", source_id="s1", source_name="信源1", published_at="2026-01-16T10:00:00+08:00"),
            TestItem(title="OpenAI 发布了 GPT-5 模型", url="https://source2.com/b", source_id="s2", source_name="信源2", published_at="2026-01-16T12:00:00+08:00"),
        ]

        # 不启用标题相似度去重
        result1 = dedupe_articles(items, enable_title_similarity=False)
        assert len(result1) == 2, f"不启用时应保留 2 条: {len(result1)}"

        # 启用标题相似度去重
        result2 = dedupe_articles(items, enable_title_similarity=True, title_similarity_threshold=0.5)
        assert len(result2) == 1, f"启用时应去重为 1 条: {len(result2)}"
        print("✓ 测试6: 标题相似度去重通过")
    except Exception as e:
        errors.append(f"测试6失败: {e}")
        print(f"✗ 测试6: {e}")

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
