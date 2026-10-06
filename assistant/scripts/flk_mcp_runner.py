"""flk-mcp 启动/守护器（含 TTL 自动关闭）。

用法（cwd = 仓库根目录）：
  python scripts/flk_mcp_runner.py                    # 前台启动（agent 长驻终端推荐），默认 30 分钟后自动关闭
  python scripts/flk_mcp_runner.py --ttl-minutes 60   # 自定义存活分钟数（0 = 不自动关闭）
  python scripts/flk_mcp_runner.py --detach           # 后台分离启动 + 前台探活 ≤20s（start_mcp.bat 用此模式）
  python scripts/flk_mcp_runner.py --status           # 仅探活

TTL 优先级：--ttl-minutes 参数 > 环境变量 FLK_TTL_MINUTES > 默认 30。
设计要点（2026-09-26 复盘固化）：
  - 不用 `timeout /t`（重定向 stdin 下崩溃）→ 全部等待用 Python sleep；
  - 依赖不假设已装 → 启动前自检并自动 pip install "mcp<2" ...；
  - agent 会话会回收 start/Start-Process 后台子进程 → agent 走前台模式（本脚本常驻直到 TTL 到期）；
  - 系统代理拦截 127.0.0.1 → 子进程环境注入 NO_PROXY=127.0.0.1,localhost。
"""
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST, PORT = "127.0.0.1", 18062
URL = f"http://{HOST}:{PORT}/mcp"
LOG = ROOT / "logs" / "flk-mcp.log"
DEP_PKGS = ["mcp<2", "httpx", "pydantic", "python-dotenv"]
DEP_IMPORT = "import mcp, httpx, pydantic, dotenv"
BOOT_TIMEOUT = 30  # 子进程拉起后端口必须在此秒数内可连，否则判启动失败并回收
PROBE_ATTEMPTS = 20  # --detach 模式前台探活次数（1s/次）

DETACHED_FLAGS = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
    subprocess, "CREATE_NEW_PROCESS_GROUP", 0
)


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def probe() -> bool:
    s = socket.socket()
    s.settimeout(1)
    try:
        return s.connect_ex((HOST, PORT)) == 0
    finally:
        s.close()


def log_tail(n: int = 15) -> str:
    try:
        lines = LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-n:])
    except OSError:
        return "(no log)"


def ensure_deps() -> bool:
    if subprocess.run([sys.executable, "-c", DEP_IMPORT]).returncode == 0:
        return True
    print(f"[{ts()}] [FIX] installing deps: {' '.join(DEP_PKGS)} ...", flush=True)
    subprocess.run(
        [sys.executable, "-m", "pip", "install", *DEP_PKGS, "--quiet",
         "--disable-pip-version-check"],
        check=False,
    )
    return subprocess.run([sys.executable, "-c", DEP_IMPORT]).returncode == 0


def find_server_dir() -> Path | None:
    exact = ROOT / "mcp" / "legal-tools" / "国家法律法规数据库MCP"
    if (exact / "scripts" / "server.py").is_file():
        return exact
    cands = [
        d for d in (ROOT / "mcp" / "legal-tools").glob("*MCP")
        if d.is_dir() and (d / "scripts" / "server.py").is_file()
    ]
    for d in cands:  # 名字含“国家法律法规”者优先
        if "国家法律法规" in d.name:
            return d
    return cands[0] if cands else None


def spawn_server(log_fh) -> subprocess.Popen:
    srv = find_server_dir()
    if srv is None:
        raise FileNotFoundError("mcp/legal-tools/*MCP/scripts/server.py not found")
    env = dict(os.environ)
    env["NO_PROXY"] = env["no_proxy"] = "127.0.0.1,localhost"
    LOG.parent.mkdir(exist_ok=True)
    return subprocess.Popen(
        [sys.executable, "-u", "scripts/server.py"],
        cwd=srv, env=env, stdout=log_fh, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
    )


def kill_tree(child: subprocess.Popen) -> None:
    child.terminate()  # Windows 上即 TerminateProcess
    try:
        child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(child.pid)], check=False)
        child.wait(timeout=10)


def supervise(ttl_min: float) -> int:
    """前台守护：拉起 server，TTL 到期或崩溃时回收并退出。"""
    if probe():
        print(f"[{ts()}] [OK] flk-mcp already running: {URL}")
        return 0
    if not ensure_deps():
        print(f"[{ts()}] [FAIL] deps missing. Run: python -m pip install {' '.join(DEP_PKGS)}")
        return 1
    started = time.monotonic()
    ttl_deadline = started + ttl_min * 60 if ttl_min > 0 else None
    with LOG.open("a", encoding="utf-8", errors="replace") as fh:
        print(f"[{ts()}] [START] launching flk-mcp (ttl={ttl_min:g} min) ...", flush=True)
        child = spawn_server(fh)
        if ttl_deadline:
            eta = (datetime.now() + timedelta(minutes=ttl_min)).strftime("%H:%M:%S")
            print(f"[{ts()}] [TTL] auto-close at {eta} (pid {child.pid})", flush=True)
        try:
            while True:
                rc = child.poll()
                if rc is not None:
                    print(f"[{ts()}] [FAIL] server exited code={rc} after "
                          f"{time.monotonic() - started:.0f}s. Log tail:\n{log_tail()}", flush=True)
                    return 1
                now = time.monotonic()
                if ttl_deadline and now >= ttl_deadline:
                    print(f"[{ts()}] [TTL] {ttl_min:g} min elapsed, shutting down "
                          f"(pid {child.pid})", flush=True)
                    kill_tree(child)
                    print(f"[{ts()}] [OK] flk-mcp closed.", flush=True)
                    return 0
                if now - started > BOOT_TIMEOUT and not probe():
                    print(f"[{ts()}] [FAIL] no listener within {BOOT_TIMEOUT}s. "
                          f"Log tail:\n{log_tail()}", flush=True)
                    kill_tree(child)
                    return 1
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"[{ts()}] [STOP] interrupted, killing server ...", flush=True)
            kill_tree(child)
            return 130


def detach(ttl_min: float) -> int:
    """分离模式（人工双击 bat 场景）：后台常驻守护进程 + 前台探活 ≤20s 后退出。"""
    if probe():
        print(f"[OK] flk-mcp already running: {URL}")
        return 0
    if not ensure_deps():
        print(f"[FAIL] deps missing. Run: python -m pip install {' '.join(DEP_PKGS)}")
        return 1
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8", errors="replace") as fh:
        subprocess.Popen(  # 分离的守护进程：独立于本控制台存活，负责 TTL 回收
            [sys.executable, str(Path(__file__).resolve()), "--_supervise",
             "--ttl-minutes", str(ttl_min)],
            stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            creationflags=DETACHED_FLAGS, cwd=str(ROOT),
        )
    for _ in range(PROBE_ATTEMPTS):
        time.sleep(1)
        if probe():
            msg = "no auto-close" if ttl_min <= 0 else f"auto-close after {ttl_min:g} min"
            print(f"[OK] flk-mcp started: {URL} ({msg}). Log: {LOG.relative_to(ROOT)}")
            return 0
    print(f"[FAIL] no listener within {PROBE_ATTEMPTS}s. Log tail:\n{log_tail()}")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="flk-mcp launcher with TTL auto-close")
    ap.add_argument("--ttl-minutes", type=float, default=None,
                    help="存活分钟数，0=不自动关闭（默认取 FLK_TTL_MINUTES 或 30）")
    ap.add_argument("--detach", action="store_true", help="后台分离启动+前台探活")
    ap.add_argument("--status", action="store_true", help="仅探活")
    ap.add_argument("--_supervise", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()

    if args.status:
        up = probe()
        print(f"flk-mcp {'UP' if up else 'DOWN'}: {URL}")
        return 0 if up else 1

    ttl = args.ttl_minutes
    if ttl is None:
        ttl = float(os.environ.get("FLK_TTL_MINUTES", "30") or 30)

    if args._supervise or not args.detach:
        return supervise(ttl)
    return detach(ttl)


if __name__ == "__main__":
    sys.exit(main())
