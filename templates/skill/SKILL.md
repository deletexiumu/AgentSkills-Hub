---
name: my-skill
description: [ZH] 用一句话说明这个 skill 做什么，以及在什么触发语境/任务类型下应该使用它（尽量包含关键词）；[EN] Describe what this skill does in one sentence, and in what context/task type it should be used (include keywords)；[JA] このスキルが何をするか、どのような状況/タスクで使用すべきかを一文で説明（キーワードを含む）
---

<!-- i18n-examples:start -->
## 调用 / Invoke / 呼び出し

### 中文
- "用 my-skill 执行某任务"
- "用 my-skill 生成某结果"
- "用 my-skill 处理某输入"

### English
- "Use my-skill to perform a task"
- "Use my-skill to generate a result"
- "Use my-skill to process an input"

### 日本語
- "my-skill でタスクを実行して"
- "my-skill で結果を生成して"
- "my-skill で入力を処理して"
<!-- i18n-examples:end -->

# 目标

用简短文字说明这个 skill 要帮 agent 交付的最终结果（可量化/可验收）。

# 流程

1. 澄清输入、约束与成功标准。
2. 执行核心步骤（优先复用本 skill 的脚本/参考资料/资产）。
3. 校验结果并输出交付物（包含失败时的回退策略）。

# 护栏

- 未经用户明确确认，不执行破坏性操作（删除、覆盖、不可逆变更等）。
- 对重复/易错/脆弱步骤，优先脚本化以提升确定性。

# 资源

- `scripts/`：放可运行的工具脚本（可参数化、可复用）。
- `references/`：放仅在需要时加载的资料（在本文用相对路径链接）。
- `assets/`：放模板、样式、素材等输出资源。
