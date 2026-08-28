# -*- coding: utf-8 -*-
"""
summarize_with_llm.py — 调 DeepSeek API 对抓取的 skill 物料批量生成中文总结
读 analysis_input.json，对每个 skill 调 LLM，输出 summary_part_llm.json
（summarize_skills.py 会自动合并所有 summary_part_*.json）

用法:
  python summarize_with_llm.py [--workers 5] [--limit N] [--only id1,id2]

环境变量:
  DEEPSEEK_API_KEY   必填
  DEEPSEEK_BASE_URL  可选，默认 https://api.deepseek.com
  DEEPSEEK_MODEL     可选，默认 deepseek-chat
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
import glob
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

CATS = "内容创作/办公提效/开发辅助/AI基础设施与框架/自动化/数据分析/文档与知识/多智能体协作/安全与合规/skills精选合集/其他"

PROMPT_TMPL = """你是 AI 技能整理助手。根据以下 GitHub skill 物料，输出中文结构化信息。

物料：
- 名称：{name}
- 仓库：{repo}
- 描述：{desc}
- topics：{topics}
- README 摘要：
{readme}

严格输出 JSON（不要 markdown 代码块、不要多余文字）：
{{"zhIntro":"一句话中文简介(30-60字)","sellingPoints":["3-5条核心卖点,每条8-20字"],"categories":["1-3个类别,从词表选"],"audience":"适合的使用对象(一句话)","tokenOptimized":false}}

规则：
1. 名称/作者/仓库名保留原文，不翻译
2. 所有功能介绍翻译成中文
3. 信息只能来自物料，不得编造
4. 若是技能合集/精选清单/awesome列表/市场/注册表，categories 必含 "skills精选合集"
5. 类别词表：{cats}
6. sellingPoints 3-5 条，宁缺毋滥
7. tokenOptimized 仅当该 skill **核心功能就是直接节省 token/上下文占用**（如上下文压缩、token 效率优化、减少额度消耗）才为 true；间接省 token（如少写代码、持久记忆、去 AI 味）一律 false
"""


def call_llm(skill):
    name = skill.get("skillName", "")
    readme = (skill.get("readme_head") or "")[:1800]
    prompt = PROMPT_TMPL.format(
        name=name, repo=skill.get("repo", ""), desc=skill.get("description", ""),
        topics=", ".join(skill.get("topics") or []), readme=readme, cats=CATS)
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.3,
        "max_tokens": 700,
    }).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL.rstrip("/") + "/chat/completions",
        data=body,
        headers={"Authorization": "Bearer " + API_KEY, "Content-Type": "application/json"},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.loads(r.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            obj = json.loads(content)
            if "zhIntro" in obj and "sellingPoints" in obj:
                return skill["id"], obj
            print("  [warn] %s 字段缺失: %s" % (skill["id"], list(obj.keys())), file=sys.stderr)
            return skill["id"], None
        except urllib.error.HTTPError as e:
            msg = e.read()[:200]
            print("  [err] %s HTTP %s: %s" % (skill["id"], e.code, msg), file=sys.stderr)
            if e.code == 429:
                time.sleep(15)
        except Exception as e:
            print("  [err] %s %s" % (skill["id"], e), file=sys.stderr)
        time.sleep(2 * (attempt + 1))
    return skill["id"], None


def load_existing():
    """加载已有中文总结（优先 summary_part_llm.json，回退其他 summary_part_*.json）。
    增量模式下只对缺失的 skill 调 LLM，省 token。"""
    sums = {}
    if os.path.exists("summary_part_llm.json"):
        try:
            with open("summary_part_llm.json", encoding="utf-8") as f:
                sums.update(json.load(f))
        except Exception:
            pass
    if not sums:
        for path in sorted(glob.glob("summary_part_*.json")):
            try:
                with open(path, encoding="utf-8") as f:
                    sums.update(json.load(f))
            except Exception:
                pass
    return sums


def main():
    if not API_KEY:
        print("错误：未设置 DEEPSEEK_API_KEY 环境变量", file=sys.stderr)
        sys.exit(1)
    with open("analysis_input.json", encoding="utf-8") as f:
        raw = json.load(f)
    skills = raw["skills"]

    if "--only" in sys.argv:
        i = sys.argv.index("--only")
        want = set(sys.argv[i + 1].split(","))
        skills = [s for s in skills if s["id"] in want]
    if "--limit" in sys.argv:
        i = sys.argv.index("--limit")
        skills = skills[: int(sys.argv[i + 1])]

    workers = 5
    if "--workers" in sys.argv:
        i = sys.argv.index("--workers")
        workers = int(sys.argv[i + 1])

    force = "--force" in sys.argv

    # 增量：只总结没有已有总结的 skill，省 token
    existing = {} if force else load_existing()
    need = [s for s in skills if s["id"] not in existing]
    print("已有总结 %d，需新增总结 %d（%d 并发，模型 %s）" % (len(existing), len(need), workers, MODEL))

    result = dict(existing)
    failed = []
    if not need:
        print("无新增，跳过 LLM 调用")
    else:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(call_llm, s): s for s in need}
            for i, fut in enumerate(as_completed(futs), 1):
                sid, obj = fut.result()
                if obj:
                    result[sid] = obj
                else:
                    failed.append(sid)
                print("  [%d/%d] %s %s" % (i, len(need), sid, "OK" if obj else "FAIL"))

    with open("summary_part_llm.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("完成：summary_part_llm.json 共 %d 条" % len(result))
    if failed:
        print("失败：%s" % failed, file=sys.stderr)


if __name__ == "__main__":
    main()
