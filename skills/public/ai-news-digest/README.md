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

> 时间窗口：2026-01-16（今天，Asia/Shanghai）
> 信源：13（成功 11）｜条目：11

## 研究 / 论文 / 实验室

- Google 发布 TranslateGemma：基于 Gemma 3 的开源翻译模型家族，支持 55 种语言（MarkTechPost，2026-01-16 13:39）
    - 链接：https://www.marktechpost.com/2026/01/15/google-ai-releases-translategemma-a-new-family-of-open-translation-models-built-on-gemma-3-with-support-for-55-languages/
    - 摘要：介绍 TranslateGemma（4B/12B/27B）作为面向机器翻译的开源模型系列，目标覆盖 55 种语言。文章提到其通过后训练流程强化翻译能力，并强调可在多种硬件环境部署。
- NVIDIA 开源 KVzap：KV Cache 剪枝/压缩方法，宣称近乎无损实现 2–4 倍压缩（MarkTechPost，2026-01-16 05:12）
    - 链接：https://www.marktechpost.com/2026/01/15/nvidia-ai-open-sourced-kvzap-a-sota-kv-cache-pruning-method-that-delivers-near-lossless-2x-4x-compression/
    - 摘要：聚焦长上下文推理中 KV cache 的显存与延迟瓶颈，提出通过剪枝等方式显著压缩缓存体积。核心目标是在效果损失很小的前提下提升可部署性与吞吐。
- OptiMind：一个面向"优化（optimization）"任务的研究模型（Hugging Face Blog，2026-01-16 02:49）
    - 链接：https://huggingface.co/blog/microsoft/optimind
    - 摘要：Hugging Face 博文介绍微软发布的 OptiMind 研究模型，定位为优化类问题相关研究与实验用途（细节以原文为准）。
- OpenAI 一位安全研究负责人加入 Anthropic（The Verge，2026-01-16 02:00）
    - 链接：https://www.theverge.com/ai-artificial-intelligence/862402/openai-safety-lead-model-policy-departs-for-anthropic-alignment-andrea-vallone
    - 摘要：报道 OpenAI 负责"聊天机器人对心理健康/情感依赖等风险信号如何响应"方向的研究负责人离职并加入 Anthropic。反映了行业在模型安全与用户心理风险治理上的持续投入与争议。

## 产品 / 模型 / 发布

- 如何构建"安全的自治事前授权（Prior Authorization）代理"：强调人类在环控制（MarkTechPost，2026-01-16 14:42）
    - 链接：https://www.marktechpost.com/2026/01/15/how-to-build-a-safe-autonomous-prior-authorization-agent-for-healthcare-revenue-cycle-management-with-human-in-the-loop-controls/
    - 摘要：教程式文章展示自治 agent 如何端到端处理医疗 RCM 的事前授权流程（收集材料、提交、跟踪、申诉）。重点强调保守策略与 human-in-the-loop 以降低误判与合规风险。
- Grok 被指"生成未经同意的去衣图像"，当事人起诉（The Verge，2026-01-16 07:33）
    - 链接：https://www.theverge.com/news/863097/ashley-st-clair-elon-musk-grok-undressing-lawsuit
    - 摘要：报道围绕 X 平台聊天机器人 Grok 的"虚拟去衣/性化生成"能力引发的诉讼与安全争议。焦点在于平台是否提供了足够的防滥用机制与未成年人保护。
- "Apple 输了 AI 竞赛？真正的挑战才开始"（The Verge，2026-01-16 03:00）
    - 链接：https://www.theverge.com/tech/861957/google-apple-ai-deal-iphone-gemini
    - 摘要：讨论 Apple Intelligence 推进受挫与引入 Gemini 等合作动向，以及 Apple 在"智能助手能力"与生态产品化之间的权衡。强调竞争不只在模型能力，也在落地体验与长期策略。
- CIO 视角：2026 将更重视 AI 的治理与可度量价值（Artificial Intelligence News，2026-01-16 03:29）
    - 链接：https://www.artificialintelligence-news.com/news/ai-predictions-dominated-the-conversation-in-2025-cios-shift-gears-in-2026/
    - 摘要：认为 2025 的快速上马后，2026 会更强调把 AI 嵌入工作流触发行动，并用可验证指标衡量收益。关注点从"热度/主观体验"转向"治理、成本与真实业务结果"。

## 其他

- 独家电子书：AGI 如何成为影响深远的"阴谋论"（MIT Technology Review，2026-01-16 01:16）
    - 链接：https://www.technologyreview.com/2026/01/15/1131079/exclusive-ebook-how-agi-became-a-consequential-conspiracy-theory/
    - 摘要：订阅者内容，围绕"机器将与人类同等或更聪明"的叙事如何影响产业与公众讨论展开（不绕过付费墙，仅基于公开标题/摘要信息整理）。
- Raspberry Pi 新增 AI 扩展板：8GB 内存用于本地跑生成式模型（The Verge，2026-01-16 01:30）
    - 链接：https://www.theverge.com/news/862748/raspberry-pi-ai-hat-2-gen-ai-ram
    - 摘要：报道 Raspberry Pi 推出可在 Pi 5 上辅助运行本地生成式 AI 的新扩展板，强调内存与算力配置升级。定位是把部分 AI 负载从主 CPU 分离出来以提升整体可用性。
- 当 Shapley 值"失效"时：更稳健的模型可解释性指南（Towards Data Science，2026-01-16 00:30）
    - 链接：https://towardsdatascience.com/when-shapley-values-break-a-guide-to-robust-model-explainability/
    - 摘要：指出 Shapley 值解释在一些场景下可能产生误导，并给出改进思路以获得更可靠的解释结论。适合在特征相关性强、分布漂移等情况下做方法校正参考。
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
