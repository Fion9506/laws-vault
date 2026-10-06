#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""laws-vault 体检脚本 — 语料完整性/元数据质量/git/规则技能/MCP/时效，纯标准库。"""
import json
import os
import socket
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAYERS = ["cas", "casg", "casi", "casc", "casq"]


def fm(path):
    out = {}
    lines = path.read_text(encoding="utf-8-sig").splitlines()  # utf-8-sig 兼容 BOM 头
    if lines and lines[0].strip() == "---":
        for ln in lines[1:]:
            if ln.strip() == "---":
                break
            if ":" in ln:
                k, v = ln.split(":", 1)
                out[k.strip()] = v.strip()
    return out


def sh(cmd, cwd=None):
    try:
        return subprocess.run(cmd, cwd=cwd or ROOT, capture_output=True,
                              text=True, encoding="utf-8", errors="ignore").stdout.strip()
    except Exception:
        return ""


def main():
    print(f"# laws-vault 体检 {date.today()}")
    print("\n## 语料层")
    manifest = {}
    mp = ROOT / "scripts/state/manifest.json"
    if mp.exists():
        try:
            manifest = json.loads(mp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            print("- manifest.json 损坏：按空基线对账（重跑 fetch_maodocs.py 重建）")
            manifest = {}
    for layer in LAYERS:
        d = ROOT / layer
        disk = len(list(d.glob("*.md"))) if d.exists() else 0
        man = sum(1 for k in manifest if k.split("/")[0] == layer)
        flag = "OK" if disk == man else "MISMATCH"
        print(f"- {layer}: 磁盘 {disk} / manifest {man} [{flag}]")

    print("\n## 元数据质量")
    stale = miss_no = pending = bad = 0
    today = date.today()
    for layer in LAYERS:
        for f in (ROOT / layer).glob("*.md"):
            try:
                m = fm(f)
            except (UnicodeDecodeError, OSError):
                bad += 1
                continue
            if m.get("status") == "待核":
                pending += 1
            if layer in ("cas", "casi") and not m.get("doc_number"):
                miss_no += 1
            try:
                ca = datetime.strptime(m.get("checked_at", "2000-01-01"), "%Y-%m-%d").date()
                if (today - ca).days > 14:
                    stale += 1
            except ValueError:
                stale += 1
    if bad:
        print(f"- 不可读文件：{bad}（编码损坏，已跳过统计，人工排查）")
    print(f"- status=待核：{pending} ｜ cas/casi 缺文号：{miss_no} ｜ checked_at>14天：{stale}/{sum(len(list((ROOT/l).glob('*.md'))) for l in LAYERS)}")

    print("\n## 配置")
    rules = ["project_rules.md", "00-citation-discipline.md", "01-query-transcription.md",
             "02-vault-usage.md", "03-vault-update.md"]
    missing_rules = [r for r in rules if not (ROOT / ".trae/rules" / r).exists()]
    print(f"- 规则文件：{len(rules)-len(missing_rules)}/{len(rules)}" + (f" 缺 {missing_rules}" if missing_rules else ""))
    skills = ["vault-update", "case-analysis", "mcp-ops", "health-check"]
    missing_skills = [s for s in skills if not (ROOT / ".trae/skills" / s / "SKILL.md").exists()]
    print(f"- 技能：{len(skills)-len(missing_skills)}/{len(skills)}" + (f" 缺 {missing_skills}" if missing_skills else ""))
    dirty = [l for l in sh(["git", "status", "--porcelain"]).splitlines() if l.strip()]
    print(f"- git 未提交变更：{len(dirty)} 条")

    print("\n## 服务")
    s = socket.socket()
    s.settimeout(1)
    flk_up = s.connect_ex(("127.0.0.1", 18062)) == 0
    s.close()
    print(f"- flk-mcp(18062)：{'运行中' if flk_up else '未启动（scripts/start_mcp.bat）'}")
    has_key = bool(os.environ.get("SILICONFLOW_API_KEY"))
    print(f"- SILICONFLOW_API_KEY：{'已设置' if has_key else '未设置（local-rag 语义检索未接线）'}")
    lt = ROOT / "tax/lawtext"
    if lt.exists():
        last = sh(["git", "log", "-1", "--format=%cs"], cwd=lt)
        print(f"- lawtext 同步：最后提交 {last or '未知'}")
    else:
        print("- lawtext 同步：tax/lawtext 缺失")

    print("\n## 优化空间")
    opts = []
    if pending > 10:
        opts.append(f"待核 {pending} 份：flk-mcp 或官方源批量核验后固化 overrides.json")
    if miss_no:
        opts.append(f"cas/casi 缺文号 {miss_no} 份：人工核对补齐")
    if not (ROOT / "policy").exists() or not any((ROOT / "policy").glob("*")):
        opts.append("policy/ 为空：公司执行办法未入库（分层引用需要）")
    if not has_key:
        opts.append("SILICONFLOW_API_KEY 未设：注册 cloud.siliconflow.cn 后接线 local-rag 语义检索")
    if dirty:
        opts.append(f"{len(dirty)} 条未提交变更：git add -A && git commit")
    opts.append("监管指引层（securities/garr）未接入：fetch_maodocs.py LAYERS 加一条即可扩层")
    for i, o in enumerate(opts, 1):
        print(f"{i}. {o}")


if __name__ == "__main__":
    main()
