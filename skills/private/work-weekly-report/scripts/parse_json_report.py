#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
周报原始内容解析脚本

从周报原始内容.json中解析周报，生成Markdown格式文件

使用方法:
    python3 parse_json_report.py          # 解析最新一期
    python3 parse_json_report.py --all    # 解析所有周报
    python3 parse_json_report.py -n 3     # 解析最新3期
"""

import argparse
import json
import re
from datetime import datetime, timedelta
from pathlib import Path


# 默认配置
DEFAULT_JSON_PATH = "/Users/cookie/Documents/个人周报/周报原始内容.json"
DEFAULT_OUTPUT_DIR = "/Users/cookie/Documents/个人周报"


def strip_html_tags(text: str) -> str:
    """移除HTML标签，保留格式"""
    if not text:
        return ""
    # 替换<br>和<br />为换行
    text = re.sub(r'<br\s*/?>', '\n', text)
    # 替换<p>和</p>标签
    text = re.sub(r'</?p>', '\n', text)
    # 替换&nbsp;为空格
    text = text.replace('&nbsp;', ' ')
    # 移除<span>标签但保留内容
    text = re.sub(r'</?span[^>]*>', '', text)
    # 移除其他HTML标签
    text = re.sub(r'<[^>]+>', '', text)
    # 清理行首空白但保留缩进空格
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            cleaned_lines.append(stripped)
    # 合并多个空行为一个
    result = '\n'.join(cleaned_lines)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()


def parse_date_range(end_date: str) -> tuple:
    """从结束日期推算周报的周数和日期范围"""
    dt = datetime.strptime(end_date.split()[0], "%Y-%m-%d")
    year = dt.year
    week_num = dt.isocalendar()[1]

    # 获取该周的周一
    monday = dt - timedelta(days=dt.weekday())
    sunday = monday + timedelta(days=6)

    start_str = monday.strftime("%m.%d")
    end_str = sunday.strftime("%m.%d")

    return year, week_num, start_str, end_str


def generate_markdown(report: dict) -> str:
    """生成Markdown格式的周报"""
    end_date = report.get("endDate", "")
    year, week_num, start_date, end_date_str = parse_date_range(end_date)

    job_responsibility = report.get("jobResponsibility", "")
    work_plans = report.get("workPlan") or []
    reviews = report.get("reviews") or []
    reviews_responsibility = report.get("reviewsResponsibility") or []

    lines = []
    lines.append(f"# 沈淇杰 {year} 第{week_num}周 ({start_date}~{end_date_str}) 的工作周报")
    lines.append("")
    lines.append("## 岗位职责")
    lines.append("")
    lines.append(job_responsibility)
    lines.append("")
    lines.append(f"## {year}年工作计划")
    lines.append("")

    for idx, wp in enumerate(work_plans, 1):
        work_name = wp.get("workName", "")
        year_goal = wp.get("yearGoal", "")
        quarter_goal = wp.get("quarterGoal", "")
        week_sum = strip_html_tags(wp.get("weekSum", ""))
        radio = wp.get("radio", "")

        lines.append(f"### {idx}. {work_name}")
        lines.append("")
        lines.append(f"- **{year}年主要目标**：{year_goal}")
        lines.append(f"- **Q1目标**：{quarter_goal}")
        lines.append(f"- **周进展**（精力占比：{radio}%）：")
        lines.append(week_sum)
        lines.append("")
        lines.append("- **下周计划**：")

        # 解析下周计划列表
        next_week_list = wp.get("nextWeekList") or []
        for item in next_week_list:
            matter = strip_html_tags(item.get("matter", ""))
            items_list = item.get("items") or []
            if matter:
                lines.append(matter)
            for sub_item in items_list:
                goal = strip_html_tags(sub_item.get("goal", ""))
                dates = sub_item.get("dates") or []
                if goal:
                    lines.append(goal)
                if dates:
                    lines.append("、".join(dates))
            lines.append("")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 领导审批意见")
    lines.append("")

    # 合并所有评审意见
    all_reviews = []
    for r in reviews:
        if r.get("review"):
            all_reviews.append(r)
    for r in reviews_responsibility:
        if r.get("review"):
            all_reviews.append(r)

    for r in all_reviews:
        creator = r.get("creator") or {}
        name = creator.get("name", "")
        create_time = r.get("createTime", "")
        review_text = strip_html_tags(r.get("review", ""))
        if name and review_text:
            lines.append(f"### {name} ({create_time})")
            lines.append("")
            lines.append(review_text)
            lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="解析周报原始内容JSON文件")
    parser.add_argument("--json", "-j", type=str, default=DEFAULT_JSON_PATH,
                        help=f"周报JSON文件路径（默认：{DEFAULT_JSON_PATH}）")
    parser.add_argument("--output", "-o", type=str, default=DEFAULT_OUTPUT_DIR,
                        help=f"输出目录（默认：{DEFAULT_OUTPUT_DIR}）")
    parser.add_argument("--all", action="store_true", help="解析所有周报")
    parser.add_argument("-n", type=int, default=1, help="解析最新N期周报（默认1）")
    args = parser.parse_args()

    json_file = Path(args.json)
    output_dir = Path(args.output)

    if not json_file.exists():
        print(f"错误: 找不到文件 {json_file}")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    reports = data.get("list") or []
    if not reports:
        print("错误: 没有找到周报数据")
        return 1

    # 确定要解析的数量
    count = len(reports) if args.all else min(args.n, len(reports))

    for i in range(count):
        report = reports[i]
        markdown_content = generate_markdown(report)

        # 生成文件名
        end_date = report.get("endDate", "")
        year, week_num, start_date, end_date_str = parse_date_range(end_date)
        output_file = output_dir / f"沈淇杰 {year} 第{week_num}周 ({start_date}~{end_date_str}) 的工作周报.md"

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        print(f"已生成: {output_file.name}")

    print(f"\n共生成 {count} 份周报")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
