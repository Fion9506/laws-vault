"""HC-01..HC-26：scripts/health_check.py 离线测试（sh/socket/env 全替身）。

用例命名约定同 test_update_check.py：
- 「行为钉」断言当前真实行为（含缺陷），docstring 标注 BUG 与行号；
- 「修复门」= @pytest.mark.xfail(strict=True) 断言期望行为，修复后 XPASS 变红。
"""
import re
import types
from datetime import date, timedelta

import pytest
from conftest import write_manifest, write_md

TODAY = date.today()
RULES = ["project_rules.md", "00-citation-discipline.md", "01-query-transcription.md",
         "02-vault-usage.md", "03-vault-update.md"]
SKILLS = ["vault-update", "case-analysis", "mcp-ops", "health-check"]


# ---------------------------------------------------------------- 替身

class FakeSock:
    """connect_ex 返回预设值，绝不真连 127.0.0.1:18062。"""

    def __init__(self, result):
        self._result = result
        self.target = None

    def settimeout(self, t):
        pass

    def connect_ex(self, addr):
        self.target = addr
        return self._result

    def close(self):
        pass


def wire(monkeypatch, hc, git_status="", git_log="", sock_result=1, api_key=None):
    """统一替身：hc.sh 分发 git status/log、hc.socket 换 FakeSock 工厂、清/设 API key。"""

    def fake_sh(cmd, cwd=None):
        if "status" in cmd:
            return git_status
        if "log" in cmd:
            return git_log
        return ""

    monkeypatch.setattr(hc, "sh", fake_sh)
    monkeypatch.setattr(hc, "socket", types.SimpleNamespace(socket=lambda: FakeSock(sock_result)))
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
    if api_key is not None:
        monkeypatch.setenv("SILICONFLOW_API_KEY", api_key)


def run_main(hc, monkeypatch, capsys, **kw):
    wire(monkeypatch, hc, **kw)
    hc.main()
    return capsys.readouterr().out


def write_fm(tmp_path, text, name="doc.md"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


# ---------------------------------------------------------------- fm() 解析

def test_hc01_fm_standard_three_keys_stripped(health_mod, tmp_path):
    """[P0] 标准三键 front-matter 全部解析、值已 strip。"""
    hc, _ = health_mod
    p = write_fm(tmp_path, "---\ntitle:  关于XX  \nstatus: 现行有效\ndoc_number: 财会〔2026〕1号\n---\n正文")
    assert hc.fm(p) == {"title": "关于XX", "status": "现行有效", "doc_number": "财会〔2026〕1号"}


def test_hc02_no_frontmatter_returns_empty(health_mod, tmp_path):
    """[P0] 首行是 # 标题（无 front-matter）→ {}。"""
    hc, _ = health_mod
    assert hc.fm(write_fm(tmp_path, "# 标题\n正文内容")) == {}


def test_hc03_nested_colon_preserved(health_mod, tmp_path):
    """[P0] 值内嵌套冒号保留（split(':', 1) 只切第一个冒号）。"""
    hc, _ = health_mod
    p = write_fm(tmp_path, "---\ntitle: 财政部：关于XX\n---\n正文")
    assert hc.fm(p) == {"title": "财政部：关于XX"}


def test_hc04_whitespace_both_sides_stripped(health_mod, tmp_path):
    """[P1] 键、值两侧空白都清洗。"""
    hc, _ = health_mod
    p = write_fm(tmp_path, "---\n  status  :   待核  \n---\n正文")
    assert hc.fm(p) == {"status": "待核"}


def test_hc05_unclosed_frontmatter_swallows_body(health_mod, tmp_path):
    """[P2 行为钉] BUG hc L19-24：front-matter 无闭合 --- 时无边界防御，
    整个文件体按键值对照收（foo: bar 也进 dict）。"""
    hc, _ = health_mod
    p = write_fm(tmp_path, "---\nfoo: bar\n")  # 缺闭合 ---
    assert hc.fm(p) == {"foo": "bar"}


def test_hc06_empty_and_bare_fence_no_crash(health_mod, tmp_path):
    """[P1] 空文件、仅一行 --- → {} 不炸。"""
    hc, _ = health_mod
    assert hc.fm(write_fm(tmp_path, "", name="a.md")) == {}
    assert hc.fm(write_fm(tmp_path, "---", name="b.md")) == {}


def test_hc07_bom_frontmatter_parsed(health_mod, tmp_path):
    """[P2]（原修复门，已修复）UTF-8 BOM 开头的 front-matter 正常解析出 status。"""
    hc, _ = health_mod
    p = tmp_path / "bom.md"
    p.write_bytes("\ufeff---\nstatus: 有效\n---".encode("utf-8"))
    assert hc.fm(p) == {"status": "有效"}


# ---------------------------------------------------------------- 语料层对账

def test_hc08_reconcile_ok(health_mod, monkeypatch, capsys):
    """[P0] cas 磁盘 2 / manifest 2 [OK]；无文件的层 磁盘 0 / manifest 0 [OK]。"""
    hc, root = health_mod
    write_md(root, "cas", "a", {"status": "现行有效", "checked_at": str(TODAY)})
    write_md(root, "cas", "b", {"status": "现行有效", "checked_at": str(TODAY)})
    write_manifest(root / "scripts" / "state", {"cas/a": {}, "cas/b": {}})
    out = run_main(hc, monkeypatch, capsys)
    assert "- cas: 磁盘 2 / manifest 2 [OK]" in out
    assert "- casg: 磁盘 0 / manifest 0 [OK]" in out


def test_hc09_reconcile_mismatch_both_directions(health_mod, monkeypatch, capsys):
    """[P0] MISMATCH 双向：磁盘多（3/2）与 manifest 多（0/1）都标 MISMATCH。"""
    hc, root = health_mod
    for n in ("a", "b", "c"):
        write_md(root, "cas", n, {"status": "现行有效", "checked_at": str(TODAY)})
    write_manifest(root / "scripts" / "state", {"cas/a": {}, "cas/b": {}, "casi/x": {}})
    out = run_main(hc, monkeypatch, capsys)
    assert "- cas: 磁盘 3 / manifest 2 [MISMATCH]" in out
    assert "- casi: 磁盘 0 / manifest 1 [MISMATCH]" in out


def test_hc10_manifest_missing_layer_mismatch_no_crash(health_mod, monkeypatch, capsys):
    """[P1] manifest.json 不存在 → 磁盘有文件的层标 MISMATCH，不炸。"""
    hc, root = health_mod
    write_md(root, "cas", "a", {"status": "现行有效", "checked_at": str(TODAY)})
    write_md(root, "cas", "b", {"status": "现行有效", "checked_at": str(TODAY)})
    assert not (root / "scripts" / "state" / "manifest.json").exists()
    out = run_main(hc, monkeypatch, capsys)  # 不抛异常即通过
    assert "- cas: 磁盘 2 / manifest 0 [MISMATCH]" in out
    assert "- casg: 磁盘 0 / manifest 0 [OK]" in out


# ---------------------------------------------------------------- 元数据质量

def test_hc11_pending_exact_match_only(health_mod, monkeypatch, capsys):
    """[P0] 待核 / 有效 / 待核实 三文件 → status=待核 精确只计 1。"""
    hc, root = health_mod
    for i, st in enumerate(("待核", "有效", "待核实")):
        write_md(root, "casg", f"p{i}", {"status": st, "checked_at": str(TODAY)})
    out = run_main(hc, monkeypatch, capsys)
    assert "- status=待核：1 ｜ cas/casi 缺文号：0 ｜ checked_at>14天：0/3" in out


def test_hc12_missing_doc_number_cas_casi_only(health_mod, monkeypatch, capsys):
    """[P0] 缺文号只统计 cas/casi：cas 缺号计 1、casg 缺号不计、casi 有号不计。"""
    hc, root = health_mod
    write_md(root, "cas", "n1", {"status": "现行有效", "checked_at": str(TODAY)})  # 缺号 → 计
    write_md(root, "casg", "n2", {"status": "现行有效", "checked_at": str(TODAY)})  # 非 cas/casi → 不计
    write_md(root, "casi", "n3", {"status": "现行有效", "doc_number": "财会〔2026〕1号",
                                  "checked_at": str(TODAY)})  # 有号 → 不计
    out = run_main(hc, monkeypatch, capsys)
    assert "- status=待核：0 ｜ cas/casi 缺文号：1 ｜ checked_at>14天：0/3" in out


def test_hc13_stale_boundary_strict_gt_14(health_mod, monkeypatch, capsys):
    """[P0] checked_at 边界：14 天不计、15 天计（严格 >14）、当天不计。"""
    hc, root = health_mod
    for name, days in (("a", 14), ("b", 15), ("c", 0)):
        write_md(root, "cas", name, {"status": "现行有效", "doc_number": "财会〔2026〕1号",
                                     "checked_at": str(TODAY - timedelta(days=days))})
    out = run_main(hc, monkeypatch, capsys)
    assert "- status=待核：0 ｜ cas/casi 缺文号：0 ｜ checked_at>14天：1/3" in out


def test_hc14_missing_checked_at_defaults_stale(health_mod, monkeypatch, capsys):
    """[P0] checked_at 缺失 → 默认 2000-01-01 → stale。"""
    hc, root = health_mod
    write_md(root, "cas", "a", {"status": "现行有效", "doc_number": "财会〔2026〕1号"})
    out = run_main(hc, monkeypatch, capsys)
    assert "checked_at>14天：1/1" in out


def test_hc15_invalid_date_format_counts_stale(health_mod, monkeypatch, capsys):
    """[P0] 格式非法（2026/09/01、垃圾）→ except 分支按 stale 计，不炸。"""
    hc, root = health_mod
    write_md(root, "cas", "a", {"status": "现行有效", "doc_number": "财会〔2026〕1号",
                                "checked_at": "2026/09/01"})
    write_md(root, "cas", "b", {"status": "现行有效", "doc_number": "财会〔2026〕2号",
                                "checked_at": "垃圾"})
    out = run_main(hc, monkeypatch, capsys)
    assert "checked_at>14天：2/2" in out


def test_hc16_semantically_invalid_date_stale(health_mod, monkeypatch, capsys):
    """[P1] 语义非法 2026-02-30（无此日）→ strptime ValueError → stale。"""
    hc, root = health_mod
    write_md(root, "cas", "a", {"status": "现行有效", "doc_number": "财会〔2026〕1号",
                                "checked_at": "2026-02-30"})
    out = run_main(hc, monkeypatch, capsys)
    assert "checked_at>14天：1/1" in out


def test_hc17_summary_denominator_all_layers(health_mod, monkeypatch, capsys):
    """[P1] 汇总分母 = 全层 md 总数（cas 2 + casi 1 → /3），分子只含跨层的 stale。"""
    hc, root = health_mod
    for layer, name in (("cas", "a"), ("cas", "b"), ("casi", "c")):
        write_md(root, layer, name, {"status": "现行有效", "doc_number": "财会〔2026〕1号",
                                     "checked_at": str(TODAY)})
    out = run_main(hc, monkeypatch, capsys)
    assert "- status=待核：0 ｜ cas/casi 缺文号：0 ｜ checked_at>14天：0/3" in out


# ---------------------------------------------------------------- 配置 / 服务

@pytest.mark.parametrize("porcelain,count", [(" M a\n?? b\n", 2), ("", 0)])
def test_hc18_git_dirty_count(health_mod, monkeypatch, capsys, porcelain, count):
    """[P1] git 未提交变更：sh 返回 porcelain 输出按非空行计数。"""
    hc, _ = health_mod
    out = run_main(hc, monkeypatch, capsys, git_status=porcelain)
    assert f"- git 未提交变更：{count} 条" in out


@pytest.mark.parametrize("result,expect", [(0, "运行中"), (1, "未启动（scripts/start_mcp.bat）")])
def test_hc19_flk_mcp_connect_ex_branches(health_mod, monkeypatch, capsys, result, expect):
    """[P2] flk-mcp：connect_ex 0 → 运行中，非 0 → 未启动文案。"""
    hc, _ = health_mod
    out = run_main(hc, monkeypatch, capsys, sock_result=result)
    assert f"- flk-mcp(18062)：{expect}" in out


def test_hc20_api_key_branches(health_mod, monkeypatch, capsys):
    """[P1] SILICONFLOW_API_KEY 未设/已设双分支文案。"""
    hc, _ = health_mod
    out = run_main(hc, monkeypatch, capsys, api_key=None)
    assert "- SILICONFLOW_API_KEY：未设置（local-rag 语义检索未接线）" in out
    out = run_main(hc, monkeypatch, capsys, api_key="sk-test")
    assert "- SILICONFLOW_API_KEY：已设置" in out


def test_hc21_lawtext_three_branches(health_mod, monkeypatch, capsys):
    """[P1] lawtext：缺失 → 缺失文案；存在+sh返日期 / 存在+sh返空 → 日期 / 未知。"""
    hc, root = health_mod
    out = run_main(hc, monkeypatch, capsys)
    assert "- lawtext 同步：tax/lawtext 缺失" in out

    (root / "tax" / "lawtext").mkdir(parents=True)
    out = run_main(hc, monkeypatch, capsys, git_log="2026-06-01")
    assert "- lawtext 同步：最后提交 2026-06-01" in out
    out = run_main(hc, monkeypatch, capsys, git_log="")
    assert "- lawtext 同步：最后提交 未知" in out


def test_hc22_rules_skills_missing_then_full(health_mod, monkeypatch, capsys):
    """[P2] 规则/技能缺失计数与『缺 [...]』格式；补齐后 5/5、4/4 且无缺列表。"""
    hc, root = health_mod
    out = run_main(hc, monkeypatch, capsys)
    assert ("- 规则文件：0/5 缺 ['project_rules.md', '00-citation-discipline.md', "
            "'01-query-transcription.md', '02-vault-usage.md', '03-vault-update.md']") in out
    assert "- 技能：0/4 缺 ['vault-update', 'case-analysis', 'mcp-ops', 'health-check']" in out

    for r in RULES:
        (root / ".trae" / "rules" / r).write_text("", encoding="utf-8")
    for s in SKILLS:
        (root / ".trae" / "skills" / s).mkdir(parents=True, exist_ok=True)
        (root / ".trae" / "skills" / s / "SKILL.md").write_text("", encoding="utf-8")
    out = run_main(hc, monkeypatch, capsys)
    assert "- 规则文件：5/5" in out
    assert "- 技能：4/4" in out
    assert " 缺 [" not in out


# ---------------------------------------------------------------- 优化空间

def test_hc23_optimization_matrix_11_pending(health_mod, monkeypatch, capsys):
    """[P1] 优化空间矩阵：11 份待核 → 建议行出现（阈值 >10）；policy 缺失行；
    监管指引行恒在；编号 1..4 连续无空洞。"""
    hc, root = health_mod
    for i in range(11):
        write_md(root, "cas", f"p{i:02d}", {"status": "待核", "doc_number": f"财会〔2026〕{i}号",
                                            "checked_at": str(TODAY)})
    out = run_main(hc, monkeypatch, capsys)
    assert "1. 待核 11 份：flk-mcp 或官方源批量核验后固化 overrides.json" in out
    assert "2. policy/ 为空：公司执行办法未入库（分层引用需要）" in out
    assert "3. SILICONFLOW_API_KEY 未设：注册 cloud.siliconflow.cn 后接线 local-rag 语义检索" in out
    assert "4. 监管指引层（securities/garr）未接入：fetch_maodocs.py LAYERS 加一条即可扩层" in out
    numbered = [ln.split(".", 1)[0] for ln in out.splitlines() if re.match(r"^\d+\. ", ln)]
    assert numbered == ["1", "2", "3", "4"]


def test_hc23b_optimization_matrix_10_pending_and_policy(health_mod, monkeypatch, capsys):
    """[P1] 优化空间矩阵另一半：10 份待核无建议行（10 不大于 10）；policy 有文件 → 无空目录行；
    监管指引行仍恒在，编号连续 1..2。"""
    hc, root = health_mod
    for i in range(10):
        write_md(root, "cas", f"p{i:02d}", {"status": "待核", "doc_number": f"财会〔2026〕{i}号",
                                            "checked_at": str(TODAY)})
    (root / "policy").mkdir()
    (root / "policy" / "办法.md").write_text("占位", encoding="utf-8")
    out = run_main(hc, monkeypatch, capsys)
    assert "待核 10 份" not in out
    assert "policy/ 为空" not in out
    assert "监管指引层（securities/garr）未接入" in out
    numbered = [ln.split(".", 1)[0] for ln in out.splitlines() if re.match(r"^\d+\. ", ln)]
    assert numbered == ["1", "2"]  # API key 未设 + 监管指引


# ---------------------------------------------------------------- 修复门 / 全输出结构

def test_hc24_non_utf8_file_degrades_gracefully(health_mod, monkeypatch, capsys):
    """[P2]（原修复门，已修复）非 UTF-8 文件跳过统计，体检报告照常输出。"""
    hc, root = health_mod
    (root / "cas").mkdir()
    (root / "cas" / "bad.md").write_bytes(b"\xff\xfe " + "乱码".encode())
    out = run_main(hc, monkeypatch, capsys)
    assert "# laws-vault 体检" in out
    assert "不可读文件：1" in out


def test_hc25_corrupt_manifest_degrades_gracefully(health_mod, monkeypatch, capsys):
    """[P2]（原修复门，已修复）manifest 非法 JSON → 降级为空基线继续出报告并告警。"""
    hc, root = health_mod
    (root / "scripts" / "state" / "manifest.json").write_text("{oops", encoding="utf-8")
    out = run_main(hc, monkeypatch, capsys)
    assert "## 语料层" in out
    assert "manifest.json 损坏" in out


def test_hc26_section_order(health_mod, monkeypatch, capsys):
    """[P1] 全输出结构：六节标题按序出现。"""
    hc, _ = health_mod
    out = run_main(hc, monkeypatch, capsys)
    marks = ["# laws-vault 体检", "## 语料层", "## 元数据质量", "## 配置", "## 服务", "## 优化空间"]
    pos = [out.index(m) for m in marks]
    assert pos == sorted(pos)
    assert len(set(pos)) == len(pos)
