# AI 资讯信源清单（候选）与可用性评估

说明：这里的“可作为输入”指 **能以公开、合规的方式拿到标题/链接/发布时间/摘要等元信息**（RSS/Atom 优先，其次 HTML）。由于离线环境无法在仓库内直接联网验证，本表给出**工程可行性判断 + 风险点**；落地时应对每个站点做一次“可访问性/是否有 RSS/反爬限制”的实测。

## 结论（快速判断）

- **可直接作为输入（优先）**：明显具备 RSS/Atom 或长期可抓取的公开列表页（大部分媒体/博客）。
- **可作为输入但需降级**：页面动态、反爬强、或摘要不稳定 → 建议只用 RSS/标题，或降低抓取频率。
- **不建议作为自动化输入**：明确订阅付费墙或需要登录/强交互（可保留为“人工参考源”）。

## 信源评估表（基于你提供的列表）

> URL 已补全为 `https://`（建议实现时统一 canonicalize）。

| 类别 | 名称 | URL | 可作为输入 | 推荐接入方式 | 主要风险/备注 |
|------|------|-----|-----------|-------------|--------------|
| 学术/研究 | MIT Technology Review (AI) | https://www.technologyreview.com/ai/ | 有条件 | RSS 优先，HTML 兜底 | 可能有付费/反爬；建议只取公开条目标题+摘要 |
| 学术/研究 | BAIR Blog | https://bair.berkeley.edu/blog/ | 是 | RSS/Atom | 通常稳定；需要处理文章发布时间格式 |
| 学术/研究 | OpenAI Blog | https://openai.com/blog | 是 | RSS/Atom | 偶有重定向/语言多样；注意 canonical 链接 |
| 学术/研究 | Anthropic Blog | https://www.anthropic.com/blog | 是 | RSS/Atom | feed 位置需探测；无则 HTML 列表页 |
| 行业新闻 | TechCrunch (AI tag) | https://techcrunch.com/tag/artificial-intelligence/ | 是 | RSS（tag feed） | 反爬/限流可能；RSS 通常最稳 |
| 行业新闻 | Forbes AI | https://www.forbes.com/ai/ | 有条件 | RSS 优先 | 反爬/付费/区域限制可能；不推荐正文抽取 |
| 行业新闻 | The Information (AI) | https://www.theinformation.com/ai | 否（自动化不建议） | N/A | 订阅付费墙；合规起见仅作人工参考 |
| 行业新闻 | AI Magazine | https://aimagazine.com/ | 有条件 | RSS 优先 | 分类页/搜索页结构可能变化；需适配 |
| 社区/数据科学 | KDnuggets | https://www.kdnuggets.com/ | 是 | RSS | 有广告/跳转；取 canonical 链接 |
| 社区/数据科学 | Towards Data Science | https://towardsdatascience.com/ | 是 | RSS（Medium feed） | Medium 可能限流；摘要/正文抽取不稳定，优先 RSS |
| 社区/数据科学 | Hugging Face Blog | https://huggingface.co/blog | 是 | RSS/Atom | 稳定；注意多语言与发布日期 |
| 社区/数据科学 | MarkTechPost | https://www.marktechpost.com/ | 是 | RSS | 内容量大，需关键词/主题过滤 |
| 聚合/新闻 | Artificial Intelligence News | https://www.artificialintelligence-news.com/ | 是 | RSS | 站点结构变化风险一般 |
| 聚合/新闻 | Future Tools News | https://www.futuretools.io/news | 有条件 | HTML/RSS（若有） | 可能强依赖前端渲染；建议优先找 RSS/公开 API |
| 综合媒体 | The Verge (AI) | https://www.theverge.com/ai-artificial-intelligence | 是 | RSS | RSS 一般可用；HTML 反爬较少但需限速 |
| 中文 | 机器之心 | https://www.jiqizhixin.com/ | 有条件 | RSS（若有）/HTML | 可能有反爬与动态加载；建议从公开列表页取元信息 |
| 中文 | 量子位 | https://www.qbitai.com/ | 有条件 | RSS（若有）/HTML | 页面结构变化；建议只抓标题+摘要 |
| 中文 | 雷锋网 AI 频道 | https://www.leiphone.com/category/ai | 有条件 | RSS（若有）/HTML | 可能需处理分页与发布时间抽取 |
| 中文 | 新智元 | https://www.xinzhiyuan.com.cn/ | 有条件 | RSS（若有）/HTML | 反爬/动态；限速与缓存必要 |
| 中文 | 36氪 AI | https://36kr.com/tag/ai | 有条件 | RSS（若有）/HTML | JS 渲染/反爬可能；优先找 RSS 或开放接口 |
| 中文 | 知乎话题：AI科技大本营 | https://www.zhihu.com/topic/19552832 | 否（自动化不建议） | N/A | 通常需要登录/强风控；可作为人工浏览源 |

## RSS/Atom 候选地址（待实测确认）

这些地址是常见站点约定/经验值，用于加速落地时的验证；最终以实测可用为准：

| 名称 | 候选 feed URL（示例） |
|------|------------------------|
| TechCrunch AI tag | https://techcrunch.com/tag/artificial-intelligence/feed/ |
| Towards Data Science | https://towardsdatascience.com/feed |
| The Verge AI | https://www.theverge.com/rss/ai-artificial-intelligence/index.xml |
| OpenAI Blog | https://openai.com/blog/rss.xml |
| Hugging Face Blog | https://huggingface.co/blog/feed.xml |
| MarkTechPost | https://www.marktechpost.com/feed/ |
| Artificial Intelligence News | https://www.artificialintelligence-news.com/feed/ |

## 落地验证清单（建议实现时逐个跑）

对每个站点至少验证：

1. 是否存在 RSS/Atom（页面 `<link rel="alternate" ...>` 或约定 feed URL）
2. 不登录情况下能否获取标题/链接/发布时间
3. 是否有强反爬（频率稍高就 403/验证码/JS 渲染）
4. robots/条款是否允许自动抓取（至少做到“可配置禁用”）
