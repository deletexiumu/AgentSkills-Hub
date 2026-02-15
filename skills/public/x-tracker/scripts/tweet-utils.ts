/**
 * Shared tweet classification and enrichment utilities.
 */

export interface OriginalTweet {
  id: string;
  text: string;
  author_id: string;
  author_username: string;
}

export interface EnrichedTweet {
  id: string;
  text: string;
  full_text: string;
  created_at?: string;
  author_id?: string;
  in_reply_to_user_id?: string;
  public_metrics?: any;
  entities?: any;
  referenced_tweets?: any[];
  note_tweet?: any;
  conversation_id?: string;
  attachments?: any;
  tweet_type: "原创" | "长文" | "线程" | "回复" | "引用";
  original_tweet?: OriginalTweet;
  thread_position?: number;
  // bookmark-specific
  author_name?: string;
  author_username?: string;
}

/** Standard tweet.fields for all fetch requests */
export const TWEET_FIELDS =
  "id,text,created_at,public_metrics,entities,referenced_tweets,note_tweet,conversation_id,author_id,in_reply_to_user_id";

/** Standard expansions for all fetch requests */
export const TWEET_EXPANSIONS =
  "referenced_tweets.id,referenced_tweets.id.author_id,author_id,attachments.media_keys";

/** Standard user.fields */
export const USER_FIELDS = "id,username,name";

/** Standard media.fields */
export const MEDIA_FIELDS = "url,preview_image_url,type";

/**
 * Build lookup maps from API response includes.
 */
export function buildIncludesMaps(includes: any): {
  tweetsMap: Map<string, any>;
  usersMap: Map<string, any>;
} {
  const tweetsMap = new Map<string, any>();
  const usersMap = new Map<string, any>();

  if (includes?.tweets) {
    for (const t of includes.tweets) {
      tweetsMap.set(t.id, t);
    }
  }
  if (includes?.users) {
    for (const u of includes.users) {
      usersMap.set(u.id, u);
    }
  }
  return { tweetsMap, usersMap };
}

/**
 * Classify a single tweet based on referenced_tweets, note_tweet, etc.
 *
 * @param tweet       - raw tweet object from API
 * @param authorId    - the tweet author's user ID (for self-reply detection)
 * @param includesTweetsMap - map of referenced tweet ID → tweet object
 * @param includesUsersMap  - map of user ID → user object
 */
export function classifyTweet(
  tweet: any,
  authorId: string,
  includesTweetsMap: Map<string, any>,
  includesUsersMap: Map<string, any>
): EnrichedTweet {
  const fullText = tweet.note_tweet?.text || tweet.text || "";
  const refs = tweet.referenced_tweets || [];
  const repliedTo = refs.find((r: any) => r.type === "replied_to");
  const quoted = refs.find((r: any) => r.type === "quoted");

  let tweetType: EnrichedTweet["tweet_type"];
  let originalTweet: OriginalTweet | undefined;

  if (repliedTo) {
    // Determine if self-reply (thread) or reply to someone else
    const replyToUserId = tweet.in_reply_to_user_id;
    const parentTweet = includesTweetsMap.get(repliedTo.id);
    const isSelfReply = replyToUserId
      ? replyToUserId === authorId
      : parentTweet?.author_id === authorId;

    tweetType = isSelfReply ? "线程" : "回复";

    const parentAuthorId = replyToUserId || parentTweet?.author_id || "";
    const parentAuthor = includesUsersMap.get(parentAuthorId);
    originalTweet = {
      id: repliedTo.id,
      text: (parentTweet?.note_tweet?.text || parentTweet?.text || "").substring(0, 2000),
      author_id: parentAuthorId,
      author_username: parentAuthor?.username || "",
    };
  } else if (quoted) {
    tweetType = "引用";
    const quotedTweet = includesTweetsMap.get(quoted.id);
    const quotedAuthorId = quotedTweet?.author_id || "";
    const quotedAuthor = includesUsersMap.get(quotedAuthorId);
    originalTweet = {
      id: quoted.id,
      text: (quotedTweet?.note_tweet?.text || quotedTweet?.text || "").substring(0, 2000),
      author_id: quotedAuthorId,
      author_username: quotedAuthor?.username || "",
    };
  } else if (tweet.note_tweet) {
    tweetType = "长文";
  } else {
    tweetType = "原创";
  }

  return {
    ...tweet,
    full_text: fullText,
    tweet_type: tweetType,
    original_tweet: originalTweet,
  };
}

/**
 * Assign thread_position to tweets grouped by conversation_id.
 * Operates in-place on the tweet array.
 */
export function assignThreadPositions(tweets: EnrichedTweet[]): void {
  const threads = new Map<string, EnrichedTweet[]>();

  for (const t of tweets) {
    if (!t.conversation_id) continue;
    if (!threads.has(t.conversation_id)) {
      threads.set(t.conversation_id, []);
    }
    threads.get(t.conversation_id)!.push(t);
  }

  for (const [, threadTweets] of threads) {
    if (threadTweets.length <= 1) continue;

    // Sort chronologically
    threadTweets.sort((a, b) =>
      (a.created_at ?? "").localeCompare(b.created_at ?? "")
    );

    for (let i = 0; i < threadTweets.length; i++) {
      threadTweets[i].thread_position = i + 1;
    }
  }
}
