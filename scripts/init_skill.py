#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


VALID_RESOURCES = {"scripts", "references", "assets"}
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_NAME_LENGTH = 64


def _render_skill_md(skill_name: str) -> str:
    template_path = Path("templates/skill/SKILL.md")
    if template_path.exists():
        template = template_path.read_text(encoding="utf-8")
        template = template.replace("name: my-skill", f"name: {skill_name}")
        template = template.replace("my-skill", skill_name)
        return template

    # 回退模板（含 i18n 支持）
    return (
        "---\n"
        f"name: {skill_name}\n"
        "description: [ZH] 用一句话说明这个 skill 做什么，以及在什么触发语境/任务类型下应该使用它（尽量包含关键词）；"
        "[EN] Describe what this skill does in one sentence, and in what context/task type it should be used (include keywords)；"
        "[JA] このスキルが何をするか、どのような状況/タスクで使用すべきかを一文で説明（キーワードを含む）\n"
        "---\n\n"
        "<!-- i18n-examples:start -->\n"
        "## 调用 / Invoke / 呼び出し\n\n"
        "### 中文\n"
        f'- "用 {skill_name} 执行某任务"\n'
        f'- "用 {skill_name} 生成某结果"\n'
        f'- "用 {skill_name} 处理某输入"\n\n'
        "### English\n"
        f'- "Use {skill_name} to perform a task"\n'
        f'- "Use {skill_name} to generate a result"\n'
        f'- "Use {skill_name} to process an input"\n\n'
        "### 日本語\n"
        f'- "{skill_name} でタスクを実行して"\n'
        f'- "{skill_name} で結果を生成して"\n'
        f'- "{skill_name} で入力を処理して"\n'
        "<!-- i18n-examples:end -->\n\n"
        "# 目标\n\n"
        "用简短文字说明这个 skill 要帮 agent 交付的最终结果（可量化/可验收）。\n\n"
        "# 流程\n\n"
        "1. 澄清输入、约束与成功标准。\n"
        "2. 执行核心步骤（优先复用本 skill 的脚本/参考资料/资产）。\n"
        "3. 校验结果并输出交付物（包含失败时的回退策略）。\n\n"
        "# 护栏\n\n"
        "- 未经用户明确确认，不执行破坏性操作（删除、覆盖、不可逆变更等）。\n"
        "- 对重复/易错/脆弱步骤，优先脚本化以提升确定性。\n\n"
        "# 资源\n\n"
        "- `scripts/`：放可运行的工具脚本（可参数化、可复用）。\n"
        "- `references/`：放仅在需要时加载的资料（在本文用相对路径链接）。\n"
        "- `assets/`：放模板、样式、素材等输出资源。\n"
    )


def _parse_resources(value: str) -> list[str]:
    if not value:
        return []
    resources = [part.strip() for part in value.split(",") if part.strip()]
    unknown = sorted(set(resources) - VALID_RESOURCES)
    if unknown:
        raise ValueError(f"Unknown resources: {', '.join(unknown)}")
    return resources


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize a new skill folder.")
    parser.add_argument("skill_name", help="Skill name (kebab-case).")
    parser.add_argument(
        "--path",
        required=True,
        help="Output parent directory (e.g., skills/public).",
    )
    parser.add_argument(
        "--resources",
        default="",
        help="Comma-separated resource dirs to create: scripts,references,assets",
    )
    parser.add_argument(
        "--examples",
        action="store_true",
        help="Create placeholder example files in resource dirs.",
    )
    args = parser.parse_args()

    if len(args.skill_name) > MAX_NAME_LENGTH or not NAME_RE.match(args.skill_name):
        raise SystemExit(
            f"Invalid skill name: {args.skill_name!r} (must match {NAME_RE.pattern}, <= {MAX_NAME_LENGTH})"
        )

    output_parent = Path(args.path).expanduser().resolve()
    skill_dir = output_parent / args.skill_name

    if skill_dir.exists():
        raise SystemExit(f"Refusing to overwrite existing folder: {skill_dir}")

    skill_dir.mkdir(parents=True, exist_ok=False)
    (skill_dir / "SKILL.md").write_text(_render_skill_md(args.skill_name), encoding="utf-8")

    resources = _parse_resources(args.resources)
    for resource in resources:
        (skill_dir / resource).mkdir(parents=True, exist_ok=True)
        if args.examples:
            placeholder = skill_dir / resource / f"EXAMPLE.{ 'py' if resource == 'scripts' else 'md' }"
            if resource == "scripts":
                placeholder.write_text(
                    "#!/usr/bin/env python3\nprint('hello from skill script')\n",
                    encoding="utf-8",
                )
                placeholder.chmod(0o755)
            else:
                placeholder.write_text("# Example\n\nReplace or delete this file.\n", encoding="utf-8")

    print(f"Created: {skill_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
