---
name: mcp-ops
description: 启动/检查法规库 MCP 服务（flk 在线核查 server、local-rag 语义检索）。触发词：启动MCP、启动服务、MCP状态、开启核查、语义检索服务。
---

# MCP 服务运维技能

## flk-mcp 启动（按执行环境二选一）

### 路径 A：AI agent 终端（推荐，一次成功）

agent 的命令会话结束时**会回收后台子进程**，`start`/`Start-Process` 拉起的服务短命。必须用**长驻终端前台启动**：

```powershell
# 命令类型选 web_server / long_running_process（非阻塞），工作目录如下：
python scripts\server.py
```

- cwd：`mcp\legal-tools\国家法律法规数据库MCP`
- 等待 8~9 秒后看到 `Uvicorn running on http://127.0.0.1:18062` 即成功
- 该终端须保持运行，不得在其上再执行其他命令

### 路径 B：人工交互（双击 / 交互式 cmd）

```bat
scripts\start_mcp.bat
```

脚本行为（2026-09-26 重写）：幂等探活（已运行直接退出）→ 依赖自检并自动安装 → server 入口检查 → 后台启动（日志落 `logs\flk-mcp.log`）→ ping 等待重试探活（最多 20 秒）。适合用户手动执行；agent 终端里 `start` 的子进程可能被会话回收，agent 一律走路径 A。

## 依赖（不要假设已装）

flk-mcp：`mcp<2`、`httpx`、`pydantic`、`python-dotenv`。缺失时 bat 会自动安装；手动安装命令：

```powershell
python -m pip install "mcp<2" httpx pydantic python-dotenv
```

## 验证 flk-mcp 可用性

```powershell
python scripts\verify_flk.py
```

脚本已内置 `NO_PROXY=127.0.0.1,localhost`（**必须**：系统代理会拦截回环请求，导致 502 Bad Gateway 假故障）。应输出 `flk-mcp OK (11 tools): flk_search, flk_get_detail, ...`。

禁止用 bash heredoc 方式内联验证（PowerShell 不支持 `<<`）。

## 服务清单

| 服务 | 地址/形态 | 依赖 | 状态来源 |
|---|---|---|---|
| flk-mcp | http://127.0.0.1:18062/mcp（streamable-http） | mcp<2、httpx、pydantic、python-dotenv | `scripts\verify_flk.py` |
| local-rag | stdio（mcp/nigo-skills/local-rag/mcp_server.py） | fastmcp + requirements + 环境变量 SILICONFLOW_API_KEY | key 是否设置 |
| cn-law-hub | stdio（mcp/npc-law-db/mcp_server.py） | 见其仓库 README（税法公告采集） | 仓库存在性 |

## 启动故障复盘（2026-09-26，勿重蹈）

| # | 故障 | 根因 | 对策（已固化） |
|---|---|---|---|
| F1 | `ModuleNotFoundError: No module named 'mcp'` | 文档声称依赖"已装"但实际环境缺失 | bat 增加依赖自检+自动安装；文档不再写"已装" |
| F2 | `ERROR: Input redirection is not supported` | `timeout /t /nobreak` 在 stdin 被重定向的 agent 终端立即崩溃 | bat 改用 `ping -n 3 127.0.0.1 >nul` 等待 |
| F3 | 端口探活成功后服务消失 | agent 命令会话结束回收 `start`/`Start-Process` 后台子进程 | 路径 A：长驻终端前台启动，命令设为 web_server 类型 |
| F4 | 验证报 `502 Bad Gateway` | 系统代理（HTTP_PROXY）拦截 127.0.0.1 请求 | 验证脚本内置 NO_PROXY，永远先于 httpx 请求设置 |

## 已知风险

- 上游 flk.npc.gov.cn 间歇超时（反爬）：属预案内，兜底=库内 front-matter + tax/lawtext 镜像；超时必须向用户明示「本次未在线核验」。
- local-rag 需要用户到 https://cloud.siliconflow.cn 免费注册取 SILICONFLOW_API_KEY（环境变量），缺失时报告「语义检索未配置，当前 grep 模式可用」。
- cn-law-hub 仓库当前不存在（2026-09-26 核查），缺失时如实报告，勿猜测。
