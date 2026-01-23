#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AUTO_START = "<!-- AUTO-GENERATED:START -->"
AUTO_END = "<!-- AUTO-GENERATED:END -->"

SKILL_ITER_START = "<!-- ITERATION:START -->"
SKILL_ITER_END = "<!-- ITERATION:END -->"


ISSUE_TO_QUESTION: dict[str, str] = {
    "missing_metric": "要看的核心指标是什么？指标口径（去重/分母/是否含税/是否含退款）？",
    "missing_dimension": "需要按哪些维度拆分（如 渠道/地区/品类/组织）？维度枚举口径？",
    "missing_grain": "最终结果需要的粒度是什么（天/周/月 + 用户/门店/订单…）？数组字段是全部展开还是只取第一条？",
    "missing_time_range": "时间范围是什么？用哪个时间字段（下单/支付/发货/入库/事件时间）？是否需要动态获取最新分区？",
    "missing_filters": "过滤条件有哪些（业务线/渠道/状态/人群/品类）？",
    "missing_output_fields": "输出字段清单是什么？字段命名偏好（中文/英文 alias）？",
    "missing_topn_sort": "是否需要排序/TopN？按什么排序？同分如何处理？",
    "mismatch_definition": "你们的业务口径与现有表口径有差异：以哪份口径为准？需要哪些对账样例？",
    "performance_risk": "对时效/延迟有要求吗？是否需要固定在某个更新频率（T+0/T+1）？",
    "wrong_layer": "你希望从哪个数仓层取数（ADS/DWS/DWT）？有无指定的表或口径偏好？",
    "wrong_logic": "多条件筛选时是取交集（AND/JOIN）还是并集（OR/UNION）？请明确逻辑关系。",
}

ISSUE_TO_SKILL_RULE: dict[str, str] = {
    "missing_dialect_engine": "补问执行引擎/方言（Hive/SparkSQL/GaussDB）与 Hive 版本兼容性，避免写出环境不支持的语法。",
    "missing_dw_path": "补问数仓目录路径（含 ADS/DWS/DWT + 设计文档 + DDL/ETL SQL），按「逐步加载」流程建立 catalog 再选表。",
    "missing_partition_field": "补问分区字段名与类型（dt/ds/biz_date），并确保时间过滤命中分区下推，避免全表扫描。",
    "unsupported_function": "避免使用低版本 Hive 不支持的函数（如 TRANSFORM）。数组/结构体操作优先用 LATERAL VIEW EXPLODE；字符串提取优先用 regexp_extract/get_json_object。",
    "wrong_layer": "在选表前明确用户的分层偏好：若用户明确要求从 DWT/DWS 取数，不要自动降级到 ADS 层。",
    "missing_grain": "对于数组/嵌套字段，明确是「展开每条记录」还是「只取第一条/聚合」。默认展开全部，除非用户明确只要一条。",
    "wrong_logic": "多条件筛选场景下，明确「交集（AND/INNER JOIN）」还是「并集（OR/UNION）」，避免逻辑理解偏差。",
    "missing_time_range": "默认使用动态获取最新分区（CTE 子查询 MAX(dt)），除非用户明确要求参数化占位符。",
}


@dataclass(frozen=True)
class Summary:
    total: int
    good: int
    bad: int
    top_issues_bad: list[tuple[str, int]]
    updated_at: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _normalize_label(raw: Any) -> str:
    s = str(raw or "").strip().lower()
    if s in {"good", "good_case", "goodcase"}:
        return "good"
    if s in {"bad", "bad_case", "badcase"}:
        return "bad"
    return "unknown"


def _extract_issues(entry: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for raw in entry.get("issues") or []:
        v = str(raw).strip()
        if v:
            issues.append(v)
    for raw in (entry.get("feedback") or {}).get("issues") or []:
        v = str(raw).strip()
        if v:
            issues.append(v)
    return issues


def summarize(entries: list[dict[str, Any]], top_n: int = 12) -> Summary:
    total = len(entries)
    labels = [_normalize_label(e.get("label")) for e in entries]
    good = sum(1 for x in labels if x == "good")
    bad = sum(1 for x in labels if x == "bad")

    bad_issues: Counter[str] = Counter()
    for e in entries:
        if _normalize_label(e.get("label")) != "bad":
            continue
        for issue in _extract_issues(e):
            bad_issues[issue] += 1

    top_issues_bad = bad_issues.most_common(top_n)
    return Summary(
        total=total,
        good=good,
        bad=bad,
        top_issues_bad=top_issues_bad,
        updated_at=_utc_now_iso(),
    )


def _render_auto_block(summary: Summary) -> str:
    lines: list[str] = []
    lines.append(AUTO_START)
    lines.append("")
    lines.append("## 数据侧复盘摘要（自动生成，业务无需填写）")
    lines.append("")
    lines.append(f"- 更新时间：{summary.updated_at}")
    lines.append(f"- 累计样本：{summary.total}（good={summary.good}, bad={summary.bad}）")
    lines.append("")
    lines.append("### bad case 高频问题（Top）")
    lines.append("")
    if not summary.top_issues_bad:
        lines.append("- 暂无（或未在 bad case 记录 issues）。")
    else:
        for issue, cnt in summary.top_issues_bad:
            lines.append(f"- {issue}: {cnt}")
    lines.append("")
    lines.append("### 建议补问（面向业务口径澄清）")
    lines.append("")
    if not summary.top_issues_bad:
        lines.append("- 暂无（待积累 bad case 后自动补全）。")
    else:
        used = set()
        for issue, _ in summary.top_issues_bad:
            q = ISSUE_TO_QUESTION.get(issue)
            if not q or q in used:
                continue
            used.add(q)
            lines.append(f"- {q}")
    lines.append("")
    lines.append(AUTO_END)
    return "\n".join(lines).rstrip() + "\n"


def _render_base_template() -> str:
    return (
        "# 问数需求表单（飞书/问卷风格，给业务方填写）\n"
        "\n"
        "填写说明：\n"
        "- 这是“业务需求收集表单”。请尽量用业务语言描述；不要写数仓分层、表名、SQL 方言等技术细节。\n"
        "- 题目带 `【必填】` 的请务必填写；其他按需补充。\n"
        "- 有旧报表/看板/截图/样例数据的话请一定贴上（能显著减少往返）。\n"
        "\n"
        "## A. 基本信息\n"
        "\n"
        "1. 【必填】需求标题（能一眼看懂）：  \n"
        "   - 答：\n"
        "\n"
        "2. 【必填】业务背景与目标（你要解决什么问题/支持什么决策）：  \n"
        "   - 答：\n"
        "\n"
        "3. 【必填】使用场景：  \n"
        "   - [ ] 日报/周报\n"
        "   - [ ] 专项分析\n"
        "   - [ ] 临时排查\n"
        "   - [ ] 其他：_____\n"
        "\n"
        "4. 【必填】受众与使用方式（谁看、怎么用、用来做什么动作）：  \n"
        "   - 答：\n"
        "\n"
        "5. 【必填】截止时间：  \n"
        "   - 答：\n"
        "\n"
        "6. 【选填】数据更新频率/时效要求：  \n"
        "   - [ ] 实时/准实时\n"
        "   - [ ] T+0（当天）\n"
        "   - [ ] T+1（次日）\n"
        "   - [ ] 不确定/无要求\n"
        "   - 备注：_____\n"
        "\n"
        "## B. 指标（你要看的“结果”）\n"
        "\n"
        "7. 【必填】你要看的核心指标有哪些？（可多项）  \n"
        "   - 指标列表（中文名即可）：_____\n"
        "\n"
        "8. 【必填】每个指标的口径怎么定义？（尽量明确）  \n"
        "   - 是否去重（按什么去重）：_____\n"
        "   - 状态口径（哪些算入、哪些排除）：_____\n"
        "   - 是否包含退款/取消/补贴/税费：_____\n"
        "   - 分母是什么（如“退款率”的分母）：_____\n"
        "   - 其他规则：_____\n"
        "\n"
        "9. 【必填】业务对象定义与边界（非常关键）  \n"
        "   - “订单/用户/门店/商家/活动”等对象在你们业务中的定义：_____\n"
        "   - 有无特殊边界/例外（测试单、内部员工、跨境等）：_____\n"
        "\n"
        "## C. 维度与范围（你要怎么拆分/看哪里）\n"
        "\n"
        "10. 【必填】需要按哪些维度拆分查看？（可多项）  \n"
        "   - [ ] 渠道\n"
        "   - [ ] 地区\n"
        "   - [ ] 品类\n"
        "   - [ ] 组织/部门\n"
        "   - [ ] 新老客\n"
        "   - [ ] 端（App/H5/小程序/PC）\n"
        "   - [ ] 活动/策略\n"
        "   - [ ] 其他：_____\n"
        "   - 维度的枚举口径/分组方式（如“渠道”有哪些值、是否合并）：_____\n"
        "\n"
        "11. 【必填】时间范围与汇总粒度：  \n"
        "   - 时间范围：从 ____ 到 ____\n"
        "   - 汇总粒度：  \n"
        "     - [ ] 按日\n"
        "     - [ ] 按周\n"
        "     - [ ] 按月\n"
        "     - [ ] 其他：_____\n"
        "\n"
        "12. 【必填】业务范围/过滤条件（包含/排除规则）：  \n"
        "   - 必须包含：_____\n"
        "   - 必须排除：_____\n"
        "   - 若涉及人群：人群口径/圈选方式：_____\n"
        "\n"
        "## D. 输出与验收（你想拿到什么样的结果）\n"
        "\n"
        "13. 【必填】你希望拿到的结果形态：  \n"
        "   - [ ] 一张汇总表\n"
        "   - [ ] 明细表\n"
        "   - [ ] 明细 + 汇总\n"
        "   - [ ] 多张表（请说明）：_____\n"
        "\n"
        "14. 【必填】输出字段（列）清单（中文即可）：  \n"
        "   - 列清单：_____\n"
        "\n"
        "15. 【选填】是否需要排序/TopN：  \n"
        "   - [ ] 不需要\n"
        "   - [ ] 需要 TopN：N=_____\n"
        "   - 排序规则（按什么指标、升/降序）：_____\n"
        "   - 同分如何处理：_____\n"
        "\n"
        "16. 【必填】验收方式（你如何判断数据“对”）：  \n"
        "   - 对账来源（旧报表/看板/财务口径/人工抽样）：_____\n"
        "   - 可接受误差范围（如有）：_____\n"
        "\n"
        "17. 【强烈建议】参考材料/附件：  \n"
        "   - 旧报表/看板链接：_____\n"
        "   - 截图：_____\n"
        "   - 期望结果样例（3-5 行，或贴表格）：_____\n"
        "   - 口径文档：_____\n"
        "\n"
    )


def update_template(template_path: Path, summary: Summary) -> None:
    auto_block = _render_auto_block(summary)
    if not template_path.exists():
        template_path.parent.mkdir(parents=True, exist_ok=True)
        template_path.write_text(_render_base_template() + auto_block, encoding="utf-8")
        return

    text = template_path.read_text(encoding="utf-8", errors="ignore")
    if AUTO_START in text and AUTO_END in text:
        before, rest = text.split(AUTO_START, 1)
        _, after = rest.split(AUTO_END, 1)
        template_path.write_text(before.rstrip() + "\n\n" + auto_block + after.lstrip(), encoding="utf-8")
        return

    template_path.write_text(text.rstrip() + "\n\n" + auto_block, encoding="utf-8")


def _render_skill_iteration_block(summary: Summary) -> str:
    lines: list[str] = []
    lines.append(SKILL_ITER_START)
    lines.append("")
    lines.append("## 迭代摘要（自动生成）")
    lines.append("")
    lines.append("说明：本段由日志自动汇总，用于沉淀“容易遗漏的澄清点/护栏”。业务问卷尽量保持非技术化；技术性补问沉淀在本 skill 规则中。")
    lines.append("")
    lines.append(f"- 更新时间：{summary.updated_at}")
    lines.append(f"- 累计样本：{summary.total}（good={summary.good}, bad={summary.bad}）")
    lines.append("")
    lines.append("### bad case 高频问题（Top）")
    lines.append("")
    if not summary.top_issues_bad:
        lines.append("- 暂无（或未在 bad case 记录 issues）。")
    else:
        for issue, cnt in summary.top_issues_bad:
            lines.append(f"- {issue}: {cnt}")
    lines.append("")
    lines.append("### 规则沉淀建议（偏技术，写进本 skill）")
    lines.append("")
    picked = 0
    if summary.top_issues_bad:
        used = set()
        for issue, _ in summary.top_issues_bad:
            rule = ISSUE_TO_SKILL_RULE.get(issue)
            if not rule or rule in used:
                continue
            used.add(rule)
            lines.append(f"- {rule}")
            picked += 1
    if picked == 0:
        lines.append("- 暂无（建议在 bad case 里补充 `--issues`，尤其是技术性遗漏项）。")
    lines.append("")
    lines.append(SKILL_ITER_END)
    return "\n".join(lines).rstrip() + "\n"


def update_skill_md(skill_md_path: Path, summary: Summary) -> None:
    if not skill_md_path.exists():
        return
    text = skill_md_path.read_text(encoding="utf-8", errors="ignore")
    block = _render_skill_iteration_block(summary)

    if SKILL_ITER_START in text and SKILL_ITER_END in text:
        before, rest = text.split(SKILL_ITER_START, 1)
        _, after = rest.split(SKILL_ITER_END, 1)
        skill_md_path.write_text(before.rstrip() + "\n\n" + block + after.lstrip(), encoding="utf-8")
        return

    skill_md_path.write_text(text.rstrip() + "\n\n" + block, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="从 smart-data-query 的问答日志（JSONL）里汇总 good/bad case，并更新问数需求问卷模板。"
    )
    parser.add_argument(
        "--log",
        default="assets/logs/qa.jsonl",
        help="问答日志文件路径（JSONL，每行一个 JSON 对象）。默认 assets/logs/qa.jsonl",
    )
    parser.add_argument(
        "--out",
        default="references/问数需求问卷模板.md",
        help="问卷模板输出路径（Markdown）。默认 references/问数需求问卷模板.md",
    )
    parser.add_argument("--top", type=int, default=12, help="高频问题 TopN（默认 12）。")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    skill_dir = script_dir.parent

    log_path = (skill_dir / args.log).resolve() if not Path(args.log).is_absolute() else Path(args.log).resolve()
    out_path = (skill_dir / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out).resolve()

    entries = _read_jsonl(log_path)
    summary = summarize(entries, top_n=args.top)
    update_template(out_path, summary)

    print(f"OK: updated template: {out_path}")
    print(f"    samples: total={summary.total}, good={summary.good}, bad={summary.bad}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
