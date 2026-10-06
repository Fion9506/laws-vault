"""SV-01..SV-08：scripts/search_vault.py 离线测试（tmp 沙箱语料，零网络）。

契约锚点：01 规则 Step 2 的确定性兜底——退出码 1 = 全库无命中 = 拒答判定，
该语义被 case-analysis 技能与 02 规则引用，不得改变。
"""
import importlib.util
import sys
from pathlib import Path

import pytest

from conftest import SCRIPTS, write_md


@pytest.fixture()
def sv():
    spec = importlib.util.spec_from_file_location("search_vault_t", SCRIPTS / "search_vault.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run(sv, monkeypatch, capsys, *argv):
    monkeypatch.setattr(sys, "argv", ["search_vault.py", *argv])
    code = sv.main()
    return code, capsys.readouterr().out


@pytest.fixture()
def vault(tmp_path):
    write_md(tmp_path, "cas", "14", {
        "doc_number": "财会〔2017〕22号", "status": "有效", "effective_date": "2018-01-01",
    }, "第一条 占位。\n第三十三条 对于附有质量保证条款的销售，企业应当评估该质量保证。\n"
        "第五十条 质量保证的类型及相关义务的披露要求。\n")
    write_md(tmp_path, "casq", "30__20250417", {
        "doc_number": "财会〔2014〕7号", "status": "有效", "effective_date": "2014-07-01",
    }, "问：保证类质量保证预计负债如何列示？答：区分一年内外列报。")
    write_md(tmp_path, "policy", "维修服务", {}, "公司免费保养三年服务口径：按服务类质保处理。")
    return tmp_path


# ---------------------------------------------------------------- 命中与格式

def test_sv01_hit_shows_fm_head_anchor_and_exit0(sv, vault, monkeypatch, capsys):
    """[P0] 命中：相对路径 + front-matter 时效头 + L行号[第X条]锚点 + 退出码 0。"""
    code, out = run(sv, monkeypatch, capsys, "质量保证", "--root", str(vault))
    assert code == 0
    assert "cas/14.md" in out
    assert "财会〔2017〕22号" in out and "有效" in out
    assert "[第三十三条]" in out and "[第五十条]" in out
    assert "[search] 命中" in out


def test_sv02_no_hit_exit1_is_refusal_signal(sv, vault, monkeypatch, capsys):
    """[P0] 全库 0 命中 → 退出码 1（拒答判定语义，规则层依赖）。"""
    code, _ = run(sv, monkeypatch, capsys, "不存在的术语xyz", "--root", str(vault))
    assert code == 1


def test_sv03_layers_filter_scopes_search(sv, vault, monkeypatch, capsys):
    """[P1] --layers 限定：术语只在 cas → 限定 casq 后 0 命中退出 1。"""
    code, out = run(sv, monkeypatch, capsys, "质量保证条款", "--layers", "cas",
                    "--root", str(vault))
    assert code == 0 and "cas/14.md" in out
    code2, out2 = run(sv, monkeypatch, capsys, "质量保证条款", "--layers", "casq",
                      "--root", str(vault))
    assert code2 == 1


def test_sv04_and_requires_all_terms_same_file(sv, vault, monkeypatch, capsys):
    """[P1] --and 文件级 AND：分居两文件的词 OR 命中、AND 不命中。"""
    code_or, _ = run(sv, monkeypatch, capsys, "质量保证", "列示", "--root", str(vault))
    assert code_or == 0
    code_and, out_and = run(sv, monkeypatch, capsys, "质量保证", "列示", "--and",
                            "--root", str(vault))
    assert code_and == 0 and "casq/30__20250417.md" in out_and  # 两词同在 casq 文件
    code_and2, _ = run(sv, monkeypatch, capsys, "质量保证条款", "免费保养", "--and",
                       "--root", str(vault))
    assert code_and2 == 1  # 两词分居 cas 与 policy，无同文件共现


def test_sv05_no_frontmatter_file_still_hits(sv, vault, monkeypatch, capsys):
    """[P2] 无 front-matter（policy 层）仍可命中，头行显示「无 front-matter」。"""
    code, out = run(sv, monkeypatch, capsys, "免费保养", "--layers", "policy",
                    "--root", str(vault))
    assert code == 0 and "policy/维修服务.md" in out and "无 front-matter" in out


def test_sv06_max_lines_truncation_note(sv, vault, monkeypatch, capsys):
    """[P2] 命中行数超 --max-lines → 提示「另有 N 行命中」。"""
    code, out = run(sv, monkeypatch, capsys, "质量保证", "--root", str(vault),
                    "--max-lines", "1")
    assert code == 0 and "另有" in out and "行命中" in out


def test_sv07_invalid_regex_exits_2(sv, vault, monkeypatch, capsys):
    """[P2] 非法正则 → 退出码 2（用法错误，与拒答的 1 区分）。"""
    code, _ = run(sv, monkeypatch, capsys, "([", "--root", str(vault))
    assert code == 2


def test_sv08_case_insensitive_match(sv, vault, monkeypatch, capsys):
    """[P2] 忽略大小写：IFRS 与 ifrs 互中。"""
    write_md(vault, "casc", "case1", {}, "参考 IFRS 15 的五步法。")
    code, out = run(sv, monkeypatch, capsys, "ifrs", "--layers", "casc",
                    "--root", str(vault))
    assert code == 0 and "casc/case1.md" in out
