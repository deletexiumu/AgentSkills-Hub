# X 平台帖子抓取实现指南

## 核心抓取逻辑

### 1. 页面元素选择器

```javascript
// 帖子容器
const articles = document.querySelectorAll('article[data-testid="tweet"]');

// 帖子链接（包含 tweet_id）
const statusLink = article.querySelector('a[href*="/status/"]');

// 时间元素
const timeEl = article.querySelector('time');

// 用户名容器
const userNameContainer = article.querySelector('[data-testid="User-Name"]');

// 帖子内容
const contentEl = article.querySelector('[data-testid="tweetText"]');
```

### 2. 数据提取函数

```javascript
function extractPostData(article) {
  // 提取链接和 ID
  const statusLink = article.querySelector('a[href*="/status/"]');
  const tweetUrl = statusLink ? statusLink.href : null;
  const tweetId = tweetUrl ? tweetUrl.match(/status\/(\d+)/)?.[1] : null;

  // 提取时间
  const timeEl = article.querySelector('time');
  const datetime = timeEl ? timeEl.getAttribute('datetime') : null;
  const timeText = timeEl ? timeEl.textContent : null;

  // 提取用户信息
  const userNameContainer = article.querySelector('[data-testid="User-Name"]');
  let username = null;
  let displayName = null;

  if (userNameContainer) {
    const links = userNameContainer.querySelectorAll('a[href^="/"]');
    for (const link of links) {
      const href = link.getAttribute('href');
      if (href && href.match(/^\/[^\/]+$/) && !href.includes('/status/')) {
        username = href.replace('/', '');
        break;
      }
    }
    const spans = userNameContainer.querySelectorAll('span');
    for (const span of spans) {
      const text = span.textContent;
      if (text && !text.startsWith('@') && text.length > 0 && !text.includes('·')) {
        displayName = text;
        break;
      }
    }
  }

  // 提取内容
  const contentEl = article.querySelector('[data-testid="tweetText"]');
  const content = contentEl ? contentEl.textContent : null;

  return {
    tweetId,
    tweetUrl,
    datetime,
    timeText,
    username,
    displayName,
    content
  };
}
```

### 3. 滚动抓取循环

```javascript
const allPosts = new Map();
let scrollCount = 0;
const maxScrolls = 150;
let noNewPostsCount = 0;

// 时间范围（北京时间转 UTC）
const startUTC = new Date("YYYY-MM-DDT16:00:00.000Z").getTime(); // 前一天
const endUTC = new Date("YYYY-MM-DDT15:59:59.999Z").getTime();   // 当天

while (scrollCount < maxScrolls && allPosts.size < 100) {
  // 抓取当前可见帖子
  const posts = await page.evaluate(() => {
    const results = [];
    const articles = document.querySelectorAll('article[data-testid="tweet"]');
    // ... 提取逻辑
    return results;
  });

  let newPostsThisRound = 0;

  for (const post of posts) {
    if (!allPosts.has(post.tweetId)) {
      // 检查时间范围
      if (post.datetime) {
        const postTime = new Date(post.datetime).getTime();
        if (postTime >= startUTC && postTime <= endUTC) {
          allPosts.set(post.tweetId, post);
          newPostsThisRound++;
        }
      }
    }
  }

  if (newPostsThisRound === 0) {
    noNewPostsCount++;
  } else {
    noNewPostsCount = 0;
  }

  scrollCount++;

  // 停止条件
  if (noNewPostsCount >= 10) break;
  if (allPosts.size >= 50 && noNewPostsCount >= 5) break;

  // 滚动
  await page.evaluate(() => window.scrollBy(0, 700));
  await page.waitForTimeout(1200);
}
```

## 时间处理

### UTC 与北京时间转换

X 平台返回的 `datetime` 是 UTC 时间，需要转换为北京时间 (UTC+8)：

```javascript
// UTC 时间转北京时间
function utcToBeijing(utcDatetime) {
  const date = new Date(utcDatetime);
  return new Date(date.getTime() + 8 * 60 * 60 * 1000);
}

// 格式化为 HH:MM
function formatTime(datetime) {
  const beijingTime = utcToBeijing(datetime);
  const hours = String(beijingTime.getUTCHours()).padStart(2, '0');
  const minutes = String(beijingTime.getUTCMinutes()).padStart(2, '0');
  return `${hours}:${minutes}`;
}
```

### 日期范围计算

北京时间某一天对应的 UTC 时间范围：

| 北京时间 | UTC 时间 |
|----------|----------|
| 2026-01-22 00:00:00 | 2026-01-21 16:00:00 |
| 2026-01-22 23:59:59 | 2026-01-22 15:59:59 |

## 错误处理

### 常见问题

1. **页面断开连接**
   - 原因：长时间操作或浏览器关闭
   - 处理：重新连接并从当前位置继续

2. **选择器失效**
   - 原因：X 更新了页面结构
   - 处理：检查并更新选择器

3. **反爬限制**
   - 原因：滚动过快或请求过多
   - 处理：增加等待时间，降低滚动频率

### 降级策略

```javascript
try {
  // 正常抓取
} catch (error) {
  console.log("抓取出错，保存已有数据");
  // 输出已抓取的数据
  const postsArray = Array.from(allPosts.values());
  fs.writeFileSync("tmp/x-posts-partial.json", JSON.stringify(postsArray, null, 2));
}
```

## 性能优化

1. **批量处理**：每次滚动后批量提取，而非逐条请求
2. **去重缓存**：使用 Map 存储已抓取的 tweetId
3. **早停机制**：达到目标数量或连续无新数据时停止
4. **适当等待**：滚动间隔 1-2 秒，避免触发限制
