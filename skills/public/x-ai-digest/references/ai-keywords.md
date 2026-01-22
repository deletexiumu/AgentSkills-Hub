# AI 关键词列表

用于从抓取的帖子中筛选 AI 相关内容。

## 核心关键词

### 模型与产品

| 类别 | 关键词 |
|------|--------|
| Claude 系列 | `Claude`, `Anthropic`, `Opus`, `Sonnet`, `Haiku` |
| OpenAI 系列 | `GPT`, `ChatGPT`, `OpenAI`, `Codex`, `o1`, `o3` |
| Google 系列 | `Gemini`, `Bard`, `PaLM`, `Imagen`, `Veo` |
| 其他大模型 | `LLM`, `Llama`, `Mistral`, `Qwen`, `GLM`, `DeepSeek`, `Grok` |
| 开源模型 | `Hugging Face`, `GGUF`, `GGML`, `Ollama` |

### 技术术语

| 类别 | 关键词 |
|------|--------|
| 基础技术 | `AI`, `ML`, `deep learning`, `machine learning`, `neural` |
| 模型技术 | `transformer`, `attention`, `fine-tune`, `RLHF`, `DPO` |
| 应用技术 | `RAG`, `embedding`, `vector`, `prompt`, `token`, `context` |
| Agent 技术 | `agent`, `agentic`, `MCP`, `tool use`, `function calling` |

### 开发工具

| 类别 | 关键词 |
|------|--------|
| AI 编程工具 | `Claude Code`, `Cursor`, `Copilot`, `Codeium`, `Windsurf` |
| Agent 框架 | `LangChain`, `LangGraph`, `AutoGen`, `CrewAI` |
| 部署推理 | `vLLM`, `TensorRT`, `ONNX`, `inference` |
| 开发增强 | `skill`, `skills`, `Remotion`, `Ralphy`, `Ralph` |

### 应用领域

| 类别 | 关键词 |
|------|--------|
| 代码生成 | `coding`, `code`, `vibe coding`, `AI 编程` |
| 图像生成 | `Midjourney`, `DALL-E`, `Stable Diffusion`, `Flux` |
| 视频生成 | `Sora`, `Runway`, `Pika`, `Kling` |
| 语音技术 | `TTS`, `ASR`, `Whisper`, `ElevenLabs` |

## 中文关键词

```
AI, 人工智能, 大模型, 智能, 模型, 编程, 提示词,
Agent, 代理, 智能体, 生成式, 多模态
```

## 日文关键词

```
AI, 人工知能, 大規模言語モデル, プロンプト,
エージェント, 生成AI
```

## 筛选逻辑

```javascript
const aiKeywords = [
  // 英文
  'AI', 'Claude', 'GPT', 'LLM', 'Codex', 'agent', 'skill', 'skills',
  'model', 'Gemini', 'OpenAI', 'Anthropic', 'coding', 'code',
  'prompt', 'GLM', 'Grok', 'Cursor', 'Remotion', 'Devin',
  'MCP', 'RAG', 'embedding', 'fine-tune', 'RLHF', 'vibe',
  'Ralphy', 'Ralph', 'Zed', 'Kiro', 'LangChain', 'token',
  'API', 'neural', 'deep learning', 'machine learning',
  'automation', 'chatbot', 'inference',
  // 中文
  '智能', '模型', '编程', '提示词', '大模型', '人工智能'
];

function isAIRelated(post) {
  const content = (post.content || '').toLowerCase();
  const displayName = (post.displayName || '').toLowerCase();

  return aiKeywords.some(kw =>
    content.includes(kw.toLowerCase()) ||
    displayName.includes(kw.toLowerCase())
  );
}
```

## 更新建议

关键词列表需要定期更新，以跟踪：
1. 新发布的 AI 模型和产品
2. 新兴的技术术语
3. 热门的开发工具
4. 行业热点话题
