# 数据模型与输出规范

本文档定义了 AI 资讯摘要的核心数据结构和输出验收标准。

---

## 1. ArticleItem（单条资讯）

每条资讯条目的 JSON Schema 定义：

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["title", "url", "source_id"],
  "properties": {
    "title": {
      "type": "string",
      "description": "资讯标题（输出语言）"
    },
    "title_raw": {
      "type": "string",
      "description": "原始标题（未翻译）"
    },
    "url": {
      "type": "string",
      "format": "uri",
      "description": "原文链接（必填，用于验证和去重）"
    },
    "source_id": {
      "type": "string",
      "description": "信源 ID（对应 sources.yaml 中的 id）"
    },
    "source_name": {
      "type": "string",
      "description": "信源显示名称"
    },
    "published_at": {
      "type": ["string", "null"],
      "format": "date-time",
      "description": "发布时间（ISO 8601 带时区），无法获取时为 null"
    },
    "summary": {
      "type": "string",
      "description": "摘要内容（输出语言，1-3 句）"
    },
    "summary_raw": {
      "type": "string",
      "description": "原始摘要（未翻译）"
    },
    "topic": {
      "type": "string",
      "enum": ["research", "product", "opensource", "funding", "policy", "other"],
      "description": "主题分类"
    },
    "tags": {
      "type": "array",
      "items": {"type": "string"},
      "description": "标签列表（可选）"
    },
    "mentions": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "source_id": {"type": "string"},
          "source_name": {"type": "string"},
          "url": {"type": "string"}
        }
      },
      "description": "同一资讯在多个信源的提及（去重合并后）"
    },
    "score": {
      "type": "number",
      "description": "排序得分（内部使用）"
    },
    "flags": {
      "type": "array",
      "items": {"type": "string"},
      "description": "标记列表，如：untranslated, date_unknown, paywalled"
    }
  }
}
```

### 最小必填字段（"可验收"输出）

| 字段 | 必填 | 说明 |
|------|------|------|
| title | ✓ | 必须有标题 |
| url | ✓ | 必须有可访问的原文链接 |
| source_id | ✓ | 必须标明来源 |
| published_at | 建议 | 无法获取时设为 null 并添加 `date_unknown` flag |
| summary | 建议 | 无法获取时可为空字符串 |

---

## 2. SourceFailure（信源失败记录）

```json
{
  "type": "object",
  "required": ["source_id", "reason"],
  "properties": {
    "source_id": {
      "type": "string",
      "description": "失败信源的 ID"
    },
    "source_name": {
      "type": "string",
      "description": "失败信源的显示名称"
    },
    "reason": {
      "type": "string",
      "description": "失败原因描述"
    },
    "error_code": {
      "type": "string",
      "description": "错误代码（可选），如：timeout, http_403, parse_error"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "失败时间"
    }
  }
}
```

---

## 3. Digest（完整摘要输出）

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["meta", "sections"],
  "properties": {
    "meta": {
      "type": "object",
      "required": ["generated_at", "time_window", "lang"],
      "properties": {
        "generated_at": {
          "type": "string",
          "format": "date-time",
          "description": "生成时间"
        },
        "time_window": {
          "type": "object",
          "properties": {
            "since": {"type": "string", "format": "date-time"},
            "until": {"type": "string", "format": "date-time"},
            "display": {"type": "string", "description": "显示用文本，如：2026-01-16（今天）"}
          }
        },
        "lang": {
          "type": "string",
          "description": "输出语言代码（zh/en）"
        },
        "timezone": {
          "type": "string",
          "description": "使用的时区"
        },
        "sources_queried": {
          "type": "integer",
          "description": "查询的信源数量"
        },
        "sources_succeeded": {
          "type": "integer",
          "description": "成功获取的信源数量"
        },
        "total_items": {
          "type": "integer",
          "description": "获取的资讯总条数（去重后）"
        }
      }
    },
    "sections": {
      "type": "object",
      "description": "按主题分组的资讯",
      "properties": {
        "research": {
          "type": "array",
          "items": {"$ref": "#/$defs/ArticleItem"},
          "description": "研究/论文/实验室"
        },
        "product": {
          "type": "array",
          "items": {"$ref": "#/$defs/ArticleItem"},
          "description": "产品/模型/发布"
        },
        "opensource": {
          "type": "array",
          "items": {"$ref": "#/$defs/ArticleItem"},
          "description": "开源/工具/工程"
        },
        "funding": {
          "type": "array",
          "items": {"$ref": "#/$defs/ArticleItem"},
          "description": "投融资/商业"
        },
        "policy": {
          "type": "array",
          "items": {"$ref": "#/$defs/ArticleItem"},
          "description": "政策/伦理/安全"
        },
        "other": {
          "type": "array",
          "items": {"$ref": "#/$defs/ArticleItem"},
          "description": "其他/未分类"
        }
      }
    },
    "failures": {
      "type": "array",
      "items": {"$ref": "#/$defs/SourceFailure"},
      "description": "抓取失败的信源列表"
    }
  }
}
```

---

## 4. 验收标准清单

### 必须满足（Must Have）

- [ ] **时间窗口正确**：所有资讯的 `published_at` 都在指定窗口内（或为 null 且有标记）
- [ ] **无重复**：同一 URL 只出现一次（通过 `mentions` 合并多信源）
- [ ] **来源可追溯**：每条资讯都有 `url` 和 `source_id`
- [ ] **输出语言**：默认中文输出；未翻译的条目需标记 `untranslated`

### 应该满足（Should Have）

- [ ] **摘要完整**：每条资讯有 1-3 句摘要
- [ ] **主题分类**：资讯已按主题归类到对应 section
- [ ] **失败报告**：抓取失败的信源在 `failures` 中列出原因

### 可选（Nice to Have）

- [ ] **原文保留**：JSON 输出中保留 `title_raw`/`summary_raw`
- [ ] **标签系统**：有关键词标签
- [ ] **排序得分**：按时间+权重排序

---

## 5. 主题分类定义

| 主题 ID | 中文名称 | 包含内容 |
|---------|----------|----------|
| research | 研究/论文/实验室 | 学术论文、实验室发布、研究成果 |
| product | 产品/模型/发布 | 产品发布、模型更新、功能上线 |
| opensource | 开源/工具/工程 | 开源项目、工具发布、工程实践 |
| funding | 投融资/商业 | 融资新闻、收购、商业合作 |
| policy | 政策/伦理/安全 | 监管政策、AI 伦理、安全研究 |
| other | 其他 | 无法归类到以上主题的内容 |

---

## 6. 示例输出

### JSON 示例

```json
{
  "meta": {
    "generated_at": "2026-01-16T20:00:00+08:00",
    "time_window": {
      "since": "2026-01-16T00:00:00+08:00",
      "until": "2026-01-16T23:59:59+08:00",
      "display": "2026-01-16（今天）"
    },
    "lang": "zh",
    "timezone": "Asia/Shanghai",
    "sources_queried": 10,
    "sources_succeeded": 8,
    "total_items": 15
  },
  "sections": {
    "research": [
      {
        "title": "OpenAI 发布新推理模型 o3",
        "title_raw": "OpenAI Announces New Reasoning Model o3",
        "url": "https://openai.com/blog/o3-announcement",
        "source_id": "openai_blog",
        "source_name": "OpenAI Blog",
        "published_at": "2026-01-16T09:00:00+00:00",
        "summary": "OpenAI 宣布推出新一代推理模型 o3，在数学和编程任务上表现优异。",
        "summary_raw": "OpenAI announces o3, a new reasoning model with improved performance on math and coding tasks.",
        "topic": "research",
        "tags": ["OpenAI", "推理模型", "o3"]
      }
    ],
    "product": [],
    "opensource": [],
    "funding": [],
    "policy": [],
    "other": []
  },
  "failures": [
    {
      "source_id": "theinformation",
      "source_name": "The Information",
      "reason": "需要付费订阅，跳过",
      "error_code": "paywall"
    }
  ]
}
```
