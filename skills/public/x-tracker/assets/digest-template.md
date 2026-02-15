# X Daily Digest — {{DATE}}

## Summary

- Following: **{{FOLLOWING_COUNT}}** accounts
- Bookmarks today: **{{NEW_BOOKMARKS}}** new
- My tweets today: **{{MY_TWEETS_COUNT}}**

---

## Bookmarks by Category

{{#CATEGORIES}}
### {{CATEGORY_NAME}} ({{COUNT}})

{{#ITEMS}}
- **@{{AUTHOR}}**: {{TEXT_PREVIEW}} | ❤️{{LIKES}} 🔄{{RETWEETS}}
{{/ITEMS}}

{{/CATEGORIES}}

---

## Following Changes

{{#NEW_FOLLOWS}}
- ➕ @{{USERNAME}} — {{BIO_PREVIEW}}
{{/NEW_FOLLOWS}}

{{#UNFOLLOWED}}
- ➖ @{{USERNAME}}
{{/UNFOLLOWED}}

---

## My Top Tweets

{{#TOP_TWEETS}}
1. {{TEXT_PREVIEW}} — ❤️{{LIKES}} 🔄{{RETWEETS}} 💬{{REPLIES}}
{{/TOP_TWEETS}}

---

*Generated at {{TIMESTAMP}}*
