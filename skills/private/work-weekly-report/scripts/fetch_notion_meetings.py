#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notion 会议记录获取脚本

从 Notion 数据库获取指定日期范围内的会议记录

使用方法:
    python3 fetch_notion_meetings.py --start 2026-01-19 --end 2026-01-25
    python3 fetch_notion_meetings.py --week  # 获取本周会议

依赖:
    pip install notion-client
"""

import argparse
import json
import os
import sys
from datetime import datetime, date, timedelta


# 默认配置
DEFAULT_DATABASE_ID = "27056ff3-93f2-80b3-9ae9-000b19738aa0"


def get_week_range(ref_date: date = None) -> tuple[date, date]:
    """获取指定日期所在周的周一到周日"""
    if ref_date is None:
        ref_date = date.today()
    monday = ref_date - timedelta(days=ref_date.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def fetch_meetings(
    token: str,
    database_id: str,
    start_date: date,
    end_date: date
) -> list[dict]:
    """
    从 Notion 获取会议记录

    Args:
        token: Notion API Token
        database_id: Notion 数据库 ID
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        会议记录列表
    """
    try:
        from notion_client import Client
    except ImportError:
        print("错误: 请先安装 notion-client: pip install notion-client", file=sys.stderr)
        sys.exit(1)

    notion = Client(auth=token)

    # 查询数据库
    # 假设数据库有 Date 属性用于会议日期
    results = []
    has_more = True
    start_cursor = None

    while has_more:
        query_params = {
            "database_id": database_id,
            "filter": {
                "and": [
                    {
                        "property": "Date",
                        "date": {
                            "on_or_after": start_date.isoformat()
                        }
                    },
                    {
                        "property": "Date",
                        "date": {
                            "on_or_before": end_date.isoformat()
                        }
                    }
                ]
            },
            "sorts": [
                {
                    "property": "Date",
                    "direction": "ascending"
                }
            ]
        }

        if start_cursor:
            query_params["start_cursor"] = start_cursor

        try:
            response = notion.databases.query(**query_params)
        except Exception as e:
            print(f"查询 Notion 数据库失败: {e}", file=sys.stderr)
            # 尝试不带过滤器查询
            try:
                response = notion.databases.query(database_id=database_id)
            except Exception as e2:
                print(f"再次查询失败: {e2}", file=sys.stderr)
                return []

        results.extend(response.get("results", []))
        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")

    return results


def extract_meeting_info(page: dict) -> dict:
    """从 Notion 页面提取会议信息"""
    properties = page.get("properties", {})

    # 提取标题
    title = ""
    title_prop = properties.get("Name") or properties.get("名称") or properties.get("Title")
    if title_prop:
        title_content = title_prop.get("title", [])
        if title_content:
            title = "".join(t.get("plain_text", "") for t in title_content)

    # 提取日期
    meeting_date = ""
    date_prop = properties.get("Date") or properties.get("日期")
    if date_prop and date_prop.get("date"):
        meeting_date = date_prop["date"].get("start", "")

    # 提取参会人员
    attendees = []
    people_prop = properties.get("Attendees") or properties.get("参会人员") or properties.get("People")
    if people_prop:
        for person in people_prop.get("people", []) or people_prop.get("multi_select", []):
            name = person.get("name", "")
            if name:
                attendees.append(name)

    # 提取会议类型/标签
    tags = []
    tags_prop = properties.get("Tags") or properties.get("标签") or properties.get("Type")
    if tags_prop:
        for tag in tags_prop.get("multi_select", []):
            tags.append(tag.get("name", ""))

    return {
        "id": page.get("id", ""),
        "title": title,
        "date": meeting_date,
        "attendees": attendees,
        "tags": tags,
        "url": page.get("url", "")
    }


def format_output(meetings: list[dict], output_format: str = "text") -> str:
    """格式化输出"""
    if output_format == "json":
        return json.dumps(meetings, ensure_ascii=False, indent=2)

    # 文本格式
    lines = []
    lines.append(f"共找到 {len(meetings)} 条会议记录")
    lines.append("=" * 50)

    for m in meetings:
        lines.append("")
        lines.append(f"【{m['date']}】{m['title']}")
        if m['attendees']:
            lines.append(f"  参会人员: {', '.join(m['attendees'])}")
        if m['tags']:
            lines.append(f"  标签: {', '.join(m['tags'])}")
        if m['url']:
            lines.append(f"  链接: {m['url']}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="从 Notion 获取会议记录")
    parser.add_argument("--token", type=str,
                        default=os.environ.get("NOTION_TOKEN"),
                        help="Notion API Token（或设置 NOTION_TOKEN 环境变量）")
    parser.add_argument("--db-id", type=str, default=DEFAULT_DATABASE_ID,
                        help=f"Notion 数据库 ID（默认：{DEFAULT_DATABASE_ID}）")
    parser.add_argument("--start", type=str, help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--week", action="store_true", help="获取本周会议")
    parser.add_argument("--format", choices=["text", "json"], default="text",
                        help="输出格式（默认：text）")
    args = parser.parse_args()

    # 检查 token
    if not args.token:
        print("错误: 请提供 Notion API Token（--token 或 NOTION_TOKEN 环境变量）", file=sys.stderr)
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

    # 获取会议记录
    pages = fetch_meetings(args.token, args.db_id, start_date, end_date)

    # 提取会议信息
    meetings = [extract_meeting_info(page) for page in pages]

    # 输出结果
    print(format_output(meetings, args.format))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
