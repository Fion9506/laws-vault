# 数据来源、更新与致谢

日期：2026-09-30。状态：基于当前工作树和本地第三方快照的来源清单；再分发许可和逐份官方核验仍待完成。

## 1. “数据库”实际指什么

核心知识库是带元数据的Markdown文件，由Git记录版本，不是一个独立数据库服务。

必须区分：官方权威依据源、实际下载/整理源、软件工具。致谢只说明贡献来源，不表示获官方背书、来源文本无误或已取得再分发授权。

## 2. 会计核心资料

| 层 | 当前工作树数量 | 实际采集源 |
| --- | --- | --- |
| `cas/` 会计准则 | 44 | `https://docs.maoyanqing.com/accounting/ent/cas/` |
| `casg/` 应用指南 | 42 | `https://docs.maoyanqing.com/accounting/ent/casg/` |
| `casi/` 准则解释 | 20 | `https://docs.maoyanqing.com/accounting/ent/casi/` |
| `casc/` 应用案例 | 42 | `https://docs.maoyanqing.com/accounting/ent/casc/` |
| `casq/` 实施问答 | 103 | `https://docs.maoyanqing.com/accounting/ent/casq/` |

本轮合计251份；公开发布数量须以允许公开的最终清单为准。

**官方依据源：** [财政部会计司](https://kjs.mof.gov.cn/)发布的准则、解释、应用案例和实施问答等，应逐份核对具体官方网页、正文、适用与执行安排。不能仅凭本地 `org: 财政部` 标签认为核验已完成。

**实际抓取源：** [审计文库 / MaoDocs](https://docs.maoyanqing.com/accounting/ent/)，是第三方整理镜像。本库 [抓取器](../scripts/fetch_maodocs.py)直接使用它的五层目录，并非直接同步财政部所有新文件。

`casg/` 包含《企业会计准则应用指南汇编2024》章节，不得因网页公开可读就认为书籍内容可以重新打包。MaoDocs网站及这批内容的可再分发许可本轮未确认；权限未明确的内容不进入默认公开包。书籍、法规正文、网页整理、数据转换和软件代码的权利应分别核对。

## 3. 当前会计资料更新流程

运行于仓库根目录，需要Python及联网访问主源：

```powershell
python -X utf8 scripts/update_check.py
# 或先做有限检查：仍检查五层目录新链接，只比对manifest前15项的正文。
python -X utf8 scripts/update_check.py --sample 15
```

哨兵发现新页面、比对正文SHA-256，并输出 `changelog/pending-YYYYMMDD.md`。`--sample` 不是随机抽样，有限检查不能证明全库未变化。

建议维护顺序：

1. 查新，阅读待审清单；源不可达或部分页面没核验时保留限制。
2. 逐项对照官方正文与执行安排，特别核查文号、状态、主体与版本变化。
3. 备份/审阅现有Git差异，人工确认后重抓有关层，例如：

```powershell
python -X utf8 scripts/fetch_maodocs.py --layers cas,casi
```

4. 将有证据的人工元数据修正写入 `scripts/overrides.json`，检查正文、元数据和清单变化；不要直接手改正文而期望重抓保留修改。
5. 运行体检与离线测试，完成资料审核后再选择性提交并写更新日志。

抓取器会覆盖层内已有文件，其本身没有程序化审批门禁。“人工确认后抓取”是当前工作流约定，发布前仍须加强。

建议每周及重要准则发布后维护，但本项目当前没有部署会计资料自动更新任务，不承诺每周自动得到最新官方准则。

`fetched_at` 是采集信息；当前 `checked_at` 同样被脚本写为采集当天，不能表示官方时效核验。应在修补后分开保存采集日、核验日、核验源和待核事项。

## 4. 可选/历史扩展与致谢

下面组件存在于维护者本机，但不是会计核心发布包依赖，主仓库也不会通过clone自动带上它们。

| 项目 | 贡献或用途 | 当前边界 |
| --- | --- | --- |
| [lawtext/laws：中国法律法规在线文库](https://github.com/lawtext/laws) | 将国家法律法规数据库资料转换成Markdown的第三方镜像 | 综合法律层，不是会计准则主源；许可未核实，不默认捆绑 |
| [moyupeng0422/legal-tools](https://github.com/moyupeng0422/legal-tools) | 国家法律法规数据库MCP等工具 | 相关flk MCP为CC-BY-NC许可；企业用途须确认授权，不因根项目新增其他MIT工具而重授此MCP |
| [ZongziForu/npc-law-db：CN Law Hub](https://github.com/ZongziForu/npc-law-db) | 多官方源采集、检索与MCP | 本库未完成接入；维护者自有核心按其条款于2026-09-21转Apache-2.0，贡献者组件另按各自授权，不笼统断言全库统一许可 |
| [nigo81/nigo-skills：Local RAG](https://github.com/nigo81/nigo-skills) | 可选Chroma语义检索、嵌入与重排 | 本库未接线；本地README声明MIT，实际复用前核实许可证文本与依赖 |

lawtext说明其原文来自 [国家法律法规数据库](https://flk.npc.gov.cn/)，使用markitdown转换；法律真实性仍需核对原始来源，不因Markdown存在而完成验证。

lawtext本地工作流设定周六05:05 UTC，即北京时间13:05，由**第三方项目的GitHub Actions**执行。该定时配置不是实际成功时间，也不是“官方Actions自动更新”。本地最近可见自动更新提交为2026-09-26；本轮没有核对线上最新运行结果。公开工作流使用secrets指向其他输入仓库，因此本地clone并非完整采集链的复现保证。

本地快照标识，便于追溯而非推荐用户安装旧版：

```text
lawtext/laws                 697ae4290f6389f99028555396a0fc4a934ad665
moyupeng0422/legal-tools     15d7f7646cdb6fbcaeaf9a145c9e22b0cb3ef93e
ZongziForu/npc-law-db        e0a6724afeebcc23ac22d7d667db1cdb9ba6e670
nigo81/nigo-skills           64682115565072d1db79a5f29615dd3fdc7f6174
```

核心准则问答不依赖上述镜像和工具持续在线。更新第三方工具也不能替代准则资料的官方适用性核验。

## 5. 建议公开的致谢文字

> 感谢财政部及会计司发布会计准则、解释、应用案例和实施问答，为企业会计处理研究提供权威出处；感谢审计文库（MaoDocs）的资料整理工作，本项目当前会计资料采集来自其公开页面。另感谢lawtext/laws、moyupeng0422/legal-tools、ZongziForu/npc-law-db、nigo81/nigo-skills提供的第三方资料整理或工具探索基础。上述致谢不表示任何官方或作者背书，不替代许可证、来源核验与再分发授权；可选扩展不属于核心运行依赖。

如果最终发布包并未使用某个组件，应将其标为历史探索/相关工具，不描述为生产运行依赖。每份实际公开资料应保留具体来源链接，而不只保留总括致谢。

## 6. 发布时必须明确

- 原创软件/规则许可证与知识资料来源及权限分别说明；一个MIT文件不能覆盖书籍与全部第三方内容。
- 公布每层收录范围和资料版本日期，不称“全法规库”或“时刻保持最新”。
- 保留具体官方链接、镜像链接、文档唯一标识、版本及审核记录；更新公开清单与哈希基线。
- 提供错漏报告入口，要求附官方出处和可复现场景；不通过Issue收集真实合同、客户信息或秘密材料。
- 抓取授权、合理访问频率、资料再分发与模型输入权限分别审查，不能将“能下载”解释为“可以任意使用”。

补充背景：[The Legal Side of Open Source](https://opensource.guide/legal/)。本清单不是法律意见或资料授权证明。
