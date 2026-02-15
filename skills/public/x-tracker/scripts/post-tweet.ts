#!/usr/bin/env bun
/**
 * Post a tweet via X API v2.
 *
 * Usage:
 *   bun scripts/post-tweet.ts "Hello world!"
 *   bun scripts/post-tweet.ts "Great insight!" --quote https://x.com/user/status/123
 *   bun scripts/post-tweet.ts "I agree!" --reply https://x.com/user/status/123
 */

import { existsSync, readFileSync, writeFileSync } from "fs";
import { join } from "path";
import { apiPost } from "./api";
import { loadConfig, getDataDir, parseDataDir, ensureDir } from "./config";

function parseArgs() {
  const args = process.argv.slice(2);
  let text = "";
  let quoteUrl: string | null = null;
  let replyUrl: string | null = null;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--quote" && args[i + 1]) {
      quoteUrl = args[++i];
    } else if (args[i] === "--reply" && args[i + 1]) {
      replyUrl = args[++i];
    } else if (!text) {
      text = args[i];
    }
  }

  return { text, quoteUrl, replyUrl };
}

function extractTweetId(url: string): string | null {
  const m = url.match(/(?:x\.com|twitter\.com)\/\w+\/status\/(\d+)/);
  return m ? m[1] : null;
}

const { text, quoteUrl, replyUrl } = parseArgs();

if (!text) {
  console.error("Usage:");
  console.error('  bun scripts/post-tweet.ts "Hello world!"');
  console.error('  bun scripts/post-tweet.ts "Comment" --quote https://x.com/user/status/123');
  console.error('  bun scripts/post-tweet.ts "Reply" --reply https://x.com/user/status/123');
  process.exit(1);
}

const body: Record<string, any> = { text };

if (quoteUrl) {
  const id = extractTweetId(quoteUrl);
  if (!id) {
    console.error("无法从 URL 提取 tweet ID:", quoteUrl);
    process.exit(1);
  }
  body.quote_tweet_id = id;
  console.log(`引用推文: ${quoteUrl} (ID: ${id})`);
}

if (replyUrl) {
  const id = extractTweetId(replyUrl);
  if (!id) {
    console.error("无法从 URL 提取 tweet ID:", replyUrl);
    process.exit(1);
  }
  body.reply = { in_reply_to_tweet_id: id };
  console.log(`回复推文: ${replyUrl} (ID: ${id})`);
}

console.log(`\n发布内容:\n${text}\n`);

const result = await apiPost("/tweets", body);

if (result?.data?.id) {
  const tweetId = result.data.id;
  console.log(`发布成功!`);
  console.log(`https://x.com/i/status/${tweetId}`);

  // Save to my-tweets/all.json
  const config = loadConfig();
  const dataDir = getDataDir(parseDataDir());
  const tweetsDir = join(dataDir, "my-tweets");
  ensureDir(tweetsDir);

  const newTweet = {
    id: tweetId,
    text,
    created_at: new Date().toISOString(),
    is_retweet: false,
    is_reply: !!replyUrl,
    is_article: false,
    referenced_tweets: quoteUrl
      ? [{ type: "quoted", id: extractTweetId(quoteUrl) }]
      : replyUrl
        ? [{ type: "replied_to", id: extractTweetId(replyUrl) }]
        : undefined,
  };

  const allPath = join(tweetsDir, "all.json");
  let existing: any[] = [];
  if (existsSync(allPath)) {
    const data = JSON.parse(readFileSync(allPath, "utf-8"));
    existing = data.tweets || [];
  }

  // Prepend (newest first), dedupe
  if (!existing.some((t: any) => t.id === tweetId)) {
    existing.unshift(newTweet);
  }

  writeFileSync(allPath, JSON.stringify({
    updated_at: new Date().toISOString(),
    count: existing.length,
    tweets: existing,
  }, null, 2));

  console.log(`已记录到: ${allPath} (共 ${existing.length} 条)`);
} else {
  console.error("发布失败:", JSON.stringify(result, null, 2));
  process.exit(1);
}
