#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""laws-vault 更新哨兵 — 对比 manifest 哈希与线上页面，产出待审清单。

用法:
  python scripts/update_check.py            # 全量核查（页面多时约数分钟）
  python scripts/update_check.py --sample 15 # 抽查 15 页
输出:
  [CLEAN] 无变更（部分页不可达时附警告）／ [UNREACHABLE] 全部不可达（判定无效）
  changelog/pending-YYYYMMDD.md（新增/变更 两节，人工确认后重抓）
"""
import argparse
import hashlib
import json
import re
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fetch_maodocs import BASE, LAYERS, UA, http_get, parse_page, discover, load_manifest, slug_key

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "changelog"
DELAY = 0.3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=None)
    args = ap.parse_args()
    manifest = load_manifest()
    if not manifest:
        print("manifest 不存在，请先运行 fetch_maodocs.py", file=sys.stderr)
        sys.exit(2)

    changed, added = [], []
    # 1) 发现新链接
    for layer, listing in LAYERS.items():
        for url in discover(listing, layer):
            if slug_key(layer, url) not in manifest:
                added.append(url)
        time.sleep(DELAY)

    # 2) 已入库页面哈希比对
    items = list(manifest.items())
    if args.sample:
        items = items[: args.sample]
    unreachable = 0
    for key, rec in items:
        html_text = http_get(rec["url"])
        if not html_text:
            unreachable += 1
            continue
        body, _, _ = parse_page(html_text)
        body = re.sub(r"^约\s*\d+\s*字.*分钟$\n?", "", body, flags=re.M).strip()
        sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
        if sha != rec["sha256"]:
            changed.append({"key": key, "url": rec["url"], "file": rec["file"]})
        time.sleep(DELAY)

    if not changed and not added:
        if items and unreachable == len(items):
            print(f"[UNREACHABLE] {unreachable}/{len(items)} 页全部不可达，无法判定是否有变更"
                  "（检查网络/上游后重试）")
            return
        if unreachable:
            print(f"[CLEAN] 无变更（注意：{unreachable}/{len(items)} 页不可达未核验）")
            return
        print("[CLEAN] 无变更")
        return
    CHANGELOG.mkdir(exist_ok=True)
    out = CHANGELOG / f"pending-{date.today():%Y%m%d}.md"
    lines = [f"# 待审变更清单 {date.today()}", ""]
    lines.append("## 新增页面（疑似新发布文件）")
    lines += [f"- {u}" for u in added] or ["- 无"]
    lines.append("")
    lines.append("## 内容变更（哈希不一致，需重抓并核对时效）")
    if changed:
        lines += [f"- {c['key']} → {c['url']}" for c in changed]
    else:
        lines.append("- 无")
    lines += ["", "## 处置流程", "1. 逐条核对（重点：status/supersedes 变化）",
              "2. 确认后运行: python scripts/fetch_maodocs.py --layers <涉及层>",
              "3. 人工核实的元数据写入 scripts/overrides.json",
              "4. git commit 归档"]
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[PENDING] 新增 {len(added)} / 变更 {len(changed)} → {out}")
    if unreachable:
        print(f"[WARN] {unreachable}/{len(items)} 页不可达未核验，本次结论不完整")


if __name__ == "__main__":
    main()
