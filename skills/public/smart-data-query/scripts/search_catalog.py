#!/usr/bin/env python3
"""基于 catalog.search.json 的关键词检索候选表（v2）。

改进：
- 适配 schema_version=2（columns 二维数组、description/table_comment）
- 增强 tokenize：NFKC 归一化、snake_case 拆分、stopwords 过滤、最小长度
- COMMENT / description 纳入搜索权重
- LOW_INFO token 降权
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

TOKEN_RE = re.compile(r"[a-z0-9_\.]+|[\u4e00-\u9fff]+", re.IGNORECASE)

STOPWORDS_EN = {
    "select", "from", "where", "join", "left", "right", "inner", "outer",
    "group", "by", "order", "limit", "and", "or", "as", "on", "in", "is",
    "not", "null", "like", "between", "case", "when", "then", "else", "end",
    "having", "insert", "into", "table", "create", "drop", "alter", "set",
    "with", "union", "all", "distinct", "true", "false", "the", "of", "for",
}

STOPWORDS_ZH = {
    "查询", "统计", "导出", "获取", "数据", "信息", "明细", "汇总",
    "报表", "字段", "表", "结果", "最近", "按", "各", "所有",
    "需要", "希望", "帮忙", "帮我", "请", "一下",
}

# 高频列名：降权但不删除
LOW_INFO_TOKENS = {"id", "name", "code", "dt", "ds", "type", "status", "flag"}

LOW_INFO_WEIGHT = 0.5  # 降权系数


def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).lower()
    s = re.sub(r"[^0-9a-z_\.\u4e00-\u9fff]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _tokenize(query: str) -> list[str]:
    """将查询文本拆分为去重的检索 token。"""
    query = _normalize(query)
    raw = TOKEN_RE.findall(query)
    out: list[str] = []
    seen: set[str] = set()

    for tok in raw:
        if tok.isascii():
            # 英文：拆 snake_case，保留原始 + 子段
            parts = [tok] + [p for p in re.split(r"[_\.]+", tok) if p and p != tok]
            for p in parts:
                if len(p) < 2:
                    continue
                if p in STOPWORDS_EN:
                    continue
                if p.isdigit() and len(p) < 3:
                    continue
                if p not in seen:
                    seen.add(p)
                    out.append(p)
        else:
            # 中文
            if len(tok) < 2:
                continue
            if tok in STOPWORDS_ZH:
                continue
            if tok not in seen:
                seen.add(tok)
                out.append(tok)
    return out


# ---------------------------------------------------------------------------
# Scoring（适配 schema_version=2）
# ---------------------------------------------------------------------------

def _score_entry(entry: dict, tokens: list[str], prefer_layers: list[str]) -> float:
    """计算表与查询 token 的匹配得分。"""
    hay_name = str(entry.get("name", "")).lower()
    hay_desc = str(entry.get("description", "")).lower()
    hay_table_comment = str(entry.get("table_comment", "")).lower()
    hay_path = str(entry.get("ddl_sql_file", "")).lower()

    # columns: v2 格式为 [[name, comment], ...]
    columns = entry.get("columns", [])
    if columns and isinstance(columns[0], list):
        hay_col_names = " ".join(c[0] for c in columns).lower()
        hay_col_comments = " ".join(c[1] for c in columns if len(c) > 1 and c[1]).lower()
    else:
        # 兼容 v1 格式
        hay_col_names = " ".join(c.get("name", "") for c in columns).lower()
        hay_col_comments = ""

    # partition_columns: v2 格式为 [name, ...]
    part_cols = entry.get("partition_columns", [])
    if part_cols and isinstance(part_cols[0], str):
        hay_part_cols = " ".join(part_cols).lower()
    else:
        hay_part_cols = " ".join(c.get("name", "") for c in part_cols).lower()

    score: float = 0.0
    for t in tokens:
        weight = LOW_INFO_WEIGHT if t in LOW_INFO_TOKENS else 1.0

        if t in hay_name:
            score += 5 * weight
        if t in hay_desc:
            score += 4 * weight
        if t in hay_table_comment:
            score += 4 * weight
        if t in hay_col_comments:
            score += 4 * weight
        if t in hay_col_names:
            score += 3 * weight
        if t in hay_part_cols:
            score += 3 * weight
        if t in hay_path:
            score += 1 * weight

    # 层级偏好加分
    layer = str(entry.get("layer", "UNKNOWN")).upper()
    if layer in prefer_layers:
        score += max(0, 3 - prefer_layers.index(layer))

    return score


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def _print_entry(score: float, entry: dict, catalog_root: Path | None) -> None:
    layer = entry.get("layer", "UNKNOWN")
    name = entry.get("name", "")
    desc = entry.get("description", "")
    tc = entry.get("table_comment", "")

    header = f"[{score:>5.1f}] {layer:<7} {name}"
    if desc:
        header += f"  ({desc})"
    print(header)

    if tc and tc != desc:
        print(f"      COMMENT: {tc}")

    ddl = entry.get("ddl_sql_file", "")
    if ddl:
        print(f"      SQL: {ddl}")
    doc = entry.get("doc_file", "")
    if doc:
        print(f"      DOC: {doc}")

    columns = entry.get("columns", [])
    if columns:
        if isinstance(columns[0], list):
            sample = ", ".join(
                f"{c[0]}({c[1]})" if len(c) > 1 and c[1] else c[0]
                for c in columns[:10]
            )
            more = f" ...(+{len(columns) - 10})" if len(columns) > 10 else ""
        else:
            sample = ", ".join(c.get("name", "") for c in columns[:10])
            more = f" ...(+{len(columns) - 10})" if len(columns) > 10 else ""
        print(f"      COL: {sample}{more}")

    part_cols = entry.get("partition_columns", [])
    if part_cols:
        if isinstance(part_cols[0], str):
            print(f"     PART: {', '.join(part_cols)}")
        else:
            print(f"     PART: {', '.join(c.get('name', '') for c in part_cols)}")

    detail = entry.get("detail_ref", "")
    if detail and catalog_root:
        full_path = catalog_root / detail
        if full_path.exists():
            print(f"   DETAIL: {detail}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="基于 catalog.search.json 的关键词检索候选表（v2）。"
    )
    parser.add_argument(
        "--catalog",
        required=True,
        help="catalog.search.json 路径（由 build_catalog.py 生成）。",
    )
    parser.add_argument("--q", required=True, help="检索关键词（空格分隔，支持中英文混合）。")
    parser.add_argument("--layer", default="", help="仅筛选某层（ADS/DWS/DWT/DWD/ODS）。")
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
    catalog_root = catalog_path.parent

    tokens = _tokenize(args.q)
    if not tokens:
        print("ERROR: 关键词为空（可能全被 stopwords 过滤）")
        print(f"  原始输入: {args.q}")
        return 1

    layer_filter = args.layer.strip().upper()
    prefer_layers = [p.strip().upper() for p in args.prefer.split(",") if p.strip()]

    scored: list[tuple[float, dict]] = []
    for entry in tables:
        layer = str(entry.get("layer", "UNKNOWN")).upper()
        if layer_filter and layer != layer_filter:
            continue
        score = _score_entry(entry, tokens=tokens, prefer_layers=prefer_layers)
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda x: (-x[0], x[1].get("layer", ""), x[1].get("name", "")))

    print(f"检索词: {' '.join(tokens)} (共 {len(scored)} 条命中)\n")

    for score, entry in scored[: args.top]:
        _print_entry(score, entry, catalog_root)
        print()

    if not scored:
        print("未命中任何候选表。建议：")
        print("  - 扩大关键词、改用同义词")
        print("  - 用中文业务名称搜索（如 '高校' '企业' '专利'）")
        print("  - 用英文表名片段搜索（如 'enterprise' 'patent'）")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
