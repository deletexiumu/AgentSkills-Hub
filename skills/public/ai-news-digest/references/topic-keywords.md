# 主题分类关键词

用于基于关键词的主题分类。匹配规则：不区分大小写，支持中英文。

---

## research - 研究/论文/实验室

学术论文、研究成果、实验室发布

### 关键词（优先级高 → 低）

**强指示词（高权重）：**
- paper, research, study, arxiv, preprint
- 论文, 研究, 学术, 实验
- benchmark, evaluation, sota, state-of-the-art
- neural, transformer, attention, diffusion
- training, fine-tuning, pre-training

**实验室/机构名：**
- openai, anthropic, deepmind, google brain, meta ai, microsoft research
- stanford, berkeley, mit, cmu, harvard
- 清华, 北大, 中科院, 上交

**研究领域：**
- nlp, natural language, computer vision, cv
- reinforcement learning, rl, rlhf
- multimodal, vision-language, vlm
- reasoning, chain-of-thought, cot

---

## product - 产品/模型/发布

产品发布、模型更新、功能上线

### 关键词

**强指示词：**
- launch, release, announce, introduce, unveil
- 发布, 上线, 推出, 更新, 升级
- api, sdk, platform, service
- gpt-4, gpt-5, claude, gemini, llama
- chatgpt, copilot, bard

**产品类型：**
- assistant, chatbot, agent
- 助手, 机器人, 智能体
- app, application, tool, plugin

**功能更新：**
- feature, capability, improvement
- 功能, 能力, 改进, 优化

---

## opensource - 开源/工具/工程

开源项目、工具发布、工程实践

### 关键词

**强指示词：**
- open source, opensource, open-source
- 开源, 开放源代码
- github, gitlab, huggingface
- repository, repo, library, framework
- mit license, apache license

**工具/框架：**
- pytorch, tensorflow, jax
- langchain, llamaindex, autogen
- vllm, ollama, llama.cpp
- docker, kubernetes, k8s

**工程实践：**
- tutorial, guide, how-to
- 教程, 指南, 实践
- deployment, inference, serving
- 部署, 推理, 优化

---

## funding - 投融资/商业

融资新闻、收购、商业合作

### 关键词

**强指示词：**
- funding, investment, raise, series a/b/c
- 融资, 投资, 募资, 轮
- valuation, billion, million
- 估值, 亿, 万
- acquisition, acquire, merge
- 收购, 并购, 合并

**商业活动：**
- partnership, collaborate, deal
- 合作, 战略, 协议
- ipo, public, stock
- 上市, 股票

**公司/投资者：**
- startup, unicorn
- 创业, 独角兽
- vc, venture capital
- 风投, 资本

---

## policy - 政策/伦理/安全

监管政策、AI 伦理、安全研究

### 关键词

**强指示词：**
- regulation, policy, law, legislation
- 监管, 政策, 法规, 立法
- safety, security, alignment
- 安全, 对齐, 可信
- ethics, ethical, responsible
- 伦理, 道德, 负责任

**机构/组织：**
- eu, european union, congress, senate
- 欧盟, 国会, 政府, 工信部
- fda, ftc, sec

**议题：**
- bias, fairness, discrimination
- 偏见, 公平, 歧视
- privacy, copyright, intellectual property
- 隐私, 版权, 知识产权
- deepfake, misinformation
- 深度伪造, 虚假信息
- existential risk, x-risk, agi safety
- 生存风险, AGI 安全

---

## 分类规则

1. 计算每个主题的匹配分数
2. 强指示词权重 = 3，普通关键词权重 = 1
3. 取分数最高的主题；如果最高分 < 阈值（默认 2），归类为 "other"
4. 可配置排除/包含关键词来覆盖默认规则
