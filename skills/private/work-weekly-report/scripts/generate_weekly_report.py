#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
周报生成主程序

支持两种模式:
1. parse: 解析周报原始 JSON，生成 Markdown 文件
2. generate: 收集多数据源信息，输出供 AI 整合的原始数据

使用方法:
    # 解析模式
    python3 generate_weekly_report.py --mode parse
    python3 generate_weekly_report.py --mode parse -n 3

    # 生成模式（收集数据供 AI 整合）
    python3 generate_weekly_report.py --mode generate --week "01.26~02.01"
    python3 generate_weekly_report.py --mode generate --start 2026-01-19 --end 2026-01-25
"""

import argparse
import subprocess
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
import re


SCRIPT_DIR = Path(__file__).parent
DEFAULT_OUTPUT_DIR = Path("/Users/cookie/Documents/个人周报")
DEFAULT_JSON_PATH = DEFAULT_OUTPUT_DIR / "周报原始内容.json"


def get_week_range(ref_date: date = None) -> tuple[date, date]:
    """获取指定日期所在周的周一到周日"""
    if ref_date is None:
        ref_date = date.today()
    monday = ref_date - timedelta(days=ref_date.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def parse_week_string(week_str: str) -> tuple[date, date]:
    """
    解析周报日期字符串，如 "01.26~02.01"

    Returns:
        (start_date, end_date)
    """
    # 匹配 MM.DD~MM.DD 格式
    match = re.match(r"(\d{2})\.(\d{2})~(\d{2})\.(\d{2})", week_str)
    if not match:
        raise ValueError(f"无法解析日期格式: {week_str}，期望格式: MM.DD~MM.DD")

    start_month, start_day, end_month, end_day = map(int, match.groups())

    # 推断年份（假设是当前年份或下一年）
    today = date.today()
    year = today.year

    # 如果开始月份大于结束月份，说明跨年
    if start_month > end_month:
        start_date = date(year, start_month, start_day)
        end_date = date(year + 1, end_month, end_day)
    else:
        start_date = date(year, start_month, start_day)
        end_date = date(year, end_month, end_day)

        # 如果日期在今天之前很久，可能是去年的
        if end_date < today - timedelta(days=180):
            start_date = date(year - 1, start_month, start_day)
            end_date = date(year - 1, end_month, end_day)

    return start_date, end_date


def run_parse_mode(args):
    """运行解析模式"""
    print("=" * 60)
    print("【解析模式】解析周报原始 JSON")
    print("=" * 60)

    parse_script = SCRIPT_DIR / "parse_json_report.py"
    if not parse_script.exists():
        print(f"错误: 找不到解析脚本 {parse_script}", file=sys.stderr)
        return 1

    cmd = [sys.executable, str(parse_script)]
    if args.all:
        cmd.append("--all")
    else:
        cmd.extend(["-n", str(args.n)])

    if args.json:
        cmd.extend(["--json", args.json])
    if args.output:
        cmd.extend(["--output", args.output])

    print(f"执行: {' '.join(cmd)}")
    return subprocess.call(cmd)


def find_latest_report(output_dir: Path) -> Path | None:
    """查找最新的周报文件"""
    reports = list(output_dir.glob("沈淇杰 * 的工作周报.md"))
    if not reports:
        return None

    # 按文件修改时间排序
    reports.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return reports[0]


def extract_next_week_plan(report_path: Path) -> str:
    """从周报中提取下周计划部分"""
    if not report_path.exists():
        return ""

    content = report_path.read_text(encoding="utf-8")

    # 查找 "下周计划" 部分
    lines = content.split("\n")
    result_lines = []
    in_plan_section = False

    for line in lines:
        if "下周计划" in line:
            in_plan_section = True
            result_lines.append(line)
        elif in_plan_section:
            # 遇到下一个主要章节标题时停止
            if line.startswith("## ") or line.startswith("---"):
                break
            # 遇到下一个工作项时停止
            if line.startswith("### ") and "下周计划" not in line:
                in_plan_section = False
                result_lines.append("")  # 添加分隔
                # 检查这行是否也有下周计划
                continue
            result_lines.append(line)

    return "\n".join(result_lines)


def run_generate_mode(args, start_date: date, end_date: date):
    """运行生成模式 - 收集数据供 AI 整合"""
    print("=" * 60)
    print(f"【生成模式】收集周报数据: {start_date} ~ {end_date}")
    print("=" * 60)

    output_dir = Path(args.output) if args.output else DEFAULT_OUTPUT_DIR

    # 第一步：获取上期周报的下周计划
    print("\n\n")
    print("=" * 60)
    print("【第一步】上期周报 - 下周计划")
    print("=" * 60)

    latest_report = find_latest_report(output_dir)
    if latest_report:
        print(f"\n最新周报: {latest_report.name}")
        next_week_plan = extract_next_week_plan(latest_report)
        if next_week_plan:
            print("\n--- 上期下周计划 ---")
            print(next_week_plan)
        else:
            print("未找到下周计划部分")
    else:
        print("未找到已有周报")

    # 第二步：获取 Notion 会议记录
    print("\n\n")
    print("=" * 60)
    print("【第二步】Notion 会议记录")
    print("=" * 60)

    notion_script = SCRIPT_DIR / "fetch_notion_meetings.py"
    if notion_script.exists():
        import os
        if os.environ.get("NOTION_TOKEN"):
            cmd = [
                sys.executable, str(notion_script),
                "--start", start_date.isoformat(),
                "--end", end_date.isoformat()
            ]
            print(f"\n执行: {' '.join(cmd)}")
            subprocess.call(cmd)
        else:
            print("\n提示: 未设置 NOTION_TOKEN 环境变量，跳过 Notion 数据获取")
            print("如需获取 Notion 会议记录，请设置 NOTION_TOKEN 环境变量后重试")
    else:
        print(f"脚本不存在: {notion_script}")

    # 第三步：查询微信工作消息
    print("\n\n")
    print("=" * 60)
    print("【第三步】微信工作消息")
    print("=" * 60)

    wechat_script = SCRIPT_DIR / "query_wechat_messages.py"
    if wechat_script.exists():
        cmd = [
            sys.executable, str(wechat_script),
            "--start", start_date.isoformat(),
            "--end", end_date.isoformat()
        ]
        print(f"\n执行: {' '.join(cmd)}")
        subprocess.call(cmd)
    else:
        print(f"脚本不存在: {wechat_script}")

    # 输出后续步骤提示
    print("\n\n")
    print("=" * 60)
    print("【后续步骤】")
    print("=" * 60)
    print("""
以上是收集到的原始数据，请 AI 根据这些信息：

1. 对照上期"下周计划"，总结本周实际完成情况
2. 从 Notion 会议记录提炼重要进展
3. 从微信消息中补充细节和问题跟进情况
4. 按照周报模板生成本周周报草稿

周报应包含：
- 岗位职责（保持不变）
- 年工作计划下各项目的周进展
- 下周计划
""")

    return 0


def main():
    parser = argparse.ArgumentParser(description="周报生成主程序")
    parser.add_argument("--mode", choices=["parse", "generate"], required=True,
                        help="运行模式: parse（解析JSON）或 generate（生成新周报）")

    # parse 模式参数
    parser.add_argument("--json", "-j", type=str,
                        help="周报 JSON 文件路径")
    parser.add_argument("--all", action="store_true",
                        help="解析所有周报（parse 模式）")
    parser.add_argument("-n", type=int, default=1,
                        help="解析最新 N 期周报（parse 模式，默认 1）")

    # generate 模式参数
    parser.add_argument("--week", type=str,
                        help="周报日期范围，格式: MM.DD~MM.DD（如 01.26~02.01）")
    parser.add_argument("--start", type=str,
                        help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end", type=str,
                        help="结束日期 (YYYY-MM-DD)")

    # 通用参数
    parser.add_argument("--output", "-o", type=str,
                        help="输出目录")

    args = parser.parse_args()

    if args.mode == "parse":
        return run_parse_mode(args)

    elif args.mode == "generate":
        # 确定日期范围
        if args.week:
            try:
                start_date, end_date = parse_week_string(args.week)
            except ValueError as e:
                print(f"错误: {e}", file=sys.stderr)
                return 1
        elif args.start and args.end:
            try:
                start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
                end_date = datetime.strptime(args.end, "%Y-%m-%d").date()
            except ValueError as e:
                print(f"日期格式错误: {e}", file=sys.stderr)
                return 1
        else:
            # 默认使用本周
            start_date, end_date = get_week_range()
            print(f"未指定日期范围，使用本周: {start_date} ~ {end_date}")

        return run_generate_mode(args, start_date, end_date)


if __name__ == "__main__":
    raise SystemExit(main())
