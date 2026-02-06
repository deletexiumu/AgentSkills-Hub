#!/usr/bin/env python3
"""为数仓目录生成两层 catalog：

- catalog.search.json  轻量检索索引（供 search_catalog.py 使用）
- catalog/full/<LAYER>/<table_id>.json  每表详情（按需加载）

v2: 修复层级检测、提取 COMMENT、两层输出。
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# 常量 & 正则
# ---------------------------------------------------------------------------

LAYER_NAMES = {"ADS", "DWS", "DWT", "DWD", "ODS"}
DEFAULT_TEXT_SUFFIXES = {".sql", ".md", ".markdown", ".txt"}

IDENT_RE = r"(?:`[^`]+`|\"[^\"]+\"|\[[^\]]+\]|[a-zA-Z0-9_.]+)"

# 匹配目录名中包含的层级，如 "05-应用专题库-ADS"
LAYER_PATTERN = re.compile(
    r"(?:^|[^a-zA-Z])(ADS|DWS|DWT|DWD|ODS)(?:$|[^a-zA-Z])",
    re.IGNORECASE,
)

CREATE_TABLE_RE = re.compile(
    rf"\bcreate\s+(?:external\s+)?table\b\s+(?:if\s+not\s+exists\s+)?(?P<name>{IDENT_RE})",
    re.IGNORECASE,
)

INSERT_TABLE_RE = re.compile(
    rf"\binsert\s+(?:overwrite|into)\s+table\s+(?P<name>{IDENT_RE})",
    re.IGNORECASE,
)

PARTITIONED_BY_RE = re.compile(
    r"\bpartitioned\s+by\s*\(",
    re.IGNORECASE,
)

FROM_JOIN_RE = re.compile(
    rf"\b(from|join)\s+(?P<name>{IDENT_RE})",
    re.IGNORECASE,
)

GROUP_BY_RE = re.compile(r"\bgroup\s+by\b", re.IGNORECASE)

ROW_NUMBER_OVER_RE = re.compile(
    r"\brow_number\s*\(\s*\)\s*over\s*\(",
    re.IGNORECASE,
)

SELECT_DISTINCT_RE = re.compile(r"\bselect\s+distinct\b", re.IGNORECASE)

# 字段级 COMMENT: STRING COMMENT '高校名称'
COLUMN_COMMENT_RE = re.compile(r"\bcomment\s+['\"]([^'\"]*)['\"]", re.IGNORECASE)

# TBLPROPERTIES 中的 comment
TBLPROPERTIES_COMMENT_RE = re.compile(
    r"['\"]comment['\"]\s*=\s*['\"]([^'\"]*)['\"]",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Column:
    name: str
    type: str
    comment: str = ""


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _detect_layer(path: Path) -> str:
    """从文件路径中检测数仓层级。支持 '05-应用专题库-ADS' 格式。"""
    for part in path.parts:
        m = LAYER_PATTERN.search(part)
        if m:
            return m.group(1).upper()
    return "UNKNOWN"


def _read_text_limited(path: Path, max_bytes: int) -> str:
    with path.open("rb") as f:
        data = f.read(max_bytes)
    return data.decode("utf-8", errors="ignore")


def _strip_identifier_quotes(raw: str) -> str:
    s = raw.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in {"`", '"'}:
        return s[1:-1]
    if len(s) >= 2 and s[0] == "[" and s[-1] == "]":
        return s[1:-1]
    return s


def _find_create_table_names(sql: str) -> list[str]:
    return [_strip_identifier_quotes(m.group("name")) for m in CREATE_TABLE_RE.finditer(sql)]


def _find_insert_table_names(sql: str) -> list[str]:
    return [_strip_identifier_quotes(m.group("name")) for m in INSERT_TABLE_RE.finditer(sql)]


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


# ---------------------------------------------------------------------------
# Column / Partition 解析（含 COMMENT 提取）
# ---------------------------------------------------------------------------

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
        # 跳过 SQL 注释行（如 -- 高校信息）
        stripped = re.sub(r"--[^\n]*", "", line).strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if lower.startswith(("primary key", "unique", "key ", "constraint ", "index ")):
            continue

        tokens = stripped.replace("\n", " ").split()
        if len(tokens) < 2:
            continue
        col_name = tokens[0].strip("`").strip('"')
        if col_name.startswith("--"):
            continue
        col_type = tokens[1].strip().rstrip(",")
        if col_name.lower() in {"partitioned", "clustered", "stored", "tblproperties"}:
            continue

        # 提取 COMMENT
        comment = ""
        cm = COLUMN_COMMENT_RE.search(stripped)
        if cm:
            comment = cm.group(1).strip()

        columns.append(Column(name=col_name, type=col_type, comment=comment))
    return columns


def _parse_columns_block(text: str) -> list[Column]:
    columns: list[Column] = []
    for raw in _split_top_level_comma(text):
        line = raw.strip()
        if not line:
            continue
        tokens = line.replace("\n", " ").split()
        if len(tokens) < 2:
            continue
        col_name = tokens[0].strip("`").strip('"')
        col_type = tokens[1].strip().rstrip(",")
        comment = ""
        cm = COLUMN_COMMENT_RE.search(line)
        if cm:
            comment = cm.group(1).strip()
        columns.append(Column(name=col_name, type=col_type, comment=comment))
    return columns


def _parse_partition_columns_from_create_table(sql: str) -> list[Column]:
    match = PARTITIONED_BY_RE.search(sql)
    if not match:
        return []
    after = sql[match.end() - 1 :]
    column_block = _extract_balanced_parentheses(after, 0)
    if column_block is None:
        return []
    return _parse_columns_block(column_block)


# ---------------------------------------------------------------------------
# 表级 COMMENT / 描述提取
# ---------------------------------------------------------------------------

def _extract_table_comment(sql: str) -> str:
    """从 DDL 中提取表级 COMMENT。

    策略：先找到 CREATE TABLE 的主括号结束位置，再在其后查找 COMMENT。
    这样可以避免误匹配 DECIMAL(10,6) COMMENT '...' 等字段级注释。
    """
    match = CREATE_TABLE_RE.search(sql)
    if not match:
        return ""

    after_name = sql[match.end():]
    paren_index = after_name.find("(")
    if paren_index == -1:
        return ""

    # 找到主括号块的结束位置
    block = _extract_balanced_parentheses(after_name, paren_index)
    if block is None:
        return ""

    # 主括号结束后的文本
    close_pos = match.end() + paren_index + len(block) + 2  # +2 for ( and )
    after_block = sql[close_pos:]

    # 在主括号之后查找 COMMENT（距离不应太远，限制在 500 字符内）
    snippet = after_block[:500]
    cm = re.search(r"\bcomment\s*=?\s*['\"]([^'\"]*)['\"]", snippet, re.IGNORECASE)
    if cm:
        return cm.group(1).strip()

    # 也检查 TBLPROPERTIES 中的 comment
    m = TBLPROPERTIES_COMMENT_RE.search(snippet)
    if m:
        return m.group(1).strip()
    return ""


def _extract_description_from_filename(file_path: Path) -> str:
    """从文件名中文部分提取描述。

    如 '产业地图-国内高校信息-ads_xxx.sql' → '产业地图-国内高校信息'
    """
    stem = file_path.stem
    # 在最后一个 '-英文开头' 处切分
    parts = re.split(r"-(?=[a-z_])", stem, maxsplit=1)
    if len(parts) > 1 and any("\u4e00" <= c <= "\u9fff" for c in parts[0]):
        return parts[0]
    return ""


# ---------------------------------------------------------------------------
# Signal 提取
# ---------------------------------------------------------------------------

def _extract_group_by_columns(sql: str, max_items: int = 12) -> list[str]:
    match = GROUP_BY_RE.search(sql)
    if not match:
        return []
    rest = sql[match.end() :]
    end_candidates = []
    for pat in (r"\bhaving\b", r"\border\s+by\b", r"\blimit\b", r"\bunion\b", r";"):
        m = re.search(pat, rest, flags=re.IGNORECASE)
        if m:
            end_candidates.append(m.start())
    end = min(end_candidates) if end_candidates else len(rest)
    block = rest[:end].strip()
    if not block:
        return []
    cols = []
    for item in _split_top_level_comma(block):
        cleaned = item.strip()
        if not cleaned:
            continue
        cols.append(cleaned)
        if len(cols) >= max_items:
            break
    return cols


def _extract_row_number_partition_by(sql: str, max_items: int = 12) -> list[str]:
    m = ROW_NUMBER_OVER_RE.search(sql)
    if not m:
        return []
    after = sql[m.end() - 1 :]
    over_block = _extract_balanced_parentheses(after, 0)
    if not over_block:
        return []
    pm = re.search(r"\bpartition\s+by\b", over_block, flags=re.IGNORECASE)
    if not pm:
        return []
    rest = over_block[pm.end() :]
    om = re.search(r"\border\s+by\b", rest, flags=re.IGNORECASE)
    part_block = rest[: om.start()] if om else rest
    cols = []
    for item in _split_top_level_comma(part_block.strip()):
        cleaned = item.strip()
        if not cleaned:
            continue
        cols.append(cleaned)
        if len(cols) >= max_items:
            break
    return cols


def _extract_source_tables(sql: str, max_items: int = 30) -> list[str]:
    names: list[str] = []
    for m in FROM_JOIN_RE.finditer(sql):
        raw = m.group("name").strip()
        if raw.startswith("("):
            continue
        raw = _strip_identifier_quotes(raw)
        lower = raw.lower()
        if lower in {"select", "values"}:
            continue
        names.append(raw)
        if len(names) >= max_items:
            break
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out


def _merge_signals(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for k, v in incoming.items():
        if isinstance(v, list):
            base = list(merged.get(k, [])) if isinstance(merged.get(k), list) else []
            seen = set(base)
            for item in v:
                if item in seen:
                    continue
                seen.add(item)
                base.append(item)
            merged[k] = base
        elif isinstance(v, bool):
            merged[k] = bool(merged.get(k)) or v
        else:
            if k not in merged:
                merged[k] = v
    return merged


def _compact_signals(signals: dict[str, Any]) -> dict[str, Any]:
    """去掉空列表和 False 值，减少输出体积。"""
    return {k: v for k, v in signals.items() if v}


# ---------------------------------------------------------------------------
# 核心构建逻辑
# ---------------------------------------------------------------------------

def build_catalog(
    root: Path,
    out_dir: Path,
    max_bytes: int,
    suffixes: set[str],
    include_unknown: bool,
    pretty: bool,
) -> None:
    tables: dict[tuple[str, str], dict] = {}
    known_full_by_layer_short: dict[tuple[str, str], str] = {}

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
        partition_columns: list[Column] = []
        signals: dict[str, Any] = {}
        table_comment = ""
        description = _extract_description_from_filename(file_path)

        if is_sql:
            table_names = _find_create_table_names(text)
            columns = _parse_columns_from_create_table(text)
            partition_columns = _parse_partition_columns_from_create_table(text)
            table_comment = _extract_table_comment(text)

            for name in table_names:
                short = name.split(".")[-1]
                known_full_by_layer_short[(layer, short)] = name

            insert_targets = _find_insert_table_names(text)
            normalized_targets: list[str] = []
            for name in insert_targets:
                if "." in name:
                    normalized_targets.append(name)
                    continue
                full = known_full_by_layer_short.get((layer, name))
                normalized_targets.append(full or name)

            signals = {
                "insert_targets": normalized_targets,
                "source_tables": _extract_source_tables(text),
                "group_by": _extract_group_by_columns(text),
                "row_number_partition_by": _extract_row_number_partition_by(text),
                "has_select_distinct": bool(SELECT_DISTINCT_RE.search(text)),
                "has_row_number": bool(ROW_NUMBER_OVER_RE.search(text)),
            }

        if not table_names and is_sql:
            table_names = signals.get("insert_targets", []) or []

        if not table_names:
            table_names = [file_path.stem]

        rel_path = str(file_path.relative_to(root))

        for table_name in table_names:
            key = (layer, table_name)
            entry = tables.get(key)
            if entry is None:
                entry = {
                    "layer": layer,
                    "name": table_name,
                    "description": "",
                    "table_comment": "",
                    "sql_files": [],
                    "doc_files": [],
                    "columns": [],
                    "partition_columns": [],
                    "signals": {},
                }
                tables[key] = entry

            # 描述合并：优先 table_comment > filename description > 已有
            if table_comment and not entry["table_comment"]:
                entry["table_comment"] = table_comment
            if description and not entry["description"]:
                entry["description"] = description

            if is_sql:
                entry["sql_files"].append(rel_path)
                if columns and not entry["columns"]:
                    entry["columns"] = [
                        {"name": c.name, "type": c.type, "comment": c.comment}
                        for c in columns
                    ]
                if partition_columns and not entry["partition_columns"]:
                    entry["partition_columns"] = [
                        {"name": c.name, "type": c.type, "comment": c.comment}
                        for c in partition_columns
                    ]
                if signals:
                    entry["signals"] = _merge_signals(entry.get("signals", {}), signals)
            else:
                entry["doc_files"].append(rel_path)

    # -----------------------------------------------------------------------
    # 输出
    # -----------------------------------------------------------------------

    all_entries = sorted(
        tables.values(),
        key=lambda e: (e["layer"], e["name"]),
    )

    # 过滤 UNKNOWN（除非明确要求保留）
    if not include_unknown:
        entries = [e for e in all_entries if e["layer"] != "UNKNOWN"]
    else:
        entries = all_entries

    json_kw: dict[str, Any] = {"ensure_ascii": False}
    if pretty:
        json_kw["indent"] = 2
    else:
        json_kw["separators"] = (",", ":")

    # --- catalog.search.json ---
    search_tables = []
    for e in entries:
        table_id = f"{e['layer']}|{e['name']}"
        detail_ref = f"catalog/full/{e['layer']}/{e['name']}.json"

        # columns: 二维数组 [name, comment]
        cols_compact = [[c["name"], c.get("comment", "")] for c in e.get("columns", [])]

        # partition_columns: 只取 name
        part_cols = [c["name"] for c in e.get("partition_columns", [])]

        # ddl_sql_file: 只取第一个
        ddl_sql_file = e["sql_files"][0] if e["sql_files"] else ""
        doc_file = e["doc_files"][0] if e["doc_files"] else ""

        search_entry: dict[str, Any] = {
            "id": table_id,
            "layer": e["layer"],
            "name": e["name"],
        }
        if e.get("description"):
            search_entry["description"] = e["description"]
        if e.get("table_comment"):
            search_entry["table_comment"] = e["table_comment"]
        if cols_compact:
            search_entry["columns"] = cols_compact
        if part_cols:
            search_entry["partition_columns"] = part_cols
        if ddl_sql_file:
            search_entry["ddl_sql_file"] = ddl_sql_file
        if doc_file:
            search_entry["doc_file"] = doc_file
        search_entry["detail_ref"] = detail_ref

        search_tables.append(search_entry)

    search_payload = {
        "schema_version": 2,
        "root": str(root),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tables": search_tables,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    search_path = out_dir / "catalog.search.json"
    search_path.write_text(json.dumps(search_payload, **json_kw), encoding="utf-8")

    # --- catalog/full/<LAYER>/<table>.json ---
    full_dir = out_dir / "catalog" / "full"
    for e in entries:
        layer_dir = full_dir / e["layer"]
        layer_dir.mkdir(parents=True, exist_ok=True)

        detail: dict[str, Any] = {
            "id": f"{e['layer']}|{e['name']}",
            "layer": e["layer"],
            "name": e["name"],
        }
        if e.get("description"):
            detail["description"] = e["description"]
        if e.get("table_comment"):
            detail["table_comment"] = e["table_comment"]
        if e.get("columns"):
            detail["columns"] = e["columns"]
        if e.get("partition_columns"):
            detail["partition_columns"] = e["partition_columns"]
        if e.get("sql_files"):
            detail["sql_files"] = e["sql_files"]
        if e.get("doc_files"):
            detail["doc_files"] = e["doc_files"]

        compacted = _compact_signals(e.get("signals", {}))
        if compacted:
            detail["signals"] = compacted

        detail_path = layer_dir / f"{e['name']}.json"
        detail_path.write_text(json.dumps(detail, **json_kw), encoding="utf-8")

    # --- 统计 ---
    unknown_count = sum(1 for e in all_entries if e["layer"] == "UNKNOWN")
    layer_counts: dict[str, int] = {}
    for e in entries:
        layer_counts[e["layer"]] = layer_counts.get(e["layer"], 0) + 1
    cols_with_comment = sum(
        1 for e in entries
        if any(c.get("comment") for c in e.get("columns", []))
    )

    print(f"OK: 已生成 {search_path}")
    print(f"    输出目录: {out_dir}")
    print(f"    索引表数: {len(entries)}")
    if unknown_count and not include_unknown:
        print(f"    已跳过 UNKNOWN 层级: {unknown_count} 张表")
    print(f"    层级分布: {json.dumps(layer_counts, ensure_ascii=False)}")
    print(f"    有 COMMENT 的表: {cols_with_comment}/{len(entries)}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="为数仓目录生成两层 catalog（search 索引 + 按表详情）。"
    )
    parser.add_argument("--root", required=True, help="数仓目录根路径（包含 ADS/DWS/DWT）。")
    parser.add_argument(
        "--out-dir",
        default=".",
        help="输出目录（默认当前目录）。将生成 catalog.search.json 和 catalog/full/。",
    )
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
    parser.add_argument(
        "--include-unknown",
        action="store_true",
        help="是否包含 UNKNOWN 层级的表（默认不包含）。",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="输出格式化的 JSON（默认 compact）。",
    )
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    suffixes = {s.strip().lower() for s in args.suffixes.split(",") if s.strip()}
    if not suffixes:
        suffixes = set(DEFAULT_TEXT_SUFFIXES)

    if not root.exists() or not root.is_dir():
        print(f"ERROR: 目录不存在：{root}")
        return 1

    build_catalog(
        root=root,
        out_dir=out_dir,
        max_bytes=args.max_bytes,
        suffixes=suffixes,
        include_unknown=args.include_unknown,
        pretty=args.pretty,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
