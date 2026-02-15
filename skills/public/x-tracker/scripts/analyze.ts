#!/usr/bin/env bun
/**
 * Content analysis: digest generation, rewrite candidates, and style profiling.
 *
 * Usage:
 *   bun scripts/analyze.ts digest [--date YYYY-MM-DD] [--data-dir /custom/path]
 *   bun scripts/analyze.ts rewrite [--date YYYY-MM-DD] [--top 5] [--data-dir /custom/path]
 *   bun scripts/analyze.ts rewrite --url <x-or-notion-url>
 *   bun scripts/analyze.ts style [--data-dir /custom/path]
 */

import { writeFileSync, existsSync, readFileSync } from "fs";
import { join } from "path";
import { getDataDir, getProjectRoot, parseDataDir, ensureDir, today } from "./config";
import { apiGet } from "./api";
import { readPageContent } from "./notion";

// ==================== Tweet Loading & Scoring ====================

/** Compute engagement score for ranking */
function scoreTweet(t: any): number {
  const m = t.public_metrics;
  if (!m) return 0;
  return (m.like_count || 0) + (m.retweet_count || 0) * 3 + (m.bookmark_count || 0) * 2;
}

/** Get display text: prefer full_text, fall back to text */
function getFullText(t: any): string {
  return t.full_text || t.note_tweet?.text || t.text || "";
}

/** Get tweet type label */
function getTweetTypeLabel(t: any): string {
  const type = t.tweet_type;
  if (!type) return "原创";
  const map: Record<string, string> = {
    "原创": "原创", "转推": "转推", "引用": "引用", "线程": "线程", "回复": "回复",
  };
  return map[type] || type;
}

/** Convert UTC created_at to GMT+8 date string (YYYY-MM-DD) */
function toGMT8Date(createdAt: string): string {
  if (!createdAt) return "";
  const dt = new Date(createdAt);
  // Add 8 hours for GMT+8
  dt.setUTCHours(dt.getUTCHours() + 8);
  return dt.toISOString().split("T")[0];
}


/**
 * Load and flatten tweets from following-tweets and bookmarks, deduped by tweet ID.
 * Filters by date: only keeps tweets posted on dateStr (by created_at),
 * plus newly discovered older tweets not present in previous day's data.
 * Each tweet is annotated with _isToday and _isNew flags.
 * Returns sorted array (highest score first).
 */
function loadScoredTweets(dataDir: string, dateStr: string): any[] {
  const seen = new Map<string, any>();

  // 1. following-tweets
  const ftData = loadJsonSafe(join(dataDir, "following-tweets", `${dateStr}.json`));
  if (ftData?.results) {
    for (const user of ftData.results) {
      for (const tweet of user.tweets || []) {
        if (!seen.has(tweet.id)) {
          seen.set(tweet.id, {
            ...tweet,
            _author: `@${user.username}`,
            _author_name: user.name,
            _source: "following",
          });
        }
      }
    }
  }

  // 2. bookmarks
  const bmData = loadJsonSafe(join(dataDir, "bookmarks", `${dateStr}.json`));
  if (bmData?.bookmarks) {
    for (const tweet of bmData.bookmarks) {
      if (!seen.has(tweet.id)) {
        seen.set(tweet.id, {
          ...tweet,
          _author: tweet.author_username ? `@${tweet.author_username}` : "unknown",
          _author_name: tweet.author_name || tweet.author_username || "unknown",
          _source: "bookmark",
        });
      } else {
        const existing = seen.get(tweet.id)!;
        existing._source = "both";
      }
    }
  }

  // 3. Date filtering: only keep tweets published on dateStr (GMT+8)
  const filtered: any[] = [];
  let replyCount = 0;
  let otherDateCount = 0;
  for (const tweet of seen.values()) {
    const tweetDate = toGMT8Date(tweet.created_at);
    tweet._tweetDate = tweetDate;
    // Skip replies
    if (tweet.tweet_type === "回复" || tweet.in_reply_to_user_id) { replyCount++; continue; }
    // Only keep tweets published on the target date
    if (tweetDate === dateStr) {
      filtered.push(tweet);
    } else {
      otherDateCount++;
    }
  }

  filtered.sort((a, b) => scoreTweet(b) - scoreTweet(a));

  console.log(`过滤: ${seen.size} 条 → ${filtered.length} 条 (发布于 ${dateStr}) | 排除回复 ${replyCount} + 非当日 ${otherDateCount}`);

  return filtered;
}

// ==================== Digest ====================

async function generateDigest(dateStr: string) {
  const dataDir = getDataDir(parseDataDir());
  const digestsDir = join(getProjectRoot(), "digests", dateStr);
  ensureDir(digestsDir);

  console.log(`=== 每日精选总结 (${dateStr}) ===\n`);

  const allTweets = loadScoredTweets(dataDir, dateStr);

  if (allTweets.length === 0) {
    console.log("当日无数据。请先运行 sync 命令同步数据。");
    return;
  }

  const top = allTweets.slice(0, 20);
  const sections: string[] = [];

  // Header
  sections.push(`# X 每日精选 — ${dateStr}\n`);
  sections.push(`> 数据来源：本地同步数据（following-tweets + bookmarks）`);
  sections.push(`> 总推文数：**${allTweets.length}** | 精选 Top **${top.length}**\n`);

  // Categorize top tweets
  const categorized = categorizeContent(top);

  for (const [category, tweets] of Object.entries(categorized)) {
    sections.push(`## ${category}\n`);
    for (const t of tweets as any[]) {
      const m = t.public_metrics;
      const score = scoreTweet(t);
      const typeLabel = getTweetTypeLabel(t);
      const sourceTag = t._source === "both" ? " 📌" : t._source === "bookmark" ? " 🔖" : "";
      const text = getFullText(t).substring(0, 300).replace(/\n/g, " ");

      sections.push(`### ${t._author} | ${typeLabel}${sourceTag}`);
      sections.push(`❤️ ${m?.like_count ?? 0} · 🔄 ${m?.retweet_count ?? 0} · 🔖 ${m?.bookmark_count ?? 0} · 💬 ${m?.reply_count ?? 0} · 📊 ${score}\n`);
      sections.push(`${text}\n`);
    }
  }

  const digest = sections.join("\n");
  const outputPath = join(digestsDir, "digest.md");
  writeFileSync(outputPath, digest);

  // Date distribution for selected tweets
  const digestDateDist: Record<string, number> = {};
  for (const t of top) {
    const d = t._tweetDate || "unknown";
    digestDateDist[d] = (digestDateDist[d] || 0) + 1;
  }

  // Output structured JSON for skill consumption
  const jsonData = {
    date: dateStr,
    generated_at: new Date().toISOString(),
    total_candidates: allTweets.length,
    total_selected: top.length,
    date_distribution: digestDateDist,
    tweets: top.map(t => ({
      id: t.id,
      author: t._author,
      author_name: t._author_name,
      tweet_type: getTweetTypeLabel(t),
      source: t._source,
      tweet_date: t._tweetDate,
      score: scoreTweet(t),
      metrics: t.public_metrics || {},
      text: getFullText(t),
      url: t._author !== "unknown"
        ? `https://x.com/${t._author.replace("@", "")}/status/${t.id}`
        : "",
      category: Object.entries(categorizeContent([t]))[0]?.[0] || "Other",
      thread_context: t.original_tweet?.text || null,
    })),
  };
  const jsonPath = join(digestsDir, "digest.json");
  writeFileSync(jsonPath, JSON.stringify(jsonData, null, 2));

  console.log(`Digest 已保存: ${outputPath}`);
  console.log(`JSON 已保存: ${jsonPath}`);
  console.log(`\n${digest}`);
}

// ==================== Rewrite ====================

async function generateRewrite(dateStr: string, topN: number) {
  const dataDir = getDataDir(parseDataDir());
  const digestsDir = join(getProjectRoot(), "digests", dateStr);
  ensureDir(digestsDir);

  console.log(`=== 优质内容改写候选 (${dateStr}, Top ${topN}) ===\n`);

  const allTweets = loadScoredTweets(dataDir, dateStr);

  if (allTweets.length === 0) {
    console.log("当日无数据。请先运行 sync 命令同步数据。");
    return;
  }

  const top = allTweets.slice(0, topN);

  // Compute date distribution for selected tweets
  const dateDist: Record<string, number> = {};
  for (const t of top) {
    const d = t._tweetDate || "unknown";
    dateDist[d] = (dateDist[d] || 0) + 1;
  }

  // Output structured JSON for sub-agent consumption
  const jsonData = {
    date: dateStr,
    generated_at: new Date().toISOString(),
    total_candidates: allTweets.length,
    selected: top.length,
    date_distribution: dateDist,
    tweets: top.map((t, i) => {
      const fullText = getFullText(t);
      const contentType = detectContentType(fullText);
      const isLinkOnly = /^https?:\/\/\S+$/.test(fullText.trim());
      // Extract expanded URL for link-only tweets
      let expandedUrl: string | null = null;
      if (isLinkOnly && t.entities?.urls?.length > 0) {
        expandedUrl = t.entities.urls[0].expanded_url || t.entities.urls[0].unwound_url || null;
      }
      return {
        rank: i + 1,
        id: t.id,
        author: t._author,
        author_name: t._author_name,
        tweet_type: getTweetTypeLabel(t),
        source: t._source,
        tweet_date: t._tweetDate,
        score: scoreTweet(t),
        metrics: t.public_metrics || {},
        text: fullText,
        is_link_only: isLinkOnly,
        expanded_url: expandedUrl,
        url: t._author !== "unknown"
          ? `https://x.com/${t._author.replace("@", "")}/status/${t.id}`
          : "",
        category: Object.entries(categorizeContent([t]))[0]?.[0] || "Other",
        thread_context: t.original_tweet?.text || null,
        content_type: contentType,
        rewrite_angle: getRewriteAngle(contentType),
      };
    }),
  };
  const jsonPath = join(digestsDir, "rewrite.json");
  writeFileSync(jsonPath, JSON.stringify(jsonData, null, 2));
  console.log(`JSON 已保存: ${jsonPath}`);
  console.log(`共 ${top.length} 条候选，可通过 sub-agent 并行改写`);
}

/** Detect content type for rewrite suggestions */
function detectContentType(text: string): string {
  if (/经验|教程|step|how to|指南|分享/i.test(text)) return "教程/经验分享";
  if (/观点|认为|觉得|think|believe|opinion/i.test(text)) return "观点评论";
  if (/发布|launch|release|announce|introducing|新功能/i.test(text)) return "产品发布";
  if (/research|paper|study|论文|研究/i.test(text)) return "研究解读";
  if (/数据|data|统计|report|调查/i.test(text)) return "数据洞察";
  return "信息分享";
}

/** Suggest rewrite angle based on content type */
function getRewriteAngle(contentType: string): string {
  const angles: Record<string, string> = {
    "教程/经验分享": "提炼关键步骤，加入自己实践经验，降低阅读门槛",
    "观点评论": "引述原观点后加入自己的思考和延伸，提出不同视角或补充",
    "产品发布": "从用户视角解读价值点，对比同类产品，分析适用场景",
    "研究解读": "用通俗语言解释核心发现，补充背景知识，讨论实际影响",
    "数据洞察": "可视化关键数据，结合行业趋势解读，给出可操作建议",
    "信息分享": "提炼核心信息，加入个人见解或使用体验",
  };
  return angles[contentType] || "结合个人经验进行二次创作";
}

// ==================== Rewrite from URL ====================

/** Parse URL and return type + ID */
function parseSourceUrl(url: string): { type: "x"; tweetId: string } | { type: "notion"; pageId: string } | null {
  // X/Twitter link
  const xMatch = url.match(/(?:x\.com|twitter\.com)\/\w+\/status\/(\d+)/);
  if (xMatch) return { type: "x", tweetId: xMatch[1] };

  // Notion link — extract 32-hex page ID
  const notionMatch = url.match(/notion\.so\/.*?([a-f0-9]{32})/);
  if (notionMatch) {
    const raw = notionMatch[1];
    // Format as UUID: 8-4-4-4-12
    const pageId = `${raw.slice(0, 8)}-${raw.slice(8, 12)}-${raw.slice(12, 16)}-${raw.slice(16, 20)}-${raw.slice(20)}`;
    return { type: "notion", pageId };
  }

  return null;
}

async function rewriteFromUrl(url: string) {
  const parsed = parseSourceUrl(url);
  if (!parsed) {
    console.error("无法识别的 URL 格式。支持 X 推文链接和 Notion 页面链接。");
    process.exit(1);
  }

  const dateStr = today();
  const digestsDir = join(getProjectRoot(), "digests", dateStr);
  ensureDir(digestsDir);

  let candidate: any;

  if (parsed.type === "x") {
    console.log(`=== 从 X 推文获取内容 (${parsed.tweetId}) ===\n`);

    const tweetFields = [
      "id", "text", "created_at", "public_metrics",
      "entities", "referenced_tweets", "attachments", "note_tweet",
      "author_id", "conversation_id",
    ].join(",");

    const data = await apiGet(`/tweets/${parsed.tweetId}`, {
      "tweet.fields": tweetFields,
      expansions: "author_id,attachments.media_keys",
      "user.fields": "name,username",
    });

    if (!data?.data) {
      console.error("推文未找到或 API 错误:", JSON.stringify(data));
      process.exit(1);
    }

    const tweet = data.data;
    const author = data.includes?.users?.[0];
    const fullText = tweet.note_tweet?.text || tweet.text || "";
    const contentType = detectContentType(fullText);

    candidate = {
      rank: 1,
      id: tweet.id,
      author: author?.username ? `@${author.username}` : "unknown",
      author_name: author?.name || "unknown",
      tweet_type: "原创",
      source: "url-x",
      tweet_date: tweet.created_at ? toGMT8Date(tweet.created_at) : dateStr,
      score: scoreTweet(tweet),
      metrics: tweet.public_metrics || {},
      text: fullText,
      url,
      content_type: contentType,
      rewrite_angle: getRewriteAngle(contentType),
    };

    console.log(`作者: ${candidate.author} (${candidate.author_name})`);
    console.log(`内容: ${fullText.substring(0, 100)}...`);
  } else {
    console.log(`=== 从 Notion 页面获取内容 (${parsed.pageId}) ===\n`);

    const { title, content } = await readPageContent(parsed.pageId);
    const fullText = content || title;
    const contentType = detectContentType(fullText);

    candidate = {
      rank: 1,
      id: parsed.pageId,
      author: "notion",
      author_name: title || "Notion Page",
      tweet_type: "原创",
      source: "url-notion",
      tweet_date: dateStr,
      score: 0,
      metrics: {},
      text: fullText,
      url,
      content_type: contentType,
      rewrite_angle: getRewriteAngle(contentType),
    };

    console.log(`标题: ${title}`);
    console.log(`内容: ${fullText.substring(0, 100)}...`);
  }

  const jsonData = {
    date: dateStr,
    source_url: url,
    generated_at: new Date().toISOString(),
    total_candidates: 1,
    selected: 1,
    tweets: [candidate],
  };

  const jsonPath = join(digestsDir, "rewrite.json");
  writeFileSync(jsonPath, JSON.stringify(jsonData, null, 2));
  console.log(`\nJSON 已保存: ${jsonPath}`);
}

// ==================== Style Profile ====================

async function generateStyleProfile() {
  const dataDir = getDataDir(parseDataDir());
  const styleDir = join(dataDir, "my-style");
  ensureDir(styleDir);

  console.log("=== Generate Style Profile ===\n");

  // Load all tweets
  const allPath = join(dataDir, "my-tweets", "all.json");
  if (!existsSync(allPath)) {
    console.log("No tweet archive found. Run 'bun scripts/fetch-my-tweets.ts' first.");
    return;
  }

  const data = JSON.parse(readFileSync(allPath, "utf-8"));
  const tweets = (data.tweets || []).filter((t: any) => !t.is_retweet);

  console.log(`Analyzing ${tweets.length} original tweets...\n`);

  if (tweets.length === 0) {
    console.log("No original tweets to analyze.");
    return;
  }

  const profile = {
    generated_at: new Date().toISOString(),
    total_tweets_analyzed: tweets.length,

    // Language distribution
    language: analyzeLanguage(tweets),

    // Tweet length distribution
    length: analyzeLength(tweets),

    // Posting time patterns (by hour, UTC)
    posting_times: analyzePostingTimes(tweets),

    // Top words/phrases
    vocabulary: analyzeVocabulary(tweets),

    // Hashtag usage
    hashtags: analyzeHashtags(tweets),

    // Engagement stats
    engagement: analyzeEngagement(tweets),

    // Content type distribution
    content_types: analyzeContentTypes(tweets),

    // Topic distribution
    topics: categorizeContent(tweets),
  };

  const outputPath = join(styleDir, "style-profile.json");
  writeFileSync(outputPath, JSON.stringify(profile, null, 2));
  console.log(`Style profile saved: ${outputPath}`);

  // Print summary
  console.log("\n--- Style Summary ---\n");
  console.log(`Total original tweets: ${profile.total_tweets_analyzed}`);
  console.log(`Language: ${JSON.stringify(profile.language)}`);
  console.log(`Avg length: ${profile.length.avg_chars} chars`);
  console.log(`Most active hour (UTC): ${profile.posting_times.most_active_hour}:00`);
  console.log(`Top hashtags: ${profile.hashtags.slice(0, 5).map((h: any) => `#${h.tag}(${h.count})`).join(", ")}`);
  console.log(`Avg likes: ${profile.engagement.avg_likes.toFixed(1)}`);
}

// ==================== Analysis Helpers ====================

function analyzeLanguage(tweets: any[]) {
  let chinese = 0, english = 0, mixed = 0;
  for (const t of tweets) {
    const text = t.text || "";
    const hasChinese = /[\u4e00-\u9fff]/.test(text);
    const hasEnglish = /[a-zA-Z]{3,}/.test(text);
    if (hasChinese && hasEnglish) mixed++;
    else if (hasChinese) chinese++;
    else english++;
  }
  return {
    chinese: Math.round((chinese / tweets.length) * 100),
    english: Math.round((english / tweets.length) * 100),
    mixed: Math.round((mixed / tweets.length) * 100),
  };
}

function analyzeLength(tweets: any[]) {
  const lengths = tweets.map((t: any) => (t.text || "").length);
  lengths.sort((a: number, b: number) => a - b);
  return {
    avg_chars: Math.round(lengths.reduce((a: number, b: number) => a + b, 0) / lengths.length),
    median_chars: lengths[Math.floor(lengths.length / 2)],
    min_chars: lengths[0],
    max_chars: lengths[lengths.length - 1],
  };
}

function analyzePostingTimes(tweets: any[]) {
  const hourCounts: Record<number, number> = {};
  for (let h = 0; h < 24; h++) hourCounts[h] = 0;

  for (const t of tweets) {
    if (t.created_at) {
      const hour = new Date(t.created_at).getUTCHours();
      hourCounts[hour]++;
    }
  }

  const mostActiveHour = Object.entries(hourCounts).sort(
    ([, a], [, b]) => (b as number) - (a as number)
  )[0][0];

  return { by_hour: hourCounts, most_active_hour: Number(mostActiveHour) };
}

function analyzeVocabulary(tweets: any[]) {
  const wordCounts: Record<string, number> = {};
  const stopWords = new Set([
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "but", "and", "or",
    "not", "no", "nor", "so", "yet", "both", "either", "neither", "each",
    "every", "all", "any", "few", "more", "most", "other", "some", "such",
    "than", "too", "very", "just", "about", "up", "out", "if", "then",
    "it", "its", "this", "that", "these", "those", "i", "me", "my",
    "you", "your", "he", "she", "we", "they", "them", "his", "her",
    "our", "their", "what", "which", "who", "whom", "how", "when",
    "where", "why", "rt", "https", "http", "co", "amp",
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都",
    "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你",
    "会", "着", "没有", "看", "好", "自己", "这",
  ]);

  for (const t of tweets) {
    const text = (t.text || "").toLowerCase();
    // Split on whitespace and CJK boundaries
    const words = text
      .replace(/https?:\/\/\S+/g, "")
      .replace(/[^\w\u4e00-\u9fff]/g, " ")
      .split(/\s+/)
      .filter((w: string) => w.length >= 2 && !stopWords.has(w));

    for (const w of words) {
      wordCounts[w] = (wordCounts[w] || 0) + 1;
    }
  }

  return Object.entries(wordCounts)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 50)
    .map(([word, count]) => ({ word, count }));
}

function analyzeHashtags(tweets: any[]) {
  const tagCounts: Record<string, number> = {};
  for (const t of tweets) {
    const tags = t.entities?.hashtags || [];
    for (const h of tags) {
      const tag = h.tag?.toLowerCase();
      if (tag) tagCounts[tag] = (tagCounts[tag] || 0) + 1;
    }
  }
  return Object.entries(tagCounts)
    .sort(([, a], [, b]) => b - a)
    .map(([tag, count]) => ({ tag, count }));
}

function analyzeEngagement(tweets: any[]) {
  const metrics = tweets
    .filter((t: any) => t.public_metrics)
    .map((t: any) => t.public_metrics);

  if (metrics.length === 0) {
    return { avg_likes: 0, avg_retweets: 0, avg_replies: 0, total_likes: 0 };
  }

  return {
    avg_likes:
      metrics.reduce((s: number, m: any) => s + (m.like_count || 0), 0) /
      metrics.length,
    avg_retweets:
      metrics.reduce((s: number, m: any) => s + (m.retweet_count || 0), 0) /
      metrics.length,
    avg_replies:
      metrics.reduce((s: number, m: any) => s + (m.reply_count || 0), 0) /
      metrics.length,
    total_likes: metrics.reduce(
      (s: number, m: any) => s + (m.like_count || 0),
      0
    ),
  };
}

function analyzeContentTypes(tweets: any[]) {
  let text_only = 0, with_media = 0, with_links = 0, articles = 0;
  for (const t of tweets) {
    if (t.is_article) articles++;
    else if (t.attachments?.media_keys?.length > 0) with_media++;
    else if (t.entities?.urls?.length > 0) with_links++;
    else text_only++;
  }
  return { text_only, with_media, with_links, articles };
}

/** Simple keyword-based content categorization */
function categorizeContent(items: any[]): Record<string, any[]> {
  const categories: Record<string, RegExp> = {
    "AI/ML": /\b(ai|artificial intelligence|machine learning|llm|gpt|claude|deep learning|neural|transformer|model|training|inference|rag|agent|openai|anthropic|gemini|chatgpt)\b/i,
    Programming: /\b(code|coding|programming|developer|dev|api|javascript|typescript|python|rust|golang|react|vue|next\.?js|node\.?js|github|git|bug|debug|deploy|docker|kubernetes)\b/i,
    Product: /\b(product|launch|feature|app|tool|startup|saas|ship|release|beta|announcement|introducing)\b/i,
    Design: /\b(design|ui|ux|figma|css|layout|animation|typography|color|pixel|responsive|interface)\b/i,
    Business: /\b(business|revenue|growth|market|investor|funding|valuation|profit|strategy|startup|founder|vc|enterprise)\b/i,
    Science: /\b(research|paper|study|experiment|discovery|science|physics|biology|chemistry|arxiv|journal|peer.review)\b/i,
  };

  const result: Record<string, any[]> = {};
  const uncategorized: any[] = [];

  for (const item of items) {
    const text = item.text || "";
    let matched = false;
    for (const [cat, regex] of Object.entries(categories)) {
      if (regex.test(text)) {
        if (!result[cat]) result[cat] = [];
        result[cat].push(item);
        matched = true;
        break; // First match wins
      }
    }
    if (!matched) uncategorized.push(item);
  }

  if (uncategorized.length > 0) {
    result["Other"] = uncategorized;
  }

  return result;
}

function loadJsonSafe(path: string): any | null {
  if (!existsSync(path)) return null;
  return JSON.parse(readFileSync(path, "utf-8"));
}

// ==================== CLI ====================

const command = process.argv[2];
const dateFlag = (() => {
  const idx = process.argv.indexOf("--date");
  return idx !== -1 && process.argv[idx + 1] ? process.argv[idx + 1] : today();
})();
const topFlag = (() => {
  const idx = process.argv.indexOf("--top");
  return idx !== -1 && process.argv[idx + 1] ? parseInt(process.argv[idx + 1], 10) : 10;
})();
const urlFlag = (() => {
  const idx = process.argv.indexOf("--url");
  return idx !== -1 && process.argv[idx + 1] ? process.argv[idx + 1] : null;
})();

switch (command) {
  case "digest":
    await generateDigest(dateFlag);
    break;
  case "rewrite":
    if (urlFlag) {
      await rewriteFromUrl(urlFlag);
    } else {
      await generateRewrite(dateFlag, topFlag);
    }
    break;
  case "style":
    await generateStyleProfile();
    break;
  default:
    console.log("Usage:");
    console.log("  bun scripts/analyze.ts digest [--date YYYY-MM-DD]");
    console.log("  bun scripts/analyze.ts rewrite [--date YYYY-MM-DD] [--top 5]");
    console.log("  bun scripts/analyze.ts rewrite --url <x-or-notion-url>");
    console.log("  bun scripts/analyze.ts style");
    process.exit(1);
}
