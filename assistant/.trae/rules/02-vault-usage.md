# laws-vault 使用说明（检索与维护）

## 目录结构

```
cas/    企业会计准则全文（含 30b=2026版列报、25b=已废止原保险合同）
casg/   应用指南汇编（2024）
casi/   准则解释第1-20号
casc/   应用案例
casq/   实施问答
tax/    税法（后续接入 lawtext/laws 财税子集 + fgk 公告层）
policy/ 公司执行办法（内部口径层，引用时与准则两栏分层）
changelog/  更新管道变更日志（pending-*.md 为待审清单）
scripts/    fetch_maodocs.py（抓取）update_check.py（更新哨兵）overrides.json（人工核实的元数据）
tax/    税法与法律层（tax/lawtext/：法律733+行政法规+司法解释，哈希文件名，按 front-matter title 检索，每周六官方 Actions 自动同步）

## front-matter 字段

`doc_id`（文号=唯一主键）/ `title` / `layer` / `level` / `doc_number` / `year` / `issue_date` / `effective_date` / `status`（六态：有效·尚未生效·已修改·部分废止·已废止·待核）/ `supersedes` / `superseded_by` / `org` / `source_url` / `checked_at`

## 检索模式（优先级从高到低）

1. **精确文号**：`grep -r "财会〔2026〕11号" .`
2. **条文定位**：在具体文件内 `grep -n "第X条" cas/14.md`
3. **主题+过滤**：先按准则号路由到 cas/NN.md，再正文检索术语（见 01 规则的映射表）
4. **向量检索**（local-rag MCP 接入后）：语义检索用于口语化问题召回，召回后仍必须回到原文文件核对条号

## 维护流程（每周，约 30 分钟）

```
python scripts/update_check.py          # 三源 diff：MaoDocs 页面哈希 + listing 新链接 + lawtext（接入后）
# 打开 changelog/pending-YYYYMMDD.md → 人工核对每条变更
python scripts/fetch_maodocs.py --layers cas,casi   # 重抓变更页（全量重跑亦安全，幂等覆盖）
git add -A && git commit -m "update $(date +%F)"
```

- `status=待核` 的文件：用 flk-law MCP 或官方源核验后，把确认结果写进 `scripts/overrides.json`（人工确认的事实优先级最高）。
- 新版准则发布 → 旧文件改 `status`（如 已废止/已被修订）+ 填 `superseded_by`，**不删除旧文件**（历史报表问题仍需引用旧版）。

## as-of 时点查询法

问「2026 年报适用哪个版本的 CAS30」：
1. `grep -l "财务报表列报" cas/*.md` → 得 30.md（2014）与 30b.md（2026）
2. 读两文件 front-matter：30b `status: 尚未生效, effective_date: 2027-01-01, scope_note: 境内外同时上市先行`
3. 结论：2026 年报 → 2014 版；同时提示 2026 版存在及分批生效安排
