#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信工作消息查询脚本

从 DuckDB 数据库查询指定日期范围内的工作相关消息

使用方法:
    python3 query_wechat_messages.py --start 2026-01-19 --end 2026-01-25
    python3 query_wechat_messages.py --week  # 查询本周消息

依赖:
    pip install duckdb pyyaml
"""

import argparse
import json
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

try:
    import duckdb
except ImportError:
    print("错误: 请先安装 duckdb: pip install duckdb", file=sys.stderr)
    sys.exit(1)

try:
    import yaml
except ImportError:
    yaml = None


# 默认配置
DEFAULT_DB_PATH = "/Users/cookie/Documents/wechat/wechat.duckdb"
SCRIPT_DIR = Path(__file__).parent
KEYWORDS_FILE = SCRIPT_DIR.parent / "assets" / "keywords.yaml"

# 默认工作关键词（当 yaml 文件不存在时使用）
DEFAULT_WORK_KEYWORDS = [
    "数仓", "评审", "模型", "专题", "运维", "验收", "巡检", "承诺",
    "血缘", "数据", "任务", "开发", "会议", "需求", "上线", "测试"
]

DEFAULT_WORK_CHAT_KEYWORDS = [
    "运维", "开发", "技术", "对接", "沟通", "项目", "实施", "测试",
    "产业", "平台", "系统", "数据", "中台", "神码", "神州", "东方",
    "国信", "拓尔思", "上奇", "永洪", "大数据部", "国创"
]

DEFAULT_PRIORITY_PATTERNS = ["@淇奥", "@沈淇杰", "紧急", "尽快", "问题", "故障"]


def load_keywords(keywords_file: Path) -> dict:
    """加载关键词配置"""
    if yaml and keywords_file.exists():
        with open(keywords_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    return {
        "work_keywords": DEFAULT_WORK_KEYWORDS,
        "work_chat_keywords": DEFAULT_WORK_CHAT_KEYWORDS,
        "priority_patterns": DEFAULT_PRIORITY_PATTERNS
    }


def get_week_range(ref_date: date = None) -> tuple[date, date]:
    """获取指定日期所在周的周一到周日"""
    if ref_date is None:
        ref_date = date.today()
    monday = ref_date - timedelta(days=ref_date.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def is_work_chat(chat_name: str, keywords: list[str]) -> bool:
    """判断是否工作相关聊天"""
    if not chat_name:
        return False
    return any(kw in chat_name for kw in keywords)


def query_messages(
    db_path: str,
    start_date: date,
    end_date: date,
    keywords_config: dict
) -> dict:
    """
    查询工作相关消息

    Returns:
        {
            "summary": {...},
            "priority_messages": [...],
            "work_chat_messages": [...],
            "keyword_messages": [...]
        }
    """
    conn = duckdb.connect(db_path, read_only=True, config={'access_mode': 'read_only'})

    # 时间戳范围 (毫秒)
    ts_start = int(datetime(start_date.year, start_date.month, start_date.day).timestamp() * 1000)
    ts_end = int(datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59).timestamp() * 1000)

    work_chat_keywords = keywords_config.get("work_chat_keywords", DEFAULT_WORK_CHAT_KEYWORDS)
    work_keywords = keywords_config.get("work_keywords", DEFAULT_WORK_KEYWORDS)
    priority_patterns = keywords_config.get("priority_patterns", DEFAULT_PRIORITY_PATTERNS)

    result = {
        "date_range": f"{start_date} ~ {end_date}",
        "summary": {},
        "priority_messages": [],
        "work_chat_messages": [],
        "keyword_messages": []
    }

    # 统计信息
    total = conn.execute(f"""
        SELECT COUNT(*) FROM wechat_message
        WHERE message_ts >= {ts_start} AND message_ts <= {ts_end}
    """).fetchone()[0]
    result["summary"]["total_messages"] = total

    # 获取所有文本消息
    all_messages = conn.execute(f"""
        SELECT chat_name, sender_name, text, message_ts
        FROM wechat_message
        WHERE message_ts >= {ts_start} AND message_ts <= {ts_end}
          AND msg_type = 1
          AND text IS NOT NULL AND text != ''
        ORDER BY message_ts
    """).fetchall()

    work_chat_count = 0

    for chat_name, sender_name, text, ts in all_messages:
        time_str = datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d %H:%M')
        msg_info = {
            "time": time_str,
            "chat": chat_name or "未知",
            "sender": sender_name or "未知",
            "text": text[:200] if text else ""
        }

        # 检查优先级消息（被@或紧急）
        if any(p in text for p in priority_patterns):
            result["priority_messages"].append(msg_info)

        # 检查工作群消息
        if is_work_chat(chat_name, work_chat_keywords):
            work_chat_count += 1
            # 只保留包含工作关键词的消息
            if any(kw in text for kw in work_keywords):
                result["work_chat_messages"].append(msg_info)

        # 检查包含工作关键词的消息
        elif any(kw in text for kw in work_keywords):
            result["keyword_messages"].append(msg_info)

    result["summary"]["work_chat_messages"] = work_chat_count
    result["summary"]["priority_count"] = len(result["priority_messages"])
    result["summary"]["keyword_match_count"] = len(result["work_chat_messages"]) + len(result["keyword_messages"])

    conn.close()

    # 限制输出数量，避免过多
    result["priority_messages"] = result["priority_messages"][:50]
    result["work_chat_messages"] = result["work_chat_messages"][:100]
    result["keyword_messages"] = result["keyword_messages"][:50]

    return result


def format_output(data: dict, output_format: str = "text") -> str:
    """格式化输出"""
    if output_format == "json":
        return json.dumps(data, ensure_ascii=False, indent=2)

    # 文本格式
    lines = []
    lines.append(f"查询日期: {data['date_range']}")
    lines.append("=" * 60)

    summary = data["summary"]
    lines.append(f"\n【统计摘要】")
    lines.append(f"  消息总数: {summary.get('total_messages', 0):,}")
    lines.append(f"  工作群消息: {summary.get('work_chat_messages', 0):,}")
    lines.append(f"  优先消息数: {summary.get('priority_count', 0)}")
    lines.append(f"  关键词匹配: {summary.get('keyword_match_count', 0)}")

    # 优先消息
    if data["priority_messages"]:
        lines.append(f"\n\n【优先消息】（共 {len(data['priority_messages'])} 条）")
        lines.append("-" * 50)
        for msg in data["priority_messages"]:
            lines.append(f"\n[{msg['time']}] {msg['chat']}")
            lines.append(f"  {msg['sender']}: {msg['text']}")

    # 工作群消息
    if data["work_chat_messages"]:
        lines.append(f"\n\n【工作群关键消息】（共 {len(data['work_chat_messages'])} 条）")
        lines.append("-" * 50)
        for msg in data["work_chat_messages"]:
            lines.append(f"\n[{msg['time']}] {msg['chat']}")
            lines.append(f"  {msg['sender']}: {msg['text']}")

    # 其他关键词消息
    if data["keyword_messages"]:
        lines.append(f"\n\n【其他关键词消息】（共 {len(data['keyword_messages'])} 条）")
        lines.append("-" * 50)
        for msg in data["keyword_messages"][:20]:  # 只显示前20条
            lines.append(f"\n[{msg['time']}] {msg['chat']}")
            lines.append(f"  {msg['sender']}: {msg['text']}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="查询微信工作相关消息")
    parser.add_argument("--db", type=str, default=DEFAULT_DB_PATH,
                        help=f"DuckDB 数据库路径（默认：{DEFAULT_DB_PATH}）")
    parser.add_argument("--start", type=str, help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--week", action="store_true", help="查询本周消息")
    parser.add_argument("--keywords", type=str, default=str(KEYWORDS_FILE),
                        help=f"关键词配置文件（默认：{KEYWORDS_FILE}）")
    parser.add_argument("--format", choices=["text", "json"], default="text",
                        help="输出格式（默认：text）")
    args = parser.parse_args()

    # 检查数据库
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"错误: 数据库文件不存在: {db_path}", file=sys.stderr)
        return 1

    # 确定日期范围
    if args.week:
        start_date, end_date = get_week_range()
    elif args.start and args.end:
        try:
            start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
            end_date = datetime.strptime(args.end, "%Y-%m-%d").date()
        except ValueError as e:
            print(f"日期格式错误: {e}", file=sys.stderr)
            return 1
    else:
        print("错误: 请指定日期范围（--start/--end）或使用 --week", file=sys.stderr)
        return 1

    print(f"查询日期范围: {start_date} ~ {end_date}", file=sys.stderr)

    # 加载关键词配置
    keywords_config = load_keywords(Path(args.keywords))

    # 查询消息
    data = query_messages(str(db_path), start_date, end_date, keywords_config)

    # 输出结果
    print(format_output(data, args.format))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
