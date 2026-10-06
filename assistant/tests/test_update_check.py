"""UC-01..UC-17：scripts/update_check.py 离线测试（零真网，Router 全 stub）。

用例命名约定：
- 「行为钉」= 断言当前真实行为（含缺陷），docstring 标注 BUG 与行号；
- 「修复门」= @pytest.mark.xfail(strict=True, reason="BUG ...") 断言期望行为，
  当前失败计 xfailed（绿），修复后 XPASS(strict) 变红提醒翻转本用例。
"""
import sys
import urllib.request
from datetime import date

import pytest
from conftest import cleaned_sha, make_page, write_manifest

TODAY = date.today()


# ---------------------------------------------------------------- 助手

def build_repo(ctx, uc, pages):
    """pages: {key: html}，key 如 'cas/doc-1'。

    挂 router 页面并写 sha 与线上页一致的 manifest（复刻 fetch_maodocs 入库口径：
    parse_page 后做清洗再哈希），返回 manifest dict（保持插入序）。
    """
    man = {}
    for key, html in pages.items():
        layer, slug = key.split("/", 1)
        url = f"{uc.BASE}/{layer}/{slug}.html"
        ctx["router"].pages[url] = html
        body, _, _ = uc.parse_page(html)
        man[key] = {"url": url, "sha256": cleaned_sha(body), "file": f"{layer}/{slug}.md"}
    write_manifest(ctx["state"], man)
    return man


def write_stale_manifest(ctx, uc, key="cas/doc-1"):
    """写一条 sha 必然不一致的 manifest 记录（用于触发『内容变更』路径）。"""
    layer, slug = key.split("/", 1)
    url = f"{uc.BASE}/{layer}/{slug}.html"
    ctx["router"].pages[url] = make_page()
    write_manifest(ctx["state"], {key: {"url": url, "sha256": "过期的哈希", "file": f"{layer}/{slug}.md"}})
    return url


def run(uc, monkeypatch, capsys, *argv):
    """设 argv 后驱动 uc.main()，返回 readouterr。"""
    monkeypatch.setattr(sys, "argv", ["update_check.py", *argv])
    uc.main()
    return capsys.readouterr()


def pending_file(uc):
    return uc.CHANGELOG / f"pending-{TODAY:%Y%m%d}.md"


def section(text, start, end):
    """截取 start 标题之后、end 标题之前的节内容。"""
    return text.split(start, 1)[1].split(end, 1)[0]


def stub_discover(monkeypatch, uc, result=()):
    """把 uc.discover 换成计数桩（默认恒返 []，即不发现新页）；返回层调用记录。"""
    calls = []

    def _d(listing, layer):
        calls.append(layer)
        return list(result)

    monkeypatch.setattr(uc, "discover", _d)
    return calls


# ---------------------------------------------------------------- manifest 门禁

def test_uc01_manifest_missing_exits_2(update_mod, monkeypatch, capsys):
    """[P0] manifest 文件缺失 → SystemExit(2)，stderr 含『manifest 不存在』。"""
    uc, ctx = update_mod
    assert not (ctx["state"] / "manifest.json").exists()
    with pytest.raises(SystemExit) as ei:
        run(uc, monkeypatch, capsys)
    assert ei.value.code == 2
    assert "manifest 不存在" in capsys.readouterr().err


def test_uc02_empty_manifest_exits_2(update_mod, monkeypatch, capsys):
    """[P0] manifest 为空 JSON {} 同样视为未初始化 → exit 2。"""
    uc, ctx = update_mod
    write_manifest(ctx["state"], {})
    with pytest.raises(SystemExit) as ei:
        run(uc, monkeypatch, capsys)
    assert ei.value.code == 2
    assert "manifest 不存在" in capsys.readouterr().err


def test_uc14_no_net_breaker_armed():
    """[P0] 零真网自证：conftest.no_net 熔断器在位，任何 urlopen 立即 AssertionError。"""
    with pytest.raises(AssertionError, match="熔断器"):
        urllib.request.urlopen("https://docs.maoyanqing.com/accounting/ent/cas/")


# ---------------------------------------------------------------- CLEAN 路径

def test_uc03_no_change_prints_clean_and_no_changelog(update_mod, monkeypatch, capsys):
    """[P0] 无变更 → stdout [CLEAN] 无变更，changelog 目录不创建。"""
    uc, ctx = update_mod
    build_repo(ctx, uc, {"cas/doc-1": make_page()})
    out = run(uc, monkeypatch, capsys).out
    assert "[CLEAN] 无变更" in out
    assert not (ctx["root"] / "changelog").exists()


def test_uc05_hint_line_only_change_is_clean(update_mod, monkeypatch, capsys):
    """[P0] 清洗 parity：线上页仅『约N字…分钟』行数字变化 → 不误报，[CLEAN]。"""
    uc, ctx = update_mod
    b1 = "发文机关：财政部\n约1234字，预计阅读15分钟\n第一条 为规范企业会计确认、计量和列报行为，制定本准则。"
    b2 = b1.replace("1234", "4321")  # 仅提示行数字不同
    page1, page2 = make_page(body=b1), make_page(body=b2)
    body1, _, _ = uc.parse_page(page1)
    body2, _, _ = uc.parse_page(page2)
    # parity 前提自证：原文不同、清洗后哈希一致
    assert body1 != body2
    assert cleaned_sha(body1) == cleaned_sha(body2)
    url = f"{uc.BASE}/cas/doc-1.html"
    ctx["router"].pages[url] = page2  # 线上是 b2
    write_manifest(ctx["state"], {"cas/doc-1": {"url": url, "sha256": cleaned_sha(body1), "file": "cas/doc-1.md"}})
    out = run(uc, monkeypatch, capsys).out
    assert "[CLEAN] 无变更" in out


def test_uc11_page_fetch_failure_partial(update_mod, monkeypatch, capsys):
    """[P1]（随修复重写）：2 页中 1 页 http 失败 → 不炸，[CLEAN] 带不可达警告，无 pending。"""
    uc, ctx = update_mod
    build_repo(ctx, uc, {"cas/doc-1": make_page(), "cas/doc-2": make_page()})
    del ctx["router"].pages[f"{uc.BASE}/cas/doc-1.html"]
    out = run(uc, monkeypatch, capsys).out
    assert f"{uc.BASE}/cas/doc-1.html" in ctx["router"].calls  # 确实尝试抓取过
    assert "[CLEAN] 无变更" in out
    assert "不可达" in out  # 部分失败显式警告
    assert not pending_file(uc).exists()


# ---------------------------------------------------------------- PENDING 路径

def test_uc04_body_change_pending(update_mod, monkeypatch, capsys):
    """[P0] 正文变化 → [PENDING] 新增 0 / 变更 1；变更节含 `- key → url`。"""
    uc, ctx = update_mod
    url = write_stale_manifest(ctx, uc)
    out = run(uc, monkeypatch, capsys).out
    assert "[PENDING] 新增 0 / 变更 1" in out
    text = pending_file(uc).read_text(encoding="utf-8")
    changed_sec = section(text, "## 内容变更", "## 处置流程")
    assert f"- cas/doc-1 → {url}" in changed_sec


def test_uc06_discover_new_url_listed(update_mod, monkeypatch, capsys):
    """[P0] discover 返回新 url → 『新增页面』节仅列该 url，新增 1 / 变更 0。"""
    uc, ctx = update_mod
    build_repo(ctx, uc, {"cas/doc-1": make_page()})
    new_url = f"{uc.BASE}/cas/new-2026.html"

    def fake_discover(listing, layer):
        return [new_url] if layer == "cas" else []

    monkeypatch.setattr(uc, "discover", fake_discover)
    out = run(uc, monkeypatch, capsys).out
    assert "[PENDING] 新增 1 / 变更 0" in out
    added_sec = section(pending_file(uc).read_text(encoding="utf-8"),
                        "## 新增页面（疑似新发布文件）", "## 内容变更")
    assert f"- {new_url}" in added_sec
    assert "- 无" not in added_sec


def test_uc12_pending_file_golden(update_mod, monkeypatch, capsys):
    """[P0] pending 文件 golden：1 added + 1 changed，固定章节结构与 4 步处置流程，无尾随换行。"""
    uc, ctx = update_mod
    url = write_stale_manifest(ctx, uc)
    new_url = f"{uc.BASE}/casg/new-doc.html"

    def fake_discover(listing, layer):
        return [new_url] if layer == "casg" else []

    monkeypatch.setattr(uc, "discover", fake_discover)
    run(uc, monkeypatch, capsys)
    p = pending_file(uc)
    assert p.name == f"pending-{TODAY:%Y%m%d}.md"
    text = p.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0] == f"# 待审变更清单 {TODAY}"
    assert "## 新增页面（疑似新发布文件）" in text
    assert f"- {new_url}" in text
    assert "## 内容变更（哈希不一致，需重抓并核对时效）" in text
    assert f"- cas/doc-1 → {url}" in text
    assert "## 处置流程" in text
    for step in ("1. 逐条核对（重点：status/supersedes 变化）",
                 "2. 确认后运行: python scripts/fetch_maodocs.py --layers <涉及层>",
                 "3. 人工核实的元数据写入 scripts/overrides.json",
                 "4. git commit 归档"):
        assert step in text
    assert not text.endswith("\n")  # write 前 '\n'.join，无尾随换行


def test_uc13_same_day_rerun_overwrites_identical(update_mod, monkeypatch, capsys):
    """[P2] 同日重跑：pending 文件被覆盖且内容一致。"""
    uc, ctx = update_mod
    write_stale_manifest(ctx, uc)
    run(uc, monkeypatch, capsys)
    first = pending_file(uc).read_text(encoding="utf-8")
    run(uc, monkeypatch, capsys)
    second = pending_file(uc).read_text(encoding="utf-8")
    assert first == second


def test_uc15_added_and_changed_both_listed(update_mod, monkeypatch, capsys):
    """[P1] added 与 changed 同非空：两节各有实体、计数 1/1，变更节不出现 - 无。"""
    uc, ctx = update_mod
    url = write_stale_manifest(ctx, uc)
    new_url = f"{uc.BASE}/casc/new-case.html"

    def fake_discover(listing, layer):
        return [new_url] if layer == "casc" else []

    monkeypatch.setattr(uc, "discover", fake_discover)
    out = run(uc, monkeypatch, capsys).out
    assert "[PENDING] 新增 1 / 变更 1" in out
    text = pending_file(uc).read_text(encoding="utf-8")
    added_sec = section(text, "## 新增页面（疑似新发布文件）", "## 内容变更")
    changed_sec = section(text, "## 内容变更", "## 处置流程")
    assert f"- {new_url}" in added_sec
    assert "- 无" not in added_sec
    assert f"- cas/doc-1 → {url}" in changed_sec
    assert "- 无" not in changed_sec


def test_uc16_added_only_changed_section_single_wu(update_mod, monkeypatch, capsys):
    """[P1] 仅 added：变更节恰一行 `- 无`（对照 UC-07 证明重复 bug 只在新增节）。"""
    uc, ctx = update_mod
    build_repo(ctx, uc, {"cas/doc-1": make_page()})
    new_url = f"{uc.BASE}/casq/new-q.html"

    def fake_discover(listing, layer):
        return [new_url] if layer == "casq" else []

    monkeypatch.setattr(uc, "discover", fake_discover)
    run(uc, monkeypatch, capsys)
    changed_sec = section(pending_file(uc).read_text(encoding="utf-8"),
                          "## 内容变更", "## 处置流程")
    assert changed_sec.count("- 无") == 1


# ---------------------------------------------------------------- 原修复门（已修复翻正）

def test_uc07_added_section_single_wu_when_empty(update_mod, monkeypatch, capsys):
    """[P0]（原修复门，已修复）added 空 + changed 非空 → 『新增页面』节恰一行 `- 无`。"""
    uc, ctx = update_mod
    write_stale_manifest(ctx, uc)  # changed 非空，added 为空
    run(uc, monkeypatch, capsys)
    added_sec = section(pending_file(uc).read_text(encoding="utf-8"),
                        "## 新增页面（疑似新发布文件）", "## 内容变更")
    assert added_sec.count("- 无") == 1


def test_uc11b_total_outage_is_not_clean(update_mod, monkeypatch, capsys):
    """[P1]（原修复门，已修复）router 全空 + discover→[]（全断网）→ [UNREACHABLE]，非 [CLEAN]。"""
    uc, ctx = update_mod
    write_manifest(ctx["state"],
                   {"cas/doc-1": {"url": f"{uc.BASE}/cas/doc-1.html", "sha256": "x", "file": "cas/doc-1.md"}})
    stub_discover(monkeypatch, uc)
    out = run(uc, monkeypatch, capsys).out
    assert "[UNREACHABLE]" in out
    assert "[CLEAN]" not in out


# ---------------------------------------------------------------- --sample 语义

def test_uc08_sample_limits_http_but_not_discover(update_mod, monkeypatch, capsys):
    """[P1] --sample 2：manifest 3 条有序 → 只 http 前 2 页；discover 仍跑全 5 层。"""
    uc, ctx = update_mod
    man = build_repo(ctx, uc, {"cas/a1": make_page(), "casg/b2": make_page(), "casi/c3": make_page()})
    urls = [rec["url"] for rec in man.values()]
    d_calls = stub_discover(monkeypatch, uc)
    out = run(uc, monkeypatch, capsys, "--sample", "2").out
    assert "[CLEAN] 无变更" in out
    assert ctx["router"].calls == urls[:2]      # 只抓前 2 页
    assert len(d_calls) == len(uc.LAYERS)       # discover 与 sample 无关，全层 5 次


def test_uc09_sample_beyond_size_full_scan(update_mod, monkeypatch, capsys):
    """[P2] --sample 99 超出条数 → 切片安全，全量不崩。"""
    uc, ctx = update_mod
    man = build_repo(ctx, uc, {"cas/a1": make_page(), "casg/b2": make_page(), "casi/c3": make_page()})
    urls = [rec["url"] for rec in man.values()]
    stub_discover(monkeypatch, uc)
    out = run(uc, monkeypatch, capsys, "--sample", "99").out
    assert ctx["router"].calls == urls
    assert "[CLEAN] 无变更" in out


def test_uc10_sample_zero_bypasses_to_full(update_mod, monkeypatch, capsys):
    """[P2 行为钉] BUG uc L47：`if args.sample:` 把 0 判 falsy → --sample 0 旁路为全量，无参数校验。"""
    uc, ctx = update_mod
    man = build_repo(ctx, uc, {"cas/a1": make_page(), "casg/b2": make_page(), "casi/c3": make_page()})
    urls = [rec["url"] for rec in man.values()]
    stub_discover(monkeypatch, uc)
    run(uc, monkeypatch, capsys, "--sample", "0")
    assert ctx["router"].calls == urls  # falsy 旁路：0 页都没省，等价全量


# ---------------------------------------------------------------- 健壮性行为钉

def test_uc17_manifest_missing_sha256_keyraises(update_mod, monkeypatch, capsys):
    """[P2 行为钉] BUG uc L50：`rec["sha256"]` 直接下标访问，记录缺 sha256 键时
    无任何上下文的 KeyError 裸崩（不指明哪条记录坏）。"""
    uc, ctx = update_mod
    url = f"{uc.BASE}/cas/doc-1.html"
    ctx["router"].pages[url] = make_page()
    write_manifest(ctx["state"], {"cas/doc-1": {"url": url, "file": "cas/doc-1.md"}})  # 缺 sha256
    with pytest.raises(KeyError):
        run(uc, monkeypatch, capsys)
