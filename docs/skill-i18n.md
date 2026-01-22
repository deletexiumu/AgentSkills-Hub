# Skill i18n Specification

This document defines the multi-language support specification for skills under `skills/public`, ensuring consistency across Chinese, English, and Japanese.

## 1. Frontmatter Description

### 1.1 Format

The `description` field in `SKILL.md` frontmatter must be in **English only** for compatibility with [skills.sh](https://skills.sh) and other tools:

```yaml
---
name: my-skill
description: Describe what this skill does in one sentence. Include key features and supported languages if applicable.
---
```

**Rules**:
- Use English for machine readability and tool compatibility
- Keep it concise (1-2 sentences)
- Include key features and capabilities
- Mention supported languages if multi-language output is supported (e.g., "multi-language output (ZH/EN/JA)")

### 1.2 Examples

```yaml
# Good
description: Multi-source AI news aggregation and digest generation with deduplication, classification, and source tracing. Supports 20+ sources, 5 theme categories, multi-language output (ZH/EN/JA), and image export.

# Good
description: Smart data warehouse Q&A skill - input business requirements + DWH catalog, output executable SQL queries. Features catalog-aware search, multi-dialect support (Hive/SparkSQL/GaussDB).
```

## 2. Invoke Examples Block

### 2.1 Location

After the frontmatter (line 5+), add an invoke examples block with examples in all three languages.

### 2.2 Format

```markdown
<!-- i18n-examples:start -->
## Invoke Examples

### Chinese
- "Use my-skill to perform a task"
- "Use my-skill to generate a result"
- ...

### English
- "Use my-skill to perform a task"
- "Use my-skill to generate a result"
- ...

### Japanese
- "my-skill to execute a task"
- "my-skill to generate a result"
- ...
<!-- i18n-examples:end -->
```

**Rules**:
- Use HTML comments to mark block boundaries (for validation scripts)
- At least 3-4 examples per language
- Examples should cover main use cases

## 3. Output Language Convention

### 3.1 CLI Parameter

All skills that support multi-language output should use the `--lang` parameter:

```
--lang auto|zh|en|ja
```

| Value | Description |
|-------|-------------|
| `auto` | Auto-detect (based on user prompt language) |
| `zh` | Chinese (default) |
| `en` | English |
| `ja` | Japanese |

### 3.2 Default Behavior

- When `--lang` is not specified, default to `zh` (Chinese)
- Backward compatible: existing `--lang zh` / `--lang en` continue to work

### 3.3 Output Content

- Titles, category names, UI text switch based on `--lang`
- Original data (e.g., news titles) in foreign language can be translated to target language
- JSON output preserves `title_raw` / `summary_raw` for traceability

## 4. Natural Language Triggers

Support multi-language time trigger words:

| Chinese | English | Japanese | Offset Days |
|---------|---------|----------|-------------|
| today | today | today | 0 |
| yesterday | yesterday | yesterday | -1 |
| yesterday | - | yesterday | -2 |

## 5. Validation Checklist

Use `scripts/validate_i18n.py` to validate:

1. **Invoke examples block**: SKILL.md first 60 lines contain "Invoke" section
2. **Example count**: At least 3 examples per language (ZH/EN/JA)

```bash
python scripts/validate_i18n.py skills/public/ai-news-digest
python scripts/validate_i18n.py skills/public/smart-data-query
python scripts/validate_i18n.py skills/public/x-ai-digest
```

## 6. Migration Guide

### 6.1 Migrating Existing Skills

1. Update frontmatter description to English only
2. Add invoke examples block before "# Goal" section
3. If CLI exists, extend `--lang` parameter to support `ja`
4. If time parsing exists, add Japanese trigger words
5. Run `validate_i18n.py` to validate

### 6.2 Creating New Skills

Use `scripts/init_skill.py` to create - template already includes i18n skeleton.
