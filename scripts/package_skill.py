#!/usr/bin/env python3
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

from validate_skill import validate_skill


def _iter_files(skill_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in skill_dir.rglob("*"):
        if path.is_file():
            files.append(path)
    return sorted(files, key=lambda p: str(p.relative_to(skill_dir)))


def package_skill(skill_dir: Path, output_dir: Path) -> Path:
    validate_skill(skill_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{skill_dir.name}.skill"

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in _iter_files(skill_dir):
            arcname = str(Path(skill_dir.name) / path.relative_to(skill_dir))
            zf.write(path, arcname=arcname)

    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Package a skill folder into a .skill zip.")
    parser.add_argument("skill_path", help="Path to a skill folder (contains SKILL.md).")
    parser.add_argument("output_dir", nargs="?", default="dist", help="Output directory (default: dist).")
    args = parser.parse_args()

    out_path = package_skill(Path(args.skill_path), Path(args.output_dir))
    print(f"Created: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

