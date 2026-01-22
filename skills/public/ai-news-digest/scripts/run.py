#!/usr/bin/env python3
"""
AI 资讯摘要 CLI 入口

用法:
    python run.py [选项]

示例:
    python run.py --day 今天
    python run.py --day yesterday --lang zh
    python run.py --day 2026-01-15 --format json
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# 添加脚本目录到 Python 路径
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

# 导入模块
from time_window import parse_time_window, DEFAULT_TIMEZONE
from fetch_feeds import FeedFetcher, FetchResult
from parse_feeds import parse_feed, ArticleItem
from dedupe import dedupe_articles
from classify_rank import classify_and_rank_articles, TOPICS
from render_digest import render_digest, create_digest, DigestRenderer
from summarize_llm import create_summarizer
from render_image import check_pillow_available, render_image

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo


def _parse_yaml_simple(content: str) -> List[Dict]:
    """
    简化的 YAML 解析器（不依赖 pyyaml）
    仅支持 sources.yaml 的特定结构
    """
    sources = []
    current_source = None
    current_key = None
    in_sources = False

    for line in content.split("\n"):
        # 跳过注释和空行
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # 检测 sources: 段落开始
        if stripped == "sources:":
            in_sources = True
            continue

        # 检测 defaults: 段落（结束 sources 段落）
        if stripped.startswith("defaults:"):
            in_sources = False
            continue

        if not in_sources:
            continue

        # 新的 source 条目
        if stripped.startswith("- id:"):
            if current_source:
                sources.append(current_source)
            source_id = stripped[5:].strip()
            current_source = {"id": source_id, "feeds": [], "topics": [], "flags": []}
            current_key = None
            continue

        if current_source is None:
            continue

        # 解析键值对
        if ":" in stripped and not stripped.startswith("-"):
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()

            # 处理数组值 [item1, item2]
            if value.startswith("[") and value.endswith("]"):
                inner = value[1:-1].strip()
                if inner:
                    items = [item.strip().strip("'\"") for item in inner.split(",")]
                    current_source[key] = items
                else:
                    current_source[key] = []
            # 处理数字
            elif value.isdigit():
                current_source[key] = int(value)
            # 处理空值或待续的数组
            elif value == "" or value == "[]":
                current_source[key] = []
                current_key = key
            else:
                current_source[key] = value

        # 处理数组项 - item
        elif stripped.startswith("- ") and current_key:
            item = stripped[2:].strip()
            if current_key in current_source and isinstance(current_source[current_key], list):
                current_source[current_key].append(item)

    # 添加最后一个
    if current_source:
        sources.append(current_source)

    return sources


def load_sources(sources_path: Optional[str] = None) -> List[Dict]:
    """加载信源配置"""
    if sources_path is None:
        sources_path = SCRIPT_DIR.parent / "references" / "sources.yaml"
    else:
        sources_path = Path(sources_path)

    if not sources_path.exists():
        print(f"警告: 信源配置文件不存在: {sources_path}")
        return []

    with open(sources_path, "r", encoding="utf-8") as f:
        content = f.read()

    if HAS_YAML:
        data = yaml.safe_load(content)
        return data.get("sources", [])
    else:
        # 使用内置简化解析器（不依赖 pyyaml）
        return _parse_yaml_simple(content)


def filter_sources(
    sources: List[Dict],
    enabled_ids: Optional[List[str]] = None,
    exclude_paywall: bool = True
) -> List[Dict]:
    """过滤信源"""
    result = []
    for source in sources:
        source_id = source.get("id", "")
        flags = source.get("flags", [])

        # 排除付费墙
        if exclude_paywall and "paywall" in flags:
            continue

        # 排除无 feed 的信源
        if not source.get("feeds"):
            continue

        # 按指定 ID 过滤
        if enabled_ids and source_id not in enabled_ids:
            continue

        result.append(source)

    return result


def filter_by_time_window(
    items: List[ArticleItem],
    since: str,
    until: str
) -> List[ArticleItem]:
    """按时间窗口过滤文章"""
    try:
        since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        until_dt = datetime.fromisoformat(until.replace("Z", "+00:00"))
    except ValueError:
        return items  # 无法解析时间，返回所有

    result = []
    for item in items:
        if not item.published_at:
            result.append(item)  # 无时间的保留
            continue

        try:
            pub_dt = datetime.fromisoformat(item.published_at.replace("Z", "+00:00"))
            if since_dt <= pub_dt <= until_dt:
                result.append(item)
        except ValueError:
            result.append(item)  # 无法解析的保留

    return result


def run_digest(
    day: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    tz: str = DEFAULT_TIMEZONE,
    lang: str = "zh",
    topics: Optional[List[str]] = None,
    sources: Optional[List[str]] = None,
    output_format: str = "markdown",
    output_path: Optional[str] = None,
    max_items: int = 20,
    max_per_topic: int = 5,
    use_llm: bool = False,
    verbose: bool = False,
    insecure: bool = False,
    image_preset: str = "portrait",
    image_theme: str = "dark"
) -> str:
    """
    运行摘要生成

    Args:
        day: 日期（今天/昨天/前天/YYYY-MM-DD）
        since: 起始时间（ISO 8601）
        until: 结束时间（ISO 8601）
        tz: 时区
        lang: 输出语言
        topics: 主题过滤
        sources: 信源过滤
        output_format: 输出格式（markdown/json/image）
        output_path: 输出文件路径
        max_items: 最大条数
        max_per_topic: 每主题最大条数
        use_llm: 是否使用 LLM 翻译
        verbose: 详细输出
        image_preset: 图片尺寸预设（portrait/landscape/square）
        image_theme: 图片颜色主题（dark/light）

    Returns:
        渲染后的摘要内容或图片路径
    """
    # 1. 解析时间窗口
    if since and until:
        time_window = {"since": since, "until": until, "display": f"{since} ~ {until}"}
    else:
        window_since, window_until = parse_time_window(day, tz)
        date_display = window_since[:10]
        if day:
            date_display = f"{date_display}（{day}）"
        time_window = {
            "since": window_since,
            "until": window_until,
            "display": date_display
        }

    if verbose:
        print(f"时间窗口: {time_window['display']}")

    # 2. 加载信源
    all_sources = load_sources()
    enabled_sources = filter_sources(all_sources, enabled_ids=sources)

    if verbose:
        print(f"启用信源: {len(enabled_sources)} 个")

    if not enabled_sources:
        return "错误: 无可用信源"

    # 3. 抓取 feed
    fetcher = FeedFetcher(insecure=insecure)
    fetch_results = fetcher.fetch_all(enabled_sources)

    successes = [r for r in fetch_results if r.success]
    failures = [r for r in fetch_results if not r.success]

    if verbose:
        print(f"抓取结果: 成功 {len(successes)}, 失败 {len(failures)}")

    # 4. 解析 feed
    all_items: List[ArticleItem] = []
    source_map = {s["id"]: s for s in enabled_sources}

    for result in successes:
        if not result.content:
            continue

        source_config = source_map.get(result.source_id, {})
        source_name = source_config.get("name", result.source_id)

        items, error = parse_feed(
            result.content,
            result.source_id,
            source_name,
            result.url
        )

        if error and verbose:
            print(f"解析警告 ({result.source_id}): {error}")

        all_items.extend(items)

    if verbose:
        print(f"解析条目: {len(all_items)} 条")

    # 5. 按时间窗口过滤
    filtered_items = filter_by_time_window(
        all_items,
        time_window["since"],
        time_window["until"]
    )

    if verbose:
        print(f"时间过滤后: {len(filtered_items)} 条")

    # 6. 去重
    deduped_items = dedupe_articles(filtered_items)

    if verbose:
        print(f"去重后: {len(deduped_items)} 条")

    # 7. 可选 LLM 翻译
    if use_llm and lang == "zh":
        summarizer = create_summarizer()
        if summarizer.is_available():
            if verbose:
                print("正在使用 LLM 翻译...")
            deduped_items = summarizer.process_articles(deduped_items)
        elif verbose:
            print("LLM 不可用，跳过翻译")

    # 8. 分类和排序
    source_weights = {s["id"]: s.get("weight", 5) for s in enabled_sources}
    grouped = classify_and_rank_articles(deduped_items, source_weights=source_weights)

    # 9. 按主题过滤
    if topics:
        grouped = {t: grouped.get(t, []) for t in topics if t in TOPICS}

    # 10. 限制条数
    total_count = 0
    for topic in TOPICS:
        if topic not in grouped:
            continue
        # 每主题限制
        grouped[topic] = grouped[topic][:max_per_topic]
        total_count += len(grouped[topic])
        # 总数限制（简化：按主题顺序截断）
        if total_count >= max_items:
            remaining = max_items - (total_count - len(grouped[topic]))
            grouped[topic] = grouped[topic][:remaining]
            # 清空后续主题
            for t in TOPICS[TOPICS.index(topic)+1:]:
                grouped[t] = []
            break

    # 11. 构建失败列表
    failure_list = []
    for f in failures:
        source_config = source_map.get(f.source_id, {})
        failure_list.append({
            "source_id": f.source_id,
            "source_name": source_config.get("name", f.source_id),
            "reason": f.error or "未知错误",
            "error_code": str(f.status_code) if f.status_code else ""
        })

    # 12. 渲染输出
    if output_format == "image":
        # 图片输出
        if not check_pillow_available():
            return "错误: 图片渲染需要安装 Pillow: pip install Pillow"

        # 默认输出路径
        if not output_path:
            date_str = time_window.get("display", "").split("（")[0].replace("-", "")
            if not date_str or len(date_str) < 8:
                date_str = datetime.now().strftime("%Y%m%d")
            output_path = f"ai_news_{date_str}.png"

        output = render_image(
            grouped,
            time_window,
            output_path,
            preset=image_preset,
            theme=image_theme,
            max_items=min(max_items, 8),  # 图片最多显示 8 条
        )

        if verbose:
            print(f"图片已保存: {output}")

        return output
    else:
        # Markdown/JSON 输出
        template_path = SCRIPT_DIR.parent / "assets" / "digest-template.md"
        output = render_digest(
            grouped,
            time_window,
            failures=failure_list,
            output_format=output_format,
            template_path=str(template_path) if template_path.exists() else None,
            sources_queried=len(enabled_sources),
            sources_succeeded=len(successes),
            lang=lang,
            timezone=tz
        )

        # 13. 写入文件（可选）
        if output_path:
            output_file = Path(output_path)
            output_file.write_text(output, encoding="utf-8")
            if verbose:
                print(f"已写入: {output_path}")

        return output


def main():
    """CLI 主入口"""
    parser = argparse.ArgumentParser(
        description="AI 资讯摘要生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --day 今天                    # 获取今天的资讯
  %(prog)s --day yesterday               # 获取昨天的资讯
  %(prog)s --day 2026-01-15              # 获取指定日期的资讯
  %(prog)s --day 今天 --format json      # 输出 JSON 格式
  %(prog)s --day 今天 --out digest.md    # 写入文件
        """
    )

    # 时间选项
    parser.add_argument(
        "--day", "-d",
        help="日期（今天/昨天/前天/today/yesterday/YYYY-MM-DD）",
        default=None
    )
    parser.add_argument(
        "--since",
        help="起始时间（ISO 8601）",
        default=None
    )
    parser.add_argument(
        "--until",
        help="结束时间（ISO 8601）",
        default=None
    )
    parser.add_argument(
        "--tz",
        help=f"时区（默认 {DEFAULT_TIMEZONE}）",
        default=DEFAULT_TIMEZONE
    )

    # 输出选项
    parser.add_argument(
        "--lang", "-l",
        help="输出语言（auto/zh/en/ja）",
        choices=["auto", "zh", "en", "ja"],
        default="zh"
    )
    parser.add_argument(
        "--format", "-f",
        help="输出格式",
        choices=["markdown", "json", "image"],
        default="markdown"
    )
    parser.add_argument(
        "--image-preset",
        help="图片尺寸预设（portrait=竖版/landscape=横版/square=方形）",
        choices=["portrait", "landscape", "square"],
        default="portrait"
    )
    parser.add_argument(
        "--image-theme",
        help="图片颜色主题",
        choices=["dark", "light"],
        default="dark"
    )
    parser.add_argument(
        "--out", "-o",
        help="输出文件路径",
        default=None
    )

    # 过滤选项
    parser.add_argument(
        "--topics", "-t",
        help="主题过滤（逗号分隔）",
        default=None
    )
    parser.add_argument(
        "--sources", "-s",
        help="信源过滤（ID，逗号分隔）",
        default=None
    )
    parser.add_argument(
        "--max",
        help="最大条数",
        type=int,
        default=20
    )
    parser.add_argument(
        "--max-per-topic",
        help="每主题最大条数",
        type=int,
        default=5
    )

    # 其他选项
    parser.add_argument(
        "--llm",
        help="使用 LLM 翻译",
        action="store_true"
    )
    parser.add_argument(
        "--verbose", "-v",
        help="详细输出",
        action="store_true"
    )
    parser.add_argument(
        "--insecure",
        help="禁用 SSL 证书校验（不推荐，仅用于本地证书链问题）",
        action="store_true"
    )
    parser.add_argument(
        "--test",
        help="运行自测试",
        action="store_true"
    )

    args = parser.parse_args()

    # 运行自测试
    if args.test:
        _run_smoke_test()
        return

    # 解析主题
    topics = None
    if args.topics:
        topics = [t.strip() for t in args.topics.split(",")]

    # 解析信源
    sources = None
    if args.sources:
        sources = [s.strip() for s in args.sources.split(",")]

    # 运行
    try:
        output = run_digest(
            day=args.day,
            since=args.since,
            until=args.until,
            tz=args.tz,
            lang=args.lang,
            topics=topics,
            sources=sources,
            output_format=args.format,
            output_path=args.out,
            max_items=args.max,
            max_per_topic=args.max_per_topic,
            use_llm=args.llm,
            verbose=args.verbose,
            insecure=args.insecure,
            image_preset=args.image_preset,
            image_theme=args.image_theme
        )
        print(output)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _run_smoke_test():
    """运行冒烟测试"""
    print("=== AI 资讯摘要冒烟测试 ===\n")

    errors = []

    # 测试 1: 时间窗口解析
    print("测试1: 时间窗口解析...")
    try:
        from time_window import parse_time_window
        since, until = parse_time_window("今天")
        assert "T00:00:00" in since
        print("  ✓ 通过")
    except Exception as e:
        errors.append(f"时间窗口解析: {e}")
        print(f"  ✗ 失败: {e}")

    # 测试 2: 信源加载
    print("测试2: 信源加载...")
    try:
        sources = load_sources()
        assert len(sources) > 0, "应至少有一个信源"
        print(f"  ✓ 通过（加载 {len(sources)} 个信源）")
    except Exception as e:
        errors.append(f"信源加载: {e}")
        print(f"  ✗ 失败: {e}")

    # 测试 3: 信源过滤
    print("测试3: 信源过滤...")
    try:
        filtered = filter_sources(sources, exclude_paywall=True)
        assert len(filtered) <= len(sources)
        print(f"  ✓ 通过（过滤后 {len(filtered)} 个）")
    except Exception as e:
        errors.append(f"信源过滤: {e}")
        print(f"  ✗ 失败: {e}")

    # 测试 4: 抓取器初始化
    print("测试4: 抓取器初始化...")
    try:
        fetcher = FeedFetcher()
        assert fetcher.timeout == 30
        print("  ✓ 通过")
    except Exception as e:
        errors.append(f"抓取器初始化: {e}")
        print(f"  ✗ 失败: {e}")

    # 测试 5: 抓取单个 feed（使用真实 RSS）
    print("测试5: 抓取单个 feed（Hugging Face Blog）...")
    try:
        result = fetcher.fetch("huggingface_blog", "https://huggingface.co/blog/feed.xml")
        if result.success:
            print(f"  ✓ 通过（状态码: {result.status_code}, 缓存: {result.from_cache}）")
        else:
            print(f"  ⚠ 警告: 抓取失败（{result.error}），可能是网络问题")
    except Exception as e:
        errors.append(f"抓取测试: {e}")
        print(f"  ✗ 失败: {e}")

    # 测试 6: 解析 feed
    print("测试6: 解析 feed...")
    try:
        if result.success and result.content:
            items, error = parse_feed(result.content, "test", "Test Source", result.url)
            if items:
                print(f"  ✓ 通过（解析 {len(items)} 条）")
            elif error:
                print(f"  ⚠ 警告: 解析错误（{error}）")
            else:
                print("  ⚠ 警告: 无条目")
        else:
            print("  ⚠ 跳过（无内容）")
    except Exception as e:
        errors.append(f"解析测试: {e}")
        print(f"  ✗ 失败: {e}")

    # 测试 7: 渲染输出
    print("测试7: 渲染输出...")
    try:
        test_grouped = {
            "research": [],
            "product": [],
            "opensource": [],
            "funding": [],
            "policy": [],
            "other": []
        }
        test_window = {"since": "2026-01-16T00:00:00+08:00", "until": "2026-01-16T23:59:59+08:00", "display": "测试"}
        output = render_digest(test_grouped, test_window)
        assert "AI 资讯简报" in output
        print("  ✓ 通过")
    except Exception as e:
        errors.append(f"渲染测试: {e}")
        print(f"  ✗ 失败: {e}")

    # 汇总
    print()
    if errors:
        print(f"冒烟测试完成，{len(errors)} 个失败:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("✓ 所有冒烟测试通过")
        sys.exit(0)


if __name__ == "__main__":
    main()
