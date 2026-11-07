# data

## comments_raw.csv 字段

| 字段 | 说明 |
|---|---|
| id | 自增 |
| date_collected | 采集日期 |
| note_url | 笔记链接 |
| note_type | AI前沿解读 / 书籍分享 / 工具教程 / 其他 |
| note_title | 笔记标题 |
| comment_text | 评论原文，不改写 |
| likes | 评论点赞数 |
| comment_date | 评论发布日期（看不到就留空） |
| tag | 先留空，凑够 50 条后统一打标；标签定义见 docs/01-comment-mining.md |
| notes | 任何备注 |

打标完成后另存为 `comments_tagged.csv`，保留原始文件不动。
