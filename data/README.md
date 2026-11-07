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
| tag | 原始表留空。打标结果在 `comments_tagged.csv`，多个标签用顿号分隔；定义见 docs/01-comment-mining.md |
| notes | 任何备注 |

打标完成后另存为 `comments_tagged.csv`，保留原始文件不动。

## 采集小红书 @点点 评论

在仓库根目录运行。需要 Python 3.9+ 和 Google Chrome。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install 'playwright>=1.51,<2'
python pipeline/crawl_diandian.py --target 150
```

首次运行时，按终端提示在打开的 Chrome 窗口扫码登录。脚本使用独立的浏览器资料目录，后续运行会复用登录状态。默认搜索 AI 发展、大模型、Agent、Harness 等主题，读取笔记中已加载的评论和评论区滚动后加载的内容。可以用多个 `--query` 指定搜索词。

`--target 150` 指常规样本累计达到 150 条。`notes` 标为「定向补样」的原有记录仍保留在表里。脚本按评论 ID 和同笔记下的相同原文去重，逐篇保存结果和已扫描笔记。遇到访问限制或安全验证会停止，等小红书恢复访问后运行同一命令可接续。若搜索词扫完仍未达到目标，可更换搜索词继续采集。
