#!/usr/bin/env python3
"""
摘要渲染器模块

功能：
- 渲染 Markdown 格式摘要
- 可选输出 JSON 格式
- 支持模板替换
"""

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo


# 主题中文名称映射
TOPIC_NAMES = {
    "research": "研究 / 论文 / 实验室",
    "product": "产品 / 模型 / 发布",
    "opensource": "开源 / 工具 / 工程",
    "funding": "投融资 / 商业",
    "policy": "政策 / 伦理 / 安全",
    "other": "其他",
}

TOPIC_ORDER = ["research", "product", "opensource", "funding", "policy", "other"]


@dataclass
class DigestMeta:
    """摘要元数据"""
    generated_at: str
    time_window: Dict[str, str]
    lang: str = "zh"
    timezone: str = "Asia/Shanghai"
    sources_queried: int = 0
    sources_succeeded: int = 0
    total_items: int = 0


@dataclass
class SourceFailure:
    """信源失败记录"""
    source_id: str
    source_name: str
    reason: str
    error_code: str = ""
    timestamp: str = ""


@dataclass
class Digest:
    """完整摘要"""
    meta: DigestMeta
    sections: Dict[str, List]
    failures: List[SourceFailure] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "meta": asdict(self.meta),
            "sections": {
                topic: [
                    item.to_dict() if hasattr(item, 'to_dict') else asdict(item)
                    for item in items
                ]
                for topic, items in self.sections.items()
            },
            "failures": [asdict(f) for f in self.failures]
        }


class DigestRenderer:
    """摘要渲染器"""

    def __init__(
        self,
        template_path: Optional[str] = None,
        output_lang: str = "zh"
    ):
        """
        初始化渲染器

        Args:
            template_path: 模板文件路径（可选）
            output_lang: 输出语言
        """
        self.output_lang = output_lang
        self.template = self._load_template(template_path)

    def _load_template(self, template_path: Optional[str]) -> str:
        """加载模板"""
        if template_path:
            path = Path(template_path)
            if path.exists():
                return path.read_text(encoding="utf-8")

        # 默认模板
        return """# AI 资讯简报（{{ date }}）

> 时间窗口：{{ window }}
> 语言：{{ lang }}
> 信源：{{ sources }}

{{ content }}

{{ failures }}
"""

    def _format_date(self, iso_date: Optional[str]) -> str:
        """格式化日期"""
        if not iso_date:
            return "未知"
        try:
            dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, AttributeError):
            return iso_date[:10] if len(iso_date) >= 10 else iso_date

    def _render_article(self, item: Any) -> str:
        """渲染单篇文章"""
        title = getattr(item, 'title', '未知标题')
        url = getattr(item, 'url', '')
        source_name = getattr(item, 'source_name', '')
        published_at = self._format_date(getattr(item, 'published_at', None))
        summary = getattr(item, 'summary', '')
        tags = getattr(item, 'tags', [])

        # 检查是否未翻译
        flags = getattr(item, 'flags', [])
        untranslated_mark = "（未翻译）" if "untranslated" in flags else ""

        lines = [
            f"- **{title}**{untranslated_mark}（{source_name}，{published_at}）",
            f"  - 链接：{url}",
        ]

        if summary:
            lines.append(f"  - 摘要：{summary}")

        if tags:
            lines.append(f"  - 标签：{', '.join(tags[:5])}")

        # 显示多信源提及
        mentions = getattr(item, 'mentions', [])
        if mentions:
            mention_strs = [f"{m.get('source_name', m.get('source_id', ''))}" for m in mentions]
            lines.append(f"  - 同时报道：{', '.join(mention_strs)}")

        return "\n".join(lines)

    def _render_section(self, topic: str, items: List) -> str:
        """渲染单个主题分区"""
        if not items:
            return ""

        topic_name = TOPIC_NAMES.get(topic, topic)
        lines = [f"## {topic_name}", ""]

        for item in items:
            lines.append(self._render_article(item))
            lines.append("")

        return "\n".join(lines)

    def _render_failures(self, failures: List[SourceFailure]) -> str:
        """渲染失败列表"""
        if not failures:
            return ""

        lines = ["## 抓取失败的信源", ""]
        for f in failures:
            lines.append(f"- **{f.source_name}**（{f.source_id}）：{f.reason}")

        return "\n".join(lines)

    def render_markdown(self, digest: Digest) -> str:
        """
        渲染为 Markdown 格式

        Args:
            digest: 摘要数据

        Returns:
            Markdown 字符串
        """
        # 准备元数据
        window = digest.meta.time_window
        window_display = window.get("display", f"{window.get('since', '')} ~ {window.get('until', '')}")
        date_str = self._format_date(digest.meta.generated_at)[:10]

        # 构建输出
        lines = [
            f"# AI 资讯简报（{date_str}）",
            "",
            f"> 时间窗口：{window_display}",
            f"> 语言：{'中文' if digest.meta.lang == 'zh' else digest.meta.lang}",
            f"> 信源：共 {digest.meta.sources_queried} 个，成功 {digest.meta.sources_succeeded} 个",
            "",
        ]

        # 渲染各主题分区
        for topic in TOPIC_ORDER:
            items = digest.sections.get(topic, [])
            if items:
                section_content = self._render_section(topic, items)
                lines.append(section_content)
                lines.append("")

        # 渲染失败列表
        if digest.failures:
            lines.append(self._render_failures(digest.failures))
            lines.append("")

        return "\n".join(lines).strip()

    def render_json(self, digest: Digest, pretty: bool = True) -> str:
        """
        渲染为 JSON 格式

        Args:
            digest: 摘要数据
            pretty: 是否美化输出

        Returns:
            JSON 字符串
        """
        data = digest.to_dict()
        if pretty:
            return json.dumps(data, ensure_ascii=False, indent=2)
        return json.dumps(data, ensure_ascii=False)


def create_digest(
    grouped_items: Dict[str, List],
    time_window: Dict[str, str],
    failures: Optional[List[Dict]] = None,
    sources_queried: int = 0,
    sources_succeeded: int = 0,
    lang: str = "zh",
    timezone: str = "Asia/Shanghai"
) -> Digest:
    """
    创建摘要对象

    Args:
        grouped_items: 按主题分组的文章
        time_window: 时间窗口 {since, until, display}
        failures: 失败列表
        sources_queried: 查询的信源数
        sources_succeeded: 成功的信源数
        lang: 输出语言
        timezone: 时区

    Returns:
        Digest 对象
    """
    # 计算总条数
    total_items = sum(len(items) for items in grouped_items.values())

    meta = DigestMeta(
        generated_at=datetime.now(ZoneInfo(timezone)).isoformat(),
        time_window=time_window,
        lang=lang,
        timezone=timezone,
        sources_queried=sources_queried,
        sources_succeeded=sources_succeeded,
        total_items=total_items
    )

    # 转换失败列表
    failure_objs = []
    for f in (failures or []):
        failure_objs.append(SourceFailure(
            source_id=f.get("source_id", ""),
            source_name=f.get("source_name", ""),
            reason=f.get("reason", "未知错误"),
            error_code=f.get("error_code", ""),
            timestamp=f.get("timestamp", "")
        ))

    return Digest(
        meta=meta,
        sections=grouped_items,
        failures=failure_objs
    )


def render_digest(
    grouped_items: Dict[str, List],
    time_window: Dict[str, str],
    failures: Optional[List[Dict]] = None,
    output_format: str = "markdown",
    template_path: Optional[str] = None,
    **kwargs
) -> str:
    """
    便捷函数：渲染摘要

    Args:
        grouped_items: 按主题分组的文章
        time_window: 时间窗口
        failures: 失败列表
        output_format: 输出格式（markdown/json）
        template_path: 模板路径
        **kwargs: 其他参数（传给 create_digest）

    Returns:
        渲染后的字符串
    """
    digest = create_digest(grouped_items, time_window, failures, **kwargs)
    renderer = DigestRenderer(template_path=template_path)

    if output_format == "json":
        return renderer.render_json(digest)
    return renderer.render_markdown(digest)


# ============ 自测试 ============
def _run_self_tests():
    """运行内置自测试"""
    import sys
    from dataclasses import dataclass, field

    errors = []

    # 测试数据类
    @dataclass
    class TestItem:
        title: str
        url: str
        source_id: str
        source_name: str = ""
        published_at: Optional[str] = None
        summary: str = ""
        tags: List[str] = field(default_factory=list)
        mentions: List[Dict] = field(default_factory=list)
        flags: List[str] = field(default_factory=list)

        def to_dict(self):
            return asdict(self)

    # 测试 1: 创建摘要对象
    try:
        grouped = {
            "research": [TestItem(
                title="测试论文",
                url="https://example.com/paper",
                source_id="test",
                source_name="测试信源",
                published_at="2026-01-16T10:00:00+08:00",
                summary="这是摘要"
            )],
            "product": [],
            "opensource": [],
            "funding": [],
            "policy": [],
            "other": []
        }
        time_window = {
            "since": "2026-01-16T00:00:00+08:00",
            "until": "2026-01-16T23:59:59+08:00",
            "display": "2026-01-16（今天）"
        }
        digest = create_digest(grouped, time_window, sources_queried=5, sources_succeeded=4)
        assert digest.meta.total_items == 1, f"应有 1 条: {digest.meta.total_items}"
        print("✓ 测试1: 创建摘要对象通过")
    except Exception as e:
        errors.append(f"测试1失败: {e}")
        print(f"✗ 测试1: {e}")

    # 测试 2: 渲染 Markdown
    try:
        renderer = DigestRenderer()
        md = renderer.render_markdown(digest)
        assert "AI 资讯简报" in md, "Markdown 应包含标题"
        assert "测试论文" in md, "Markdown 应包含文章标题"
        assert "研究" in md, "Markdown 应包含主题名称"
        print("✓ 测试2: 渲染 Markdown 通过")
    except Exception as e:
        errors.append(f"测试2失败: {e}")
        print(f"✗ 测试2: {e}")

    # 测试 3: 渲染 JSON
    try:
        json_str = renderer.render_json(digest)
        data = json.loads(json_str)
        assert "meta" in data, "JSON 应包含 meta"
        assert "sections" in data, "JSON 应包含 sections"
        assert data["meta"]["total_items"] == 1
        print("✓ 测试3: 渲染 JSON 通过")
    except Exception as e:
        errors.append(f"测试3失败: {e}")
        print(f"✗ 测试3: {e}")

    # 测试 4: 便捷函数
    try:
        md = render_digest(grouped, time_window, output_format="markdown", sources_queried=5, sources_succeeded=4)
        assert "AI 资讯简报" in md
        print("✓ 测试4: 便捷函数（Markdown）通过")
    except Exception as e:
        errors.append(f"测试4失败: {e}")
        print(f"✗ 测试4: {e}")

    # 测试 5: 失败列表渲染
    try:
        failures = [{"source_id": "fail1", "source_name": "失败信源", "reason": "连接超时"}]
        digest_with_fail = create_digest(grouped, time_window, failures=failures)
        md = renderer.render_markdown(digest_with_fail)
        assert "抓取失败" in md, "应包含失败信息"
        assert "连接超时" in md, "应包含失败原因"
        print("✓ 测试5: 失败列表渲染通过")
    except Exception as e:
        errors.append(f"测试5失败: {e}")
        print(f"✗ 测试5: {e}")

    # 测试 6: 多信源提及
    try:
        item_with_mentions = TestItem(
            title="热门新闻",
            url="https://example.com/hot",
            source_id="s1",
            source_name="信源1",
            mentions=[
                {"source_id": "s2", "source_name": "信源2", "url": "https://other.com/hot"},
            ]
        )
        grouped_mentions = {"research": [item_with_mentions], "product": [], "opensource": [], "funding": [], "policy": [], "other": []}
        md = render_digest(grouped_mentions, time_window)
        assert "同时报道" in md, "应包含多信源提及"
        print("✓ 测试6: 多信源提及通过")
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
