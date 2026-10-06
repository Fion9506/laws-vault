# laws-vault 离线测试夹具：网络全部 stub，文件系统全部进 tmp 沙箱。
#
# 契约（所有 test_*.py 必须遵守）：
# 1. autouse 网络熔断器 no_net：任何经 urllib.request.urlopen 的真实请求立即 AssertionError。
#    需要模拟 HTTP 的用例请 patch Router（sandbox/update_mod 已自动安装）或自行
#    monkeypatch urllib.request.urlopen（会覆盖熔断器，测试级补丁先生效）。
# 2. sandbox/update_mod 重定向模块级路径常量（ROOT/MANIFEST/OVERRIDES/STATE_DIR/CHANGELOG）
#    到 tmp 沙箱，绝不触碰真实库。
# 3. update_check 通过 `from fetch_maodocs import http_get, discover, ...` 值拷贝符号，
#    discover 内部解析 fetch_maodocs.http_get——update_mod 已把同一个 Router 同时装进
#    两个命名空间，杜绝"只补一处、另一处直连真网"的旁路。
import importlib
import json
import re
import sys
from hashlib import sha256
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


@pytest.fixture(autouse=True)
def no_net(monkeypatch):
    """网络熔断器：证明整套测试零真实联网。"""
    import urllib.request

    def _boom(*a, **k):
        raise AssertionError("真实网络访问被熔断器拦截！")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)


class Router:
    """url -> html 路由表；未登记的 url 返回 None（模拟网络失败）。记录调用序。"""

    def __init__(self):
        self.pages = {}
        self.calls = []

    def __call__(self, url, retries=1):
        self.calls.append(url)
        return self.pages.get(url)


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """重载 fetch_maodocs，路径常量重定向到 tmp；http_get 换成 Router。"""
    fm_mod = importlib.reload(importlib.import_module("fetch_maodocs"))
    root = tmp_path / "vault"
    state = root / "scripts" / "state"
    state.mkdir(parents=True)
    overrides = root / "scripts" / "overrides.json"
    router = Router()
    monkeypatch.setattr(fm_mod, "ROOT", root)
    monkeypatch.setattr(fm_mod, "MANIFEST", state / "manifest.json")
    monkeypatch.setattr(fm_mod, "STATE_DIR", state)
    monkeypatch.setattr(fm_mod, "OVERRIDES", overrides)
    monkeypatch.setattr(fm_mod, "DELAY", 0)
    monkeypatch.setattr(fm_mod, "http_get", router)
    return fm_mod, {
        "root": root, "state": state, "overrides": overrides, "router": router,
    }


@pytest.fixture()
def update_mod(sandbox, monkeypatch):
    """重载 update_check 并重定向 ROOT/CHANGELOG/DELAY；Router 双点注入。"""
    uc = importlib.reload(importlib.import_module("update_check"))
    fm_mod, dirs = sandbox
    router = dirs["router"]
    monkeypatch.setattr(uc, "ROOT", dirs["root"])
    monkeypatch.setattr(uc, "CHANGELOG", dirs["root"] / "changelog")
    monkeypatch.setattr(uc, "DELAY", 0)
    monkeypatch.setattr(uc, "http_get", router)
    return uc, dirs


@pytest.fixture()
def health_mod(tmp_path, monkeypatch):
    """重载 health_check 并重定向 ROOT 到 tmp 沙箱（.trae 骨架 + state 目录）。"""
    hc = importlib.reload(importlib.import_module("health_check"))
    root = tmp_path / "vault"
    (root / ".trae" / "rules").mkdir(parents=True)
    (root / ".trae" / "skills" / "vault-update").mkdir(parents=True)
    (root / "scripts" / "state").mkdir(parents=True)
    monkeypatch.setattr(hc, "ROOT", root)
    return hc, root


# ---------------------------------------------------------------- HTML 工厂

def make_page(title="测试文档", body=None, doc_number="财会〔2026〕1号",
              org="财政部", issue="2026-01-01", eff="2026-02-01",
              status="现行有效", modified="2026-01-01T00:00:00+08:00", extra_head="",
              raw_title=None, raw_meta=None):
    """构造 MaoDocs 风格 HTML（<title> 带 | 审计文库 后缀 + meta modified_time + <main> 正文）。

    raw_title/raw_meta 可整体替换 head 中的对应片段（测属性顺序/异常 title）。
    """
    if body is None:
        body = (
            f"发文机关：{org}\n发布日期：{issue}\n生效日期：{eff}\n时效性：{status}\n"
            f"{doc_number}\n各省、自治区、直辖市财政厅（局）：\n"
            + "第一条 为规范企业会计确认、计量和列报行为，制定本准则。" * 12
        )
    body_html = "".join(f"<p>{ln}</p>" for ln in body.splitlines())
    title_html = raw_title if raw_title is not None else f"<title>{title} | 审计文库（MaoDocs）</title>"
    meta_html = raw_meta if raw_meta is not None else \
        f'<meta name="article:modified_time" content="{modified}">'
    return (
        "<!DOCTYPE html><html><head>" + title_html + meta_html +
        "</head><body><nav>导航噪声</nav>"
        f"<main><h1>{extra_head}{title}</h1>{body_html}</main>"
        "<footer>页脚噪声</footer></body></html>"
    )


def make_listing(layer, names):
    """构造层目录页 HTML，names 为文件名列表（不含扩展名）。"""
    links = "".join(
        f'<a href="/accounting/ent/{layer}/{n}.html">{n}</a>' for n in names
    )
    return f"<html><body><main>{links}</main></body></html>"


# ---------------------------------------------------------------- 校验助手

def parse_fm_text(text):
    """独立实现的 front-matter 解析（不依赖被测代码）。"""
    assert text.startswith("---\n"), "缺少 front-matter 起始符"
    end = text.index("\n---\n", 3)
    out = {}
    for ln in text[4:end].splitlines():
        if ":" in ln:
            k, v = ln.split(":", 1)
            out[k.strip()] = v.strip()
    return out, text[end + 5:]


def read_front_matter(path):
    """读取生成的 md 的 (front-matter dict, 正文)。"""
    return parse_fm_text(Path(path).read_text(encoding="utf-8"))


CLEAN_RE = re.compile(r"^约\s*\d+\s*字.*分钟$\n?", re.MULTILINE)


def cleaned_sha(body):
    """复刻 fetch_maodocs L207 / update_check L54 的入库前清洗哈希。"""
    return sha256(CLEAN_RE.sub("", body).strip().encode("utf-8")).hexdigest()


def write_manifest(state_dir, entries):
    """直接写沙箱 manifest.json。"""
    p = Path(state_dir) / "manifest.json"
    p.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def write_md(root, layer, name, fields, body="正文占位。"):
    """写一个带 front-matter 的语料 md 到沙箱层目录。"""
    d = Path(root) / layer
    d.mkdir(parents=True, exist_ok=True)
    lines = ["---"] + [f"{k}: {v}" for k, v in fields.items()] + ["---", "", body]
    p = d / f"{name}.md"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p
