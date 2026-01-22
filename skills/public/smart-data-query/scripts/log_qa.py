#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class State:
    last_optimized_labeled_count: int
    last_optimized_at: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_text_arg(text: str | None, file_path: str | None) -> str:
    if text and file_path:
        raise SystemExit("ERROR: use only one of --question/--question-file (or --answer/--answer-file)")
    if file_path:
        return Path(file_path).read_text(encoding="utf-8", errors="ignore").strip()
    return (text or "").strip()


def _parse_kv(items: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in items:
        if "=" not in raw:
            raise SystemExit(f"ERROR: invalid --meta item (expected k=v): {raw!r}")
        k, v = raw.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not k:
            raise SystemExit(f"ERROR: invalid --meta key: {raw!r}")
        out[k] = v
    return out


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    _ensure_parent(path)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _count_jsonl_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("rb") as f:
        return sum(1 for line in f if line.strip())

def _normalize_label(raw: Any) -> str:
    s = str(raw or "").strip().lower()
    if s in {"good", "good_case", "goodcase"}:
        return "good"
    if s in {"bad", "bad_case", "badcase"}:
        return "bad"
    return "unknown"


def _count_labeled_sessions(path: Path) -> int:
    if not path.exists():
        return 0
    labeled = 0
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        if _normalize_label(obj.get("label")) in {"good", "bad"}:
            labeled += 1
    return labeled


def _load_state(path: Path) -> State:
    if not path.exists():
        return State(last_optimized_labeled_count=0, last_optimized_at="")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return State(last_optimized_labeled_count=0, last_optimized_at="")
    return State(
        last_optimized_labeled_count=int(
            payload.get("last_optimized_labeled_count") or payload.get("last_optimized_count") or 0
        ),
        last_optimized_at=str(payload.get("last_optimized_at") or ""),
    )


def _save_state(path: Path, state: State) -> None:
    _ensure_parent(path)
    path.write_text(
        json.dumps(
            {
                "last_optimized_labeled_count": state.last_optimized_labeled_count,
                "last_optimized_at": state.last_optimized_at,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

def _update_jsonl_entry(path: Path, entry_id: str, patch: dict[str, Any]) -> bool:
    if not path.exists():
        return False

    updated = False
    tmp = path.with_suffix(path.suffix + ".tmp")
    with path.open("r", encoding="utf-8", errors="ignore") as src, tmp.open("w", encoding="utf-8") as dst:
        for raw in src:
            line = raw.rstrip("\n")
            stripped = line.strip()
            if not stripped:
                dst.write(raw)
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError:
                dst.write(raw)
                continue
            if isinstance(obj, dict) and str(obj.get("id", "")).strip() == entry_id:
                obj.update(patch)
                dst.write(json.dumps(obj, ensure_ascii=False) + "\n")
                updated = True
            else:
                dst.write(raw if raw.endswith("\n") else raw + "\n")

    tmp.replace(path)
    return updated


def _maybe_optimize(skill_dir: Path, log_path: Path, template_rel: str, state_path: Path, threshold: int) -> None:
    state = _load_state(state_path)
    labeled = _count_labeled_sessions(log_path)
    if labeled < threshold:
        return
    if labeled - state.last_optimized_labeled_count < threshold:
        return

    scripts_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(scripts_dir))
    try:
        import optimize_questionnaire  # type: ignore
    finally:
        sys.path.pop(0)

    argv = ["--log", str(log_path), "--out", str((skill_dir / template_rel).resolve())]
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--log")
    parser.add_argument("--out")
    args, _ = parser.parse_known_args(argv)

    entries = optimize_questionnaire._read_jsonl(Path(args.log))  # noqa: SLF001
    summary = optimize_questionnaire.summarize(entries)  # noqa: SLF001
    optimize_questionnaire.update_template(Path(args.out), summary)  # noqa: SLF001
    optimize_questionnaire.update_skill_md((skill_dir / "SKILL.md").resolve(), summary)  # noqa: SLF001

    _save_state(state_path, State(last_optimized_labeled_count=labeled, last_optimized_at=_utc_now_iso()))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="记录一次 smart-data-query 问答样本（JSONL），并在样本数达到阈值时自动更新问卷模板。"
    )
    parser.add_argument("--label", default="unknown", choices=["good", "bad", "unknown"], help="样本标签。")
    parser.add_argument(
        "--update",
        action="store_true",
        help="更新已存在的 session-id 记录（用于补充 good/bad + 反馈/问题标签）；若不存在则回退为追加写入。",
    )

    parser.add_argument("--question", default="", help="用户原始问数需求文本。")
    parser.add_argument("--question-file", default="", help="用户原始问数需求文本文件路径。")
    parser.add_argument("--answer", default="", help="助手最终交付（SQL/说明）。")
    parser.add_argument("--answer-file", default="", help="助手最终交付文件路径。")

    parser.add_argument("--feedback", default="", help="人工反馈（1-3 句即可）。")
    parser.add_argument(
        "--issues",
        default="",
        help="结构化问题标签（逗号分隔），建议用于 bad case，比如 missing_grain,missing_time_range。",
    )
    parser.add_argument("--session-id", default="", help="可选：同一轮对话的 session id（不填则自动生成）。")
    parser.add_argument("--dialect", default="", help="可选：hive/sparksql/gaussdb/hive-legacy。")
    parser.add_argument("--warehouse-path", default="", help="可选：本次使用的数仓目录路径。")
    parser.add_argument("--sql-path", default="", help="可选：最终 SQL 文件路径（相对或绝对）。")
    parser.add_argument("--meta", action="append", default=[], help="可选：额外元信息 k=v，可重复。")

    parser.add_argument(
        "--log-file",
        default="assets/logs/qa.jsonl",
        help="日志文件路径（相对 skill 根目录）。默认 assets/logs/qa.jsonl",
    )
    parser.add_argument(
        "--state-file",
        default="assets/logs/state.json",
        help="优化状态文件路径（相对 skill 根目录）。默认 assets/logs/state.json",
    )
    parser.add_argument(
        "--template",
        default="references/问数需求问卷模板.md",
        help="问卷模板路径（相对 skill 根目录）。默认 references/问数需求问卷模板.md",
    )
    parser.add_argument("--threshold", type=int, default=20, help="自动优化触发阈值（默认 20）。")
    parser.add_argument("--no-optimize", action="store_true", help="仅写日志，不触发自动优化。")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    skill_dir = script_dir.parent

    entry_id = args.session_id.strip() or str(uuid.uuid4())
    issues = [x.strip() for x in (args.issues or "").split(",") if x.strip()]

    log_path = (skill_dir / args.log_file).resolve()
    state_path = (skill_dir / args.state_file).resolve()

    question = _read_text_arg(args.question, args.question_file or None)
    answer = _read_text_arg(args.answer, args.answer_file or None)

    if args.update:
        patch: dict[str, Any] = {
            "label": args.label,
            "feedback": {"text": (args.feedback or "").strip(), "issues": issues},
            "dialect": (args.dialect or "").strip(),
            "warehouse_path": (args.warehouse_path or "").strip(),
            "sql_path": (args.sql_path or "").strip(),
            "meta": _parse_kv(args.meta),
            "updated_at": _utc_now_iso(),
        }
        if question:
            patch["question"] = question
        if answer:
            patch["answer"] = answer
        ok = _update_jsonl_entry(log_path, entry_id, patch)
        if ok:
            print(f"OK: updated log: {log_path} (id={entry_id})")
        else:
            print(f"NOTE: log id not found, appending instead (id={entry_id})")
        if ok:
            if not args.no_optimize:
                _maybe_optimize(skill_dir, log_path, args.template, state_path, threshold=args.threshold)
            return 0

    if not question:
        print("ERROR: empty question (provide --question or --question-file)", file=sys.stderr)
        return 2
    if not answer:
        print("ERROR: empty answer (provide --answer or --answer-file)", file=sys.stderr)
        return 2

    payload: dict[str, Any] = {
        "id": entry_id,
        "ts": _utc_now_iso(),
        "skill": "smart-data-query",
        "label": args.label,
        "question": question,
        "answer": answer,
        "feedback": {"text": (args.feedback or "").strip(), "issues": issues},
        "dialect": (args.dialect or "").strip(),
        "warehouse_path": (args.warehouse_path or "").strip(),
        "sql_path": (args.sql_path or "").strip(),
        "meta": _parse_kv(args.meta),
    }

    _append_jsonl(log_path, payload)
    print(f"OK: appended log: {log_path}")
    print("NOTE: logs live under assets/logs/ and are gitignored; use ls/cat to view them (git status won't show).")

    if not args.no_optimize:
        _maybe_optimize(skill_dir, log_path, args.template, state_path, threshold=args.threshold)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
