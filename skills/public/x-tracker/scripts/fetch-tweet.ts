#!/usr/bin/env bun
/**
 * Fetch a single tweet by ID via X API v2.
 * Used for enriching link-only tweets in rewrite workflow.
 *
 * Usage:
 *   bun scripts/fetch-tweet.ts <tweet_id>
 *
 * Output: JSON to stdout with tweet text, entities, and note_tweet (for articles).
 */

import { apiGet } from "./api";

const tweetId = process.argv[2];
if (!tweetId) {
  console.error("Usage: bun scripts/fetch-tweet.ts <tweet_id>");
  process.exit(1);
}

const tweetFields = [
  "id", "text", "created_at", "public_metrics",
  "entities", "referenced_tweets", "attachments", "note_tweet",
  "author_id", "conversation_id",
].join(",");

const data = await apiGet(`/tweets/${tweetId}`, {
  "tweet.fields": tweetFields,
  expansions: "author_id,attachments.media_keys",
  "user.fields": "name,username",
});

if (!data?.data) {
  console.error("Tweet not found or API error:", JSON.stringify(data));
  process.exit(1);
}

const tweet = data.data;
const author = data.includes?.users?.[0];

const result = {
  id: tweet.id,
  text: tweet.note_tweet?.text || tweet.text,
  created_at: tweet.created_at,
  author_name: author?.name,
  author_username: author?.username,
  public_metrics: tweet.public_metrics,
  entities: tweet.entities,
  has_note_tweet: !!tweet.note_tweet,
};

console.log(JSON.stringify(result, null, 2));
