#!/usr/bin/env bun
/**
 * Fetch authenticated user's own tweets for style analysis.
 *
 * Usage:
 *   bun scripts/fetch-my-tweets.ts [--days 30] [--data-dir /custom/path]
 */

import { writeFileSync, existsSync, readFileSync } from "fs";
import { join } from "path";
import { fetchAllPages } from "./api";
import { loadConfig, getDataDir, parseDataDir, ensureDir, today } from "./config";

interface MyTweet {
  id: string;
  text: string;
  created_at?: string;
  public_metrics?: {
    retweet_count: number;
    reply_count: number;
    like_count: number;
    quote_count: number;
  };
  entities?: any;
  referenced_tweets?: any[];
  attachments?: any;
  note_tweet?: any;
  // Derived
  is_retweet?: boolean;
  is_reply?: boolean;
  is_article?: boolean;
}

/** Read since_id from all.json (newest tweet ID) */
function loadSinceId(tweetsDir: string): string | null {
  const allPath = join(tweetsDir, "all.json");
  if (!existsSync(allPath)) return null;
  try {
    const data = JSON.parse(readFileSync(allPath, "utf-8"));
    const tweets = data.tweets || [];
    if (tweets.length === 0) return null;
    // tweets are sorted newest-first by created_at, but ID is the reliable cursor
    // Find the max ID (largest numeric value = newest)
    return tweets.reduce((max: string, t: any) =>
      BigInt(t.id) > BigInt(max) ? t.id : max, tweets[0].id);
  } catch {
    return null;
  }
}

async function fetchMyTweets() {
  const config = loadConfig();
  const dataDir = getDataDir(parseDataDir());
  const tweetsDir = join(dataDir, "my-tweets");
  ensureDir(tweetsDir);

  const days = parseDaysFlag();
  const dateStr = today();
  const sinceId = loadSinceId(tweetsDir);

  console.log(`=== Fetch My Tweets (${dateStr}) ===\n`);
  console.log(`User: @${config.username} (ID: ${config.user_id})`);
  if (sinceId) {
    console.log(`Mode: incremental (since_id: ${sinceId})`);
  } else {
    console.log(`Mode: full (last ${days} days, no previous data)`);
  }
  console.log(`Data dir: ${tweetsDir}\n`);

  const tweetFields = [
    "id", "text", "created_at", "public_metrics",
    "entities", "referenced_tweets", "attachments", "note_tweet",
  ].join(",");

  const params: Record<string, string> = {
    "tweet.fields": tweetFields,
    expansions: "attachments.media_keys,referenced_tweets.id",
    "media.fields": "url,preview_image_url,type,alt_text",
  };

  if (sinceId) {
    // Incremental: only fetch tweets newer than last known
    params.since_id = sinceId;
  } else {
    // First run: use start_time fallback
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - days);
    params.start_time = startDate.toISOString();
  }

  const result = await fetchAllPages(
    `/users/${config.user_id}/tweets`,
    params,
    100
  );

  // Annotate tweets
  const tweets: MyTweet[] = result.data.map((t: any) => ({
    ...t,
    is_retweet: t.referenced_tweets?.some((r: any) => r.type === "retweeted") ?? false,
    is_reply: t.referenced_tweets?.some((r: any) => r.type === "replied_to") ?? false,
    is_article: detectArticle(t),
  }));

  const originalTweets = tweets.filter((t) => !t.is_retweet);
  const retweets = tweets.filter((t) => t.is_retweet);
  const replies = tweets.filter((t) => t.is_reply && !t.is_retweet);
  const articles = tweets.filter((t) => t.is_article);

  console.log(`\nTotal tweets: ${tweets.length}`);
  console.log(`  Original: ${originalTweets.length}`);
  console.log(`  Retweets: ${retweets.length}`);
  console.log(`  Replies: ${replies.length}`);
  console.log(`  Articles: ${articles.length}`);

  // Save daily snapshot
  const snapshotPath = join(tweetsDir, `${dateStr}.json`);
  writeFileSync(
    snapshotPath,
    JSON.stringify(
      {
        date: dateStr,
        period_days: days,
        count: tweets.length,
        stats: {
          original: originalTweets.length,
          retweets: retweets.length,
          replies: replies.length,
          articles: articles.length,
        },
        tweets,
        includes: result.includes,
      },
      null,
      2
    )
  );
  console.log(`\nSnapshot saved: ${snapshotPath}`);

  // Merge into cumulative archive
  mergeIntoAll(tweetsDir, tweets);

  console.log("\nDone.");
}

/** Detect if a tweet is an X Article */
function detectArticle(tweet: any): boolean {
  if (tweet.entities?.urls) {
    return tweet.entities.urls.some(
      (u: any) =>
        u.expanded_url?.includes("/articles/") ||
        u.display_url?.includes("/articles/")
    );
  }
  return false;
}

/** Merge new tweets into all.json (deduplicated by ID) */
function mergeIntoAll(dir: string, newTweets: MyTweet[]) {
  const allPath = join(dir, "all.json");
  let existing: MyTweet[] = [];

  if (existsSync(allPath)) {
    const data = JSON.parse(readFileSync(allPath, "utf-8"));
    existing = data.tweets || [];
  }

  // Merge and deduplicate
  const tweetMap = new Map<string, MyTweet>();
  for (const t of existing) tweetMap.set(t.id, t);
  for (const t of newTweets) tweetMap.set(t.id, t);

  const merged = Array.from(tweetMap.values()).sort((a, b) =>
    (b.created_at ?? "").localeCompare(a.created_at ?? "")
  );

  const newCount = merged.length - existing.length;
  writeFileSync(
    allPath,
    JSON.stringify(
      {
        updated_at: new Date().toISOString(),
        count: merged.length,
        tweets: merged,
      },
      null,
      2
    )
  );
  console.log(
    `Archive updated: ${allPath} (${merged.length} total, +${newCount} new)`
  );
}

function parseDaysFlag(): number {
  const idx = process.argv.indexOf("--days");
  if (idx !== -1 && process.argv[idx + 1]) {
    return parseInt(process.argv[idx + 1], 10) || 30;
  }
  return 30;
}

await fetchMyTweets();
