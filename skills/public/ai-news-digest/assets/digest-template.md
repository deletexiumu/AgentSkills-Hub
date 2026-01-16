# AI 资讯简报（{{ date }}）

> 时间窗口：{{ window }}  
> 语言：{{ lang }}  
> 信源：{{ sources }}  

## 研究 / 论文 / 实验室

{{#research}}
- {{ title }}（{{ source_name }}，{{ published_at }}）{{ url }}
  - 摘要：{{ summary }}
  - 标签：{{ tags }}
{{/research}}

## 产品 / 模型 / 发布

{{#product}}
- {{ title }}（{{ source_name }}，{{ published_at }}）{{ url }}
  - 摘要：{{ summary }}
  - 标签：{{ tags }}
{{/product}}

## 开源 / 工具 / 工程

{{#opensource}}
- {{ title }}（{{ source_name }}，{{ published_at }}）{{ url }}
  - 摘要：{{ summary }}
  - 标签：{{ tags }}
{{/opensource}}

## 投融资 / 商业

{{#funding}}
- {{ title }}（{{ source_name }}，{{ published_at }}）{{ url }}
  - 摘要：{{ summary }}
  - 标签：{{ tags }}
{{/funding}}

## 政策 / 伦理 / 安全

{{#policy}}
- {{ title }}（{{ source_name }}，{{ published_at }}）{{ url }}
  - 摘要：{{ summary }}
  - 标签：{{ tags }}
{{/policy}}

## 抓取失败的信源（如有）

{{#failures}}
- {{ source_name }}：{{ reason }}
{{/failures}}

