# -*- coding: utf-8 -*-
"""
detect_skills.py — 检测每个仓库的 SKILL.md 位置与技能结构
用于区分三类仓库：
  - 根目录有 SKILL.md        → 标准单技能包（整个仓库即一个技能）
  - skills/ 或子目录有 SKILL.md → 多技能合集（需要选技能后安装）
  - 无任何 SKILL.md          → 非标准技能仓库（应用/框架/清单，装到 skills 目录会失败）

用法: python detect_skills.py    # 需 GITHUB_TOKEN（5000/h，50 个仓库的 trees 调用）
产出: detect_report.json  {id: {skillmd:[...], hasSkillsDir, hasRootSkill, treeSize}}
断点续传：每检完一个即写盘，配额耗尽可稍后重跑。
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

API = "https://api.github.com"
UA = "SkillSwipe-detect/1.0"
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
DATA = "analysis_input.json"
OUT = "detect_report.json"


def http(url, retries=3):
    h = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    if TOKEN:
        h["Authorization"] = "Bearer " + TOKEN
    req = urllib.request.Request(url, headers=h)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                reset = 0
                try:
                    reset = int(e.headers.get("X-RateLimit-Reset") or 0)
                except Exception:
                    reset = 0
                wait = 30 * (attempt + 1)
                if reset:
                    wait = reset - int(time.time()) + 2
                if wait > 90:
                    print("  [中断] 配额耗尽，约 %ds 后恢复（重跑续传）" % wait, file=sys.stderr)
                    return None
                print("  [limit] 等 %ds" % wait, file=sys.stderr)
                time.sleep(max(wait, 5))
            elif e.code == 404:
                return {"error": "not_found"}
            else:
                print("  [http%d] %s" % (e.code, url[:90]), file=sys.stderr)
                return {"error": "http%d" % e.code}
        except Exception as e:
            if attempt == retries - 1:
                print("  [net] %s -> %s" % (url[:90], e), file=sys.stderr)
                return None
            time.sleep(3)
    return None


def detect(full):
    tree = http("%s/repos/%s/git/trees/HEAD?recursive=1" % (API, full))
    if not tree or tree.get("error"):
        return {"skillmd": [], "hasSkillsDir": False, "hasRootSkill": False,
                "treeSize": 0, "note": tree.get("error") if tree else "no-tree"}
    paths = [t["path"] for t in tree.get("tree", []) if t.get("type") == "blob"]
    skillmd = [p for p in paths if p.lower().rsplit("/", 1)[-1] in ("skill.md", "skills.md")]
    hasSkillsDir = any(p.lower().startswith("skills/") for p in paths)
    hasRootSkill = any(p.lower() == "skill.md" for p in paths)
    return {"skillmd": skillmd[:20], "hasSkillsDir": bool(hasSkillsDir),
            "hasRootSkill": bool(hasRootSkill), "treeSize": len(paths)}


def kind_of(s, r):
    if r.get("error"):
        return "unknown", r.get("note")
    if r.get("hasRootSkill"):
        return "single", "仓库根目录就是该技能（含 SKILL.md），整个仓库目录安装即可"
    if r.get("skillmd"):
        return "collection", "多技能仓库，SKILL.md 在子目录（%s），先选目标技能" % (r["skillmd"][0] or "?")
    return "app", "无 SKILL.md：非标准技能包（可能是应用/框架/清单），请查看仓库 README"


def main():
    if not TOKEN:
        print("错误：未设置 GITHUB_TOKEN 环境变量（50 个仓库的 trees 调用需要 5000/h）", file=sys.stderr)
        sys.exit(1)
    skills = json.load(open(DATA, encoding="utf-8"))["skills"]
    done = {}
    if os.path.exists(OUT):
        done = json.load(open(OUT, encoding="utf-8"))
    todo = [s for s in skills if s["id"] not in done]
    print("检测 %d 个仓库（已有 %d，待检 %d）" % (len(skills), len(done), len(todo)))
    for i, s in enumerate(todo, 1):
        print("  [%d/%d] %s" % (i, len(todo), s["id"]), flush=True)
        r = detect(s["id"])
        if r is None:
            break
        done[s["id"]] = r
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(done, f, ensure_ascii=False, indent=2)
        time.sleep(0.3)

    n = len(done)
    roots = sum(1 for v in done.values() if v.get("hasRootSkill"))
    subs = sum(1 for v in done.values() if v.get("skillmd") and not v.get("hasRootSkill"))
    none = sum(1 for v in done.values() if not v.get("skillmd"))
    print("完成 %d/%d：标准单技能 %d / 多技能合集 %d / 非标准仓库 %d"
          % (n, len(skills), roots, subs, none))


if __name__ == "__main__":
    main()