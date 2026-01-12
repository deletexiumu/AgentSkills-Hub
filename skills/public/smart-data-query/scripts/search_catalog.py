#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _tokenize(query: str) -> list[str]:
    return [t.strip().lower() for t in query.split() if t.strip()]


def _score_entry(entry: dict, tokens: list[str], prefer_layers: list[str]) -> int:
    hay_name = str(entry.get("name", "")).lower()
    hay_paths = " ".join(entry.get("sql_files", []) + entry.get("doc_files", [])).lower()
    hay_cols = " ".join([c.get("name", "") for c in entry.get("columns", [])]).lower()
    hay_part_cols = " ".join([c.get("name", "") for c in entry.get("partition_columns", [])]).lower()
    signals = entry.get("signals", {}) or {}
    hay_insert_targets = " ".join(signals.get("insert_targets", [])).lower()
    hay_sources = " ".join(signals.get("source_tables", [])).lower()
    hay_group_by = " ".join(signals.get("group_by", [])).lower()

    score = 0
    for t in tokens:
        if t in hay_name:
            score += 5
        if t in hay_cols:
            score += 3
        if t in hay_part_cols:
            score += 3
        if t in hay_insert_targets:
            score += 2
        if t in hay_group_by:
            score += 2
        if t in hay_sources:
            score += 1
        if t in hay_paths:
            score += 1

    layer = str(entry.get("layer", "UNKNOWN")).upper()
    if layer in prefer_layers:
        score += max(0, 3 - prefer_layers.index(layer))

    return score


def main() -> int:
    parser = argparse.ArgumentParser(description="基于 catalog 关键词检索候选表（用于逐步加载）。")
    parser.add_argument("--catalog", required=True, help="catalog.json 路径（由 build_catalog.py 生成）。")
    parser.add_argument("--q", required=True, help="检索关键词（空格分隔）。")
    parser.add_argument("--layer", default="", help="仅筛选某层（ADS/DWS/DWT）。")
    parser.add_argument("--top", type=int, default=20, help="返回数量（默认 20）。")
    parser.add_argument(
        "--prefer",
        default="ADS,DWS,DWT",
        help="层级偏好顺序（逗号分隔，默认 ADS,DWS,DWT）。",
    )
    args = parser.parse_args()

    catalog_path = Path(args.catalog).expanduser().resolve()
    if not catalog_path.exists():
        print(f"ERROR: catalog 不存在：{catalog_path}")
        return 1

    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    tables = payload.get("tables", [])

    tokens = _tokenize(args.q)
    if not tokens:
        print("ERROR: 关键词为空")
        return 1

    layer_filter = args.layer.strip().upper()
    prefer_layers = [p.strip().upper() for p in args.prefer.split(",") if p.strip()]

    scored: list[tuple[int, dict]] = []
    for entry in tables:
        layer = str(entry.get("layer", "UNKNOWN")).upper()
        if layer_filter and layer != layer_filter:
            continue
        score = _score_entry(entry, tokens=tokens, prefer_layers=prefer_layers)
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda x: (-x[0], x[1].get("layer", ""), x[1].get("name", "")))

    for score, entry in scored[: args.top]:
        layer = entry.get("layer", "UNKNOWN")
        name = entry.get("name", "")
        sql_files = entry.get("sql_files", [])
        doc_files = entry.get("doc_files", [])
        cols = entry.get("columns", [])
        part_cols = entry.get("partition_columns", [])
        signals = entry.get("signals", {}) or {}

        print(f"[{score:>3}] {layer:<7} {name}")
        if sql_files:
            print(f"      SQL: {sql_files[0]}")
        if doc_files:
            print(f"      DOC: {doc_files[0]}")
        if cols:
            sample = ", ".join([c.get("name", "") for c in cols[:12]])
            more = "" if len(cols) <= 12 else f" ...(+{len(cols) - 12})"
            print(f"      COL: {sample}{more}")
        if part_cols:
            sample = ", ".join([c.get("name", "") for c in part_cols[:8]])
            more = "" if len(part_cols) <= 8 else f" ...(+{len(part_cols) - 8})"
            print(f"     PART: {sample}{more}")

        group_by = signals.get("group_by") or []
        if group_by:
            sample = ", ".join(group_by[:10])
            more = "" if len(group_by) <= 10 else f" ...(+{len(group_by) - 10})"
            print(f"  SIGNAL: group_by={sample}{more}")
        row_part = signals.get("row_number_partition_by") or []
        if row_part:
            sample = ", ".join(row_part[:10])
            more = "" if len(row_part) <= 10 else f" ...(+{len(row_part) - 10})"
            print(f"  SIGNAL: row_number_partition_by={sample}{more}")
        if signals.get("has_select_distinct"):
            print("  SIGNAL: has_select_distinct=true")

    if not scored:
        print("未命中任何候选表。建议：扩大关键词、改用同义词、或先手动确认业务实体/指标中文名与表命名规则。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
