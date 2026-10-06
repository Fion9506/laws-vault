"""FM-01..FM-69：scripts/fetch_maodocs.py 离线测试（零真网，Router 全 stub）。

用例命名约定（与 conftest 契约一致）：
- 「行为钉」= 断言当前真实行为（含缺陷），注释标注 BUG 与行号；
- 「修复门」= @pytest.mark.xfail(strict=True, reason="BUG ...") 断言期望行为，
  当前失败计 xfailed（绿），修复后 XPASS(strict) 变红提醒翻转本用例。
"""
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

import fetch_maodocs as fm  # scripts 已由 conftest 注入 sys.path；sandbox reload 同一模块对象
import pytest
from conftest import (
    cleaned_sha,
    make_listing,
    make_page,
    read_front_matter,
    write_manifest,
)

TODAY = str(date.today())
PAGE_URL = "https://docs.maoyanqing.com/accounting/ent/{}/{}.html"

EXPECTED_FM_KEYS = [
    "doc_id", "title", "layer", "level", "doc_number", "year", "issue_date",
    "effective_date", "status", "supersedes", "superseded_by", "org",
    "source_url", "site_modified", "checked_at", "fetched_at",
]


# ---------------------------------------------------------------- 助手

def _feed(html):
    """直接实例化 PageText 并喂入 html（复刻 parse_page 的预处理）。"""
    p = fm.PageText()
    p._intitle = False
    p.feed(html)
    return p


def _raw_listing(*links):
    return "<html><body><main>" + "".join(links) + "</main></body></html>"


def _hang(fm_mod, ctx, layer, names, pages=None):
    """挂层目录页 + 内容页（pages: {name: html}，缺省 make_page()），返回内容 URL 列表。"""
    ctx["router"].pages[fm_mod.LAYERS[layer]] = make_listing(layer, names)
    urls = []
    for n in names:
        u = PAGE_URL.format(layer, n)
        ctx["router"].pages[u] = (pages or {}).get(n) or make_page()
        urls.append(u)
    return urls


def _fetch_one(fm_mod, ctx, layer, name, html=None):
    """挂单页 listing+内容并跑 fetch_layer，返回 (url, front_matter, body)。"""
    pages = {name: html} if html is not None else None
    (url,) = _hang(fm_mod, ctx, layer, [name], pages)
    fm_mod.fetch_layer(layer)
    # slug_key 将路径中的 / 扁平化为 __（如 sub/page → sub__page）
    flat = name.replace("/", "__")
    fm_dict, body = read_front_matter(ctx["root"] / layer / f"{flat}.md")
    return url, fm_dict, body


def _fixed_page(n_chars):
    """正文恰为 n 个汉字的极简页（无 h1、无 meta、无文号）。"""
    return ("<html><head><title>T | 审计文库（MaoDocs）</title></head>"
            f"<body><main><p>{'字' * n_chars}</p></main></body></html>")


# ================================================================ Unit — PageText

def test_page_text_main_extraction_only(sandbox):
    """FM-01 [P0]：nav/footer 文本不进正文，main 内 p 进正文。"""
    html = ("<html><head><title>T</title></head><body><nav>导航噪声</nav>"
            "<main><p>正文甲</p><p>正文乙</p></main><footer>页脚噪声</footer></body></html>")
    p = _feed(html)
    out = p.result()
    assert out == "正文甲\n\n正文乙"
    assert "导航噪声" not in out and "页脚噪声" not in out


@pytest.mark.parametrize("tag", ["script", "style", "nav", "header", "footer", "aside"])
def test_page_text_skip_tags(sandbox, tag):
    """FM-02 [P0]：六类 skip 标签整块丢弃，skip 结束后文本恢复。"""
    p = _feed(f"<main><{tag}>噪声内容</{tag}>正文</main>")
    assert p.result() == "正文"


def test_page_text_skip_tag_nested_content(sandbox):
    """FM-02b [P0]：script 内嵌 div（CDATA）连同嵌套文本全部丢弃。"""
    p = _feed('<main><div><script>var a="<div>内嵌</div>";</script>恢复文</div></main>')
    out = p.result()
    assert out == "恢复文"
    assert "内嵌" not in out and "var a" not in out


@pytest.mark.parametrize("n", range(1, 7))
def test_page_text_heading_downgrade(sandbox, n):
    """FM-03 [P0]：h1~h6 → '#'*n 前缀。"""
    p = _feed(f"<main><h{n}>标题层级</h{n}>正文段落</main>")
    assert p.result() == "#" * n + " 标题层级\n\n正文段落"


@pytest.mark.parametrize("raw", ["<h3></h3>", "<h3>   </h3>"])
def test_page_text_empty_heading_no_line(sandbox, raw):
    """FM-03b [P0]：空/纯空白标题不产出行。"""
    p = _feed(f"<main>{raw}正文段落</main>")
    out = p.result()
    assert out == "正文段落"
    assert "#" not in out


def test_page_text_block_flush(sandbox):
    """FM-04 [P0]：p/li/tr/div/blockquote/br 各自成行，a<br>b 分两行。"""
    html = ("<main><p>A段</p><ul><li>B项</li></ul><table><tr>C行</tr></table>"
            "<div>D块</div><blockquote>E引</blockquote><p>F行<br>G行</p></main>")
    p = _feed(html)
    assert p.result().split("\n\n") == ["A段", "B项", "C行", "D块", "E引", "F行", "G行"]


def test_page_text_inline_merged(sandbox):
    """FM-05 [P1]：行内标签（strong）不切断，合并单行。"""
    p = _feed("<main><p>a<strong>b</strong>c</p></main>")
    assert p.result() == "abc"


def test_page_text_title_outside_main(sandbox):
    """FM-06 [P1]：<title> 只进 p.title，不进正文。"""
    p = _feed("<html><head><title>标题甲</title></head>"
              "<body><main><p>正文乙</p></main></body></html>")
    assert p.title == "标题甲"
    assert "标题甲" not in p.result()


def test_page_text_blank_collapse(sandbox):
    """FM-07 [P2]：无 3+ 连续换行、首尾无空白。"""
    p = _feed("<main><p></p><p>  </p><p>甲</p><p></p><p>乙</p><p> </p></main>")
    out = p.result()
    assert out == "甲\n\n乙"
    assert "\n\n\n" not in out
    assert out == out.strip()


def test_page_text_unclosed_heading_plain_line(sandbox):
    """FM-08 [P2 行为钉]：未闭合 <h2> 遇 </main> 直接关门，文本按普通行输出（无 ## 前缀）。
    现状：handle_endtag 中 main 关门后 `if not self.in_main: return`（L112-115），
    缓冲文本由 result() 的兜底 _flush 输出为普通行。"""
    p = _feed("<main><h2>文</main>")
    out = p.result()
    assert out == "文"
    assert not out.startswith("#")


def test_page_text_stray_end_heading_leading_space(sandbox):
    """FM-09 [P2 行为钉 BUG L119]：正文里离散的 </h2> 以 '#'*0 + ' ' + text 输出 → 行首空格。
    现状：endtag 分支不校验 _heading 是否被 starttag 置过，level-0 标题产出 ' 文本'。
    注意：首行的前导空格会被 result() 的最终 strip() 吞掉，故同时钉 lines 原始行。"""
    p = _feed("<main>文本</h2>续")
    assert " 文本" in p.lines  # BUG L119：产出了带行首空格的 0 级『标题』行
    assert p.result() == "文本\n\n续"  # 行为钉：首行空格被 strip() 掩盖


def test_page_text_nested_main_premature_close(sandbox):
    """FM-10 [P2 行为钉 BUG L77/L112]：嵌套 <main> 内层 </main> 提前关门（无深度计数），
    外层尾部『外尾』丢失。"""
    p = _feed("<main>外<main>内</main>外尾</main>")
    out = p.result()
    assert out == "外内"
    assert "外尾" not in out


def test_page_text_nbsp_only_dropped(sandbox):
    """FM-11 [P2]：&nbsp; 独立段落 strip 后为空，不产出行。"""
    p = _feed("<main><p>&nbsp;</p><p>正文</p></main>")
    assert p.result() == "正文"


# ================================================================ Unit — parse_page

def test_parse_page_triple_fields(sandbox):
    """FM-12 [P0]：body/title/modified 三元组；title 后缀剥离。"""
    body, title, modified = fm.parse_page(make_page())
    assert "发文机关：财政部" in body and "第一条" in body
    assert title == "测试文档"
    assert "审计文库" not in title
    assert modified == "2026-01-01T00:00:00+08:00"


def test_parse_page_meta_missing_empty(sandbox):
    """FM-13 [P1]：无 meta → modified 为空串。"""
    _, _, modified = fm.parse_page(make_page(raw_meta=""))
    assert modified == ""


def test_parse_page_meta_attr_order_sensitive(sandbox):
    """FM-14 [P2 行为钉 BUG L152]：meta 的 content 写在 name 前 → 正则失配，modified 为空。
    现状：L152 正则硬编码 name→content 顺序，不容忍属性换序。"""
    _, _, modified = fm.parse_page(make_page(
        raw_meta='<meta content="2026-05-05T00:00:00+08:00" name="article:modified_time">'))
    assert modified == ""


@pytest.mark.parametrize("html", [
    "<html><head><title>x</title><body><main><p>截断标签",
    "<main><p>未闭合段落",
    "<main><p>非法实体 &bogus; &#xZZ; &#999999999;</p></main>",
    "<html><body><nav>只有导航</nav></body></html>",
    "<html><body><main></main></body></html>",
], ids=["truncated-tag", "unclosed-p", "bad-entities", "nav-only", "empty-main"])
def test_parse_page_malformed_no_raise(sandbox, html):
    """FM-15 [P0]：病态输入一律不抛异常，返回三元组。"""
    result = fm.parse_page(html)
    assert isinstance(result, tuple) and len(result) == 3


def test_parse_page_feed_exception_swallowed(sandbox, monkeypatch, capsys):
    """FM-16 [P1]：feed 抛异常被吞，stderr 含 [WARN] parse error。"""
    def boom(self, html_text):
        raise RuntimeError("boom")

    monkeypatch.setattr(fm.PageText, "feed", boom)
    body, title, modified = fm.parse_page(make_page())
    assert body == "" and title == ""
    assert modified == "2026-01-01T00:00:00+08:00"  # meta 正则在 html 原文上独立运行
    err = capsys.readouterr().err
    assert "[WARN] parse error" in err and "boom" in err


def test_parse_page_empty_string(sandbox):
    """FM-17 [P2]：空串输入不抛，返回全空三元组。"""
    assert fm.parse_page("") == ("", "", "")


# ================================================================ Unit — DOCNO_RE

def test_docno_fullwidth_brackets(sandbox):
    """FM-18 [P0]：全角六角括号文号，group(0)/1/2 全对。"""
    m = fm.DOCNO_RE.search("财会〔2026〕11号")
    assert m
    assert m.group(0) == "财会〔2026〕11号"
    assert m.group(1) == "2026" and m.group(2) == "11"


def test_docno_ascii_brackets(sandbox):
    """FM-19 [P0]：ASCII 方括号文号。"""
    m = fm.DOCNO_RE.search("财会[2006]3号")
    assert m
    assert m.group(0) == "财会[2006]3号"
    assert m.group(1) == "2006" and m.group(2) == "3"


def test_docno_spacing_tolerant(sandbox):
    """FM-20 [P1]：括号后与数字/『号』之间容许空白。"""
    m = fm.DOCNO_RE.search("财会〔2026〕 11 号")
    assert m
    assert m.group(0) == "财会〔2026〕 11 号"
    assert m.group(1) == "2026" and m.group(2) == "11"


def test_docno_single_char_org_no_match(sandbox):
    """FM-21 [P1]：括号前不足 2 字 → 不匹配。"""
    assert fm.DOCNO_RE.search("部〔2020〕1号") is None


def test_docno_prefix_overcapture(sandbox):
    """FM-22 [P1 行为钉 BUG L54+L209]：{2,14}? 前缀从最早可行位置起匹配，
    『关于印发的通知』整体污染 group(0)，入库 doc_number 带垃圾前缀。"""
    text = "关于印发的通知财会〔2006〕3号"
    m = fm.DOCNO_RE.search(text)
    assert m
    assert m.group(0) == text  # 行为钉：group(0) == 全串（含前缀污染）
    assert m.group(1) == "2006" and m.group(2) == "3"


def test_docno_long_run_tail_truncation(sandbox):
    """FM-23 [P2 行为钉]：括号前 16 连汉字超出 {2,14} 上限 → 只匹配尾部 14 字 + 文号
    （start=2，头部 2 字被跳过）。"""
    text = "一" * 16 + "〔2020〕5号"
    m = fm.DOCNO_RE.search(text)
    assert m
    assert m.start() == 2
    assert m.group(0) == text[2:] == "一" * 14 + "〔2020〕5号"
    assert m.group(1) == "2020" and m.group(2) == "5"


@pytest.mark.parametrize("text", [
    "财会〔2026〕号",   # 缺号数
    "财会[26]3号",      # 年份非 4 位
    "财会2026〕3号",    # 缺左括号
], ids=["no-number", "short-year", "no-open-bracket"])
def test_docno_invalid_forms_no_match(sandbox, text):
    """FM-24 [P1]：残缺文号形态一律不匹配。"""
    assert fm.DOCNO_RE.search(text) is None


def test_docno_dihao_style_not_matched(sandbox):
    """FM-25 [P2 行为钉]：『第 N 号』令牌形态（数字前有『第』）不匹配。"""
    assert fm.DOCNO_RE.search("财政部令〔2023〕第1号") is None


# ================================================================ Unit — slug_key

def test_slug_key_basic(sandbox):
    """FM-26 [P0]：单段路径 → cas/30b。"""
    assert fm.slug_key("cas", PAGE_URL.format("cas", "30b")) == "cas/30b"


def test_slug_key_nested_double_underscore(sandbox):
    """FM-27 [P0]：子目录 → 双下划线扁平化。"""
    assert fm.slug_key("cas", PAGE_URL.format("cas", "sub/page")) == "cas/sub__page"


def test_slug_key_multi_level(sandbox):
    """FM-28 [P1]：多级目录 → 多个双下划线。"""
    assert fm.slug_key("cas", PAGE_URL.format("cas", "a/b/c")) == "cas/a__b__c"


def test_slug_key_html_replaced_everywhere(sandbox):
    """FM-29 [P2 行为钉 BUG L182]：replace(".html","") 全量替换 —— 路径里两处 .html 都被删。"""
    slug = fm.slug_key("cas", PAGE_URL.format("cas", "a.html.b/c.html"))
    assert ".html" not in slug
    assert slug == "cas/a.b__c"


def test_slug_key_malformed_url_indexerror(sandbox):
    """FM-30 [P2 行为钉 BUG L182]：url 不含 /{layer}/ → split[1] 直接 IndexError。"""
    with pytest.raises(IndexError):
        fm.slug_key("cas", "https://docs.maoyanqing.com/accounting/ent/index.html")


# ================================================================ Unit — discover

def test_discover_extracts_full_urls_in_order(sandbox):
    """FM-31 [P0]：href → 完整 URL 且保序。"""
    fm_mod, ctx = sandbox
    ctx["router"].pages[fm_mod.LAYERS["cas"]] = make_listing("cas", ["a01", "b02", "c03"])
    assert fm_mod.discover(fm_mod.LAYERS["cas"], "cas") == [
        PAGE_URL.format("cas", n) for n in ("a01", "b02", "c03")
    ]


def test_discover_dedup_keeps_first(sandbox):
    """FM-32 [P0]：重复 href 去重，保留首条。"""
    fm_mod, ctx = sandbox
    ctx["router"].pages[fm_mod.LAYERS["cas"]] = make_listing("cas", ["dup", "dup", "dup"])
    assert fm_mod.discover(fm_mod.LAYERS["cas"], "cas") == [PAGE_URL.format("cas", "dup")]


def test_discover_index_excluded(sandbox):
    """FM-33 [P0]：index.html / index2.html 排除，myindex.html 保留。"""
    fm_mod, ctx = sandbox
    ctx["router"].pages[fm_mod.LAYERS["cas"]] = make_listing("cas", ["index", "index2", "myindex"])
    assert fm_mod.discover(fm_mod.LAYERS["cas"], "cas") == [PAGE_URL.format("cas", "myindex")]


def test_discover_other_layer_ignored(sandbox):
    """FM-34 [P0]：layer='cas' 时 /casg/ 链接不匹配。"""
    fm_mod, ctx = sandbox
    ctx["router"].pages[fm_mod.LAYERS["cas"]] = _raw_listing(
        '<a href="/accounting/ent/casg/x.html">x</a>')
    assert fm_mod.discover(fm_mod.LAYERS["cas"], "cas") == []


def test_discover_fragment_query_skipped(sandbox):
    """FM-35 [P1]：带 #frag / ?q= 的 href 不匹配。"""
    fm_mod, ctx = sandbox
    ctx["router"].pages[fm_mod.LAYERS["cas"]] = _raw_listing(
        '<a href="/accounting/ent/cas/x.html#frag">x</a>',
        '<a href="/accounting/ent/cas/y.html?q=1">y</a>')
    assert fm_mod.discover(fm_mod.LAYERS["cas"], "cas") == []


@pytest.mark.parametrize("listing", [None, ""], ids=["unregistered-none", "empty-string"])
def test_discover_http_fail_empty(sandbox, listing):
    """FM-36 [P0]：listing 请求失败（None）或空串 → 空列表。"""
    fm_mod, ctx = sandbox
    if listing is not None:
        ctx["router"].pages[fm_mod.LAYERS["cas"]] = listing
    assert fm_mod.discover(fm_mod.LAYERS["cas"], "cas") == []


def test_discover_relative_href_not_matched(sandbox):
    """FM-37 [P2 行为钉]：相对路径 href（无 /accounting/ent/ 前缀）不匹配 → 空列表。"""
    fm_mod, ctx = sandbox
    ctx["router"].pages[fm_mod.LAYERS["cas"]] = _raw_listing(
        '<a href="x.html">x</a>', '<a href="./y.html">y</a>',
        '<a href="cas/z.html">z</a>')
    assert fm_mod.discover(fm_mod.LAYERS["cas"], "cas") == []


# ================================================================ Unit — load_overrides / load_manifest

def test_load_overrides_file_used(sandbox):
    """FM-38 [P0]：文件键逐键生效，且与 DEFAULT_OVERRIDES 合并（默认其余保留）。"""
    fm_mod, ctx = sandbox
    entry = {"status": "有效", "doc_number": "财会〔2026〕99号"}
    ctx["overrides"].write_text(
        json.dumps({"cas/99x": entry}, ensure_ascii=False), encoding="utf-8")
    result = fm_mod.load_overrides()
    assert result["cas/99x"] == entry
    assert "cas/30b" in result
    assert "cas/25b" in result


def test_load_overrides_missing_falls_back_to_defaults(sandbox):
    """FM-39 [P0]：无文件 → DEFAULT_OVERRIDES（含 cas/30b、cas/25b）。"""
    fm_mod, ctx = sandbox
    assert not ctx["overrides"].exists()
    assert fm_mod.load_overrides() == fm_mod.DEFAULT_OVERRIDES
    assert "cas/30b" in fm_mod.DEFAULT_OVERRIDES
    assert "cas/25b" in fm_mod.DEFAULT_OVERRIDES


def test_load_overrides_no_merge_with_defaults(sandbox):
    """FM-40 [P1]（原修复门，已修复）：文件只写 cas/99x → 与 DEFAULT_OVERRIDES
    逐键合并（结果同时含 cas/99x、cas/30b、cas/25b）。"""
    fm_mod, ctx = sandbox
    ctx["overrides"].write_text(
        json.dumps({"cas/99x": {"status": "有效"}}, ensure_ascii=False), encoding="utf-8")
    data = fm_mod.load_overrides()
    assert "cas/99x" in data
    assert "cas/30b" in data
    assert "cas/25b" in data


def test_load_overrides_invalid_json_raises(sandbox):
    """FM-41 [P2 行为钉]：坏 JSON 直接抛 JSONDecodeError（无容错）。"""
    fm_mod, ctx = sandbox
    ctx["overrides"].write_text("{bad", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        fm_mod.load_overrides()


def test_load_manifest_missing_and_roundtrip(sandbox):
    """FM-42 [P1]：无 manifest → {}；写入后读回相等。"""
    fm_mod, ctx = sandbox
    assert fm_mod.load_manifest() == {}
    entries = {"cas/01": {"url": "https://u", "sha256": "abc", "file": "cas/01.md"}}
    write_manifest(ctx["state"], entries)
    assert fm_mod.load_manifest() == entries


# ================================================================ Unit — http_get

class _FakeResp:
    """带上下文管理器协议的最小响应。"""

    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_http_get_success_decodes_and_sends_ua(monkeypatch):
    """FM-43 [P1]：成功路径解码 utf-8(ignore)，Request 带 laws-vault UA。"""
    seen = {}

    def fake_urlopen(req, timeout=None):
        seen["req"] = req
        return _FakeResp(b"<html>ok</html>")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)  # 覆盖 no_net 熔断器
    out = fm.http_get("https://example.com/a")
    assert out == "<html>ok</html>"
    ua = seen["req"].get_header("User-agent")
    assert ua == fm.UA["User-Agent"]
    assert "laws-vault" in ua


def test_http_get_retry_then_none(monkeypatch, capsys):
    """FM-44 [P1]：retries=1 且恒失败 → 调 2 次、返 None、stderr 含 [FAIL]。"""
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append(req.full_url)
        raise OSError("网络不可达")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(fm.time, "sleep", lambda s: None)  # 屏蔽重试间 2s 真睡眠
    assert fm.http_get("https://example.com/a", retries=1) is None
    assert len(calls) == 2
    assert "[FAIL]" in capsys.readouterr().err


def test_http_get_zero_retries_single_attempt(monkeypatch):
    """FM-45 [P2]：retries=0 → 仅 1 次尝试即返 None。"""
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append(req.full_url)
        raise OSError("网络不可达")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(fm.time, "sleep", lambda s: None)
    assert fm.http_get("https://example.com/a", retries=0) is None
    assert len(calls) == 1


def test_http_get_invalid_bytes_ignored(monkeypatch):
    """FM-46 [P2]：非法 UTF-8 字节被 errors='ignore' 丢弃。"""
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=None: _FakeResp(b"\xff" + "文".encode()))
    assert fm.http_get("https://example.com/a") == "文"


# ================================================================ Module — status_map（黑盒经 fetch_layer）

@pytest.mark.parametrize("raw,expected", [
    ("现行有效", "有效"),
    ("有效", "有效"),
    ("已废止", "已废止"),
    ("已失效", "已废止"),
    ("尚未生效", "尚未生效"),
    ("已被修改", "已修改"),
    ("部分失效", "部分废止"),
])
def test_status_map_known_values(sandbox, raw, expected):
    """FM-47 [P0]：七种已知时效性 → 映射值写入 front-matter status。"""
    fm_mod, ctx = sandbox
    _, fm_dict, _ = _fetch_one(fm_mod, ctx, "cas", "p", make_page(status=raw))
    assert fm_dict["status"] == expected


def test_status_map_unknown_passthrough(sandbox):
    """FM-48 [P1]：未知时效性原样保留。"""
    fm_mod, ctx = sandbox
    _, fm_dict, _ = _fetch_one(fm_mod, ctx, "cas", "p", make_page(status="已修订（自定义）"))
    assert fm_dict["status"] == "已修订（自定义）"


@pytest.mark.parametrize("layer,expected", [("cas", "待核"), ("casg", "有效")])
def test_status_missing_layer_default(sandbox, layer, expected):
    """FM-49 [P1]：正文无时效性行 → cas 兜底『待核』，casg 兜底『有效』。"""
    fm_mod, ctx = sandbox
    src = "发文机关：财政部\n发布日期：2026-01-01\n" + "字" * 220
    _, fm_dict, _ = _fetch_one(fm_mod, ctx, layer, "p", make_page(body=src))
    assert fm_dict["status"] == expected


# ================================================================ Module — fetch_layer
def test_fetch_writes_md_with_complete_front_matter(sandbox):
    """FM-50 [P0]：产出 cas/p.md（中性键，不触发 overrides）；front-matter 恰 16 键且保序；
    正文紧跟第二组 --- 之后。"""
    fm_mod, ctx = sandbox
    _, fm_dict, body = _fetch_one(fm_mod, ctx, "cas", "p")
    md = ctx["root"] / "cas" / "p.md"
    assert md.exists()
    assert list(fm_dict.keys()) == EXPECTED_FM_KEYS
    assert len(fm_dict) == 16
    raw = md.read_text(encoding="utf-8")
    assert raw.startswith("---\n")
    assert "\n---\n" in raw
    assert "\n---\n" not in body  # 正文区不再有分隔符 → 正文紧跟第二组 ---
    # make_page 在 main 首部放 <h1>{title}</h1> → 正文首行为降级标题行
    assert body.startswith("# 测试文档\n\n发文机关：财政部")
    assert body.endswith("\n")


def test_override_scope_note_survives_to_front_matter(sandbox):
    """FM-51 [P1]（原修复门，已修复）：overrides 的 scope_note → 落入 front-matter。"""
    fm_mod, ctx = sandbox
    ctx["overrides"].write_text(
        json.dumps({"cas/30b": {"scope_note": "境内外同时上市企业先行"}},
                   ensure_ascii=False),
        encoding="utf-8")
    _, fm_dict, _ = _fetch_one(fm_mod, ctx, "cas", "30b")
    assert fm_dict["scope_note"] == "境内外同时上市企业先行"


def test_fetch_field_extraction_chain(sandbox):
    """FM-52 [P0]：一页含 发文机关/发布日期/生效日期/时效性/文号 → 全链路抽取正确。"""
    fm_mod, ctx = sandbox
    url, fm_dict, _ = _fetch_one(fm_mod, ctx, "cas", "p")
    assert fm_dict["org"] == "财政部"
    assert fm_dict["issue_date"] == "2026-01-01"
    assert fm_dict["effective_date"] == "2026-02-01"
    assert fm_dict["status"] == "有效"  # 现行有效 → 有效
    assert fm_dict["doc_number"] == "财会〔2026〕1号"
    assert fm_dict["year"] == "2026"
    assert fm_dict["level"] == "具体准则"
    assert fm_dict["source_url"] == url
    assert fm_dict["site_modified"] == "2026-01-01T00:00:00+08:00"


def test_fetch_override_field_priority(sandbox):
    """FM-53 [P0]：overrides 的 status/effective_date 优先，doc_number/org 仍自动抽取。"""
    fm_mod, ctx = sandbox
    ctx["overrides"].write_text(
        json.dumps({"cas/p": {"status": "尚未生效", "effective_date": "2027-01-01"}},
                   ensure_ascii=False),
        encoding="utf-8")
    _, fm_dict, _ = _fetch_one(fm_mod, ctx, "cas", "p")
    assert fm_dict["status"] == "尚未生效"
    assert fm_dict["effective_date"] == "2027-01-01"
    assert fm_dict["doc_number"] == "财会〔2026〕1号"
    assert fm_dict["org"] == "财政部"


def test_fetch_doc_id_fallback(sandbox):
    """FM-54 [P1]：无文号无覆盖 → doc_id 回退 key，doc_number 空串。"""
    fm_mod, ctx = sandbox
    _, fm_dict, _ = _fetch_one(fm_mod, ctx, "cas", "p", make_page(doc_number=""))
    assert fm_dict["doc_number"] == ""
    assert fm_dict["doc_id"] == "cas/p"


def test_fetch_docno_whitelist_strips_title_prefix(sandbox):
    """FM-54b [P1]（新增，随白名单修复）：文号嵌在长标题句中
    『关于印发……的通知财会〔2006〕3号』→ doc_number 只取干净文号，不带标题前缀。"""
    fm_mod, ctx = sandbox
    body = ("发文机关：财政部\n发布日期：2006-02-15\n生效日期：2007-01-01\n时效性：现行有效\n"
            "关于印发《企业会计准则第1号——存货》的通知财会〔2006〕3号\n"
            "第一条 为了规范存货的确认和计量，制定本准则。" * 8)
    _, fm_dict, _ = _fetch_one(fm_mod, ctx, "cas", "p", make_page(body=body))
    assert fm_dict["doc_number"] == "财会〔2006〕3号"
    assert fm_dict["doc_id"] == "财会〔2006〕3号"
    assert fm_dict["year"] == "2006"


def test_fetch_empty_page_199_skipped(sandbox, capsys):
    """FM-55 [P0]：正文恰 199 字 → 无 md、无 manifest 条目（文件不建）、stderr [SKIP-EMPTY]、fail=1。"""
    fm_mod, ctx = sandbox
    _hang(fm_mod, ctx, "cas", ["p"], {"p": _fixed_page(199)})
    fm_mod.fetch_layer("cas")
    captured = capsys.readouterr()
    assert not (ctx["root"] / "cas" / "p.md").exists()
    assert not (ctx["state"] / "manifest.json").exists()
    assert "[SKIP-EMPTY] cas/p" in captured.err
    assert "[cas] done ok=0 fail=1" in captured.out


def test_fetch_boundary_200_passes(sandbox, capsys):
    """FM-56 [P1]：恰 200 字 ≥ 阈值 → 成功写盘。"""
    fm_mod, ctx = sandbox
    _hang(fm_mod, ctx, "cas", ["p"], {"p": _fixed_page(200)})
    fm_mod.fetch_layer("cas")
    out = capsys.readouterr().out
    assert (ctx["root"] / "cas" / "p.md").exists()
    assert "[OK] cas/p (200 chars)" in out


def test_fetch_http_fail_counted(sandbox, capsys):
    """FM-57 [P0]：内容页未登记（http 失败）→ ok=0 fail=1、无文件、无 manifest。"""
    fm_mod, ctx = sandbox
    ctx["router"].pages[fm_mod.LAYERS["cas"]] = make_listing("cas", ["p"])  # 仅登记 listing
    fm_mod.fetch_layer("cas")
    out = capsys.readouterr().out
    assert "[cas] done ok=0 fail=1" in out
    assert not (ctx["root"] / "cas" / "p.md").exists()
    assert not (ctx["state"] / "manifest.json").exists()


def test_fetch_manifest_merge_preexisting(sandbox):
    """FM-58 [P0]：预置 cas/old + 新页 → 两键共存；新键字段齐、sha256 与清洗后正文一致。"""
    fm_mod, ctx = sandbox
    write_manifest(ctx["state"], {
        "cas/old": {"url": "https://old", "title": "旧文档", "sha256": "deadbeef",
                     "file": "cas/old.md", "fetched_at": "2020-01-01"},
    })
    url, fm_dict, body = _fetch_one(fm_mod, ctx, "cas", "new")
    man = json.loads((ctx["state"] / "manifest.json").read_text(encoding="utf-8"))
    assert set(man) == {"cas/old", "cas/new"}
    entry = man["cas/new"]
    assert set(entry) == {"url", "title", "sha256", "file", "fetched_at"}
    assert entry["url"] == url
    assert entry["title"] == fm_dict["title"]
    assert entry["fetched_at"] == TODAY
    assert entry["sha256"] == cleaned_sha(body)
    assert man["cas/old"]["title"] == "旧文档"  # 旧条目原样保留


def test_fetch_listing_fail_zero(sandbox, capsys):
    """FM-59 [P1]：listing 未登记 → discovered 0、ok=0 fail=0、manifest 文件不创建。"""
    fm_mod, ctx = sandbox
    fm_mod.fetch_layer("cas")
    out = capsys.readouterr().out
    assert "[cas] discovered 0 pages" in out
    assert "[cas] done ok=0 fail=0" in out
    assert not (ctx["state"] / "manifest.json").exists()
    assert list((ctx["root"] / "cas").glob("*.md")) == []


def test_fetch_limit_trims_and_zero_means_all(sandbox):
    """FM-60 [P1 行为钉 BUG L188]：limit=2 截取前 2 页；limit=0 为假值 → 不限（3 页全抓）。"""
    fm_mod, ctx = sandbox
    _hang(fm_mod, ctx, "cas", ["a", "b", "c"])
    fm_mod.fetch_layer("cas", limit=2)
    assert sorted(p.name for p in (ctx["root"] / "cas").glob("*.md")) == ["a.md", "b.md"]
    fm_mod.fetch_layer("cas", limit=0)  # BUG L188：`if limit:` 把 0 当『不限』
    assert sorted(p.name for p in (ctx["root"] / "cas").glob("*.md")) == \
        ["a.md", "b.md", "c.md"]


def test_fetch_reading_time_stripped(sandbox):
    """FM-61 [P1]：『约 N 字 · 阅读 N 分钟』行从输出与 sha 中剥离；无『分钟』的『约 N 字』保留。"""
    fm_mod, ctx = sandbox
    # p：带分钟 → 剥离
    src_p = "发文机关：财政部\n约 1234 字 · 阅读 5 分钟\n" + "字" * 220
    _, fm_p, body_p = _fetch_one(fm_mod, ctx, "cas", "p", make_page(body=src_p))
    assert "约 1234 字" not in body_p
    man = json.loads((ctx["state"] / "manifest.json").read_text(encoding="utf-8"))
    assert man["cas/p"]["sha256"] == cleaned_sha(body_p)
    # q：无分钟 → 不剥离
    src_q = "发文机关：财政部\n约 1234 字\n" + "字" * 220
    _, fm_q, body_q = _fetch_one(fm_mod, ctx, "cas", "q", make_page(body=src_q))
    assert "约 1234 字" in body_q
    man = json.loads((ctx["state"] / "manifest.json").read_text(encoding="utf-8"))
    assert man["cas/q"]["sha256"] == cleaned_sha(body_q)


def test_fetch_nested_slug_flat_file(sandbox):
    """FM-62 [P1]：子目录页 → 扁平文件 cas/sub__page.md + manifest 键 cas/sub__page。"""
    fm_mod, ctx = sandbox
    _, fm_dict, _ = _fetch_one(fm_mod, ctx, "cas", "sub/page")
    assert (ctx["root"] / "cas" / "sub__page.md").exists()
    assert not (ctx["root"] / "cas" / "sub" / "page.md").exists()
    man = json.loads((ctx["state"] / "manifest.json").read_text(encoding="utf-8"))
    assert "cas/sub__page" in man


def test_fetch_extraction_window(sandbox):
    """FM-63 [P2 行为钉]：文号在 3000 字窗外、时效性在 2500 字窗外 → 抽不到，走层兜底
    （doc_number 空、doc_id 回退 key、status 兜底『待核』）。"""
    fm_mod, ctx = sandbox
    html = ("<html><head><title>T</title></head><body><main>"
            f"<p>{'字' * 3000}</p><p>财会〔2026〕1号</p><p>时效性：现行有效</p>"
            f"<p>{'尾' * 60}</p></main></body></html>")
    _, fm_dict, body = _fetch_one(fm_mod, ctx, "cas", "p", html)
    assert "财会〔2026〕1号" in body  # 文号确实在正文里
    assert "时效性：现行有效" in body
    assert body.index("财会〔2026〕1号") >= 3000
    assert body.index("时效性") >= 2500
    assert fm_dict["doc_number"] == ""
    assert fm_dict["year"] == ""
    assert fm_dict["doc_id"] == "cas/p"
    assert fm_dict["status"] == "待核"


def test_fetch_manifest_file_field_backslash(sandbox):
    """FM-64 [P2 行为钉 BUG L243]：manifest file 字段为 str(relative_to(ROOT)) ——
    win32 下是反斜杠风格（sys.platform 分支），断言用 Path 构造保持平台一致。"""
    fm_mod, ctx = sandbox
    _fetch_one(fm_mod, ctx, "cas", "p")
    man = json.loads((ctx["state"] / "manifest.json").read_text(encoding="utf-8"))
    assert man["cas/p"]["file"] == str(Path("cas", "p.md"))


@pytest.mark.parametrize("layer,level", [
    ("cas", "具体准则"),
    ("casg", "应用指南"),
    ("casi", "准则解释"),
    ("casc", "应用案例"),
    ("casq", "实施问答"),
])
def test_fetch_five_layers_level_map(sandbox, layer, level):
    """FM-65 [P1]：五层各一页 → level 与层映射一一对应。"""
    fm_mod, ctx = sandbox
    _, fm_dict, _ = _fetch_one(fm_mod, ctx, layer, "p")
    assert fm_dict["layer"] == layer
    assert fm_dict["level"] == level


def test_fetch_timestamps_today(sandbox):
    """FM-66 [P2]：checked_at == fetched_at == 今天。"""
    fm_mod, ctx = sandbox
    _, fm_dict, _ = _fetch_one(fm_mod, ctx, "cas", "p")
    assert fm_dict["checked_at"] == TODAY
    assert fm_dict["fetched_at"] == TODAY


# ================================================================ Module — main() CLI

def _spy_fetch_layer(monkeypatch):
    calls = []
    monkeypatch.setattr(fm, "fetch_layer",
                        lambda layer, limit: calls.append((layer, limit)))
    return calls


def test_main_dispatch_split_strip(sandbox, monkeypatch):
    """FM-67 [P1]：--layers 按逗号拆分且去空白；--limit 透传。"""
    fm_mod, _ = sandbox
    calls = _spy_fetch_layer(monkeypatch)
    monkeypatch.setattr(sys, "argv",
                        ["fetch_maodocs.py", "--layers", "cas, casi", "--limit", "1"])
    fm_mod.main()
    assert calls == [("cas", 1), ("casi", 1)]


def test_main_unknown_layer_exit2(sandbox, monkeypatch, capsys):
    """FM-68 [P1]：未知层 → SystemExit(2)、stderr 提示；之前的合法层已执行。"""
    fm_mod, _ = sandbox
    calls = _spy_fetch_layer(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["fetch_maodocs.py", "--layers", "cas,foo"])
    with pytest.raises(SystemExit) as excinfo:
        fm_mod.main()
    assert excinfo.value.code == 2
    assert "unknown layer foo" in capsys.readouterr().err
    assert calls == [("cas", None)]


def test_main_default_layers(sandbox, monkeypatch):
    """FM-69 [P2]：无 --layers → 默认恰 cas,casi 两层，limit=None。"""
    fm_mod, _ = sandbox
    calls = _spy_fetch_layer(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["fetch_maodocs.py"])
    fm_mod.main()
    assert calls == [("cas", None), ("casi", None)]
