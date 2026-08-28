# SkillSwipe 部署指南

两件事：① 每周自动更新数据 ② 采集左右滑使用统计。两者独立，可分别启用。

## ① 每周自动更新（GitHub Actions）

把项目推到 GitHub 仓库后：

1. **加 Secret**：仓库 Settings → Secrets and variables → Actions → New secret
   - `DEEPSEEK_API_KEY` = 你的 DeepSeek API key（https://platform.deepseek.com 申请）
2. **启用 Actions**：Settings → Actions → Allow all actions
3. **运行**：Actions 页面可手动触发 `Weekly Skill Update`；或等每周一 03:00 UTC 自动跑

流程：`fetch_skills.py`（抓取）→ `summarize_with_llm.py`（**仅对新增 skill 调 LLM，已有总结复用，省 token**）→ `summarize_skills.py`（合并注入）→ 自动 commit & push 更新 `index.html`。

> 增量总结：`summarize_with_llm.py` 读已有 `summary_part_llm.json`，只对缺失的 id 调 LLM。`--force` 可强制全量重跑。

4. **托管页面**（可选）：Settings → Pages → Source 选 main 分支 `/` 根目录，即可得到 `https://<user>.github.io/<repo>/index.html` 访问链接。

## ② 使用统计（Cloudflare Worker + D1）

匿名方案，无需登录。前端生成设备 `clientId`，滑卡片时上报，后端聚合各 skill 的收藏/跳过次数。

1. **装 wrangler**：`npm i -g wrangler`（或 `npx wrangler`）
2. **登录**：`wrangler login`
3. **建库**：
   ```bash
   cd worker
   wrangler d1 create skillswipe
   ```
   把返回的 `database_id` 填进 `worker/wrangler.toml` 的 `database_id` 字段。
4. **建表**：
   ```bash
   wrangler d1 execute skillswipe --remote --file=schema.sql
   ```
5. **部署**：
   ```bash
   wrangler deploy
   ```
   得到 Worker URL，如 `https://skillswipe-stats.<你的子域>.workers.dev`
6. **接前端**：编辑 `index.html`，把 `STATS_API` 填为该 URL：
   ```js
   var STATS_API = "https://skillswipe-stats.xxx.workers.dev";
   ```
   留空则本地模式不上报，不影响浏览。

### API

- `POST /swipe` `{clientId, skillId, action:"like|skip"}` → `{ok:true}`
- `GET /stats` → `{skillId:{like,skip}, ...}`
- `GET /stats?skillId=xxx` → `{like,skip}`
- `GET /me?clientId=xxx` → 个人最近 200 条滑动记录

详情页会展示「♥ N · ✕ M」热度。匿名 clientId 存 localStorage，换设备/清缓存会重置（无需登录）。

## 本地开发

不部署任何后端也能用：`index.html` 直接浏览器打开即可浏览。`STATS_API` 留空时所有上报静默跳过。
