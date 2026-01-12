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
    return warnings


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
    return warnings


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="对生成的查询 SQL 做静态检查（启发式警告，不连库）。")
    parser.add_argument("--sql", help="SQL 文件路径；不提供则从 stdin 读取。")
    parser.add_argument("--catalog", help="catalog.json（由 build_catalog.py 生成，可用于分区过滤检查）。")
    parser.add_argument(
        "--dialect",
        default="hive",
        choices=["hive", "sparksql", "gaussdb"],
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
