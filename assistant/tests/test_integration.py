# laws-vault 端到端集成测试：fetch_maodocs → update_check → health_check 全链路（离线沙箱）。
# 约定：行为钉 = 断言当前真实行为（含缺陷，注明 BUG 与行号）；
#       修复门 = @pytest.mark.xfail(strict=True) 断言期望行为（修复后 XPASS 变红提醒翻转）。
import importlib
import io
import json
import os
import re
import sys
import time
import types
import urllib.request

import pytest
from conftest import (
    cleaned_sha,
    make_listing,
    make_page,
    read_front_matter,
    write_md,
)

BASE = "https://docs.maoyanqing.com/accounting/ent"
A1_PAGES = {"cas": ["2026n1", "2026n2"], "casq": ["q2026a", "q2026b"]}


# ---------------------------------------------------------------- 助手

def page_url(layer, name):
    return f"{BASE}/{layer}/{name}.html"


def seed_pages(fm_mod, ctx, spec):
    """向 Router 登记 listing 与各贞页面。spec: {layer: [贞名]}。"""
    for layer, names in spec.items():
        ctx["router"].pages[fm_mod.LAYERS[layer]] = make_listing(layer, names)
        for n in names:
            ctx["router"].pages[page_url(layer, n)] = make_page(title=n)


def seed_and_fetch(fm_mod, ctx, spec=None):
    spec = spec if spec is not None else A1_PAGES
    seed_pages(fm_mod, ctx, spec)
    for layer in spec:
        fm_mod.fetch_layer(layer)
    return spec


def revised_body():
    """与 make_page 默认正文不同、仍满足元数据抽取的最小修订正文。"""
    return (
        "发文机关：财政部\n发布日期：2026-01-01\n生效日期：2026-02-01\n时效性：现行有效\n"
        "财会〔2026〕1号\n各省、自治区、直辖市财政厅（局）：\n"
        + "第一条 为规范企业会计确认、计量和列报行为，制定本准则。" * 12
        + "\n第二条 修订新增条款，正文实质变化。"
    )


def run_uc(uc, monkeypatch):
    """uc.main() 内部 argparse 读 sys.argv，必须清空避免吃进 pytest 参数。"""
    monkeypatch.setattr(sys, "argv", ["update_check.py"])
    uc.main()


def pending_text(root):
    files = list((root / "changelog").glob("pending-*.md"))
    assert len(files) == 1, files
    return files[0].read_text(encoding="utf-8")


class _ClosedSock:
    """health_check 服务探测桩：端口永远未监听。"""

    def settimeout(self, t):
        pass

    def connect_ex(self, addr):
        return 1

    def close(self):
        pass


def load_health(monkeypatch, root):
    """复刻 health_mod 的模块装载，但 ROOT 直接指向集成沙箱 root；stub git/socket/env。"""
    hc = importlib.reload(importlib.import_module("health_check"))
    monkeypatch.setattr(hc, "ROOT", root)
    monkeypatch.setattr(hc, "sh", lambda *a, **k: "")  # 跳过 git 子进程
    monkeypatch.setattr(hc, "socket", types.SimpleNamespace(socket=lambda: _ClosedSock()))
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
    return hc


def layer_line(out, layer):
    m = re.search(rf"- {layer}: 磁盘 (\d+) / manifest (\d+) \[(\w+)\]", out)
    assert m, f"未找到 {layer} 层对账行：\n{out}"
    return m.group(1), m.group(2), m.group(3)


# ---------------------------------------------------------------- A 干净链路 / 更新哨兵

def test_a1_clean_chain_fetch_update_clean(sandbox, update_mod, capsys, monkeypatch):
    """[P0] 干净链路：两层各 2 贞 fetch → update_check 全绿 [CLEAN]，changelog 不创建。"""
    fm_mod, ctx = sandbox
    uc, _ = update_mod
    seed_and_fetch(fm_mod, ctx)

    for layer, names in A1_PAGES.items():
        for n in names:
            p = ctx["root"] / layer / f"{n}.md"
            assert p.exists(), p
            fm_dict, body = read_front_matter(p)
            assert fm_dict["doc_id"] == "财会〔2026〕1号"
            assert fm_dict["status"] == "有效"  # 时效性：现行有效 → status_map 归一
            assert fm_dict["source_url"] == page_url(layer, n)
            assert len(body) > 0

    manifest = json.loads(fm_mod.MANIFEST.read_text(encoding="utf-8"))
    assert set(manifest) == {f"{l}/{n}" for l, ns in A1_PAGES.items() for n in ns}

    run_uc(uc, monkeypatch)
    out = capsys.readouterr().out
    assert "[CLEAN] 无变更" in out
    assert not (ctx["root"] / "changelog").exists()


def test_a2_pending_added_section_single_none_line(sandbox, update_mod, capsys, monkeypatch):
    """[P0]（原修复门，已修复）改 1 贞 body → pending『新增页面』节恰一行『- 无』。"""
    fm_mod, ctx = sandbox
    uc, _ = update_mod
    seed_and_fetch(fm_mod, ctx)

    ctx["router"].pages[page_url("cas", "2026n1")] = make_page(
        title="2026n1", body=revised_body())
    run_uc(uc, monkeypatch)
    out = capsys.readouterr().out
    assert "[PENDING] 新增 0 / 变更 1" in out

    text = pending_text(ctx["root"])
    assert "cas/2026n1 →" in text  # 内容变更节正确列出（当前行为本就正确）
    added_sec = text.split("## 新增页面（疑似新发布文件）", 1)[1].split("## ", 1)[0]
    added_lines = [ln for ln in added_sec.splitlines() if ln.strip()]
    assert added_lines == ["- 无"]  # BUG：当前为 ['- 无', '- 无']


def test_a3_new_page_reported_as_added(sandbox, update_mod, capsys, monkeypatch):
    """[P0] 新增路径：listing 加 1 新 href → pending『新增页面』节含新 URL，无误报变更。"""
    fm_mod, ctx = sandbox
    uc, _ = update_mod
    seed_and_fetch(fm_mod, ctx)

    ctx["router"].pages[fm_mod.LAYERS["cas"]] = make_listing(
        "cas", ["2026n1", "2026n2", "2026n3"])
    run_uc(uc, monkeypatch)
    out = capsys.readouterr().out
    assert "[PENDING] 新增 1 / 变更 0" in out

    text = pending_text(ctx["root"])
    added_sec = text.split("## 新增页面（疑似新发布文件）", 1)[1].split("## ", 1)[0]
    added_lines = [ln for ln in added_sec.splitlines() if ln.strip()]
    assert added_lines == [f"- {page_url('cas', '2026n3')}"]  # 不再有『- 无』行
    changed_sec = text.split("## 内容变更", 1)[1]
    assert "- 无" in changed_sec
    assert not (ctx["root"] / "cas" / "2026n3.md").exists()  # 哨兵只发现，不抓取


def test_a4_missing_manifest_exit_2(update_mod, capsys, monkeypatch):
    """[P1] manifest 缺失（空沙箱）→ uc.main() SystemExit 2 + stderr 提示。"""
    uc, _ = update_mod
    monkeypatch.setattr(sys, "argv", ["update_check.py"])
    with pytest.raises(SystemExit) as ei:
        uc.main()
    assert ei.value.code == 2
    assert "manifest 不存在" in capsys.readouterr().err


def test_a5_health_reconcile(sandbox, monkeypatch, capsys):
    """[P0] health 对账：fetch 后各层 [OK]；删 md → [MISMATCH]；手工待核件计数 +1。"""
    fm_mod, ctx = sandbox
    seed_and_fetch(fm_mod, ctx)
    hc = load_health(monkeypatch, ctx["root"])

    hc.main()
    out = capsys.readouterr().out
    for layer in ("cas", "casq"):
        disk, man, flag = layer_line(out, layer)
        assert (disk, man, flag) == ("2", "2", "OK")

    (ctx["root"] / "cas" / "2026n1.md").unlink()
    hc.main()
    out2 = capsys.readouterr().out
    assert layer_line(out2, "cas") == ("1", "2", "MISMATCH")
    pending_before = int(re.search(r"status=待核：(\d+)", out2).group(1))

    write_md(ctx["root"], "casq", "manual", {"doc_id": "手工件", "status": "待核"})
    hc.main()
    out3 = capsys.readouterr().out
    pending_after = int(re.search(r"status=待核：(\d+)", out3).group(1))
    assert pending_after == pending_before + 1


def test_a6_idempotent_rerun(sandbox, capsys):
    """[P1] 幂等重跑：同输入连跑两次 fetch_layer，md 内容与 manifest 完全一致。"""
    fm_mod, ctx = sandbox
    seed_and_fetch(fm_mod, ctx, {"cas": ["2026n1", "2026n2"]})

    man_before = json.loads(fm_mod.MANIFEST.read_text(encoding="utf-8"))
    md_before = {p.name: p.read_text(encoding="utf-8")
                 for p in sorted((ctx["root"] / "cas").glob("*.md"))}

    fm_mod.fetch_layer("cas")

    man_after = json.loads(fm_mod.MANIFEST.read_text(encoding="utf-8"))
    md_after = {p.name: p.read_text(encoding="utf-8")
                for p in sorted((ctx["root"] / "cas").glob("*.md"))}
    assert man_after == man_before  # sha/fetched_at/file 均不变
    assert md_after == md_before
    assert "done ok=2 fail=0" in capsys.readouterr().out


# ---------------------------------------------------------------- B 哨兵健壮性

def test_b1_unreachable_listings_not_clean(sandbox, update_mod, capsys, monkeypatch):
    """[P0]（原修复门，已修复）站点整体不可达 → [UNREACHABLE]，不误报 [CLEAN]。"""
    fm_mod, ctx = sandbox
    uc, _ = update_mod
    seed_and_fetch(fm_mod, ctx)
    ctx["router"].pages.clear()  # 全部 404/超时

    run_uc(uc, monkeypatch)
    out = capsys.readouterr().out
    assert "不可达" in out  # 期望：显式不可达信号
    assert "[CLEAN] 无变更" not in out


def test_b2_partial_page_failure(sandbox, capsys):
    """[P1] 4 贞挂 3（未登记→http_get None）→ ok=3 fail=1，manifest 只 3 键。"""
    fm_mod, ctx = sandbox
    names = ["a1", "a2", "a3", "a4"]
    ctx["router"].pages[fm_mod.LAYERS["cas"]] = make_listing("cas", names)
    for n in names[:3]:
        ctx["router"].pages[page_url("cas", n)] = make_page(title=n)

    fm_mod.fetch_layer("cas")
    assert "done ok=3 fail=1" in capsys.readouterr().out
    manifest = json.loads(fm_mod.MANIFEST.read_text(encoding="utf-8"))
    assert set(manifest) == {"cas/a1", "cas/a2", "cas/a3"}


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_b3_retry_semantics(monkeypatch, capsys):
    """[P2] 重试语义：retries=1 首挂次成 → 返回内容恰 2 次调用；全挂 → None + stderr [FAIL]。"""
    # 独立重载取回未被 Router 顶替的真 http_get（本用例不触路径常量）
    fm_mod = importlib.reload(importlib.import_module("fetch_maodocs"))
    monkeypatch.setattr(time, "sleep", lambda s: None)  # 跳过 2s 重试间隔

    payload = "<html><body>重试后成功</body></html>".encode()
    calls = []

    def flaky(req, timeout=None):
        calls.append(1)
        if len(calls) == 1:
            raise TimeoutError("模拟首调超时")
        return _FakeResp(payload)

    # 测试级补丁覆盖 no_net 熔断器（conftest 明确允许）
    monkeypatch.setattr(urllib.request, "urlopen", flaky)
    assert fm_mod.http_get("https://example.com/flaky", retries=1) == payload.decode("utf-8")
    assert len(calls) == 2

    dead_calls = []

    def dead(req, timeout=None):
        dead_calls.append(1)
        raise TimeoutError("持续超时")

    monkeypatch.setattr(urllib.request, "urlopen", dead)
    assert fm_mod.http_get("https://example.com/dead", retries=1) is None
    assert len(dead_calls) == 2
    err = capsys.readouterr().err
    assert "[FAIL]" in err
    assert "example.com/dead" in err


def test_b4_unreachable_listing_no_false_added(sandbox, update_mod, capsys, monkeypatch):
    """[P1 行为钉] listing 不可达 → discover 返回 [] → added 空，不误报新增（当前即正确）。"""
    fm_mod, ctx = sandbox
    uc, _ = update_mod
    seed_and_fetch(fm_mod, ctx)
    for listing in list(fm_mod.LAYERS.values()):
        ctx["router"].pages.pop(listing, None)  # 仅摘掉 5 个层目录页，内容页保持可达

    run_uc(uc, monkeypatch)
    out = capsys.readouterr().out
    assert "[CLEAN] 无变更" in out  # added 空 → 不产生 pending（listing 失败不误报新增）
    assert not (ctx["root"] / "changelog").exists()


# ---------------------------------------------------------------- C 抓取健壮性

def test_c1_empty_or_mainless_pages(sandbox, capsys):
    """[P0] 空页 / 无 <main> 页 → 计 fail（SKIP-EMPTY），不写文件不进 manifest。"""
    fm_mod, ctx = sandbox
    ctx["router"].pages[fm_mod.LAYERS["cas"]] = make_listing("cas", ["empty1", "nomain"])
    ctx["router"].pages[page_url("cas", "empty1")] = "<html><body></body></html>"
    ctx["router"].pages[page_url("cas", "nomain")] = (
        "<html><head><title>无正文页 | 审计文库（MaoDocs）</title></head>"
        "<body><nav>导航噪声</nav><p>main 之外的段落不计数</p>"
        "<footer>页脚噪声</footer></body></html>")

    fm_mod.fetch_layer("cas")
    ro = capsys.readouterr()
    assert "done ok=0 fail=2" in ro.out
    assert ro.err.count("[SKIP-EMPTY]") == 2
    assert list((ctx["root"] / "cas").glob("*.md")) == []
    assert not fm_mod.MANIFEST.exists()


def test_c2_parse_exception_tolerated(sandbox, monkeypatch, capsys):
    """[P1] 单贞解析器崩溃（feed 抛 ValueError）→ 该贞计 fail，同层正常贞仍成功。"""
    fm_mod, ctx = sandbox
    ctx["router"].pages[fm_mod.LAYERS["cas"]] = make_listing("cas", ["bad", "good"])
    ctx["router"].pages[page_url("cas", "bad")] = make_page(
        title="bad", body="坏页标记\n" + "第一条 崩溃页内容。" * 40)
    ctx["router"].pages[page_url("cas", "good")] = make_page(title="good")

    orig_feed = fm_mod.PageText.feed

    def feed(self, html):
        if "坏页标记" in html:
            raise ValueError("模拟解析器崩溃")
        return orig_feed(self, html)

    monkeypatch.setattr(fm_mod.PageText, "feed", feed)

    fm_mod.fetch_layer("cas")
    ro = capsys.readouterr()
    assert "done ok=1 fail=1" in ro.out
    assert "[WARN] parse error" in ro.err  # parse_page 内部容忍并降级为 SKIP-EMPTY
    manifest = json.loads(fm_mod.MANIFEST.read_text(encoding="utf-8"))
    assert set(manifest) == {"cas/good"}
    assert (ctx["root"] / "cas" / "good.md").exists()
    assert not (ctx["root"] / "cas" / "bad.md").exists()


def test_c3_very_large_body(sandbox, capsys):
    """[P2] 100KB 正文贞 → 正常完成并完整落盘。"""
    fm_mod, ctx = sandbox
    big = "第十条 超长正文压力测试，内容持续重复填充。" * 4800  # ≈105K 字符
    ctx["router"].pages[fm_mod.LAYERS["cas"]] = make_listing("cas", ["huge"])
    ctx["router"].pages[page_url("cas", "huge")] = make_page(title="huge", body="长文如下\n" + big)

    fm_mod.fetch_layer("cas")
    assert "done ok=1 fail=0" in capsys.readouterr().out
    fm_dict, body = read_front_matter(ctx["root"] / "cas" / "huge.md")
    assert len(body) >= 100_000
    assert "超长正文压力测试" in body


# ---------------------------------------------------------------- D Windows / 编码 / 路径

@pytest.mark.skipif(os.name != "nt", reason="CRLF 落盘翻译是 Windows 行为钉")
def test_d1_crlf_on_disk_sha_from_memory(sandbox, capsys):
    """[P1 行为钉] win32 write_text 默认翻译 → 原始字节含 CRLF；sha 基于内存 body 不受影响。"""
    fm_mod, ctx = sandbox
    seed_pages(fm_mod, ctx, {"cas": ["2026n1"]})
    fm_mod.fetch_layer("cas")
    assert "done ok=1 fail=0" in capsys.readouterr().out

    md = ctx["root"] / "cas" / "2026n1.md"
    assert b"\r\n" in md.read_bytes()  # 落盘原始字节是 CRLF
    text = md.read_text(encoding="utf-8")  # 读回归一为 \n，内容无损往返
    assert "\r" not in text
    assert "第一条 为规范企业会计确认、计量和列报行为" in text

    fm_dict, body = read_front_matter(md)
    manifest = json.loads(fm_mod.MANIFEST.read_text(encoding="utf-8"))
    assert manifest["cas/2026n1"]["sha256"] == cleaned_sha(body)  # 逻辑正文哈希，与 CRLF 无关


def test_d2_gbk_console_output(sandbox, monkeypatch):
    """[P1] GBK 控制台：中文贞名的 [OK] 输出经 GBK stdout 不抛 UnicodeEncodeError。"""
    fm_mod, ctx = sandbox
    seed_pages(fm_mod, ctx, {"cas": ["准则2026"]})  # 中文 key → [OK] 行含中文
    buf = io.BytesIO()
    wrapper = io.TextIOWrapper(buf, encoding="gbk", errors="strict", line_buffering=True)
    monkeypatch.setattr(sys, "stdout", wrapper)

    fm_mod.fetch_layer("cas")  # 不应抛 UnicodeEncodeError
    wrapper.flush()
    out = buf.getvalue().decode("gbk")
    assert "[OK] cas/准则2026" in out
    assert "done ok=1 fail=0" in out


def test_d3_manifest_file_sep_vs_pending_keys(sandbox, update_mod, monkeypatch):
    """[P2 行为钉] manifest file 字段 win32 含 os.sep；pending 输出用 key/url 不受影响。"""
    fm_mod, ctx = sandbox
    uc, _ = update_mod
    seed_and_fetch(fm_mod, ctx)

    manifest = json.loads(fm_mod.MANIFEST.read_text(encoding="utf-8"))
    rec = manifest["cas/2026n1"]
    if os.name == "nt":
        assert rec["file"] == f"cas{os.sep}2026n1.md"  # os.sep 进入 file 字段

    ctx["router"].pages[page_url("cas", "2026n1")] = make_page(
        title="2026n1", body=revised_body())
    run_uc(uc, monkeypatch)
    text = pending_text(ctx["root"])
    assert f"- cas/2026n1 → {page_url('cas', '2026n1')}" in text  # key/url，正斜杠
    assert f"cas{os.sep}2026n1" not in text  # file 字段的反斜杠路径不漏进 pending


def test_d4_chinese_root_path_chain(sandbox, update_mod, tmp_path, monkeypatch, capsys):
    """[P1] 中文根目录（复刻 D:/个人资料库 场景）：fetch→update→health 缩微链路全绿。"""
    fm_mod, ctx = sandbox
    uc, _ = update_mod
    cn_root = tmp_path / "个人资料库"
    cn_root.mkdir()  # fetch_layer 的 outdir.mkdir 不带 parents，根目录须先存在
    monkeypatch.setattr(fm_mod, "ROOT", cn_root)
    monkeypatch.setattr(fm_mod, "STATE_DIR", cn_root / "scripts" / "state")
    monkeypatch.setattr(fm_mod, "MANIFEST", cn_root / "scripts" / "state" / "manifest.json")
    monkeypatch.setattr(uc, "ROOT", cn_root)
    monkeypatch.setattr(uc, "CHANGELOG", cn_root / "changelog")

    seed_pages(fm_mod, ctx, {"cas": ["2026n1"]})
    fm_mod.fetch_layer("cas")
    assert (cn_root / "cas" / "2026n1.md").exists()

    run_uc(uc, monkeypatch)
    assert "[CLEAN] 无变更" in capsys.readouterr().out
    assert not (cn_root / "changelog").exists()

    hc = load_health(monkeypatch, cn_root)
    hc.main()
    out = capsys.readouterr().out
    assert layer_line(out, "cas") == ("1", "1", "OK")
