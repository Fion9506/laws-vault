# GitHub 相近工具与重合程度

检索日期：2026-09-30。

## 1. 结论

**有重合，不能把“会计事实问答 + 条文依据”宣传为首次出现。**

本轮发现会计准则RAG、会计专业Skill、带证据/人工复核规则的会计工作流等相近形态。较明显的业务重合是韩国 `rag_for_accounting`；专业工作流形态还有 `chwezi-accounting-doctrine`。国内有CPA知识Skill，财务办公工具中也有可互补的对账Skill。

本项目仍有可建设的明确范围：中国企业会计准则多层资料、业务事实驱动的候选准则排查、可核对引用、主体和时点适用，以及既有AI客户端内的轻量使用。它们是目标和已有设计方向，不是已经证明的质量优势。

本轮没有确认一个可以无需改造就替代本库全部目标的现成项目，但这不等于证明不存在同类产品。不要宣传“唯一”或依据GitHub星数推断专业准确性。

## 2. 检索方法与证据边界

查询包括“会计准则 AI 助手”“企业会计准则 RAG”“会计准则 问答/知识库”“会计 skills 准则”“accounting standards assistant”“IFRS RAG”等，范围为公开GitHub及其原始文件。

读取了下列仓库的README、相关Skill或配置说明；没有部署外部项目、跑它们的测试、核对每份知识资料权利或开展匹配模型/预算的质量比较。下列能力均按维护者公开描述归纳，不当作实测正确率。公开在GitHub不等于全部内容都符合开放源代码许可。

## 3. 主要相近项目

| 项目 | 重合点 | 关键区别 | 判断 |
| --- | --- | --- | --- |
| [dongtan-91-dong-welfare-center/rag_for_accounting](https://github.com/dongtan-91-dong-welfare-center/rag_for_accounting) | 自然语言会计处理问答，原文条款检索和引用输出 | 当前以韩国K-GAAP为主；LangGraph/pgvector等独立应用，K-IFRS为后续方向 | 业务概念直接重合，知识体系和部署方式不同 |
| [peterbamuhigire/chwezi-accounting-doctrine](https://github.com/peterbamuhigire/chwezi-accounting-doctrine) | 会计判断备忘录、来源登记、审核与专业Skill | IFRS/IFRS for SMEs及多个其他标准，含东非等法域与广泛财务工作流 | 专业工作流和证据治理部分直接重合，不是中国CAS专用 |
| [yjkj999999/cpa-china-2026](https://github.com/yjkj999999/cpa-china-2026) | 中国会计准则知识、会计专业问答、Skill形态 | 基于CPA考试六科知识体系的概览Skill | 国内主题和入口重合；完整资料/更新/校验效果未验证 |
| [DanTCIM/ValAct_RAG](https://github.com/DanTCIM/ValAct_RAG) | 专业文档问答与引用上下文，包含US GAAP/IFRS17 | 主要为寿险估值精算；采用外部嵌入、向量检索、重排和模型服务 | 原理重合，专业对象与运行依赖不同 |
| [cxtx/finance-copilot-skills](https://github.com/cxtx/finance-copilot-skills) | 中文、已有Agent内财务工作流、确定性程序与人工复核 | 当前已发布方向为对账Preview；明确不提供会计政策判断 | 财务受众及工程原则重合，核心业务互补 |

## 4. 逐项证据和可借鉴点

### rag_for_accounting

[README原文](https://raw.githubusercontent.com/dongtan-91-dong-welfare-center/rag_for_accounting/main/README.md)明确当前基于K-GAAP，回答确认、计量、披露等问题，并返回条文与引用；列出问题改写、检索、重排、质量评估及生成流程，也有CLI/API/MCP/Skill入口。

它没有默认提供原始准则数据，要求用户自行准备；README声明非商业用途。不能因为代码公开就直接照搬数据或商用。

可借鉴：共享的回答/引用结构、依据不足时重检索、原文定位和自带资料方式。不能据README宣称其质量高于或低于本库，也没有理由为追求类似形态就立即改用其基础设施。

### chwezi-accounting-doctrine

[README原文](https://raw.githubusercontent.com/peterbamuhigire/chwezi-accounting-doctrine/main/README.md)列出会计处理分析和判断备忘录，要求报告基础、来源记录、审计线索和人工审核，并覆盖IFRS等框架以及区域税务。

可借鉴：来源登记、未核事项显式标记、人工复核与产物放行条件。应避免照搬并不适用中国企业会计准则的法域知识、安装方式或模型配置。

### cpa-china-2026

[仓库README](https://github.com/yjkj999999/cpa-china-2026)与[SKILL文件](https://github.com/yjkj999999/cpa-china-2026/blob/main/SKILL.md)说明中国CPA六科知识体系，提供会计等专业问答。README声明MIT；本轮未确认教材内容的独立再分发授权。

本轮可见的主要文件是README、SKILL和package信息；没有验证它具有与本项目等价的法规抓取、版本适用和引用校验能力。可参考分类和使用入口，不将考试概览当作当前业务适用的原文依据。

### ValAct_RAG

[README原文](https://raw.githubusercontent.com/DanTCIM/ValAct_RAG/main/README.md)说明寿险估值/精算文档集合，包括US GAAP和IFRS17，回答时展示引用的原始上下文；依赖外部检索、嵌入、重排和模型服务。README声明Apache-2.0。

可借鉴：展示完整引用上下文和专业集合选择。会计体系、资料权限、API费用和业务质量仍需独立评估，不能直接当作中国企业会计处理助手使用。

### finance-copilot-skills

[README原文](https://raw.githubusercontent.com/cxtx/finance-copilot-skills/main/README.md)描述当前对账Skill的Preview状态，区分程序计算、AI引导、人工业务判断，并明确不出会计政策判断。

可借鉴：每个能力单独列成熟度、平台支持与测试状态；披露输入输出与人工确认。它更适合作为相邻工作流，不作为本库准则判断准确率的对照证据。

## 5. 对开源定位的影响

建议公开介绍：

> 本项目聚焦执行中国企业会计准则的业务处理研究，在用户已有AI客户端中，通过本地资料和规则组织事实识别、候选准则排查、引用及适用条件说明。它不是全能财务系统，也不声称替代专业复核。

差异化应由演示和验收证明，而不是只靠文字：

1. 同一事实是否完整识别相关会计问题，而非单关键词命中？
2. 是否排查有关解释、案例/问答，避免只引一个准则？
3. 摘录和定位能否由人或程序核对？
4. 主体、时点、版本与未知事实是否改变处理分支？
5. 新用户能否在不安装一套平台的情况下完成部署和复核？

本轮搜索结论支持继续筹备，但不支持宣传“首创”“无竞品”或“优于现有RAG”。先完善证据、适用性和最小部署，再通过实际财务用户测试确定价值。

本轮没有引入以上项目代码，它们是研究引用，不是运行依赖。实际复用任何内容前须另查所用版本、许可证和资料授权。
