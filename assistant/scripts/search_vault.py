#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""laws-vault 全库确定性兜底检索 — 转录后定向检索 0 命中时的强制兜底（01 规则 Step 2）。

用法:
  python scripts/search_vault.py 质量保证
  python scripts/search_vault.py 质保 单项履约义务 --and      # 文件级 AND
  python scripts/search_vault.py 收入确认 --layers casi,casq  # 限定层
输出: 每命中文件一行头（文号|时效|生效日）+ 命中行（行号+[第X条]锚点+截断原文），末尾汇总。
退出码: 0=有命中  1=全库无命中（→按引用纪律输出「未检索到现行依据」拒答）  2=用法错误
设计: 纯标准库、正则忽略大小写、确定性排序（文件字典序+行序），给 agent/CI 一个无判断余地的判定。
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LAYERS = "cas,casg,casi,casc,casq"
FM_KEYS = ("doc_number", "status", "effective_date")
ARTICLE_RE = re.compile(r"^第[一二三四五六七八九十百千零〇\d]+条")
LINE_MAX = 120


def parse_fm(lines):
    """返回 front-matter 里 FM_KEYS 的子集（无 front-matter 返回 {}）。"""
    fm = {}
    if not lines or lines[0].strip() != "---":
        return fm
    for ln in lines[1:]:
        if ln.strip() == "---":
            break
        m = re.match(r"^([A-Za-z_]+):\s*(.*)$", ln)
        if m and m.group(1) in FM_KEYS:
            fm[m.group(1)] = m.group(2).strip()
    return fm


def trim(s: str) -> str:
    s = s.strip()
    return s if len(s) <= LINE_MAX else s[: LINE_MAX - 1] + "…"


def main() -> int:
    ap = argparse.ArgumentParser(description="laws-vault 全库兜底检索（0 命中→退出码 1→拒答）")
    ap.add_argument("terms", nargs="+", help="检索词（正则语法，忽略大小写；多词默认文件级 OR）")
    ap.add_argument("--layers", default=DEFAULT_LAYERS,
                    help=f"逗号分隔的层目录，默认 {DEFAULT_LAYERS}")
    ap.add_argument("--and", dest="mode_and", action="store_true",
                    help="文件级 AND：所有词都命中的文件才算命中")
    ap.add_argument("--root", default=str(ROOT), help="库根目录（默认本仓库）")
    ap.add_argument("--max-lines", type=int, default=8, help="每文件最多展示的命中行数")
    args = ap.parse_args()

    try:
        pats = [re.compile(t, re.IGNORECASE) for t in args.terms]
    except re.error as e:
        print(f"[用法错误] 非法正则: {e}", file=sys.stderr)
        return 2
    root = Path(args.root)

    files = []
    for layer in [x.strip() for x in args.layers.split(",") if x.strip()]:
        d = root / layer
        if d.is_dir():
            files += sorted(d.rglob("*.md"))
    files = sorted(set(files))

    hit_files, total_lines = 0, 0
    for f in files:
        rel = f.relative_to(root)
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        hits = []  # (行号, 锚点, 行文本)
        seen_terms = set()
        for idx, ln in enumerate(lines, 1):
            matched = [i for i, p in enumerate(pats) if p.search(ln)]
            if matched:
                seen_terms.update(matched)
                hits.append((idx, ln))
        if not hits or (args.mode_and and seen_terms != set(range(len(pats)))):
            continue
        fm = parse_fm(lines)
        head = " ｜ ".join(f"{k}={fm[k]}" for k in FM_KEYS if fm.get(k)) or "无 front-matter"
        print(f"{rel.as_posix()}  〔{head}〕")
        anchor = ""
        for idx, ln in hits[: args.max_lines]:
            anchor = next((lines[j].strip().split("　")[0].split(" ")[0]
                           for j in range(idx - 1, -1, -1)
                           if ARTICLE_RE.match(lines[j].strip())), anchor)
            print(f"  L{idx} [{anchor}] {trim(ln)}")
        if len(hits) > args.max_lines:
            print(f"  … 另有 {len(hits) - args.max_lines} 行命中（--max-lines 调整）")
        hit_files += 1
        total_lines += len(hits)

    mode = "AND" if args.mode_and else "OR"
    print(f"[search] 命中 {hit_files} 文件 / {total_lines} 行 ｜ 词: {' '.join(args.terms)}"
          f" ｜ 层: {args.layers} ｜ {mode}")
    return 0 if hit_files else 1


if __name__ == "__main__":
    sys.exit(main())
