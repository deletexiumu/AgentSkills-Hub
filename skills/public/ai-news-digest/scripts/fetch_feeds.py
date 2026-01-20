#!/usr/bin/env python3
"""
Feed 抓取器模块

功能：
- 域名级别限速
- 超时与重试（带 jitter）
- ETag/Last-Modified 缓存
- 本地缓存目录输出
"""

import hashlib
import json
import os
import random
import time
import urllib.request
import urllib.error
import ssl
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo


@dataclass
class FetchResult:
    """抓取结果"""
    source_id: str
    url: str
    success: bool
    content: Optional[str] = None
    content_type: Optional[str] = None
    status_code: Optional[int] = None
    error: Optional[str] = None
    from_cache: bool = False
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    fetched_at: str = field(default_factory=lambda: datetime.now(ZoneInfo("Asia/Shanghai")).isoformat())


@dataclass
class CacheEntry:
    """缓存条目"""
    url: str
    content: str
    content_type: str
    etag: Optional[str]
    last_modified: Optional[str]
    cached_at: str
    expires_at: str


class RateLimiter:
    """域名级别限速器"""

    def __init__(self, requests_per_second: float = 2.0):
        self.min_interval = 1.0 / requests_per_second
        self.last_request: Dict[str, float] = {}

    def wait(self, domain: str) -> None:
        """等待直到可以请求该域名"""
        now = time.time()
        if domain in self.last_request:
            elapsed = now - self.last_request[domain]
            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                # 添加 jitter（0-20% 额外等待）
                wait_time += random.uniform(0, wait_time * 0.2)
                time.sleep(wait_time)
        self.last_request[domain] = time.time()


class FeedFetcher:
    """Feed 抓取器"""

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        rate_limit: float = 2.0,
        cache_ttl_minutes: int = 15,
        user_agent: str = "AI-News-Digest/1.0 (RSS Reader)",
        insecure: bool = False
    ):
        """
        初始化抓取器

        Args:
            cache_dir: 缓存目录路径，None 则使用临时目录
            timeout: 请求超时（秒）
            max_retries: 最大重试次数
            rate_limit: 每秒每域名最大请求数
            cache_ttl_minutes: 缓存有效期（分钟）
            user_agent: User-Agent 字符串
            insecure: 禁用 SSL 证书校验（不推荐，仅用于本地环境证书问题）
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.cache_ttl_minutes = cache_ttl_minutes
        self.user_agent = user_agent
        self.rate_limiter = RateLimiter(rate_limit)
        self.insecure = insecure
        self._ssl_context = ssl._create_unverified_context() if insecure else ssl.create_default_context()

        # 设置缓存目录
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path.home() / ".cache" / "ai-news-digest" / "feeds"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, url: str) -> Path:
        """获取 URL 对应的缓存文件路径"""
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return self.cache_dir / f"{url_hash}.json"

    def _load_cache(self, url: str) -> Optional[CacheEntry]:
        """加载缓存"""
        cache_path = self._get_cache_path(url)
        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                entry = CacheEntry(**data)

            # 检查是否过期
            expires_at = datetime.fromisoformat(entry.expires_at)
            if datetime.now(expires_at.tzinfo or ZoneInfo("Asia/Shanghai")) > expires_at:
                return None

            return entry
        except (json.JSONDecodeError, TypeError, KeyError):
            return None

    def _save_cache(
        self,
        url: str,
        content: str,
        content_type: str,
        etag: Optional[str],
        last_modified: Optional[str]
    ) -> None:
        """保存缓存"""
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        expires_at = datetime.fromtimestamp(
            now.timestamp() + self.cache_ttl_minutes * 60,
            tz=ZoneInfo("Asia/Shanghai")
        )

        entry = CacheEntry(
            url=url,
            content=content,
            content_type=content_type,
            etag=etag,
            last_modified=last_modified,
            cached_at=now.isoformat(),
            expires_at=expires_at.isoformat()
        )

        cache_path = self._get_cache_path(url)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(asdict(entry), f, ensure_ascii=False, indent=2)

    def _fetch_with_retry(
        self,
        url: str,
        cached_etag: Optional[str] = None,
        cached_last_modified: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str], int, Optional[str], Optional[str]]:
        """
        带重试的抓取

        Returns:
            (content, content_type, status_code, etag, last_modified)
            content 为 None 表示 304 Not Modified 或失败
        """
        domain = urlparse(url).netloc
        last_error = None

        for attempt in range(self.max_retries):
            try:
                # 域名限速
                self.rate_limiter.wait(domain)

                # 构建请求
                request = urllib.request.Request(url)
                request.add_header("User-Agent", self.user_agent)
                request.add_header("Accept", "application/rss+xml, application/atom+xml, application/xml, text/xml, */*")

                # 条件请求
                if cached_etag:
                    request.add_header("If-None-Match", cached_etag)
                if cached_last_modified:
                    request.add_header("If-Modified-Since", cached_last_modified)

                # 发送请求
                with urllib.request.urlopen(request, timeout=self.timeout, context=self._ssl_context) as response:
                    status_code = response.status
                    content_type = response.headers.get("Content-Type", "")
                    etag = response.headers.get("ETag")
                    last_modified = response.headers.get("Last-Modified")

                    # 304 Not Modified
                    if status_code == 304:
                        return None, content_type, 304, etag, last_modified

                    # 读取内容
                    content = response.read()
                    # 尝试检测编码
                    encoding = "utf-8"
                    if "charset=" in content_type:
                        encoding = content_type.split("charset=")[-1].split(";")[0].strip()
                    try:
                        content_str = content.decode(encoding)
                    except (UnicodeDecodeError, LookupError):
                        content_str = content.decode("utf-8", errors="replace")

                    return content_str, content_type, status_code, etag, last_modified

            except urllib.error.HTTPError as e:
                last_error = f"HTTP {e.code}: {e.reason}"
                if e.code in (403, 404, 410):  # 不重试
                    return None, None, e.code, None, None
            except urllib.error.URLError as e:
                last_error = f"URL 错误: {e.reason}"
            except TimeoutError:
                last_error = "请求超时"
            except Exception as e:
                last_error = f"未知错误: {str(e)}"

            # 重试前等待（指数退避 + jitter）
            if attempt < self.max_retries - 1:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(wait_time)

        return None, None, 0, None, last_error

    def fetch(self, source_id: str, url: str, use_cache: bool = True) -> FetchResult:
        """
        抓取单个 feed

        Args:
            source_id: 信源 ID
            url: feed URL
            use_cache: 是否使用缓存

        Returns:
            FetchResult 对象
        """
        # 尝试加载缓存
        cached = None
        if use_cache:
            cached = self._load_cache(url)
            if cached:
                return FetchResult(
                    source_id=source_id,
                    url=url,
                    success=True,
                    content=cached.content,
                    content_type=cached.content_type,
                    status_code=200,
                    from_cache=True,
                    etag=cached.etag,
                    last_modified=cached.last_modified
                )

        # 发起请求
        content, content_type, status_code, etag, last_modified = self._fetch_with_retry(
            url,
            cached_etag=cached.etag if cached else None,
            cached_last_modified=cached.last_modified if cached else None
        )

        # 304 Not Modified，使用缓存
        if status_code == 304 and cached:
            return FetchResult(
                source_id=source_id,
                url=url,
                success=True,
                content=cached.content,
                content_type=cached.content_type,
                status_code=304,
                from_cache=True,
                etag=cached.etag,
                last_modified=cached.last_modified
            )

        # 成功获取新内容
        if content and status_code == 200:
            # 保存缓存
            if use_cache:
                self._save_cache(url, content, content_type, etag, last_modified)

            return FetchResult(
                source_id=source_id,
                url=url,
                success=True,
                content=content,
                content_type=content_type,
                status_code=status_code,
                etag=etag,
                last_modified=last_modified
            )

        # 失败
        error_msg = last_modified if status_code == 0 else f"HTTP {status_code}"
        return FetchResult(
            source_id=source_id,
            url=url,
            success=False,
            status_code=status_code if status_code else None,
            error=error_msg
        )

    def fetch_all(
        self,
        sources: List[Dict],
        use_cache: bool = True
    ) -> List[FetchResult]:
        """
        批量抓取多个信源

        Args:
            sources: 信源配置列表，每个包含 id, feeds 字段
            use_cache: 是否使用缓存

        Returns:
            FetchResult 列表
        """
        results = []
        for source in sources:
            source_id = source.get("id", "unknown")
            feeds = source.get("feeds", [])

            if not feeds:
                results.append(FetchResult(
                    source_id=source_id,
                    url="",
                    success=False,
                    error="无可用的 feed URL"
                ))
                continue

            # 尝试第一个可用的 feed
            for feed_url in feeds:
                result = self.fetch(source_id, feed_url, use_cache)
                results.append(result)
                if result.success:
                    break  # 成功则跳过备选 feed

        return results

    def clear_cache(self, max_age_hours: int = 24) -> int:
        """
        清理过期缓存

        Args:
            max_age_hours: 超过此小时数的缓存将被删除

        Returns:
            删除的文件数量
        """
        deleted = 0
        cutoff = time.time() - max_age_hours * 3600

        for cache_file in self.cache_dir.glob("*.json"):
            if cache_file.stat().st_mtime < cutoff:
                cache_file.unlink()
                deleted += 1

        return deleted


# ============ 自测试 ============
def _run_self_tests():
    """运行内置自测试"""
    import sys
    import tempfile

    errors = []

    # 测试 1: 初始化
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = FeedFetcher(cache_dir=tmpdir)
            assert fetcher.timeout == 30
            assert fetcher.max_retries == 3
        print("✓ 测试1: 初始化通过")
    except Exception as e:
        errors.append(f"测试1失败: {e}")
        print(f"✗ 测试1: {e}")

    # 测试 2: 限速器
    try:
        limiter = RateLimiter(requests_per_second=10)  # 每秒 10 次
        start = time.time()
        limiter.wait("example.com")
        limiter.wait("example.com")
        elapsed = time.time() - start
        assert elapsed >= 0.08, f"限速应至少等待 0.08 秒，实际 {elapsed}"
        print("✓ 测试2: 限速器通过")
    except Exception as e:
        errors.append(f"测试2失败: {e}")
        print(f"✗ 测试2: {e}")

    # 测试 3: 缓存路径生成
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = FeedFetcher(cache_dir=tmpdir)
            path1 = fetcher._get_cache_path("https://example.com/feed1")
            path2 = fetcher._get_cache_path("https://example.com/feed2")
            assert path1 != path2, "不同 URL 应有不同缓存路径"
            assert path1.suffix == ".json"
        print("✓ 测试3: 缓存路径生成通过")
    except Exception as e:
        errors.append(f"测试3失败: {e}")
        print(f"✗ 测试3: {e}")

    # 测试 4: FetchResult 数据结构
    try:
        result = FetchResult(
            source_id="test",
            url="https://example.com/feed",
            success=True,
            content="<rss>...</rss>",
            status_code=200
        )
        assert result.source_id == "test"
        assert result.success is True
        assert result.from_cache is False
        print("✓ 测试4: FetchResult 数据结构通过")
    except Exception as e:
        errors.append(f"测试4失败: {e}")
        print(f"✗ 测试4: {e}")

    # 测试 5: 缓存保存和加载
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = FeedFetcher(cache_dir=tmpdir, cache_ttl_minutes=60)
            url = "https://test.example.com/feed"

            # 保存
            fetcher._save_cache(url, "<content>", "application/xml", "etag123", "Mon, 01 Jan 2026 00:00:00 GMT")

            # 加载
            cached = fetcher._load_cache(url)
            assert cached is not None, "缓存应存在"
            assert cached.content == "<content>"
            assert cached.etag == "etag123"
        print("✓ 测试5: 缓存保存和加载通过")
    except Exception as e:
        errors.append(f"测试5失败: {e}")
        print(f"✗ 测试5: {e}")

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
