# AgentSkills-Hub

通用的 agent skill 开发与管理仓库：提供规范、模板与脚本工具，用于快速创建、校验并打包可分发的 skill。

**[English](README.md) | [日本語](README_ja.md)**

## 核心优势

- **多语言支持（中/英/日）**：所有公开 skill 均支持中文、英文、日文输出
- **零依赖运行**：核心功能仅需 Python 3.10+，无需安装第三方包
- **优雅降级**：无 LLM/网络也能工作；可选 AI 翻译增强
- **生产级模板**：经过验证的 skill 模板，内置 i18n 支持

## 安装

### 一键安装（推荐）

使用 [skills.sh](https://skills.sh) 直接安装：

```bash
# 安装本仓库所有 skill
npx skills add deletexiumu/AgentSkills-Hub

# 或安装特定 skill
npx skills add deletexiumu/AgentSkills-Hub/ai-news-digest
npx skills add deletexiumu/AgentSkills-Hub/smart-data-query
npx skills add deletexiumu/AgentSkills-Hub/x-ai-digest
```

### 手动安装

```bash
# Claude Code
mkdir -p ~/.claude/skills
git clone https://github.com/deletexiumu/AgentSkills-Hub.git
cp -R AgentSkills-Hub/skills/public/* ~/.claude/skills/

# Codex
mkdir -p ~/.codex/skills
cp -R AgentSkills-Hub/skills/public/* ~/.codex/skills/
```

详见：`docs/skill-installation.md`。

---

## 快速开始（创建自己的 Skill）

创建一个新 skill（示例：放到 `skills/public`）：

```bash
python3 scripts/init_skill.py my-skill --path skills/public --resources scripts,references,assets
```

校验与打包：

```bash
python3 scripts/validate_skill.py skills/public/my-skill
python3 scripts/validate_i18n.py skills/public/my-skill   # i18n 校验
python3 scripts/package_skill.py skills/public/my-skill dist
```

更多流程与规范见：`docs/skill-workflow.md`。

---

## 当前包含的 Skills

| Skill | 说明 | 亮点 |
|-------|------|------|
| `ai-news-digest` | 多信源 AI 资讯聚合与简报生成 | 20+ 信源、自动去重、5 大分类、图片导出 |
| `smart-data-query` | 智能问数/数仓问答，产出可执行 SQL | 自动迭代、业务问卷、问答日志 |
| `x-ai-digest` | X 平台 AI 资讯抓取与回复建议 | 浏览器自动化、分享卡片生成 |

---

## ai-news-digest

> **多信源 AI 资讯聚合与简报生成，支持自动去重、分类、链接溯源。**

从 20+ 个 AI 领域信源（OpenAI、Anthropic、DeepMind、Google AI、TechCrunch、Hugging Face 等）自动抓取资讯，智能去重、分类，生成 Markdown/JSON/图片格式的每日简报。

### 为什么选择 ai-news-digest？

| 优势 | 说明 |
|------|------|
| **20+ 精选信源** | OpenAI、Anthropic、DeepMind、Google AI、Meta AI、TechCrunch、Hugging Face、arXiv 等 |
| **智能去重** | 多信源相同新闻自动合并，保留交叉引用 |
| **5 大主题分类** | 研究 / 产品 / 开源 / 投融资 / 政策 - 自动分类 |
| **多语言输出** | 中文、英文、日文 - 使用 `--lang zh/en/ja` |
| **自然语言时间** | "今天"、"昨天"、"2026-01-20" - 全部支持 |
| **零依赖** | 核心功能仅需 Python 3.10+ |
| **多种输出格式** | Markdown、JSON、可分享的 PNG 图片 |
| **优雅降级** | 无 LLM 也能工作；可选 AI 翻译（Anthropic/OpenAI） |

### 使用示例

**在 Claude Code / Codex 对话中：**

```
# 中文
"用 ai-news-digest 生成今天的 AI 资讯简报"

# English
"Use ai-news-digest to generate today's AI news in English"

# 日本語
"ai-news-digest で今日のAIニュース要約を日本語で作成して"
```

**命令行：**

```bash
cd skills/public/ai-news-digest/scripts

# 默认（中文）
python run.py --day 今天

# 英文输出
python run.py --day yesterday --lang en

# 日文输出
python run.py --day 今日 --lang ja

# 导出分享图片
python run.py --day 今天 --format image --image-preset landscape
```

### 安装

```bash
# 一键安装（推荐）
npx skills add deletexiumu/AgentSkills-Hub/ai-news-digest

# 或手动安装到 Claude Code
mkdir -p ~/.claude/skills
cp -R skills/public/ai-news-digest ~/.claude/skills/ai-news-digest
```

详见：[ai-news-digest/SKILL.md](skills/public/ai-news-digest/SKILL.md)

---

## smart-data-query

> **智能问数/数仓问答技能：输入业务需求+数仓目录，产出可执行查询 SQL。**

将自然语言业务需求转化为生产级 SQL 查询，通过智能检索数仓目录实现。

### 为什么选择 smart-data-query？

| 优势 | 说明 |
|------|------|
| **目录感知** | 从 ADS/DWS/DWT 表、DDL、ETL 脚本构建索引 |
| **渐进式加载** | 仅加载相关表，保持上下文最小化 |
| **多方言支持** | Hive、SparkSQL、GaussDB - 处理语法差异 |
| **业务问卷** | 结构化模板确保需求不遗漏 |
| **问答日志** | 每次会话记录，便于迭代改进 |
| **自动迭代** | Bad case 触发问卷模板自动优化 |
| **静态校验** | 检查字段存在性、join key、分区裁剪 |

### 使用示例

```
# 中文
"用 smart-data-query：查最近7天各渠道新增用户数"

# English
"Use smart-data-query: SQL for daily active users by channel"

# 日本語
"smart-data-query：チャネル別DAUを取得するSQLを作成して"
```

详见：[smart-data-query/SKILL.md](skills/public/smart-data-query/SKILL.md)

---

## x-ai-digest

> **从 X 平台主页「为你推荐」栏目抓取 AI 相关资讯，生成每日简报并提供回复建议。**

连接到已登录的浏览器，从 X 的推荐栏目抓取 AI 相关帖子，生成结构化每日简报并提供智能回复建议。

### 为什么选择 x-ai-digest？

| 优势 | 说明 |
|------|------|
| **实时 X 内容** | 抓取实时「为你推荐」，非缓存数据 |
| **AI 话题过滤** | 智能关键词匹配 AI 相关内容 |
| **回复建议** | AI 生成的回复思路，使用原帖语言 |
| **分享卡片生成** | 精美 PNG 卡片，适合微信/社交分享 |
| **浏览器集成** | 使用现有登录，无需 API 密钥 |
| **多语言输出** | 简报和建议支持中/英/日 |

### 使用示例

```
# 中文
"用 x-ai-digest 抓取今天的 AI 热点"

# English
"Use x-ai-digest to summarize AI posts from yesterday in English"

# 日本語
"x-ai-digest で今日のAI関連投稿を日本語で要約して"
```

详见：[x-ai-digest/SKILL.md](skills/public/x-ai-digest/SKILL.md)

---

## i18n 规范

所有公开 skill 遵循 [i18n 规范](docs/skill-i18n.md)：

- **Frontmatter**：`description: [ZH] 中文；[EN] English；[JA] 日本語`
- **调用示例区块**：三语调用示例
- **CLI 参数**：`--lang auto|zh|en|ja`
- **自然语言**：三语时间表达（today/今天/今日）

校验 i18n 合规性：

```bash
python scripts/validate_i18n.py skills/public/ai-news-digest
```

---

## 贡献指南

1. Fork 本仓库
2. 使用 `scripts/init_skill.py` 创建 skill
3. 遵循 `docs/skill-i18n.md` 中的 i18n 规范
4. 使用 `validate_skill.py` 和 `validate_i18n.py` 校验
5. 提交 Pull Request

## 许可证

MIT
