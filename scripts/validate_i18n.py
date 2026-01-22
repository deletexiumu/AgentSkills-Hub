#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skill i18n 校验脚本

校验 SKILL.md 是否符合多语言规范：
1. frontmatter description 包含 [ZH]、[EN]、[JA] 标记
2. SKILL.md 前 60 行存在"调用/Invoke/呼び出し"区块
3. 中/英/日示例各 >= 3 条

用法:
    python scripts/validate_i18n.py skills/public/ai-news-digest
    python scripts/validate_i18n.py skills/public/smart-data-query
    python scripts/validate_i18n.py skills/public/x-ai-digest
"""

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple


class I18nValidator:
    """i18n 校验器"""

    def __init__(self, skill_path: Path):
        self.skill_path = skill_path
        self.skill_md_path = skill_path / "SKILL.md"
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate(self) -> bool:
        """运行所有校验，返回是否通过"""
        if not self.skill_md_path.exists():
            self.errors.append(f"SKILL.md 不存在: {self.skill_md_path}")
            return False

        content = self.skill_md_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        self._validate_frontmatter(lines)
        self._validate_examples_block(lines)
        self._validate_example_counts(lines)

        return len(self.errors) == 0

    def _validate_frontmatter(self, lines: List[str]) -> None:
        """校验 frontmatter description 包含三语标记"""
        in_frontmatter = False
        description = ""

        for line in lines[:20]:  # 只检查前 20 行
            if line.strip() == "---":
                if in_frontmatter:
                    break
                in_frontmatter = True
                continue

            if in_frontmatter and line.startswith("description:"):
                description = line[12:].strip()
                break

        if not description:
            self.errors.append("frontmatter 缺少 description 字段")
            return

        missing_tags = []
        for tag in ["[ZH]", "[EN]", "[JA]"]:
            if tag not in description:
                missing_tags.append(tag)

        if missing_tags:
            self.errors.append(f"description 缺少语言标记: {', '.join(missing_tags)}")

    def _validate_examples_block(self, lines: List[str]) -> None:
        """校验存在调用示例区块"""
        # 检查前 60 行
        header_60 = "\n".join(lines[:60])

        # 检查区块标记
        has_start = "<!-- i18n-examples:start -->" in header_60
        has_end = "<!-- i18n-examples:end -->" in header_60

        if not has_start:
            self.warnings.append("缺少 <!-- i18n-examples:start --> 标记")

        if not has_end:
            self.warnings.append("缺少 <!-- i18n-examples:end --> 标记")

        # 检查标题
        has_invoke_header = any([
            "调用" in header_60 and "Invoke" in header_60,
            "呼び出し" in header_60
        ])

        if not has_invoke_header:
            self.errors.append("前 60 行缺少 '调用 / Invoke / 呼び出し' 区块")

    def _validate_example_counts(self, lines: List[str]) -> None:
        """校验各语言示例数量"""
        content = "\n".join(lines[:80])  # 检查前 80 行

        # 提取示例区块
        start_match = re.search(r"<!-- i18n-examples:start -->", content)
        end_match = re.search(r"<!-- i18n-examples:end -->", content)

        if not start_match or not end_match:
            return  # 没有示例区块，跳过计数校验

        examples_block = content[start_match.end():end_match.start()]

        # 按语言统计示例数量
        counts = {
            "中文": self._count_examples(examples_block, "### 中文", ["### English", "### 日本語", "<!--"]),
            "English": self._count_examples(examples_block, "### English", ["### 中文", "### 日本語", "<!--"]),
            "日本語": self._count_examples(examples_block, "### 日本語", ["### 中文", "### English", "<!--"]),
        }

        for lang, count in counts.items():
            if count < 3:
                self.errors.append(f"{lang} 示例不足 3 条（当前 {count} 条）")

    def _count_examples(self, block: str, start_header: str, end_markers: List[str]) -> int:
        """统计某语言的示例数量"""
        start_idx = block.find(start_header)
        if start_idx == -1:
            return 0

        # 找到该语言段落的结束位置
        end_idx = len(block)
        for marker in end_markers:
            marker_idx = block.find(marker, start_idx + len(start_header))
            if marker_idx != -1 and marker_idx < end_idx:
                end_idx = marker_idx

        section = block[start_idx:end_idx]

        # 统计以 - " 开头的行（示例格式）
        example_pattern = re.compile(r'^\s*-\s*"', re.MULTILINE)
        matches = example_pattern.findall(section)
        return len(matches)

    def print_report(self) -> None:
        """打印校验报告"""
        print(f"\n=== i18n validation: {self.skill_path.name} ===\n")

        if self.errors:
            print("ERRORS:")
            for err in self.errors:
                print(f"  [X] {err}")
            print()

        if self.warnings:
            print("WARNINGS:")
            for warn in self.warnings:
                print(f"  [!] {warn}")
            print()

        if not self.errors and not self.warnings:
            print("[OK] All checks passed")
        elif not self.errors:
            print("[OK] Passed with warnings")
        else:
            print("[FAIL] Validation failed")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="校验 skill 的 i18n 规范",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s skills/public/ai-news-digest
  %(prog)s skills/public/smart-data-query
  %(prog)s skills/public/x-ai-digest
        """
    )
    parser.add_argument(
        "skill_path",
        help="Skill 目录路径",
        type=Path
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="严格模式（警告也视为失败）"
    )

    args = parser.parse_args()

    skill_path = args.skill_path.resolve()
    if not skill_path.exists():
        print(f"错误: 路径不存在: {skill_path}")
        return 1

    if not skill_path.is_dir():
        print(f"错误: 不是目录: {skill_path}")
        return 1

    validator = I18nValidator(skill_path)
    passed = validator.validate()
    validator.print_report()

    if args.strict and validator.warnings:
        return 1

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
