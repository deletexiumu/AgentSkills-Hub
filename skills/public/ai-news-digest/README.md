# AI 资讯摘要技能 (ai-news-digest)

> **致谢**：本项目受 [ai-daily-skill](https://github.com/geekjourneyx/ai-daily-skill) 启发，感谢该项目在 AI 资讯聚合领域的探索与分享。

从多个 AI 领域信源自动抓取、去重、分类并生成每日资讯简报。

## 功能特性

- **多信源聚合**：支持 20+ 个 AI 领域主流信源（中英文）
- **智能去重**：基于 URL 和标题相似度的双重去重机制
- **主题分类**：自动分类为研究/产品/开源/投融资/政策五大主题
- **时间窗口**：支持自然语言（今天/昨天/前天）和日期格式
- **多格式输出**：Markdown 和 JSON 格式
- **零依赖运行**：仅需 Python 3.10+，无第三方依赖即可运行
- **可选 LLM 翻译**：支持 Anthropic/OpenAI API 进行中文翻译

---

## 快速开始

```bash
# 进入脚本目录
cd skills/public/ai-news-digest/scripts

# 获取今天的 AI 资讯摘要
python run.py --day 今天

# 获取昨天的资讯
python run.py --day yesterday

# 输出为 JSON 格式
python run.py --day 今天 --format json

# 保存到文件
python run.py --day 今天 --out ~/ai-digest-2026-01-16.md

# 详细模式（显示抓取进度）
python run.py --day 今天 --verbose
```

---

## 信源列表

### 英文信源（13 个）

| 信源 | 类型 | 主题 | Feed 状态 |
|------|------|------|-----------|
| **OpenAI Blog** | 官方博客 | 研究、产品 | ✅ RSS |
| **Anthropic Blog** | 官方博客 | 研究、产品、政策 | ✅ RSS (GitHub) |
| **Google DeepMind Blog** | 官方博客 | 研究 | ✅ RSS |
| **BAIR Blog** | 学术博客 | 研究 | ✅ Atom |
| **MIT Technology Review (AI)** | 科技媒体 | 研究、产品、政策 | ✅ RSS |
| **TechCrunch AI** | 科技媒体 | 产品、投融资、开源 | ✅ RSS |
| **The Verge AI** | 科技媒体 | 产品、政策 | ✅ RSS |
| **Ars Technica AI** | 科技媒体 | 产品、研究 | ✅ RSS |
| **Artificial Intelligence News** | 行业媒体 | 产品、研究、投融资 | ✅ RSS |
| **Hugging Face Blog** | 社区博客 | 开源、研究、产品 | ✅ Atom |
| **MarkTechPost** | 技术博客 | 研究、开源 | ✅ RSS |
| **Towards Data Science** | 社区博客 | 研究、开源 | ✅ RSS (Medium) |
| **KDnuggets** | 社区网站 | 研究、开源 | ✅ RSS |

### 中文信源（5 个，需手动配置 feed）

| 信源 | 类型 | 主题 | Feed 状态 |
|------|------|------|-----------|
| **机器之心** | 行业媒体 | 研究、产品、投融资 | ⚠️ 需配置 |
| **量子位** | 行业媒体 | 研究、产品 | ⚠️ 需配置 |
| **雷锋网 AI** | 行业媒体 | 产品、研究、投融资 | ⚠️ 需配置 |
| **新智元** | 行业媒体 | 研究、产品 | ⚠️ 需配置 |
| **36氪 AI** | 行业媒体 | 产品、投融资 | ⚠️ 需配置 |

### 不建议自动抓取（2 个）

| 信源 | 原因 |
|------|------|
| **The Information** | 付费墙 |
| **知乎 AI 话题** | 需登录、强风控 |

---

## CLI 参数说明

```
python run.py [选项]
```

### 时间选项

| 参数 | 说明 | 示例 |
|------|------|------|
| `--day, -d` | 日期（自然语言或 YYYY-MM-DD） | `今天`、`yesterday`、`2026-01-15` |
| `--since` | 起始时间（ISO 8601） | `2026-01-15T00:00:00+08:00` |
| `--until` | 结束时间（ISO 8601） | `2026-01-15T23:59:59+08:00` |
| `--tz` | 时区（默认 Asia/Shanghai） | `UTC+8`、`America/New_York` |

### 输出选项

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--lang, -l` | 输出语言 | `zh` |
| `--format, -f` | 输出格式（markdown/json） | `markdown` |
| `--out, -o` | 输出文件路径 | 标准输出 |

### 过滤选项

| 参数 | 说明 | 示例 |
|------|------|------|
| `--topics, -t` | 主题过滤（逗号分隔） | `research,product` |
| `--sources, -s` | 信源过滤（ID，逗号分隔） | `openai_blog,anthropic_blog` |
| `--max` | 最大条数（默认 20） | `30` |
| `--max-per-topic` | 每主题最大条数（默认 5） | `10` |

### 其他选项

| 参数 | 说明 |
|------|------|
| `--llm` | 启用 LLM 翻译（需配置 API key） |
| `--verbose, -v` | 详细输出模式 |
| `--test` | 运行冒烟测试 |

---

## 信源配置

### 配置文件位置

```
references/sources.yaml
```

### 配置格式

```yaml
sources:
  - id: example_blog          # 唯一标识符（小写下划线）
    name: Example Blog        # 显示名称
    homepage: https://example.com/blog    # 官网首页
    feeds:                    # RSS/Atom 订阅地址列表
      - https://example.com/feed.xml
      - https://example.com/rss         # 备用地址
    lang: en                  # 语言代码 (en/zh)
    topics: [research, product]         # 主题分类
    weight: 8                 # 信源权重（1-10）
    flags: []                 # 特殊标记
```

### 支持的 flags 标记

| 标记 | 说明 |
|------|------|
| `paywall` | 付费墙，不自动抓取 |
| `needs_manual_feed` | 需要手动配置 feed 地址 |
| `anti_bot` | 有反爬机制 |
| `dynamic_page` | 动态页面，需要 JS 渲染 |

### 添加新信源步骤

1. **查找 RSS/Atom feed 地址**
   - 查看网页源码中的 `<link rel="alternate" type="application/rss+xml">`
   - 尝试常见路径：`/feed`、`/rss`、`/feed.xml`、`/rss.xml`
   - 使用 [RSSHub](https://docs.rsshub.app/) 查找第三方 feed

2. **验证 feed 可用性**
   ```bash
   curl -s "https://example.com/feed.xml" | head -20
   ```

3. **添加到 sources.yaml**
   ```yaml
   - id: new_source
     name: New Source Name
     homepage: https://example.com
     feeds:
       - https://example.com/feed.xml
     lang: en
     topics: [research]
     weight: 6
     flags: []
   ```

4. **测试新信源**
   ```bash
   python run.py --sources new_source --verbose
   ```

---

## 主题分类

资讯自动分类为以下主题：

| 主题 ID | 中文名称 | 包含内容 |
|---------|----------|----------|
| `research` | 研究/论文/实验室 | 学术论文、研究成果、实验室发布 |
| `product` | 产品/模型/发布 | 产品发布、模型更新、功能上线 |
| `opensource` | 开源/工具/工程 | 开源项目、工具发布、工程实践 |
| `funding` | 投融资/商业 | 融资新闻、收购、商业合作 |
| `policy` | 政策/伦理/安全 | 监管政策、AI 伦理、安全研究 |
| `other` | 其他 | 无法归类的内容 |

分类基于关键词匹配，详见 `references/topic-keywords.md`。

---

## 目录结构

```
ai-news-digest/
├── SKILL.md              # 技能定义文件
├── README.md             # 本文档
├── scripts/              # 脚本模块
│   ├── run.py            # CLI 入口
│   ├── time_window.py    # 时间窗口解析
│   ├── fetch_feeds.py    # Feed 抓取器
│   ├── parse_feeds.py    # RSS/Atom 解析
│   ├── dedupe.py         # 去重合并
│   ├── classify_rank.py  # 主题分类排序
│   ├── render_digest.py  # 摘要渲染
│   └── summarize_llm.py  # LLM 翻译（可选）
├── references/           # 配置与规范
│   ├── sources.yaml      # 信源注册表
│   ├── sources.md        # 信源评估说明
│   ├── output-spec.md    # 数据模型规范
│   ├── time-window.md    # 时间窗口规范
│   ├── topic-keywords.md # 主题关键词
│   └── translation.md    # 翻译规范
└── assets/               # 模板与资源
    ├── digest-template.md    # Markdown 模板
    └── summarize-prompt.md   # LLM 提示词
```

---

## 依赖说明

### 必需

- Python 3.10+
- 无第三方依赖即可运行

### 可选（增强功能）

| 包 | 用途 | 安装命令 |
|----|------|----------|
| `pyyaml` | 更完整的 YAML 解析 | `pip install pyyaml` |
| `anthropic` | Anthropic Claude 翻译 | `pip install anthropic` |
| `openai` | OpenAI GPT 翻译 | `pip install openai` |

> **注意**：未安装 pyyaml 时，脚本会使用内置的简化 YAML 解析器，可正常加载完整信源列表。

### LLM 翻译配置

```bash
# Anthropic（推荐）
export ANTHROPIC_API_KEY="your-api-key"

# 或 OpenAI
export OPENAI_API_KEY="your-api-key"

# 然后运行时添加 --llm 参数
python run.py --day 今天 --llm
```

---

## 缓存机制

抓取的 feed 内容会缓存在 `~/.cache/ai-news-digest/feeds/` 目录：

- 默认缓存有效期：15 分钟
- 支持 ETag/Last-Modified 条件请求
- 清理缓存：`rm -rf ~/.cache/ai-news-digest/feeds/*.json`

---

## 输出示例

### Markdown 格式

```markdown
# AI 资讯简报（2026-01-16）

> 时间窗口：2026-01-16（今天）
> 语言：中文
> 信源：共 13 个，成功 11 个

## 研究 / 论文 / 实验室

- **Google AI Releases TranslateGemma**（MarkTechPost，2026-01-16 05:39）
  - 链接：https://www.marktechpost.com/...
  - 摘要：Google AI has released TranslateGemma...
  - 标签：AI Paper Summary, Applications

## 产品 / 模型 / 发布

- **Apple lost the AI race**（The Verge AI，2026-01-15 14:00）
  - 链接：https://www.theverge.com/...
  - 摘要：With news that Apple will use Gemini...
  - 标签：AI, Apple, Mobile
```

### JSON 格式

```json
{
  "meta": {
    "generated_at": "2026-01-16T20:00:00+08:00",
    "time_window": {
      "since": "2026-01-16T00:00:00+08:00",
      "until": "2026-01-16T23:59:59+08:00"
    },
    "lang": "zh",
    "total_items": 15
  },
  "sections": {
    "research": [...],
    "product": [...],
    "opensource": [...],
    "funding": [...],
    "policy": []
  },
  "failures": [...]
}
```

---

## 常见问题

### Q: 如何只获取特定主题的资讯？

```bash
python run.py --day 今天 --topics research,opensource
```

### Q: 如何只使用特定信源？

```bash
python run.py --day 今天 --sources openai_blog,anthropic_blog,huggingface_blog
```

### Q: 抓取失败怎么办？

1. 检查网络连接
2. 清理缓存：`rm -rf ~/.cache/ai-news-digest/feeds/*.json`
3. 使用 `--verbose` 查看详细错误信息
4. 检查信源的 feed URL 是否仍然有效

### Q: 如何添加中文信源？

中文信源（如机器之心、量子位）大多没有公开 RSS feed，可以：

1. 使用 [RSSHub](https://docs.rsshub.app/) 提供的第三方 feed
2. 自建 RSS 生成服务
3. 在 `sources.yaml` 中配置找到的 feed 地址

---

## 更新日志

### 2026-01-16

- 初始版本发布
- 支持 20 个 AI 领域信源
- 实现完整的抓取、解析、去重、分类、渲染流程
- 内置简化 YAML 解析器，无需 pyyaml 依赖
- 可选 LLM 翻译功能

---

## 许可证

MIT License
