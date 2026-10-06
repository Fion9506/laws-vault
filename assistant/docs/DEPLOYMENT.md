# 部署指南

更新：2026-10-06。公开代码为研究工具alpha，完整资料另存私有仓库。先阅读 [仓库说明](../../README.md)，再将 `assistant/` 作为客户端项目根目录。下述未验证的平台和业务验收边界仍然有效。

## 1. 部署的是什么

本项目是本地Markdown知识库、助手规则/技能和维护脚本，不是一个独立的聊天网站、模型服务器或数据库服务。

最小运行组合：允许使用的准则资料 + 支持本地文件访问的AI客户端。默认入口为TraeWork桌面版的本地项目。只读资料与分析不要求先安装Python；运行检索、体检、更新和测试脚本时需要Python。

不需要先安装Qdrant、Chroma、数据库服务、税法镜像或第三方MCP，也不需要单独申请嵌入/重排API Key。模型访问及其费用仍由所用AI客户端决定，不能据此宣称AI全程离线。

## 2. 环境与验证边界

| 项目 | 要求 / 本轮情况 |
| --- | --- |
| AI客户端 | TraeWork桌面版、本地任务；须有本库文件读取权限 |
| Git | 使用clone与更新归档时需要；下载已审核资料包时可不使用 |
| Python | 脚本文档声明3.10+；本轮测试环境为3.14.3，不代表所有版本已测试 |
| pytest | 仅测试需要；本轮9.0.2，共173项通过 |
| Windows | 有历史运行记录，本轮完成脚本验证；当前TraeWork真实问答仍待验收 |
| macOS / Linux | 核心资料和Python脚本具有可移植设计，但未完成部署验收；`.bat` 不适用 |
| 云端/网页版 | 不属于首版部署承诺；本地路径和localhost服务不能直接视为云端资源 |

TraeWork对项目规则、项目技能和本地/云端的官方说明：[规则](https://docs.trae.cn/work_rules)、[技能](https://docs.trae.cn/work_skills)。

## 3. 获取发布包

从公开代码仓库克隆，随后进入实际助手工作区：

```powershell
git clone https://github.com/Fion9506/laws-vault.git
cd laws-vault/assistant
```

公开代码目录包含脚本、规则、Skills和合成测试，不包含资料正文。完整251份资料与manifest存于 [私有资料仓库](https://github.com/Fion9506/laws-vault-data) 的 `laws-vault-data-20261006.zip`；有访问权的维护者将其解压到 `assistant/`。其他使用者须自行准备有权使用的同格式语料。不要把私有资料复制到公开提交中。

拿到发布包后确认有 `.trae/rules/project_rules.md`、`.trae/skills/case-analysis/SKILL.md` 和声明支持的资料目录；如果资料缺失，按来源/许可说明处理，不能让模型凭记忆替代缺失资料。

## 4. 在TraeWork使用本地项目

1. 将仓库根目录作为TraeWork的本地项目目录，不只挂载某个子目录。
2. 确认任务使用本地环境；按需允许AI读取本库及运行只读检索脚本。
3. 检查项目规则与 `case-analysis` 技能是否进入上下文。官方项目位置分别是 `.trae/rules/` 与 `.trae/skills/`。
4. 开启新对话，使用下面的冒烟问题；规则未加载时可明确要求先读文件。

```text
请先阅读 .trae/rules/project_rules.md 和
.trae/skills/case-analysis/SKILL.md。
只就会计处理分析：我们销售设备并附三年免费保养。
请先列出缺失事实，排查保证类/服务类质保，再检索依据。
不要直接给单一结论，不要凭记忆编造条文。
```

成功标准是出现真实库内引用、可核对摘录和处理分支，不是仅能聊天或显示技能名称。输入、产物与正式意见的复核方法见 [使用指南](USAGE.md)。

## 5. 可选的脚本自检

在仓库根目录运行；如果使用虚拟环境，命令中的 `python` 应指向该环境解释器。

```powershell
python --version
python -X utf8 scripts/health_check.py
python -X utf8 scripts/search_vault.py '质量保证' --layers cas,casi,casc,casq --max-lines 3
```

运行测试需要安装pytest，建议使用已妥善排除的虚拟环境，不把环境目录提交到Git：

```powershell
python -m pip install pytest
python -X utf8 -m pytest tests/ -q -p no:cacheprovider
```

数量对账失败、缺文件或坏清单需要排查；MCP未启动、语义检索Key未设置在最小配置下不是必须修复的错误。`health_check.py` 当前检查的是数量等基础项目，不能证明正文完整、规则已加载或会计意见正确。

## 6. 可选增强

- 官方在线核验：仅在明确需要时配置适合所需文件的官方源/工具；某个MCP在线不代表一定收录财政部会计文件。
- `legal-tools` flk MCP：独立第三方、许可与联网要求另行审核；不是默认部署步骤。
- `nigo-skills` Local RAG：可选语义检索，需额外依赖和嵌入/重排服务，当前本库未接线。
- `tax/lawtext`、CN Law Hub：属于历史扩展探索，不是本次会计处理首版的必要组件。

不在默认安装时自动克隆/安装全部扩展；不得把本机手工安装事实写成新用户自动具备的功能。

## 7. 发布后的更新

先区分助手代码升级与知识资料更新。代码升级应审阅Release和差异；资料更新执行 [来源文档中的人工审核流程](SOURCES_AND_ACKNOWLEDGEMENTS.md)。首次使用无需立即全量重抓，否则会覆盖当前语料。

部署时仍须区分代码测试、资料核验与真实会计业务验收。脚本测试通过不代表当前TraeWork问答、历史/分主体版本判断或全部会计结论已经验证。
