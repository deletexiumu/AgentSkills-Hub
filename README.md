# AgentSkills-Hub

A universal agent skill development and management repository: providing specifications, templates, and script tools for quickly creating, validating, and packaging distributable skills.

**[中文](README_zh.md) | [日本語](README_ja.md)**

## Key Features

- **Multi-language Support (ZH/EN/JA)**: All public skills support Chinese, English, and Japanese output
- **Zero-dependency Runtime**: Core functionality works with Python 3.10+ only, no external packages required
- **Graceful Degradation**: Works without LLM/network; optional AI-powered translation
- **Production-ready Templates**: Battle-tested skill templates with i18n support built-in

## Installation

### One-line Install (Recommended)

Install skills directly using [skills.sh](https://skills.sh):

```bash
# Install all skills from this repository
npx skills add deletexiumu/AgentSkills-Hub

# Or install a specific skill
npx skills add deletexiumu/AgentSkills-Hub/ai-news-digest
npx skills add deletexiumu/AgentSkills-Hub/smart-data-query
npx skills add deletexiumu/AgentSkills-Hub/tech-article-creator
```

### Manual Install

```bash
# For Claude Code
mkdir -p ~/.claude/skills
git clone https://github.com/deletexiumu/AgentSkills-Hub.git
cp -R AgentSkills-Hub/skills/public/* ~/.claude/skills/

# For Codex
mkdir -p ~/.codex/skills
cp -R AgentSkills-Hub/skills/public/* ~/.codex/skills/
```

For more details, see: `docs/skill-installation.md`.

---

## Quick Start (Create Your Own Skill)

Create a new skill (example: place it in `skills/public`):

```bash
python3 scripts/init_skill.py my-skill --path skills/public --resources scripts,references,assets
```

Validate and package:

```bash
python3 scripts/validate_skill.py skills/public/my-skill
python3 scripts/validate_i18n.py skills/public/my-skill   # i18n check
python3 scripts/package_skill.py skills/public/my-skill dist
```

For more workflows and specifications, see: `docs/skill-workflow.md`.

---

## Available Skills

### Content & Writing

| Skill | Description | Highlights |
|-------|-------------|------------|
| [`tech-article-creator`](#tech-article-creator) | End-to-end technical article creation pipeline | 9-stage workflow, Agent Team writing, multi-model review, configurable publishing |

### News & Social Media

| Skill | Description | Highlights |
|-------|-------------|------------|
| [`ai-news-digest`](#ai-news-digest) | Multi-source AI news aggregation and digest generation | 20+ sources, auto-dedup, 5 categories, image export |
| [`x-ai-digest`](#x-ai-digest) | X platform AI news scraper with reply suggestions | Browser automation, share card generation |
| [`x-tracker`](#x-tracker) | X following/bookmarks/tweets tracking and archival | Notion sync, content digest, style profiling |

### Data & Operations

| Skill | Description | Highlights |
|-------|-------------|------------|
| [`smart-data-query`](#smart-data-query) | Intelligent data warehouse Q&A with executable SQL output | Auto-iteration, business questionnaire, Q&A logging |
| [`data-inspection-weekly-report`](#data-inspection-weekly-report) | Data processing inspection weekly report generator | YARN/Hive/ES/CK data, auto-upload to Feishu Wiki |
| [`data-issue-handler`](#data-issue-handler) | Data governance issue processing pipeline | Feishu integration, AI analysis, batch review |
| [`app-inspection`](#app-inspection) | Automated web application daily inspection | SMS login, screenshot logs, health checks |

---

## tech-article-creator

> **End-to-end technical article creation: from topic selection to publishing, with multi-version writing and multi-model review.**

A configurable 9-stage pipeline that takes you from topic brainstorming to published articles. Supports parallel Agent Team writing, external model review, and multi-platform publishing — all driven by a single config file.

### Why tech-article-creator?

| Advantage | Description |
|-----------|-------------|
| **9-Stage Pipeline** | Topic → Outline → Materials → Review → Writing → Title → Final Review → Images → Publish |
| **Multi-Version Writing** | Configurable variants (e.g., technical deep-dive + storytelling version) with independent style/audience |
| **Agent Team** | Parallel writing with dedicated writers and reviewers per version |
| **External Review** | Optional multi-model review (any LLM provider) with iterative feedback |
| **Configurable Publishing** | Local-only by default; opt-in to blog, WeChat, social media, or any platform |
| **Zero-Config Start** | Works out of the box with sensible defaults; interactive setup on first use |

### Usage Examples

```
"写一篇技术文章"
"帮我选题"
"评审一下大纲"
"Write a technical tutorial about Docker networking"
"Create an article outline for API design best practices"
```

See: [tech-article-creator/SKILL.md](skills/public/tech-article-creator/SKILL.md) | [tech-article-creator/README.md](skills/public/tech-article-creator/README.md)

---

## ai-news-digest

> **Multi-source AI news aggregation and digest generation with deduplication, classification, and source tracing.**

Automatically fetches news from 20+ AI sources (OpenAI, Anthropic, DeepMind, Google AI, TechCrunch, Hugging Face, etc.), intelligently deduplicates and categorizes, and generates daily briefings in Markdown/JSON/Image format.

### Why ai-news-digest?

| Advantage | Description |
|-----------|-------------|
| **20+ Curated Sources** | OpenAI, Anthropic, DeepMind, Google AI, Meta AI, TechCrunch, Hugging Face, arXiv, and more |
| **Smart Deduplication** | Same news from multiple sources automatically merged with cross-references |
| **5 Theme Categories** | Research / Products / Open Source / Funding / Policy - auto-classified |
| **Multi-language Output** | Chinese, English, Japanese - use `--lang zh/en/ja` |
| **Natural Language Time** | "today", "yesterday", "2026-01-20" - all supported |
| **Zero Dependencies** | Only Python 3.10+ required for core functionality |
| **Multiple Output Formats** | Markdown, JSON, shareable PNG images |
| **Graceful Degradation** | Works without LLM; optional AI translation (Anthropic/OpenAI) |

### Usage Examples

**In Claude Code / Codex conversation:**

```
# Chinese
"Use ai-news-digest to generate today's AI news digest"

# English
"Use ai-news-digest to generate today's AI news in English"

# Japanese
"ai-news-digest で今日のAIニュース要約を日本語で作成して"
```

**CLI:**

```bash
cd skills/public/ai-news-digest/scripts

# Default (Chinese)
python run.py --day today

# English output
python run.py --day yesterday --lang en

# Japanese output
python run.py --day today --lang ja

# Export shareable image
python run.py --day today --format image --image-preset landscape
```

### Installation

```bash
# One-line install (recommended)
npx skills add deletexiumu/AgentSkills-Hub/ai-news-digest

# Or manual install for Claude Code
mkdir -p ~/.claude/skills
cp -R skills/public/ai-news-digest ~/.claude/skills/ai-news-digest
```

See: [ai-news-digest/SKILL.md](skills/public/ai-news-digest/SKILL.md)

---

## smart-data-query

> **Intelligent data warehouse Q&A: input business requirements + DWH catalog, output executable SQL queries.**

Transform natural language business requirements into production-ready SQL queries by intelligently searching your data warehouse catalog.

### Why smart-data-query?

| Advantage | Description |
|-----------|-------------|
| **Catalog-aware** | Builds index from ADS/DWS/DWT tables, DDL, and ETL scripts |
| **Progressive Loading** | Only loads relevant tables, keeps context minimal |
| **Multi-dialect Support** | Hive, SparkSQL, GaussDB - handles syntax differences |
| **Business Questionnaire** | Structured template ensures no requirements missed |
| **Q&A Logging** | Every session logged for iteration and improvement |
| **Auto-iteration** | Bad cases trigger automatic questionnaire optimization |
| **Static Validation** | Checks field existence, join keys, partition pruning |

### Usage Examples

```
# Chinese
"Use smart-data-query: query new users by channel for last 7 days"

# English
"Use smart-data-query: SQL for daily active users by channel"

# Japanese
"smart-data-query：チャネル別DAUを取得するSQLを作成して"
```

See: [smart-data-query/SKILL.md](skills/public/smart-data-query/SKILL.md)

---

## x-ai-digest

> **Scrape AI-related posts from X platform's "For You" feed, generate daily digest with reply suggestions.**

Connects to your logged-in browser, scrapes AI-related posts from X's recommendation feed, and generates structured daily briefings with intelligent reply suggestions.

### Why x-ai-digest?

| Advantage | Description |
|-----------|-------------|
| **Real-time X Content** | Scrapes live "For You" feed, not cached data |
| **AI Topic Filtering** | Smart keyword matching for AI-related content |
| **Reply Suggestions** | AI-generated reply ideas in original language |
| **Share Card Generation** | Beautiful PNG cards for WeChat/social sharing |
| **Browser Integration** | Uses your existing login, no API keys needed |
| **Multi-language Output** | Digest and suggestions in ZH/EN/JA |

### Usage Examples

```
"Use x-ai-digest to scrape today's AI hot topics from X"
"Use x-ai-digest to summarize AI posts from yesterday in English"
"x-ai-digest で今日のAI関連投稿を日本語で要約して"
```

See: [x-ai-digest/SKILL.md](skills/public/x-ai-digest/SKILL.md)

---

## x-tracker

> **Track and archive X (Twitter) following list, bookmarks, and personal tweets with Notion sync.**

Periodically archives your X data to local JSON and syncs to Notion. Generates content digests with ranking, rewrite candidates, and personal writing style profiling.

### Why x-tracker?

| Advantage | Description |
|-----------|-------------|
| **Full Archive** | Following list, bookmarks, and personal tweets |
| **Notion Sync** | Automatic sync to Notion databases |
| **Content Digest** | Daily/weekly curated digest with ranking |
| **Style Profiling** | Analyze your posting patterns and writing style |
| **Rewrite Suggestions** | Identify high-potential tweets for repurposing |

### Usage Examples

```
"Sync my X following list"
"Archive my bookmarks to Notion"
"Generate today's X digest"
"Analyze my posting style"
```

See: [x-tracker/SKILL.md](skills/public/x-tracker/SKILL.md)

---

## data-inspection-weekly-report

> **Data processing inspection weekly report generator with auto-upload to Feishu Wiki.**

Downloads raw inspection data from servers (YARN/Hive/ES/ClickHouse), analyzes metrics, generates a complete weekly report, and uploads to Feishu Wiki.

### Usage Examples

```
"生成第8周的巡检周报"
"Generate this week's data inspection report"
```

See: [data-inspection-weekly-report/SKILL.md](skills/public/data-inspection-weekly-report/SKILL.md)

---

## data-issue-handler

> **Data governance issue processing pipeline: fetch from Feishu → AI analysis → batch review → update back.**

End-to-end data governance workflow: fetches issue lists from Feishu, generates AI-powered analysis and recommendations, supports batch review and approval, then updates results back to Feishu.

### Usage Examples

```
"处理数据治理问题清单"
"Process data governance issues from Feishu"
```

See: [data-issue-handler/SKILL.md](skills/public/data-issue-handler/SKILL.md)

---

## app-inspection

> **Automated web application daily inspection with SMS login and screenshot logging.**

Automates login with credentials and SMS verification, verifies page load time, and captures screenshots as inspection logs.

### Usage Examples

```
"应用巡检"
"Run daily app inspection"
```

See: [app-inspection/SKILL.md](skills/public/app-inspection/SKILL.md)

---

## i18n Specification

All public skills follow the [i18n specification](docs/skill-i18n.md):

- **Frontmatter**: `description: [ZH] 中文；[EN] English；[JA] 日本語`
- **Examples Block**: Invoke examples in all three languages
- **CLI Parameter**: `--lang auto|zh|en|ja`
- **Natural Language**: Time expressions in all languages (today/今天/今日)

Validate i18n compliance:

```bash
python scripts/validate_i18n.py skills/public/ai-news-digest
```

---

## Contributing

1. Fork this repository
2. Create your skill using `scripts/init_skill.py`
3. Follow the i18n specification in `docs/skill-i18n.md`
4. Validate with `validate_skill.py` and `validate_i18n.py`
5. Submit a pull request

## License

MIT
