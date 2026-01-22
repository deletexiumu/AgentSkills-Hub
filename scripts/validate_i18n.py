#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skill i18n validation script

Validates SKILL.md conforms to i18n specification:
1. frontmatter description exists and is in English
2. SKILL.md first 60 lines contain invoke examples block
3. At least 3 examples per language (ZH/EN/JA)

Usage:
    python scripts/validate_i18n.py skills/public/ai-news-digest
    python scripts/validate_i18n.py skills/public/smart-data-query
    python scripts/validate_i18n.py skills/public/x-ai-digest
"""

import argparse
import re
import sys
from pathlib import Path
from typing import List


class I18nValidator:
    """i18n validator"""

    def __init__(self, skill_path: Path):
        self.skill_path = skill_path
        self.skill_md_path = skill_path / "SKILL.md"
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate(self) -> bool:
        """Run all validations, return whether passed"""
        if not self.skill_md_path.exists():
            self.errors.append(f"SKILL.md not found: {self.skill_md_path}")
            return False

        content = self.skill_md_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        self._validate_frontmatter(lines)
        self._validate_examples_block(lines)
        self._validate_example_counts(lines)

        return len(self.errors) == 0

    def _validate_frontmatter(self, lines: List[str]) -> None:
        """Validate frontmatter has description in English"""
        in_frontmatter = False
        description = ""
        name = ""

        for line in lines[:20]:  # Only check first 20 lines
            if line.strip() == "---":
                if in_frontmatter:
                    break
                in_frontmatter = True
                continue

            if in_frontmatter:
                if line.startswith("description:"):
                    description = line[12:].strip()
                elif line.startswith("name:"):
                    name = line[5:].strip()

        if not name:
            self.errors.append("frontmatter missing 'name' field")

        if not description:
            self.errors.append("frontmatter missing 'description' field")
            return

        # Check if description looks like English (no language tags)
        if "[ZH]" in description or "[EN]" in description or "[JA]" in description:
            self.errors.append("description should be plain English, not use [ZH]/[EN]/[JA] tags")

    def _validate_examples_block(self, lines: List[str]) -> None:
        """Validate invoke examples block exists"""
        # Check first 60 lines
        header_60 = "\n".join(lines[:60])

        # Check block markers
        has_start = "<!-- i18n-examples:start -->" in header_60
        has_end = "<!-- i18n-examples:end -->" in header_60

        if not has_start:
            self.warnings.append("Missing <!-- i18n-examples:start --> marker")

        if not has_end:
            self.warnings.append("Missing <!-- i18n-examples:end --> marker")

        # Check for invoke header (any language)
        has_invoke_header = any([
            "Invoke" in header_60,
            "invoke" in header_60.lower(),
        ])

        if not has_invoke_header:
            self.errors.append("First 60 lines missing invoke examples section")

    def _validate_example_counts(self, lines: List[str]) -> None:
        """Validate example counts per language"""
        content = "\n".join(lines[:80])  # Check first 80 lines

        # Extract examples block
        start_match = re.search(r"<!-- i18n-examples:start -->", content)
        end_match = re.search(r"<!-- i18n-examples:end -->", content)

        if not start_match or not end_match:
            return  # No examples block, skip count validation

        examples_block = content[start_match.end():end_match.start()]

        # Count total examples (lines starting with - ")
        example_pattern = re.compile(r'^\s*-\s*"', re.MULTILINE)
        total_examples = len(example_pattern.findall(examples_block))

        # Check for language section headers (any format)
        has_chinese = any(h in examples_block for h in ["###", "Chinese"])
        has_english = "English" in examples_block
        has_japanese = any(h in examples_block for h in ["###", "Japanese"])

        # We expect at least 9 examples total (3 per language)
        if total_examples < 9:
            self.warnings.append(f"Total examples: {total_examples} (recommend >= 9 for 3 languages x 3 each)")

        # Check language sections exist
        if not has_chinese and not has_english and not has_japanese:
            self.errors.append("No language sections found in examples block")

    def print_report(self) -> None:
        """Print validation report"""
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
        description="Validate skill i18n specification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s skills/public/ai-news-digest
  %(prog)s skills/public/smart-data-query
  %(prog)s skills/public/x-ai-digest
        """
    )
    parser.add_argument(
        "skill_path",
        help="Skill directory path",
        type=Path
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Strict mode (warnings also count as failure)"
    )

    args = parser.parse_args()

    skill_path = args.skill_path.resolve()
    if not skill_path.exists():
        print(f"Error: path not found: {skill_path}")
        return 1

    if not skill_path.is_dir():
        print(f"Error: not a directory: {skill_path}")
        return 1

    validator = I18nValidator(skill_path)
    passed = validator.validate()
    validator.print_report()

    if args.strict and validator.warnings:
        return 1

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
