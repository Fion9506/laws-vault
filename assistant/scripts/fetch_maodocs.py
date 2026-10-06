#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MaoDocs (docs.maoyanqing.com) 会计准则五层知识抓取器 — 纯标准库，零依赖。

层: cas 准则全文 / casg 应用指南 / casi 准则解释 / casc 应用案例 / casq 实施问答
用法:
  python fetch_maodocs.py --layers cas,casi          # 先抓核心两层
  python fetch_maodocs.py --layers casg,casc,casq    # 再抓其余三层
  python fetch_maodocs.py --layers cas --limit 3     # 试跑
输出: laws-vault/<layer>/<slug>.md（YAML front-matter + 正文）+ scripts/state/manifest.json
"""
import argparse
import hashlib
import html as htmllib
import json
import re
import sys
import time
import urllib.request
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

BASE = "https://docs.maoyanqing.com/accounting/ent"
LAYERS = {
    "cas": f"{BASE}/cas/",
    "casg": f"{BASE}/casg/",
    "casi": f"{BASE}/casi/",
    "casc": f"{BASE}/casc/",
    "casq": f"{BASE}/casq/",
}
ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "scripts" / "state"
MANIFEST = STATE_DIR / "manifest.json"
OVERRIDES = Path(__file__).with_name("overrides.json")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) laws-vault/0.1 personal-research"}
DELAY = 0.4

# 已核实的元数据修正（人工确认过的事实，优先级高于自动抽取）
DEFAULT_OVERRIDES = {
    "cas/30b": {
        "doc_number": "财会〔2026〕11号",
        "status": "尚未生效",
        "effective_date": "2027-01-01",
        "supersedes": "财会〔2014〕7号（CAS30 2014版）",
        "scope_note": "境内外同时上市企业 2027-01-01 起执行；分主体分批推迟，2026 年报仍适用 2014 版",
    },
    "cas/25b": {
        "status": "已废止",
        "superseded_by": "财会〔2020〕20号（CAS25 保险合同 2020版）",
    },
}

DOCNO_RE = re.compile(r"[\u4e00-\u9fa5A-Za-z]{2,14}?[〔\[](\d{4})[〕\]]\s*(\d+)\s*号")

SKIP_TAGS = {"script", "style", "nav", "header", "footer", "aside"}

def http_get(url, retries=1):
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:
            if i >= retries:
                print(f"[FAIL] {url} :: {e}", file=sys.stderr)
                return None
            time.sleep(2)


class PageText(HTMLParser):
    """提取 <main> 内正文，标题降级为 markdown 井号，其余按块换行。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_main = False
        self.depth = 0
        self.skip = 0
        self.lines = []
        self._buf = []
        self._heading = 0
        self.title = ""

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self.skip += 1
            return
        if self.skip:
            return
        if tag == "main":
            self.in_main = True
            return
        if not self.in_main:
            if tag == "title":
                self._intitle = True
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._flush()
            self._heading = int(tag[1])
        elif tag in ("p", "li", "tr", "br", "div", "table", "blockquote"):
            self._flush()

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag == "title":
            self._intitle = False
            return
        if tag == "main":
            self.in_main = False
        if not self.in_main:
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = "".join(self._buf).strip()
            if text:
                self.lines.append("#" * self._heading + " " + text)
            self._buf, self._heading = [], 0
        elif tag in ("p", "li", "tr", "div", "table", "blockquote"):
            self._flush()

    def handle_data(self, data):
        if self.skip:
            return
        if getattr(self, "_intitle", False):
            self.title = self.title + data
            return
        if self.in_main:
            self._buf.append(data)

    def _flush(self):
        text = "".join(self._buf).strip()
        if text:
            self.lines.append(text)
        self._buf = []

    def result(self):
        self._flush()
        body = "\n\n".join(self.lines)
        return re.sub(r"\n{3,}", "\n\n", body).strip()


def parse_page(html_text):
    p = PageText()
    p._intitle = False
    try:
        p.feed(html_text)
    except Exception as e:
        print(f"[WARN] parse error: {e}", file=sys.stderr)
    m = re.search(r'meta[^>]+name="article:modified_time"[^>]+content="([^"]+)"', html_text)
    return p.result(), (p.title or "").replace(" | 审计文库（MaoDocs）", "").strip(), (m.group(1) if m else "")


def discover(listing_url, layer):
    html_text = http_get(listing_url)
    if not html_text:
        return []
    hrefs = re.findall(r'href="(/accounting/ent/%s/[^"#?]+\.html)"' % layer, html_text)
    seen, out = set(), []
    for h in hrefs:
        if h not in seen and not re.search(r"/index\d*\.html$", h):
            seen.add(h)
            out.append("https://docs.maoyanqing.com" + h)
    return out


def load_overrides():
    if OVERRIDES.exists():
        data = json.loads(OVERRIDES.read_text(encoding="utf-8"))
        merged = dict(DEFAULT_OVERRIDES)
        merged.update(data)  # 文件键逐键覆盖默认，默认其余保留
        return merged
    return DEFAULT_OVERRIDES


DOCNO_WL_RE = re.compile(
    r"(?:财会|财办会|财会便|财办|财税|财金|金规|银保监办发|证监会计|证监会|国税发|国税函)"
    r"[〔\[](\d{4})[〕\]]\s*(\d+)\s*号")


def load_manifest():
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {}


def slug_key(layer, url):
    path = url.split(f"/{layer}/", 1)[1].replace(".html", "")
    return f"{layer}/{path.replace('/', '__')}"


def fetch_layer(layer, limit=None):
    urls = discover(LAYERS[layer], layer)
    if limit:
        urls = urls[:limit]
    print(f"[{layer}] discovered {len(urls)} pages")
    manifest = load_manifest()
    overrides = load_overrides()
    outdir = ROOT / layer
    outdir.mkdir(exist_ok=True)
    ok = fail = 0
    for url in urls:
        key = slug_key(layer, url)
        html_text = http_get(url)
        if not html_text:
            fail += 1
            continue
        body, title, modified = parse_page(html_text)
        if len(body) < 200:
            print(f"[SKIP-EMPTY] {key}", file=sys.stderr)
            fail += 1
            continue
        body = re.sub(r"^约\s*\d+\s*字.*分钟$\n?", "", body, flags=re.M).strip()
        m = DOCNO_WL_RE.search(body[:3000]) or DOCNO_RE.search(body[:3000])
        doc_number = m.group(0) if m else ""
        year = m.group(1) if m else ""
        org_x = (re.search(r"发文机关[：:]\s*([^\n]+)", body[:2500]) or type("R", (), {"group": lambda s, n: ""})()).group(1).strip()
        issue_x = (re.search(r"发布日期[：:]\s*(\d{4}-\d{2}-\d{2})", body[:2500]) or type("R", (), {"group": lambda s, n: ""})()).group(1).strip()
        eff_x = (re.search(r"生效日期[：:]\s*(\d{4}-\d{2}-\d{2})", body[:2500]) or type("R", (), {"group": lambda s, n: ""})()).group(1).strip()
        status_x = (re.search(r"时效性[：:]\s*([^\n]+)", body[:2500]) or type("R", (), {"group": lambda s, n: ""})()).group(1).strip()
        status_map = {"现行有效": "有效", "有效": "有效", "已废止": "已废止", "已失效": "已废止",
                      "尚未生效": "尚未生效", "已被修改": "已修改", "部分失效": "部分废止"}
        status_x = status_map.get(status_x, status_x)
        ov = overrides.get(key, {})
        fm = {
            "doc_id": ov.get("doc_number", doc_number or key),
            "title": title or key,
            "layer": layer,
            "level": {"cas": "具体准则", "casg": "应用指南", "casi": "准则解释",
                      "casc": "应用案例", "casq": "实施问答"}[layer],
            "doc_number": ov.get("doc_number", doc_number),
            "year": ov.get("year", year),
            "issue_date": ov.get("issue_date", issue_x),
            "effective_date": ov.get("effective_date", eff_x),
            "status": ov.get("status", status_x or ("有效" if layer == "casg" else "待核")),
            "supersedes": ov.get("supersedes", ""),
            "superseded_by": ov.get("superseded_by", ""),
            "org": ov.get("org", org_x or ("财政部" if layer in ("cas", "casg", "casi", "casc", "casq") else "")),
            "source_url": url,
            "site_modified": modified,
            "checked_at": str(date.today()),
            "fetched_at": str(date.today()),
        }
        if ov.get("scope_note"):
            fm["scope_note"] = ov["scope_note"]  # 人工备注（如 30b 分批生效范围）只在提供时输出
        fm_lines = ["---"] + [f"{k}: {v}" for k, v in fm.items()] + ["---", ""]
        text = "\n".join(fm_lines) + body + "\n"
        sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
        out = outdir / (key.split("/", 1)[1] + ".md")
        out.write_text(text, encoding="utf-8")
        manifest[key] = {"url": url, "title": fm["title"], "sha256": sha,
                         "file": str(out.relative_to(ROOT)), "fetched_at": fm["fetched_at"]}
        ok += 1
        print(f"[OK] {key} ({len(body)} chars)")
        STATE_DIR.mkdir(exist_ok=True, parents=True)
        MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(DELAY)
    print(f"[{layer}] done ok={ok} fail={fail}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layers", default="cas,casi")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    for layer in args.layers.split(","):
        layer = layer.strip()
        if layer not in LAYERS:
            print(f"unknown layer {layer}", file=sys.stderr)
            sys.exit(2)
        fetch_layer(layer, args.limit)


if __name__ == "__main__":
    main()
