#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_NAME_LENGTH = 64


DISALLOWED_TOP_LEVEL = {
    "README.md",
    "INSTALLATION_GUIDE.md",
    "QUICK_REFERENCE.md",
    "CHANGELOG.md",
}


@dataclass(frozen=True)
class Frontmatter:
    name: str
    description: str


class ValidationError(Exception):
    pass


def _read_frontmatter(skill_md: Path) -> tuple[Frontmatter, list[str]]:
    lines = skill_md.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValidationError("SKILL.md must start with YAML frontmatter '---'")

    try:
        end_index = next(i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration as exc:
        raise ValidationError("YAML frontmatter must be terminated by '---'") from exc

    fm_lines = lines[1:end_index]
    body_lines = lines[end_index + 1 :]

    kv: dict[str, str] = {}
    for raw in fm_lines:
        if not raw.strip():
            continue
        if raw.lstrip().startswith("#"):
            continue
        if ":" not in raw:
            raise ValidationError(f"Invalid frontmatter line (expected key: value): {raw!r}")
        key, value = raw.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            raise ValidationError(f"Invalid frontmatter line (empty key/value): {raw!r}")
        if value.startswith(("|", ">")):
            raise ValidationError("Frontmatter values must be single-line scalars")
        kv[key] = value

    allowed = {"name", "description"}
    extra = sorted(set(kv) - allowed)
    missing = sorted(allowed - set(kv))
    if extra:
        raise ValidationError(f"Frontmatter must contain only name/description; extra keys: {', '.join(extra)}")
    if missing:
        raise ValidationError(f"Frontmatter missing keys: {', '.join(missing)}")

    return Frontmatter(name=kv["name"], description=kv["description"]), body_lines


def _iter_markdown_links(markdown_lines: list[str]) -> list[str]:
    content = "\n".join(markdown_lines)
    links = []
    for match in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", content):
        target = match.group(1).strip()
        if not target:
            continue
        if target.startswith("#"):
            continue
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
            continue
        links.append(target)
    return links


def validate_skill(skill_dir: Path) -> None:
    if not skill_dir.exists() or not skill_dir.is_dir():
        raise ValidationError(f"Not a directory: {skill_dir}")

    skill_name = skill_dir.name
    if len(skill_name) > MAX_NAME_LENGTH or not NAME_RE.match(skill_name):
        raise ValidationError(
            f"Invalid skill folder name: {skill_name!r} (must match {NAME_RE.pattern}, <= {MAX_NAME_LENGTH})"
        )

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        raise ValidationError("Missing required file: SKILL.md")

    for disallowed in sorted(DISALLOWED_TOP_LEVEL):
        if (skill_dir / disallowed).exists():
            raise ValidationError(f"Disallowed file in skill root: {disallowed}")

    frontmatter, body_lines = _read_frontmatter(skill_md)
    if frontmatter.name != skill_name:
        raise ValidationError(f"Frontmatter name must match folder name: {frontmatter.name!r} != {skill_name!r}")
    if not frontmatter.description.strip():
        raise ValidationError("Frontmatter description must be non-empty")

    for link in _iter_markdown_links(body_lines):
        if link.startswith("/"):
            raise ValidationError(f"Absolute path link not allowed: {link}")
        if ".." in Path(link).parts:
            raise ValidationError(f"Link must not escape skill directory: {link}")
        target = (skill_dir / link).resolve()
        if not str(target).startswith(str(skill_dir.resolve())):
            raise ValidationError(f"Link must stay within skill directory: {link}")
        if not target.exists():
            raise ValidationError(f"Linked file does not exist: {link}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a skill folder.")
    parser.add_argument("skill_path", help="Path to a skill folder (contains SKILL.md).")
    args = parser.parse_args()

    try:
        validate_skill(Path(args.skill_path))
    except ValidationError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

