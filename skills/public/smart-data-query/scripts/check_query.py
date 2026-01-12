#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


FROM_JOIN_RE = re.compile(
    r"\b(from|join)\s+(?P<name>(?:`[^`]+`|\"[^\"]+\"|\[[^\]]+\]|[a-zA-Z0-9_.]+))",
    re.IGNORECASE,
)

WHERE_RE = re.compile(r"\bwhere\b", re.IGNORECASE)
CLAUSE_END_RE = re.compile(r"\b(group\s+by|having|order\s+by|limit|union)\b|;", re.IGNORECASE)

DESTRUCTIVE_RE = re.compile(
    r"\b(drop|truncate|delete|update|insert\s+overwrite|insert\s+into|create\s+table|alter\s+table)\b",
    re.IGNORECASE,
)

SELECT_STAR_RE = re.compile(r"\bselect\s+\*", re.IGNORECASE)


@dataclass(frozen=True)
class WarningItem:
    code: str
    message: str


def _read_sql(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _extract_tables(sql: str, max_items: int = 50) -> list[str]:
    names: list[str] = []
    for m in FROM_JOIN_RE.finditer(sql):
        raw = m.group("name").strip()
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"`", '"'}:
            raw = raw[1:-1]
        elif len(raw) >= 2 and raw[0] == "[" and raw[-1] == "]":
            raw = raw[1:-1]
        if not raw or raw.lower() in {"select", "values"}:
            continue
        names.append(raw)
        if len(names) >= max_items:
            break
    seen = set()
    out = []
    for n in names:
        if n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out


def _where_block(sql: str) -> str:
    m = WHERE_RE.search(sql)
    if not m:
        return ""
    rest = sql[m.end() :]
    end = CLAUSE_END_RE.search(rest)
    return rest[: end.start()] if end else rest


def _load_catalog(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    tables = payload.get("tables", [])
    index: dict[str, dict] = {}
    for entry in tables:
        name = str(entry.get("name", ""))
        if not name:
            continue
        index[name] = entry
        short = name.split(".")[-1]
        index.setdefault(short, entry)
    return index


def _dialect_warnings(sql: str, dialect: str) -> list[WarningItem]:
    warnings: list[WarningItem] = []
    if dialect == "gaussdb":
        if "`" in sql:
            warnings.append(
                WarningItem(
                    code="gaussdb-backticks",
                    message="GaussDB 通常不支持反引号标识符；建议改为不加引号或使用双引号。",
                )
            )
        for token in ("lateral view", "explode(", "collect_set(", "from_unixtime(", "unix_timestamp("):
            if token.lower() in sql.lower():
                warnings.append(
                    WarningItem(
                        code="gaussdb-hive-only",
                        message=f"发现疑似 Hive/SparkSQL 专属语法/函数：{token!r}；需要改写为 GaussDB 写法。",
                    )
                )
                break
    elif dialect in {"hive", "sparksql"}:
        if "::" in sql:
            warnings.append(
                WarningItem(
                    code="hive-postgres-cast",
                    message="发现 '::' 类型转换（更像 Postgres）；Hive/SparkSQL 可能需要改为 cast(x as type)。",
                )
            )
    elif dialect == "hive-legacy":
        if "::" in sql:
            warnings.append(
                WarningItem(
                    code="hive-legacy-postgres-cast",
                    message="发现 '::' 类型转换（更像 Postgres）；低版本 Hive 建议改为 cast(x as type)。",
                )
            )
    return warnings


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"/\\*.*?\\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\\n]*", " ", sql)
    return sql


def _find_top_level_keyword(sql: str, keyword: str, start: int = 0) -> int:
    target = keyword.lower()
    depth = 0
    in_single = False
    in_double = False
    in_backtick = False

    i = start
    while i < len(sql):
        ch = sql[i]
        if ch == "'" and not in_double and not in_backtick:
            in_single = not in_single
            i += 1
            continue
        if ch == '"' and not in_single and not in_backtick:
            in_double = not in_double
            i += 1
            continue
        if ch == "`" and not in_single and not in_double:
            in_backtick = not in_backtick
            i += 1
            continue

        if in_single or in_double or in_backtick:
            i += 1
            continue

        if ch == "(":
            depth += 1
            i += 1
            continue
        if ch == ")":
            depth = max(0, depth - 1)
            i += 1
            continue

        if depth == 0:
            if sql[i : i + len(target)].lower() == target:
                before = sql[i - 1] if i > 0 else " "
                after = sql[i + len(target)] if i + len(target) < len(sql) else " "
                if not (before.isalnum() or before == "_") and not (after.isalnum() or after == "_"):
                    return i
        i += 1
    return -1


def _find_top_level_select_clause(sql: str) -> str:
    cleaned = _strip_comments(sql)
    select_pos = _find_top_level_keyword(cleaned, "select", start=0)
    if select_pos == -1:
        return ""
    from_pos = _find_top_level_keyword(cleaned, "from", start=select_pos + 6)
    if from_pos == -1:
        return ""
    return cleaned[select_pos + 6 : from_pos]


def _find_top_level_order_by_clause(sql: str) -> str:
    cleaned = _strip_comments(sql)
    ob_pos = _find_top_level_keyword(cleaned, "order by", start=0)
    if ob_pos == -1:
        return ""
    rest = cleaned[ob_pos + len("order by") :]
    end = CLAUSE_END_RE.search(rest)
    return rest[: end.start()] if end else rest


def _split_top_level_comma(text: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    in_single = False
    in_double = False
    in_backtick = False

    for ch in text:
        if ch == "'" and not in_double and not in_backtick:
            in_single = not in_single
        elif ch == '"' and not in_single and not in_backtick:
            in_double = not in_double
        elif ch == "`" and not in_single and not in_double:
            in_backtick = not in_backtick
        elif not in_single and not in_double and not in_backtick:
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


def _extract_select_identifiers(sql: str) -> set[str]:
    clause = _find_top_level_select_clause(sql)
    if not clause.strip():
        return set()
    out: set[str] = set()

    for raw in _split_top_level_comma(clause):
        item = raw.strip()
        if not item:
            continue

        # Prefer explicit alias: "... as alias"
        m = re.search(
            r"\bas\s+(?P<alias>(?:`[^`]+`|\"[^\"]+\"|\[[^\]]+\]|[a-zA-Z_][a-zA-Z0-9_]*))\s*$",
            item,
            flags=re.IGNORECASE,
        )
        if m:
            alias = m.group("alias").strip()
            if len(alias) >= 2 and alias[0] == alias[-1] and alias[0] in {"`", '"'}:
                alias = alias[1:-1]
            elif len(alias) >= 2 and alias[0] == "[" and alias[-1] == "]":
                alias = alias[1:-1]
            out.add(alias.lower())
            continue

        # Otherwise, if it ends with "... <alias>" (and the left isn't just a dotted identifier),
        # treat that last token as alias.
        tokens = item.split()
        if len(tokens) >= 2:
            tail = tokens[-1].strip()
            if re.match(r"^(?:`[^`]+`|\"[^\"]+\"|\[[^\]]+\]|[a-zA-Z_][a-zA-Z0-9_]*)$", tail):
                if len(tail) >= 2 and tail[0] == tail[-1] and tail[0] in {"`", '"'}:
                    tail = tail[1:-1]
                elif len(tail) >= 2 and tail[0] == "[" and tail[-1] == "]":
                    tail = tail[1:-1]
                out.add(tail.lower())
                continue

        # Fallback: if it's a simple column reference, collect both full and short name.
        m2 = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*\.)?([a-zA-Z_][a-zA-Z0-9_]*)$", item)
        if m2:
            out.add(m2.group(2).lower())
    return out


def _extract_order_by_identifiers(sql: str) -> list[str]:
    clause = _find_top_level_order_by_clause(sql)
    if not clause.strip():
        return []
    out: list[str] = []
    for raw in _split_top_level_comma(clause):
        item = raw.strip()
        if not item:
            continue
        # Drop nulls first/last and direction
        item = re.sub(r"\s+nulls\s+(first|last)\s*$", "", item, flags=re.IGNORECASE).strip()
        item = re.sub(r"\s+(asc|desc)\s*$", "", item, flags=re.IGNORECASE).strip()
        if not item:
            continue
        if re.match(r"^\d+$", item):
            out.append(item)
            continue
        if re.match(r"^(?:`[^`]+`|\"[^\"]+\"|\[[^\]]+\])$", item):
            ident = item
            if len(ident) >= 2 and ident[0] == ident[-1] and ident[0] in {"`", '"'}:
                ident = ident[1:-1]
            elif len(ident) >= 2 and ident[0] == "[" and ident[-1] == "]":
                ident = ident[1:-1]
            out.append(ident.lower())
            continue
        m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*\.)?([a-zA-Z_][a-zA-Z0-9_]*)$", item)
        if m:
            out.append(m.group(2).lower())
            continue
        # expression/function: ignore (can't safely validate)
    return out


def _iter_top_level_on_clauses(sql: str, max_clauses: int = 20) -> list[str]:
    cleaned = _strip_comments(sql)
    clauses: list[str] = []
    start = 0
    while len(clauses) < max_clauses:
        on_pos = _find_top_level_keyword(cleaned, "on", start=start)
        if on_pos == -1:
            break
        next_pos = len(cleaned)
        for kw in (" join ", " where ", " group by ", " having ", " order by ", " limit ", " union "):
            p = cleaned.lower().find(kw, on_pos + 2)
            if p != -1:
                next_pos = min(next_pos, p)
        clauses.append(cleaned[on_pos + 2 : next_pos])
        start = on_pos + 2
    return clauses


def check(sql: str, dialect: str, catalog_index: dict[str, dict] | None) -> list[WarningItem]:
    warnings: list[WarningItem] = []
    if DESTRUCTIVE_RE.search(sql):
        warnings.append(
            WarningItem(
                code="destructive",
                message="SQL 包含潜在破坏性语句（drop/truncate/delete/insert/create/alter 等）；智能问数默认只应产出查询导出 SQL。",
            )
        )
    if SELECT_STAR_RE.search(sql):
        warnings.append(
            WarningItem(
                code="select-star",
                message="发现 'select *'；建议显式列出字段以便对账与避免维表字段膨胀。",
            )
        )

    tables = _extract_tables(sql)
    where_block = _where_block(sql).lower()
    if catalog_index:
        for t in tables:
            entry = catalog_index.get(t) or catalog_index.get(t.split(".")[-1])
            if not entry:
                continue
            part_cols = [c.get("name", "") for c in entry.get("partition_columns", []) if c.get("name")]
            if not part_cols:
                continue
            if not where_block:
                warnings.append(
                    WarningItem(
                        code="missing-where",
                        message=f"表 {entry.get('name')} 有分区列 {part_cols}，但 SQL 未发现 where；可能无法下推分区导致全表扫描。",
                    )
                )
                continue
            hit = any(re.search(rf"\\b{re.escape(col.lower())}\\b", where_block) for col in part_cols)
            if not hit:
                warnings.append(
                    WarningItem(
                        code="missing-partition-filter",
                        message=f"表 {entry.get('name')} 有分区列 {part_cols}，但 where 未命中；建议用分区列做时间过滤（下推）。",
                    )
                )

    warnings.extend(_dialect_warnings(sql, dialect=dialect))
    if sql.lower().count(" join ") >= 3 and "row_number" not in sql.lower():
        warnings.append(
            WarningItem(
                code="many-joins",
                message="join 数量较多；注意维表多版本/多行导致多对多放大，必要时先对维表去重/取最新再 join。",
            )
        )

    if dialect in {"hive", "hive-legacy"}:
        selected = _extract_select_identifiers(sql)
        order_by = _extract_order_by_identifiers(sql)
        missing = [c for c in order_by if not c.isdigit() and c not in selected]
        if missing:
            warnings.append(
                WarningItem(
                    code="hive-orderby-not-selected",
                    message=(
                        "ORDER BY 引用了未出现在最终 SELECT 列表的字段（"
                        + ", ".join(missing)
                        + "）；部分 Hive 版本会报 `Invalid table alias or column reference`。"
                        "建议：把排序字段也输出（可命名为辅助列并提示用户忽略/后处理删除），或改用 ORDER BY 位置序号。"
                    ),
                )
            )

    if dialect == "hive-legacy":
        select_clause = _find_top_level_select_clause(sql)
        if re.search(r"\(\s*select\b", select_clause, flags=re.IGNORECASE):
            warnings.append(
                WarningItem(
                    code="hive-legacy-scalar-subquery-select",
                    message="疑似在 SELECT 列表中使用 scalar subquery（形如 `(select ...)`）；低版本 Hive 常报 `Unsupported SubQuery Expression`，建议改写为 JOIN/派生表/CTE。",
                )
            )
        for on_clause in _iter_top_level_on_clauses(sql):
            if re.search(r"\(\s*select\b", on_clause, flags=re.IGNORECASE):
                warnings.append(
                    WarningItem(
                        code="hive-legacy-scalar-subquery-on",
                        message="疑似在 JOIN ... ON 条件中使用 subquery（形如 `(select ...)`）；低版本 Hive 可能不支持，建议先把子查询变成派生表再 JOIN，或改为两步聚合后 JOIN。",
                    )
                )
    return warnings


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="对生成的查询 SQL 做静态检查（启发式警告，不连库）。")
    parser.add_argument("--sql", help="SQL 文件路径；不提供则从 stdin 读取。")
    parser.add_argument("--catalog", help="catalog.json（由 build_catalog.py 生成，可用于分区过滤检查）。")
    parser.add_argument(
        "--dialect",
        default="hive",
        choices=["hive", "hive-legacy", "sparksql", "gaussdb"],
        help="目标方言（默认 hive）。",
    )
    args = parser.parse_args(argv)

    sql = sys.stdin.read() if not args.sql else _read_sql(Path(args.sql).expanduser().resolve())
    if not sql.strip():
        print("ERROR: SQL 为空", file=sys.stderr)
        return 1

    catalog_index = None
    if args.catalog:
        catalog_index = _load_catalog(Path(args.catalog).expanduser().resolve())

    warnings = check(sql, dialect=args.dialect, catalog_index=catalog_index)
    if not warnings:
        print("OK: 未发现明显风险（仅静态启发式检查）。")
        return 0

    print(f"WARN: 共 {len(warnings)} 条")
    for w in warnings:
        print(f"- [{w.code}] {w.message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
