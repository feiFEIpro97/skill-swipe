# -*- coding: utf-8 -*-
"""
summarize_skills.py — 合并中文总结并注入前端（支持多类别标签 + Token 优化自动标记）
- 读取 analysis_input.json（fetch_skills.py 产物：原始技能信息）
- 读取所有 summary_part_*.json / summary_zh.json（LLM/人工总结结果：id -> 中文信息）
- 合并生成 skills.json 并注入 index.html
- categories 支持数组（多标签）；旧的单值 category 自动包成数组
- 自动识别 token/上下文优化相关 skill，追加 "Token 优化" 标签
用法: python summarize_skills.py [--output index.html]
"""
import glob
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TOKEN_KW = [
    "省 token", "省token", "节省 token", "节省token",
    "token 效率", "token efficiency", "token optimization",
    "零 token", "零token", "zero token", "token 浪费", "token浪费",
    "额度浪费", "省额度",
]


def load_summaries():
    sums = {}
    for path in sorted(glob.glob("summary_part_*.json")) + (["summary_zh.json"] if os.path.exists("summary_zh.json") else []):
        try:
            with open(path, encoding="utf-8") as f:
                obj = json.load(f)
            for k, v in obj.items():
                sums[k] = v
        except Exception as e:
            print(f"  [skip] {path}: {e}", file=sys.stderr)
    return sums


def to_categories(v):
    if isinstance(v, list):
        return [c for c in v if c]
    if isinstance(v, str) and v:
        return [v]
    return []


def is_token_related(skill, summary):
    # 优先用 LLM 产出的 tokenOptimized 字段（精准判断）
    if "tokenOptimized" in summary:
        return bool(summary.get("tokenOptimized"))
    # 只看核心定位（description + zhIntro 一句话简介），
    # 不看 sellingPoints/readme 的附带提及，避免误标
    blob = (str(skill.get("description", "")) + " " + str(summary.get("zhIntro", ""))).lower()
    return any(kw.lower() in blob for kw in TOKEN_KW)


COLLECTION_KW = [
    "合集", "精选", "大全", "清单", "市场", "注册表", "registry",
    "awesome", "资源集", "技能集", "插件市场", "目录", "聚合",
]


def is_collection(skill, summary):
    blob = " ".join([
        str(skill.get("skillName", "")),
        str(skill.get("description", "")),
        str(skill.get("readme_head", ""))[:1200],
        " ".join(summary.get("sellingPoints", [])),
        str(summary.get("zhIntro", "")),
    ]).lower()
    return any(kw.lower() in blob for kw in COLLECTION_KW)


def main():
    with open("analysis_input.json", encoding="utf-8") as f:
        raw = json.load(f)
    sums = load_summaries()
    print(f"已加载 {len(sums)} 条中文总结")

    skills = raw["skills"]
    updated = 0
    for s in skills:
        item = sums.get(s["id"]) or {}
        cats = to_categories(item.get("categories")) or to_categories(item.get("category"))
        if not cats:
            cats = to_categories(s.get("categories")) or to_categories(s.get("category")) or ["其他"]
        zh = item.get("zhIntro") or s.get("zhIntro")
        points = item.get("sellingPoints") or s.get("sellingPoints") or (s.get("coreFeatures") or [])
        aud = item.get("audience") or s.get("audience")
        if not (zh or points or cats or aud):
            continue
        if zh:
            s["zhIntro"] = zh
        if points:
            s["sellingPoints"] = list(points)
        if is_collection(s, item) and "其他" in cats:
            cats = ["skills精选合集" if c == "其他" else c for c in cats]
        if is_token_related(s, item):
            if "Token 优化" not in cats:
                cats.append("Token 优化")
        s["categories"] = cats
        s["category"] = cats[0] if cats else "其他"
        if aud:
            s["audience"] = aud
        updated += 1

    payload = {"generatedAt": raw.get("generatedAt"), "count": len(skills), "skills": skills}
    with open("skills.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    js = "window.SKILLS_DATA = " + json.dumps(payload, ensure_ascii=True) + ";"
    js = js.replace("</script", "<\\/script")
    out = sys.argv[sys.argv.index("--output") + 1] if "--output" in sys.argv else "index.html"
    with open(out, encoding="utf-8") as f:
        html = f.read()
    pattern = re.compile(r'<script id="skills-data">.*?</script>', re.S)
    if not pattern.search(html):
        raise SystemExit("index.html 中找不到 <script id=\"skills-data\"> 占位，未注入")
    html = pattern.sub(lambda m: '<script id="skills-data">' + js + '</script>', html, count=1)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    token_n = sum(1 for s in skills if "Token 优化" in (s.get("categories") or []))
    print(f"完成：合并 {updated}/{len(skills)} 条中文信息 -> skills.json / {out}（Token 优化 {token_n} 个）")


if __name__ == "__main__":
    main()