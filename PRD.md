# SkillSwipe（技能卡）产品需求文档（PRD）

> 版本：v0.1（草案，待确认）
> 日期：2026-08
> 状态：待评审
> 一句话定位：**用 Tinder 式的左右滑动，发现并安装 GitHub 高 star 的 AI Agent Skills 的手机端极简卡片工具。**

---

## 1. 背景与问题

AI Agent（Claude Code、Codex、Cursor、Gemini CLI、Copilot 等）生态爆发后，出现了大量高质量的 Agent Skills（标准格式为 `SKILL.md`，含 YAML frontmatter 的 Markdown 指令包），主要分布在 GitHub 上（`claude-skills`、`agent-skills` 等 topic 下已有数千仓库，头部仓库如 `anthropics/skills` 超过 5 万 star）。

用户发现与选择技能的现有路径是：逛 GitHub topic 页 / awesome 列表 → 逐个进仓库读 README → 手动判断是否有用 → 手动下载并放到对应目录。**发现效率低、无沉浸浏览体验、缺乏"感兴趣/不感兴趣"的快速决策机制**。

本产品把"逛技能库"变成"滑卡片"，降低发现成本，并在右滑（感兴趣）后提供**一键复制安装 prompt**，把「看到 → 决定 → 装进自己的 AI agent」闭环缩短到几秒。

## 2. 目标用户

- 主力：正在使用 Claude Code / Codex / Cursor 等 coding agent 的开发者，希望扩展 agent 能力。
- 次主力：AI 工具爱好者，想了解当前热门的 Agent Skills 生态。
- 使用场景：通勤 / 碎片时间在手机端浏览；看到感兴趣的技能后复制 prompt，粘贴到自己的 agent 里安装。

## 3. 核心概念

| 概念 | 说明 |
| --- | --- |
| Skill 卡片 | 一张高 star skills 的信息卡：名称、stars、核心功能、热门评论（如有） |
| 左滑（不感兴趣） | 卡片飞出，进入"已跳过"列表，不再打扰 |
| 右滑（感兴趣） | 卡片进入"我的收藏"，并可进入详情页 |
| 安装 Prompt | 一段可复制的指令文本，粘贴给自己的 AI agent 即可完成该 skill 的安装 |
| AI Agent 类型 | Claude Code、Codex、Cursor、Gemini CLI、Copilot 等，安装路径不同，详情页可切换 |

## 4. 功能需求（MVP 范围）

### F1 卡片流浏览（手机端主页）

- 卡片堆叠展示（最多叠 2–3 张），最上层卡片可交互。
- 卡片内容：
  - 技能名称（突出显示，如 `document-skills`）
  - ⭐ Stars 数（高亮，作为"高赞"的信号）
  - 核心功能（2–3 条要点，自动从 SKILL.md / README 摘要提取）
  - 热门评论（如有，引用块样式，最多 1–2 条）
  - 所属仓库与所属 Agent 生态标识（小字）
- 列表顶部：进度信息（已滑 n / 总数）、剩余卡片数。

### F2 左右滑决策

- 手势：触摸拖动卡片，卡片跟随手指位移并旋转；松手时根据位移/速度阈值判定方向。
  - 左滑 = 不感兴趣（飞出动画 + 灰色/✕ 反馈）
  - 右滑 = 感兴趣（飞出动画 + 绿色/♥ 反馈）
- 兜底：底部按钮（✕ 跳过 / ♥ 喜欢），保证无手势能力时可用。
- 可回退一步（撤销上一次滑动）。
- 情绪反馈：拖动过程中卡片上渐显 LIKE / SKIP 水印。
- 偏好持久化：滑动记录存入 localStorage，刷新/重开 App 不丢。

### F3 详情页（右滑后进入）

- 完整信息：技能名、仓库、stars、完整描述、核心功能列表、适用 Agent 类型、GitHub 链接、原文 README/SKILL.md 链接。
- **安装 Prompt 区（核心功能）**：
  - 展示一段可复制的 prompt 文本，明确写着"粘贴给 XX Agent 即可安装"。
  - 提供「复制」按钮（Clipboard API，含 iOS 降级方案）。
  - 支持切换 Agent 类型（Claude Code / Codex / Cursor / Gemini CLI / Copilot），prompt 中安装路径随之变化。
  - prompt 末尾附安全性提示（"安装前建议检查脚本权限，谨慎对待要求 shell 权限的 skill"）。
- 评论区：展示其他用户对该 skill 的使用评论（数据来源见 F4）；评论为空时显示占位文案。
- 详情页支持从"我的收藏"再次进入。

### F4 数据源与数据管道

- 数据来源：GitHub Search API（`q=topic:claude-skills OR topic:agent-skills`，按 stars 排序），辅以人工审核过滤（排除纯 awesome 列表、明显灌水/废弃仓库）。
- 每条 skill 的元数据：仓库名、stars、updated_at、README 摘要、SKILL.md frontmatter（name/description）、技能目录路径（用于生成安装命令/prompt）。
- **MVP 采用"预抓取静态数据"策略**：用脚本抓取并清洗后生成 `skills.json`，内置在前端应用中（约 30–60 个高 star skill），前端零 API 依赖、无限流问题。
- 评论数据来源（MVP）：人工精选 1–3 条来自 README / 社区 / Issues 的真实反馈；不承诺覆盖每一个 skill（见 §8 风险）。

### F5 我的收藏

- 右滑过的 skill 的列表页，可重新查看详情或移除。
- 展示收藏数。

### 非功能需求

- 手机端优先（375px 基准，竖屏），桌面端只保证可用不保证体验。
- 极简 UI：大留白、少配色、卡片式、动效流畅（触屏 60fps，优先 transform/opacity 动画）。
- 隐私：纯本地应用，无账号、无埋点、不上传用户行为。
- 首屏加载 < 2s（静态数据 + 无重框架）。
- 代码安全：不执行任何用户输入；复制 prompt 仅文本，不做任何自动执行。

## 5. 页面与交互规格

### 5.1 主页（卡片流）

```
┌─────────────────────┐
│  SkillSwipe   已滑 3/40 │  ← 顶栏
│                     │
│      ┌─────────┐    │
│      │ 卡片 3   │    │  ← 背景堆叠层（淡出）
│      └─────────┘    │
│    ┌───────────┐    │
│    │ 卡片 2     │    │  ← 中间层
│    └───────────┘    │
│  ┌─────────────┐    │
│  │ 卡片 1 (可拖) │    │  ← 当前卡片：名称/⭐/核心功能/评论
│  └─────────────┘    │
│  [回退]  [✕]  [♥]   │  ← 底部操作区
└─────────────────────┘
```

卡片拖动规则：
- 拖动位移量 <= 可视宽度 30% 时回弹；> 阈值或松手速度 > 0.4 px/ms 时触发飞出。
- 飞出方向决定结果并写入 localStorage。

### 5.2 详情页

- 顶部：返回按钮 + 技能名。
- 中段 1：基本信息卡（stars、仓库、描述、核心功能）。
- 中段 2（高亮）：安装 Prompt 卡 —— agent 类型 Tab（如 `Claude Code` `Codex` `Cursor`），prompt 文本框 + 一键复制按钮 + 复制成功 toast。
- 中段 3：评论区（评论列表 / 空态）。
- 底部：GitHub 仓库链接。

## 6. 数据模型

```json
{
  "id": "anthropics/skills::document-skills",
  "repo": "anthropics/skills",
  "repoUrl": "https://github.com/anthropics/skills",
  "skillName": "document-skills",
  "sourceDir": "skills/document-skills",
  "stars": 56124,
  "updatedAt": "2026-08-01",
  "description": "从文档生成知识卡片，供 agent 在离线场景引用",
  "coreFeatures": ["...", "...", "..."],
  "agents": ["claude-code", "codex", "cursor"],
  "install": {
    "claude-code": { "dir": ".claude/skills/document-skills" },
    "codex": { "dir": ".agents/skills/document-skills" }
  },
  "comments": [
    { "author": "@user", "text": "...", "source": "README/社区精选" }
  ],
  "topics": ["claude-code", "skills"]
}
```

技能安装 prompt 生成模板（按 Agent 类型拼接）：

```text
请帮我把 GitHub 仓库 {repo} 中的技能 {sourceDir} 安装到我的 {agentName}：
1. 下载该目录到 {installDir}；
2. 阅读 SKILL.md 并确认 name/description 字段正确；
3. 告诉我如何使用它。
注意：如果技能含脚本，请先解释脚本作用再执行。
```

## 7. 技术方案与选型

### 架构（MVP：纯静态单页应用）

```
[抓取脚本 fetch-skills.py / fetch-skills.ps1]
        │  GitHub REST API（Search + README + SKILL.md raw）
        ▼
   data/skills.json  ──► 静态前端：index.html + app.js + styles.css
        ▲
   localStorage（滑动记录 / 收藏）
```

- 前端：HTML + CSS + 原生 JS（零构建，双击即可打开；也可部署到 GitHub Pages / Vercel / 任意静态托管）。
- 手势：Pointer Events（touch + mouse 统一）实现拖动/飞出，无需第三方库；如需可引入 hammer.js（<5KB）。
- 复制：`navigator.clipboard.writeText` + iOS 兼容降级（document.execCommand）。
- 抓取脚本：Python（requests 一次抓完，输出 JSON）。
- agent 安装目录约定（标准路径）：
  - Claude Code：`.claude/skills/<name>`
  - Copilot / Codex / 其他通用：`~/.agents/skills/<name>`
  - Cursor、Gemini CLI 等：以目标 agent 文档为准，prompt 中给"最通用路径 + 提示以官方文档为准"。

### 里程碑

| 阶段 | 内容 | 验收 |
| --- | --- | --- |
| M0 | 数据管道：抓取并清洗 30–60 个高 star skill → skills.json | 数据完整、有 stars 排序、含核心功能摘要 |
| M1 | 卡片流 + 左右滑 + 回退 + localStorage | 手机浏览器实测手势顺滑，状态持久 |
| M2 | 详情页 + Agent 切换 + 一键复制 prompt + 收藏列表 | 复制到 Claude Code 可成功安装一个 skill |
| M3 | UI 打磨、空态/加载态、分享、评论扩展 | 全流程走查通过 |

## 8. 可行性评估与风险

### 可行性结论：**整体可行，建议按「纯静态 + 预抓取数据」路线做 MVP**

| 关键能力 | 判断 | 依据 / 方案 |
| --- | --- | --- |
| 高 star skills 数据 | ✅ 可行 | GitHub Search API 支持 topic+sort=stars；`claude-skills` topic 下数千仓库，排名数据稳定 |
| Stars 排序（"高赞"） | ✅ 可行 | stars 为公开字段，每次抓取刷新即可 |
| 核心功能摘要 | ✅ 可行 | 读取仓库 SKILL.md frontmatter 的 description + README 首段；自动抽取要点（规则截断即可，不依赖 LLM） |
| 左右滑卡片 UI | ✅ 可行 | Pointer Events + CSS transform，手机端成熟方案 |
| 一键复制安装 prompt | ✅ 可行 | 模板化生成 + Clipboard API；可行性已在 GitHub 生态验证（SKILL.md 标准 + `gh skill` 等工具已有官方支持） |
| 用户评论（使用反馈） | ⚠️ 部分可行 | GitHub 没有统一的"技能评分/评论"体系；MVP 先人工精选评论 + 空态占位，UGC 评论需要后端，放入 V2 |

### 主要风险

1. **评论数据稀缺**：没有官方"用户使用评论"数据源。MVP 用人工精选（README/社区/Issues 中的真实反馈），覆盖不全属预期；V2 可考虑接入 GitHub Discussions/Issues 或自建后端 UGC。
2. **GitHub API 限流**：Search API 未认证 10 req/min、认证 30 req/min / 5000 req/h；单次全量抓取约需 100+ 请求。→ 用预抓取静态数据方案规避（只在构建时调 API，前端永不直接调）。
3. **"仓库 = 技能"假设不成立**：很多高 star 仓库是 awesome 列表或多技能合集，需过滤（pipeline 中按"是否存在 SKILL.md / skills/ 目录"判定），并解析"repo 内某个子目录"才是技能本体。
4. **安装 prompt 的准确性**：各仓库目录结构差异大。→ prompt 生成规则 + 人工抽查 10 个头部仓库校准；prompt 末尾提示"以仓库 README 为准"。
5. **注入与脚本安全**：skill 可含脚本，复制 prompt 时明确提示用户谨慎对待要求 shell/`allowed-tools: shell` 权限的技能。
6. **搜索结果噪音**：自动抓取会混入低质/灌水仓库 → 管道中加入"人工审核 + star 阈值 + 更新时间过滤"三步清洗。

## 9. 竞品 / 对标参考

- 官方 `claude.ai/marketplace`（Skills Marketplace）：有浏览体验，但未聚合 GitHub 全生态高 star 社区技能。
- `linny006/trending-claude-skills`：GitHub Actions 定时抓 Search API 生成排行榜 README，验证了"Search API 按星抓取"可行。
- `K-Dense-AI/claude-skills-mcp`：MCP 实现技能检索，验证社区对"发现工具"的需求。
- 本产品的差异化：**Tinder 式滑动决策 + 一键复制安装 + 移动端极简浏览**，同赛道无直接竞品。

## 10. V2 展望（本期不做）

- UGC 评论与点赞（需后端与账号体系）。
- 按分类/生态筛选与搜索。
- 分享单张技能卡片（生成分享图/链接）。
- 每周自动更新数据（GitHub Actions 定时任务）。
- 桌面端适配。

## 11. 已确认决策（2026-08-27 评审通过）

| 决策项 | 结论 |
| --- | --- |
| 数据获取 | ✅ 预抓取静态数据：`fetch_skills.py` 抓 GitHub API → 生成 `skills.json` 并注入 `index.html` |
| 技术形态 | ✅ 零构建单文件：单一 `index.html`（内嵌 CSS/JS/数据），双击即可打开，可部署任意静态托管 |
| 评论来源 | ✅ MVP 留空：评论区显示空态占位，UGC 评论（需后端）列入 V2 |
| Agent 范围 | ✅ 多 agent 通用：详情页可切换 Claude Code / Codex / Cursor / Copilot CLI / Gemini CLI，prompt 分别生成对应安装路径 |

### MVP 交付物清单
- `index.html` — 完整可用的单文件应用（卡片流 + 左右滑 + 详情页 + 复制安装 prompt + 我的收藏）
- `fetch_skills.py` — 数据管道脚本（`python fetch_skills.py --limit N` 可重新抓取并刷新数据）
- `skills.json` — 最近一次抓取的技能数据快照（26 个高 star skills）