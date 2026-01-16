# AgentSkills

通用的 agent skill 开发与管理仓库：提供规范、模板与脚本工具，用于快速创建、校验并打包可分发的 skill。

> **致谢**：`ai-news-digest` 技能受 [ai-daily-skill](https://github.com/geekjourneyx/ai-daily-skill) 启发，感谢该项目在 AI 资讯聚合领域的探索与分享。

## 快速开始

创建一个新 skill（示例：放到 `skills/public`）：

```bash
python3 scripts/init_skill.py my-skill --path skills/public --resources scripts,references,assets
```

校验与打包：

```bash
python3 scripts/validate_skill.py skills/public/my-skill
python3 scripts/package_skill.py skills/public/my-skill dist
```

更多流程与规范见：`docs/skill-workflow.md`。

安装与加载（Claude / Codex）见：`docs/skill-installation.md`。

## 当前包含的 Skills

Public（可分发）：

| Skill | 说明 | 位置 |
|-------|------|------|
| `example-skill` | 示例 skill，用于验证本仓库的 skill 工具链与约束 | `skills/public/example-skill/` |
| `smart-data-query` | 智能问数/数仓问答（基于需求 + 数仓目录 DDL+ETL 产出可执行 SQL；默认 Hive/SparkSQL） | `skills/public/smart-data-query/` |
| `ai-news-digest` | AI 资讯摘要生成器（多信源聚合、去重、分类，输出每日简报） | `skills/public/ai-news-digest/` |

### ai-news-digest

从 20+ 个 AI 领域信源（OpenAI、Anthropic、DeepMind、TechCrunch、Hugging Face 等）自动抓取资讯，智能去重、分类，生成 Markdown/JSON 格式的每日简报。

**特性**：
- 支持自然语言时间窗口（今天/昨天/前天）
- 自动分类为研究/产品/开源/投融资/政策五大主题
- 零依赖运行（仅需 Python 3.10+）
- 可选 LLM 翻译（Anthropic/OpenAI）

**快速使用**：
```bash
cd skills/public/ai-news-digest/scripts
python run.py --day 今天 --verbose
```

详见：[ai-news-digest/README.md](skills/public/ai-news-digest/README.md)

---

Private（内部使用）：
- `skills/private/`：当前无内置 skill（如新增请遵循同样的 `SKILL.md` 规范）
