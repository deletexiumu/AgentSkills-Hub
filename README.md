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
npx skills add deletexiumu/AgentSkills-Hub/x-ai-digest
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

| Skill | Description | Highlights |
|-------|-------------|------------|
| `ai-news-digest` | Multi-source AI news aggregation and digest generation | 20+ sources, auto-dedup, 5 categories, image export |
| `smart-data-query` | Intelligent data warehouse Q&A with executable SQL output | Auto-iteration, business questionnaire, Q&A logging |
| `x-ai-digest` | X platform AI news scraper with reply suggestions | Browser automation, share card generation |

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
# Chinese
"Use x-ai-digest to scrape today's AI hot topics from X"

# English
"Use x-ai-digest to summarize AI posts from yesterday in English"

# Japanese
"x-ai-digest で今日のAI関連投稿を日本語で要約して"
```

See: [x-ai-digest/SKILL.md](skills/public/x-ai-digest/SKILL.md)

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
