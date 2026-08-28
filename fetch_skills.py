# -*- coding: utf-8 -*-
"""
SkillSwipe 数据管道 v3（网络受限环境适配：仅依赖 api.github.com 域）
背景：raw.githubusercontent.com / github.com 页面在某些网络不可达，
      因此 README 与封面图全部走 GitHub REST API。
- 搜索近期活跃(pushed)的高 star AI Agent Skills（多 topic 合并、按 stars 排序）
- 每个仓库：1 次 API 调用（GET /repos/{full}/readme，Accept: raw）拿 README 原文
- 封面图：README 中第一个绝对 URL 图片（排除 badge/icon）；无则留空（前端 fallback）
- 产出 skills.json / analysis_input.json（供总结步骤）
用法: python fetch_skills.py [--limit 50] [--days 180]
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

API = "https://api.github.com"
HOME = "https://github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
TOPICS = ["topic:claude-skills", "topic:agent-skills", "topic:claude-code-skills", "topic:ai-skills"]
# token/上下文优化专项搜索关键词（按 stars 召回，单独配额确保 token 主题 skill 入库）
EXTRA_QUERIES = [
    "token efficiency claude skill",
    "context compression agent skill",
    "token optimization claude",
    "reduce token agent",
    "context window skill claude",
]
MIN_STARS = 100
AGENTS = ["claude-code", "codex", "cursor", "copilot", "gemini-cli"]
UA = "SkillSwipe-fetcher/3.0"
PARTIAL = "partial_skills.jsonl"


class RateLimited(Exception):
    pass


def http(url, headers=None, retries=3, timeout=25):
    h = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    if TOKEN:
        h["Authorization"] = "Bearer " + TOKEN
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                reset = None
                try:
                    reset = int(e.headers.get("X-RateLimit-Reset") or 0)
                except Exception:
                    reset = 0
                wait = 30 * (attempt + 1)
                if reset:
                    wait = reset - int(time.time()) + 2
                if reset and wait > 90:
                    raise RateLimited(f"API 配额已耗尽，约 {wait}s 后恢复（可稍后重跑续传）")
                print(f"  [limit] {e.code} 等待 {wait}s 重试", file=sys.stderr)
                time.sleep(max(wait, 5))
            elif e.code in (404, 410):
                return None
            else:
                print(f"  [http{e.code}] {url[:90]}", file=sys.stderr)
                return None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt == retries - 1:
                print(f"  [net] {url[:90]} -> {e}", file=sys.stderr)
                return None
            time.sleep(3)
    return None


def gh_json(url):
    data = http(url)
    if not data:
        return None
    try:
        return json.loads(data)
    except Exception:
        return None


def search_repos(topic, pushed_since):
    q = f"{topic} pushed:>{pushed_since}"
    url = f"{API}/search/repositories?q={urllib.parse.quote(q)}&sort=stars&order=desc&per_page=100"
    return (gh_json(url) or {}).get("items", [])


def split_features(desc):
    if not desc:
        return []
    parts = re.split(r"\s*[;；·,，]\s*|\s*—\s*|\s*\|\s*", desc)
    seen, feats = set(), []
    for p in parts:
        p = re.sub(r"^[^\w\u4e00-\u9fff]+", "", p).strip().strip(".")
        if 6 <= len(p) <= 110 and p not in seen:
            seen.add(p)
            feats.append(p)
        if len(feats) >= 4:
            break
    return feats


def first_cover_image(text):
    """README 中第一个非徽章类绝对 URL 图片。"""
    for m in re.finditer(r"!\[[^\]]*\]\(([^)\s]+)\)", text or ""):
        u = m.group(1).strip()
        if not u.startswith("http"):
            continue
        if any(x in u for x in ("badge", "shield", "img.shields", "github.com/.*/actions/workflows", "codecov", "gitter")):
            continue
        if "githubusercontent.com" in u and ("/raw/" not in u and "/assets/" not in u and ".svg" not in u):
            continue
        return u
    return None


def analyze_repo(item):
    full = item["full_name"]
    out = {
        "id": full,
        "skillName": item["name"],
        "author": full.split("/")[0],
        "repo": full,
        "repoUrl": item.get("html_url", f"{HOME}/{full}"),
        "stars": item.get("stargazers_count", 0),
        "updatedAt": (item.get("updated_at") or "")[:10],
        "description": (item.get("description") or "").strip(),
        "topics": (item.get("topics") or [])[:6],
        "agents": AGENTS,
        "cover": None,
        "comments": [],
    }

    raw = http(f"{API}/repos/{full}/readme",
               headers={"User-Agent": UA, "Accept": "application/vnd.github.raw+json"})
    readme_text = raw.decode("utf-8", errors="replace") if raw else ""
    out["readme_head"] = readme_text[:2800]
    out["readme_headings"] = [ln.strip() for ln in readme_text.splitlines() if re.match(r"^#{1,3}\s", ln)][:28]
    out["cover"] = first_cover_image(readme_text)

    name, desc = item["name"], out["description"]
    lower = name.lower()
    if "awesome" in lower or "curated" in (desc or "").lower():
        out["kind"] = "collection"
        out["sourceDir"] = "仓库 skills/ 目录"
    else:
        out["kind"] = "unknown"
        out["sourceDir"] = "仓库根目录（具体以 README 说明为准）"
    return out


def load_partial():
    """读取已抓取的局部数据（断点续传）。"""
    done = {}
    if os.path.exists(PARTIAL):
        with open(PARTIAL, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        s = json.loads(line)
                        done[s["id"]] = s
                    except Exception:
                        pass
    return done


def save_partial(skill):
    with open(PARTIAL, "a", encoding="utf-8") as f:
        f.write(json.dumps(skill, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--token-quota", type=int, default=10, help="token 主题 skill 专项配额")
    args = ap.parse_args()

    pushed_since = time.strftime("%Y-%m-%d", time.localtime(time.time() - args.days * 86400))
    main_limit = max(args.limit - args.token_quota, 10)
    print(f"1/3 搜索近期活跃 skills（主 {main_limit} + token 专项 {args.token_quota}）...")
    merged = {}
    for topic in TOPICS:
        for item in search_repos(topic, pushed_since):
            stars = item.get("stargazers_count", 0)
            if stars < MIN_STARS:
                continue
            full = item.get("full_name", "")
            if full and (full not in merged or merged[full]["stargazers_count"] < stars):
                merged[full] = item
        time.sleep(2)
    main_ranked = sorted(merged.values(), key=lambda i: -i["stargazers_count"])[:main_limit]
    main_ids = set(it["full_name"] for it in main_ranked)

    # token 专项搜索：关键词召回 token/上下文优化相关 skill
    token_hits = {}
    for q in EXTRA_QUERIES:
        for item in search_repos(q, pushed_since):
            stars = item.get("stargazers_count", 0)
            if stars < MIN_STARS:
                continue
            full = item.get("full_name", "")
            if full and full not in main_ids and (full not in token_hits or token_hits[full]["stargazers_count"] < stars):
                token_hits[full] = item
        time.sleep(2)
    token_ranked = sorted(token_hits.values(), key=lambda i: -i["stargazers_count"])[:args.token_quota]
    ranked = main_ranked + token_ranked

    done = load_partial()
    todo = [it for it in ranked if it["full_name"] not in done]
    print(f"  合并 {len(merged)} 个，目标前 {len(ranked)} 个；已抓 {len(done)} 个，待抓 {len(todo)} 个")

    for i, item in enumerate(todo, 1):
        full = item["full_name"]
        print(f"2/3 [{len(done)+i}/{len(ranked)}] {full} ★{item['stargazers_count']:,}", flush=True)
        try:
            skill = analyze_repo(item)
            save_partial(skill)
            done[full] = skill
        except RateLimited as e:
            print(f"  [中断] {e}", file=sys.stderr)
            break
        except Exception as e:
            print(f"  [!] {full} 异常: {e}", file=sys.stderr)
        time.sleep(0.4)

    skills = list(done.values())
    skills.sort(key=lambda s: -s["stars"])
    payload = {"generatedAt": time.strftime("%Y-%m-%d %H:%M:%S"), "count": len(skills), "skills": skills}
    with open("skills.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    analysis = {
        "任务": "为每个 skill 生成中文信息：zhIntro(≤60字中文简介)、sellingPoints(3-5条中文核心卖点)、category(类别：内容创作/办公提效/开发辅助/AI基础设施与框架/自动化/数据分析/文档与知识/多智能体协作/安全与合规/其他)、audience(适合的使用对象与场景)",
        "规则": "名称与作者名保留原名不翻译；中文信息必须来自物料，不得编造；stars/repo 等字段不改动",
        "skills": skills,
    }
    with open("analysis_input.json", "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)

    covers = sum(1 for s in skills if s["cover"])
    print(f"3/3 完成：{len(skills)} 条 -> skills.json / analysis_input.json（封面图 {covers}/{len(skills)}）")


if __name__ == "__main__":
    main()