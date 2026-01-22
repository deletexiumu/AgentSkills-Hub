# 公众号分享卡片生成指南

## 卡片设计规范

### 尺寸
- 卡片宽度：750px
- 高度：自适应内容（通常 1200-1600px）
- 圆角：24px

### 配色方案
- 头部背景：深蓝渐变 `#1a1a2e` → `#16213e`
- 卡片背景：纯白 `#ffffff`
- 主色调：紫蓝渐变 `#667eea` → `#764ba2`

### 话题卡片配色
| 类型 | 边框色 | 背景渐变 | 适用场景 |
|------|--------|----------|----------|
| anthropic | #d97706 | 暖黄色 | Anthropic/Claude 相关 |
| google | #4285f4 | 蓝色 | Google/Gemini 相关 |
| langchain | #00b894 | 绿色 | LangChain/Agent 相关 |
| openai | #7c3aed | 紫色 | OpenAI/GPT 相关 |

## 生成流程

### 1. 准备 HTML 文件

基于模板 `assets/share-card-template.html` 填充数据：

```javascript
const htmlContent = `
<!DOCTYPE html>
<html lang="zh-CN">
...
<div class="card">
  <div class="header">
    <div class="header-top">
      <div class="logo">
        <div class="logo-icon">🤖</div>
        <span class="logo-text">AI 每日简报</span>
      </div>
      <div class="date">${formattedDate}</div>
    </div>
    <div class="title">今日 AI 圈发生了什么？</div>
    <div class="subtitle">X 平台热点精选 · ${postCount} 条 AI 资讯汇总</div>
  </div>

  <div class="content">
    ${sectionsHtml}
  </div>

  <div class="footer">
    ...
  </div>
</div>
...
`;
```

### 2. 生成话题卡片 HTML

```javascript
function generateSectionHtml(topic) {
  return `
    <div class="section">
      <div class="section-header">
        <div class="section-icon ${topic.iconClass}">${topic.icon}</div>
        <div class="section-title">${topic.title}</div>
      </div>
      <div class="topic-card ${topic.cardClass}">
        <div class="topic-title">
          ${topic.topicTitle}
          ${topic.badge ? `<span class="topic-badge ${topic.badgeClass}">${topic.badgeText}</span>` : ''}
        </div>
        <div class="topic-desc">${topic.description}</div>
        <div class="topic-tags">
          ${topic.tags.map(tag => `<span class="tag">${tag}</span>`).join('')}
        </div>
      </div>
    </div>
  `;
}
```

### 3. 截图生成 PNG

```javascript
import { chromium } from "playwright";

async function generateShareCard(htmlPath, outputPath) {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 900, height: 1800 }
  });

  await page.goto(`file://${htmlPath}`);
  await page.waitForTimeout(2000);

  // 只截取 .card 元素
  const card = await page.$('.card');
  if (card) {
    await card.screenshot({
      path: outputPath,
      type: "png"
    });
  }

  await browser.close();
}
```

## 注意事项

1. **字体加载**：使用 Google Fonts 的 Noto Sans SC，需要等待字体加载完成
2. **元素截图**：只截取 `.card` 元素，避免背景渐变
3. **内容控制**：建议 3-4 个热点话题，过多会导致图片过长
4. **Emoji 支持**：系统需要支持 Emoji 渲染

## 话题图标参考

| 话题类型 | 图标 | 图标 class |
|----------|------|------------|
| 最大热点 | 🔥 | fire |
| Google/Gemini | 🚀 | google |
| Agent/框架 | 🔗 | chain |
| OpenAI/代码 | 💻 | code |
| 新功能 | 🆕 | - |
| 工具发布 | 🛠️ | - |
