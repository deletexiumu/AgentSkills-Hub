# AI 每日简报 | {{date}}

> 数据来源：X 平台「为你推荐」栏目
> 筛选条件：AI 相关内容
> 有效帖子：{{count}} 条

---

## 一、今日热点话题

{{#topics}}
### {{icon}} {{title}}
{{description}}
{{items}}
{{/topics}}

---

## 二、重要产品/功能发布

| 产品 | 发布方 | 内容 |
|------|--------|------|
{{#releases}}
| {{product}} | {{author}} | {{description}} |
{{/releases}}

---

## 三、行业观察

{{#observations}}
{{index}}. **{{title}}** - {{description}}
{{/observations}}

---

## 四、精选帖子及回复建议

{{#selected_posts}}
### {{index}}. {{author}} - {{topic}}

**原文**：
> {{content}}

**链接**：{{url}}

**建议回复（{{language}}）**：
> {{reply}}

{{#is_foreign}}
**中文说明**：{{chinese_explanation}}
{{/is_foreign}}

---

{{/selected_posts}}

## 五、今日金句

{{#quotes}}
> "{{content}}"
> — @{{username}} ({{displayName}})

{{/quotes}}

---

## 六、值得关注的账号

| 账号 | 方向 | 推荐理由 |
|------|------|----------|
{{#recommended_accounts}}
| @{{username}} | {{focus}} | {{reason}} |
{{/recommended_accounts}}

---

*简报生成时间：{{generated_at}} 北京时间*
