#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


LAYER_NAMES = {"ADS", "DWS", "DWT"}
DEFAULT_TEXT_SUFFIXES = {".sql", ".md", ".markdown", ".txt"}


CREATE_TABLE_RE = re.compile(
    r"\bcreate\s+table\b\s+(?:if\s+not\s+exists\s+)?(?P<name>[`\"\\[]?[a-zA-Z0-9_.]+[`\"\\]]?)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Column:
    name: str
    type: str


def _detect_layer(path: Path) -> str:
    for part in path.parts:
        upper = part.upper()
        if upper in LAYER_NAMES:
            return upper
    return "UNKNOWN"


def _read_text_limited(path: Path, max_bytes: int) -> str:
    with path.open("rb") as f:
        data = f.read(max_bytes)
    return data.decode("utf-8", errors="ignore")


def _find_create_table_names(sql: str) -> list[str]:
    names: list[str] = []
    for match in CREATE_TABLE_RE.finditer(sql):
        raw = match.group("name").strip()
        raw = raw.strip("`").strip('"').strip("[").strip("]")
        names.append(raw)
    return names


def _extract_balanced_parentheses(text: str, start_index: int) -> str | None:
    if start_index < 0 or start_index >= len(text) or text[start_index] != "(":
        return None
    depth = 0
    for i in range(start_index, len(text)):
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[start_index + 1 : i]
    return None


def _split_top_level_comma(text: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    in_single = False
    in_double = False

    for ch in text:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth = max(0, depth - 1)
            elif ch == "," and depth == 0:
                item = "".join(buf).strip()
                if item:
                    parts.append(item)
                buf = []
                continue
        buf.append(ch)

    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def _parse_columns_from_create_table(sql: str) -> list[Column]:
    match = CREATE_TABLE_RE.search(sql)
    if not match:
        return []

    after_name = sql[match.end() :]
    paren_index = after_name.find("(")
    if paren_index == -1:
        return []

    column_block = _extract_balanced_parentheses(after_name, paren_index)
    if column_block is None:
        return []

    columns: list[Column] = []
    for raw in _split_top_level_comma(column_block):
        line = raw.strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith(("primary key", "unique", "key ", "constraint ", "index ")):
            continue

        tokens = line.replace("\n", " ").split()
        if len(tokens) < 2:
            continue
        col_name = tokens[0].strip("`").strip('"')
        col_type = tokens[1].strip().rstrip(",")
        if col_name.lower() in {"partitioned", "clustered", "stored", "tblproperties"}:
            continue
        columns.append(Column(name=col_name, type=col_type))
    return columns


def build_catalog(root: Path, out_path: Path, max_bytes: int, suffixes: set[str]) -> None:
    tables: dict[tuple[str, str], dict] = {}

    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in suffixes:
            continue

        layer = _detect_layer(file_path)
        is_sql = file_path.suffix.lower() == ".sql"

        text = ""
        if is_sql:
            text = _read_text_limited(file_path, max_bytes=max_bytes)

        table_names: list[str] = []
        columns: list[Column] = []
        if is_sql:
            table_names = _find_create_table_names(text)
            columns = _parse_columns_from_create_table(text)

        if not table_names:
            table_names = [file_path.stem]

        for table_name in table_names:
            key = (layer, table_name)
            entry = tables.get(key)
            if entry is None:
                entry = {
                    "layer": layer,
                    "name": table_name,
                    "sql_files": [],
                    "doc_files": [],
                    "columns": [],
                }
                tables[key] = entry

            if is_sql:
                entry["sql_files"].append(str(file_path))
                if columns and not entry["columns"]:
                    entry["columns"] = [{"name": c.name, "type": c.type} for c in columns]
            else:
                entry["doc_files"].append(str(file_path))

    payload = {
        "root": str(root),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tables": sorted(
            tables.values(),
            key=lambda e: (e["layer"], e["name"]),
        ),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="为数仓目录生成轻量 catalog（表/层级/文件路径/DDL 字段）。")
    parser.add_argument("--root", required=True, help="数仓目录根路径（包含 ADS/DWS/DWT）。")
    parser.add_argument("--out", default="catalog.json", help="输出 catalog 路径（默认：catalog.json）。")
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=2_000_000,
        help="读取单个 SQL 文件的最大字节数（默认：2000000）。",
    )
    parser.add_argument(
        "--suffixes",
        default=",".join(sorted(DEFAULT_TEXT_SUFFIXES)),
        help="要纳入索引的文件后缀（逗号分隔）。",
    )
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    out_path = Path(args.out).expanduser().resolve()
    suffixes = {s.strip().lower() for s in args.suffixes.split(",") if s.strip()}
    if not suffixes:
        suffixes = set(DEFAULT_TEXT_SUFFIXES)

    if not root.exists() or not root.is_dir():
        print(f"ERROR: 目录不存在：{root}")
        return 1

    build_catalog(root=root, out_path=out_path, max_bytes=args.max_bytes, suffixes=suffixes)
    print(f"OK: 已生成 {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

