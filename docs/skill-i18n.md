# Skill 多语言（i18n）规范

本文档定义 `skills/public` 下 skill 的多语言支持规范，确保中文、英文、日文三语一致性。

## 1. Frontmatter Description 规范

### 1.1 单行写法

在 `SKILL.md` 的 frontmatter 中，`description` 字段使用 `[ZH]/[EN]/[JA]` 标记区分不同语言版本：

```yaml
---
name: my-skill
description: [ZH] 中文描述；[EN] English description；[JA] 日本語の説明
---
```

**规则**：
- 三语版本用分号（`；`）分隔
- 每段以 `[ZH]`、`[EN]`、`[JA]` 开头
- 中文版本放在最前面（向后兼容）
- 单行不换行，保持 YAML 解析兼容性

### 1.2 示例

```yaml
description: [ZH] 多信源 AI 资讯聚合与简报生成，支持自动去重、分类、链接溯源；[EN] Multi-source AI news aggregation and digest generation with deduplication, classification, and source tracing；[JA] 複数ソースからのAIニュース収集と要約生成、重複排除・分類・出典追跡機能付き
```

## 2. 调用示例区块规范

### 2.1 位置

在 `SKILL.md` 的 frontmatter 结束后（第 5 行之后），紧跟"调用 / Invoke / 呼び出し"示例区块。

### 2.2 格式

```markdown
<!-- i18n-examples:start -->
## 调用 / Invoke / 呼び出し

### 中文
- "用 {skill-name} 生成今天的 AI 资讯简报"
- "用 {skill-name} 获取昨天的新闻"
- ...

### English
- "Use {skill-name} to generate today's AI news digest"
- "Use {skill-name} to get yesterday's news"
- ...

### 日本語
- "{skill-name} で今日のAIニュース要約を生成して"
- "{skill-name} で昨日のニュースを取得して"
- ...
<!-- i18n-examples:end -->
```

**规则**：
- 使用 HTML 注释标记区块边界（便于校验脚本识别）
- 每种语言至少 3-4 条示例
- 示例应覆盖主要使用场景

## 3. 输出语言约定

### 3.1 CLI 参数

所有支持多语言输出的 skill，统一使用 `--lang` 参数：

```
--lang auto|zh|en|ja
```

| 值 | 说明 |
|---|---|
| `auto` | 自动检测（根据用户提示词语言） |
| `zh` | 中文（默认） |
| `en` | English |
| `ja` | 日本語 |

### 3.2 默认行为

- 未指定 `--lang` 时，默认 `zh`（中文）
- 向后兼容：现有 `--lang zh` / `--lang en` 继续可用

### 3.3 输出内容

- 标题、分类名、UI 文案根据 `--lang` 切换
- 原始数据（如新闻标题）若为外语，可翻译为目标语言
- JSON 输出中保留 `title_raw` / `summary_raw` 等原始字段

## 4. 自然语言触发词

支持多语言的时间触发词：

| 中文 | English | 日本語 | 偏移天数 |
|------|---------|--------|----------|
| 今天 | today | 今日/きょう | 0 |
| 昨天 | yesterday | 昨日/きのう | -1 |
| 前天 | - | 一昨日/おととい | -2 |

## 5. 校验清单

使用 `scripts/validate_i18n.py` 校验以下项：

1. **frontmatter description**：包含 `[ZH]`、`[EN]`、`[JA]` 三个标记
2. **调用示例区块**：SKILL.md 前 60 行存在"调用/Invoke/呼び出し"区块
3. **示例数量**：中/英/日示例各 >= 3 条

```bash
python scripts/validate_i18n.py skills/public/ai-news-digest
python scripts/validate_i18n.py skills/public/smart-data-query
python scripts/validate_i18n.py skills/public/x-ai-digest
```

## 6. 迁移指南

### 6.1 现有 skill 迁移步骤

1. 更新 frontmatter description，添加 `[ZH]/[EN]/[JA]` 标记
2. 在"# 目标"之前添加调用示例区块
3. 若有 CLI，扩展 `--lang` 参数支持 `ja`
4. 若有时间解析，添加日语触发词
5. 运行 `validate_i18n.py` 校验

### 6.2 新建 skill

使用 `scripts/init_skill.py` 创建时，模板已包含 i18n 骨架。
