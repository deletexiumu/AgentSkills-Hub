# tech-article-creator

End-to-end technical article creation pipeline — from topic selection to multi-platform publishing.

## Overview

A configurable 9-stage pipeline that handles the entire lifecycle of technical article creation. Supports multi-version writing (e.g., technical deep-dive + storytelling version), Agent Team parallel writing with iterative review, and optional multi-model external review.

**Key design principle**: zero-config start with sensible defaults. All optional features (external review, image generation, publishing) are opt-in via configuration.

## Pipeline Stages

```
1. Topic Selection    ─→  Scan existing articles + trending topics → recommend 3-5 topics
2. Outline            ─→  Create outline with per-version annotations
3. Material Collection ─→  Parallel subagent collection by theme
4. Outline Review     ─→  External model review (optional, configurable)
5. Writing + Review   ─→  Agent Team: parallel writers + iterative reviewer feedback
5.5 Title Finalization ─→  Generate title candidates → user selects
6. Final Review       ─→  External model final review (optional, configurable)
7. Human Review       ─→  User final approval
8. Illustrations      ─→  Cover + diagrams (optional, configurable)
9. Format & Publish   ─→  Multi-platform publishing (optional, configurable)
```

Stages 4, 6, 8, 9 are **conditional** — they only execute when the corresponding feature is enabled in config.

## Configuration

### Config File Locations

| File | Location | Purpose |
|------|----------|---------|
| `config.yaml` | Skill directory | **Template** with full comments and defaults |
| `.tech-article-creator.yaml` | Article root directory | **Runtime config** (user's actual settings) |

### First-Time Setup

On first use, the skill detects the missing runtime config and guides you through interactive setup:

1. **Article root directory** — where articles are stored
2. **Version strategy** — single / dual (default) / custom
3. **External review** — which LLM models to use (default: none)
4. **Publishing platforms** — local-only (default) / blog / WeChat / social media

Your choices are saved to `.tech-article-creator.yaml`. Edit anytime to adjust.

### Config Sections

| Section | What It Controls | Default |
|---------|-----------------|---------|
| `workspace` | Directory structure, naming template, indexing | Auto-detect, `{index}-{title}` |
| `variants` | Article versions (id, prefix, audience, word count, style) | Dual: blog + wechat |
| `review` | External review models and pass criteria | Disabled (empty) |
| `writing_team` | Parallel/serial mode, reviewer roles | Parallel, 2 reviewers |
| `image` | Image generation skill and types | Disabled |
| `publish` | Publishing platforms and their skills | Local-only |
| `compliance` | Compliance rules file, redaction policy | Redaction enabled |

## File Structure

```
{article_root}/
├── .tech-article-creator.yaml    # Runtime config
├── {topics_dir}/                  # Topic selection files
├── {article_dir}/                 # Per-article directory
│   ├── 大纲.md                    # Outline with version annotations
│   ├── 原始素材/                   # Raw materials + review feedback
│   │   ├── {topic}素材.md
│   │   └── 评审意见-{model}.md
│   ├── {prefix}{title}.md         # One file per version
│   └── {image_dir}/               # Illustrations (if enabled)
```

## Usage

### Full Pipeline

```
"写一篇技术文章"
"Write a technical article about Docker networking"
```

### Jump to Specific Stage

```
"帮我选题"                    → Stage 1: Topic Selection
"评审一下大纲"                → Stage 4: Outline Review
"收集素材"                    → Stage 3: Material Collection
"Review the final draft"     → Stage 6: Final Review
```

## Agent Team (Stage 5)

The writing stage uses an Agent Team for parallel, iterative work:

- **Writers**: One per version, writes according to variant config (style, audience, word count)
- **Reviewers**: Configured via `writing_team.reviewers`, each with a specific focus area
- **Iteration**: Reviewers provide feedback → writers revise → re-review until all pass

If the runtime doesn't support subagents, writing falls back to serial mode automatically.

## Customization Examples

### Single-Version Technical Tutorial

```yaml
variants:
  - id: "tutorial"
    file_prefix: ""
    target_audience: "Developers with 1-3 years experience"
    word_count: "3000-4000"
    style: "Step-by-step tutorial, code-heavy, practical"
```

### Three-Version Strategy

```yaml
variants:
  - id: "deep-dive"
    file_prefix: "[Deep Dive] "
    target_audience: "Senior engineers"
    word_count: "5000-6000"
    style: "Architecture analysis, performance benchmarks, trade-offs"
  - id: "practical"
    file_prefix: "[Hands-On] "
    target_audience: "Mid-level developers"
    word_count: "3000-4000"
    style: "Step-by-step, copy-paste ready, troubleshooting tips"
  - id: "newsletter"
    file_prefix: "[Newsletter] "
    target_audience: "Tech leads, managers"
    word_count: "1500-2000"
    style: "Business impact, key takeaways, decision framework"
```

## References

| File | Content |
|------|---------|
| `references/dual-version-writing-guide.md` | Writing templates, style guides, title formulas |
| `references/material-collection-guide.md` | Parallel collection patterns, quality standards |
| `references/review-prompt-templates.md` | Review prompt templates for any LLM model |

## Installation

```bash
# One-line install
npx skills add deletexiumu/AgentSkills-Hub/tech-article-creator

# Manual install
cp -R tech-article-creator ~/.claude/skills/tech-article-creator
```

## License

MIT
