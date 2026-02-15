#!/usr/bin/env bun
/**
 * Fetch latest tweets from filtered following list.
 * Records since_id per user for incremental fetching.
 * Classifies tweets (原创/长文/线程/回复/引用) with enriched data.
 * Merges into daily file on repeated runs within the same day.
 *
 * Usage:
 *   bun scripts/fetch-following-tweets.ts [--max-per-user 10] [--data-dir /custom/path]
 */

import { existsSync, readFileSync, writeFileSync } from "fs";
import { join } from "path";
import { apiGet } from "./api";
import { getDataDir, parseDataDir, ensureDir, today } from "./config";
import { syncTweetsToNotion } from "./notion";
import {
  classifyTweet,
  buildIncludesMaps,
  assignThreadPositions,
  TWEET_FIELDS,
  TWEET_EXPANSIONS,
  USER_FIELDS,
  MEDIA_FIELDS,
  type EnrichedTweet,
} from "./tweet-utils";

interface UserTweets {
  user_id: string;
  username: string;
  name: string;
  followers_count: number;
  tweets: EnrichedTweet[];
  latest_tweet_id: string | null;
}

async function fetchFollowingTweets() {
  const dataDir = getDataDir(parseDataDir());
  const filteredPath = join(dataDir, "following", "filtered.json");

  if (!existsSync(filteredPath)) {
    console.error("filtered.json not found. Run sync-following.ts and filter first.");
    process.exit(1);
  }

  const filtered = JSON.parse(readFileSync(filteredPath, "utf-8"));
  const users: any[] = filtered.users;
  const maxPerUser = parseMaxFlag();
  const dateStr = today();

  const outDir = join(dataDir, "following-tweets");
  ensureDir(outDir);

  // Load existing since_ids
  const sinceIdsPath = join(outDir, "since_ids.json");
  let sinceIds: Record<string, string> = {};
  if (existsSync(sinceIdsPath)) {
    sinceIds = JSON.parse(readFileSync(sinceIdsPath, "utf-8"));
  }

  // Load existing daily file for merging
  const snapshotPath = join(outDir, `${dateStr}.json`);
  let existingData: Record<string, UserTweets> = {};
  if (existsSync(snapshotPath)) {
    const prev = JSON.parse(readFileSync(snapshotPath, "utf-8"));
    for (const r of prev.results || []) {
      existingData[r.user_id] = r;
    }
  }

  const ts = new Date().toISOString().slice(11, 19);
  console.log(`=== Fetch Following Tweets (${dateStr} ${ts}) ===\n`);
  console.log(`Users: ${users.length}`);
  console.log(`Max per user (new): ${maxPerUser}`);
  console.log(`Data dir: ${outDir}\n`);

  let newTweets = 0;
  let newUsers = 0;
  let errors = 0;
  const newTweetsForNotion: { tweet: EnrichedTweet; authorUsername: string }[] = [];

  for (let i = 0; i < users.length; i++) {
    const u = users[i];
    const progress = `[${i + 1}/${users.length}]`;
    const isNewUser = !sinceIds[u.id];

    if (isNewUser) newUsers++;

    try {
      const params: Record<string, string> = {
        max_results: String(Math.min(maxPerUser, 100)),
        "tweet.fields": TWEET_FIELDS,
        expansions: TWEET_EXPANSIONS,
        "user.fields": USER_FIELDS,
        "media.fields": MEDIA_FIELDS,
        exclude: "replies",
      };

      // Incremental: use since_id for existing users
      const sinceId = sinceIds[u.id];
      if (sinceId) {
        params.since_id = sinceId;
      }

      const json = await apiGet(`/users/${u.id}/tweets`, params);
      const fetchedTweets: any[] = json.data || [];

      // Build includes maps for classification
      const { tweetsMap, usersMap } = buildIncludesMaps(json.includes);

      // Classify fetched tweets
      const classifiedFetched: EnrichedTweet[] = fetchedTweets.map((t) =>
        classifyTweet(t, u.id, tweetsMap, usersMap)
      );

      // Collect new tweets for Notion sync
      for (const t of classifiedFetched) {
        newTweetsForNotion.push({ tweet: t, authorUsername: u.username });
      }

      // Merge with existing daily tweets (deduplicate by tweet id)
      const existingTweets = existingData[u.id]?.tweets || [];
      const tweetMap = new Map<string, EnrichedTweet>();
      for (const t of existingTweets) tweetMap.set(t.id, t);
      for (const t of classifiedFetched) tweetMap.set(t.id, t);
      const mergedTweets = Array.from(tweetMap.values()).sort(
        (a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? "")
      );

      // Assign thread positions on merged set
      assignThreadPositions(mergedTweets);

      // Update since_id to newest tweet
      let latestId: string | null = sinceId || null;
      if (mergedTweets.length > 0) {
        latestId = mergedTweets[0].id;
      }
      if (latestId) {
        sinceIds[u.id] = latestId;
      }

      existingData[u.id] = {
        user_id: u.id,
        username: u.username,
        name: u.name,
        followers_count: u.public_metrics?.followers_count || 0,
        tweets: mergedTweets,
        latest_tweet_id: latestId,
      };

      newTweets += fetchedTweets.length;
      const tag = isNewUser ? " [NEW]" : "";
      const sinceTag = sinceId ? ` (since ${sinceId.slice(-6)})` : "";
      console.log(
        `  ${progress} @${u.username.padEnd(22)} +${fetchedTweets.length} (total: ${mergedTweets.length})${sinceTag}${tag}`
      );
    } catch (err: any) {
      errors++;
      console.error(`  ${progress} @${u.username.padEnd(22)} ERROR: ${err.message}`);
    }
  }

  // Build final results
  const results = users.map((u) => existingData[u.id]).filter(Boolean);
  const totalTweets = results.reduce((s, r) => s + r.tweets.length, 0);

  // Save daily file (merge)
  writeFileSync(
    snapshotPath,
    JSON.stringify(
      {
        date: dateStr,
        last_updated: new Date().toISOString(),
        user_count: results.length,
        total_tweets: totalTweets,
        results,
      },
      null,
      2
    )
  );

  // Save since_ids
  writeFileSync(sinceIdsPath, JSON.stringify(sinceIds, null, 2));

  // Sync new tweets to Notion
  let notionCount = 0;
  if (newTweetsForNotion.length > 0) {
    console.log(`\n--- Notion Sync ---`);
    try {
      notionCount = await syncTweetsToNotion(newTweetsForNotion);
      console.log(`  Notion: ${notionCount} new tweets pushed`);
    } catch (err: any) {
      console.error(`  Notion sync error: ${err.message}`);
    }
  }

  console.log(`\n--- Summary ---`);
  console.log(`Users: ${results.length} (${newUsers} new)`);
  console.log(`New tweets this run: ${newTweets}`);
  console.log(`Total tweets today: ${totalTweets}`);
  console.log(`Notion pushed: ${notionCount}`);
  console.log(`Errors: ${errors}`);
  console.log(`File: ${snapshotPath}`);
  console.log("Done.");
}

function parseMaxFlag(): number {
  const idx = process.argv.indexOf("--max-per-user");
  if (idx !== -1 && process.argv[idx + 1]) {
    return parseInt(process.argv[idx + 1], 10) || 10;
  }
  return 10;
}

await fetchFollowingTweets();
