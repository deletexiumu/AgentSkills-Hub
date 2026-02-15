#!/usr/bin/env bun
/**
 * One-time rebuild: re-fetch all tweets/bookmarks via batch lookup
 * with enriched fields (conversation_id, note_tweet, referenced_tweets),
 * classify, create new Notion DB, push everything.
 *
 * Cost: ~6 API calls (GET /2/tweets?ids=..., 100 IDs each)
 */

import { existsSync, readFileSync, writeFileSync } from "fs";
import { join } from "path";
import { apiGet } from "./api";
import { loadConfig, getDataDir, parseDataDir, ensureDir, today, saveConfig } from "./config";
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
import {
  createXInfoDatabase,
  syncFollowingToNotion,
  syncTweetsToNotion,
  syncBookmarksToNotion,
} from "./notion";

async function main() {
  const config = loadConfig();
  const dataDir = getDataDir(parseDataDir());
  const dateStr = today();

  console.log("=== Rebuild All Data ===\n");
  console.log(`Data dir: ${dataDir}`);
  console.log(`Date: ${dateStr}\n`);

  // --- Step 1: Collect all tweet IDs ---
  console.log("--- Step 1: Collect tweet IDs ---");

  const tweetsDir = join(dataDir, "following-tweets");
  const tweetsPath = join(tweetsDir, `${dateStr}.json`);
  const filteredPath = join(dataDir, "following", "filtered.json");

  const filtered = existsSync(filteredPath)
    ? JSON.parse(readFileSync(filteredPath, "utf-8"))
    : { users: [] };

  // Map tweet ID → user info (for regrouping later)
  const tweetToUser = new Map<
    string,
    { user_id: string; username: string; name: string; followers_count: number }
  >();
  const followingTweetIds: string[] = [];

  if (existsSync(tweetsPath)) {
    const data = JSON.parse(readFileSync(tweetsPath, "utf-8"));
    for (const r of data.results || []) {
      for (const t of r.tweets || []) {
        followingTweetIds.push(t.id);
        tweetToUser.set(t.id, {
          user_id: r.user_id,
          username: r.username,
          name: r.name,
          followers_count: r.followers_count,
        });
      }
    }
  }

  // Bookmarks
  const bookmarksDir = join(dataDir, "bookmarks");
  const bookmarksPath = join(bookmarksDir, "latest.json");
  const bookmarkIdSet = new Set<string>();
  let existingBookmarks: any[] = [];

  if (existsSync(bookmarksPath)) {
    const data = JSON.parse(readFileSync(bookmarksPath, "utf-8"));
    existingBookmarks = data.bookmarks || data.tweets || [];
    for (const b of existingBookmarks) bookmarkIdSet.add(b.id);
  }

  // Combine and deduplicate
  const allIds = [...new Set([...followingTweetIds, ...bookmarkIdSet])];
  console.log(`Following tweets: ${followingTweetIds.length}`);
  console.log(`Bookmarks: ${bookmarkIdSet.size}`);
  console.log(`Unique IDs to fetch: ${allIds.length}`);

  // --- Step 2: Batch lookup with enriched fields ---
  console.log("\n--- Step 2: Batch lookup ---");

  const enrichedMap = new Map<string, any>();
  const allIncludesTweets: any[] = [];
  const allIncludesUsers: any[] = [];

  for (let i = 0; i < allIds.length; i += 100) {
    const chunk = allIds.slice(i, i + 100);
    const batchNum = Math.floor(i / 100) + 1;

    try {
      const json = await apiGet("/tweets", {
        ids: chunk.join(","),
        "tweet.fields": TWEET_FIELDS,
        expansions: TWEET_EXPANSIONS,
        "user.fields": USER_FIELDS,
        "media.fields": MEDIA_FIELDS,
      });

      const fetched = json.data || [];
      for (const t of fetched) enrichedMap.set(t.id, t);
      if (json.includes?.tweets) allIncludesTweets.push(...json.includes.tweets);
      if (json.includes?.users) allIncludesUsers.push(...json.includes.users);

      const missing = chunk.length - fetched.length;
      console.log(
        `  Batch ${batchNum}: ${fetched.length} fetched` +
          (missing > 0 ? ` (${missing} deleted/unavailable)` : "")
      );
    } catch (err: any) {
      console.error(`  Batch ${batchNum} error: ${err.message}`);
    }
  }

  console.log(`  Total enriched: ${enrichedMap.size}`);

  // --- Step 3: Classify ---
  console.log("\n--- Step 3: Classify tweets ---");

  const { tweetsMap: includesTweetsMap, usersMap: includesUsersMap } =
    buildIncludesMaps({ tweets: allIncludesTweets, users: allIncludesUsers });

  // Also add main tweets to includes map for cross-referencing
  for (const [id, t] of enrichedMap) {
    if (!includesTweetsMap.has(id)) includesTweetsMap.set(id, t);
  }

  // Classify following tweets, grouped by user
  const classifiedByUser = new Map<string, EnrichedTweet[]>();
  for (const [tweetId, tweet] of enrichedMap) {
    const userInfo = tweetToUser.get(tweetId);
    if (!userInfo) continue; // bookmark-only tweet

    const classified = classifyTweet(
      tweet,
      userInfo.user_id,
      includesTweetsMap,
      includesUsersMap
    );

    if (!classifiedByUser.has(userInfo.user_id)) {
      classifiedByUser.set(userInfo.user_id, []);
    }
    classifiedByUser.get(userInfo.user_id)!.push(classified);
  }

  // Assign thread positions per user
  for (const [, tweets] of classifiedByUser) {
    assignThreadPositions(tweets);
  }

  // Count types
  const typeCounts: Record<string, number> = { 原创: 0, 长文: 0, 线程: 0, 回复: 0, 引用: 0 };
  let totalClassified = 0;
  for (const [, tweets] of classifiedByUser) {
    for (const t of tweets) {
      typeCounts[t.tweet_type]++;
      totalClassified++;
    }
  }
  console.log(`Following tweets classified: ${totalClassified}`);
  console.log(`  原创: ${typeCounts["原创"]}, 长文: ${typeCounts["长文"]}, 线程: ${typeCounts["线程"]}, 回复: ${typeCounts["回复"]}, 引用: ${typeCounts["引用"]}`);

  // Classify bookmarks
  const classifiedBookmarks: EnrichedTweet[] = [];
  for (const b of existingBookmarks) {
    const enriched = enrichedMap.get(b.id);
    if (!enriched) {
      // Tweet deleted, keep basic info
      classifiedBookmarks.push({
        ...b,
        full_text: b.text || "",
        tweet_type: "原创",
      });
      continue;
    }
    const authorId = enriched.author_id || b.author_id || "";
    const classified = classifyTweet(enriched, authorId, includesTweetsMap, includesUsersMap);
    // Preserve bookmark author info
    classified.author_name = b.author_name || includesUsersMap.get(authorId)?.name;
    classified.author_username = b.author_username || includesUsersMap.get(authorId)?.username;
    classifiedBookmarks.push(classified);
  }
  assignThreadPositions(classifiedBookmarks);

  const bmTypeCounts: Record<string, number> = { 原创: 0, 长文: 0, 线程: 0, 回复: 0, 引用: 0 };
  for (const b of classifiedBookmarks) bmTypeCounts[b.tweet_type]++;
  console.log(`\nBookmarks classified: ${classifiedBookmarks.length}`);
  console.log(`  原创: ${bmTypeCounts["原创"]}, 长文: ${bmTypeCounts["长文"]}, 线程: ${bmTypeCounts["线程"]}, 回复: ${bmTypeCounts["回复"]}, 引用: ${bmTypeCounts["引用"]}`);

  // --- Step 4: Save updated JSON ---
  console.log("\n--- Step 4: Save updated JSON ---");

  // Following tweets
  ensureDir(tweetsDir);
  const results = filtered.users
    .map((u: any) => {
      const tweets = classifiedByUser.get(u.id) || [];
      tweets.sort((a: any, b: any) => (b.created_at ?? "").localeCompare(a.created_at ?? ""));
      return {
        user_id: u.id,
        username: u.username,
        name: u.name,
        followers_count: u.public_metrics?.followers_count || 0,
        tweets,
        latest_tweet_id: tweets[0]?.id || null,
      };
    })
    .filter((r: any) => r.tweets.length > 0);

  const totalTweets = results.reduce((s: number, r: any) => s + r.tweets.length, 0);
  writeFileSync(
    join(tweetsDir, `${dateStr}.json`),
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

  // Update since_ids
  const sinceIds: Record<string, string> = {};
  for (const r of results) {
    if (r.latest_tweet_id) sinceIds[r.user_id] = r.latest_tweet_id;
  }
  writeFileSync(join(tweetsDir, "since_ids.json"), JSON.stringify(sinceIds, null, 2));
  console.log(`  Following tweets: ${totalTweets} saved (${results.length} users)`);

  // Bookmarks
  ensureDir(bookmarksDir);
  const bookmarkData = {
    date: dateStr,
    last_updated: new Date().toISOString(),
    count: classifiedBookmarks.length,
    bookmarks: classifiedBookmarks,
  };
  writeFileSync(join(bookmarksDir, "latest.json"), JSON.stringify(bookmarkData, null, 2));
  writeFileSync(join(bookmarksDir, `${dateStr}.json`), JSON.stringify(bookmarkData, null, 2));
  console.log(`  Bookmarks: ${classifiedBookmarks.length} saved`);

  // --- Step 5: Create new Notion DB ---
  console.log("\n--- Step 5: Create new Notion DB ---");

  // Parent page: 日记 page
  const parentPageId = "27056ff3-93f2-80af-a858-cdad75b3e43c";
  const newDbId = await createXInfoDatabase(parentPageId);
  if (!newDbId) {
    console.error("Failed to create Notion DB. Aborting Notion push.");
    console.log("\nJSON data saved successfully. Run again to retry Notion.");
    return;
  }
  console.log(`  New DB: ${newDbId}`);

  // Update config
  config.notion!.x_info_db_id = newDbId;
  saveConfig(config);
  console.log("  Config updated");

  // --- Step 6: Push to Notion ---
  console.log("\n--- Step 6: Push to Notion ---");

  // 6a: Following
  const followingUsers = filtered.users;
  console.log(`\n  [Following] ${followingUsers.length} users...`);
  try {
    const count = await syncFollowingToNotion(followingUsers);
    console.log(`  -> ${count} pushed`);
  } catch (err: any) {
    console.error(`  -> Error: ${err.message}`);
  }

  // 6b: Tweets (in batches)
  const allTweetsForNotion: { tweet: EnrichedTweet; authorUsername: string }[] = [];
  for (const r of results) {
    for (const t of r.tweets) {
      allTweetsForNotion.push({ tweet: t, authorUsername: r.username });
    }
  }
  console.log(`\n  [Tweets] ${allTweetsForNotion.length} tweets...`);
  let tweetsPushed = 0;
  const BATCH = 50;
  for (let i = 0; i < allTweetsForNotion.length; i += BATCH) {
    const batch = allTweetsForNotion.slice(i, i + BATCH);
    try {
      const count = await syncTweetsToNotion(batch);
      tweetsPushed += count;
      console.log(`  -> Batch ${Math.floor(i / BATCH) + 1}: ${count} pushed (${tweetsPushed} total)`);
    } catch (err: any) {
      console.error(`  -> Batch ${Math.floor(i / BATCH) + 1} error: ${err.message}`);
    }
  }

  // 6c: Bookmarks (in batches)
  console.log(`\n  [Bookmarks] ${classifiedBookmarks.length} bookmarks...`);
  let bmPushed = 0;
  for (let i = 0; i < classifiedBookmarks.length; i += BATCH) {
    const batch = classifiedBookmarks.slice(i, i + BATCH);
    try {
      const count = await syncBookmarksToNotion(batch);
      bmPushed += count;
      console.log(`  -> Batch ${Math.floor(i / BATCH) + 1}: ${count} pushed (${bmPushed} total)`);
    } catch (err: any) {
      console.error(`  -> Batch ${Math.floor(i / BATCH) + 1} error: ${err.message}`);
    }
  }

  // Summary
  console.log("\n--- Summary ---");
  console.log(`Following: ${followingUsers.length}`);
  console.log(`Tweets: ${totalTweets} (${typeCounts["原创"]} 原创, ${typeCounts["长文"]} 长文, ${typeCounts["线程"]} 线程, ${typeCounts["回复"]} 回复, ${typeCounts["引用"]} 引用)`);
  console.log(`Bookmarks: ${classifiedBookmarks.length}`);
  console.log(`Notion DB: ${newDbId}`);
  console.log("Done.");
}

await main();
