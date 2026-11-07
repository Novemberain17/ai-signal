# AI Signal

把散落在播客、大厂博客、公众号、推特、arXiv 里的 AI 前沿信息，变成一个有编辑判断、可溯源的订阅源。

**起点观察**：小红书 AI 知识类笔记评论区大量用户 @点点 说"多给我推这个类型的视频"——用户在用自然语言向推荐系统下指令，说明他们要的是一个稳定的、不用自己维护的信息源。

## 进度

| 阶段 | 产出 | 状态 |
|---|---|---|
| 0. 观察与问题定义 | `docs/00-observation.md` | 初版完成，待用访谈修订 |
| 1. 评论挖掘（100–150 条） | `data/comments_raw.csv` → `docs/01-comment-mining.md` | 完成，n=157 |
| 2. 用户访谈（8–12 人） | `docs/02-interviews.md` | 进行中 |
| 3. 竞品定位 | `docs/03-competitors.md` | 未开始 |
| 4. 方案与取舍 | `docs/04-solution.md` | 未开始 |
| 5. 半自动流水线 + 上线 4–6 期 | `pipeline/`、`issues/` | 未开始 |
| 6. 数据与复盘 | `docs/05-retro.md` | 未开始 |

## 目录

```
docs/       研究文档，按阶段编号；decisions.md 记录每个关键取舍
data/       原始数据与打标后的数据
pipeline/   抓取 → 摘要 → 人工挑选的半自动流水线
issues/     每一期发出去的内容存档，文件名为发布日期
```

## 约定

- 每有一个结论就 commit，commit message 写结论而不是动作
- `docs/decisions.md` 每周至少一条
- 用户原话一律加引号并标注来源（评论链接 / 访谈编号），不改写
